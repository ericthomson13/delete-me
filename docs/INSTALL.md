# Install

`delete-me` ships in three forms. Phase 0–1 (today) deliver the CLI and the
docker-compose self-host. The Tauri desktop app is roadmap (Phase 4).

## Path A — CLI only (fastest)

Use this if you just want to generate letters on your own machine.

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
git clone https://github.com/ericthomson13/delete-me
cd delete-me
uv sync
bash scripts/install-hooks.sh   # installs the pre-push hook
uv run delete-me --help
```

Optional: PDF rendering needs WeasyPrint's system libraries. If you only
need markdown output, skip this step.

- macOS: `brew install pango`
- Ubuntu/Debian: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`

Then re-run `uv sync` and pass `--pdf` to `delete-me letters`.

## Path B — docker-compose self-host (Phase 1, today)

Use this if you want the HTTP API too, or you want Postgres-backed case
tracking instead of local SQLite.

### Prerequisites

- Docker 24+ and Docker Compose v2

### Bring it up

```sh
git clone https://github.com/ericthomson13/delete-me
cd delete-me

cp docker/.env.example docker/.env
# Edit docker/.env. At minimum set POSTGRES_PASSWORD to a strong random value.
# Leave POSTMARK_SERVER_TOKEN blank to keep all sends in safe dry-run mode.

docker compose -f docker/docker-compose.yml --env-file docker/.env up -d --build
```

First build takes 1–3 minutes (downloading Pango/Cairo). After that:

```sh
curl http://localhost:8080/health
# {"status":"ok","version":"0.0.1"}
```

The interactive API docs are at http://localhost:8080/docs.

### Going live (real Postmark sends)

1. Verify a sending domain in [Postmark](https://account.postmarkapp.com).
2. Set `POSTMARK_SERVER_TOKEN` and `DELETE_ME_FROM_ADDRESS` in `docker/.env`.
3. `docker compose -f docker/docker-compose.yml --env-file docker/.env up -d`
   to restart with new env.
4. Pass `{"live": true}` to `POST /cases/{id}/send` or `--live` to the CLI.

Even in "live" mode, you have to opt in per send. There is no global
"always live" switch by design.

## Path C — Tauri desktop app (Phase 4, roadmap)

Download a signed installer for your OS from the
[Releases page](https://github.com/ericthomson13/delete-me/releases):

- **macOS** — `delete-me.dmg`
- **Windows** — `delete-me.msi`
- **Linux** — `delete-me.AppImage`

In Tauri builds, your PII never leaves the device. Only signed letters and
optional outbound email (Postmark) ever touch the network.

## Environment variables

All env vars are optional. Without them, the tool stays in safe defaults
(dry-run sends, no breach lookups, local SQLite). Reference:

| Variable | Used by | Default if unset |
|---|---|---|
| `DELETE_ME_DB_URL` | CLI + service | SQLite under platformdirs (see below) |
| `POSTMARK_SERVER_TOKEN` | `send --live` | `send --live` errors; dry-run is unaffected |
| `DELETE_ME_FROM_ADDRESS` | `send --live` | `send --live` errors; dry-run is unaffected |
| `CALPRIVACY_DROP_ENDPOINT` + `CALPRIVACY_DROP_TOKEN` | `drop-submit --live` | dry-run writes the submission to disk and returns a synthetic receipt |
| `HIBP_API_KEY` | `breach-check` (HIBP provider) | HIBP skipped; setup hint shown in the breach-check footer |
| `INTELX_API_KEY` (optional `INTELX_BASE_URL`) | `breach-check` (IntelX provider) | IntelX skipped; setup hint shown |
| `DEHASHED_USERNAME` + `DEHASHED_API_KEY` | `breach-check` (DeHashed provider) | DeHashed skipped; setup hint shown |

For provider-by-provider trade-offs and signup links, see
[`USER_GUIDE.md` → Discovery](USER_GUIDE.md#6b-discovery--find-out-where-youre-exposed-optional).
`password-check` needs no env vars at all.

## Where is my data?

- CLI mode: a SQLite file under the platform's user-data dir
  (macOS: `~/Library/Application Support/delete-me/delete-me.sqlite3`,
  Linux: `~/.local/share/delete-me/...`).
  Override with `DELETE_ME_DB_URL=sqlite:///./somewhere.db`.
- docker mode: a named Postgres volume `delete-me-pg` on the docker host.
  Override with `DELETE_ME_DB_URL=postgresql+psycopg://...`.

## Verifying a release

All release binaries are signed. Verification instructions land with each
release.
