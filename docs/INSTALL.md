# Install

`delete-me` ships in three forms. Phase 0 (today) only ships the CLI; the
other two are roadmap.

## Phase 0 — CLI (today)

### Prerequisites

- Python 3.12 or newer
- [`uv`](https://github.com/astral-sh/uv) — fast Python package manager

On macOS:
```sh
brew install uv python@3.12
```

On Ubuntu/Debian:
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
sudo apt install python3.12
```

### Install from source

```sh
git clone https://github.com/extra-terrestrial-designs/delete-me
cd delete-me
uv sync
uv run delete-me --help
```

Optional: PDF rendering needs WeasyPrint's system libraries. If you only
need markdown output, skip this step.

- macOS: `brew install pango`
- Ubuntu/Debian: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`

Then re-run `uv sync` and pass `--pdf` to `delete-me letters`.

## Phase 1 — docker-compose (roadmap)

```sh
git clone https://github.com/extra-terrestrial-designs/delete-me
cd delete-me/docker
docker compose up -d
```

Browse to `http://localhost:8080`. The web UI walks you through profile,
broker selection, and letter generation; PII is encrypted at rest with a
passphrase you supply.

## Phase 4 — Tauri desktop app (roadmap)

Download a signed installer for your OS from the
[Releases page](https://github.com/extra-terrestrial-designs/delete-me/releases):

- **macOS** — `delete-me.dmg`
- **Windows** — `delete-me.msi`
- **Linux** — `delete-me.AppImage`

In Tauri builds, your PII never leaves the device. Only signed letters and
optional outbound email (Postmark) ever touch the network.

## Verifying a release

All release binaries are signed. Verification instructions land with each
release.
