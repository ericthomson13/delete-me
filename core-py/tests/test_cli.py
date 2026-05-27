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
