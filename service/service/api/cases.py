from __future__ import annotations

from delete_me.cases import case_as_dict, draft_case, list_cases, send_case
from delete_me.db import Case, CaseStatus, Profile
from delete_me.transport import PostmarkTransport
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from ._deps import get_session

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseDraftIn(BaseModel):
    profile_id: int
    broker_id: str


class SendIn(BaseModel):
    live: bool = False


class SendDraftsIn(BaseModel):
    live: bool = False
    profile_id: int | None = None


@router.post("")
def create_case(
    payload: CaseDraftIn,
    session: Session = Depends(get_session),
) -> dict:
    profile = session.get(Profile, payload.profile_id)
    if not profile:
        raise HTTPException(404, f"profile {payload.profile_id} not found")
    try:
        case, designation = draft_case(session, profile, payload.broker_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    out = case_as_dict(case)
    out["letter_markdown"] = case.letter_markdown
    out["agent_designation_markdown"] = designation.markdown if designation else None
    return out


@router.get("")
def list_all_cases(
    profile_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    return [case_as_dict(c) for c in list_cases(session, profile_id=profile_id)]


@router.get("/{case_id}")
def get_case(case_id: int, session: Session = Depends(get_session)) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    out = case_as_dict(case)
    out["letter_markdown"] = case.letter_markdown
    return out


@router.post("/send-drafts")
def send_all_drafts(
    payload: SendDraftsIn,
    session: Session = Depends(get_session),
) -> dict:
    """Bulk-send every case in DRAFT status, optionally scoped to one profile.

    Mirrors `delete-me send --all-drafts`. Per-case failures (e.g.,
    web-form-only brokers that can't be email-sent) are recorded without
    aborting the batch.
    """
    stmt = select(Case).where(Case.status == CaseStatus.DRAFT).order_by(Case.id)
    if payload.profile_id is not None:
        stmt = stmt.where(Case.profile_id == payload.profile_id)
    targets = list(session.exec(stmt))

    transport = PostmarkTransport()
    sent_rows: list[dict] = []
    skipped_rows: list[dict] = []
    failed_rows: list[dict] = []

    for case in targets:
        try:
            result = send_case(session, case, transport, live=payload.live)
        except ValueError as exc:
            failed_rows.append({
                "case_id": case.id,
                "broker_id": case.broker_id,
                "error": str(exc),
            })
            continue
        sent_rows.append({
            "case_id": case.id,
            "broker_id": case.broker_id,
            "dry_run": result.dry_run,
            "case": case_as_dict(case),
        })

    return {
        "sent": sent_rows,
        "skipped": skipped_rows,
        "failed": failed_rows,
        "summary": {
            "total": len(targets),
            "sent": len(sent_rows),
            "skipped": len(skipped_rows),
            "failed": len(failed_rows),
        },
    }


@router.post("/{case_id}/send")
def send(
    case_id: int,
    payload: SendIn,
    session: Session = Depends(get_session),
) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    transport = PostmarkTransport()
    try:
        result = send_case(session, case, transport, live=payload.live)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        "case": case_as_dict(case),
        "result": {
            "dry_run": result.dry_run,
            "message_id": result.message_id,
            "to": result.to,
            "subject": result.subject,
            "accepted_at": result.accepted_at.isoformat(),
        },
    }
