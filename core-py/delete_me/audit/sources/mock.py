"""Deterministic mock adapter for tests and demos.

Pre-loaded with a dict of (full_name_lower, source_id) -> ListingResult,
the adapter returns the configured result for matching queries and
inconclusive=True for everything else. Tests use this exclusively so the
suite doesn't depend on broker uptime or network availability.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import AuditAdapter, AuditQuery, ListingResult


@dataclass
class MockAuditAdapter(AuditAdapter):
    source_id: str = "mock"
    fixtures: dict[str, ListingResult] = field(default_factory=dict)
    inconclusive_for_unknown: bool = True

    def search(self, query: AuditQuery) -> ListingResult:
        key = query.full_name.lower().strip()
        if key in self.fixtures:
            template = self.fixtures[key]
            return ListingResult(
                source=self.source_id,
                found=template.found,
                inconclusive=template.inconclusive,
                listings_url=template.listings_url,
                evidence_html_path=template.evidence_html_path,
                screenshot_path=template.screenshot_path,
                notes=template.notes or "mock fixture",
                checked_at=self._now(),
            )
        return ListingResult(
            source=self.source_id,
            found=False,
            inconclusive=self.inconclusive_for_unknown,
            notes="no mock fixture for this consumer",
            checked_at=self._now(),
        )


def found_fixture(listings_url: str = "https://example.com/listing/jane-doe") -> ListingResult:
    return ListingResult(
        source="mock",
        found=True,
        inconclusive=False,
        listings_url=listings_url,
        notes="mock: consumer is still listed",
    )


def not_found_fixture() -> ListingResult:
    return ListingResult(
        source="mock",
        found=False,
        inconclusive=False,
        notes="mock: consumer not found",
    )
