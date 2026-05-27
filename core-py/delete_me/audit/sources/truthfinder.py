"""TruthFinder audit adapter (experimental).

Sibling to InstantCheckmate. Same anti-bot stack (PerimeterX).
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class TruthFinderAdapter(PeopleSearchAdapter):
    source_id = "truthfinder_search"
    SEARCH_URL_TEMPLATE = "https://www.truthfinder.com/people-search/{name}/{location}"
    CARD_CLASS_PATTERN = "search-result"
    BLOCK_MARKERS = ("/_px/", "px-captcha")
