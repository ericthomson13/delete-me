# Phased Milestones

Extracted from `PLAN.md`. Each phase is independently shippable. Effort
estimates assume a single maintainer working part-time; revise as we learn.

> Open follow-ups are tracked in [`../ROADMAP.md`](../ROADMAP.md) with one
> GitHub issue per deliverable.

| Phase | Status | Scope | Ships | Success criteria |
|---|---|---|---|---|
| **0 — Foundation** | ✅ **shipped** | Registry schema, 10 western-state brokers, letter engine, agent form, CLI only | `uv run delete-me` | Non-CA user produces 10 signed letters in <10 min |
| **1 — Service + Send** | ✅ **shipped** | FastAPI, SQLModel, Postmark integration (dry-run default), case tracking, docker-compose | `docker compose up` | Dry-run send persists a case with status `sent_dry_run` and an `audit_due_at` 60 days out |
| **2 — Audit MVP** | ✅ **shipped** | Audit orchestrator + mock + one experimental httpx adapter + audit-due sweeper (CLI + HTTP + docker scheduler container) | `delete-me audit-due` or POST `/audits/sweep` | A noncompliant case transitions to status `noncompliant` with audit evidence on disk |
| **3 — Evidence Package** | ✅ **shipped** | PackageBuilder produces a directory + zip with letter, agent designation, send receipt, audit evidence, statute citations, pre-filled CA AG complaint draft, and attorney referral pointers | `delete-me evidence --case N` or POST `/cases/:id/evidence` | A user can hand the zip to the CA AG or a plaintiff's attorney |
| **4 — Tauri Desktop** | 🚧 **in progress** | Tauri v2 shell, embedded Python sidecar, signed builds | DMG + MSI + AppImage in Releases | Non-tech user installs without terminal |
| **5 — Eastern States** | ✅ **shipped** | +25 brokers, NY SHIELD, VA CDPA, CO CPA, CT CTDPA templates | Registry grows | Coverage of top-50 US brokers |
| **6 — DROP Integration** | 🚧 **in progress** | CalPrivacy DROP submission path; aligned with 2026-08-01 enforcement | CA users submit via DROP from app | First DROP receipts logged |
| **7 — GDPR/UK** | pending | Art. 17 erasure templates, EU broker subset | EU launch | First successful Art. 17 erasure confirmed |
| **8 — Submission Automation** | 🚧 **in progress** | Tiered Playwright submission framework (auto/semi/manual), per-broker scripts, weekly CI health-check | `delete-me automation-run --broker X` | First broker auto-submitted with screenshot evidence |

## Phase 6 status

Submission packager, transport adapter, case status, CLI, HTTP route, and
tests are all in. The DROP submission payload (`DropSubmission` in
`core-py/delete_me/transport/drop.py`) follows the CalPrivacy rulemaking
("Required Consumer Information") shape: identity + prior addresses +
attestation citing Cal. Civ. Code §1798.99.86 + a list of broker
CalPrivacy IDs.

**Live submit is stubbed pending the production endpoint.** As of writing
(2026-05-19), the CalPrivacy production submission URL has not published.
The transport reads `CALPRIVACY_DROP_ENDPOINT` from the environment; until
that's set, `live=True` raises `TransportError` with a clear message
pointing at the 2026-08-01 enforcement date. Dry-run is the default and
fully functional — it writes the submission payload to
`$DELETE_ME_DROP_OUT/<receipt>.json` for evidence and returns a synthetic
receipt id.

What needs to happen before declaring Phase 6 shipped:

1. **Populate `opt_out.calprivacy_id`** on the broker entries marked
   `drop_registered: true`. **Blocked on upstream as of 2026-05-20**: the
   CPPA public registry (4 CSV downloads at
   `https://cppa.ca.gov/data_broker_registry/`) keys every broker by
   *legal name* — there is no DB-xxxx (or any other) per-broker ID column,
   and the consumer-facing DROP docs describe a single broadcast request
   rather than a per-broker selector. Best guess: the production DROP API
   spec (publishing alongside the 2026-08-01 enforcement date) will
   define what identifier to send; until then this field has no canonical
   value to populate. Tracked in #6.
2. **Wire the production URL** into `CALPRIVACY_DROP_ENDPOINT` (or hardcode
   in `transport/drop.py`) once CalPrivacy publishes it. The live-path code
   is already written and tested against a `httpx.MockTransport`.
3. **First real receipt logged** — the success criterion in the table
   above. Until step 2 is done, dry-run receipts and the on-disk payload
   are the closest we get.

The on-disk submission payload (dry-run) is itself useful evidence today:
a CA user can run `delete-me drop-submit --dry-run` and hand the resulting
JSON to the AG as proof that a delete request *would have been* submitted
through DROP, in the format CalPrivacy intends.

## Phase 5 status

**Scope target hit: 25 new brokers added (10 → 35 total).** The four
eastern-state statutes (NY SHIELD, VA CDPA, CO CPA, CT CTDPA) were already
present in `legal/statute_citations.yaml` from earlier work; Phase 5 wired
`va_cdpa`/`co_cpa`/`ct_ctdpa` into the existing 10 Phase 0 entries so
residents of those states get those rights cited in their letters. NY SHIELD
is a security-safeguards statute rather than a deletion right and is
intentionally not referenced from broker entries.

New brokers, by tranche:
- **Tranche 1** (commit `4ee949e`): lexisnexis_risk, corelogic, epsilon,
  pipl, truthfinder, instantcheckmate, peoplelooker, peekyou,
  familytreenow, thatsthem, nuwber.
- **Tranche 2**: clustrmaps, smartbackgroundchecks, advancedbackgroundchecks,
  backgroundalert, checkpeople, publicrecordsnow, publicrecords360,
  usphonebook, searchpeoplefree, veripages, searchquarry, lookupanyone,
  zoominfo, dun_bradstreet.

**Tranche-2 browser-verification pass** (2026-05-20): all 14 entries
were walked through in a real browser. 12 confirmed (most gated by
Cloudflare/reCAPTCHA or, in ZoomInfo's case, a press-and-hold challenge —
all require human submission, which is fine for a locally-running desktop
app). 2 dropped from the registry: `backgroundalert` (DNS-dead) and
`lookupanyone` (TCP-unreachable from multiple networks). Net broker
count is therefore 33, not 35.

**Top-50 success criterion hit 2026-05-20: 33 → 50 brokers.** Tranche 3
added 17 new entries pulled from CPPA's `complete-reg-data-brokers.csv`
and `registry2025.csv`, all browser-verified the same day:

- **Enterprise aggregators (9)**: liveramp, oracle_data_cloud, data_axle,
  rocketreach, apollo_io, seamless_ai, lusha, peopledatalabs, outlogic.
- **People search (5)**: spydialer, searchbug, peoplesearcher,
  uspeoplesearch, calltruth's slot replaced *(see below)*.
- **Long-tail / reputation (3)**: privaterecords, infomatics, weinform,
  checksecrets.

Deliberate omissions: the three Big-3 credit bureaus (Experian, Equifax,
TransUnion) and Equifax Workforce Solutions were considered and **deferred
to a follow-up**, because they're FCRA-regulated and need new schema
fields (`regulated_by`, `removal_scope`, `disclaimers`) to be presented
honestly in the desktop UI — sending a generic "we deleted you" message
for a credit bureau would misrepresent what CCPA actually does (FCRA
exempts the credit-report data itself). The four long-tail/mugshot
entries carry a `disclaimer_pending` marker in their `notes:` block for
the same follow-up.

Mid-pass replacements: `openpeoplesearch` was added but immediately
dropped (site discontinued per browser check); `calltruth` was added,
discovered DNS-dead during pre-screen (same shape as backgroundalert
from tranche 2), and replaced with `uspeoplesearch` from the 2025 CSV.

Forward-looking automation work (Playwright-based tiered submission) is
tracked in #8.

## Phase 4 status

Vertical slice + reliability + release plumbing landed. What's in:

- Tauri v2 + SvelteKit scaffold in `tauri-app/`, FastAPI sidecar entry at
  `service/sidecar_entry.py`, PyInstaller build at `scripts/build-sidecar.sh`,
  one wired screen (case list).
- Rust shell spawns the sidecar, reads its advertised loopback port from
  stdout, exposes it to the UI via the `get_api_base` Tauri command.
- **Sidecar healthcheck + auto-restart**: a Rust async monitor polls
  `/health` every 10s; after 3 consecutive failures it respawns the
  sidecar, re-using the original port (via `DELETE_ME_SIDECAR_PORT`) so the
  UI's cached api_base stays valid across crashes.
- **Release CI** (`.github/workflows/release-desktop.yml`): on tag push,
  builds **unsigned** DMG / MSI / AppImage bundles on macOS / Windows /
  Linux runners and uploads to a draft GitHub release.
- **Signing playbook** (`docs/RELEASING.md`): manual Developer ID + notarize
  for macOS, Authenticode + EV token for Windows, optional GPG for AppImage.
  Signing stays maintainer-local for now (EV tokens and Apple keys aren't
  going into GH Actions secrets while pre-1.0).

Remaining: rest of the UI (profiles / brokers / audits / evidence), real
product icons, and the first-run argon2id passphrase flow. See
`tauri-app/README.md` for the dev loop.

## Phase 8 status

Tiered submission-automation framework (#8) landed as a skeleton: schema
field, dispatcher, reference stub. The UI still needs work to surface the
new return values, and the per-broker scripts are mostly unwritten.

What's in:

- `registry/schemas/broker.schema.json` — optional `automation` block
  with `tier: auto|semi|manual`, `script: <filename>.py`, and
  `last_automation_pass: <ISO date>` (bot-filled by CI). Absence of the
  block = treat as `manual`, identical to `tier=manual`.
- `core-py/delete_me/automation/` — `base.py` (interfaces +
  `AutomationUnavailable`), `dispatcher.py`, `scripts/`. The dispatcher
  never raises for the "no automation configured" case; it returns
  `SubmissionResult(status="needs_human", evidence_payload={"url": ...})`
  so the UI can open the broker's web form.
- `automation/scripts/checkpeople.py` — reference implementation as a
  **stub**: dry-run returns `submitted`; live raises
  `AutomationUnavailable` until the real Playwright impl lands. Wired
  into `registry/brokers/checkpeople.yaml` (the only broker with an
  `automation:` block today).
- `delete-me automation-run --broker <id> --dry-run` CLI command that
  exercises the dispatcher end-to-end.
- Tests in `core-py/tests/test_automation.py` cover the dispatcher's
  three branches (unknown broker → ValueError; no automation block →
  needs_human; auto tier with stub script → submitted on dry-run, needs_human
  on live), plus the `automation-health` CLI iteration.

Contributor pipeline (#9, commit `f09622b`):
- `core-py/delete_me/automation/scripts/_TEMPLATE.py` — heavily commented
  reference module a contributor copies to add a Tier-A/B script.
- `docs/ADDING_AN_AUTOMATION_SCRIPT.md` — 5-minute-PR walkthrough that
  mirrors `ADDING_A_BROKER.md` in tone.

Weekly health-check (#10):
- `delete-me automation-health [--json] [--screenshot-dir DIR]` CLI
  command iterates every broker with `automation.tier in (auto, semi)`
  and emits one row per result. Used locally for spot-checks and by CI.
- `.github/workflows/automation-health.yml` runs the CLI weekly (Mon
  14:17 UTC), uploads screenshots as artifacts, opens a single GitHub
  issue per broken script (labeled `automation-broken`, idempotent),
  and bot-commits a `last_automation_pass` date bump for each script
  that passed.
- `.github/scripts/automation_health_followup.py` handles the gh-CLI
  side effects (label create, idempotent issue open, regex-based YAML
  date bump that preserves comments and formatting).

What's missing:

- **Real per-broker scripts.** The checkpeople stub is the only one;
  each Tier-A/B broker gets its own follow-up issue per the
  "5-minute non-coder PR" contract.
- **UI integration.** The case-detail page (added in #1) needs a
  "Submit via automation" action that calls the new CLI command and
  routes the SubmissionResult — submitted → success toast,
  needs_human → open the URL, failed → surface fallback_reason.
  Tracked in #11.
- **Per-broker tier audit.** Most of our 50 brokers should land in
  Tier C (manual) without a YAML change. Tier A candidates probably
  include checkpeople, publicrecordsnow (no bot gate per the 2026-05-20
  verification). Tier B candidates include the captcha-gated ones and
  zoominfo's press-and-hold. None of this is in the registry yet.

The disclaimer/regulation schema work (`regulated_by`, `removal_scope`,
`disclaimers`) that the Phase 5 tranche-3 verification deferred is a
separate follow-up to this work — it changes per-broker UX presentation,
not the submission path itself.

## Phase 9 status

Pre-send presence-check landed. Reuses the existing `AuditAdapter` contract
verbatim — the only new code is an orchestrator, a `PresenceResult` table
keyed on (profile_id, broker_id, source), and the CLI wiring.

What's in:

- `core-py/delete_me/audit/presence.py` — `PresenceOrchestrator.check_profile`
  iterates a profile against every broker (or a subset), caches results for
  `fresh_days` (default 7), and degrades to inconclusive on adapter errors
  or missing adapters — never raises.
- `core-py/delete_me/db/models.py` — `PresenceResult` table. New tables are
  picked up automatically by `init_db()`; no migration needed.
- CLI: `delete-me presence-check [--broker ID] [--fresh-days N] [--json]`
  prints a marker-per-row table plus a coverage footer that names how many
  brokers had no audit source configured.
- CLI: `delete-me send --case N --check-first [--force]` runs the
  presence-check for the case's broker first and skips the send if every
  real source returned not-found.
- Tests: `core-py/tests/test_presence.py` covers found / not-found /
  no-source / no-adapter / adapter-raises / cache-hit / cache-expired
  using the existing `MockAuditAdapter`.

What's missing (explicit scope cutoffs):

- **Adapter coverage.** Today only `truepeoplesearch_search` is wired in
  `production_registry()`. Most broker YAMLs still have `audit_sources: []`
  and will surface in the footer as uncheckable. Adding adapters is the
  next leverage point and is tracked separately from this phase.
- **Service / Tauri surface.** CLI-only for MVP. The FastAPI service and
  the desktop app can mirror in a follow-up; the orchestrator + table are
  reusable as-is.

## Phase 10 status

Breach-exposure lookup across three independently-optional providers
(HIBP, IntelX, DeHashed), plus a free k-anonymity password check.
Each provider degrades gracefully: missing credentials at startup → a
setup-hint row; auth/quota failure mid-run → provider disabled for the
run, others keep going.

What's in:

- `core-py/delete_me/breaches/` — `base.py` (`BreachAdapter` ABC +
  `BreachAdapterUnavailable`), one adapter module per provider:
  - `hibp.py` — v3 `breachedaccount`, 1.5s in-process throttle,
    401/404/429 handled distinctly. Setup: `HIBP_API_KEY` (paid).
  - `intelx.py` — async phonebook search (POST + poll), collapses
    records to one row per unique bucket. Setup: `INTELX_API_KEY` (free
    tier exists; rate-limited). `INTELX_BASE_URL` overridable.
  - `dehashed.py` — basic-auth search, collapses entries to one row per
    `database_name` with the populated columns mapped to data-class
    labels (no credentials persisted). Setup: `DEHASHED_USERNAME` +
    `DEHASHED_API_KEY` (paid).
  - `passwords.py` — `PwnedPasswordsClient.lookup(password)` does SHA-1
    locally and sends only the 5-char hex prefix. No key, no persistence.
  - `orchestrator.py` — `discover_registry()` returns the live adapters
    plus a `ProviderStatus` row per provider (with setup hint when
    unavailable). `BreachOrchestrator.check_email` upserts
    `BreachExposure` rows; mid-run `BreachAdapterUnavailable` removes
    the offending provider from the active set and records it in
    `runtime_disabled` instead of aborting.
- `core-py/delete_me/db/models.py` — `BreachExposure` table.
- CLI:
  - `delete-me breach-check [--email ADDR]... [--json]` — runs every
    available provider, prints a per-row `[source]` tag plus an
    "Active providers" / "Skipped at startup" / "Disabled mid-run"
    footer so the user knows exactly which providers ran and which
    didn't (and why).
  - `delete-me password-check [--stdin]` — k-anonymity Pwned Passwords
    check. Hidden prompt by default; `--stdin` for piped input.
- Tests: `core-py/tests/test_breaches.py` covers each adapter (missing
  creds / 200 / 404 / 401 / 429-retry / rerun-dedup / IntelX bucket
  collapse / DeHashed credit-exhaustion / Pwned Passwords prefix-only
  contract) plus the multi-provider discovery and mid-run-disable logic.

What's missing:

- **Service / Tauri surface.** CLI-only for now; the orchestrator and
  adapters are pure-Python and reusable as-is.
- **Tor-style anonymization for IntelX / DeHashed lookups.** HIBP gets
  the k-anonymity treatment via the password endpoint, but the email
  endpoints on all three send the actual email. Out of scope for MVP.

## Phase 0 acceptance gate

Phase 0 is complete and shippable when all six verification steps in
`PLAN.md` ("Verification") pass on a fresh clone. The CI workflow
`registry-validate.yml` runs the schema-validation step automatically on PRs.

## Geographic phasing inside each phase

US coverage rolls out in two slices to bound the per-phase surface:

- **Slice A — Western states** (Phases 0–4): AK, AZ, CA, CO, HI, ID, MT, NM,
  NV, OR, UT, WA, WY plus the federal CCPA-portable brokers. ~25 jurisdictions.
- **Slice B — Eastern states** (Phase 5): NY, NJ, PA, MA, CT, VT, NH, ME, MD,
  DC, VA, NC, SC, GA, FL, AL, MS, TN, KY, WV, OH, IN, IL, MI, WI, MN, IA,
  MO, AR, LA, OK, KS, NE, ND, SD, TX. ~25 jurisdictions (some overlap).
- **EU/UK** lands in Phase 7 (GDPR Article 17).

The point of the slicing is so a maintainer can stop after any phase and the
prior slice still works end-to-end for its users.
