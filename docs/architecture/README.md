# Architecture docs

This directory is the source of truth for the project's scope, phases, and
risk posture. The toplevel `docs/README.md` links here; new contributors
should read these documents in order:

1. [`PLAN.md`](PLAN.md) — the full implementation plan that was approved
   when the repo was scaffolded. Covers context, recommended approach,
   architecture diagram, broker registry schema, authorized-agent form,
   compliance escalation pipeline, audit pipeline, stack, and Phase 0
   verification.
2. [`RESEARCH.md`](RESEARCH.md) — the landscape research that decided
   *why* `delete-me` is letter-based + audit instead of yet another
   per-broker scraper. Important context for any "should we add
   automated form-submission?" PR.
3. [`PHASES.md`](PHASES.md) — phased milestone table with success
   criteria. Each phase is independently shippable.
4. [`RISKS.md`](RISKS.md) — top 5 risks and concrete mitigations. Every
   feature PR should be auditable against this list.

These documents are intentionally version-controlled with the code so that
the architecture, the reasoning, and the implementation evolve together. If
you make a change that contradicts what's here, update the doc in the same
PR.
