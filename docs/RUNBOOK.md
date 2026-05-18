# Runbook — startup, test, and run

This is the operator's guide. If you just want to use the tool, see
[`USER_GUIDE.md`](USER_GUIDE.md). This document is for someone who is
maintaining or developing `delete-me`.

## 1. Startup — get a working dev environment

### Once per machine

```sh
brew install uv python@3.12    # macOS; on Linux see INSTALL.md
git clone https://github.com/extra-terrestrial-designs/delete-me
cd delete-me
```

### Once per clone

```sh
uv sync --extra dev --extra service
bash scripts/install-hooks.sh    # installs pre-push: ruff + pytest + validate-registry
```

The pre-push hook is the test gate — CI only runs the broker schema
validator (intentional, to keep the GitHub Actions footprint light).
**Don't push with `--no-verify`** unless a maintainer explicitly says to.

### Confirm

```sh
uv run delete-me --help
uv run pytest -q                 # 29 passing as of MVP (Phase 3 shipped)
uv run ruff check                # clean
uv run delete-me validate-registry
```

## 2. Test — what to run before pushing

### Fast loop (every save)

```sh
uv run pytest -q
```

### Full local check (pre-push hook will do this automatically)

```sh
uv run ruff check
uv run pytest -q
uv run delete-me validate-registry
```

### CLI smoke test

```sh
# A throwaway DB and profile in /tmp:
export DELETE_ME_DB_URL="sqlite:////tmp/delete-me-smoke.sqlite3"
rm -f /tmp/delete-me-smoke.sqlite3

uv run delete-me db-init
uv run delete-me init --name "Test User" --address "123 Main St, Portland OR 97201"
uv run delete-me case-create --broker spokeo
uv run delete-me cases
uv run delete-me send --case 1            # dry-run
uv run delete-me cases                    # should show status=sent_dry_run

# Audit (will likely be inconclusive — no Spokeo adapter wired in production):
uv run delete-me audit --case 1
uv run delete-me cases                    # status updates per audit verdict

# If audit comes back noncompliant, build the evidence package:
uv run delete-me evidence --case 1 --out /tmp/evidence
ls /tmp/evidence/case-1
unset DELETE_ME_DB_URL
```

### Service smoke test (no Docker)

```sh
uv run uvicorn service.app:app --reload --port 8080
# in another terminal:
curl http://localhost:8080/health
curl -X POST http://localhost:8080/profiles \
    -H "content-type: application/json" \
    -d '{"full_legal_name":"Test User","current_address":"123 Main St"}'
curl -X POST http://localhost:8080/cases \
    -H "content-type: application/json" \
    -d '{"profile_id":1,"broker_id":"spokeo"}'
curl -X POST http://localhost:8080/cases/1/send \
    -H "content-type: application/json" \
    -d '{"live":false}'
```

### docker-compose smoke test

```sh
cp docker/.env.example docker/.env
# edit docker/.env: set POSTGRES_PASSWORD
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d --build
# first build: 1-3 minutes
docker compose -f docker/docker-compose.yml --env-file docker/.env logs -f service &
docker compose -f docker/docker-compose.yml --env-file docker/.env logs -f scheduler &
curl http://localhost:8080/health
# Drive the full flow:
curl -X POST http://localhost:8080/profiles -H "content-type: application/json" \
    -d '{"full_legal_name":"Test","current_address":"123 Main St, Portland, OR"}'
curl -X POST http://localhost:8080/cases -H "content-type: application/json" \
    -d '{"profile_id":1,"broker_id":"spokeo"}'
curl -X POST http://localhost:8080/cases/1/send -H "content-type: application/json" -d '{"live":false}'
curl -X POST http://localhost:8080/cases/1/audit
curl -X POST http://localhost:8080/cases/1/evidence
curl -OJ http://localhost:8080/cases/1/evidence/download
# tear down when done:
docker compose -f docker/docker-compose.yml --env-file docker/.env down
# add -v to wipe the Postgres volume:
docker compose -f docker/docker-compose.yml --env-file docker/.env down -v
```

## 3. Run — operating a self-host instance

### Day-one bring-up

1. Choose a host. Anything that runs Docker. 512 MB RAM is plenty for one
   user; budget 1 GB for headroom.
2. Reverse-proxy `localhost:8080` behind TLS (Caddy, nginx, Traefik). The
   service does NOT terminate TLS itself.
3. Set `DELETE_ME_CORS_ORIGINS` in `docker/.env` to your origin(s).
4. Verify a sending domain in [Postmark](https://account.postmarkapp.com)
   *before* setting `POSTMARK_SERVER_TOKEN`. Bad DMARC is the fastest way
   to get your sends ignored.

### Going live (real Postmark sends)

1. Edit `docker/.env`: set `POSTMARK_SERVER_TOKEN` and
   `DELETE_ME_FROM_ADDRESS` to a verified address.
2. Restart: `docker compose ... up -d`.
3. Each send still requires `{"live": true}`. There is no global switch.

### Backups

The data lives in the `delete-me-pg` named volume. Back it up like any
Postgres deployment:

```sh
docker exec -t docker-db-1 pg_dump -U delete_me delete_me \
    | gzip > delete-me-backup-$(date +%F).sql.gz
```

Restore with `psql -U delete_me -d delete_me < backup.sql`.

### Upgrades

```sh
git pull
docker compose -f docker/docker-compose.yml --env-file docker/.env up -d --build
```

Phase 1 does not migrate the schema automatically — additive changes only
land via SQLModel's `metadata.create_all()`. Once we ship a Phase 2 schema
change that needs migration, this runbook will gain an `alembic upgrade`
step.

### Where do logs go?

```sh
docker compose -f docker/docker-compose.yml --env-file docker/.env logs -f service
docker compose -f docker/docker-compose.yml --env-file docker/.env logs -f db
```

Set `DELETE_ME_LOG_LEVEL=DEBUG` in `.env` for more detail.

### How do I know a "send" actually worked?

```sh
curl http://localhost:8080/cases/1
# status: sent_dry_run | sent | failed
# transport_message_id: present on success
# last_error: present on failure
```

For real sends, also check Postmark's dashboard for delivery state and
bounces.

## 4. Common operations cheatsheet

| Task | Command |
|---|---|
| Reset local CLI DB | `rm ~/Library/Application\ Support/delete-me/delete-me.sqlite3` (macOS) |
| Wipe docker DB | `docker compose ... down -v` (destructive) |
| Open API docs | `open http://localhost:8080/docs` |
| Tail service logs | `docker compose ... logs -f service` |
| Run a single test | `uv run pytest core-py/tests/test_letter_engine.py -k agent -v` |
| Re-validate registry | `uv run delete-me validate-registry` |
| Rebuild Docker image | `docker compose ... build --no-cache service` |

## 5. When something is wrong

- **Tests pass but `delete-me` errors at runtime.** Usually a stale DB
  schema. `rm` the SQLite file (CLI) or `down -v` (docker), then re-run
  `db-init` / restart.
- **Postmark returns 401.** Token wrong or revoked. Generate a new server
  token in Postmark and update `docker/.env`.
- **Letters look broken.** Open the Jinja2 template at
  `core-py/delete_me/letters/templates/ccpa_authorized_agent.j2`. Test
  with `uv run delete-me letters --brokers spokeo --output /tmp/out`.
- **CI keeps failing on the broker validator.** Run it locally:
  `uv run delete-me validate-registry` — the error points to the field.
