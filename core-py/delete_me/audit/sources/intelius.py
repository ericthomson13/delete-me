"""Intelius audit adapter (experimental).

Intelius is owned by the same group as BeenVerified, so the HTML shape
is similar. Akamai-style anti-bot.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class InteliusAdapter(PeopleSearchAdapter):
    source_id = "intelius_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.intelius.com/people-search/{name}/{location}"
    )
    CARD_CLASS_PATTERN = "person-result"
    BLOCK_MARKERS = ("/_Incapsula_Resource",)
