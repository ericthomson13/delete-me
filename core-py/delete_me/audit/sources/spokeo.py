"""Spokeo audit adapter (experimental).

Spokeo has notoriously aggressive anti-bot (PerimeterX). Expect the
common case to be inconclusive=True. The adapter is wired anyway because
even a fraction of successful lookups beats none — Spokeo is one of the
most-requested brokers in the registry.

If a user wants reliable Spokeo presence-check, they'll need to swap in
a paid scraping service (out of scope here) or fall back to manually
checking the search URL.

Experimental.
"""

from __future__ import annotations

from ._people_search_base import PeopleSearchAdapter


class SpokeoAdapter(PeopleSearchAdapter):
    source_id = "spokeo_search"
    SEARCH_URL_TEMPLATE = "https://www.spokeo.com/{name}/{location}"
    # Spokeo's PerimeterX shows generic interstitials with this marker.
    BLOCK_MARKERS = ("/_px/", "px-captcha", "Please verify you are a human")
    CARD_CLASS_PATTERN = "single-column-list-item"
