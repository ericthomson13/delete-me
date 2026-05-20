from __future__ import annotations

from delete_me.cases import case_as_dict, submit_via_drop
from delete_me.db import Profile
from delete_me.transport import DropTransport
from delete_me.transport.base import TransportError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ._deps import get_session

router = APIRouter(prefix="/drop", tags=["drop"])


class DropSubmitIn(BaseModel):
    profile_id: int
    live: bool = False


@router.post("/submit")
def submit(
    payload: DropSubmitIn,
    session: Session = Depends(get_session),
) -> dict:
    profile = session.get(Profile, payload.profile_id)
    if not profile:
        raise HTTPException(404, f"profile {payload.profile_id} not found")
    transport = DropTransport()
    try:
        receipt, cases = submit_via_drop(session, profile, transport, live=payload.live)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except TransportError as exc:
        raise HTTPException(502, str(exc)) from exc

    return {
        "receipt": {
            "receipt_id": receipt.receipt_id,
            "dry_run": receipt.dry_run,
            "accepted_at": receipt.accepted_at.isoformat(),
            "on_disk_path": str(receipt.on_disk_path) if receipt.on_disk_path else None,
            "broker_calprivacy_ids": list(receipt.broker_calprivacy_ids),
        },
        "cases": [case_as_dict(c) for c in cases],
    }
