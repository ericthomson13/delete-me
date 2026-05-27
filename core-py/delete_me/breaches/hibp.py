"""HaveIBeenPwned breach-corpus adapter.

Uses the v3 breachedaccount endpoint, which requires a paid API key
(HIBP_API_KEY env var). If the key is absent or invalid, raises
BreachAdapterUnavailable so the CLI can show a one-time setup message
instead of silently returning empty.

Honors HIBP's 1.5s minimum interval between requests via a single
in-process throttle. That's sufficient for the small N of emails a typical
consumer profile holds; a multi-tenant service would want a real limiter.
"""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import quote

import httpx

from .base import BreachAdapter, BreachAdapterUnavailable, BreachExposureResult

LOG = logging.getLogger(__name__)


class HIBPAdapter(BreachAdapter):
    source_id = "hibp"
    BASE_URL = "https://haveibeenpwned.com/api/v3"
    USER_AGENT = "delete-me/0.1 (open-source data-broker opt-out tool)"
    MIN_INTERVAL_S = 1.5

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("HIBP_API_KEY")
        if not key:
            raise BreachAdapterUnavailable(
                "HIBP_API_KEY not set. Subscribe at "
                "https://haveibeenpwned.com/api/key and export the key to enable "
                "`delete-me breach-check`."
            )
        self.client = client or httpx.Client(
            timeout=15.0,
            headers={
                "hibp-api-key": key,
                "User-Agent": self.USER_AGENT,
            },
        )
        self._last_request_at: float = 0.0

    def _maybe_sleep(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.MIN_INTERVAL_S:
            time.sleep(self.MIN_INTERVAL_S - elapsed)

    def check(self, email: str) -> list[BreachExposureResult]:
        url = f"{self.BASE_URL}/breachedaccount/{quote(email, safe='@.+-_')}"
        self._maybe_sleep()
        try:
            response = self.client.get(url, params={"truncateResponse": "false"})
            self._last_request_at = time.monotonic()
        except httpx.HTTPError as exc:
            LOG.warning("hibp fetch failed for %s: %s", email, exc)
            return []

        if response.status_code == 404:
            return []
        if response.status_code == 401:
            raise BreachAdapterUnavailable("HIBP rejected the API key (401).")
        if response.status_code == 429:
            # Retry once, honoring Retry-After, then give up.
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            LOG.info("hibp rate-limited; sleeping %ss before single retry", retry_after)
            time.sleep(retry_after)
            try:
                response = self.client.get(url, params={"truncateResponse": "false"})
                self._last_request_at = time.monotonic()
            except httpx.HTTPError as exc:
                LOG.warning("hibp retry failed for %s: %s", email, exc)
                return []
            if response.status_code == 404:
                return []
            if response.status_code >= 400:
                LOG.warning("hibp retry returned HTTP %s for %s", response.status_code, email)
                return []
        elif response.status_code >= 400:
            LOG.warning("hibp returned HTTP %s for %s", response.status_code, email)
            return []

        payload = response.json()
        if not isinstance(payload, list):
            return []
        now = self._now()
        return [
            BreachExposureResult(
                source=self.source_id,
                email=email,
                breach_name=str(item.get("Name", "")),
                breach_date=item.get("BreachDate"),
                data_classes=tuple(item.get("DataClasses") or ()),
                description_excerpt=_excerpt(item.get("Description")),
                checked_at=now,
            )
            for item in payload
            if item.get("Name")
        ]


def _parse_retry_after(value: str | None) -> float:
    if not value:
        return 2.0
    try:
        return max(1.0, float(value))
    except (TypeError, ValueError):
        return 2.0


def _excerpt(description: str | None, limit: int = 280) -> str | None:
    if not description:
        return None
    text = description.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
