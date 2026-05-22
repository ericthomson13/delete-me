"""Interfaces for the submission-automation framework.

Each per-broker script in `automation/scripts/` exports a `submit` callable
(or a class implementing `Submitter`) that the dispatcher invokes. The
return value is always a `SubmissionResult`.

Scripts that need Playwright import it themselves — Playwright is in the
`audit` optional dep, not the base install, so the framework's import path
must stay Playwright-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from delete_me.letters.engine import ConsumerProfile

SubmissionStatus = Literal["submitted", "needs_human", "failed"]


@dataclass(frozen=True)
class SubmissionResult:
    """Return value from any automation script.

    - `status="submitted"`: the script filled and submitted the form
      (or completed its dry-run equivalent). `screenshot_path` should
      point at success-page evidence when not in dry_run.
    - `status="needs_human"`: the broker's form is gated (captcha,
      login, agreement, region selector) and the dispatcher should
      surface `evidence_payload["url"]` to the UI so the user can
      finish in their browser.
    - `status="failed"`: the script ran but the form's success
      selector didn't resolve — likely the form changed.
      `fallback_reason` carries diagnostic detail; the CI health-check
      uses this to open a "script broken" issue.
    """

    status: SubmissionStatus
    broker_id: str
    dry_run: bool
    screenshot_path: Path | None = None
    evidence_payload: dict = field(default_factory=dict)
    fallback_reason: str | None = None


class AutomationUnavailable(Exception):
    """Raised by a script when it can't proceed unattended.

    The dispatcher catches this and converts it to a `SubmissionResult`
    with `status="needs_human"` so calling code never has to branch on
    exception vs return value. Scripts raise this (instead of returning
    needs_human directly) when the unavailability is detected DURING
    execution — e.g., the form returned a captcha challenge that wasn't
    present at registration time.
    """

    def __init__(self, reason: str, *, url: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.url = url


class Submitter(Protocol):
    """Interface every script in `automation/scripts/` must satisfy.

    Implementations can be a module-level `submit` function or any
    callable object. The dispatcher loads the script module and looks
    for a top-level `submit` callable matching this signature.
    """

    def __call__(
        self,
        profile: ConsumerProfile,
        *,
        broker_id: str,
        dry_run: bool = False,
    ) -> SubmissionResult: ...
