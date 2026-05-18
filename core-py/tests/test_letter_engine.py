"""Letter engine + agent form generator tests."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest
from delete_me.agent_form import generate_designation
from delete_me.letters import LetterEngine
from delete_me.letters.engine import ConsumerProfile
from delete_me.registry import load_brokers, load_statutes


@pytest.fixture
def consumer() -> ConsumerProfile:
    return ConsumerProfile(
        full_legal_name="Jane Q. Doe",
        current_address="123 Main St, Portland OR 97201",
        email="jane@example.com",
        dob_year=1985,
        prior_addresses=("456 Old Rd, Seattle WA 98101",),
    )


def test_letter_render_includes_consumer_and_broker(consumer):
    brokers = {b.id: b for b in load_brokers()}
    statutes = load_statutes()
    engine = LetterEngine()
    rendered = engine.render(brokers["spokeo"], consumer, statutes)
    assert "Jane Q. Doe" in rendered.markdown
    assert "Spokeo" in rendered.markdown
    assert "1798.105" in rendered.markdown


def test_letter_marks_user_submit_for_fastpeoplesearch(consumer):
    brokers = {b.id: b for b in load_brokers()}
    statutes = load_statutes()
    engine = LetterEngine()
    rendered = engine.render(brokers["fastpeoplesearch"], consumer, statutes)
    assert rendered.user_submit_only is True
    assert "consumer-direct request" in rendered.markdown


def test_letter_writes_markdown(consumer, tmp_path: Path):
    brokers = {b.id: b for b in load_brokers()}
    statutes = load_statutes()
    engine = LetterEngine()
    rendered = engine.render(brokers["whitepages"], consumer, statutes)
    path = engine.write_markdown(rendered, tmp_path)
    assert path.exists()
    assert "Whitepages" in path.read_text()


def test_agent_designation_contains_name_and_scope(consumer):
    designation = generate_designation(consumer, ["spokeo", "whitepages"])
    assert "Jane Q. Doe" in designation.markdown
    assert "limited" in designation.markdown.lower()
    assert "Power of Attorney" in designation.markdown
    assert designation.document_sha256 == designation.document_sha256.lower()
    assert len(designation.document_sha256) == 64


def test_agent_designation_hash_is_stable_for_same_inputs(consumer):
    """Same inputs (incl. signature audit_id/timestamp) should produce the same hash."""
    from datetime import datetime

    from delete_me.agent_form.generator import SignatureContext

    sig = SignatureContext(audit_id="deadbeef", timestamp=datetime(2026, 5, 18, tzinfo=UTC))
    d1 = generate_designation(consumer, ["spokeo"], signature=sig)
    d2 = generate_designation(consumer, ["spokeo"], signature=sig)
    assert d1.document_sha256 == d2.document_sha256


def test_agent_designation_schedule_a_hash_changes_with_brokers(consumer):
    d1 = generate_designation(consumer, ["spokeo"])
    d2 = generate_designation(consumer, ["spokeo", "whitepages"])
    assert d1.schedule_a_hash != d2.schedule_a_hash
