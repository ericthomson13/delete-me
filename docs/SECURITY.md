# Security & PII threat model

`delete-me` exists because data brokers leak personal information. It would
be deeply embarrassing if the tool itself became a leak. This document is
the threat model and the commitments we make to the user.

## What data the tool handles

The PII captured by `delete-me init`:

- Full legal name
- Current address (one line)
- Optional: email, phone, year of birth, prior addresses, former names

The tool does **not** ask for, and the registry does not require, a full
date of birth, SSN, government ID, or financial information. If a future
broker entry requires one of those fields, the registry schema is
restrictive enough that adding it requires a deliberate change.

## What the tool does with that data

| Phase | Where PII lives | Network egress |
|---|---|---|
| 0 — CLI (today) | `profile.json` in your current directory | None. The CLI never talks to the network. |
| 1 — docker self-host | Postgres on your machine, argon2id-encrypted columns | Outbound email to brokers via Postmark; no PII sent to delete-me's authors. |
| 4 — Tauri desktop | SQLite inside the app's local data directory | Same as docker. PII never leaves the device. |

In Phases 1+ the master encryption key is derived from a passphrase the
operator supplies, using argon2id. The passphrase is never persisted. If
you lose it, the data is unrecoverable — that's by design.

## What the tool will never do

- Phone home with usage telemetry containing PII.
- Send your PII to anyone other than the broker(s) you select.
- Upload your `profile.json` or any derived data to a delete-me-controlled
  server. (There is no such server.)
- Embed analytics, ad pixels, or third-party trackers in any UI surface.

## Reporting a vulnerability

Email **eric.thomson13@gmail.com** with `[delete-me security]` in the
subject. Please do not file public GitHub issues for security problems.

We aim to acknowledge reports within 5 business days. There is no bounty
program — the project is unfunded.

## Threats explicitly out of scope

- Endpoint compromise — if your machine is already compromised, encrypting
  the local DB doesn't help. Use disk encryption.
- Postmark account compromise — outbound mail credentials live in your own
  Postmark account in Phase 1+. Use a dedicated, scoped API key.
- Broker malfeasance — if a broker decides to keep your data anyway, the
  audit pipeline catches it, but the tool can't *prevent* it.

## Crypto / hashing choices

- Document hashes: SHA-256
- At-rest encryption key derivation: argon2id (Phase 1+)
- Audit identifiers: `secrets.token_hex(8)` — non-secret, just a local UUID

If you spot a use of MD5, SHA-1, raw PBKDF2, or "rolled my own crypto",
that's a bug — file an issue.
