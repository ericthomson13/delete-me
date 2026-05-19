# Plan: `delete-me` — Open-Source Data Broker Letter-Sender + DROP Audit Tool

**Repo target:** `ericthomson13/delete-me` (working name; alternatives: `vanish`, `optout-kit`)
**Maintainer:** `ericthomson13`
**License:** AGPL-3.0 (copyleft prevents commercial fork-and-close)

---

## Context

The user wants a new open-source repo that helps "minorly tech-savvy" people remove themselves from data brokers. Initial research (cited in the planning trail) found that the standard approach — per-broker form-submission scraping — is a graveyard: PrivacyBot (Berkeley, 541 ⭐, deprecated 2021), JustVanish (113 ⭐, never shipped to users), Auto-Identity-Remove (2025 beta, "most heuristics fail") all died fighting Cloudflare Turnstile and broker-page churn. Meanwhile, two market shifts changed the calculus:

1. **California's DROP registry** (under SB 362, the Delete Act) went live **2026-01-01**, with enforcement and $200/request/day penalties beginning **2026-08-01** — 11 weeks from today. 545+ brokers are registered and must honor a single bulk-delete request every 45 days.
2. **EasyOptOuts** ($19.99/yr) already covers the commercial market for minimally-tech-savvy users; competing on raw broker coverage is unwinnable for one maintainer.

So `delete-me` does **not** try to scrape opt-out forms. Instead it occupies two niches existing tools don't:

- **CCPA / state-DSAR / GDPR letter-sender** — generate and email authorized-agent deletion letters to brokers. ~80% of the value of paid tools at ~5% of the engineering cost. (What Incogni does, productized for OSS.)
- **DROP compliance audit** — genuinely novel: after a CA DROP request, wait ~60 days, then verify the user is actually gone from people-search sites. Generate a non-compliance evidence package the user can take to the CA AG, a private-right-of-action plaintiff's attorney, or a state regulator. **Nobody is building this.** It also doubles as the post-letter audit for non-CA users.

The repo serves a real public-interest gap (holding the new law accountable) while being maintainable by one person because it deliberately stays out of the scraping arms race.

---

## Recommended approach

### Architecture (single monorepo)

```
delete-me/
├── registry/                YAML, one file per broker — the OSS leverage point
│   ├── brokers/             e.g. acxiom.yaml, spokeo.yaml
│   └── schemas/             broker.schema.json, statute.schema.json
├── core-py/                 Python 3.12 shared domain logic
│   └── delete_me/
│       ├── registry/        pydantic loader + validator
│       ├── letters/         Jinja2 templates → WeasyPrint PDF
│       ├── audit/           Playwright read-only adapters per source
│       ├── evidence/        compliance package builder
│       └── agent_form/      authorized-agent designation generator + audit log
├── service/                 FastAPI app (used by both Tauri sidecar and docker)
│   └── service/
│       ├── api/
│       ├── workers/         arq (Redis-backed) for the 60-day audit timers
│       └── db/              SQLModel; SQLite (Tauri) / Postgres (docker)
├── tauri-app/               Rust workspace (Tauri v2 + SvelteKit UI)
│   ├── src-tauri/
│   └── ui/
├── docker/                  Dockerfile.service + docker-compose.yml
├── legal/
│   ├── authorized_agent_template.md
│   ├── statute_citations.yaml      machine-readable CCPA / Delete Act / GDPR refs
│   └── attorney_referral_sources.md  links to NACA + state bar lookups (no firm endorsements)
├── docs/                    README, INSTALL, USER_GUIDE, SECURITY, CONTRIBUTING, LEGAL_DISCLAIMER, ADDING_A_BROKER
└── .github/workflows/       ci-python.yml, ci-rust.yml, registry-validate.yml
```

**Why one repo:** the broker registry is the load-bearing artifact and must be the single source of truth consumed by both Python (letters/audit) and Rust (Tauri UI). Two repos = constant version skew on the only thing whose value is staying current.

### Two deployment targets, shared core

- **Tauri v2 desktop app** (Rust shell + SvelteKit UI + embedded Python sidecar) — PII never leaves the user's machine. Default for non-technical users. Signed builds for macOS/Windows/Linux published to GitHub Releases.
- **docker-compose self-host** — FastAPI + Postgres + Redis. For users who prefer a server. PII encrypted at rest with argon2id-derived key (passphrase the operator never sees).

### Core data flow

```
  registry/*.yaml ──┐
                    ├─► Letter Engine (Jinja2→PDF→Postmark) ──┐
                    │                                          ▼
                    ├─► Audit Engine (Playwright read-only) ─► Case Store (SQLModel)
                    │                                          │
                    └─► Tauri UI (reads registry directly)     │ 60-day timer fires
                                                               ▼
                                                       Evidence Package Builder
                                                       (PDF: letter copy + audit
                                                        screenshots + statute cites
                                                        + pre-filled AG form)
```

### Broker registry schema (`registry/schemas/broker.schema.json`)

Each broker is one YAML file. Adding a broker is a 5-minute non-coder PR; CI validates against JSON Schema.

```yaml
id: spokeo
name: Spokeo, Inc.
opt_out:
  methods: [email, web_form, postal, drop]   # ordered by preference
  email: privacy@spokeo.com
  web_form: https://spokeo.com/optout
  drop_registered: true
  calprivacy_id: "DB-0000123"
accepts_authorized_agent: true
agent_form_requirements: [signed_permission, government_id_redacted]
required_pii: [full_name, current_address, prior_addresses, dob_year]
re_aggregation_days: 45
audit_sources: [spokeo_search]
statutes: [ccpa_1798_105, delete_act_1798_99_86]
last_verified: 2026-04-12
```

### Authorized-agent form — answering the PoA question directly

**A full Power of Attorney is NOT required and NOT recommended.** Per CCPA §1798.140(d) and 11 CCR §7063, a **scoped written permission** is sufficient. This is *not* a Probate Code §4000 PoA (which grants broad authority over assets and is the wrong instrument here). The form `delete-me` generates contains:

- Consumer name + address + email
- Agent name: `Extra-Terrestrial Designs / delete-me tool, acting on behalf of consumer`
- **Scope (deliberately narrow):** "Authority limited to submitting CCPA §1798.105 deletion requests and §1798.120 opt-out-of-sale requests to data brokers in the attached schedule. No authority to modify accounts, receive personal information, or take any other action."
- **Term:** 12 months, auto-expires; revocable any time
- **Signing flow (no paid e-sign vendor needed):** HTML form → user types legal name → checkbox attestation under E-SIGN Act 15 USC §7001 → captures timestamp + machine fingerprint (Tauri) or IP (docker) → renders to PDF (WeasyPrint) → SHA-256 hashed into immutable audit log → embedded in every outbound letter.

**Ramifications of not using one:**
- ~70% of brokers accept consumer-direct deletion letters under the user's own signature — tool generates the letter, user signs/mails it themselves. Fine.
- ~30% (Acxiom, LexisNexis, CoreLogic, Epsilon historically) require notarized authorized-agent designation. These are flagged `user-submit only` in the UI with instructions.
- **DROP submissions are always consumer-direct** — the CalPrivacy registry verifies the consumer directly, so agent designation is irrelevant for that channel.

### Compliance escalation pipeline (user-requested)

When the audit pipeline detects continued listing 60+ days after a request, `evidence/package_builder.py` assembles a PDF "non-compliance package" containing:

1. Proof of original request — timestamped letter copy + delivery receipt, or DROP submission receipt
2. Evidence of non-compliance — dated screenshot + raw HTML of user's listing on broker site
3. Statute citation — specific violation (CCPA §1798.105, Delete Act §1798.99.86 penalty schedule, state equivalent)
4. **Pre-filled** CA AG complaint form (or state equivalent) — user reviews and submits. Pre-filled is "form filling," not "legal advice" — same UPL posture as TurboTax filling a 1040.
5. Attorney referral pointers from `/legal/attorney_referral_sources.md` — links to **NACA** (National Association of Consumer Advocates plaintiff-side directory) and state bar consumer/privacy section lookups. **No specific firm endorsements** (UPL + liability hazard).

### Audit pipeline — staying out of the scraper graveyard

Read-only public search on ~5 sources (FastPeopleSearch, TruePeopleSearch, Spokeo, Whitepages, BeenVerified). Per-source adapter implements `search(name, city, state, dob_year) -> ListingResult`. Playwright with stealth, 1 req/min rate limit, residential-friendly user agent. **If a source blocks us, we log `audit_inconclusive` and continue** — the user still has their letter receipt; we never block on audit. This is fundamentally different from opt-out scraping: read-only, no auth, no form submission, CFAA-safe public-data access only.

### Stack (confirmed)

- **Python 3.12** + **uv** (dep mgmt) + **FastAPI** + **SQLModel** + **Jinja2** + **WeasyPrint** + **Playwright** + **argon2id** + **arq** (Redis-backed 60-day timers; survives restarts) + **Postmark** (better DMARC/deliverability than SendGrid for transactional)
- **Rust**: **Tauri v2** + **SvelteKit** (smaller bundle/faster cold start than React on weak laptops) reading `/registry/*.yaml` directly for offline first-paint
- **CI**: GitHub Actions — `ci-python.yml` (Ruff, pytest), `ci-rust.yml` (clippy, cargo test), `registry-validate.yml` (JSON-schema validate every broker YAML on every PR)

### Phased milestones (each independently shippable)

| Phase | Scope | Ships | Success criteria | Rough effort |
|---|---|---|---|---|
| **0 — Foundation** | Registry schema, 10 western-state brokers, letter engine, agent form, CLI only | `uv add delete-me`, PDFs to disk | Non-CA user produces 10 signed letters in <10 min | ~3 weeks |
| **1 — Service + Send** | FastAPI, SQLModel, Postmark integration, case tracking | `docker compose up` | Letter sent + delivery receipt logged | ~3 weeks |
| **2 — Audit MVP** | 5 audit sources, 60-day arq scheduler, "still listed?" report | Nightly auditor | 80%+ audit success on test personas | ~4 weeks |
| **3 — Evidence Package** | Compliance PDF builder, pre-filled CA AG form, statute citations | One-click "escalate" | Package matches CA AG submission requirements | ~3 weeks |
| **4 — Tauri Desktop** | Tauri v2 shell, embedded Python sidecar, signed builds | DMG + MSI + AppImage in Releases | Non-tech user installs without terminal | ~4 weeks |
| **5 — Eastern States** | +25 brokers, NY SHIELD, VA CDPA, CO CPA, CT CTDPA templates | Registry grows | Coverage of top-50 US brokers | ~3 weeks |
| **6 — DROP Integration** | CalPrivacy DROP submission path; aligned with 2026-08-01 enforcement | CA users submit via DROP from app | First DROP receipts logged | ~3 weeks |
| **7 — GDPR/UK** | Art. 17 erasure templates, EU broker subset | EU launch | First successful Art. 17 erasure confirmed | ~4 weeks |

### Top 5 risks & mitigations

1. **UPL (unauthorized practice of law).** Templates not advice. `LEGAL_DISCLAIMER.md` prominent. Pre-filled forms only — no recommendations to sue. No firm endorsements.
2. **PII liability.** Tauri default (PII stays on device). Docker uses argon2id-encrypted columns, master key derived from operator passphrase, never stored. `SECURITY.md` publishes the threat model day one.
3. **Abuse — weaponizing against a third party.** Attestation requires user's own legal name; proof-of-address upload (hashed, not stored); one consumer profile per install.
4. **Registry rot.** `last_verified` field on every broker; GitHub Action flags stale >180 days; `ADDING_A_BROKER.md` makes broker updates a 5-min PR.
5. **Broker retaliation / IP blocking on audit.** Audit is graceful-degrade; never blocks the user-visible result. Read-only public search only — no CAPTCHA solving, no auth bypass, stays clearly within CFAA-safe access.

### Day-one docs (in `/docs/`)

- `README.md` — what / who / 3-line install
- `INSTALL.md` — DMG / MSI / AppImage / `docker compose up` with screenshots
- `USER_GUIDE.md` — plain-English walkthrough with screenshots
- `SECURITY.md` — PII threat model, encryption-at-rest, what we never transmit
- `CONTRIBUTING.md` + `ADDING_A_BROKER.md` — copy-paste YAML template, one-command local validate
- `LEGAL_DISCLAIMER.md` — not legal advice, not a law firm, jurisdiction caveats
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1

---

## Critical files to create (Phase 0)

- `registry/schemas/broker.schema.json` — JSON Schema, gates every broker PR in CI
- `registry/brokers/{acxiom,spokeo,whitepages,beenverified,intelius,mylife,peoplefinder,radaris,fastpeoplesearch,truepeoplesearch}.yaml` — first 10 brokers
- `core-py/delete_me/registry/loader.py` — pydantic models + YAML loader
- `core-py/delete_me/letters/engine.py` — Jinja2 + WeasyPrint pipeline
- `core-py/delete_me/agent_form/generator.py` — authorized-agent form generator + audit log
- `core-py/delete_me/letters/templates/ccpa_authorized_agent.j2` — primary letter template
- `legal/authorized_agent_template.md` — the human-readable scoped designation
- `legal/statute_citations.yaml` — machine-readable statute refs
- `docs/README.md` + `docs/LEGAL_DISCLAIMER.md` — must exist before first public push
- `pyproject.toml` (uv-managed) + `.github/workflows/{ci-python.yml,registry-validate.yml}`

---

## Verification (end-to-end test of Phase 0)

1. `uv sync && uv run pytest core-py/tests/` — unit tests pass for registry loader, letter engine, agent-form generator.
2. `uv run delete-me init --name "Test User" --address "123 Main St, Portland OR 97201" --dob-year 1985` — produces a profile file (no PII transmitted anywhere).
3. `uv run delete-me letters --brokers spokeo,whitepages,intelius --output ./out/` — generates one PDF letter per broker into `./out/`. Manually inspect: each PDF embeds the authorized-agent designation, scoped language is present, broker-specific PII fields are populated correctly.
4. `uv run delete-me validate-registry` — JSON-schema validates all 10 broker YAML files; CI workflow `registry-validate.yml` runs the same check on PRs.
5. Open each generated PDF, confirm it would be acceptable to a reasonable broker compliance team (legal name signed, scope clear, statute cited, revocation mechanism present).
6. Create a deliberately broken `registry/brokers/badbroker.yaml`, push to a branch, confirm `registry-validate.yml` GitHub Action fails the PR with a clear error pointing to the schema violation. This proves the 5-minute non-coder broker-add workflow gates correctly.

Phase 0 is complete and shippable when all six steps pass on a fresh clone.
