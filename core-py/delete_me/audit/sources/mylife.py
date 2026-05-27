"""MyLife audit adapter (experimental).

MyLife has notoriously aggressive anti-bot and frequent HTML changes.
Wired anyway because removal requests there are critical (MyLife is one
of the most-complained-about brokers).
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ._people_search_base import PeopleSearchAdapter
from .base import AuditQuery


class MyLifeAdapter(PeopleSearchAdapter):
    source_id = "mylife_search"
    SEARCH_URL_TEMPLATE = "https://www.mylife.com/pub-people-search.pubview?search={name}+{location}"
    CARD_CLASS_PATTERN = "people-card"

    def build_url(self, query: AuditQuery) -> str:
        return self.SEARCH_URL_TEMPLATE.format(
            name=quote_plus(query.full_name),
            location=quote_plus(self.format_location(query)).replace("%2C+", "+"),
        )
