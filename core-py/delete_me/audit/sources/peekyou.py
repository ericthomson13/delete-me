"""PeekYou audit adapter (experimental).

PeekYou aggregates social-profile data. Search is a query-string GET;
less aggressive anti-bot than the people-search-only sites.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ._people_search_base import PeopleSearchAdapter
from .base import AuditQuery


class PeekYouAdapter(PeopleSearchAdapter):
    source_id = "peekyou_search"
    SEARCH_URL_TEMPLATE = "https://www.peekyou.com/{first}_{last}/{location}"
    CARD_CLASS_PATTERN = "listing"

    def build_url(self, query: AuditQuery) -> str:
        first, _, last = query.full_name.strip().partition(" ")
        if not last:
            first, last = "", query.full_name.strip()
        return self.SEARCH_URL_TEMPLATE.format(
            first=quote_plus(first.lower()),
            last=quote_plus(last.lower()),
            location=quote_plus(self.format_location(query)),
        )
