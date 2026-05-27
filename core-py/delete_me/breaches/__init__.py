"""Breach-exposure subsystem.

Discovery feature parallel to the broker-listings audit: given a profile's
email address(es), query breach-corpus providers (HIBP today) and surface
which breaches the address appears in. Separate adapter shape and DB table
from AuditAdapter — a breach is a property of an email, not a broker.
"""

from .base import BreachAdapter, BreachAdapterUnavailable, BreachExposureResult
from .orchestrator import BreachOrchestrator, ProviderStatus, default_registry, discover_registry

__all__ = [
    "BreachAdapter",
    "BreachAdapterUnavailable",
    "BreachExposureResult",
    "BreachOrchestrator",
    "ProviderStatus",
    "default_registry",
    "discover_registry",
]
