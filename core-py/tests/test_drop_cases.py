"""Tests for cases.submit_via_drop — the case-lifecycle side of the DROP path."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from delete_me import cases as cases_mod
from delete_me.cases import submit_via_drop, upsert_profile
from delete_me.db import CaseStatus
from delete_me.letters.engine import ConsumerProfile
from delete_me.transport import DropTransport

from .test_drop_transport import fixture_drop_broker


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'drop.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def consumer() -> ConsumerProfile:
    return ConsumerProfile(
        full_legal_name="CA Resident",
        current_address="100 Market St, San Francisco CA 94105",
        email="ca@example.com",
        phone=None,
        dob_year=1990,
        prior_addresses=(),
        former_names=(),
    )


def test_no_eligible_brokers_raises(
    session: Session,
    consumer: ConsumerProfile,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    # Only brokers that are drop_registered AND have a calprivacy_id are
    # eligible. The bare fixture broker without an ID should be skipped, and
    # if it's the only candidate the call must raise.
    broker = fixture_drop_broker()
    broker.opt_out.calprivacy_id = None
    monkeypatch.setattr(cases_mod, "load_brokers", lambda: [broker])

    profile = upsert_profile(session, consumer)
    with pytest.raises(ValueError, match="no drop_registered brokers"):
        submit_via_drop(session, profile, DropTransport(out_dir=tmp_path))


def test_happy_path_creates_sent_via_drop_cases(
    session: Session,
    consumer: ConsumerProfile,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    brokers = [
        fixture_drop_broker("alpha", "DB-A-001"),
        fixture_drop_broker("beta", "DB-B-002"),
    ]
    monkeypatch.setattr(cases_mod, "load_brokers", lambda: brokers)

    profile = upsert_profile(session, consumer)
    receipt, created_cases = submit_via_drop(
        session, profile, DropTransport(out_dir=tmp_path)
    )

    assert receipt.dry_run is True
    assert len(created_cases) == 2
    assert {c.broker_id for c in created_cases} == {"alpha", "beta"}
    for c in created_cases:
        assert c.status == CaseStatus.SENT_VIA_DROP
        assert c.transport_message_id == receipt.receipt_id
        # 45-day audit window is the cadence the Delete Act mandates.
        assert (c.audit_due_at - c.sent_at).days == 45


def test_resubmit_updates_existing_cases_in_place(
    session: Session,
    consumer: ConsumerProfile,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    brokers = [fixture_drop_broker("alpha", "DB-A-001")]
    monkeypatch.setattr(cases_mod, "load_brokers", lambda: brokers)

    profile = upsert_profile(session, consumer)
    receipt1, cases1 = submit_via_drop(
        session, profile, DropTransport(out_dir=tmp_path)
    )
    receipt2, cases2 = submit_via_drop(
        session, profile, DropTransport(out_dir=tmp_path)
    )

    # Same case row, refreshed — not a duplicate.
    assert len(cases2) == 1
    assert cases1[0].id == cases2[0].id
    assert cases2[0].transport_message_id == receipt2.receipt_id
    assert receipt1.receipt_id != receipt2.receipt_id


def test_brokers_missing_calprivacy_id_are_skipped(
    session: Session,
    consumer: ConsumerProfile,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    eligible = fixture_drop_broker("alpha", "DB-A-001")
    ineligible = fixture_drop_broker("beta", "DB-B-002")
    ineligible.opt_out.calprivacy_id = None
    monkeypatch.setattr(cases_mod, "load_brokers", lambda: [eligible, ineligible])

    profile = upsert_profile(session, consumer)
    receipt, created_cases = submit_via_drop(
        session, profile, DropTransport(out_dir=tmp_path)
    )

    assert [c.broker_id for c in created_cases] == ["alpha"]
    assert receipt.broker_calprivacy_ids == ("DB-A-001",)
