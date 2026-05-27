"""PeopleLooker audit adapter (experimental).

PeopleLooker is part of the BeenVerified/Intelius family of brokers; HTML
shape mirrors them closely. Akamai-style anti-bot.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class PeopleLookerAdapter(PeopleSearchAdapter):
    source_id = "peoplelooker_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.peoplelooker.com/app/search/person?fname={name}&state={location}"
    )
    CARD_CLASS_PATTERN = "person-result"
    BLOCK_MARKERS = ("/_Incapsula_Resource",)
