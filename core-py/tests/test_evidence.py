"""Evidence package builder tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from delete_me.audit import AuditOrchestrator, MockAuditAdapter, found_fixture
from delete_me.cases import draft_case, upsert_profile
from delete_me.db.session import engine_from_url
from delete_me.evidence import PackageBuilder
from delete_me.letters.engine import ConsumerProfile
from sqlmodel import Session, SQLModel


@pytest.fixture
def session(tmp_path) -> Session:
    url = f"sqlite:///{tmp_path / 'evidence.db'}"
    engine = engine_from_url(url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _setup_noncompliant_case(session: Session) -> int:
    consumer = ConsumerProfile(
        full_legal_name="Jane Q. Doe",
        current_address="123 Main St, Portland, OR 97201",
        email="jane@example.com",
        dob_year=1985,
    )
    profile = upsert_profile(session, consumer)
    case, _ = draft_case(session, profile, "spokeo")
    AuditOrchestrator.from_registry(
        {"spokeo_search": MockAuditAdapter(
            source_id="spokeo_search",
            fixtures={"jane q. doe": found_fixture()},
            inconclusive_for_unknown=False,
        )}
    ).audit_case(session, case)
    return case.id


def test_package_contains_required_files(session: Session, tmp_path: Path):
    case_id = _setup_noncompliant_case(session)
    case = session.get(__import__("delete_me.db", fromlist=["Case"]).Case, case_id)

    builder = PackageBuilder(out_dir=tmp_path / "ev")
    pkg = builder.build(session, case)

    expected_files = [
        "01-original-letter.md",
        "02-agent-designation.md",
        "03-send-receipt.json",
        "05-statute-citations.md",
        "06-ca-ag-complaint-DRAFT.md",
        "07-attorney-referrals.md",
        "MANIFEST.json",
    ]
    for name in expected_files:
        assert (pkg.directory / name).exists(), f"missing {name}"

    # Audit evidence subdir has the JSON for the audit we ran.
    assert (pkg.directory / "04-audit-evidence" / "spokeo_search.json").exists()


def test_package_zip_is_well_formed(session: Session, tmp_path: Path):
    case_id = _setup_noncompliant_case(session)
    case = session.get(__import__("delete_me.db", fromlist=["Case"]).Case, case_id)
    pkg = PackageBuilder(out_dir=tmp_path / "ev").build(session, case)

    with zipfile.ZipFile(pkg.zip_path) as zf:
        names = zf.namelist()

    assert any(n.endswith("MANIFEST.json") for n in names)
    assert any(n.endswith("01-original-letter.md") for n in names)
    assert any(n.endswith("06-ca-ag-complaint-DRAFT.md") for n in names)


def test_complaint_draft_includes_consumer_and_broker(session: Session, tmp_path: Path):
    case_id = _setup_noncompliant_case(session)
    case = session.get(__import__("delete_me.db", fromlist=["Case"]).Case, case_id)
    pkg = PackageBuilder(out_dir=tmp_path / "ev").build(session, case)

    complaint = (pkg.directory / "06-ca-ag-complaint-DRAFT.md").read_text()
    assert "Jane Q. Doe" in complaint
    assert "Spokeo" in complaint
    assert "1798.105" in complaint
    assert "draft, not a submission" in complaint.lower()


def test_manifest_lists_files(session: Session, tmp_path: Path):
    case_id = _setup_noncompliant_case(session)
    case = session.get(__import__("delete_me.db", fromlist=["Case"]).Case, case_id)
    pkg = PackageBuilder(out_dir=tmp_path / "ev").build(session, case)

    manifest = json.loads((pkg.directory / "MANIFEST.json").read_text())
    assert manifest["case_id"] == case_id
    assert manifest["broker_id"] == "spokeo"
    assert "01-original-letter.md" in manifest["files"]
    assert manifest["case_status"] == "noncompliant"


def test_evidence_path_is_persisted_on_case(session: Session, tmp_path: Path):
    Case = __import__("delete_me.db", fromlist=["Case"]).Case
    case_id = _setup_noncompliant_case(session)
    case = session.get(Case, case_id)
    pkg = PackageBuilder(out_dir=tmp_path / "ev").build(session, case)

    refreshed = session.get(Case, case_id)
    assert refreshed.evidence_path == str(pkg.zip_path)
