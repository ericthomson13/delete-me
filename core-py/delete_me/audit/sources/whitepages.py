"""Whitepages audit adapter (experimental).

Whitepages uses a path-style URL: /name/{First}-{Last}/{State}-{City}.
Anti-bot is moderate (Cloudflare). Failures degrade to inconclusive.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ._people_search_base import PeopleSearchAdapter
from .base import AuditQuery


class WhitepagesAdapter(PeopleSearchAdapter):
    source_id = "whitepages_search"
    SEARCH_URL_TEMPLATE = "https://www.whitepages.com/name/{first}-{last}/{location}"
    CARD_CLASS_PATTERN = "search-result"

    def build_url(self, query: AuditQuery) -> str:
        first, _, last = query.full_name.strip().partition(" ")
        if not last:
            first, last = "", query.full_name.strip()
        loc = ""
        if query.current_state and query.current_city:
            loc = f"{query.current_state}-{query.current_city.replace(' ', '-')}"
        elif query.current_state:
            loc = query.current_state
        return self.SEARCH_URL_TEMPLATE.format(
            first=quote_plus(first),
            last=quote_plus(last),
            location=quote_plus(loc),
        )
