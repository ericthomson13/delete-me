"""Breach-check + password-check API.

Three endpoints:

- GET /breaches/providers — which providers are configured (with setup
  hints for the ones that aren't). Lets a client render a "configure
  HIBP" hint without trying a request that'll exit early.
- POST /profiles/{profile_id}/breach-check — run all available providers
  for the profile's email (or explicit emails). Mirrors
  `delete-me breach-check`. Failed providers are reported, not raised.
- POST /passwords/check — HIBP k-anonymity Pwned Passwords lookup. The
  password crosses the wire from the client to this service, then only
  the SHA-1 prefix leaves this service. For docker self-host deployments
  with remote clients, only call this over TLS.
"""

from __future__ import annotations

import json

from delete_me.breaches import BreachOrchestrator, discover_registry
from delete_me.breaches.passwords import PwnedPasswordsClient
from delete_me.db import BreachExposure, Profile
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ._deps import get_session

router = APIRouter(tags=["breaches"])


class BreachCheckRequest(BaseModel):
    emails: list[str] | None = Field(
        default=None,
        description="Emails to check. Default: the profile's email.",
    )


class PasswordCheckRequest(BaseModel):
    password: str = Field(min_length=1, description="The password to look up.")


def _row_to_dict(r: BreachExposure) -> dict:
    return {
        "id": r.id,
        "source": r.source,
        "email": r.email,
        "breach_name": r.breach_name,
        "breach_date": r.breach_date,
        "data_classes": json.loads(r.data_classes_json or "[]"),
        "description_excerpt": r.description_excerpt,
        "checked_at": r.checked_at.isoformat() if r.checked_at else None,
    }


@router.get("/breaches/providers")
def list_providers() -> dict:
    """Report which breach providers are configured + setup hints for the rest."""
    adapters, statuses = discover_registry()
    return {
        "active": [a.source_id for a in adapters],
        "providers": [
            {"source_id": s.source_id, "available": s.available, "detail": s.detail}
            for s in statuses
        ],
    }


@router.post("/profiles/{profile_id}/breach-check")
def run_breach_check(
    profile_id: int,
    body: BreachCheckRequest | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """Run every available breach provider for the given profile."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, f"profile {profile_id} not found")

    adapters, statuses = discover_registry()
    if not adapters:
        raise HTTPException(
            503,
            {
                "error": "no breach providers configured",
                "providers": [
                    {"source_id": s.source_id, "detail": s.detail}
                    for s in statuses
                ],
            },
        )

    req = body or BreachCheckRequest()
    targets = req.emails if req.emails else ([profile.email] if profile.email else [])
    if not targets:
        raise HTTPException(400, "profile has no email and no emails provided")

    orch = BreachOrchestrator.from_registry(adapters)
    results: dict[str, list[dict]] = {}
    for email in targets:
        rows = orch.check_email(session, profile, email)
        results[email] = [_row_to_dict(r) for r in rows]

    return {
        "results": results,
        "providers": {
            "active": [a.source_id for a in orch.adapters],
            "skipped_at_startup": [
                {"source_id": s.source_id, "detail": s.detail}
                for s in statuses
                if not s.available
            ],
            "disabled_mid_run": [
                {"source_id": d.source_id, "detail": d.detail}
                for d in orch.runtime_disabled
            ],
        },
    }


@router.post("/passwords/check")
def check_password(body: PasswordCheckRequest) -> dict:
    """k-anonymity Pwned Passwords lookup. Returns the breach count, never persisted."""
    try:
        count = PwnedPasswordsClient().lookup(body.password)
    except Exception as exc:  # noqa: BLE001 — network/parse failures all surface the same way
        raise HTTPException(502, f"pwned-passwords lookup failed: {exc}") from exc
    return {"breach_count": count, "found": count > 0}
