"""Load and validate broker registry YAML files against the JSON schema.

Two-stage validation:

1. JSON Schema validates structural correctness — required keys, enum values,
   patterns. This is what CI runs on every PR to gate broker additions.
2. Pydantic models give typed Python access plus cross-file invariants (every
   statute slug referenced by a broker must exist in statute_citations.yaml).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import jsonschema
import yaml
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from delete_me.paths import brokers_dir, legal_dir, schemas_dir

OptOutMethod = Literal["email", "web_form", "postal", "drop", "phone"]
PIIField = Literal[
    "full_name",
    "current_address",
    "prior_addresses",
    "dob_year",
    "dob_full",
    "email",
    "phone",
    "ssn_last_4",
    "former_names",
]
AgentRequirement = Literal[
    "signed_permission",
    "government_id_redacted",
    "notarized",
    "postal_only",
    "company_letterhead",
]
Tier = Literal["enterprise_aggregator", "people_search", "long_tail"]


class OptOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    methods: list[OptOutMethod]
    email: EmailStr | None = None
    web_form: HttpUrl | None = None
    postal: str | None = None
    phone: str | None = None
    drop_registered: bool | None = None
    calprivacy_id: str | None = None
    instructions_url: HttpUrl | None = None


AutomationTier = Literal["auto", "semi", "manual"]


class Automation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: AutomationTier
    script: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]*\.py$")
    last_automation_pass: date | None = None


class Broker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    website: HttpUrl | None = None
    parent_company: str | None = None
    tier: Tier | None = None
    opt_out: OptOut
    accepts_authorized_agent: bool
    agent_form_requirements: list[AgentRequirement] = Field(default_factory=list)
    required_pii: list[PIIField]
    optional_pii: list[PIIField] = Field(default_factory=list)
    re_aggregation_days: int | None = None
    audit_sources: list[str] = Field(default_factory=list)
    statutes: list[str]
    letter_template: str | None = None
    user_submit_only: bool = False
    last_verified: date
    maintainer: str = Field(pattern=r"^@[A-Za-z0-9-]+$")
    notes: str | None = None
    automation: Automation | None = None


class Statute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jurisdiction: str
    short_name: str
    citation: str
    right_description: str
    penalty: str | None = None
    private_right_of_action: bool | None = None
    url: HttpUrl | None = None


def _broker_schema() -> dict:
    with (schemas_dir() / "broker.schema.json").open() as f:
        return json.load(f)


def _normalize_for_schema(value: Any) -> Any:
    """Convert YAML-native dates/datetimes to ISO strings for jsonschema validation.

    YAML's safe_load parses ISO date scalars into datetime.date objects. The
    JSON Schema validator expects strings with format=date. Normalizing here
    means contributors don't have to remember to quote dates in their YAML.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize_for_schema(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_schema(v) for v in value]
    return value


def validate_broker_file(path: Path) -> Broker:
    """Validate one broker YAML against the JSON Schema and return a typed Broker.

    Raises jsonschema.ValidationError for schema violations and
    pydantic.ValidationError for type violations.
    """
    with path.open() as f:
        raw = yaml.safe_load(f)

    jsonschema.validate(instance=_normalize_for_schema(raw), schema=_broker_schema())
    broker = Broker.model_validate(raw)

    if broker.id != path.stem:
        raise ValueError(
            f"broker.id ({broker.id!r}) must match filename stem ({path.stem!r}) in {path}"
        )
    return broker


def load_broker(broker_id: str) -> Broker:
    path = brokers_dir() / f"{broker_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No broker named {broker_id!r} in {brokers_dir()}")
    return validate_broker_file(path)


def load_brokers() -> list[Broker]:
    """Load every broker in registry/brokers/, sorted by id."""
    results = []
    for path in sorted(brokers_dir().glob("*.yaml")):
        results.append(validate_broker_file(path))
    return results


def load_statutes() -> dict[str, Statute]:
    """Load legal/statute_citations.yaml into a map keyed by slug."""
    path = legal_dir() / "statute_citations.yaml"
    with path.open() as f:
        raw = yaml.safe_load(f)
    return {slug: Statute.model_validate(body) for slug, body in raw.items()}


def cross_check(brokers: list[Broker], statutes: dict[str, Statute]) -> list[str]:
    """Return list of human-readable errors found across the registry."""
    errors: list[str] = []
    for b in brokers:
        for s in b.statutes:
            if s not in statutes:
                errors.append(f"{b.id}: references unknown statute {s!r}")
        for src in b.audit_sources:
            if not src.replace("_", "").isalnum():
                errors.append(f"{b.id}: audit_source {src!r} has invalid characters")
    return errors
