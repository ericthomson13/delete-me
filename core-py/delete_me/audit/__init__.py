"""Audit pipeline package.

Phase 0 only ships the adapter base class so the registry can validate
audit_sources references. Concrete adapters land in Phase 2.
"""

from .sources.base import AuditAdapter, ListingResult

__all__ = ["AuditAdapter", "ListingResult"]
