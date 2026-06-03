"""CLI tests for the discovery commands (presence-check, breach-check,
password-check).

These tests exercise Click's command surface end-to-end via CliRunner,
catching wiring bugs that unit tests on the orchestrators miss (e.g., env
var plumbing, exit codes, output shape). The CLI uses DELETE_ME_DB_URL to
point at a per-test SQLite file, so the tests don't touch the user's data
directory.
"""

from __future__ import annotations

import json

import httpx
import pytest
from click.testing import CliRunner
from delete_me.breaches import passwords as passwords_mod
from delete_me.cli.main import main


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Per-test tmp DB; no breach provider env vars unless a test sets them."""
    db = tmp_path / "cli.sqlite3"
    monkeypatch.setenv("DELETE_ME_DB_URL", f"sqlite:///{db}")
    for var in ("HIBP_API_KEY", "INTELX_API_KEY", "DEHASHED_USERNAME", "DEHASHED_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    return {"db": db}


def _seed_profile(runner: CliRunner) -> None:
    result = runner.invoke(main, [
        "init",
        "--name", "Jane Q. Doe",
        "--address", "123 Main St, Portland, OR 97201",
        "--email", "jane@example.com",
    ])
    assert result.exit_code == 0, result.output
    # init writes profile.json to cwd; case-create persists the profile to the DB.
    result = runner.invoke(main, ["db-init"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(main, ["case-create", "--broker", "spokeo"])
    assert result.exit_code == 0, result.output


def test_presence_check_without_profile_errors_cleanly(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["presence-check"])
        assert result.exit_code == 2
        assert "no profile in DB" in result.output


def test_presence_check_with_profile_runs_and_shows_footer(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        # --broker spokeo: spokeo has audit_sources=[] today, so the result
        # is one "(none)" sentinel row and the footer notes the gap.
        result = runner.invoke(main, ["presence-check", "--broker", "spokeo"])
        assert result.exit_code == 0, result.output
        assert "no-audit-source" in result.output


def _seed_second_profile(runner: CliRunner) -> None:
    """Add a second profile to the same DB so --all-profiles has multiple targets."""
    from delete_me.cases import upsert_profile
    from delete_me.db.session import get_session, init_db
    init_db()
    from delete_me.letters.engine import ConsumerProfile

    with get_session() as session:
        upsert_profile(
            session,
            ConsumerProfile(
                full_legal_name="Bob T. Tester",
                current_address="456 Pine Rd, Salem, OR 97301",
                email="bob@example.com",
            ),
        )


def test_presence_check_profile_id_targets_specific(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        _seed_second_profile(runner)
        result = runner.invoke(
            main, ["presence-check", "--profile-id", "1", "--broker", "spokeo", "--json"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert list(payload["by_profile"].keys()) == ["1"]
        assert payload["by_profile"]["1"]["profile_name"] == "Jane Q. Doe"


def test_presence_check_unknown_profile_id_errors(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        result = runner.invoke(
            main, ["presence-check", "--profile-id", "999", "--broker", "spokeo"]
        )
        assert result.exit_code == 2
        assert "profile 999 not found" in result.output


def test_presence_check_all_profiles_iterates(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        _seed_second_profile(runner)
        result = runner.invoke(
            main, ["presence-check", "--all-profiles", "--broker", "spokeo", "--json"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert set(payload["by_profile"].keys()) == {"1", "2"}
        names = {entry["profile_name"] for entry in payload["by_profile"].values()}
        assert names == {"Jane Q. Doe", "Bob T. Tester"}


def test_cases_from_presence_drafts_for_found_brokers(cli_env):
    """Seed PresenceResult rows directly, then assert the CLI drafts only
    for brokers where the latest row per source has found=True."""
    from datetime import UTC, datetime

    from delete_me.cases import upsert_profile
    from delete_me.db import PresenceResult
    from delete_me.db.session import get_session, init_db
    init_db()
    from delete_me.letters.engine import ConsumerProfile

    with get_session() as session:
        profile = upsert_profile(session, ConsumerProfile(
            full_legal_name="Jane Q. Doe",
            current_address="123 Main St, Portland, OR 97201",
            email="jane@example.com",
        ))
        now = datetime.now(UTC)
        # spokeo: found  → should be drafted
        # whitepages: not found → skip
        # truepeoplesearch: found via two sources, one True one False with True newer → drafted
        session.add(PresenceResult(
            profile_id=profile.id, broker_id="spokeo", source="spokeo_search",
            checked_at=now, found=True, inconclusive=False,
        ))
        session.add(PresenceResult(
            profile_id=profile.id, broker_id="whitepages", source="whitepages_search",
            checked_at=now, found=False, inconclusive=False,
        ))
        session.commit()

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["cases-from-presence", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        created = [r["broker_id"] for r in payload["rows"] if r["action"] == "created"]
        assert created == ["spokeo"]
        assert payload["summary"]["created"] == 1


def test_cases_from_presence_skips_brokers_with_existing_case(cli_env):
    """If a case already exists for (profile, broker), the command skips it."""
    from datetime import UTC, datetime

    from delete_me.cases import draft_case, upsert_profile
    from delete_me.db import PresenceResult
    from delete_me.db.session import get_session, init_db
    init_db()
    from delete_me.letters.engine import ConsumerProfile

    with get_session() as session:
        profile = upsert_profile(session, ConsumerProfile(
            full_legal_name="Jane Q. Doe",
            current_address="123 Main St, Portland, OR 97201",
            email="jane@example.com",
        ))
        session.add(PresenceResult(
            profile_id=profile.id, broker_id="spokeo", source="spokeo_search",
            checked_at=datetime.now(UTC), found=True, inconclusive=False,
        ))
        # Pre-existing case for spokeo
        draft_case(session, profile, "spokeo")
        session.commit()

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["cases-from-presence", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        actions = {r["broker_id"]: r["action"] for r in payload["rows"]}
        assert actions == {"spokeo": "skipped_existing"}


def test_cases_from_presence_empty_when_nothing_found(cli_env):
    _seed_profile(CliRunner())  # noop without isolated_filesystem; use CLI
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        result = runner.invoke(main, ["cases-from-presence"])
        assert result.exit_code == 0
        assert "No brokers have you currently listed" in result.output


def test_send_all_drafts_iterates_every_draft(cli_env):
    """--all-drafts sends every draft, returns bulk-shaped JSON."""
    from delete_me.cases import draft_case, upsert_profile
    from delete_me.db.session import get_session, init_db
    init_db()
    from delete_me.letters.engine import ConsumerProfile

    with get_session() as session:
        profile = upsert_profile(session, ConsumerProfile(
            full_legal_name="Jane Q. Doe",
            current_address="123 Main St, Portland, OR 97201",
            email="jane@example.com",
        ))
        # Three brokers that each have an email opt-out channel (send-eligible).
        # Whitepages / radaris / truepeoplesearch are web-form-only and would
        # legitimately fail send_case's email-channel check.
        draft_case(session, profile, "spokeo")
        draft_case(session, profile, "intelius")
        draft_case(session, profile, "mylife")
        session.commit()

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["send", "--all-drafts"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["summary"]["total"] == 3
        # All three have email opt-outs → dry-run sends succeed.
        assert payload["summary"]["sent"] == 3, payload
        sent_brokers = {r["broker_id"] for r in payload["sent"]}
        assert sent_brokers == {"spokeo", "intelius", "mylife"}


def test_send_all_drafts_records_send_failures_without_aborting(cli_env):
    """Mixed batch with one send-ineligible broker: the rest still send."""
    from delete_me.cases import draft_case, upsert_profile
    from delete_me.db.session import get_session, init_db
    from delete_me.letters.engine import ConsumerProfile

    init_db()
    with get_session() as session:
        profile = upsert_profile(session, ConsumerProfile(
            full_legal_name="Jane Q. Doe",
            current_address="123 Main St, Portland, OR 97201",
            email="jane@example.com",
        ))
        draft_case(session, profile, "spokeo")        # has email → sends
        draft_case(session, profile, "whitepages")    # web_form only → fails
        session.commit()

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["send", "--all-drafts"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["summary"]["total"] == 2
        assert payload["summary"]["sent"] == 1
        assert payload["summary"]["failed"] == 1
        assert payload["failed"][0]["broker_id"] == "whitepages"
        assert "email opt-out" in payload["failed"][0]["error"]


def test_send_requires_case_or_all_drafts(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        result = runner.invoke(main, ["send"])
        assert result.exit_code == 2
        assert "--case" in result.output and "--all-drafts" in result.output


def test_send_case_and_all_drafts_conflict(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        result = runner.invoke(main, ["send", "--case", "1", "--all-drafts"])
        assert result.exit_code == 2
        assert "mutually exclusive" in result.output


def test_send_all_drafts_filtered_by_profile_id(cli_env):
    from delete_me.cases import draft_case, upsert_profile
    from delete_me.db.session import get_session, init_db
    init_db()
    from delete_me.letters.engine import ConsumerProfile

    with get_session() as session:
        jane = upsert_profile(session, ConsumerProfile(
            full_legal_name="Jane Q. Doe",
            current_address="123 Main St, Portland, OR 97201",
            email="jane@example.com",
        ))
        bob = upsert_profile(session, ConsumerProfile(
            full_legal_name="Bob T. Tester",
            current_address="456 Pine Rd, Salem, OR 97301",
            email="bob@example.com",
        ))
        draft_case(session, jane, "spokeo")
        draft_case(session, bob, "intelius")
        session.commit()
        jane_id = jane.id  # capture before the session closes

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["send", "--all-drafts", "--profile-id", str(jane_id)]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        # Only jane's draft (spokeo) gets sent
        assert payload["summary"]["total"] == 1
        assert payload["sent"][0]["broker_id"] == "spokeo"


def test_presence_check_all_profiles_and_profile_id_conflict(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        result = runner.invoke(
            main, ["presence-check", "--all-profiles", "--profile-id", "1"]
        )
        assert result.exit_code == 2
        assert "mutually exclusive" in result.output


def test_breach_check_with_no_providers_lists_all_setup_hints(cli_env):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["breach-check"])
        assert result.exit_code == 2
        assert "no providers configured" in result.output
        # Every supported provider must be named with its setup hint.
        assert "[hibp]" in result.output and "HIBP_API_KEY" in result.output
        assert "[intelx]" in result.output and "INTELX_API_KEY" in result.output
        assert "[dehashed]" in result.output and "DEHASHED_USERNAME" in result.output


def test_breach_check_json_output_shape(cli_env, monkeypatch):
    """With one provider configured (mocked at the httpx layer), --json
    returns the documented structure: results map + providers metadata."""
    from delete_me.breaches import hibp as hibp_mod

    monkeypatch.setenv("HIBP_API_KEY", "test-key")

    class _StubClient:
        def get(self, url, params=None):
            return httpx.Response(
                status_code=200,
                content=json.dumps([{
                    "Name": "Adobe",
                    "BreachDate": "2013-10-04",
                    "DataClasses": ["Email addresses"],
                    "Description": "A breach.",
                }]).encode(),
                request=httpx.Request("GET", url),
            )

    # Patch HIBPAdapter to ignore the env-driven client and use our stub.
    real_init = hibp_mod.HIBPAdapter.__init__

    def _patched_init(self, api_key=None, client=None):
        real_init(self, api_key=api_key or "test-key", client=_StubClient())

    monkeypatch.setattr(hibp_mod.HIBPAdapter, "__init__", _patched_init)

    runner = CliRunner()
    with runner.isolated_filesystem():
        _seed_profile(runner)
        result = runner.invoke(main, ["breach-check", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "results" in payload and "providers" in payload
        assert payload["providers"]["active"] == ["hibp"]
        # IntelX and DeHashed should be in skipped_at_startup with their hints.
        skipped_ids = {s["source_id"] for s in payload["providers"]["skipped_at_startup"]}
        assert skipped_ids == {"intelx", "dehashed"}
        rows = next(iter(payload["results"].values()))
        assert rows[0]["breach_name"] == "Adobe"


def test_password_check_stdin_found(cli_env, monkeypatch):
    """Pipe a password in; mock the HIBP range endpoint to report a match."""
    import hashlib

    sha1 = hashlib.sha1(b"hunter2").hexdigest().upper()
    suffix = sha1[5:]
    body = f"{suffix}:1234\n"

    class _StubClient:
        def get(self, url):
            return httpx.Response(
                status_code=200, content=body.encode(),
                request=httpx.Request("GET", url),
            )

    real_init = passwords_mod.PwnedPasswordsClient.__init__

    def _patched_init(self, client=None):
        real_init(self, client=_StubClient())

    monkeypatch.setattr(passwords_mod.PwnedPasswordsClient, "__init__", _patched_init)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["password-check", "--stdin"], input="hunter2\n")
        assert result.exit_code == 1  # found → non-zero exit for scriptability
        assert "FOUND" in result.output
        assert "1,234" in result.output


def test_audit_adapter_health_reports_each_adapter(cli_env, monkeypatch):
    """Replace production_registry with a deterministic mix so we can assert
    the three non-healthy statuses (blocked / false_positive / error) plus
    healthy in one run."""
    from delete_me.audit.orchestrator import production_registry as _prod
    from delete_me.audit.sources.base import AuditAdapter, ListingResult

    class _Healthy(AuditAdapter):
        source_id = "healthy_src"
        def search(self, q):
            return ListingResult(source=self.source_id, found=False, inconclusive=False, notes="ok")

    class _Blocked(AuditAdapter):
        source_id = "blocked_src"
        def search(self, q):
            return ListingResult(source=self.source_id, found=False, inconclusive=True, notes="bot block")

    class _FalsePositive(AuditAdapter):
        source_id = "fp_src"
        def search(self, q):
            return ListingResult(source=self.source_id, found=True, inconclusive=False, notes="matched something")

    class _Boom(AuditAdapter):
        source_id = "boom_src"
        def search(self, q):
            raise RuntimeError("kapow")

    fake = {
        "healthy_src": _Healthy(),
        "blocked_src": _Blocked(),
        "fp_src": _FalsePositive(),
        "boom_src": _Boom(),
    }
    # Patch in cli.main's namespace too — the command imports locally.
    monkeypatch.setattr(
        "delete_me.audit.orchestrator.production_registry", lambda: fake
    )

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["audit-adapter-health", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        statuses = {r["source_id"]: r["status"] for r in payload["rows"]}
        assert statuses == {
            "healthy_src": "healthy",
            "blocked_src": "blocked",
            "fp_src": "false_positive",
            "boom_src": "error",
        }
        # Every row must carry broker_id (may be None for unregistered sources)
        # so the followup script can bump the right YAML.
        assert all("broker_id" in r for r in payload["rows"])


def test_password_check_stdin_not_found(cli_env, monkeypatch):
    class _StubClient:
        def get(self, url):
            return httpx.Response(
                status_code=200, content=b"DEAD:0\n",
                request=httpx.Request("GET", url),
            )

    real_init = passwords_mod.PwnedPasswordsClient.__init__

    def _patched_init(self, client=None):
        real_init(self, client=_StubClient())

    monkeypatch.setattr(passwords_mod.PwnedPasswordsClient, "__init__", _patched_init)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main, ["password-check", "--stdin"], input="unique-test-password-xyz\n"
        )
        assert result.exit_code == 0
        assert "not found" in result.output
