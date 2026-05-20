# delete-me desktop (Tauri v2)

Phase 4 of the [project roadmap](../docs/architecture/PHASES.md). Wraps the
existing FastAPI service as an embedded sidecar so non-technical users can
install via DMG / MSI / AppImage with no terminal.

> **Status: vertical slice.** One screen (case list) is wired end-to-end.
> Remaining work: rest of the UI, code-signing, release CI. See
> "Remaining work" below.

## Layout

```
tauri-app/
├── src-tauri/          Rust shell (Tauri v2)
│   ├── src/lib.rs      Spawns the sidecar and exposes `get_api_base`
│   ├── tauri.conf.json
│   ├── capabilities/   Tauri v2 permissions
│   └── binaries/       PyInstaller output lands here (gitignored)
└── ui/                 SvelteKit (Svelte 5, adapter-static)
    └── src/routes/+page.svelte   Case list
```

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

## Remaining work for Phase 4

- [ ] Build out screens for profiles, brokers, audits, evidence (currently only case list)
- [ ] App icons in `src-tauri/icons/` (PNG / ICO / ICNS)
- [ ] macOS code signing + notarization (Apple Developer ID)
- [ ] Windows code signing (EV cert)
- [ ] Linux AppImage signing
- [ ] CI workflow that runs `build-sidecar.sh` per OS and uploads release artifacts
- [ ] Sidecar healthcheck (currently we only wait for the stdout signal; on crash mid-session we don't recover)
- [ ] First-run experience: prompt for an argon2id passphrase to derive the SQLite encryption key
