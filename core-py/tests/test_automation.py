"""Tests for the tiered submission-automation framework (issue #8)."""

from __future__ import annotations

import pytest

from delete_me.automation import (
    AutomationUnavailable,
    SubmissionResult,
    dispatch,
    load_script,
)
from delete_me.letters.engine import ConsumerProfile
from delete_me.registry import load_brokers


def _profile() -> ConsumerProfile:
    return ConsumerProfile(
        full_legal_name="Test Person",
        current_address="1 Test St, Test City, CA 90001",
        email="t@example.com",
    )


def test_dispatch_unknown_broker_raises() -> None:
    with pytest.raises(ValueError, match="unknown broker_id"):
        dispatch("does-not-exist", _profile())


def test_dispatch_manual_returns_needs_human_with_url() -> None:
    # spokeo has no automation block → treated as manual.
    result = dispatch("spokeo", _profile())
    assert result.status == "needs_human"
    assert result.broker_id == "spokeo"
    assert "manual" in (result.fallback_reason or "").lower()
    # Some URL surfaced for the user to open in their browser.
    assert "url" in result.evidence_payload
    assert result.evidence_payload["url"]


def test_dispatch_checkpeople_dry_run_uses_reference_stub() -> None:
    """checkpeople.yaml carries automation.tier=auto + script=checkpeople.py."""
    result = dispatch("checkpeople", _profile(), dry_run=True)
    assert isinstance(result, SubmissionResult)
    assert result.status == "submitted"
    assert result.dry_run is True
    assert result.broker_id == "checkpeople"
    # Stub records what it would have submitted.
    assert result.evidence_payload.get("stub") is True
    assert result.evidence_payload["would_submit"]["full_legal_name"] == "Test Person"


def test_dispatch_checkpeople_live_degrades_to_needs_human() -> None:
    """Reference stub raises AutomationUnavailable on live until real impl lands.

    The dispatcher must convert that to needs_human, not bubble the exception.
    """
    result = dispatch("checkpeople", _profile(), dry_run=False)
    assert result.status == "needs_human"
    assert result.dry_run is False
    assert "stub" in (result.fallback_reason or "").lower()
    # AutomationUnavailable carried a URL override; dispatcher used it.
    assert result.evidence_payload["url"] == "https://www.checkpeople.com/opt-out"


def test_load_script_missing_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_script("does_not_exist_at_all.py")


def test_schema_accepts_brokers_with_and_without_automation_block() -> None:
    """The automation block is optional. Loading the full registry must succeed
    even though 49 of 50 brokers have no automation block and 1 (checkpeople) does.
    """
    brokers = load_brokers()
    assert len(brokers) >= 50
    cp = next((b for b in brokers if b.id == "checkpeople"), None)
    assert cp is not None
    assert cp.automation is not None
    assert cp.automation.tier == "auto"
    assert cp.automation.script == "checkpeople.py"

    # Brokers without the block have automation=None.
    spokeo = next((b for b in brokers if b.id == "spokeo"), None)
    assert spokeo is not None
    assert spokeo.automation is None


def test_automation_unavailable_carries_url_through() -> None:
    """Exception's optional url= override should surface in evidence_payload.

    Covered end-to-end by test_dispatch_checkpeople_live_degrades_to_needs_human,
    but tested in isolation here so the exception contract is documented.
    """
    exc = AutomationUnavailable("captcha appeared", url="https://example.com/captcha")
    assert exc.reason == "captcha appeared"
    assert exc.url == "https://example.com/captcha"
    assert str(exc) == "captcha appeared"
