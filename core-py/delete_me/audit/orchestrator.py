"""Audit orchestrator.

Given a Case, look up the broker's audit_sources, run each registered
adapter, persist AuditResult rows, and transition the Case status:

  - any source returned found=True  -> NONCOMPLIANT
  - all sources returned found=False AND none inconclusive
                                    -> DELETED_CONFIRMED
  - otherwise                        -> AUDIT_INCONCLUSIVE

Adapters are loaded lazily — the heavy ones (Playwright in future phases)
shouldn't import at module load.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlmodel import Session, select

from delete_me.cases import broker_for_case, profile_to_consumer
from delete_me.db import AuditResult, Case, CaseStatus, Profile

from .sources.base import AuditAdapter, AuditQuery, ListingResult
from .sources.mock import MockAuditAdapter

LOG = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class AuditOrchestrator:
    adapters: dict[str, AuditAdapter] = field(default_factory=dict)

    @classmethod
    def from_registry(cls, registry: dict[str, AuditAdapter]) -> AuditOrchestrator:
        return cls(adapters=dict(registry))

    def audit_case(self, session: Session, case: Case) -> list[AuditResult]:
        """Run every registered adapter named in the broker's audit_sources."""
        broker = broker_for_case(case)
        results: list[AuditResult] = []

        consumer_profile = session.get(Profile, case.profile_id)
        consumer = profile_to_consumer(consumer_profile) if consumer_profile else None
        if consumer is None:
            raise ValueError(f"case {case.id} has no profile")

        city, state = _split_city_state(consumer.current_address)
        query = AuditQuery(
            full_name=consumer.full_legal_name,
            current_city=city,
            current_state=state,
            dob_year=consumer.dob_year,
        )

        if not broker.audit_sources:
            LOG.info(
                "audit: broker %s has no audit_sources; marking inconclusive", broker.id
            )
            result = AuditResult(
                case_id=case.id,
                source="(none)",
                checked_at=_now(),
                found=False,
                inconclusive=True,
                notes="broker has no audit_sources configured",
            )
            session.add(result)
            results.append(result)
        else:
            for source_id in broker.audit_sources:
                adapter = self.adapters.get(source_id)
                if adapter is None:
                    LOG.warning(
                        "audit: no adapter registered for source %s (broker %s)",
                        source_id,
                        broker.id,
                    )
                    results.append(
                        _persist(
                            session,
                            case,
                            ListingResult(
                                source=source_id,
                                found=False,
                                inconclusive=True,
                                notes="no adapter registered",
                                checked_at=_now(),
                            ),
                        )
                    )
                    continue

                try:
                    listing = adapter.search(query)
                except Exception as exc:  # noqa: BLE001 — never let an adapter break the sweep
                    LOG.exception("audit: adapter %s raised", source_id)
                    listing = ListingResult(
                        source=source_id,
                        found=False,
                        inconclusive=True,
                        notes=f"adapter exception: {exc}",
                        checked_at=_now(),
                    )
                results.append(_persist(session, case, listing))

        case.status = _decide_status(results)
        case.last_audited_at = _now()
        session.add(case)
        session.commit()
        for r in results:
            session.refresh(r)
        session.refresh(case)
        return results

    def cases_due(self, session: Session, limit: int | None = None) -> list[Case]:
        """Return cases whose audit_due_at has passed and are still in a sendable stage."""
        now = _now()
        stmt = select(Case).where(
            Case.audit_due_at.is_not(None),
            Case.audit_due_at <= now,
            Case.status.in_(
                [CaseStatus.SENT, CaseStatus.SENT_DRY_RUN, CaseStatus.AUDIT_INCONCLUSIVE]
            ),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(session.exec(stmt))


def _persist(session: Session, case: Case, listing: ListingResult) -> AuditResult:
    row = AuditResult(
        case_id=case.id,
        source=listing.source,
        checked_at=listing.checked_at or _now(),
        found=listing.found,
        inconclusive=listing.inconclusive,
        listings_url=listing.listings_url,
        evidence_html_path=listing.evidence_html_path,
        screenshot_path=listing.screenshot_path,
        notes=listing.notes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _decide_status(results: list[AuditResult]) -> CaseStatus:
    if any(r.found for r in results):
        return CaseStatus.NONCOMPLIANT
    if all(not r.inconclusive for r in results):
        return CaseStatus.DELETED_CONFIRMED
    return CaseStatus.AUDIT_INCONCLUSIVE


def _split_city_state(address: str | None) -> tuple[str | None, str | None]:
    """Best-effort split of 'Street, City, ST ZIP' or 'City, ST'. Conservative.

    Returns (city, state) — both None if we can't parse.
    """
    if not address:
        return None, None
    parts = [p.strip() for p in address.split(",")]
    if len(parts) < 2:
        return None, None
    city = parts[-2]
    last = parts[-1].split()
    state = last[0] if last else None
    return city or None, state


def default_registry() -> dict[str, AuditAdapter]:
    """Mock-only registry, suitable for tests and offline demos.

    Real adapter wiring happens in delete_me.audit.production_registry().
    """
    return {"mock": MockAuditAdapter(source_id="mock")}


def production_registry() -> dict[str, AuditAdapter]:
    """Wire the real (experimental) adapters. Imported lazily for httpx cost."""
    from .sources.truepeoplesearch import TruePeopleSearchAdapter

    return {
        "truepeoplesearch_search": TruePeopleSearchAdapter(),
        # Future adapters land here, gated on Phase 2.x readiness.
    }
