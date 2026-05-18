# Phased Milestones

Extracted from `PLAN.md`. Each phase is independently shippable. Effort
estimates assume a single maintainer working part-time; revise as we learn.

| Phase | Status | Scope | Ships | Success criteria |
|---|---|---|---|---|
| **0 — Foundation** | ✅ **shipped** | Registry schema, 10 western-state brokers, letter engine, agent form, CLI only | `uv run delete-me` | Non-CA user produces 10 signed letters in <10 min |
| **1 — Service + Send** | ✅ **shipped** | FastAPI, SQLModel, Postmark integration (dry-run default), case tracking, docker-compose | `docker compose up` | Dry-run send persists a case with status `sent_dry_run` and an `audit_due_at` 60 days out |
| **2 — Audit MVP** | pending | 5 audit sources, 60-day arq scheduler, "still listed?" report | Nightly auditor | 80%+ audit success on test personas |
| **3 — Evidence Package** | pending | Compliance PDF builder, pre-filled CA AG form, statute citations | One-click "escalate" | Package matches CA AG submission requirements |
| **4 — Tauri Desktop** | pending | Tauri v2 shell, embedded Python sidecar, signed builds | DMG + MSI + AppImage in Releases | Non-tech user installs without terminal |
| **5 — Eastern States** | pending | +25 brokers, NY SHIELD, VA CDPA, CO CPA, CT CTDPA templates | Registry grows | Coverage of top-50 US brokers |
| **6 — DROP Integration** | pending | CalPrivacy DROP submission path; aligned with 2026-08-01 enforcement | CA users submit via DROP from app | First DROP receipts logged |
| **7 — GDPR/UK** | pending | Art. 17 erasure templates, EU broker subset | EU launch | First successful Art. 17 erasure confirmed |

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
