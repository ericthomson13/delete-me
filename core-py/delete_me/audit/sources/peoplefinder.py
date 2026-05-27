"""PeopleFinder (peoplefinders.com) audit adapter (experimental).

The broker's YAML id is `peoplefinder` but its public URL is
peoplefinders.com (plural). Search is a query-string GET.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class PeopleFinderAdapter(PeopleSearchAdapter):
    source_id = "peoplefinder_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.peoplefinders.com/people/{name}/{location}"
    )
    CARD_CLASS_PATTERN = "result-row"
