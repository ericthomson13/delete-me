"""Presence-check API — pre-send discovery surface.

Mirrors `delete-me presence-check` from the CLI. POST a profile_id and
optional broker subset / fresh_days; rows are persisted to presence_results
and returned. GET returns the latest stored row per (broker, source) for a
profile without re-hitting any source.
"""

from __future__ import annotations

import os

from delete_me.audit import PresenceOrchestrator
from delete_me.audit.orchestrator import default_registry, production_registry
from delete_me.db import PresenceResult, Profile
from delete_me.registry import load_brokers
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ._deps import get_session

router = APIRouter(tags=["presence"])


class PresenceCheckRequest(BaseModel):
    broker_ids: list[str] | None = Field(
        default=None,
        description="Subset of broker ids to check. Default: every broker with audit_sources.",
    )
    fresh_days: int = Field(default=7, ge=0, description="Reuse a stored row if newer than N days.")


def _orchestrator() -> PresenceOrchestrator:
    use_mock = os.environ.get("DELETE_ME_AUDIT_USE_MOCK", "").lower() in ("1", "true")
    registry = default_registry() if use_mock else production_registry()
    return PresenceOrchestrator.from_registry(registry)


def _row_to_dict(r: PresenceResult) -> dict:
    if r.found:
        status = "found"
    elif r.inconclusive:
        status = "inconclusive"
    else:
        status = "not_found"
    return {
        "id": r.id,
        "broker_id": r.broker_id,
        "source": r.source,
        "status": status,
        "found": r.found,
        "inconclusive": r.inconclusive,
        "listings_url": r.listings_url,
        "notes": r.notes,
        "checked_at": r.checked_at.isoformat() if r.checked_at else None,
    }


@router.post("/profiles/{profile_id}/presence-check")
def run_presence_check(
    profile_id: int,
    body: PresenceCheckRequest | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """Run presence-check for the given profile. Persists results."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, f"profile {profile_id} not found")

    req = body or PresenceCheckRequest()
    all_brokers = load_brokers()
    if req.broker_ids is not None:
        wanted = set(req.broker_ids)
        selected = [b for b in all_brokers if b.id in wanted]
        unknown = wanted - {b.id for b in selected}
        if unknown:
            raise HTTPException(400, f"unknown broker ids: {sorted(unknown)}")
    else:
        selected = all_brokers

    orch = _orchestrator()
    results = orch.check_profile(session, profile, brokers=selected, fresh_days=req.fresh_days)

    no_source = sum(1 for r in results if r.source == "(none)")
    found = sum(1 for r in results if r.found)
    not_found = sum(1 for r in results if not r.found and not r.inconclusive and r.source != "(none)")
    inconclusive = sum(1 for r in results if r.inconclusive and r.source != "(none)")

    return {
        "results": [_row_to_dict(r) for r in results],
        "summary": {
            "found": found,
            "not_found": not_found,
            "inconclusive": inconclusive,
            "no_audit_source_configured": no_source,
            "brokers_checked": len(selected),
        },
    }


@router.get("/profiles/{profile_id}/presence-results")
def list_presence_results(
    profile_id: int,
    broker_id: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    """Latest stored row per (broker, source) for a profile. No re-query."""
    profile = session.get(Profile, profile_id)
    if not profile:
        raise HTTPException(404, f"profile {profile_id} not found")

    stmt = (
        select(PresenceResult)
        .where(PresenceResult.profile_id == profile_id)
        .order_by(PresenceResult.checked_at.desc())
    )
    if broker_id is not None:
        stmt = stmt.where(PresenceResult.broker_id == broker_id)

    seen: dict[tuple[str, str], PresenceResult] = {}
    for row in session.exec(stmt):
        key = (row.broker_id, row.source)
        if key not in seen:
            seen[key] = row
    return [_row_to_dict(r) for r in seen.values()]
