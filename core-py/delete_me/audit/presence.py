"""Presence-check orchestrator — pre-send variant of the audit pipeline.

Reuses the AuditAdapter contract verbatim. The difference vs. AuditOrchestrator
is *when* it runs (before a case exists, to decide whether to bother sending)
and *where* results land (keyed on profile + broker, not on case).

A broker's audit_sources list drives which adapters get called. Brokers
without audit_sources are skipped with an "inconclusive: no source" row so
the caller can distinguish "not listed" from "couldn't check".

Results are cached: a PresenceResult newer than fresh_days for the same
(profile, broker, source) triple is reused instead of re-hitting the source.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from delete_me.cases import profile_to_consumer
from delete_me.db import PresenceResult, Profile
from delete_me.registry import load_brokers
from delete_me.registry.loader import Broker

from .orchestrator import _split_city_state
from .sources.base import AuditAdapter, AuditQuery, ListingResult

LOG = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class PresenceOrchestrator:
    adapters: dict[str, AuditAdapter] = field(default_factory=dict)

    @classmethod
    def from_registry(cls, registry: dict[str, AuditAdapter]) -> PresenceOrchestrator:
        return cls(adapters=dict(registry))

    def check_profile(
        self,
        session: Session,
        profile: Profile,
        brokers: list[Broker] | None = None,
        fresh_days: int = 7,
    ) -> list[PresenceResult]:
        """Check presence for every broker (or the supplied subset).

        Brokers with no audit_sources get a single "no source configured"
        inconclusive row so the caller can show a coverage-gap footer.
        """
        if brokers is None:
            brokers = load_brokers()

        consumer = profile_to_consumer(profile)
        city, state = _split_city_state(consumer.current_address)
        query = AuditQuery(
            full_name=consumer.full_legal_name,
            current_city=city,
            current_state=state,
            dob_year=consumer.dob_year,
        )
        fresh_cutoff = _now() - timedelta(days=fresh_days)

        results: list[PresenceResult] = []
        for broker in brokers:
            if not broker.audit_sources:
                results.append(
                    _persist(
                        session,
                        profile_id=profile.id,
                        broker_id=broker.id,
                        listing=ListingResult(
                            source="(none)",
                            found=False,
                            inconclusive=True,
                            notes="broker has no audit_sources configured",
                            checked_at=_now(),
                        ),
                    )
                )
                continue

            for source_id in broker.audit_sources:
                cached = _latest_fresh(
                    session, profile.id, broker.id, source_id, fresh_cutoff
                )
                if cached is not None:
                    results.append(cached)
                    continue

                adapter = self.adapters.get(source_id)
                if adapter is None:
                    LOG.warning(
                        "presence: no adapter registered for source %s (broker %s)",
                        source_id,
                        broker.id,
                    )
                    results.append(
                        _persist(
                            session,
                            profile_id=profile.id,
                            broker_id=broker.id,
                            listing=ListingResult(
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
                    LOG.exception("presence: adapter %s raised", source_id)
                    listing = ListingResult(
                        source=source_id,
                        found=False,
                        inconclusive=True,
                        notes=f"adapter exception: {exc}",
                        checked_at=_now(),
                    )
                results.append(
                    _persist(
                        session,
                        profile_id=profile.id,
                        broker_id=broker.id,
                        listing=listing,
                    )
                )

        return results


def found_broker_ids(session: Session, profile_id: int) -> list[str]:
    """Return broker_ids where the most recent PresenceResult for at least one
    source has found=True. Used by `cases-from-presence` to decide which
    brokers to draft letters for.

    A broker is considered "found" if its newest row per source has found=True.
    A stale True followed by a fresh False (the user was removed since) does
    NOT count — the freshest row per (broker, source) wins.
    """
    rows = list(
        session.exec(
            select(PresenceResult)
            .where(PresenceResult.profile_id == profile_id)
            .order_by(PresenceResult.checked_at.desc())
        )
    )
    # Reduce to latest row per (broker, source); newest first means first-seen
    # is the winner.
    latest: dict[tuple[str, str], PresenceResult] = {}
    for r in rows:
        latest.setdefault((r.broker_id, r.source), r)

    found_set: set[str] = set()
    for (broker_id, _), row in latest.items():
        if row.found:
            found_set.add(broker_id)
    return sorted(found_set)


def latest_for_broker(
    session: Session, profile_id: int, broker_id: str
) -> list[PresenceResult]:
    """Return the most recent PresenceResult per source for one broker."""
    stmt = (
        select(PresenceResult)
        .where(PresenceResult.profile_id == profile_id, PresenceResult.broker_id == broker_id)
        .order_by(PresenceResult.checked_at.desc())
    )
    seen: dict[str, PresenceResult] = {}
    for row in session.exec(stmt):
        if row.source not in seen:
            seen[row.source] = row
    return list(seen.values())


def _latest_fresh(
    session: Session,
    profile_id: int,
    broker_id: str,
    source: str,
    cutoff: datetime,
) -> PresenceResult | None:
    stmt = (
        select(PresenceResult)
        .where(
            PresenceResult.profile_id == profile_id,
            PresenceResult.broker_id == broker_id,
            PresenceResult.source == source,
            PresenceResult.checked_at >= cutoff,
        )
        .order_by(PresenceResult.checked_at.desc())
        .limit(1)
    )
    return session.exec(stmt).first()


def _persist(
    session: Session,
    *,
    profile_id: int,
    broker_id: str,
    listing: ListingResult,
) -> PresenceResult:
    row = PresenceResult(
        profile_id=profile_id,
        broker_id=broker_id,
        source=listing.source,
        checked_at=listing.checked_at or _now(),
        found=listing.found,
        inconclusive=listing.inconclusive,
        listings_url=listing.listings_url,
        notes=listing.notes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
