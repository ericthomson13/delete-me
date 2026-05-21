# Roadmap

The trackable counterpart to [`architecture/PHASES.md`](architecture/PHASES.md).
`PHASES.md` is the *narrative* doc — what shipped, why, and what's next in
prose. This is the *trackable* doc — each open item is a GitHub issue you
can close when it lands.

## Active phases

### Phase 4 — Tauri desktop

- [ ] [#1](https://github.com/ericthomson13/delete-me/issues/1) — Build out UI screens beyond case list (profiles / brokers / audits / evidence)
- [ ] [#2](https://github.com/ericthomson13/delete-me/issues/2) — Replace placeholder icons with real product artwork
- [ ] [#3](https://github.com/ericthomson13/delete-me/issues/3) — First-run argon2id passphrase / SQLite encryption

### Phase 5 — Eastern states / top-50 broker coverage

- [ ] [#4](https://github.com/ericthomson13/delete-me/issues/4) — Add 15 more brokers toward top-50 coverage
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

1. **Phase 6** ([#6](https://github.com/ericthomson13/delete-me/issues/6) then [#7](https://github.com/ericthomson13/delete-me/issues/7)) — date-driven, blocks live submissions.
2. **Phase 5** ([#4](https://github.com/ericthomson13/delete-me/issues/4), [#5](https://github.com/ericthomson13/delete-me/issues/5) in parallel) — easy-PR path, no architectural risk.
3. **Phase 4** ([#1](https://github.com/ericthomson13/delete-me/issues/1), [#2](https://github.com/ericthomson13/delete-me/issues/2), [#3](https://github.com/ericthomson13/delete-me/issues/3)) — largest scope, can land incrementally without blocking shipping.

## Shipped phases

See [`architecture/PHASES.md`](architecture/PHASES.md) — Phases 0–3 are
✅ shipped (foundation, service + send, audit MVP, evidence package).
