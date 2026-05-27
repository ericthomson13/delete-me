# Roadmap

The trackable counterpart to [`architecture/PHASES.md`](architecture/PHASES.md).
`PHASES.md` is the *narrative* doc — what shipped, why, and what's next in
prose. This is the *trackable* doc — each open item is a GitHub issue you
can close when it lands.

> **Blocked on you, not on code?** See
> [`MAINTAINER_CHECKLIST.md`](MAINTAINER_CHECKLIST.md) for the
> consolidated list of verification work, optional service
> credentials, developer tooling, design assets, and scheduled
> checkpoints.

## Active phases

### Phase 4 — Tauri desktop

- [x] [#1](https://github.com/ericthomson13/delete-me/issues/1) — Build out UI screens beyond case list (profiles / brokers / audits / evidence). *Profiles, brokers, discovery, audits, and evidence views all shipped (2026-05-27).*
- [ ] [#2](https://github.com/ericthomson13/delete-me/issues/2) — Replace placeholder icons with real product artwork
- [ ] [#3](https://github.com/ericthomson13/delete-me/issues/3) — First-run argon2id passphrase / SQLite encryption *(decision: SQLCipher + OS keychain hybrid, see deposited research)*

### Phase 5 — Eastern states / top-50 broker coverage

- [ ] [#4](https://github.com/ericthomson13/delete-me/issues/4) — Add 15 more brokers toward top-50 coverage. *15 draft skeletons landed in `registry/brokers_draft/` (2026-05-27); each needs browser verification via [`VERIFYING_DRAFT_BROKERS.md`](VERIFYING_DRAFT_BROKERS.md) before promotion to the active registry.*
- [ ] [#5](https://github.com/ericthomson13/delete-me/issues/5) — Browser-verify tranche-2 broker opt-out URLs

### Phase 6 — CalPrivacy DROP

- [ ] [#6](https://github.com/ericthomson13/delete-me/issues/6) — Populate `opt_out.calprivacy_id` on `drop_registered` brokers
- [ ] [#7](https://github.com/ericthomson13/delete-me/issues/7) — Wire `CALPRIVACY_DROP_ENDPOINT` default once CalPrivacy publishes

> **Scheduled checkpoint:** remote-trigger routine
> [`trig_01Fho9wU38DimJXn1sw3UhfV`](https://claude.ai/code/routines/trig_01Fho9wU38DimJXn1sw3UhfV)
> fires on `2026-08-01T15:00:00Z` (the CA Delete Act enforcement date, 9am
> America/Denver) and opens a `DROP go-live readiness check (2026-08-01)`
> issue summarising the state of #6 and #7. If either is still open then,
> live DROP submissions are still blocked.

## Suggested order

1. **Phase 5** ([#4](https://github.com/ericthomson13/delete-me/issues/4) draft promotions, [#5](https://github.com/ericthomson13/delete-me/issues/5) re-verification) — only verification work, doable in 15-30 min slices via [`VERIFYING_DRAFT_BROKERS.md`](VERIFYING_DRAFT_BROKERS.md).
2. **Phase 4 [#2](https://github.com/ericthomson13/delete-me/issues/2)** (real icons) — when design bandwidth is available.
3. **Phase 4 [#3](https://github.com/ericthomson13/delete-me/issues/3)** (encryption) — pick up when a threat model justifies the complexity; research is deposited.
4. **Phase 6** ([#6](https://github.com/ericthomson13/delete-me/issues/6), [#7](https://github.com/ericthomson13/delete-me/issues/7)) — blocked on CalPrivacy; the 2026-08-01 trigger will surface it automatically.

## Shipped phases

See [`architecture/PHASES.md`](architecture/PHASES.md) for the narrative. Status summary:

- ✅ **Phase 0** — Foundation (registry, letter engine, agent form, CLI)
- ✅ **Phase 1** — Service + Send (FastAPI, SQLModel, Postmark, docker)
- ✅ **Phase 2** — Audit MVP (orchestrator, mock + experimental real adapters, sweeper)
- ✅ **Phase 3** — Evidence package (zip with letter, audit findings, CA AG draft)
- ✅ **Phase 8** — Tiered submission-automation framework (#8) + per-broker template (#9) + weekly automation-health CI (#10) + UI integration (#11)
- ✅ **Phase 9** — Pre-send presence-check (CLI + `send --check-first` + service API + Tauri Discovery view)
- ✅ **Phase 10** — Breach-check (HIBP + IntelX + DeHashed) + free k-anonymity password-check (CLI + service API + Tauri Discovery view). Tor-proxy follow-up scoped in [`architecture/proposals/tor-proxy-for-breach-lookups.md`](architecture/proposals/tor-proxy-for-breach-lookups.md) — *not recommended for build today.*
- ✅ **Adapter rollout** — 16 of 16 declared `audit_sources` have shipped adapters via the shared `PeopleSearchAdapter` base. Weekly `audit-adapter-health` CI files regression issues and bot-commits `audit_sources_last_pass` date bumps.
