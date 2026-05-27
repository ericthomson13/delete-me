"""End-to-end FastAPI tests against an in-memory SQLite DB.

These exercise the same code paths the CLI uses (delete_me.cases) so a green
test suite proves both surfaces work.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DELETE_ME_DB_URL", f"sqlite:///{tmp_path / 'test.db'}")
    # Force a fresh import so create_app() uses the test DB URL.
    import importlib

    import service.app as service_app

    importlib.reload(service_app)
    return TestClient(service_app.create_app())


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_brokers_returns_phase_0_ten(client: TestClient):
    r = client.get("/brokers")
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()]
    assert len(ids) >= 10
    assert "spokeo" in ids


def test_create_profile_and_case_and_dry_run_send(client: TestClient):
    r = client.post(
        "/profiles",
        json={
            "full_legal_name": "Test User",
            "current_address": "123 Main St, Portland OR 97201",
            "dob_year": 1985,
            "email": "test@example.com",
            "prior_addresses": ["456 Old Rd, Seattle WA 98101"],
        },
    )
    assert r.status_code == 200, r.text
    profile_id = r.json()["id"]

    r = client.post("/cases", json={"profile_id": profile_id, "broker_id": "spokeo"})
    assert r.status_code == 200, r.text
    case = r.json()
    assert case["broker_id"] == "spokeo"
    assert case["status"] == "draft"
    assert "Spokeo" in case["letter_markdown"]
    assert case["agent_designation_markdown"] is not None

    case_id = case["id"]
    r = client.post(f"/cases/{case_id}/send", json={"live": False})
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["result"]["dry_run"] is True
    assert result["case"]["status"] == "sent_dry_run"
    assert result["case"]["audit_due_at"] is not None

    r = client.get("/cases")
    assert r.status_code == 200
    cases = r.json()
    assert any(c["id"] == case_id and c["status"] == "sent_dry_run" for c in cases)


def test_cannot_send_user_submit_only_broker(client: TestClient):
    pr = client.post(
        "/profiles",
        json={
            "full_legal_name": "Another User",
            "current_address": "99 Pine Ave, Boise ID 83702",
        },
    ).json()
    case = client.post(
        "/cases", json={"profile_id": pr["id"], "broker_id": "fastpeoplesearch"}
    ).json()
    r = client.post(f"/cases/{case['id']}/send", json={"live": False})
    assert r.status_code == 400
    assert "user-submit-only" in r.json()["detail"]


def test_audit_endpoint_marks_noncompliant(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Audit endpoint with a mock adapter aliased to the broker's audit_source."""
    monkeypatch.setenv("DELETE_ME_AUDIT_USE_MOCK", "true")

    from delete_me.audit import MockAuditAdapter, found_fixture
    from service.api import audits as audits_module

    monkeypatch.setattr(
        audits_module,
        "default_registry",
        lambda: {
            "spokeo_search": MockAuditAdapter(
                source_id="spokeo_search",
                fixtures={"audit user": found_fixture()},
                inconclusive_for_unknown=False,
            )
        },
    )

    pr = client.post(
        "/profiles",
        json={"full_legal_name": "Audit User", "current_address": "1 First St, Portland, OR"},
    ).json()
    case = client.post(
        "/cases", json={"profile_id": pr["id"], "broker_id": "spokeo"}
    ).json()

    r = client.post(f"/cases/{case['id']}/audit")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["case"]["status"] == "noncompliant"
    assert len(body["results"]) == 1
    assert body["results"][0]["found"] is True

    r = client.get(f"/cases/{case['id']}/audits")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_drop_submit_404_on_unknown_profile(client: TestClient):
    r = client.post("/drop/submit", json={"profile_id": 999, "live": False})
    assert r.status_code == 404


def test_drop_submit_happy_path(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    # Make the DROP transport write its dry-run payloads into tmp_path so we
    # don't touch the user's data dir during tests.
    monkeypatch.setenv("DELETE_ME_DROP_OUT", str(tmp_path / "drop"))

    # Stand up a DROP-eligible broker via monkeypatch — none of the real
    # registry entries have calprivacy_id populated yet.
    from delete_me import cases as cases_mod

    from tests.test_drop_transport import fixture_drop_broker  # noqa: E402

    monkeypatch.setattr(
        cases_mod, "load_brokers", lambda: [fixture_drop_broker("alpha", "DB-A-001")]
    )

    r = client.post(
        "/profiles",
        json={
            "full_legal_name": "CA Resident",
            "current_address": "100 Market St, San Francisco CA 94105",
            "dob_year": 1990,
            "email": "ca@example.com",
        },
    )
    assert r.status_code == 200, r.text
    profile_id = r.json()["id"]

    r = client.post("/drop/submit", json={"profile_id": profile_id, "live": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["receipt"]["dry_run"] is True
    assert body["receipt"]["broker_calprivacy_ids"] == ["DB-A-001"]
    assert len(body["cases"]) == 1
    assert body["cases"][0]["status"] == "sent_via_drop"
    assert body["cases"][0]["transport_message_id"] == body["receipt"]["receipt_id"]


# ---------------------------------------------------------------- presence-check

def _seed_profile(client: TestClient, email: str = "jane@example.com") -> int:
    r = client.post(
        "/profiles",
        json={
            "full_legal_name": "Jane Q. Doe",
            "current_address": "123 Main St, Portland OR 97201",
            "email": email,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_presence_check_persists_results(client: TestClient, monkeypatch):
    """Force the mock adapter registry so we don't hit the network."""
    monkeypatch.setenv("DELETE_ME_AUDIT_USE_MOCK", "1")
    profile_id = _seed_profile(client)

    # With every broker having audit_sources=[] OR sources the mock registry
    # doesn't know about, the response should still be 200 with a summary.
    r = client.post(f"/profiles/{profile_id}/presence-check", json={"broker_ids": ["spokeo"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "results" in body and "summary" in body
    assert body["summary"]["brokers_checked"] == 1


def test_presence_check_unknown_broker_400(client: TestClient, monkeypatch):
    monkeypatch.setenv("DELETE_ME_AUDIT_USE_MOCK", "1")
    profile_id = _seed_profile(client)
    r = client.post(
        f"/profiles/{profile_id}/presence-check",
        json={"broker_ids": ["does-not-exist"]},
    )
    assert r.status_code == 400
    assert "does-not-exist" in r.text


def test_presence_check_404_for_missing_profile(client: TestClient, monkeypatch):
    monkeypatch.setenv("DELETE_ME_AUDIT_USE_MOCK", "1")
    r = client.post("/profiles/9999/presence-check", json={})
    assert r.status_code == 404


def test_list_presence_results_empty_then_populated(client: TestClient, monkeypatch):
    monkeypatch.setenv("DELETE_ME_AUDIT_USE_MOCK", "1")
    profile_id = _seed_profile(client)

    r = client.get(f"/profiles/{profile_id}/presence-results")
    assert r.status_code == 200
    assert r.json() == []

    client.post(f"/profiles/{profile_id}/presence-check", json={"broker_ids": ["spokeo"]})

    r = client.get(f"/profiles/{profile_id}/presence-results")
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ------------------------------------------------------------ breach + password

def test_breaches_providers_lists_all_three(client: TestClient, monkeypatch):
    for var in ("HIBP_API_KEY", "INTELX_API_KEY", "DEHASHED_USERNAME", "DEHASHED_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    r = client.get("/breaches/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["active"] == []
    source_ids = {p["source_id"] for p in body["providers"]}
    assert source_ids == {"hibp", "intelx", "dehashed"}
    assert all(not p["available"] for p in body["providers"])


def test_breach_check_503_when_no_providers(client: TestClient, monkeypatch):
    for var in ("HIBP_API_KEY", "INTELX_API_KEY", "DEHASHED_USERNAME", "DEHASHED_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    profile_id = _seed_profile(client)
    r = client.post(f"/profiles/{profile_id}/breach-check", json={})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["error"] == "no breach providers configured"
    assert {p["source_id"] for p in detail["providers"]} == {"hibp", "intelx", "dehashed"}


def test_breach_check_with_mock_provider(client: TestClient, monkeypatch):
    """Configure HIBP via env + monkeypatch its httpx client to a stub."""
    import httpx
    from delete_me.breaches import hibp as hibp_mod

    monkeypatch.setenv("HIBP_API_KEY", "test-key")
    monkeypatch.delenv("INTELX_API_KEY", raising=False)
    monkeypatch.delenv("DEHASHED_USERNAME", raising=False)
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)

    class _Stub:
        def get(self, url, params=None):
            import json as _json
            return httpx.Response(
                status_code=200,
                content=_json.dumps([{
                    "Name": "Adobe",
                    "BreachDate": "2013-10-04",
                    "DataClasses": ["Email addresses"],
                    "Description": "A breach.",
                }]).encode(),
                request=httpx.Request("GET", url),
            )

    real_init = hibp_mod.HIBPAdapter.__init__

    def _patched(self, api_key=None, client=None):
        real_init(self, api_key=api_key or "test-key", client=_Stub())

    monkeypatch.setattr(hibp_mod.HIBPAdapter, "__init__", _patched)

    profile_id = _seed_profile(client)
    r = client.post(f"/profiles/{profile_id}/breach-check", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["providers"]["active"] == ["hibp"]
    skipped = {s["source_id"] for s in body["providers"]["skipped_at_startup"]}
    assert skipped == {"intelx", "dehashed"}
    rows = next(iter(body["results"].values()))
    assert rows[0]["breach_name"] == "Adobe"


def test_password_check(client: TestClient, monkeypatch):
    import hashlib

    import httpx
    from delete_me.breaches import passwords as passwords_mod

    sha1 = hashlib.sha1(b"hunter2").hexdigest().upper()
    suffix = sha1[5:]

    class _Stub:
        def get(self, url):
            return httpx.Response(
                status_code=200,
                content=f"{suffix}:99\n".encode(),
                request=httpx.Request("GET", url),
            )

    real_init = passwords_mod.PwnedPasswordsClient.__init__

    def _patched(self, client=None):
        real_init(self, client=_Stub())

    monkeypatch.setattr(passwords_mod.PwnedPasswordsClient, "__init__", _patched)

    r = client.post("/passwords/check", json={"password": "hunter2"})
    assert r.status_code == 200
    assert r.json() == {"breach_count": 99, "found": True}
