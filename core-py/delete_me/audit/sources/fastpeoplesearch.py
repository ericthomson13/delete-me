"""FastPeopleSearch audit adapter (experimental).

URL pattern based on the publicly visible search form. The site uses a
path-style URL: /name/{first}-{last}_{city}-{state}. We approximate with
a query-string form first; if real-world hits show the path form is the
only accepted shape, override build_url accordingly.

Experimental: selectors and URL shape inferred from common patterns and
may need tuning against the live site. Failures degrade to inconclusive,
never block a case.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class FastPeopleSearchAdapter(PeopleSearchAdapter):
    source_id = "fastpeoplesearch_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.fastpeoplesearch.com/results?name={name}&citystatezip={location}"
    )
