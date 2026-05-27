"""delete-me CLI — Phase 0 entry point.

Commands:
  delete-me init           Capture a consumer profile to a local JSON file.
  delete-me letters        Generate letters for one or more brokers.
  delete-me validate-registry
                           Validate every broker YAML against the schema.
  delete-me list-brokers   Print the registry inventory.

Phase 0 deliberately keeps state on local disk only. No network calls.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click
import jsonschema
from pydantic import ValidationError
from sqlmodel import select

from delete_me.agent_form import generate_designation
from delete_me.audit import AuditOrchestrator, PresenceOrchestrator, latest_for_broker
from delete_me.audit.orchestrator import production_registry
from delete_me.cases import (
    case_as_dict,
    draft_case,
    list_cases,
    send_case,
    submit_via_drop,
    upsert_profile,
)
from delete_me.db import Case, Profile
from delete_me.db.session import default_db_url, get_session, init_db
from delete_me.evidence import PackageBuilder
from delete_me.letters import LetterEngine
from delete_me.letters.engine import ConsumerProfile
from delete_me.registry import load_brokers, load_statutes
from delete_me.registry.loader import cross_check, validate_broker_file
from delete_me.transport import DropTransport, PostmarkTransport
from delete_me.transport.base import TransportError


@click.group()
@click.version_option(package_name="delete-me", prog_name="delete-me")
def main() -> None:
    """delete-me — open-source data-broker letter generator + DROP auditor."""


@main.command()
@click.option("--name", required=True, help="Your full legal name.")
@click.option("--address", required=True, help="Your current address as one line.")
@click.option("--email", default=None)
@click.option("--phone", default=None)
@click.option("--dob-year", type=int, default=None, help="Your year of birth (4 digits).")
@click.option(
    "--prior-address",
    "prior_addresses",
    multiple=True,
    help="Repeat for each prior address you want included.",
)
@click.option(
    "--former-name",
    "former_names",
    multiple=True,
    help="Repeat for each prior legal name.",
)
@click.option(
    "--profile",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("./profile.json"),
    show_default=True,
)
def init(
    name: str,
    address: str,
    email: str | None,
    phone: str | None,
    dob_year: int | None,
    prior_addresses: tuple[str, ...],
    former_names: tuple[str, ...],
    profile: Path,
) -> None:
    """Capture a consumer profile to a local JSON file. No network calls."""
    p = ConsumerProfile(
        full_legal_name=name,
        current_address=address,
        email=email,
        phone=phone,
        dob_year=dob_year,
        prior_addresses=tuple(prior_addresses),
        former_names=tuple(former_names),
    )
    profile.write_text(json.dumps(asdict(p), indent=2), encoding="utf-8")
    click.echo(f"Wrote profile to {profile}")
    click.echo(
        "This file contains your PII. delete-me does not transmit it anywhere "
        "unless you explicitly run a send command in a later phase."
    )


def _load_profile(path: Path) -> ConsumerProfile:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["prior_addresses"] = tuple(raw.get("prior_addresses") or ())
    raw["former_names"] = tuple(raw.get("former_names") or ())
    return ConsumerProfile(**raw)


@main.command()
@click.option(
    "--profile",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("./profile.json"),
    show_default=True,
)
@click.option(
    "--brokers",
    required=True,
    help=(
        "Comma-separated broker ids (e.g., spokeo,whitepages,intelius). "
        "Use 'all' for every broker."
    ),
)
@click.option(
    "--output",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./out"),
    show_default=True,
)
@click.option("--pdf/--no-pdf", default=False, help="Also render PDFs (requires WeasyPrint deps).")
@click.option(
    "--include-agent-form/--no-agent-form",
    default=True,
    help="Also generate the authorized-agent designation in the output dir.",
)
def letters(
    profile: Path,
    brokers: str,
    output: Path,
    pdf: bool,
    include_agent_form: bool,
) -> None:
    """Generate letters for one or more brokers."""
    consumer = _load_profile(profile)
    all_brokers = {b.id: b for b in load_brokers()}
    statutes = load_statutes()

    selected_ids: list[str]
    if brokers.strip() == "all":
        selected_ids = sorted(all_brokers)
    else:
        selected_ids = [s.strip() for s in brokers.split(",") if s.strip()]
        unknown = [bid for bid in selected_ids if bid not in all_brokers]
        if unknown:
            click.echo(f"Unknown broker id(s): {', '.join(unknown)}", err=True)
            sys.exit(2)

    engine = LetterEngine(render_pdf=pdf)
    output.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for bid in selected_ids:
        rendered = engine.render(all_brokers[bid], consumer, statutes)
        written.append(engine.write_markdown(rendered, output))
        if pdf:
            try:
                written.append(engine.write_pdf(rendered, output))
            except (ImportError, OSError) as exc:
                click.echo(
                    f"PDF render failed for {bid}: {exc}. Markdown was still written.",
                    err=True,
                )

    if include_agent_form:
        designation = generate_designation(consumer, selected_ids)
        written.append(designation.write(output))

    for path in written:
        click.echo(f"Wrote {path}")

    user_submit_only = [
        bid for bid in selected_ids if all_brokers[bid].user_submit_only
        or not all_brokers[bid].accepts_authorized_agent
    ]
    if user_submit_only:
        click.echo(
            "\nNote: these brokers do not accept authorized-agent letters; you "
            "must submit them yourself: " + ", ".join(user_submit_only)
        )


@main.command("validate-registry")
def validate_registry() -> None:
    """Validate every broker YAML against the JSON schema and cross-check statutes."""
    from delete_me.paths import brokers_dir

    paths = sorted(brokers_dir().glob("*.yaml"))
    if not paths:
        click.echo("No broker files found.", err=True)
        sys.exit(1)

    errors: list[str] = []
    brokers = []
    for path in paths:
        try:
            brokers.append(validate_broker_file(path))
            click.echo(f"ok   {path.name}")
        except (jsonschema.ValidationError, ValidationError, ValueError) as exc:
            click.echo(f"FAIL {path.name}: {exc}", err=True)
            errors.append(path.name)

    statutes = load_statutes()
    cross_errors = cross_check(brokers, statutes)
    for e in cross_errors:
        click.echo(f"cross-check FAIL: {e}", err=True)

    if errors or cross_errors:
        sys.exit(1)
    click.echo(f"\n{len(brokers)} broker(s) valid, {len(statutes)} statute(s) loaded.")


@main.command("list-brokers")
def list_brokers() -> None:
    """Print the registry inventory."""
    for b in load_brokers():
        tier = b.tier or "—"
        agent = "agent" if b.accepts_authorized_agent and not b.user_submit_only else "user-submit"
        click.echo(f"{b.id:24}  {tier:22}  {agent:12}  {b.name}")


@main.command("db-init")
def db_init() -> None:
    """Create local case-tracking tables if they don't exist. Idempotent."""
    init_db()
    click.echo(f"DB ready at {default_db_url()}")


@main.command("case-create")
@click.option(
    "--profile",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("./profile.json"),
    show_default=True,
)
@click.option("--broker", "broker_id", required=True)
def case_create(profile: Path, broker_id: str) -> None:
    """Persist a profile, generate a letter for one broker, and store a Case."""
    init_db()
    consumer = _load_profile(profile)
    with get_session() as session:
        p = upsert_profile(session, consumer)
        try:
            case, designation = draft_case(session, p, broker_id)
        except ValueError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(2)
        click.echo(
            f"case #{case.id} drafted for broker={case.broker_id} profile_id={p.id}"
        )
        if designation:
            click.echo(f"agent designation sha256: {designation.document_sha256}")


@main.command("cases")
def cases_list() -> None:
    """List local cases (most recent first)."""
    init_db()
    with get_session() as session:
        items = sorted(list_cases(session), key=lambda c: c.created_at, reverse=True)
        if not items:
            click.echo("(no cases)")
            return
        for c in items:
            sent = c.sent_at.strftime("%Y-%m-%d") if c.sent_at else "—"
            click.echo(
                f"#{c.id:<4} {c.broker_id:24}  status={c.status.value:18}  sent={sent}"
            )


@main.command("send")
@click.option("--case", "case_id", required=True, type=int)
@click.option(
    "--live/--dry-run",
    default=False,
    help="Live send requires POSTMARK_SERVER_TOKEN. Dry-run by default.",
)
@click.option(
    "--check-first/--no-check-first",
    default=False,
    help=(
        "Run presence-check against the broker before sending. Skips the "
        "send if every configured audit source reports found=False. "
        "Inconclusive sources are treated as 'send anyway'."
    ),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="With --check-first, send even if presence reports not-found.",
)
def send_cmd(case_id: int, live: bool, check_first: bool, force: bool) -> None:
    """Send (or dry-run-send) a case's letter via Postmark."""
    init_db()
    transport = PostmarkTransport()
    with get_session() as session:
        case = session.get(Case, case_id)
        if not case:
            click.echo(f"error: case {case_id} not found", err=True)
            sys.exit(2)

        if check_first:
            broker_brokers = [b for b in load_brokers() if b.id == case.broker_id]
            profile = session.get(Profile, case.profile_id)
            if not profile:
                click.echo(f"error: case {case_id} has no profile", err=True)
                sys.exit(2)
            orch = PresenceOrchestrator.from_registry(production_registry())
            presence = orch.check_profile(session, profile, brokers=broker_brokers)
            if not _should_send(presence, force=force):
                click.echo(json.dumps({
                    "skipped": True,
                    "case_id": case_id,
                    "reason": "presence-check returned not-found for every configured source; pass --force to send anyway",
                    "presence": [_presence_row(r) for r in presence],
                }, indent=2))
                return

        try:
            result = send_case(session, case, transport, live=live)
        except ValueError as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(2)

        click.echo(json.dumps({"case": case_as_dict(case), "dry_run": result.dry_run}, indent=2))


def _should_send(presence, *, force: bool) -> bool:
    """Skip only if every real source returned found=False with no inconclusives.

    "(none)" sentinel rows (broker has no audit_sources) are ignored — we
    can't draw a conclusion from them either way, so they fall back to send.
    """
    if force:
        return True
    real = [r for r in presence if r.source != "(none)"]
    if not real:
        return True  # nothing to check against; default to send
    if any(r.found for r in real):
        return True
    if any(r.inconclusive for r in real):
        return True
    return False  # every real source said not-found


def _presence_row(r) -> dict:
    if r.found:
        status = "FOUND"
    elif r.inconclusive:
        status = "inconclusive"
    else:
        status = "not found"
    return {
        "broker_id": r.broker_id,
        "source": r.source,
        "status": status,
        "listings_url": r.listings_url,
        "notes": r.notes,
        "checked_at": r.checked_at.isoformat() if r.checked_at else None,
    }


@main.command("drop-submit")
@click.option(
    "--profile",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("./profile.json"),
    show_default=True,
    help="Profile JSON written by `delete-me init`.",
)
@click.option(
    "--live/--dry-run",
    default=False,
    help=(
        "Live submit requires CALPRIVACY_DROP_ENDPOINT + CALPRIVACY_DROP_TOKEN. "
        "Dry-run writes the submission JSON to $DELETE_ME_DROP_OUT and returns a "
        "synthetic receipt."
    ),
)
def drop_submit_cmd(profile: Path, live: bool) -> None:
    """Submit a CalPrivacy DROP deletion request covering all drop_registered brokers."""
    init_db()
    consumer = _load_profile(profile)
    transport = DropTransport()
    with get_session() as session:
        p = upsert_profile(session, consumer)
        try:
            receipt, cases = submit_via_drop(session, p, transport, live=live)
        except (TransportError, ValueError) as exc:
            click.echo(f"error: {exc}", err=True)
            sys.exit(2)

        click.echo(
            json.dumps(
                {
                    "receipt_id": receipt.receipt_id,
                    "dry_run": receipt.dry_run,
                    "on_disk_path": str(receipt.on_disk_path)
                    if receipt.on_disk_path
                    else None,
                    "broker_count": len(cases),
                    "case_ids": [c.id for c in cases],
                },
                indent=2,
            )
        )


@main.command("audit")
@click.option("--case", "case_id", required=True, type=int)
def audit_cmd(case_id: int) -> None:
    """Run the audit pipeline immediately against one case."""
    init_db()
    orch = AuditOrchestrator.from_registry(production_registry())
    with get_session() as session:
        case = session.get(Case, case_id)
        if not case:
            click.echo(f"error: case {case_id} not found", err=True)
            sys.exit(2)
        results = orch.audit_case(session, case)
    click.echo(
        json.dumps(
            {
                "case": case_as_dict(case),
                "results": [
                    {
                        "source": r.source,
                        "found": r.found,
                        "inconclusive": r.inconclusive,
                        "listings_url": r.listings_url,
                        "notes": r.notes,
                    }
                    for r in results
                ],
            },
            indent=2,
        )
    )


@main.command("presence-check")
@click.option(
    "--broker",
    "broker_id",
    default=None,
    help="Check just this broker. Default: every broker with audit_sources.",
)
@click.option(
    "--fresh-days",
    type=int,
    default=7,
    show_default=True,
    help="Reuse a stored PresenceResult if it's newer than this many days.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def presence_check_cmd(broker_id: str | None, fresh_days: int, as_json: bool) -> None:
    """Check which brokers actually list this consumer (pre-send discovery).

    Requires a profile in the DB (run `case-create` once or `init` + `case-create`).
    Only hits brokers whose YAML lists at least one audit_source adapter — most
    broker YAMLs have no consumer-facing search and will show in the coverage
    footer instead.
    """
    init_db()
    all_brokers = load_brokers()
    if broker_id is not None:
        selected = [b for b in all_brokers if b.id == broker_id]
        if not selected:
            click.echo(f"error: unknown broker {broker_id!r}", err=True)
            sys.exit(2)
    else:
        selected = all_brokers

    orch = PresenceOrchestrator.from_registry(production_registry())
    with get_session() as session:
        profile = session.exec(select(Profile)).first()
        if profile is None:
            click.echo(
                "error: no profile in DB. Run `delete-me init` then `delete-me case-create` "
                "(or any command that persists a profile) first.",
                err=True,
            )
            sys.exit(2)
        results = orch.check_profile(session, profile, brokers=selected, fresh_days=fresh_days)

    no_source_count = sum(1 for r in results if r.source == "(none)")
    found_count = sum(1 for r in results if r.found)
    notfound_count = sum(1 for r in results if not r.found and not r.inconclusive and r.source != "(none)")
    incon_count = sum(1 for r in results if r.inconclusive and r.source != "(none)")

    if as_json:
        click.echo(json.dumps({
            "results": [_presence_row(r) for r in results],
            "summary": {
                "found": found_count,
                "not_found": notfound_count,
                "inconclusive": incon_count,
                "no_audit_source_configured": no_source_count,
            },
        }, indent=2))
        return

    if not results:
        click.echo("(no brokers to check)")
        return
    for r in results:
        if r.source == "(none)":
            continue
        if r.found:
            marker = "FOUND"
        elif r.inconclusive:
            marker = "incn "
        else:
            marker = "miss "
        url = r.listings_url or ""
        click.echo(f"{marker}  {r.broker_id:24}  {r.source:30}  {url}")
    click.echo(
        f"\nfound={found_count}  not-found={notfound_count}  inconclusive={incon_count}  "
        f"no-audit-source={no_source_count} (of {len(selected)} brokers checked)"
    )
    if no_source_count:
        click.echo(
            "Note: brokers without audit_sources can't be presence-checked. "
            "Coverage grows as adapters are added."
        )


@main.command("breach-check")
@click.option(
    "--email",
    "emails",
    multiple=True,
    help="Email to check (repeat). Default: profile.email.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def breach_check_cmd(emails: tuple[str, ...], as_json: bool) -> None:
    """Check whether an email address appears in known breaches.

    Supports multiple providers (HIBP, IntelX, DeHashed). Each is independently
    optional — set the relevant env vars to enable each one. If none are
    configured the command exits with setup hints for every supported provider.
    """
    from delete_me.breaches import BreachOrchestrator, discover_registry

    init_db()
    adapters, statuses = discover_registry()

    if not adapters:
        click.echo("breach-check: no providers configured. Set up at least one:\n", err=True)
        for s in statuses:
            click.echo(f"  [{s.source_id}] {s.detail}", err=True)
        sys.exit(2)

    orch = BreachOrchestrator.from_registry(adapters)
    with get_session() as session:
        profile = session.exec(select(Profile)).first()
        if profile is None:
            click.echo(
                "error: no profile in DB. Run `delete-me init` then `delete-me case-create` first.",
                err=True,
            )
            sys.exit(2)

        targets = list(emails) if emails else ([profile.email] if profile.email else [])
        if not targets:
            click.echo(
                "error: no email to check. Pass --email or set one via `delete-me init --email ...`.",
                err=True,
            )
            sys.exit(2)

        all_results: dict[str, list] = {addr: [] for addr in targets}
        for addr in targets:
            all_results[addr] = orch.check_email(session, profile, addr)

    skipped = [{"source_id": d.source_id, "detail": d.detail} for d in statuses if not d.available]
    runtime = [{"source_id": d.source_id, "detail": d.detail} for d in orch.runtime_disabled]

    if as_json:
        out = {
            "results": {
                addr: [_breach_row(r) for r in rows]
                for addr, rows in all_results.items()
            },
            "providers": {
                "active": [a.source_id for a in orch.adapters],
                "skipped_at_startup": skipped,
                "disabled_mid_run": runtime,
            },
        }
        click.echo(json.dumps(out, indent=2))
        return

    total = 0
    for addr, rows in all_results.items():
        click.echo(f"\n{addr}")
        if not rows:
            click.echo("  (no breaches found)")
            continue
        total += len(rows)
        for r in rows:
            date = r.breach_date or "—"
            click.echo(f"  {date:12}  [{r.source}]  {r.breach_name}")
    click.echo(f"\nTotal exposures: {total} across {len(all_results)} address(es).")
    click.echo(f"Active providers: {', '.join(a.source_id for a in orch.adapters) or '(none)'}")
    if skipped:
        click.echo("\nSkipped at startup (not configured):")
        for s in skipped:
            click.echo(f"  [{s['source_id']}] {s['detail']}")
    if runtime:
        click.echo("\nDisabled mid-run (auth or quota error):")
        for s in runtime:
            click.echo(f"  [{s['source_id']}] {s['detail']}")


def _breach_row(r) -> dict:
    import json as _json
    return {
        "source": r.source,
        "email": r.email,
        "breach_name": r.breach_name,
        "breach_date": r.breach_date,
        "data_classes": _json.loads(r.data_classes_json or "[]"),
        "description_excerpt": r.description_excerpt,
        "checked_at": r.checked_at.isoformat() if r.checked_at else None,
    }


@main.command("password-check")
@click.option(
    "--stdin",
    "from_stdin",
    is_flag=True,
    help="Read the password from stdin instead of prompting. Use for piping; "
         "the password never leaves your shell history this way only if your "
         "source is also history-safe.",
)
def password_check_cmd(from_stdin: bool) -> None:
    """Check whether a password appears in HIBP's breach corpus (k-anonymity).

    No API key, no subscription, no persistence. We SHA-1 the password
    locally and send only the first 5 hex characters of the hash to HIBP;
    the password itself never crosses the wire. Nothing is written to the
    database.
    """
    import httpx

    from delete_me.breaches.passwords import PwnedPasswordsClient

    if from_stdin:
        password = sys.stdin.readline().rstrip("\n")
        if not password:
            click.echo("error: empty password on stdin", err=True)
            sys.exit(2)
    else:
        password = click.prompt("Password", hide_input=True, confirmation_prompt=False)
        if not password:
            click.echo("error: empty password", err=True)
            sys.exit(2)

    try:
        count = PwnedPasswordsClient().lookup(password)
    except httpx.HTTPError as exc:
        click.echo(f"error: pwned-passwords lookup failed: {exc}", err=True)
        sys.exit(3)
    finally:
        # Best-effort: clear our local reference so the password isn't
        # sitting in a long-lived frame after this function returns.
        password = ""  # noqa: F841

    if count == 0:
        click.echo("not found in HIBP's breach corpus")
    else:
        click.echo(f"FOUND — this password has been seen {count:,} time(s) in known breaches")
        click.echo("Treat it as compromised. Change it everywhere you've used it and switch to a password manager.")
        sys.exit(1)


@main.command("evidence")
@click.option("--case", "case_id", required=True, type=int)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./evidence"),
    show_default=True,
)
def evidence_cmd(case_id: int, out_dir: Path) -> None:
    """Build a non-compliance evidence package for one case."""
    init_db()
    out_dir.mkdir(parents=True, exist_ok=True)
    builder = PackageBuilder(out_dir=out_dir)
    with get_session() as session:
        case = session.get(Case, case_id)
        if not case:
            click.echo(f"error: case {case_id} not found", err=True)
            sys.exit(2)
        pkg = builder.build(session, case)
    click.echo(
        json.dumps(
            {
                "case_id": pkg.case_id,
                "directory": str(pkg.directory),
                "zip": str(pkg.zip_path),
                "manifest": str(pkg.manifest_path),
                "file_count": len(pkg.files),
            },
            indent=2,
        )
    )


@main.command("audit-due")
@click.option("--limit", default=20, type=int, show_default=True)
def audit_due_cmd(limit: int) -> None:
    """Run the audit pipeline against every case whose audit_due_at has passed."""
    init_db()
    orch = AuditOrchestrator.from_registry(production_registry())
    summary = []
    with get_session() as session:
        due = orch.cases_due(session, limit=limit)
        for case in due:
            try:
                orch.audit_case(session, case)
            except Exception as exc:  # noqa: BLE001 — keep the sweep going
                click.echo(f"case {case.id}: audit error: {exc}", err=True)
                continue
            summary.append(case_as_dict(case))
    click.echo(json.dumps({"audited": summary, "count": len(summary)}, indent=2))


@main.command("audit-adapter-health")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a human-readable table.")
def audit_adapter_health_cmd(as_json: bool) -> None:
    """Dry-run every audit adapter against a synthetic profile; report status per source.

    Powers a weekly CI workflow that catches adapter regressions when a
    broker changes its HTML. An adapter is "healthy" when it returns a
    real response with inconclusive=False AND found=False for a name that
    cannot exist in any broker's index.
    """
    from datetime import UTC, datetime

    from delete_me.audit.orchestrator import production_registry
    from delete_me.audit.sources.base import AuditQuery

    # Deliberately weird so no broker can legitimately have a match.
    synthetic = AuditQuery(
        full_name="DeleteMe Health-Check ZzzNotARealPerson",
        current_city="Springfield",
        current_state="OR",
        dob_year=None,
    )

    rows: list[dict] = []
    for source_id, adapter in production_registry().items():
        try:
            result = adapter.search(synthetic)
        except Exception as exc:  # noqa: BLE001 — never let an adapter crash the sweep
            rows.append({
                "source_id": source_id,
                "status": "error",
                "notes": f"adapter raised: {exc}",
                "listings_url": None,
            })
            continue

        if result.inconclusive:
            status = "blocked"
        elif result.found:
            # The synthetic name shouldn't match anything; if it does, our
            # name-match heuristic is broken (false positives are dangerous).
            status = "false_positive"
        else:
            status = "healthy"

        rows.append({
            "source_id": source_id,
            "status": status,
            "notes": result.notes,
            "listings_url": result.listings_url,
        })

    if as_json:
        click.echo(json.dumps(
            {"rows": rows, "checked_at": datetime.now(UTC).isoformat()},
            indent=2,
        ))
        return

    if not rows:
        click.echo("No audit adapters wired in production_registry().")
        return
    fail_count = sum(1 for r in rows if r["status"] != "healthy")
    for r in rows:
        marker = "OK  " if r["status"] == "healthy" else "FAIL"
        click.echo(
            f"{marker}  {r['source_id']:30}  {r['status']:14}  {r['notes'] or ''}"
        )
    click.echo(f"\n{len(rows) - fail_count}/{len(rows)} adapters healthy.")


@main.command("automation-health")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a human-readable table.")
@click.option(
    "--screenshot-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=(
        "If set, scripts that return screenshot_bytes in evidence_payload "
        "get them written to <dir>/<broker_id>.png; the JSON output points "
        "at the path instead of carrying raw bytes."
    ),
)
def automation_health_cmd(as_json: bool, screenshot_dir: Path | None) -> None:
    """Dry-run every Tier-A/B automation script; report status per broker.

    Powers the weekly automation-health CI workflow. Also useful locally
    to spot scripts broken by upstream form changes.
    """
    from delete_me.automation import dispatch  # local import keeps base CLI light

    synthetic = ConsumerProfile(
        full_legal_name="Automation Health Synthetic Consumer",
        current_address="1 Test St, Test City, CA 90001",
        email="health-check@example.invalid",
    )
    if screenshot_dir:
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for broker in load_brokers():
        if broker.automation is None or broker.automation.tier == "manual":
            continue
        result = dispatch(broker.id, synthetic, dry_run=True)
        evidence = dict(result.evidence_payload)
        screenshot_path: Path | None = None
        if screenshot_dir and "screenshot_bytes" in evidence:
            screenshot_path = screenshot_dir / f"{broker.id}.png"
            screenshot_path.write_bytes(evidence["screenshot_bytes"])
        # Drop raw bytes from output regardless — they don't belong in JSON.
        evidence.pop("screenshot_bytes", None)
        rows.append({
            "broker_id": broker.id,
            "tier": broker.automation.tier,
            "status": result.status,
            "fallback_reason": result.fallback_reason,
            "screenshot_path": str(screenshot_path) if screenshot_path else None,
            "evidence_payload": evidence,
        })

    if as_json:
        from datetime import UTC, datetime
        click.echo(json.dumps(
            {"rows": rows, "checked_at": datetime.now(UTC).isoformat()},
            indent=2,
        ))
        return

    if not rows:
        click.echo("No brokers with automation.tier in (auto, semi). Nothing to check.")
        return
    fail_count = sum(1 for r in rows if r["status"] != "submitted")
    for r in rows:
        marker = "OK " if r["status"] == "submitted" else "FAIL"
        click.echo(
            f"{marker}  {r['tier']:4}  {r['broker_id']:30}  {r['status']:12}  "
            f"{r['fallback_reason'] or ''}"
        )
    click.echo(f"\n{len(rows) - fail_count}/{len(rows)} scripts healthy.")


@main.command("automation-run")
@click.option("--broker", "broker_id", required=True, help="Broker id (e.g., checkpeople).")
@click.option(
    "--profile",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("./profile.json"),
    show_default=True,
    help="Path to a consumer profile JSON (same shape as `delete-me init` produces).",
)
@click.option(
    "--dry-run/--live",
    default=True,
    show_default=True,
    help=(
        "Dry-run: scripts fill the form and validate selectors but don't submit. "
        "Live: scripts submit for real (Tier A) or wait for user gate-clearance (Tier B). "
        "Use --live only when you're ready for the request to leave your machine."
    ),
)
def automation_run_cmd(broker_id: str, profile: Path, dry_run: bool) -> None:
    """Dispatch a submission for one broker via the tiered automation framework (#8)."""
    from delete_me.automation import dispatch  # local import keeps base CLI light

    consumer = _load_profile(profile)
    result = dispatch(broker_id, consumer, dry_run=dry_run)
    payload = {
        "status": result.status,
        "broker_id": result.broker_id,
        "dry_run": result.dry_run,
        "screenshot_path": str(result.screenshot_path) if result.screenshot_path else None,
        "evidence_payload": result.evidence_payload,
        "fallback_reason": result.fallback_reason,
    }
    click.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
