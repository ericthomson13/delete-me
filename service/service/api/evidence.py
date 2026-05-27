from __future__ import annotations

import os
from pathlib import Path

from delete_me.db import Case
from delete_me.evidence import PackageBuilder
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from platformdirs import user_data_path
from sqlmodel import Session, select

from ._deps import get_session

router = APIRouter(tags=["evidence"])

ENV_OUT_DIR = "DELETE_ME_EVIDENCE_DIR"


def _evidence_dir() -> Path:
    """User-writable evidence directory.

    Defaults to platformdirs' per-user data path so the desktop app works
    out of the box on macOS/Linux/Windows without sudo. Override via
    DELETE_ME_EVIDENCE_DIR for server deployments (e.g. /var/lib/delete-me).
    """
    override = os.environ.get(ENV_OUT_DIR)
    if override:
        return Path(override)
    return user_data_path("delete-me", "delete-me") / "evidence"


@router.post("/cases/{case_id}/evidence")
def build_evidence(case_id: int, session: Session = Depends(get_session)) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    out_dir = _evidence_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    builder = PackageBuilder(out_dir=out_dir)
    pkg = builder.build(session, case)
    return {
        "case_id": pkg.case_id,
        "directory": str(pkg.directory),
        "zip": str(pkg.zip_path),
        "manifest": str(pkg.manifest_path),
        "file_count": len(pkg.files),
    }


@router.get("/cases/{case_id}/evidence/download")
def download_evidence(case_id: int, session: Session = Depends(get_session)) -> FileResponse:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    if not case.evidence_path:
        raise HTTPException(404, "no evidence package has been built for this case")
    path = Path(case.evidence_path)
    if not path.exists():
        raise HTTPException(404, "evidence package no longer on disk")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/zip",
    )


@router.get("/evidence")
def list_evidence_packages(session: Session = Depends(get_session)) -> list[dict]:
    """Every case with an evidence package built, newest first.

    Backs the Tauri Evidence index page so a user can find packages
    without navigating into individual cases.
    """
    rows = session.exec(
        select(Case)
        .where(Case.evidence_path.is_not(None))
        .order_by(Case.last_audited_at.desc())
    ).all()
    out: list[dict] = []
    for c in rows:
        path = Path(c.evidence_path) if c.evidence_path else None
        on_disk = path.exists() if path else False
        out.append({
            "case_id": c.id,
            "broker_id": c.broker_id,
            "case_status": c.status.value,
            "evidence_path": c.evidence_path,
            "on_disk": on_disk,
            "last_audited_at": c.last_audited_at.isoformat() if c.last_audited_at else None,
        })
    return out
