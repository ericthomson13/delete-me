"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from delete_me.db.session import engine_from_url
from sqlmodel import Session


def get_session() -> Iterator[Session]:
    engine = engine_from_url()
    with Session(engine) as session:
        yield session
