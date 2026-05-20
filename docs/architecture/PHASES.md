# Phased Milestones

Extracted from `PLAN.md`. Each phase is independently shippable. Effort
estimates assume a single maintainer working part-time; revise as we learn.

| Phase | Status | Scope | Ships | Success criteria |
|---|---|---|---|---|
| **0 — Foundation** | ✅ **shipped** | Registry schema, 10 western-state brokers, letter engine, agent form, CLI only | `uv run delete-me` | Non-CA user produces 10 signed letters in <10 min |
| **1 — Service + Send** | ✅ **shipped** | FastAPI, SQLModel, Postmark integration (dry-run default), case tracking, docker-compose | `docker compose up` | Dry-run send persists a case with status `sent_dry_run` and an `audit_due_at` 60 days out |
| **2 — Audit MVP** | ✅ **shipped** | Audit orchestrator + mock + one experimental httpx adapter + audit-due sweeper (CLI + HTTP + docker scheduler container) | `delete-me audit-due` or POST `/audits/sweep` | A noncompliant case transitions to status `noncompliant` with audit evidence on disk |
| **3 — Evidence Package** | ✅ **shipped** | PackageBuilder produces a directory + zip with letter, agent designation, send receipt, audit evidence, statute citations, pre-filled CA AG complaint draft, and attorney referral pointers | `delete-me evidence --case N` or POST `/cases/:id/evidence` | A user can hand the zip to the CA AG or a plaintiff's attorney |
| **4 — Tauri Desktop** | 🚧 **in progress** | Tauri v2 shell, embedded Python sidecar, signed builds | DMG + MSI + AppImage in Releases | Non-tech user installs without terminal |
| **5 — Eastern States** | 🚧 **in progress** | +25 brokers, NY SHIELD, VA CDPA, CO CPA, CT CTDPA templates | Registry grows | Coverage of top-50 US brokers |
| **6 — DROP Integration** | pending | CalPrivacy DROP submission path; aligned with 2026-08-01 enforcement | CA users submit via DROP from app | First DROP receipts logged |
| **7 — GDPR/UK** | pending | Art. 17 erasure templates, EU broker subset | EU launch | First successful Art. 17 erasure confirmed |

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

**Toward the "top-50" success criterion** (35 → 50): the remaining ~15
entries belong on the easy-PR path. `registry-validate.yml` gates each new
YAML on schema + statute cross-check, and the 5-minute non-coder PR
contract described in CONTRIBUTING applies. Maintainers should also do a
verification pass on the tranche-2 entries (current `last_verified=2026-05-19`
reflects research-time, not browser-time, validation of opt-out URLs).

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
