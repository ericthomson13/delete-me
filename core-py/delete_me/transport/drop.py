"""CalPrivacy DROP (Delete Request and Opt-Out Platform) transport adapter.

The California Delete Act (Cal. Civ. Code §§1798.99.80–1798.99.89) creates a
single state-run portal through which California residents submit ONE
deletion request that all registered brokers must honor on a 45-day cadence.
Enforcement begins **2026-08-01**.

As of the project's writing the CalPrivacy production submission API has not
yet published a stable URL or auth model. This module is structured so the
submission *payload* is correct now — when CalPrivacy publishes the
production endpoint, only `DropTransport.submit`'s live path needs to flip
on. Tests + dry-run + CLI all keep working.

Dry-run is the default: the submission JSON is written to
`$DELETE_ME_DROP_OUT/<receipt>.json` (defaulting to a platformdirs path) and
a synthetic receipt id is returned. The on-disk artifact is the evidence
the consumer/maintainer hands to the AG if a registered broker fails to
honor the request.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from platformdirs import user_data_path

from .base import TransportError

LOG = logging.getLogger(__name__)
ENV_TOKEN = "CALPRIVACY_DROP_TOKEN"
ENV_OUT_DIR = "DELETE_ME_DROP_OUT"
# CalPrivacy has signalled this URL shape; the exact path will lock in
# closer to the 2026-08-01 enforcement date. Override via env var.
ENV_ENDPOINT = "CALPRIVACY_DROP_ENDPOINT"


@dataclass(frozen=True)
class DropSubmission:
    """The payload submitted to the CalPrivacy DROP system.

    Shape mirrors the CalPrivacy rulemaking ("Required Consumer Information"
    in 11 CCR §7600 et seq.) — the consumer attests, identifies themselves,
    and the platform fans the request out to all registered brokers.
    """

    full_legal_name: str
    current_address: str
    prior_addresses: tuple[str, ...]
    dob_year: int | None
    email: str | None
    phone: str | None
    former_names: tuple[str, ...]
    broker_calprivacy_ids: tuple[str, ...]
    attestation: str = (
        "I declare under penalty of perjury under the laws of the State of "
        "California that I am the consumer whose personal information is the "
        "subject of this request, or that I am authorized by such consumer to "
        "submit this request, and that the information provided is true and "
        "correct. (Cal. Civ. Code §1798.99.86)"
    )
    submitted_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def to_payload(self) -> dict:
        d = asdict(self)
        d["prior_addresses"] = list(self.prior_addresses)
        d["former_names"] = list(self.former_names)
        d["broker_calprivacy_ids"] = list(self.broker_calprivacy_ids)
        return d


@dataclass(frozen=True)
class DropReceipt:
    """What we get back from a successful submission."""

    dry_run: bool
    receipt_id: str
    accepted_at: datetime
    broker_calprivacy_ids: tuple[str, ...]
    on_disk_path: Path | None = None


def _default_out_dir() -> Path:
    return Path(
        os.environ.get(ENV_OUT_DIR)
        or user_data_path("delete-me", "delete-me") / "drop"
    )


class DropTransport:
    def __init__(
        self,
        token: str | None = None,
        endpoint: str | None = None,
        out_dir: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token or os.environ.get(ENV_TOKEN)
        self.endpoint = endpoint or os.environ.get(ENV_ENDPOINT)
        self.out_dir = out_dir or _default_out_dir()
        self.client = client or httpx.Client(timeout=15.0)

    def submit(self, submission: DropSubmission, live: bool = False) -> DropReceipt:
        """Submit (or dry-run-submit) a deletion request to CalPrivacy DROP."""
        accepted_at = datetime.now(UTC)
        receipt_id = f"drop-{uuid.uuid4()}"

        if not live:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            on_disk = self.out_dir / f"{receipt_id}.json"
            payload = {
                "receipt_id": receipt_id,
                "dry_run": True,
                "submission": submission.to_payload(),
            }
            on_disk.write_text(json.dumps(payload, indent=2))
            LOG.info(
                "DRY RUN DROP: receipt=%s brokers=%d on_disk=%s",
                receipt_id,
                len(submission.broker_calprivacy_ids),
                on_disk,
            )
            return DropReceipt(
                dry_run=True,
                receipt_id=receipt_id,
                accepted_at=accepted_at,
                broker_calprivacy_ids=submission.broker_calprivacy_ids,
                on_disk_path=on_disk,
            )

        if not self.endpoint:
            # The DROP API publishes alongside the 2026-08-01 enforcement
            # date. Until then, the maintainer overrides CALPRIVACY_DROP_ENDPOINT
            # to test against a staging URL, or runs in dry-run mode.
            raise TransportError(
                f"CalPrivacy DROP endpoint not configured (env var: {ENV_ENDPOINT}). "
                "The production API publishes alongside the 2026-08-01 enforcement "
                "date; until then, use dry-run mode."
            )
        if not self.token:
            raise TransportError(
                f"CalPrivacy DROP token required for live submit (env var: {ENV_TOKEN})"
            )

        try:
            response = self.client.post(
                self.endpoint,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.token}",
                },
                json=submission.to_payload(),
            )
        except httpx.HTTPError as exc:
            raise TransportError(f"DROP request failed: {exc}") from exc

        if response.status_code >= 400:
            raise TransportError(
                f"DROP returned {response.status_code}: {response.text[:500]}"
            )

        body = response.json()
        return DropReceipt(
            dry_run=False,
            receipt_id=body.get("receipt_id") or receipt_id,
            accepted_at=accepted_at,
            broker_calprivacy_ids=submission.broker_calprivacy_ids,
            on_disk_path=None,
        )
