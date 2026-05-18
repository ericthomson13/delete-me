"""Adapter base for read-only public-search audit sources.

Adapters are intentionally narrow: given a consumer profile, return whether
the consumer is currently listed on the source. They never submit forms,
log in, or attempt to bypass any access controls — staying clearly within
CFAA-safe public-data access.

If a source blocks the request (Cloudflare, rate-limit, anything), the
adapter returns inconclusive=True rather than raising. The orchestrator
treats inconclusive as "couldn't verify" and never blocks the user-visible
case status on it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class AuditQuery:
    full_name: str
    current_city: str | None
    current_state: str | None
    dob_year: int | None


@dataclass(frozen=True)
class ListingResult:
    source: str
    found: bool
    inconclusive: bool
    listings_url: str | None = None
    evidence_html_path: str | None = None
    screenshot_path: str | None = None
    notes: str | None = None
    checked_at: datetime | None = None


class AuditAdapter(ABC):
    """Implementations register themselves under a unique source_id."""

    source_id: str = ""

    @abstractmethod
    def search(self, query: AuditQuery) -> ListingResult: ...

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
