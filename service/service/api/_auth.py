"""Optional API-key authentication.

If `DELETE_ME_API_KEY` is set, every request must carry a matching
`X-API-Key` header (case-insensitive name) — otherwise the request is
rejected with 401. If the env var is unset (the default for the Tauri
loopback case), no check runs.

Health endpoints (`/health`) are always exempt so a remote operator can
liveness-probe without an API key.
"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

ENV_KEY = "DELETE_ME_API_KEY"
HEADER_NAME = "X-API-Key"
EXEMPT_PATHS = ("/health",)


def expected_key() -> str | None:
    raw = os.environ.get(ENV_KEY)
    if not raw:
        return None
    return raw


def check_api_key(request: Request) -> None:
    """FastAPI dependency: enforce the X-API-Key header if configured."""
    expected = expected_key()
    if expected is None:
        return
    if request.url.path in EXEMPT_PATHS:
        return
    provided = request.headers.get(HEADER_NAME) or request.headers.get(HEADER_NAME.lower())
    # Constant-time comparison to avoid leaking key length / prefix via
    # response-time analysis.
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "missing or invalid X-API-Key")
