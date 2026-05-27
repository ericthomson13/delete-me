# Maintainer checklist

Everything the project depends on that *isn't* code — credentials,
verification passes, design assets, and time-driven checkpoints. Skim
this when planning a session to remember what's blocked on you vs.
what's blocked on code.

Companion doc to [`ROADMAP.md`](ROADMAP.md): the roadmap is the *what's
left to build*; this is the *what's left to provide*.

---

## 1. Verification work (only you can do this)

These tasks need a human with a browser and a real consumer profile.
Code can't validate them.

- [ ] **Live-test the 16 audit adapters against your profile.** Run
  `delete-me presence-check` (or wait for the next weekly
  `audit-adapter-health` CI run on Tuesday 14:23 UTC — it'll start
  filing `audit-adapter-broken` issues for any that come back
  `blocked` or `false_positive`). Per-adapter fix is usually a one-line
  tweak to `CARD_CLASS_PATTERN` or the URL template. See
  [`PHASES.md`](architecture/PHASES.md#phase-9-status) for the
  status taxonomy.

- [ ] **Promote the 15 draft brokers.** Files live in
  [`registry/brokers_draft/`](../registry/brokers_draft/). Follow
  [`VERIFYING_DRAFT_BROKERS.md`](VERIFYING_DRAFT_BROKERS.md) — about
  15–30 min per broker. Credit bureaus (Equifax / Experian /
  TransUnion) take longer because FCRA carve-outs apply.

- [ ] **Re-verify tranche-2 broker opt-out URLs** (Phase 5
  [#5](https://github.com/ericthomson13/delete-me/issues/5)). Brokers
  rotate their opt-out flows every few months; `last_verified` dates
  in `registry/brokers/*.yaml` show which are stale.

---

## 2. Optional service credentials

Every credential below is optional — the tool degrades gracefully
without it and tells the user how to configure it. Listed here so you
can decide *which* to set up when, not so you have to set them all up.

### For live email sending
- [ ] `POSTMARK_SERVER_TOKEN` — sign up at
  [postmarkapp.com](https://account.postmarkapp.com), verify a sending
  domain. Without this, `send --live` errors; dry-run still works.
- [ ] `DELETE_ME_FROM_ADDRESS` — must match a verified Postmark
  sender. Pair with the above.

### For breach-check (each provider independently optional)
- [ ] `HIBP_API_KEY` — paid ~$3.50/mo at
  [haveibeenpwned.com/api/key](https://haveibeenpwned.com/api/key).
  Most useful single provider — the canonical breach corpus.
- [ ] `INTELX_API_KEY` — free tier rate-limited at
  [intelx.io/account](https://intelx.io/account). Broader leak corpus
  (forums, paste sites, Telegram).
- [ ] `DEHASHED_USERNAME` + `DEHASHED_API_KEY` — paid at
  [dehashed.com/pricing](https://dehashed.com/pricing). Per-field
  exposure detail (which columns leaked) and more obscure dumps.

### For docker self-host with remote clients
- [ ] `DELETE_ME_API_KEY` — pick any random string. Set it on the
  service env and on every client that calls in. `/health` stays
  exempt for liveness probes.

### Blocked on external timing
- [ ] `CALPRIVACY_DROP_ENDPOINT` + `CALPRIVACY_DROP_TOKEN` — waiting
  for CalPrivacy to publish the production DROP API spec. See the
  scheduled checkpoint below.

Reference table for every env var the tool reads: [`INSTALL.md`](INSTALL.md#environment-variables).

---

## 3. Developer tooling

What contributors need installed to build, test, and run the project.

### Required for any work
- **Python 3.12** — pin matches `pyproject.toml`. `pyenv` or `uv
  python install 3.12` both work.
- **uv ≥ 0.4** — the Python package manager. Install with
  `curl -LsSf https://astral.sh/uv/install.sh | sh`. Replaces
  pip/venv/poetry workflow; one command (`uv sync --all-extras`)
  installs everything.

### Required for Tauri UI work
- **Node ≥ 22** — Tauri's UI runtime. Bundled via Tauri's docs link.
- **pnpm ≥ 11** — UI package manager. `npm install -g pnpm` if needed.
- **Rust toolchain** — Tauri's Rust core. Install via `rustup`.
- **Platform-specific Tauri prereqs** (WebView2 on Windows, libs on
  Linux) — see [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

### Required only for the audit / automation extras
- **Playwright + Chromium** — used by Tier-A/B automation scripts and
  the experimental real audit adapters. `uv run playwright install
  --with-deps chromium` after `uv sync --all-extras`.

### Required only for desktop release builds
- **PyInstaller** — bundles the FastAPI service as the Tauri sidecar.
  Already in dev deps; pulled in by `uv sync --all-extras`.

### Optional, recommended
- **`gh` CLI** — used by automation-health and audit-adapter-health
  workflows to open/close issues. Local dev doesn't need it; CI uses
  the workflow's `GITHUB_TOKEN`.
- **`torsocks` or local Tor proxy** — only if you want to anonymize
  breach lookups today. The
  [tor-proxy proposal](architecture/proposals/tor-proxy-for-breach-lookups.md)
  recommends *not* building native support; `torsocks delete-me
  breach-check` is the escape hatch.

---

## 4. Design assets

- [ ] **Real product icons** (Phase 4
  [#2](https://github.com/ericthomson13/delete-me/issues/2)). The
  Tauri app currently uses the bold-M + strikethrough placeholder
  generated by `scripts/gen-icon.py`. See
  [`tauri-app/src-tauri/icons/README.md`](../tauri-app/src-tauri/icons/README.md)
  for regeneration steps. Brand identity: strikethrough "me" + muted
  purple (`#7c3aed`), already encoded in `app.css`.

- [ ] **Favicon** for the UI dev server — `tauri-app/ui/static/favicon.png`
  if you want one in browser-dev mode.

- [ ] **Marketing artwork** — README hero image, social cards, etc.
  Not blocking; nice for a v1 announcement.

---

## 5. Time-driven checkpoints

- **2026-08-01 — DROP go-live readiness check**. A remote-trigger
  routine
  ([`trig_01Fho9wU38DimJXn1sw3UhfV`](https://claude.ai/code/routines/trig_01Fho9wU38DimJXn1sw3UhfV))
  fires at 15:00 UTC and opens a `DROP go-live readiness check`
  issue. If Phase 6
  [#6](https://github.com/ericthomson13/delete-me/issues/6) /
  [#7](https://github.com/ericthomson13/delete-me/issues/7) are still
  open then, live DROP submissions stay blocked. The trigger is
  configured to remind, not to fix — you still drive the response.

- **Weekly — automation-health**. `.github/workflows/automation-health.yml`
  runs Monday 14:17 UTC, dry-runs every Tier-A/B automation script
  against a synthetic profile, files `automation-broken` issues on
  regressions, and bot-commits `last_automation_pass` date bumps on
  successes. No action needed unless an issue lands in your inbox.

- **Weekly — audit-adapter-health**. `.github/workflows/audit-adapter-health.yml`
  runs Tuesday 14:23 UTC, probes every audit adapter against a
  synthetic profile, files `audit-adapter-broken` issues on
  regressions, and bot-commits `audit_sources_last_pass` date bumps.
  Same maintenance posture — only act when issues are filed.

---

## 6. Editorial / policy decisions deferred

These are explicitly held until you decide; they don't auto-unblock.

- **Argon2id + SQLite encryption** (Phase 4
  [#3](https://github.com/ericthomson13/delete-me/issues/3)).
  Research deposited: SQLCipher + OS keychain hybrid (NOT Stronghold).
  Hold reason: real threat model needed before adding complexity.
- **Tor proxy for breach email lookups**. Proposal at
  [`architecture/proposals/tor-proxy-for-breach-lookups.md`](architecture/proposals/tor-proxy-for-breach-lookups.md).
  Recommendation: don't build until a user surfaces a concrete threat
  model. Half-day to ship when triggered.
