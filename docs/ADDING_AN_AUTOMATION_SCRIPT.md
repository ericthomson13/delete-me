# Adding a submission-automation script

This is a focused, scoped PR. You do need to write a bit of Python — but it's
mostly Playwright selectors and the framework handles the rest.

If you're adding a *broker* (not automation for an existing one), start with
[`ADDING_A_BROKER.md`](ADDING_A_BROKER.md) instead.

## 1. Decide the tier

| Tier | Use when | What the script does |
|---|---|---|
| **`auto`** | The broker's form has no bot gate (no captcha, no login, no agreement interstitial). Found by browser verification. | Fills the form and clicks submit. Returns `submitted` on success. |
| **`semi`** | The form has a gate the user can clear (login they already have, agreement they accept). | Fills what it can, navigates to the gate, raises `AutomationUnavailable` with a URL the user opens. |
| **`manual`** | The form is captcha-gated end-to-end, or the broker requires human verification (notarized form, email click-through). | **No script needed.** Omit the `automation:` block entirely — the dispatcher already opens the broker's web form for the user. |

If the answer is `manual`, you're done — no script, no PR. Otherwise, continue.

## 2. Copy the template

```sh
cp core-py/delete_me/automation/scripts/_TEMPLATE.py \
   core-py/delete_me/automation/scripts/<broker_id>.py
```

The filename's stem (without `.py`) must match `[a-z][a-z0-9_]*` (validated
by the schema). Use the broker's slug from `registry/brokers/`.

## 3. Fill in the template

Edit the four marked sections in your new file:

- `FORM_URL` — the opt-out form. Same as the broker YAML's `opt_out.web_form`.
- `SUCCESS_SELECTOR` — a CSS selector that only renders **after** a
  successful submission. Don't use the submit button — that's there before
  submission too. Good picks: thank-you headings, confirmation text, URL hash
  changes.
- The field-fill block inside `with sync_playwright() as p:` — use
  Playwright's `get_by_label` / `get_by_role` selectors; they break less
  often than CSS paths.
- The dry-run check at the bottom — verify the field selectors exist
  without actually submitting.

## 4. Wire the broker YAML

Add an `automation:` block to `registry/brokers/<broker_id>.yaml`:

```yaml
automation:
  tier: auto       # or semi
  script: <broker_id>.py
```

`last_automation_pass` gets filled in by CI after the first green run.
Don't hand-edit it.

## 5. Run it locally

```sh
# Dry-run first — fills the form and validates selectors but doesn't submit.
uv run delete-me automation-run --broker <broker_id> \
    --profile ./profile.json --dry-run

# When dry-run looks clean, try a live submission against your own data.
uv run delete-me automation-run --broker <broker_id> \
    --profile ./profile.json --live
```

`--dry-run` is the default for safety. The framework also gracefully
degrades if Playwright isn't installed — you'll get `needs_human` instead
of an import error. Install with `uv sync --all-extras` to bring in the
`audit` extra (which includes Playwright), then `playwright install chromium`.

## 6. Run the health check (optional)

```sh
uv run delete-me automation-health
```

Iterates every script in `--dry-run` and prints a summary. Same code path
the weekly CI workflow uses.

## 7. Open a PR

- Branch: `add-automation-<broker_id>`
- Commit: `Phase 8 (#8): automation script for <broker_id>`
- Include in the PR description: a screenshot from the dry-run, the
  `last_verified` date you confirmed the form against, and any
  workaround you used for a quirky selector.

## Common pitfalls

- **Eager Playwright import at the top of your script.** The template
  lazy-imports inside `submit()` so the module loads in environments
  without Playwright (e.g., contributors running `pytest` without
  `--all-extras`). If you must eager-import, the dispatcher catches the
  ImportError and returns `needs_human`, but the test suite will skip
  your file.
- **`SUCCESS_SELECTOR` matches a pre-submission element.** Symptom: the
  script returns `submitted` even when submission failed. Pick a
  post-submission-only element.
- **Selectors brittle to broker UI redesigns.** Prefer
  `get_by_label("Full name")` over `input[name="fullName"]` over
  `#fl-1234`. The first two survive class renames; the third doesn't.
- **Forgetting to raise `AutomationUnavailable` for runtime gates.** If a
  captcha or login appears mid-flow, *raising* (not returning `failed`)
  is the right move — the dispatcher converts it to a `needs_human` with
  the URL override, which is what you want.

## What CI does with your script

The `automation-health.yml` workflow runs every Monday:

1. `uv sync --all-extras && playwright install chromium`
2. `delete-me automation-health` over every broker with `automation.tier
   in (auto, semi)`.
3. On success: a bot commit bumps `automation.last_automation_pass` to
   today.
4. On failure: a single GitHub issue is opened (idempotent — re-runs
   don't dupe) with the screenshot as a workflow artifact and the
   `fallback_reason` in the body.

So: when your script breaks because the broker changed their form, you'll
get a notification within 7 days instead of when a user tries to send.
