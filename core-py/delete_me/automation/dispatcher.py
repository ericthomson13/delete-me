"""Dispatches a submission to the right tier for a broker.

Dispatch rules:

- broker has no `automation` block, OR `automation.tier == "manual"`:
  return needs_human pointing at the broker's web_form / instructions_url.
  The UI surfaces the URL and (Phase-7+) copies prefilled values to the
  user's clipboard.

- `automation.tier in ("auto", "semi")` but `automation.script` is missing
  or fails to import: return needs_human with a clear fallback_reason so
  the user isn't blocked, and the CI health-check has a signal to open
  a "script missing/broken" issue.

- `automation.tier in ("auto", "semi")` with a loadable script: invoke
  `script.submit(profile, broker_id=..., dry_run=...)`. The script's
  return value is returned as-is. If the script raises
  `AutomationUnavailable`, convert to needs_human.

The dispatcher never raises for the "no automation configured" case —
that is the expected path for the majority of brokers in our registry
today, not an error.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import cast

from delete_me.letters.engine import ConsumerProfile
from delete_me.registry import load_brokers

from .base import AutomationUnavailable, SubmissionResult, Submitter


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent / "scripts"


def load_script(filename: str) -> Submitter:
    """Import `automation/scripts/<filename>` and return its `submit` callable.

    Raises:
        FileNotFoundError: if `<filename>` doesn't exist in scripts/.
        AttributeError: if the loaded module has no `submit` callable.
        ImportError: if the script itself fails to import (e.g., missing
            Playwright when the script needs it).
    """
    path = _scripts_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(f"automation script not found: scripts/{filename}")

    # Use the package-relative import path so the script can do
    # `from delete_me.automation.base import SubmissionResult` etc.
    module_name = f"delete_me.automation.scripts.{path.stem}"
    module = importlib.import_module(module_name)

    submit = getattr(module, "submit", None)
    if submit is None or not callable(submit):
        raise AttributeError(
            f"scripts/{filename} must expose a top-level callable named `submit`"
        )
    return cast(Submitter, submit)


def dispatch(
    broker_id: str,
    profile: ConsumerProfile,
    *,
    dry_run: bool = False,
) -> SubmissionResult:
    """Dispatch a submission for `broker_id`. See module docstring."""
    brokers = {b.id: b for b in load_brokers()}
    broker = brokers.get(broker_id)
    if broker is None:
        raise ValueError(f"unknown broker_id: {broker_id}")

    automation = broker.automation
    fallback_url = (
        str(broker.opt_out.web_form)
        if broker.opt_out.web_form
        else (str(broker.opt_out.instructions_url) if broker.opt_out.instructions_url else None)
    )

    # Case A: no automation block → manual (Tier C).
    if automation is None or automation.tier == "manual":
        return SubmissionResult(
            status="needs_human",
            broker_id=broker_id,
            dry_run=dry_run,
            evidence_payload={"url": fallback_url} if fallback_url else {},
            fallback_reason="tier C (manual) — app opens the broker's web form for the user",
        )

    # Case B: auto/semi declared but missing script — degrade gracefully.
    if not automation.script:
        return SubmissionResult(
            status="needs_human",
            broker_id=broker_id,
            dry_run=dry_run,
            evidence_payload={"url": fallback_url} if fallback_url else {},
            fallback_reason=(
                f"tier {automation.tier!r} declared but no automation.script "
                "set in the YAML — falling back to manual"
            ),
        )

    # Case C: auto/semi with a script — load and run.
    try:
        submit = load_script(automation.script)
    except (FileNotFoundError, AttributeError, ImportError) as exc:
        return SubmissionResult(
            status="needs_human",
            broker_id=broker_id,
            dry_run=dry_run,
            evidence_payload={"url": fallback_url} if fallback_url else {},
            fallback_reason=f"automation script failed to load: {exc}",
        )

    try:
        return submit(profile, broker_id=broker_id, dry_run=dry_run)
    except AutomationUnavailable as exc:
        return SubmissionResult(
            status="needs_human",
            broker_id=broker_id,
            dry_run=dry_run,
            evidence_payload={"url": exc.url or fallback_url} if (exc.url or fallback_url) else {},
            fallback_reason=exc.reason,
        )
