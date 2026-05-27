"""DeHashed breach-search adapter.

DeHashed indexes leak corpora that often include plaintext credentials.
This adapter is off by default — it activates only when BOTH
DEHASHED_USERNAME and DEHASHED_API_KEY are set.

Setup: subscribe at https://dehashed.com/pricing, then on
https://dehashed.com/profile copy the API key and your account email,
and export:

  export DEHASHED_USERNAME='you@example.com'
  export DEHASHED_API_KEY='...'

Each record carries a `database_name` (the breach corpus the record came
from) and a set of populated columns (email, username, password,
hashed_password, name, phone, address, ip_address). We collapse to one
BreachExposureResult per unique database_name and roll up the populated
columns into data_classes so the user sees what was exposed without us
ever persisting the credentials themselves.
"""

from __future__ import annotations

import logging
import os

import httpx

from .base import BreachAdapter, BreachAdapterUnavailable, BreachExposureResult

LOG = logging.getLogger(__name__)

# Columns we surface as data_classes if non-empty in a record.
_DATA_CLASS_FIELDS = (
    ("email", "Email addresses"),
    ("username", "Usernames"),
    ("password", "Passwords (plaintext)"),
    ("hashed_password", "Passwords (hashed)"),
    ("name", "Names"),
    ("phone", "Phone numbers"),
    ("address", "Physical addresses"),
    ("ip_address", "IP addresses"),
    ("vin", "Vehicle identifiers"),
)


class DeHashedAdapter(BreachAdapter):
    source_id = "dehashed"
    SEARCH_URL = "https://api.dehashed.com/search"
    USER_AGENT = "delete-me/0.1 (open-source data-broker opt-out tool)"

    def __init__(
        self,
        username: str | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        user = username if username is not None else os.environ.get("DEHASHED_USERNAME")
        key = api_key if api_key is not None else os.environ.get("DEHASHED_API_KEY")
        if not user or not key:
            raise BreachAdapterUnavailable(
                "DeHashed needs DEHASHED_USERNAME and DEHASHED_API_KEY. "
                "Subscribe at https://dehashed.com/pricing and grab both from "
                "https://dehashed.com/profile, then export them to enable the "
                "DeHashed provider."
            )
        self.client = client or httpx.Client(
            timeout=20.0,
            auth=(user, key),
            headers={
                "Accept": "application/json",
                "User-Agent": self.USER_AGENT,
            },
        )

    def check(self, email: str) -> list[BreachExposureResult]:
        try:
            response = self.client.get(
                self.SEARCH_URL,
                params={"query": f"email:{email}", "size": 100},
            )
        except httpx.HTTPError as exc:
            LOG.warning("dehashed fetch failed for %s: %s", email, exc)
            return []

        if response.status_code == 401:
            raise BreachAdapterUnavailable(
                "DeHashed rejected the credentials (401). Re-check "
                "DEHASHED_USERNAME and DEHASHED_API_KEY."
            )
        if response.status_code == 402:
            raise BreachAdapterUnavailable(
                "DeHashed account is out of query credits (402). "
                "Top up at https://dehashed.com/billing."
            )
        if response.status_code >= 400:
            LOG.warning("dehashed HTTP %s for %s", response.status_code, email)
            return []

        payload = response.json() if response.content else {}
        entries = payload.get("entries") or []

        by_db: dict[str, set[str]] = {}
        for entry in entries:
            db = str(entry.get("database_name") or "dehashed")
            classes = by_db.setdefault(db, set())
            for field, label in _DATA_CLASS_FIELDS:
                if entry.get(field):
                    classes.add(label)

        now = self._now()
        return [
            BreachExposureResult(
                source=self.source_id,
                email=email,
                breach_name=db,
                breach_date=None,  # DeHashed doesn't carry a per-record breach date
                data_classes=tuple(sorted(classes)),
                description_excerpt=None,
                checked_at=now,
            )
            for db, classes in sorted(by_db.items())
        ]
