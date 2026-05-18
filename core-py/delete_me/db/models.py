"""SQLModel ORM for delete-me's case tracker.

One Profile per consumer (Tauri/CLI: usually one; docker self-host: one per
account). One Case per (profile, broker) deletion attempt. Cases keep the
generated letter text and the agent-designation hash for evidence.

Phase 1 stores Profile.pii_json as plain text in SQLite — fine for the
local-first Tauri use case. Phase 1.5 will add argon2id-encrypted columns
behind a feature flag for the docker deployment, where the operator is
trusted but not necessarily the disk.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class CaseStatus(enum.StrEnum):
    DRAFT = "draft"
    SENT_DRY_RUN = "sent_dry_run"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    DELETED_CONFIRMED = "deleted_confirmed"
    AUDIT_INCONCLUSIVE = "audit_inconclusive"
    NONCOMPLIANT = "noncompliant"
    FAILED = "failed"


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: int | None = Field(default=None, primary_key=True)
    full_legal_name: str
    current_address: str
    email: str | None = None
    phone: str | None = None
    dob_year: int | None = None
    prior_addresses_json: str = "[]"
    former_names_json: str = "[]"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Case(SQLModel, table=True):
    __tablename__ = "cases"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profiles.id", index=True)
    broker_id: str = Field(index=True)
    status: CaseStatus = Field(default=CaseStatus.DRAFT, index=True)

    letter_markdown: str
    agent_designation_sha256: str | None = None
    schedule_a_hash: str | None = None

    created_at: datetime = Field(default_factory=_now)
    sent_at: datetime | None = None
    response_received_at: datetime | None = None
    audit_due_at: datetime | None = Field(default=None, index=True)

    transport_message_id: str | None = None
    last_error: str | None = None
    evidence_path: str | None = None
