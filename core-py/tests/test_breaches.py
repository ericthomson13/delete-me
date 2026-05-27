"""Breach-check tests.

Each adapter is tested by injecting a fake httpx.Client. The real APIs are
never hit. Also covers the multi-provider discovery + mid-run-disable logic
in BreachOrchestrator.
"""

from __future__ import annotations

import json

import httpx
import pytest
from delete_me.breaches import (
    BreachAdapterUnavailable,
    BreachOrchestrator,
    discover_registry,
)
from delete_me.breaches.dehashed import DeHashedAdapter
from delete_me.breaches.hibp import HIBPAdapter
from delete_me.breaches.intelx import IntelXAdapter
from delete_me.breaches.passwords import PwnedPasswordsClient
from delete_me.cases import upsert_profile
from delete_me.db import BreachExposure
from delete_me.db.session import engine_from_url
from delete_me.letters.engine import ConsumerProfile
from sqlmodel import Session, SQLModel, select


@pytest.fixture
def session(tmp_path) -> Session:
    url = f"sqlite:///{tmp_path / 'breaches.db'}"
    engine = engine_from_url(url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _profile(session: Session):
    return upsert_profile(
        session,
        ConsumerProfile(
            full_legal_name="Jane Q. Doe",
            current_address="123 Main St, Portland, OR 97201",
            email="jane@example.invalid",
        ),
    )


class _FakeClient:
    """Stand-in for httpx.Client. Returns the queued response per request.

    Records every call so tests can assert what was sent. Supports both
    .get() (used by HIBP, DeHashed, password range) and .post() (IntelX).
    """

    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict, dict]] = []

    def _take(self, method: str, url: str, params: dict | None, json_body: dict | None) -> httpx.Response:
        self.calls.append((method, url, dict(params or {}), dict(json_body or {})))
        if not self.responses:
            raise AssertionError(f"unexpected extra {method}: {url}")
        return self.responses.pop(0)

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        return self._take("GET", url, params, None)

    def post(self, url: str, json: dict | None = None) -> httpx.Response:  # noqa: A002
        return self._take("POST", url, None, json)


def _response(status: int, body=None, headers: dict | None = None) -> httpx.Response:
    if body is None:
        content = b""
    elif isinstance(body, (dict, list)):
        content = json.dumps(body).encode()
    else:
        content = body.encode() if isinstance(body, str) else body
    return httpx.Response(
        status_code=status,
        content=content,
        headers=headers or {},
        request=httpx.Request("GET", "https://haveibeenpwned.com/test"),
    )


def test_hibp_missing_key_raises_unavailable(monkeypatch):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    with pytest.raises(BreachAdapterUnavailable, match="HIBP_API_KEY"):
        HIBPAdapter()


def test_hibp_200_parses_breaches(session: Session):
    profile = _profile(session)
    fake = _FakeClient([
        _response(200, [
            {
                "Name": "Adobe",
                "BreachDate": "2013-10-04",
                "DataClasses": ["Email addresses", "Password hints"],
                "Description": "In October 2013, 153 million Adobe accounts were breached…",
            },
            {
                "Name": "LinkedIn",
                "BreachDate": "2012-05-05",
                "DataClasses": ["Email addresses", "Passwords"],
                "Description": "In May 2012, LinkedIn was hacked…",
            },
        ]),
    ])
    adapter = HIBPAdapter(api_key="test-key", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    rows = orch.check_email(session, profile, "jane@example.invalid")

    assert {r.breach_name for r in rows} == {"Adobe", "LinkedIn"}
    persisted = list(session.exec(select(BreachExposure)))
    assert {p.breach_name for p in persisted} == {"Adobe", "LinkedIn"}
    assert json.loads(persisted[0].data_classes_json)  # non-empty


def test_hibp_404_returns_empty(session: Session):
    profile = _profile(session)
    fake = _FakeClient([_response(404)])
    adapter = HIBPAdapter(api_key="test-key", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    assert orch.check_email(session, profile, "jane@example.invalid") == []


def test_hibp_401_disables_provider_gracefully(session: Session):
    """401 from HIBP must not abort the whole run — adapter is recorded as
    runtime-disabled and the orchestrator continues."""
    profile = _profile(session)
    fake = _FakeClient([_response(401)])
    adapter = HIBPAdapter(api_key="bad-key", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    rows = orch.check_email(session, profile, "jane@example.invalid")
    assert rows == []
    assert [d.source_id for d in orch.runtime_disabled] == ["hibp"]
    assert "401" in orch.runtime_disabled[0].detail


def test_hibp_429_retries_once_then_succeeds(session: Session, monkeypatch):
    # Stub out sleep so the test stays fast.
    monkeypatch.setattr("delete_me.breaches.hibp.time.sleep", lambda _s: None)
    profile = _profile(session)
    fake = _FakeClient([
        _response(429, headers={"Retry-After": "1"}),
        _response(200, [{
            "Name": "Adobe",
            "BreachDate": "2013-10-04",
            "DataClasses": ["Email addresses"],
            "Description": "A breach.",
        }]),
    ])
    adapter = HIBPAdapter(api_key="test-key", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    rows = orch.check_email(session, profile, "jane@example.invalid")
    assert [r.breach_name for r in rows] == ["Adobe"]


def test_hibp_upsert_dedupes_on_rerun(session: Session):
    profile = _profile(session)
    fake = _FakeClient([
        _response(200, [{
            "Name": "Adobe",
            "BreachDate": "2013-10-04",
            "DataClasses": ["Email addresses"],
            "Description": "A breach.",
        }]),
        _response(200, [{
            "Name": "Adobe",
            "BreachDate": "2013-10-04",
            "DataClasses": ["Email addresses", "Password hints"],
            "Description": "A breach (updated).",
        }]),
    ])
    adapter = HIBPAdapter(api_key="test-key", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])

    orch.check_email(session, profile, "jane@example.invalid")
    orch.check_email(session, profile, "jane@example.invalid")

    rows = list(session.exec(select(BreachExposure)))
    assert len(rows) == 1, "second run should update the existing row, not insert"
    assert "Password hints" in rows[0].data_classes_json


# ---------------------------------------------------------------------- IntelX

def test_intelx_missing_key_raises_unavailable(monkeypatch):
    monkeypatch.delenv("INTELX_API_KEY", raising=False)
    with pytest.raises(BreachAdapterUnavailable, match="INTELX_API_KEY"):
        IntelXAdapter()


def test_intelx_collapses_records_to_unique_buckets(session: Session):
    profile = _profile(session)
    fake = _FakeClient([
        _response(200, {"id": "abc-123"}),  # start-search
        _response(200, {  # result poll
            "status": 0,
            "selectors": [
                {"bucket": "leaks.public", "date": "2020-01-15T00:00:00", "name": "user dump"},
                {"bucket": "leaks.public", "date": "2019-06-01T00:00:00", "name": "user dump v2"},
                {"bucket": "documents.public", "date": "2021-03-04T00:00:00", "name": "doc"},
            ],
        }),
    ])
    adapter = IntelXAdapter(api_key="test", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    rows = orch.check_email(session, profile, "jane@example.invalid")

    names = sorted(r.breach_name for r in rows)
    assert names == ["documents.public", "leaks.public"]
    leaks = next(r for r in rows if r.breach_name == "leaks.public")
    assert leaks.breach_date == "2019-06-01"  # earliest date wins


def test_intelx_401_raises_unavailable(session: Session):
    profile = _profile(session)
    fake = _FakeClient([_response(401)])
    adapter = IntelXAdapter(api_key="bad", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    rows = orch.check_email(session, profile, "jane@example.invalid")
    # Orchestrator catches BreachAdapterUnavailable, disables the adapter,
    # and returns no results — without aborting.
    assert rows == []
    assert any(d.source_id == "intelx" for d in orch.runtime_disabled)


# -------------------------------------------------------------------- DeHashed

def test_dehashed_missing_credentials_raises_unavailable(monkeypatch):
    monkeypatch.delenv("DEHASHED_USERNAME", raising=False)
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    with pytest.raises(BreachAdapterUnavailable, match="DEHASHED_USERNAME"):
        DeHashedAdapter()


def test_dehashed_collapses_entries_with_data_classes(session: Session):
    profile = _profile(session)
    fake = _FakeClient([
        _response(200, {
            "entries": [
                {"database_name": "AcmeLeak", "email": "x", "password": "p"},
                {"database_name": "AcmeLeak", "email": "x", "phone": "555"},
                {"database_name": "BetaLeak", "email": "x", "hashed_password": "h"},
            ],
        }),
    ])
    adapter = DeHashedAdapter(username="u", api_key="k", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    rows = orch.check_email(session, profile, "jane@example.invalid")

    by_name = {r.breach_name: json.loads(r.data_classes_json) for r in rows}
    assert set(by_name) == {"AcmeLeak", "BetaLeak"}
    assert "Phone numbers" in by_name["AcmeLeak"]
    assert "Passwords (plaintext)" in by_name["AcmeLeak"]
    assert by_name["BetaLeak"] == ["Email addresses", "Passwords (hashed)"]


def test_dehashed_402_out_of_credits_raises_unavailable(session: Session):
    profile = _profile(session)
    fake = _FakeClient([_response(402)])
    adapter = DeHashedAdapter(username="u", api_key="k", client=fake)
    orch = BreachOrchestrator.from_registry([adapter])
    rows = orch.check_email(session, profile, "jane@example.invalid")
    assert rows == []
    detail = next(d.detail for d in orch.runtime_disabled if d.source_id == "dehashed")
    assert "credits" in detail.lower()


# ------------------------------------------------------- multi-provider registry

def test_discover_registry_reports_each_provider(monkeypatch):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    monkeypatch.delenv("INTELX_API_KEY", raising=False)
    monkeypatch.delenv("DEHASHED_USERNAME", raising=False)
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    adapters, statuses = discover_registry()
    assert adapters == []
    by_id = {s.source_id: s for s in statuses}
    assert set(by_id) == {"hibp", "intelx", "dehashed"}
    assert all(not s.available for s in statuses)
    # Each status must carry an actionable setup hint.
    assert "HIBP_API_KEY" in by_id["hibp"].detail
    assert "INTELX_API_KEY" in by_id["intelx"].detail
    assert "DEHASHED_USERNAME" in by_id["dehashed"].detail


def test_discover_registry_partial_availability(monkeypatch):
    monkeypatch.setenv("HIBP_API_KEY", "test-key")
    monkeypatch.delenv("INTELX_API_KEY", raising=False)
    monkeypatch.delenv("DEHASHED_USERNAME", raising=False)
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    adapters, statuses = discover_registry()
    assert [a.source_id for a in adapters] == ["hibp"]
    by_id = {s.source_id: s for s in statuses}
    assert by_id["hibp"].available is True
    assert by_id["intelx"].available is False
    assert by_id["dehashed"].available is False


def test_orchestrator_keeps_running_when_one_provider_fails_midrun(session: Session):
    """A 401 on one provider must not abort the run for the others."""
    profile = _profile(session)

    bad = HIBPAdapter(api_key="bad", client=_FakeClient([_response(401)]))
    good = IntelXAdapter(api_key="ok", client=_FakeClient([
        _response(200, {"id": "x"}),
        _response(200, {
            "status": 0,
            "selectors": [
                {"bucket": "leaks.public", "date": "2020-01-15", "name": "good dump"},
            ],
        }),
    ]))
    orch = BreachOrchestrator.from_registry([bad, good])
    rows = orch.check_email(session, profile, "jane@example.invalid")

    assert [r.source for r in rows] == ["intelx"]
    assert [d.source_id for d in orch.runtime_disabled] == ["hibp"]
    # After mid-run failure, the adapter list shrinks.
    assert [a.source_id for a in orch.adapters] == ["intelx"]


# -------------------------------------------------------- pwned-passwords (k-anon)

def test_pwned_passwords_found(monkeypatch):
    """Returns the count when the SHA-1 suffix matches a row in the range."""
    import hashlib
    sha1 = hashlib.sha1(b"password123").hexdigest().upper()
    suffix = sha1[5:]
    body = f"DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEAD:5\n{suffix}:42\nOTHER:1\n"
    fake = _FakeClient([_response(200, body)])
    count = PwnedPasswordsClient(client=fake).lookup("password123")
    assert count == 42


def test_pwned_passwords_not_found():
    fake = _FakeClient([_response(200, "DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEAD:5\n")])
    count = PwnedPasswordsClient(client=fake).lookup("hopefully-not-pwned-xyz-123")
    assert count == 0


def test_pwned_passwords_sends_only_prefix():
    """Critical: the password and full hash must never cross the wire."""
    fake = _FakeClient([_response(200, "")])
    PwnedPasswordsClient(client=fake).lookup("hunter2")
    assert len(fake.calls) == 1
    method, url, _, _ = fake.calls[0]
    assert method == "GET"
    assert url.startswith("https://api.pwnedpasswords.com/range/")
    sent_prefix = url.rsplit("/", 1)[-1]
    assert len(sent_prefix) == 5
    # The full hash and the plaintext password must NOT appear in the URL.
    import hashlib
    full = hashlib.sha1(b"hunter2").hexdigest().upper()
    assert full not in url
    assert "hunter2" not in url
