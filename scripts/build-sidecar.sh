#!/usr/bin/env bash
# Bundles the FastAPI service into a single-file binary the Tauri shell can
# spawn as an `externalBin`. Tauri resolves sidecars by the
# `<name>-<rust-target-triple>` filename convention, so this script suffixes
# the host triple automatically.
#
# Prereqs:
#   - uv (https://docs.astral.sh/uv/) with the service + audit extras installed
#   - rustc (used only to query the host triple)
#
# Usage:
#   scripts/build-sidecar.sh                # build for host triple
#   TARGET_TRIPLE=aarch64-apple-darwin ...  # cross-target override
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TARGET_TRIPLE="${TARGET_TRIPLE:-$(rustc -vV | awk '/host:/ { print $2 }')}"
OUT_DIR="tauri-app/src-tauri/binaries"
OUT_NAME="delete-me-sidecar-${TARGET_TRIPLE}"
DIST_DIR="$(mktemp -d -t delete-me-sidecar-XXXXXX)"
trap 'rm -rf "$DIST_DIR"' EXIT

echo "==> Building sidecar for $TARGET_TRIPLE"

uv run --extra service --extra dev pyinstaller \
  --noconfirm \
  --onefile \
  --name "delete-me-sidecar" \
  --distpath "$DIST_DIR/dist" \
  --workpath "$DIST_DIR/build" \
  --specpath "$DIST_DIR" \
  --paths core-py \
  --paths service \
  --collect-all delete_me \
  --collect-all service \
  --collect-data weasyprint \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.loops.asyncio \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.http.h11_impl \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  service/sidecar_entry.py

mkdir -p "$OUT_DIR"
SRC="$DIST_DIR/dist/delete-me-sidecar"
[ -f "$SRC" ] || SRC="$DIST_DIR/dist/delete-me-sidecar.exe"
DEST="$OUT_DIR/$OUT_NAME"
case "$TARGET_TRIPLE" in
  *windows*) DEST="$DEST.exe" ;;
esac
cp "$SRC" "$DEST"
chmod +x "$DEST" || true

echo "==> Wrote $DEST"
