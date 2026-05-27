"""FamilyTreeNow audit adapter (experimental).

FamilyTreeNow has historically been one of the more scraper-friendly
people-search sites. The detail results render server-side, which means
the name-in-card heuristic works without JS.

Experimental: needs real-world validation; degrades to inconclusive on
any block / 4xx / 5xx response.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ._people_search_base import PeopleSearchAdapter
from .base import AuditQuery


class FamilyTreeNowAdapter(PeopleSearchAdapter):
    source_id = "familytreenow_search"
    SEARCH_URL_TEMPLATE = "https://www.familytreenow.com/search/genealogy/results?first={first}&last={last}&citystatezip={location}"
    CARD_CLASS_PATTERN = "result"

    def build_url(self, query: AuditQuery) -> str:
        first, _, last = query.full_name.strip().partition(" ")
        # If the name doesn't split cleanly, fall back to putting the whole
        # name in the last-name slot — FTN's search tolerates it.
        if not last:
            first, last = "", query.full_name.strip()
        return self.SEARCH_URL_TEMPLATE.format(
            first=quote_plus(first),
            last=quote_plus(last),
            location=quote_plus(self.format_location(query)),
        )
