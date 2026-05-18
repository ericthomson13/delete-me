# User Guide

This is the plain-English walkthrough. If a step sounds confusing, that's a
documentation bug — please open an issue.

There are two ways to use `delete-me`. Pick one:

- **A. CLI on your laptop** — fastest, no Docker. Generates letters as
  files; case tracking lives in a local SQLite file.
- **B. docker-compose self-host** — same features, HTTP API, Postgres-backed.
  Good if you also want to drive the tool from a script or a future UI.

Both paths produce the same outputs. **Sending is always dry-run by
default**; you have to explicitly pass `--live` to actually email a broker.

## What you'll end up with

After ~20 minutes you'll have:

- A signed **Authorized Agent Designation** — one page that says "the
  delete-me tool may submit deletion requests to data brokers on my behalf
  for the next 12 months." This is **not** a Power of Attorney.
- One **letter per broker** you selected, addressed to that broker.
- A **case record** for each broker, tracking status (`draft` → `sent_dry_run`
  → `sent` → eventually `deleted_confirmed` or `noncompliant`).
- An **audit due date** 60 days out — the date the (future) audit pipeline
  will check whether the broker actually complied.

---

## Path A — CLI on your laptop

### 1. Install

Follow [INSTALL.md → Path A](INSTALL.md#path-a--cli-only-fastest).
Confirm with:

```sh
uv run delete-me --help
```

### 2. Capture your profile

```sh
uv run delete-me init \
    --name "Your Full Legal Name" \
    --address "123 Main St, City, State ZIP" \
    --dob-year 1985 \
    --email "you@example.com" \
    --prior-address "Old street address, city, state, ZIP"
```

This writes `profile.json` in your current directory. **Nothing leaves
your machine.** You can re-run with new flags any time; the file is
overwritten.

### 3. Browse the broker registry

```sh
uv run delete-me list-brokers
```

### 4. Initialize case tracking (one-time)

```sh
uv run delete-me db-init
# DB ready at sqlite:////.../delete-me/delete-me.sqlite3
```

### 5. Create a case for one broker

```sh
uv run delete-me case-create --broker spokeo
# case #1 drafted for broker=spokeo profile_id=1
# agent designation sha256: <hex>
```

Or, generate letters for several brokers as files (no DB):

```sh
uv run delete-me letters --brokers spokeo,whitepages,intelius --output ./out
```

### 6. List cases

```sh
uv run delete-me cases
# #1    spokeo                    status=draft               sent=—
```

### 7. Dry-run send

```sh
uv run delete-me send --case 1
# … status=sent_dry_run, audit_due_at = today + 60 days
```

### 8. Live send (when ready)

Set `POSTMARK_SERVER_TOKEN` and `DELETE_ME_FROM_ADDRESS` in your shell:

```sh
export POSTMARK_SERVER_TOKEN=...    # from Postmark dashboard
export DELETE_ME_FROM_ADDRESS=delete-me-agent@your-verified-domain.example

uv run delete-me send --case 1 --live
```

You must pass `--live` per send. There is no global "always live" switch.

### 9. Audit (after ~60 days)

```sh
uv run delete-me audit --case 1
# Or sweep all cases past their audit_due_at:
uv run delete-me audit-due
```

The audit pipeline runs read-only public searches on the sources configured
for the broker. If you're still listed, the case status becomes
`noncompliant`. If you're not listed and the source returned conclusively,
status becomes `deleted_confirmed`. Anything else is `audit_inconclusive`
and the tool will re-try on the next sweep.

### 10. Build an evidence package (on noncompliance)

```sh
uv run delete-me evidence --case 1 --out ./evidence
# Produces ./evidence/case-1/ and ./evidence/case-1.zip
```

The directory contains:

- `01-original-letter.md` — the deletion letter we sent
- `02-agent-designation.md` — the scoped authorized-agent designation
- `03-send-receipt.json` — when we sent, message ID, etc.
- `04-audit-evidence/` — per-source JSON + any captured HTML/screenshots
- `05-statute-citations.md` — the statutes invoked
- `06-ca-ag-complaint-DRAFT.md` — **draft, not a submission.** Review,
  then file via the OFFICIAL form at
  https://oag.ca.gov/contact/consumer-complaint-against-business-or-company
- `07-attorney-referrals.md` — pointers to NACA and state bar lookups
- `MANIFEST.json` — index of everything in the package

Attach the zip when filing the CA AG complaint, or hand it to a
plaintiff-side privacy attorney via the directories in
`07-attorney-referrals.md`.

---

## Path B — docker-compose self-host

### 1. Install

Follow [INSTALL.md → Path B](INSTALL.md#path-b--docker-compose-self-host-phase-1-today).
Confirm with:

```sh
curl http://localhost:8080/health
```

Open the interactive API docs at http://localhost:8080/docs.

### 2. Create your profile

```sh
curl -X POST http://localhost:8080/profiles \
    -H "content-type: application/json" \
    -d '{
      "full_legal_name": "Your Full Legal Name",
      "current_address": "123 Main St, City, State ZIP",
      "dob_year": 1985,
      "email": "you@example.com",
      "prior_addresses": ["Old street address, city, state, ZIP"]
    }'
# {"id": 1, ...}
```

### 3. Browse brokers

```sh
curl http://localhost:8080/brokers
curl http://localhost:8080/brokers/spokeo
```

### 4. Draft a case

```sh
curl -X POST http://localhost:8080/cases \
    -H "content-type: application/json" \
    -d '{"profile_id": 1, "broker_id": "spokeo"}'
# returns: letter_markdown, agent_designation_markdown, case id, ...
```

### 5. Dry-run send

```sh
curl -X POST http://localhost:8080/cases/1/send \
    -H "content-type: application/json" \
    -d '{"live": false}'
# { "case": {... "status":"sent_dry_run", "audit_due_at":"..."}, "result": {"dry_run": true, ...} }
```

### 6. List cases

```sh
curl http://localhost:8080/cases
```

### 7. Live send

Set `POSTMARK_SERVER_TOKEN` and `DELETE_ME_FROM_ADDRESS` in `docker/.env`,
restart with `docker compose ... up -d`, then:

```sh
curl -X POST http://localhost:8080/cases/1/send \
    -H "content-type: application/json" \
    -d '{"live": true}'
```

### 8. Audit + evidence (HTTP)

```sh
# Run the audit pipeline immediately:
curl -X POST http://localhost:8080/cases/1/audit

# Sweep all due cases (the scheduler container does this automatically once
# per AUDIT_INTERVAL_SECONDS; this endpoint is for ad-hoc triggers):
curl -X POST 'http://localhost:8080/audits/sweep?limit=100'

# Inspect audit history for a case:
curl http://localhost:8080/cases/1/audits

# Build an evidence package (saves to DELETE_ME_EVIDENCE_DIR, default
# /var/lib/delete-me/evidence inside the container):
curl -X POST http://localhost:8080/cases/1/evidence

# Download the zip:
curl -OJ http://localhost:8080/cases/1/evidence/download
```

The docker-compose stack also runs a separate `scheduler` container that
invokes `delete-me audit-due --limit 100` on a configurable interval
(default 24h via `AUDIT_INTERVAL_SECONDS`). Inspect it with:

```sh
docker compose -f docker/docker-compose.yml --env-file docker/.env logs -f scheduler
```

---

## Review and sign

Open `authorized_agent_designation.md` (CLI) or the
`agent_designation_markdown` field (HTTP) in any text editor or markdown
viewer. **Re-read every word and confirm you are comfortable with what
you're authorizing.** The scope is deliberately narrow — only deletion and
opt-out requests, not any other authority.

## What happens after a real send?

- Most brokers must respond within 45 days under CCPA.
- In a later phase (Phase 2 — Audit MVP) the tool will automatically check
  ~60 days after your request whether you still appear in the broker's
  public people-search results. If you do, it builds an evidence package
  you can use to file a complaint with the California AG or contact an
  attorney via the directories in
  [`../legal/attorney_referral_sources.md`](../legal/attorney_referral_sources.md).

## What `delete-me` won't do

- It won't fill out broker opt-out web forms for you. See
  [`architecture/RESEARCH.md`](architecture/RESEARCH.md) for why.
- It won't give you legal advice. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md).
- It won't send your PII anywhere unless you explicitly pass `--live` (CLI)
  or `{"live": true}` (HTTP), and even then only to the broker contact in
  the registry.
