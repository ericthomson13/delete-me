"""IntelX phonebook-search breach adapter.

IntelX exposes a leaked-document corpus broader than HIBP (forums, paste
sites, telegram dumps, etc.). The phonebook endpoint takes an email and
returns records that mention it; we collapse to one BreachExposureResult
per unique source bucket so the output stays comparable to HIBP's
breach-level shape.

Setup: subscribe and grab an API key at https://intelx.io/account, then
export INTELX_API_KEY. The free tier is rate-limited; this adapter polls
at most POLL_MAX times with a small sleep between polls.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from .base import BreachAdapter, BreachAdapterUnavailable, BreachExposureResult

LOG = logging.getLogger(__name__)


class IntelXAdapter(BreachAdapter):
    source_id = "intelx"
    DEFAULT_BASE_URL = "https://2.intelx.io"
    USER_AGENT = "delete-me/0.1 (open-source data-broker opt-out tool)"
    POLL_MAX = 5
    POLL_INTERVAL_S = 1.5
    MAX_RESULTS = 100

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("INTELX_API_KEY")
        if not key:
            raise BreachAdapterUnavailable(
                "INTELX_API_KEY not set. Get a key at https://intelx.io/account "
                "and export INTELX_API_KEY to enable the IntelX provider."
            )
        self.base_url = (base_url or os.environ.get("INTELX_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.client = client or httpx.Client(
            timeout=20.0,
            headers={
                "x-key": key,
                "User-Agent": self.USER_AGENT,
                "content-type": "application/json",
            },
        )

    def check(self, email: str) -> list[BreachExposureResult]:
        try:
            search_id = self._start_search(email)
        except httpx.HTTPError as exc:
            LOG.warning("intelx start-search failed for %s: %s", email, exc)
            return []
        if search_id is None:
            return []

        records = self._collect_records(search_id)
        if not records:
            return []

        # Collapse to one row per unique bucket — IntelX returns many records
        # per breach, but we want HIBP-comparable per-source granularity.
        by_bucket: dict[str, dict] = {}
        for rec in records:
            bucket = str(rec.get("bucket") or rec.get("bucketh") or "intelx")
            existing = by_bucket.get(bucket)
            date = rec.get("date") or rec.get("added")
            name = rec.get("name") or ""
            if existing is None:
                by_bucket[bucket] = {
                    "date": date,
                    "name": name,
                }
                continue
            # Keep the earliest date and longest name we've seen.
            if date and (existing["date"] is None or date < existing["date"]):
                existing["date"] = date
            if name and len(name) > len(existing["name"]):
                existing["name"] = name

        now = self._now()
        return [
            BreachExposureResult(
                source=self.source_id,
                email=email,
                breach_name=bucket,
                breach_date=_date_only(meta["date"]),
                data_classes=(),
                description_excerpt=meta["name"] or None,
                checked_at=now,
            )
            for bucket, meta in sorted(by_bucket.items())
        ]

    def _start_search(self, email: str) -> str | None:
        url = f"{self.base_url}/phonebook/search"
        body = {
            "term": email,
            "maxresults": self.MAX_RESULTS,
            "media": 0,
            "target": 0,
            "terminate": [],
        }
        response = self.client.post(url, json=body)
        if response.status_code == 401:
            raise BreachAdapterUnavailable("IntelX rejected the API key (401).")
        if response.status_code >= 400:
            LOG.warning("intelx start-search HTTP %s", response.status_code)
            return None
        data = response.json() if response.content else {}
        return data.get("id")

    def _collect_records(self, search_id: str) -> list[dict]:
        url = f"{self.base_url}/phonebook/search/result"
        records: list[dict] = []
        for _ in range(self.POLL_MAX):
            response = self.client.get(
                url,
                params={"id": search_id, "limit": self.MAX_RESULTS, "offset": 0},
            )
            if response.status_code == 401:
                raise BreachAdapterUnavailable("IntelX rejected the API key (401).")
            if response.status_code >= 400:
                LOG.warning("intelx result HTTP %s", response.status_code)
                return records
            payload = response.json() if response.content else {}
            batch = payload.get("selectors") or payload.get("records") or []
            records.extend(batch)
            status = payload.get("status")
            # status: 0=success, 1=more available, 2=delete, 3=no results
            if status in (0, 2, 3):
                break
            time.sleep(self.POLL_INTERVAL_S)
        return records


def _date_only(value) -> str | None:
    if not value:
        return None
    text = str(value)
    return text[:10] if len(text) >= 10 else text
