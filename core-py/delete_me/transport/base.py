"""Transport base types — kept tiny so adding SMTP or AWS SES later is easy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class TransportError(RuntimeError):
    """Raised when a transport fails to send (network error, auth, etc.)."""


@dataclass(frozen=True)
class SendResult:
    dry_run: bool
    accepted_at: datetime
    message_id: str | None
    to: str
    subject: str
