"""InstantCheckmate audit adapter (experimental).

Sibling to TruthFinder; the public search shape is similar.
Anti-bot via PerimeterX. Expect inconclusive frequently.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class InstantCheckmateAdapter(PeopleSearchAdapter):
    source_id = "instantcheckmate_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.instantcheckmate.com/people/{name}/{location}"
    )
    CARD_CLASS_PATTERN = "search-result"
    BLOCK_MARKERS = ("/_px/", "px-captcha")
