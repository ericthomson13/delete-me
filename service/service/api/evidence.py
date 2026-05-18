from __future__ import annotations

import os
from pathlib import Path

from delete_me.db import Case
from delete_me.evidence import PackageBuilder
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from ._deps import get_session

router = APIRouter(prefix="/cases", tags=["evidence"])

_DEFAULT_OUT = Path(
    os.environ.get("DELETE_ME_EVIDENCE_DIR", "/var/lib/delete-me/evidence")
)


@router.post("/{case_id}/evidence")
def build_evidence(case_id: int, session: Session = Depends(get_session)) -> dict:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(404, f"case {case_id} not found")
    _DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    builder = PackageBuilder(out_dir=_DEFAULT_OUT)
    pkg = builder.build(session, case)
    return {
        "case_id": pkg.case_id,
        "directory": str(pkg.directory),
        "zip": str(pkg.zip_path),
        "manifest": str(pkg.manifest_path),
        "file_count": len(pkg.files),
    }


@router.get("/{case_id}/evidence/download")
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
