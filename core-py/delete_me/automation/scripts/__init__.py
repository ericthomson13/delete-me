"""Per-broker submission scripts.

One Python module per broker that has an `automation.tier` of `auto` or
`semi`. Each module exports a top-level `submit(profile, *, broker_id,
dry_run=False)` callable returning a `SubmissionResult`.

Brokers without automation (or with tier=manual) don't need a script;
the dispatcher handles them by returning `status="needs_human"`.
"""
