"""Radaris audit adapter (experimental).

Radaris uses a path-style URL keyed on the name and state.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ._people_search_base import PeopleSearchAdapter
from .base import AuditQuery


class RadarisAdapter(PeopleSearchAdapter):
    source_id = "radaris_search"
    SEARCH_URL_TEMPLATE = "https://radaris.com/p/{first}/{last}"
    CARD_CLASS_PATTERN = "person-list-item"

    def build_url(self, query: AuditQuery) -> str:
        first, _, last = query.full_name.strip().partition(" ")
        if not last:
            first, last = "", query.full_name.strip()
        return self.SEARCH_URL_TEMPLATE.format(
            first=quote_plus(first),
            last=quote_plus(last),
        )
