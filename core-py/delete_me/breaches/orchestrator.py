"""Breach-check orchestrator.

Given a profile and one or more emails, runs every available BreachAdapter
and persists BreachExposure rows, deduped on (profile_id, source, breach_name)
across re-runs.

Each provider is independently optional. The CLI calls
discover_registry() once at startup to learn which providers are configured
and which are missing (with a one-line setup hint per missing provider).
A provider that authenticates fine at startup but fails mid-run (revoked
key, out of credits, etc.) is skipped for that email without aborting the
rest of the run.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlmodel import Session, select

from delete_me.db import BreachExposure, Profile

from .base import BreachAdapter, BreachAdapterUnavailable

LOG = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ProviderStatus:
    source_id: str
    available: bool
    detail: str  # human-readable: setup hint when unavailable, "ready" when ok


@dataclass
class BreachOrchestrator:
    adapters: list[BreachAdapter] = field(default_factory=list)
    runtime_disabled: list[ProviderStatus] = field(default_factory=list)

    @classmethod
    def from_registry(cls, adapters: list[BreachAdapter]) -> BreachOrchestrator:
        return cls(adapters=list(adapters))

    def check_email(
        self,
        session: Session,
        profile: Profile,
        email: str,
    ) -> list[BreachExposure]:
        """Run every available adapter; upsert results.

        If a provider raises BreachAdapterUnavailable mid-run (e.g., 401 or
        out-of-credits), it's removed from the active set and recorded in
        runtime_disabled so the CLI can show the user what happened — but
        the other providers still get a chance to return results.
        """
        if not self.adapters:
            return []

        out: list[BreachExposure] = []
        still_active: list[BreachAdapter] = []
        for adapter in self.adapters:
            try:
                results = adapter.check(email)
            except BreachAdapterUnavailable as exc:
                LOG.warning("%s disabled mid-run: %s", adapter.source_id, exc)
                self.runtime_disabled.append(
                    ProviderStatus(source_id=adapter.source_id, available=False, detail=str(exc))
                )
                continue
            still_active.append(adapter)
            for r in results:
                out.append(_upsert(session, profile_id=profile.id, result=r))
        self.adapters = still_active
        return out


def discover_registry() -> tuple[list[BreachAdapter], list[ProviderStatus]]:
    """Try to construct every supported provider.

    Returns the live adapters plus a status row per provider (available or
    not, with a setup-hint string for the ones that aren't). The CLI uses
    the status list to either run the available providers or, if none are
    available, show all the setup hints at once so the user knows every
    way to make breach-check work.
    """
    adapters: list[BreachAdapter] = []
    statuses: list[ProviderStatus] = []
    for source_id, factory in _PROVIDER_FACTORIES:
        try:
            adapter = factory()
        except BreachAdapterUnavailable as exc:
            statuses.append(ProviderStatus(source_id=source_id, available=False, detail=str(exc)))
            continue
        adapters.append(adapter)
        statuses.append(ProviderStatus(source_id=source_id, available=True, detail="ready"))
    return adapters, statuses


def default_registry() -> list[BreachAdapter]:
    """Backwards-compatible accessor returning only the live adapters."""
    adapters, _ = discover_registry()
    return adapters


def _hibp_factory() -> BreachAdapter:
    from .hibp import HIBPAdapter
    return HIBPAdapter()


def _intelx_factory() -> BreachAdapter:
    from .intelx import IntelXAdapter
    return IntelXAdapter()


def _dehashed_factory() -> BreachAdapter:
    from .dehashed import DeHashedAdapter
    return DeHashedAdapter()


_PROVIDER_FACTORIES: list[tuple[str, callable]] = [
    ("hibp", _hibp_factory),
    ("intelx", _intelx_factory),
    ("dehashed", _dehashed_factory),
]


def _upsert(session: Session, *, profile_id: int, result) -> BreachExposure:
    existing = session.exec(
        select(BreachExposure).where(
            BreachExposure.profile_id == profile_id,
            BreachExposure.source == result.source,
            BreachExposure.breach_name == result.breach_name,
        )
    ).first()
    if existing is not None:
        existing.email = result.email
        existing.breach_date = result.breach_date
        existing.data_classes_json = json.dumps(list(result.data_classes))
        existing.description_excerpt = result.description_excerpt
        existing.checked_at = result.checked_at or _now()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    row = BreachExposure(
        profile_id=profile_id,
        email=result.email,
        source=result.source,
        breach_name=result.breach_name,
        breach_date=result.breach_date,
        data_classes_json=json.dumps(list(result.data_classes)),
        description_excerpt=result.description_excerpt,
        checked_at=result.checked_at or _now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
