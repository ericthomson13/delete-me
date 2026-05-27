"""BeenVerified audit adapter (experimental).

BeenVerified often gates detail results behind login, but the
people-search summary cards render server-side. Anti-bot via Akamai is
common; expect inconclusive often.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class BeenVerifiedAdapter(PeopleSearchAdapter):
    source_id = "beenverified_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.beenverified.com/app/search/person?fname={name}&state={location}"
    )
    CARD_CLASS_PATTERN = "person-result"
    BLOCK_MARKERS = ("/_Incapsula_Resource",)
