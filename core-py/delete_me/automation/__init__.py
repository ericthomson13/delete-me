"""Tiered submission-automation framework (see issue #8).

Tier A (`auto`):   headless Playwright fills + submits the form
Tier B (`semi`):   Playwright preps, waits at a gate, user clears, resumes
Tier C (`manual`): no automation; app opens the broker's web form in the
                   user's browser with prefilled values on the clipboard

Always-on parallel: the CCPA authorized-agent letter ships regardless of
which tier handled the form. Form submission is the convenience layer; the
letter is the legal teeth.

Public surface:
- `dispatch(broker_id, profile, *, dry_run=False)` -> SubmissionResult
- `AutomationUnavailable` — raised when a script can't proceed unattended
- `SubmissionResult`, `SubmissionStatus` — return shape from any script
"""

from .base import (
    AutomationUnavailable,
    Submitter,
    SubmissionResult,
    SubmissionStatus,
)
from .dispatcher import dispatch, load_script

__all__ = [
    "AutomationUnavailable",
    "SubmissionResult",
    "SubmissionStatus",
    "Submitter",
    "dispatch",
    "load_script",
]
