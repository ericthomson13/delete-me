"""Adapter base for read-only public-search audit sources.

Audit adapters are intentionally narrow: given a consumer profile, return
whether the consumer is currently listed on the source. They never submit
forms, log in, or attempt to bypass any access controls — staying clearly
within CFAA-safe public-data access.

Phase 2 implements the first concrete adapters (FastPeopleSearch,
TruePeopleSearch, Spokeo, Whitepages, BeenVerified).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ListingResult:
    source: str
    found: bool
    inconclusive: bool
    listings_url: str | None
    evidence_html_path: str | None
    evidence_screenshot_path: str | None
    checked_at: datetime


class AuditAdapter(Protocol):
    """Each broker that supports auditing implements one of these."""

    source_id: str

    def search(
        self,
        full_name: str,
        city: str,
        state: str,
        dob_year: int | None,
    ) -> ListingResult: ...
