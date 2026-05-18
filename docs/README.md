# delete-me

> Open-source CCPA / state-DSAR / GDPR deletion-letter generator + sender
> with California-DROP compliance auditing for data brokers. AGPL-3.0.

`delete-me` helps a person remove themselves from US (and eventually EU/UK)
data brokers by doing the two things existing open-source tools have not
sustained:

1. **Generate the letters.** Produce a signed, scoped CCPA-style
   authorized-agent designation plus per-broker deletion letters, ready to
   mail or email. ~80% of the value of a $200/yr commercial service.
2. **Verify the result.** After ~60 days, check whether the broker actually
   deleted you. If not, assemble a non-compliance evidence package you can
   take to the California AG, a state regulator, or a plaintiff-side
   privacy attorney.

What it does **not** do: try to scrape and submit broker opt-out forms.
That approach is a graveyard — see
[`architecture/RESEARCH.md`](architecture/RESEARCH.md) for why.

## Current state

| Phase | Status | Ships |
|---|---|---|
| 0 — Foundation (registry, letter engine, agent form, CLI) | **shipped** | `uv run delete-me` |
| 1 — Service + Send (FastAPI, SQLModel, Postmark, docker) | **shipped** | `docker compose up` |
| 2 — Audit MVP (5 sources, 60-day scheduler) | roadmap | |
| 3 — Evidence Package | roadmap | |
| 4 — Tauri Desktop | roadmap | |
| 5+ — Eastern States, DROP, GDPR | roadmap | |

Full roadmap: [`architecture/PHASES.md`](architecture/PHASES.md).

## Quickstart — 60 seconds

**CLI on your laptop:**

```sh
git clone https://github.com/extra-terrestrial-designs/delete-me
cd delete-me
uv sync

uv run delete-me init \
    --name "Your Full Legal Name" \
    --address "123 Main St, City, State ZIP" \
    --dob-year 1985

uv run delete-me db-init
uv run delete-me case-create --broker spokeo
uv run delete-me send --case 1     # dry-run by default
```

**docker-compose self-host:**

```sh
cp docker/.env.example docker/.env  # set POSTGRES_PASSWORD
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d --build
curl http://localhost:8080/health
open http://localhost:8080/docs
```

Full walkthrough: [`USER_GUIDE.md`](USER_GUIDE.md).
Install details: [`INSTALL.md`](INSTALL.md).
Runbook (testing & operating): [`RUNBOOK.md`](RUNBOOK.md).

## Architecture

Read these in order:

- [`architecture/PLAN.md`](architecture/PLAN.md) — full implementation plan
- [`architecture/RESEARCH.md`](architecture/RESEARCH.md) — why letter-based + audit, not scraping
- [`architecture/PHASES.md`](architecture/PHASES.md) — milestones
- [`architecture/RISKS.md`](architecture/RISKS.md) — risk register

## Contributing

The broker registry is the most leverage-able artifact in the project.
Adding a new broker is one YAML file and CI validates the schema for you.
See [`ADDING_A_BROKER.md`](ADDING_A_BROKER.md).

For code contributions, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

AGPL-3.0-or-later. See [`LICENSE`](../LICENSE).

## Legal disclaimer

This is not legal advice. See [`LEGAL_DISCLAIMER.md`](LEGAL_DISCLAIMER.md).
