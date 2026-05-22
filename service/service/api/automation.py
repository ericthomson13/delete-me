"""HTTP surface for the tiered submission-automation framework (#8/#11).

Pure RPC: takes a case_id + dry_run, runs the dispatcher, returns the
SubmissionResult. Does not mutate the case row — case-status flow lives
in the existing /cases/{id}/send path, and threading automation through
it cleanly is a Phase 8+ follow-up.
"""

from __future__ import annotations

from dataclasses import asdict

from delete_me.automation import dispatch
from delete_me.cases import profile_to_consumer
from delete_me.db import Case, Profile
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ._deps import get_session

router = APIRouter(prefix="/cases", tags=["automation"])


class AutomationRunIn(BaseModel):
    dry_run: bool = True  # safe default — never submit unless explicitly asked


@router.post("/{case_id}/automation-run")
def automation_run(
    case_id: int,
    payload: AutomationRunIn,
    session: Session = Depends(get_session),
) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    profile = session.get(Profile, case.profile_id)
    if not profile:
        raise HTTPException(404, f"profile {case.profile_id} for case {case_id} not found")

    consumer = profile_to_consumer(profile)
    try:
        result = dispatch(case.broker_id, consumer, dry_run=payload.dry_run)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    out = asdict(result)
    # Path isn't JSON-serializable.
    if result.screenshot_path is not None:
        out["screenshot_path"] = str(result.screenshot_path)
    # screenshot_bytes (if a script returned them) should NOT cross the
    # HTTP boundary — they belong on disk via the CLI's --screenshot-dir
    # flag, not in an API response.
    if "screenshot_bytes" in out.get("evidence_payload", {}):
        out["evidence_payload"] = {
            k: v for k, v in out["evidence_payload"].items() if k != "screenshot_bytes"
        }
    return out
