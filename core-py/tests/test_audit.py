"""Audit orchestrator tests using the deterministic MockAuditAdapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from delete_me.audit import AuditOrchestrator, MockAuditAdapter, found_fixture, not_found_fixture
from delete_me.audit.orchestrator import _decide_status, _split_city_state
from delete_me.cases import draft_case, upsert_profile
from delete_me.db import AuditResult, CaseStatus
from delete_me.db.session import engine_from_url
from delete_me.letters.engine import ConsumerProfile
from sqlmodel import Session, SQLModel


@pytest.fixture
def session(tmp_path) -> Session:
    url = f"sqlite:///{tmp_path / 'audit.db'}"
    engine = engine_from_url(url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_case(session: Session, broker_id: str = "spokeo") -> tuple:
    consumer = ConsumerProfile(
        full_legal_name="Jane Q. Doe",
        current_address="123 Main St, Portland, OR 97201",
        dob_year=1985,
    )
    profile = upsert_profile(session, consumer)
    case, _ = draft_case(session, profile, broker_id)
    return profile, case


def _adapter_for(source_id: str, fixtures: dict) -> MockAuditAdapter:
    return MockAuditAdapter(source_id=source_id, fixtures=fixtures, inconclusive_for_unknown=False)


def test_audit_noncompliant_when_found(session: Session):
    profile, case = _make_case(session)
    orch = AuditOrchestrator.from_registry(
        {"spokeo_search": _adapter_for("spokeo_search", {"jane q. doe": found_fixture()})}
    )
    results = orch.audit_case(session, case)

    assert len(results) == 1
    assert results[0].found is True
    assert case.status == CaseStatus.NONCOMPLIANT
    assert case.last_audited_at is not None


def test_audit_deleted_when_not_found(session: Session):
    profile, case = _make_case(session)
    orch = AuditOrchestrator.from_registry(
        {"spokeo_search": _adapter_for("spokeo_search", {"jane q. doe": not_found_fixture()})}
    )
    orch.audit_case(session, case)
    assert case.status == CaseStatus.DELETED_CONFIRMED


def test_audit_inconclusive_when_no_adapter(session: Session):
    profile, case = _make_case(session)
    orch = AuditOrchestrator.from_registry({})  # no adapters
    orch.audit_case(session, case)
    assert case.status == CaseStatus.AUDIT_INCONCLUSIVE


def test_cases_due_filters_by_status_and_due_time(session: Session):
    profile, case = _make_case(session)
    # Mark the case as sent and due in the past.
    case.status = CaseStatus.SENT_DRY_RUN
    case.sent_at = datetime.now(UTC) - timedelta(days=61)
    case.audit_due_at = datetime.now(UTC) - timedelta(seconds=10)
    session.add(case)
    session.commit()

    orch = AuditOrchestrator()
    due = orch.cases_due(session)
    assert [c.id for c in due] == [case.id]


def test_decide_status_helper():
    now = datetime.now(UTC)
    found = AuditResult(case_id=1, source="x", checked_at=now, found=True, inconclusive=False)
    miss = AuditResult(case_id=1, source="y", checked_at=now, found=False, inconclusive=False)
    incon = AuditResult(case_id=1, source="z", checked_at=now, found=False, inconclusive=True)

    assert _decide_status([found, miss]) == CaseStatus.NONCOMPLIANT
    assert _decide_status([miss, miss]) == CaseStatus.DELETED_CONFIRMED
    assert _decide_status([miss, incon]) == CaseStatus.AUDIT_INCONCLUSIVE


def test_split_city_state():
    assert _split_city_state("123 Main St, Portland, OR 97201") == ("Portland", "OR")
    assert _split_city_state("Portland, OR") == ("Portland", "OR")
    assert _split_city_state("Portland") == (None, None)
    assert _split_city_state(None) == (None, None)
