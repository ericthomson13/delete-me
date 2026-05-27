"""Nuwber audit adapter (experimental).

Nuwber uses a path-based URL: /persons/{first}-{last}/{state}/{city}.
The search-results page (used here for breadth) accepts query strings.

Experimental.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class NuwberAdapter(PeopleSearchAdapter):
    source_id = "nuwber_search"
    SEARCH_URL_TEMPLATE = "https://nuwber.com/search?name={name}&city={location}"
    CARD_CLASS_PATTERN = "person"
