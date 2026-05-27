"""TruePeopleSearch audit adapter (experimental).

Read-only public search. We hit the same URL a browser would and look for
the consumer's name in the response HTML. Shared rate-limit + block-page
detection + name-match logic lives in PeopleSearchAdapter.

This adapter is marked experimental:
- It can break any time TruePeopleSearch changes its HTML.
- It runs at 1 request per minute per adapter instance via a simple
  in-process rate limiter.
- It is NOT exercised in the unit test suite (tests use MockAuditAdapter).
- Real-world invocation happens only through `delete-me audit` /
  `delete-me audit-due` / `delete-me presence-check`, where a single
  failure cannot block other audits.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class TruePeopleSearchAdapter(PeopleSearchAdapter):
    source_id = "truepeoplesearch_search"
    SEARCH_URL_TEMPLATE = (
        "https://www.truepeoplesearch.com/results?name={name}"
        "&citystatezip={location}"
    )
