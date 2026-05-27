from __future__ import annotations

import os

from delete_me.audit import AuditOrchestrator
from delete_me.audit.orchestrator import default_registry, production_registry
from delete_me.db import AuditResult, Case
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ._deps import get_session

router = APIRouter(tags=["audits"])


def _orchestrator() -> AuditOrchestrator:
    use_mock = os.environ.get("DELETE_ME_AUDIT_USE_MOCK", "").lower() in ("1", "true")
    registry = default_registry() if use_mock else production_registry()
    return AuditOrchestrator.from_registry(registry)


@router.post("/cases/{case_id}/audit")
def run_audit(case_id: int, session: Session = Depends(get_session)) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    orch = _orchestrator()
    results = orch.audit_case(session, case)
    return {
        "case": {
            "id": case.id,
            "status": case.status.value,
            "last_audited_at": case.last_audited_at.isoformat()
            if case.last_audited_at
            else None,
        },
        "results": [
            {
                "id": r.id,
                "source": r.source,
                "found": r.found,
                "inconclusive": r.inconclusive,
                "listings_url": r.listings_url,
                "notes": r.notes,
                "checked_at": r.checked_at.isoformat(),
            }
            for r in results
        ],
    }


@router.get("/cases/{case_id}/audits")
def list_case_audits(case_id: int, session: Session = Depends(get_session)) -> list[dict]:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    rows = session.exec(
        select(AuditResult)
        .where(AuditResult.case_id == case_id)
        .order_by(AuditResult.checked_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "found": r.found,
            "inconclusive": r.inconclusive,
            "listings_url": r.listings_url,
            "notes": r.notes,
            "checked_at": r.checked_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/audits")
def list_all_audits(
    limit: int = 200, session: Session = Depends(get_session)
) -> list[dict]:
    """Cross-case audit log, newest first, capped at `limit`.

    Each row carries the case + broker context so the UI can show an
    aggregate audit timeline across every case without 1+N requests.
    """
    rows = session.exec(
        select(AuditResult, Case)
        .join(Case, AuditResult.case_id == Case.id)
        .order_by(AuditResult.checked_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "case_id": r.case_id,
            "broker_id": c.broker_id,
            "case_status": c.status.value,
            "source": r.source,
            "found": r.found,
            "inconclusive": r.inconclusive,
            "listings_url": r.listings_url,
            "notes": r.notes,
            "checked_at": r.checked_at.isoformat(),
        }
        for r, c in rows
    ]


@router.post("/audits/sweep")
def run_due_audits(
    limit: int = 20, session: Session = Depends(get_session)
) -> dict:
    """Run every case whose audit_due_at has passed (capped at limit)."""
    orch = _orchestrator()
    due = orch.cases_due(session, limit=limit)
    audited: list[dict] = []
    for case in due:
        try:
            orch.audit_case(session, case)
            audited.append({"case_id": case.id, "status": case.status.value})
        except Exception as exc:  # noqa: BLE001 — keep the sweep going
            audited.append({"case_id": case.id, "error": str(exc)})
    return {"count": len(audited), "audited": audited}
