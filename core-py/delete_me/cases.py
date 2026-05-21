"""Case-lifecycle service used by the CLI and the FastAPI app.

This is the seam between domain (registry + letters + agent form) and storage
(SQLModel). The FastAPI handlers in service/service/api/cases.py call these
functions; the CLI calls the same functions. There is no business logic in
the HTTP layer.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import timedelta

from sqlmodel import Session, select

from delete_me.agent_form import generate_designation
from delete_me.agent_form.generator import AgentDesignation
from delete_me.db import Case, CaseStatus, Profile
from delete_me.db.models import _now
from delete_me.letters import LetterEngine
from delete_me.letters.engine import ConsumerProfile
from delete_me.registry import load_brokers, load_statutes
from delete_me.registry.loader import Broker
from delete_me.transport import (
    DropReceipt,
    DropSubmission,
    DropTransport,
    PostmarkTransport,
    SendResult,
)
from delete_me.transport.base import TransportError
from delete_me.transport.postmark import OutboundLetter


def profile_to_consumer(profile: Profile) -> ConsumerProfile:
    return ConsumerProfile(
        full_legal_name=profile.full_legal_name,
        current_address=profile.current_address,
        email=profile.email,
        phone=profile.phone,
        dob_year=profile.dob_year,
        prior_addresses=tuple(json.loads(profile.prior_addresses_json or "[]")),
        former_names=tuple(json.loads(profile.former_names_json or "[]")),
    )


def upsert_profile(session: Session, consumer: ConsumerProfile) -> Profile:
    existing = session.exec(
        select(Profile).where(Profile.full_legal_name == consumer.full_legal_name)
    ).first()
    if existing:
        existing.current_address = consumer.current_address
        existing.email = consumer.email
        existing.phone = consumer.phone
        existing.dob_year = consumer.dob_year
        existing.prior_addresses_json = json.dumps(list(consumer.prior_addresses))
        existing.former_names_json = json.dumps(list(consumer.former_names))
        existing.updated_at = _now()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    profile = Profile(
        full_legal_name=consumer.full_legal_name,
        current_address=consumer.current_address,
        email=consumer.email,
        phone=consumer.phone,
        dob_year=consumer.dob_year,
        prior_addresses_json=json.dumps(list(consumer.prior_addresses)),
        former_names_json=json.dumps(list(consumer.former_names)),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def draft_case(
    session: Session, profile: Profile, broker_id: str
) -> tuple[Case, AgentDesignation | None]:
    """Generate a letter + (if applicable) agent designation, persist a Case."""
    brokers = {b.id: b for b in load_brokers()}
    if broker_id not in brokers:
        raise ValueError(f"unknown broker_id: {broker_id}")
    broker = brokers[broker_id]
    statutes = load_statutes()
    consumer = profile_to_consumer(profile)
    engine = LetterEngine()
    rendered = engine.render(broker, consumer, statutes)

    designation: AgentDesignation | None = None
    if broker.accepts_authorized_agent and not broker.user_submit_only:
        designation = generate_designation(consumer, [broker_id])

    case = Case(
        profile_id=profile.id,
        broker_id=broker_id,
        status=CaseStatus.DRAFT,
        letter_markdown=rendered.markdown,
        agent_designation_sha256=designation.document_sha256 if designation else None,
        schedule_a_hash=designation.schedule_a_hash if designation else None,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case, designation


def list_cases(session: Session, profile_id: int | None = None) -> list[Case]:
    stmt = select(Case)
    if profile_id is not None:
        stmt = stmt.where(Case.profile_id == profile_id)
    return list(session.exec(stmt))


def send_case(
    session: Session,
    case: Case,
    transport: PostmarkTransport,
    live: bool = False,
) -> SendResult:
    """Send a case's letter via the given transport. Dry-run unless live=True."""
    if case.status not in (CaseStatus.DRAFT, CaseStatus.FAILED):
        raise ValueError(f"case #{case.id} is in status {case.status}, not sendable")

    broker = broker_for_case(case)
    if broker.user_submit_only or not broker.accepts_authorized_agent:
        raise ValueError(
            f"broker {broker.id} is user-submit-only; this case cannot be sent by the tool"
        )
    if not broker.opt_out.email:
        raise ValueError(
            f"broker {broker.id} has no email opt-out channel; Phase 1 only supports email"
        )

    attachments: list[tuple[str, str]] = []
    if case.agent_designation_sha256:
        consumer = profile_to_consumer(session.get(Profile, case.profile_id))
        designation = generate_designation(consumer, [broker.id])
        attachments.append(("authorized_agent_designation.md", designation.markdown))

    letter = OutboundLetter(
        to=str(broker.opt_out.email),
        subject=f"CCPA Deletion + Opt-Out Request — {consumer_name(session, case)}",
        body_markdown=case.letter_markdown,
        attachments=tuple(attachments),
    )

    try:
        result = transport.send(letter, live=live)
    except TransportError as exc:
        case.status = CaseStatus.FAILED
        case.last_error = str(exc)
        session.add(case)
        session.commit()
        raise

    case.status = CaseStatus.SENT_DRY_RUN if result.dry_run else CaseStatus.SENT
    case.sent_at = result.accepted_at
    case.transport_message_id = result.message_id
    case.audit_due_at = result.accepted_at + timedelta(days=60)
    case.last_error = None
    session.add(case)
    session.commit()
    session.refresh(case)
    return result


def submit_via_drop(
    session: Session,
    profile: Profile,
    transport: DropTransport,
    live: bool = False,
) -> tuple[DropReceipt, list[Case]]:
    """Submit a CalPrivacy DROP request covering every drop_registered broker.

    Creates (or refreshes) a Case per broker with status=SENT_VIA_DROP and a
    45-day audit window (the cadence the Delete Act mandates). All cases
    share the same DROP receipt id as transport_message_id so the evidence
    package can trace them back to a single submission.
    """
    drop_brokers = [b for b in load_brokers() if b.opt_out.drop_registered]
    if not drop_brokers:
        raise ValueError("no drop_registered brokers in the registry")

    # Only brokers with a known CalPrivacy ID can be in the payload — DROP
    # routes by that ID, not by broker name. Brokers marked
    # drop_registered=true but missing calprivacy_id are skipped with a log
    # warning; they'll need a maintainer follow-up.
    missing_ids = [b.id for b in drop_brokers if not b.opt_out.calprivacy_id]
    if missing_ids:
        import logging

        logging.getLogger(__name__).warning(
            "drop_registered brokers missing calprivacy_id, skipped: %s",
            missing_ids,
        )
    payload_brokers = [b for b in drop_brokers if b.opt_out.calprivacy_id]
    if not payload_brokers:
        raise ValueError(
            "no drop_registered brokers have a calprivacy_id set — cannot submit"
        )

    consumer = profile_to_consumer(profile)
    submission = DropSubmission(
        full_legal_name=consumer.full_legal_name,
        current_address=consumer.current_address,
        prior_addresses=consumer.prior_addresses,
        dob_year=consumer.dob_year,
        email=consumer.email,
        phone=consumer.phone,
        former_names=consumer.former_names,
        broker_calprivacy_ids=tuple(b.opt_out.calprivacy_id for b in payload_brokers),
    )

    try:
        receipt = transport.submit(submission, live=live)
    except TransportError:
        # Don't persist any case state on transport failure — the next
        # attempt should be idempotent. The error bubbles up to the caller.
        raise

    cases: list[Case] = []
    audit_due = receipt.accepted_at + timedelta(days=45)
    engine = LetterEngine()
    statutes = load_statutes()
    for broker in payload_brokers:
        existing = session.exec(
            select(Case).where(
                Case.profile_id == profile.id, Case.broker_id == broker.id
            )
        ).first()
        if existing is None:
            rendered = engine.render(broker, consumer, statutes)
            existing = Case(
                profile_id=profile.id,
                broker_id=broker.id,
                letter_markdown=rendered.markdown,
            )
        existing.status = CaseStatus.SENT_VIA_DROP
        existing.sent_at = receipt.accepted_at
        existing.audit_due_at = audit_due
        existing.transport_message_id = receipt.receipt_id
        existing.last_error = None
        session.add(existing)
        cases.append(existing)

    session.commit()
    for c in cases:
        session.refresh(c)
    return receipt, cases


def broker_for_case(case: Case) -> Broker:
    brokers = {b.id: b for b in load_brokers()}
    if case.broker_id not in brokers:
        raise ValueError(f"case references unknown broker {case.broker_id!r}")
    return brokers[case.broker_id]


def consumer_name(session: Session, case: Case) -> str:
    p = session.get(Profile, case.profile_id)
    return p.full_legal_name if p else "unknown"


def case_as_dict(case: Case) -> dict:
    return {
        "id": case.id,
        "profile_id": case.profile_id,
        "broker_id": case.broker_id,
        "status": case.status.value,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "sent_at": case.sent_at.isoformat() if case.sent_at else None,
        "audit_due_at": case.audit_due_at.isoformat() if case.audit_due_at else None,
        "transport_message_id": case.transport_message_id,
        "agent_designation_sha256": case.agent_designation_sha256,
        "last_error": case.last_error,
    }


def consumer_to_dict(consumer: ConsumerProfile) -> dict:
    d = asdict(consumer)
    d["prior_addresses"] = list(d.get("prior_addresses") or ())
    d["former_names"] = list(d.get("former_names") or ())
    return d


def brokers_summary() -> Iterable[dict]:
    for b in load_brokers():
        yield {
            "id": b.id,
            "name": b.name,
            "tier": b.tier,
            "accepts_authorized_agent": b.accepts_authorized_agent,
            "user_submit_only": b.user_submit_only,
            "methods": list(b.opt_out.methods),
            "drop_registered": b.opt_out.drop_registered,
        }
