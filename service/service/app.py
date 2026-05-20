"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os

from delete_me import __version__
from delete_me.db.session import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import audits, brokers, cases, evidence, health, profiles


def create_app() -> FastAPI:
    logging.basicConfig(level=os.environ.get("DELETE_ME_LOG_LEVEL", "INFO").upper())
    init_db()

    app = FastAPI(
        title="delete-me",
        version=__version__,
        description=(
            "Open-source CCPA / state-DSAR / GDPR deletion-letter service. "
            "Phase 1: profiles, cases, dry-run send. See docs/architecture/PLAN.md."
        ),
    )

    # Tauri front-end + local dev only. Tighten in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get(
            "DELETE_ME_CORS_ORIGINS", "tauri://localhost,http://localhost:5173"
        ).split(","),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(brokers.router)
    app.include_router(profiles.router)
    app.include_router(cases.router)
    app.include_router(audits.router)
    app.include_router(evidence.router)
    return app


app = create_app()
