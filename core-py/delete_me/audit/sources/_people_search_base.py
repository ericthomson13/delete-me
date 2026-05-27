"""Shared base for people-search-style audit adapters.

Every adapter in this family does the same dance:

1. Build a search URL from the consumer's name + city/state.
2. GET it with a browser-like User-Agent, respecting a per-instance rate
   limit so we don't get banned.
3. Detect anti-bot pages (Cloudflare challenge, generic blocks) and
   return inconclusive=True if we hit one.
4. Look for the consumer's name inside a result-card block of the HTML.
   Conservative regex by default — false negatives are fine (we re-audit
   next cycle), false positives mark a broker noncompliant when the user
   has actually been removed.

Subclasses set class attributes (URL template, optional source-specific
markers and card class) and override hooks only when the site doesn't fit
the defaults.

All adapters in this family are **experimental** by construction. They
break whenever a site changes its HTML. The orchestrator treats every
exception and every block-page response as inconclusive, so a broken
adapter never blocks a user's case status.
"""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import quote_plus

import httpx

from .base import AuditAdapter, AuditQuery, ListingResult

LOG = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_BLOCK_MARKERS = (
    "just a moment...",
    "cf-challenge",
    "attention required!",
    "access denied",
    "please verify you are human",
    "px-captcha",
)


class PeopleSearchAdapter(AuditAdapter):
    """Base for any broker with a public name+location search page.

    Subclasses MUST set:
      - source_id
      - SEARCH_URL_TEMPLATE — must contain {name} and {location} placeholders

    Subclasses MAY override:
      - LOCATION_FORMAT — default "{city}, {state}" if both present
      - CARD_CLASS_PATTERN — substring of the HTML class that wraps results
      - BLOCK_MARKERS — extra site-specific anti-bot markers
      - MIN_INTERVAL_S — per-source rate limit (default 60s)
      - build_url(query) — when the site needs different URL params
      - name_appears_in_results(body, name) — when card structure differs
    """

    source_id: str = ""
    SEARCH_URL_TEMPLATE: str = ""
    LOCATION_FORMAT: str = "{city}, {state}"
    CARD_CLASS_PATTERN: str = "card"
    BLOCK_MARKERS: tuple[str, ...] = ()
    USER_AGENT: str = DEFAULT_USER_AGENT
    MIN_INTERVAL_S: float = 60.0

    def __init__(self, client: httpx.Client | None = None) -> None:
        if not self.source_id or not self.SEARCH_URL_TEMPLATE:
            raise TypeError(
                f"{type(self).__name__} must set source_id and SEARCH_URL_TEMPLATE"
            )
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

    def format_location(self, query: AuditQuery) -> str:
        if query.current_city and query.current_state:
            return self.LOCATION_FORMAT.format(
                city=query.current_city, state=query.current_state
            )
        return query.current_city or query.current_state or ""

    def build_url(self, query: AuditQuery) -> str:
        return self.SEARCH_URL_TEMPLATE.format(
            name=quote_plus(query.full_name),
            location=quote_plus(self.format_location(query)),
        )

    def name_appears_in_results(self, body: str, full_name: str) -> bool:
        return _name_in_card_block(body, full_name, self.CARD_CLASS_PATTERN)

    def search(self, query: AuditQuery) -> ListingResult:
        url = self.build_url(query)
        self._maybe_sleep()
        try:
            response = self.client.get(url)
            self._last_request_at = time.monotonic()
        except httpx.HTTPError as exc:
            LOG.warning("%s fetch failed: %s", self.source_id, exc)
            return self._inconclusive(f"network error: {exc}")

        if response.status_code in (403, 429):
            return self._inconclusive(f"blocked: HTTP {response.status_code}")
        if response.status_code >= 400:
            return self._inconclusive(f"HTTP {response.status_code}")

        body = response.text
        if self._looks_like_block_page(body):
            return self._inconclusive("response looks like a bot-block page")

        found = self.name_appears_in_results(body, query.full_name)
        return ListingResult(
            source=self.source_id,
            found=found,
            inconclusive=False,
            listings_url=url,
            notes="match found in result cards" if found else "no match in result cards",
            checked_at=self._now(),
        )

    def _looks_like_block_page(self, body: str) -> bool:
        markers = DEFAULT_BLOCK_MARKERS + tuple(m.lower() for m in self.BLOCK_MARKERS)
        lowered = body.lower()
        return any(marker in lowered for marker in markers)

    def _inconclusive(self, note: str) -> ListingResult:
        return ListingResult(
            source=self.source_id,
            found=False,
            inconclusive=True,
            notes=note,
            checked_at=self._now(),
        )


def _name_in_card_block(body: str, full_name: str, card_class: str) -> bool:
    """Conservative: only count as found if the name appears inside an HTML
    element whose class contains the configured card-class substring.

    False negatives are acceptable; false positives are not (they'd mark a
    broker noncompliant when the user has already been removed).
    """
    if not full_name.strip() or not card_class.strip():
        return False
    needle = re.escape(full_name.strip())
    class_pattern = re.escape(card_class)
    pattern = re.compile(
        rf'<[a-z]+[^>]*class="[^"]*{class_pattern}[^"]*"[^>]*>[\s\S]*?{needle}[\s\S]*?</[a-z]+>',
        flags=re.IGNORECASE,
    )
    return bool(pattern.search(body))
