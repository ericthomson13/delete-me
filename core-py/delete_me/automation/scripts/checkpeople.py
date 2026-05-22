"""Reference Tier-A automation script for checkpeople.com.

Status: **stub**. Implements the framework's contract (`submit`
callable returning `SubmissionResult`) so the dispatcher can be tested
end-to-end, but does not yet drive a real Playwright session. The real
form-fill + success-selector verification is tracked as the follow-up
"per-broker script" issue for checkpeople (see #8).

Why a stub:

- The framework is shippable independently; real Playwright work needs
  hands-on testing against the live form which the framework MVP
  doesn't block.
- In dry-run mode this stub returns `status="submitted"` so CLI smoke
  tests pass without network access.
- In live mode (`dry_run=False`) this stub raises
  `AutomationUnavailable` so production callers get the same
  graceful-degradation path as a real broken script would, until the
  Playwright impl lands.
"""

from __future__ import annotations

from delete_me.automation.base import (
    AutomationUnavailable,
    SubmissionResult,
)
from delete_me.letters.engine import ConsumerProfile


def submit(
    profile: ConsumerProfile,
    *,
    broker_id: str,
    dry_run: bool = False,
) -> SubmissionResult:
    if dry_run:
        return SubmissionResult(
            status="submitted",
            broker_id=broker_id,
            dry_run=True,
            evidence_payload={
                "stub": True,
                "would_submit": {
                    "full_legal_name": profile.full_legal_name,
                    "current_address": profile.current_address,
                },
                "note": (
                    "Reference stub — real Playwright fill + success-selector "
                    "verification pending follow-up issue."
                ),
            },
        )
    raise AutomationUnavailable(
        "checkpeople.py is a reference stub; live submission not yet implemented. "
        "Use the manual fallback (open the browser to /opt-out) until the "
        "Playwright script lands.",
        url="https://www.checkpeople.com/opt-out",
    )
