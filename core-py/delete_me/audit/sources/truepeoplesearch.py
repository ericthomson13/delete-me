"""TruePeopleSearch audit adapter (experimental).

Read-only public search. We hit the same URL a browser would and look for
the consumer's name in the response HTML. If anti-bot blocks us (403, JS
challenge, weird response), we return inconclusive=True — the audit
pipeline will degrade gracefully and the user keeps their letter receipt.

This adapter is marked experimental:
- It can break any time TruePeopleSearch changes its HTML.
- It runs at 1 request per minute per adapter instance via a simple
  in-process rate limiter.
- It is NOT exercised in the unit test suite (tests use MockAuditAdapter).
- Real-world invocation happens only through `delete-me audit` / `delete-me
  audit-due`, where a single failure cannot block other audits.
"""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import quote_plus

import httpx

from .base import AuditAdapter, AuditQuery, ListingResult

LOG = logging.getLogger(__name__)


class TruePeopleSearchAdapter(AuditAdapter):
    source_id = "truepeoplesearch_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.truepeoplesearch.com/results?name={name}"
        "&citystatezip={location}"
    )
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    MIN_INTERVAL_S = 60.0

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=15.0,
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
        )
        self._last_request_at: float = 0.0

    def _maybe_sleep(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.MIN_INTERVAL_S:
            time.sleep(self.MIN_INTERVAL_S - elapsed)

    def search(self, query: AuditQuery) -> ListingResult:
        location = ""
        if query.current_city and query.current_state:
            location = f"{query.current_city}, {query.current_state}"
        url = self.SEARCH_URL_TEMPLATE.format(
            name=quote_plus(query.full_name),
            location=quote_plus(location),
        )

        self._maybe_sleep()
        try:
            response = self.client.get(url)
            self._last_request_at = time.monotonic()
        except httpx.HTTPError as exc:
            LOG.warning("truepeoplesearch fetch failed: %s", exc)
            return ListingResult(
                source=self.source_id,
                found=False,
                inconclusive=True,
                notes=f"network error: {exc}",
                checked_at=self._now(),
            )

        if response.status_code == 403 or response.status_code == 429:
            return ListingResult(
                source=self.source_id,
                found=False,
                inconclusive=True,
                notes=f"blocked: HTTP {response.status_code}",
                checked_at=self._now(),
            )

        if response.status_code >= 400:
            return ListingResult(
                source=self.source_id,
                found=False,
                inconclusive=True,
                notes=f"HTTP {response.status_code}",
                checked_at=self._now(),
            )

        body = response.text
        if _looks_like_block_page(body):
            return ListingResult(
                source=self.source_id,
                found=False,
                inconclusive=True,
                notes="response looks like a bot-block page",
                checked_at=self._now(),
            )

        # Detection heuristic: if the page contains a results card with a name
        # that fuzzy-matches the consumer's, we count it as found.
        found = _name_appears_in_results(body, query.full_name)
        return ListingResult(
            source=self.source_id,
            found=found,
            inconclusive=False,
            listings_url=url,
            notes="match found in result cards" if found else "no match in result cards",
            checked_at=self._now(),
        )


def _looks_like_block_page(body: str) -> bool:
    markers = ("Just a moment...", "cf-challenge", "Attention Required!", "Access denied")
    return any(marker.lower() in body.lower() for marker in markers)


def _name_appears_in_results(body: str, full_name: str) -> bool:
    """Heuristic: case-insensitive substring match of the full name in result blocks.

    Deliberately conservative — false negatives are fine (we'll re-audit
    next cycle); false positives are worse (we'd mark a broker noncompliant
    when the user is gone).
    """
    if not full_name.strip():
        return False
    needle = re.escape(full_name.strip())
    # Only count as found if the name appears inside a card-style block,
    # not in unrelated chrome.
    pattern = re.compile(
        rf'<div[^>]*class="[^"]*card[^"]*"[^>]*>[\s\S]*?{needle}[\s\S]*?</div>',
        flags=re.IGNORECASE,
    )
    return bool(pattern.search(body))
