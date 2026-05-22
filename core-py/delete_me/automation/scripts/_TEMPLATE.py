"""Template for a per-broker submission script.

Copy this file to `<broker_id>.py`, fill in the marked sections, and add
an `automation:` block to the broker's YAML pointing at your new file.
See `docs/ADDING_AN_AUTOMATION_SCRIPT.md` for the contributor walkthrough.

The file name MUST match `[a-z][a-z0-9_]*\\.py` (validated by the schema).
"""

from __future__ import annotations

from delete_me.automation.base import (
    AutomationUnavailable,
    SubmissionResult,
)
from delete_me.letters.engine import ConsumerProfile

# --- 1. Broker-specific constants. Edit these. ----------------------------

# The opt-out form URL. Tier-A scripts navigate here directly; Tier-B
# scripts may navigate to a parent URL and wait at a gate.
FORM_URL = "https://example.com/opt-out"

# CSS selector that proves the form was accepted. Pick something that
# only renders AFTER successful submission (a thank-you message, a
# confirmation page heading, the URL hash changing). Don't pick the
# submit button — that's there before submission too.
SUCCESS_SELECTOR = 'h1:has-text("Thanks — we received your request")'

# Maximum wait for the success selector. 30s is the default; bump it if
# the broker's form is slow.
SUCCESS_TIMEOUT_MS = 30_000


def submit(
    profile: ConsumerProfile,
    *,
    broker_id: str,
    dry_run: bool = False,
) -> SubmissionResult:
    """Fill (and, if not dry-run, submit) the opt-out form for one broker.

    Contract:
    - Return `SubmissionResult(status="submitted", ...)` on success.
    - Raise `AutomationUnavailable(reason, url=...)` when the form
      surfaces a gate the script can't clear (captcha appeared,
      login required, region selector, etc.). The dispatcher catches
      this and converts to `status="needs_human"` so the UI can route
      the user to the gate's URL.
    - Return `SubmissionResult(status="failed", fallback_reason=...)`
      when the success selector doesn't resolve within the timeout —
      almost always means the broker changed their form and the script
      needs an update. The weekly CI health-check picks this up.
    """
    # Playwright is in the `audit` optional dep. Lazy-import inside the
    # function so the module can be loaded even when Playwright isn't
    # installed (e.g., pytest in the base environment). The dispatcher
    # gracefully handles ImportError and returns needs_human.
    from playwright.sync_api import sync_playwright

    if dry_run:
        # In dry-run, prove the script *would* work without sending the
        # request: navigate to the form, validate the field selectors
        # exist, capture a screenshot, and return submitted.
        return _dry_run_check(profile, broker_id=broker_id)

    # --- 2. Live submission. Edit the selectors and field-fill steps. -----

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(FORM_URL, wait_until="networkidle")

            # Detect runtime gates BEFORE filling. If a captcha appeared,
            # raising here gets the user a direct deep-link.
            if page.query_selector("iframe[src*='recaptcha']"):
                raise AutomationUnavailable(
                    "reCAPTCHA appeared on the form — needs a human to solve",
                    url=FORM_URL,
                )

            # Fill the form. Use Playwright's text/role/test-id selectors;
            # input names break less often than tag/css paths.
            page.get_by_label("Full name").fill(profile.full_legal_name)
            page.get_by_label("Address").fill(profile.current_address)
            if profile.email:
                page.get_by_label("Email").fill(profile.email)

            page.get_by_role("button", name="Submit").click()

            # Wait for the success selector, not just `networkidle`.
            try:
                page.wait_for_selector(SUCCESS_SELECTOR, timeout=SUCCESS_TIMEOUT_MS)
            except Exception as exc:  # noqa: BLE001 — Playwright wraps many
                return SubmissionResult(
                    status="failed",
                    broker_id=broker_id,
                    dry_run=False,
                    fallback_reason=(
                        f"success selector {SUCCESS_SELECTOR!r} did not resolve "
                        f"within {SUCCESS_TIMEOUT_MS}ms — broker likely changed "
                        f"the form. Original error: {exc}"
                    ),
                )

            screenshot = page.screenshot(full_page=True)
            # Caller (dispatcher or CI) decides where to persist the
            # screenshot; we return the bytes via evidence_payload so the
            # script stays I/O-free for testability.
            return SubmissionResult(
                status="submitted",
                broker_id=broker_id,
                dry_run=False,
                evidence_payload={
                    "form_url": FORM_URL,
                    "screenshot_bytes": screenshot,
                    "screenshot_mime": "image/png",
                },
            )
        finally:
            browser.close()


def _dry_run_check(profile: ConsumerProfile, *, broker_id: str) -> SubmissionResult:
    """Verify selectors resolve without submitting. Called from submit()."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(FORM_URL, wait_until="networkidle")

            # Confirm the form fields exist. If any is missing, the broker
            # changed their form — surface that as failed, not submitted.
            missing = []
            for label in ("Full name", "Address"):
                if not page.get_by_label(label).count():
                    missing.append(label)
            if missing:
                return SubmissionResult(
                    status="failed",
                    broker_id=broker_id,
                    dry_run=True,
                    fallback_reason=f"dry-run: form fields missing: {missing}",
                )

            return SubmissionResult(
                status="submitted",
                broker_id=broker_id,
                dry_run=True,
                evidence_payload={
                    "form_url": FORM_URL,
                    "fields_present": ["Full name", "Address"],
                },
            )
        finally:
            browser.close()
