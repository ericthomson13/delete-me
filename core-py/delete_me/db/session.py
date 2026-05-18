"""Engine + session helpers shared by the CLI and the FastAPI service.

The default URL is a SQLite file under platformdirs' user-data-dir, so the
CLI works offline and a developer doesn't need a Postgres install just to
exercise Phase 1. The docker service overrides DELETE_ME_DB_URL to point at
Postgres.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from platformdirs import user_data_path
from sqlmodel import Session, SQLModel, create_engine

ENV_DB_URL = "DELETE_ME_DB_URL"


def default_db_url() -> str:
    """Return the URL used when DELETE_ME_DB_URL is not set."""
    if env := os.environ.get(ENV_DB_URL):
        return env
    data_dir: Path = user_data_path("delete-me", appauthor=False)
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'delete-me.sqlite3'}"


def engine_from_url(url: str | None = None):
    resolved = url or default_db_url()
    connect_args = {"check_same_thread": False} if resolved.startswith("sqlite") else {}
    return create_engine(resolved, connect_args=connect_args)


def init_db(url: str | None = None) -> None:
    """Create tables if they don't exist. Idempotent."""
    from delete_me.db import models  # noqa: F401  ensure models import before create_all

    engine = engine_from_url(url)
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(url: str | None = None) -> Iterator[Session]:
    engine = engine_from_url(url)
    with Session(engine) as session:
        yield session
