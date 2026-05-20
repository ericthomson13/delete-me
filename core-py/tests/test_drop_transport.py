"""Tests for the CalPrivacy DROP transport adapter."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from delete_me.registry.loader import Broker, OptOut
from delete_me.transport import DropSubmission, DropTransport, TransportError
from delete_me.transport.drop import ENV_ENDPOINT, ENV_TOKEN


def _sample_submission() -> DropSubmission:
    return DropSubmission(
        full_legal_name="Test User",
        current_address="123 Main St, Portland OR 97201",
        prior_addresses=("456 Old Rd, Seattle WA 98101",),
        dob_year=1985,
        email="test@example.com",
        phone=None,
        former_names=(),
        broker_calprivacy_ids=("DB-0000123", "DB-0000456"),
    )


def test_submission_payload_shape():
    s = _sample_submission()
    p = s.to_payload()
    assert p["full_legal_name"] == "Test User"
    assert p["prior_addresses"] == ["456 Old Rd, Seattle WA 98101"]
    assert p["broker_calprivacy_ids"] == ["DB-0000123", "DB-0000456"]
    assert "attestation" in p
    # The attestation must cite the Delete Act penalty section so the
    # submission carries its own legal weight if it ever has to be
    # introduced as evidence.
    assert "1798.99.86" in p["attestation"]
    assert "submitted_at" in p
    # Payload must be JSON-serializable (the live POST sends it as JSON).
    json.dumps(p)


def test_dry_run_writes_file_and_returns_receipt(tmp_path: Path):
    transport = DropTransport(out_dir=tmp_path)
    receipt = transport.submit(_sample_submission(), live=False)

    assert receipt.dry_run is True
    assert receipt.receipt_id.startswith("drop-")
    assert receipt.broker_calprivacy_ids == ("DB-0000123", "DB-0000456")
    assert receipt.on_disk_path is not None
    assert receipt.on_disk_path.exists()

    on_disk = json.loads(receipt.on_disk_path.read_text())
    assert on_disk["receipt_id"] == receipt.receipt_id
    assert on_disk["dry_run"] is True
    assert on_disk["submission"]["full_legal_name"] == "Test User"


def test_live_without_endpoint_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_ENDPOINT, raising=False)
    monkeypatch.delenv(ENV_TOKEN, raising=False)
    transport = DropTransport()
    with pytest.raises(TransportError, match="endpoint not configured"):
        transport.submit(_sample_submission(), live=True)


def test_live_without_token_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_TOKEN, raising=False)
    transport = DropTransport(endpoint="https://drop.example/submit")
    with pytest.raises(TransportError, match="token required"):
        transport.submit(_sample_submission(), live=True)


def test_live_happy_path_against_fake_endpoint():
    """The live path POSTs JSON + Bearer auth and accepts a server receipt id."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer test-token"
        body = json.loads(request.content)
        assert body["full_legal_name"] == "Test User"
        assert body["broker_calprivacy_ids"] == ["DB-0000123", "DB-0000456"]
        return httpx.Response(200, json={"receipt_id": "server-receipt-42"})

    transport = DropTransport(
        token="test-token",
        endpoint="https://drop.example/submit",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    receipt = transport.submit(_sample_submission(), live=True)
    assert receipt.dry_run is False
    assert receipt.receipt_id == "server-receipt-42"
    assert receipt.on_disk_path is None


def test_live_server_error_raises():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    transport = DropTransport(
        token="test-token",
        endpoint="https://drop.example/submit",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TransportError, match="503"):
        transport.submit(_sample_submission(), live=True)


# --- Helpers other test modules import to fake a DROP-registered broker. ---


def fixture_drop_broker(
    broker_id: str = "drop_test_broker",
    calprivacy_id: str = "DB-TEST-001",
) -> Broker:
    return Broker(
        id=broker_id,
        name="DROP Test Broker",
        opt_out=OptOut(
            methods=["drop", "web_form"],
            web_form="https://example.test/optout",
            drop_registered=True,
            calprivacy_id=calprivacy_id,
        ),
        accepts_authorized_agent=True,
        required_pii=["full_name", "current_address"],
        statutes=["ccpa_1798_105", "ca_delete_act"],
        last_verified=date(2026, 5, 19),
        maintainer="@ericthomson13",
    )
