"""Adapter base for breach-corpus lookups.

Adapters take a single email address and return a list of exposures. They
never accept passwords, never store responses on disk, and never call any
endpoint that requires the user's plaintext credentials.

When an adapter's credentials are missing or invalid, it raises
BreachAdapterUnavailable rather than returning empty — the CLI distinguishes
"no breaches found" from "couldn't ask".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime


class BreachAdapterUnavailable(RuntimeError):
    """Adapter cannot run (missing key, revoked credentials, etc.)."""


@dataclass(frozen=True)
class BreachExposureResult:
    source: str
    email: str
    breach_name: str
    breach_date: str | None
    data_classes: tuple[str, ...]
    description_excerpt: str | None
    checked_at: datetime


class BreachAdapter(ABC):
    source_id: str = ""

    @abstractmethod
    def check(self, email: str) -> list[BreachExposureResult]: ...

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
