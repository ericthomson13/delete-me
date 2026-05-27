"""HaveIBeenPwned Pwned Passwords — k-anonymity check.

Different from the email-breach endpoint in three important ways:

1. No API key required, no subscription. Free.
2. The password never leaves the machine in a recoverable form. We SHA-1
   the password locally, send only the first 5 characters of the hash,
   and search the returned suffix list ourselves.
3. Results are never persisted. The point of this check is exactly to
   know without writing anything down.

Setup: nothing to set up. Just run `delete-me password-check` and you'll
be prompted for the password with input hidden.
"""

from __future__ import annotations

import hashlib
import logging

import httpx

LOG = logging.getLogger(__name__)

RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"
USER_AGENT = "delete-me/0.1 (open-source data-broker opt-out tool)"


class PwnedPasswordsClient:
    """Tiny wrapper so tests can inject a fake httpx.Client."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=10.0,
            headers={
                "User-Agent": USER_AGENT,
                "Add-Padding": "true",  # request padding to defeat range-size fingerprinting
            },
        )

    def lookup(self, password: str) -> int:
        """Return the number of times the password appears in HIBP's corpus.

        0 means not seen. Anything > 0 means the password is in at least one
        known breach and should be considered compromised.

        Raises httpx.HTTPError on transport failure — callers should wrap.
        """
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        response = self.client.get(RANGE_URL.format(prefix=prefix))
        response.raise_for_status()
        for line in response.text.splitlines():
            if ":" not in line:
                continue
            candidate, count = line.split(":", 1)
            # Padding rows have count=0; skip them defensively and ignore
            # whitespace.
            if candidate.strip().upper() == suffix:
                try:
                    return int(count.strip())
                except ValueError:
                    return 0
        return 0
