# Draft brokers (not loaded)

YAML files in this directory are **drafts**, not active registry entries.
The schema/loader scans `registry/brokers/` only, so anything here is
ignored by:

- `delete-me list-brokers`
- `delete-me validate-registry`
- the FastAPI `/brokers` endpoint
- the CLI/UI presence-check + breach-check flows

## What's in a draft

Each draft has the fields a human can fill in confidently from public
knowledge — id, name, website, tier classification, the kinds of PII
the broker typically requires — and leaves the verification-dependent
fields blank with `TODO:` markers:

- `opt_out.email` / `opt_out.web_form` / `opt_out.postal` — these are
  what a deletion letter is actually sent to; **wrong values here cause
  silent failures and waste user time**, which is why they don't ship
  until a human verifies them against the live broker site.
- `last_verified` — set to the sentinel `1970-01-01` to mean "never
  verified by a human". The schema's `format: date` requirement is
  satisfied; the value's wrongness is obvious.
- `maintainer` — set to `@needs-verification`. When a real maintainer
  takes over, they replace this with their `@handle`.

## How to promote a draft

See [`docs/VERIFYING_DRAFT_BROKERS.md`](../../docs/VERIFYING_DRAFT_BROKERS.md)
for the checklist. The short version:

1. Open the draft YAML in this dir.
2. Open the broker's privacy / opt-out page in a browser.
3. Fill in every `TODO:` field with what you observed.
4. Update `last_verified` to today (UTC, ISO date).
5. Update `maintainer` to your `@handle`.
6. `git mv registry/brokers_draft/<broker>.yaml registry/brokers/<broker>.yaml`.
7. `uv run delete-me validate-registry` — must pass.
8. Open a PR titled `registry: promote <broker_id> from draft`.

## Why not just write the data here

Because data brokers change their opt-out flows constantly. A field
filled in from memory today is wrong six months from now — and the
worst kind of wrong, because the user has no way to tell their letter
went to a dead address. Drafts are an honest scaffold: they say
"someone thinks this broker exists; nobody has verified the contact
path yet."
