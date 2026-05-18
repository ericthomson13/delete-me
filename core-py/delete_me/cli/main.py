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

from delete_me.agent_form import generate_designation
from delete_me.letters import LetterEngine
from delete_me.letters.engine import ConsumerProfile
from delete_me.registry import load_brokers, load_statutes
from delete_me.registry.loader import cross_check, validate_broker_file


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


if __name__ == "__main__":  # pragma: no cover
    main()
