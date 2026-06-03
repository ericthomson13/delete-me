# delete-me desktop (Tauri v2)

Phase 4 of the [project roadmap](../docs/architecture/PHASES.md). Wraps the
existing FastAPI service as an embedded sidecar so non-technical users can
install via DMG / MSI / AppImage with no terminal.

> **Status: feature-complete UI, design polish pending.** Six screens
> wired end-to-end (see "Screens" below); the open work is real product
> artwork and the first-run encryption flow.

## Layout

```
tauri-app/
├── src-tauri/          Rust shell (Tauri v2)
│   ├── src/lib.rs      Spawns the sidecar and exposes `get_api_base`
│   ├── tauri.conf.json
│   ├── capabilities/   Tauri v2 permissions
│   └── binaries/       PyInstaller output lands here (gitignored)
└── ui/                 SvelteKit (Svelte 5, adapter-static)
    └── src/routes/             Six screens, file-based routing
```

## Screens

Navigation lives in `ui/src/routes/+layout.svelte`. Every screen owns
its own state and fetches from the sidecar via `ui/src/lib/api.ts`.

| Route        | Purpose                                                                                          |
|--------------|--------------------------------------------------------------------------------------------------|
| `/`          | Case list — every deletion case with status, broker, sent date                                  |
| `/profiles`  | People CRUD — add/edit consumer profiles                                                        |
| `/brokers`   | Broker registry browser with tier + automation + DROP + agent filters                           |
| `/discovery` | Presence-check + breach-check + password-check (k-anonymity) for the selected profile; per-row "Create case" CTA on found brokers, or a link to the existing case if one exists |
| `/audits`    | Cross-case audit log with status filters and text search                                        |
| `/evidence`  | Cross-case evidence packages with on-disk indicator and direct .zip download                    |
| `/cases/[id]`| Case detail — letter, audits, automation, evidence build/download, send                         |

The FastAPI service itself still lives at `service/` in the repo root; the
sidecar entry is `service/sidecar_entry.py`.

## How the sidecar handshake works

1. Tauri's shell plugin spawns the bundled `delete-me-sidecar-<target-triple>` binary.
2. The sidecar picks a free loopback port and prints `LISTENING_ON 127.0.0.1:<port>` to stdout **before** uvicorn binds the socket.
3. The Rust shell parses that line, stores the URL in app state, and the UI retrieves it via the `get_api_base` Tauri command.
4. On exit, the Rust shell kills the child process.

The UI never talks to a fixed port — multiple installs can coexist and we never collide with whatever else is on 8000.

## Dev loop

Prereqs: `rustup` (stable), `node` (≥20), `pnpm`, `uv`, and the Tauri v2 CLI:

```sh
cargo install tauri-cli --version "^2.0" --locked
```

One-time setup:

```sh
cd tauri-app/ui && pnpm install && cd -
# install Python deps for the sidecar build
uv sync --extra service --extra dev
```

Build the sidecar (creates `tauri-app/src-tauri/binaries/delete-me-sidecar-<triple>`):

```sh
scripts/build-sidecar.sh
```

Run the app in dev mode (auto-reloads the UI, restarts the Rust shell on Rust changes):

```sh
cd tauri-app/src-tauri
cargo tauri dev
```

Production build (DMG / MSI / AppImage):

```sh
cd tauri-app/src-tauri
cargo tauri build
```

## UI-only browser mode

If you just want to iterate on Svelte without firing up Tauri, point at a manually-launched FastAPI:

```sh
# terminal 1
uvicorn service.app:app --port 8000
# terminal 2
cd tauri-app/ui && VITE_API_BASE=http://127.0.0.1:8000 pnpm dev
```

## Automated verification

Two layers cover the desktop app:

**Python integration test** — `service/service_tests/test_sidecar_entry.py`
spawns `sidecar_entry.py` as a real subprocess (the same way the Rust shell
does), reads its `LISTENING_ON 127.0.0.1:<port>` line from stdout, hits
`/health` and `/cases`, and asserts clean SIGTERM shutdown. Runs as part of
the normal `uv run pytest` suite — so it's already wired into the pre-push
hook (`scripts/install-hooks.sh`).

```sh
uv run pytest service/service_tests/test_sidecar_entry.py -v
```

**Rust unit tests** — `tauri-app/src-tauri/src/lib.rs` has `cargo test`
cases around `parse_listening_line` covering happy path, trailing newline,
malformed addresses, and non-handshake noise. Run from `tauri-app/src-tauri/`:

```sh
cargo test --lib
```

Between the two: the Python test proves the sidecar honors the contract,
the Rust test proves the shell parses it correctly. The remaining surface
(spawning, lifecycle) is straight wiring through `tauri-plugin-shell`.

## Remaining work for Phase 4

- [x] Build out screens for profiles, brokers, audits, evidence (and Discovery)
- [ ] Replace placeholder icons in `src-tauri/icons/` with real product artwork (`tauri icon` CLI generates from a single source PNG). See [`MAINTAINER_CHECKLIST.md`](../docs/MAINTAINER_CHECKLIST.md#4-design-assets).
- [ ] First-run experience: prompt for an argon2id passphrase to derive the SQLite encryption key. Decision: SQLCipher + OS keychain hybrid (research deposited).
- [x] Sidecar healthcheck + auto-restart (`src-tauri/src/lib.rs` — see `HealthState` and `spawn_health_monitor`)
- [x] Release CI workflow (`.github/workflows/release-desktop.yml` — unsigned bundles only)
- [x] Code-signing playbook (`docs/RELEASING.md` — manual maintainer step)
