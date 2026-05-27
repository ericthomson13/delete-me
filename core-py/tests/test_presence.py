"""Presence orchestrator tests using the deterministic MockAuditAdapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from delete_me.audit import (
    MockAuditAdapter,
    PresenceOrchestrator,
    found_fixture,
    not_found_fixture,
)
from delete_me.cases import upsert_profile
from delete_me.db import PresenceResult
from delete_me.db.session import engine_from_url
from delete_me.letters.engine import ConsumerProfile
from delete_me.registry.loader import Broker, OptOut
from sqlmodel import Session, SQLModel, select


@pytest.fixture
def session(tmp_path) -> Session:
    url = f"sqlite:///{tmp_path / 'presence.db'}"
    engine = engine_from_url(url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _profile(session: Session):
    consumer = ConsumerProfile(
        full_legal_name="Jane Q. Doe",
        current_address="123 Main St, Portland, OR 97201",
        dob_year=1985,
    )
    return upsert_profile(session, consumer)


def _broker(audit_sources: list[str], broker_id: str = "spokeo") -> Broker:
    """Build an in-memory Broker without touching the YAML registry."""
    return Broker(
        id=broker_id,
        name=broker_id.title(),
        opt_out=OptOut(methods=["email"], email="opt-out@example.com"),
        accepts_authorized_agent=True,
        required_pii=["full_name", "current_address"],
        audit_sources=audit_sources,
        statutes=["ccpa"],
        last_verified="2026-01-01",
        maintainer="@test",
    )


def test_presence_found_persists_row(session: Session):
    profile = _profile(session)
    broker = _broker(audit_sources=["spokeo_search"])
    orch = PresenceOrchestrator.from_registry({
        "spokeo_search": MockAuditAdapter(
            source_id="spokeo_search",
            fixtures={"jane q. doe": found_fixture()},
            inconclusive_for_unknown=False,
        ),
    })
    results = orch.check_profile(session, profile, brokers=[broker])

    assert len(results) == 1
    assert results[0].found is True
    assert results[0].broker_id == "spokeo"
    assert results[0].source == "spokeo_search"
    rows = list(session.exec(select(PresenceResult)))
    assert len(rows) == 1


def test_presence_not_found_records_miss(session: Session):
    profile = _profile(session)
    broker = _broker(audit_sources=["spokeo_search"])
    orch = PresenceOrchestrator.from_registry({
        "spokeo_search": MockAuditAdapter(
            source_id="spokeo_search",
            fixtures={"jane q. doe": not_found_fixture()},
            inconclusive_for_unknown=False,
        ),
    })
    results = orch.check_profile(session, profile, brokers=[broker])
    assert len(results) == 1
    assert results[0].found is False
    assert results[0].inconclusive is False


def test_presence_no_audit_source_returns_sentinel(session: Session):
    profile = _profile(session)
    broker = _broker(audit_sources=[])
    orch = PresenceOrchestrator.from_registry({})
    results = orch.check_profile(session, profile, brokers=[broker])
    assert len(results) == 1
    assert results[0].source == "(none)"
    assert results[0].inconclusive is True


def test_presence_no_adapter_registered_returns_inconclusive(session: Session):
    profile = _profile(session)
    broker = _broker(audit_sources=["spokeo_search"])
    orch = PresenceOrchestrator.from_registry({})  # source named but not registered
    results = orch.check_profile(session, profile, brokers=[broker])
    assert len(results) == 1
    assert results[0].inconclusive is True
    assert "no adapter registered" in (results[0].notes or "")


def test_presence_adapter_exception_returns_inconclusive(session: Session):
    profile = _profile(session)
    broker = _broker(audit_sources=["broken"])

    class BoomAdapter(MockAuditAdapter):
        def search(self, query):
            raise RuntimeError("source unreachable")

    orch = PresenceOrchestrator.from_registry({"broken": BoomAdapter(source_id="broken")})
    results = orch.check_profile(session, profile, brokers=[broker])
    assert len(results) == 1
    assert results[0].inconclusive is True
    assert "source unreachable" in (results[0].notes or "")


def test_presence_cache_reuses_fresh_row(session: Session):
    profile = _profile(session)
    broker = _broker(audit_sources=["spokeo_search"])

    call_count = {"n": 0}

    class CountingAdapter(MockAuditAdapter):
        def search(self, query):
            call_count["n"] += 1
            return super().search(query)

    orch = PresenceOrchestrator.from_registry({
        "spokeo_search": CountingAdapter(
            source_id="spokeo_search",
            fixtures={"jane q. doe": found_fixture()},
            inconclusive_for_unknown=False,
        ),
    })
    orch.check_profile(session, profile, brokers=[broker], fresh_days=7)
    orch.check_profile(session, profile, brokers=[broker], fresh_days=7)
    assert call_count["n"] == 1, "second call should hit the cache"


def test_presence_cache_expires_outside_fresh_window(session: Session):
    profile = _profile(session)
    broker = _broker(audit_sources=["spokeo_search"])

    # Seed a stale row directly.
    stale = PresenceResult(
        profile_id=profile.id,
        broker_id="spokeo",
        source="spokeo_search",
        checked_at=datetime.now(UTC) - timedelta(days=30),
        found=True,
        inconclusive=False,
    )
    session.add(stale)
    session.commit()

    orch = PresenceOrchestrator.from_registry({
        "spokeo_search": MockAuditAdapter(
            source_id="spokeo_search",
            fixtures={"jane q. doe": not_found_fixture()},
            inconclusive_for_unknown=False,
        ),
    })
    results = orch.check_profile(session, profile, brokers=[broker], fresh_days=7)
    # We re-queried, so the latest row reflects the fresh mock fixture (not the stale True).
    assert results[0].found is False
