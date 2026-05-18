# delete-me

> Open-source CCPA / state-DSAR / GDPR deletion-letter generator with
> California-DROP compliance auditing for data brokers. AGPL-3.0.

`delete-me` helps a person remove themselves from US (and eventually EU/UK)
data brokers by doing the two things existing open-source tools have not
sustained:

1. **Generate the letters.** Produce a signed, scoped CCPA-style
   authorized-agent designation plus per-broker deletion letters, ready to
   mail or email. ~80% of the value of a $200/yr commercial service.
2. **Verify the result.** After ~60 days, check whether the broker
   actually deleted you. If not, assemble a non-compliance evidence
   package you can take to the California AG, a state regulator, or a
   plaintiff-side privacy attorney.

What it does **not** do: try to scrape and submit broker opt-out forms.
That approach is a graveyard — see [`architecture/RESEARCH.md`](architecture/RESEARCH.md)
for why.

## Install (Phase 0 — CLI)

```sh
git clone https://github.com/extra-terrestrial-designs/delete-me
cd delete-me
uv sync                  # installs Python 3.12 deps via uv
uv run delete-me --help
```

Later phases ship a Tauri desktop app (Phase 4) and a docker-compose
self-host (Phase 1). See [`INSTALL.md`](INSTALL.md).

## Quickstart

```sh
# 1. Capture your profile locally (this file never leaves your disk).
uv run delete-me init \
    --name "Jane Q. Doe" \
    --address "123 Main St, Portland OR 97201" \
    --dob-year 1985 \
    --prior-address "456 Old Rd, Seattle WA 98101"

# 2. See what brokers are in the registry.
uv run delete-me list-brokers

# 3. Generate letters for a few brokers (markdown to ./out/).
uv run delete-me letters --brokers spokeo,whitepages,intelius --output ./out
```

Read the generated `./out/authorized_agent_designation.md` carefully. Sign,
date, and mail or email each letter per the broker's instructions.

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
