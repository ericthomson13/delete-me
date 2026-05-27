"""ThatsThem audit adapter (experimental).

ThatsThem uses a path-based name URL pattern: /name/{first}-{last}. The
city/state filter is appended as a query string.

Experimental.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ._people_search_base import PeopleSearchAdapter
from .base import AuditQuery


class ThatsThemAdapter(PeopleSearchAdapter):
    source_id = "thatsthem_search"
    SEARCH_URL_TEMPLATE = "https://thatsthem.com/name/{first}-{last}?location={location}"
    CARD_CLASS_PATTERN = "result-record"

    def build_url(self, query: AuditQuery) -> str:
        first, _, last = query.full_name.strip().partition(" ")
        if not last:
            first, last = "", query.full_name.strip()
        return self.SEARCH_URL_TEMPLATE.format(
            first=quote_plus(first),
            last=quote_plus(last),
            location=quote_plus(self.format_location(query)),
        )
