#!/usr/bin/env bash
# Idempotently installs the delete-me git hooks. Run this once after cloning.
#
# Why: tests do NOT run in GitHub Actions for this repo, to keep the CI
# footprint light. The pre-push hook is the gate. Bypassing it with
# `git push --no-verify` is allowed for maintainers only.

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
hooks_dir="$repo_root/.git/hooks"

mkdir -p "$hooks_dir"

cat > "$hooks_dir/pre-push" <<'HOOK'
#!/usr/bin/env bash
# delete-me pre-push hook: runs lint, tests, and registry validation.
# Edit scripts/install-hooks.sh and re-run it to update.
set -euo pipefail

echo "[pre-push] ruff..."
uv run ruff check

echo "[pre-push] pytest..."
uv run pytest -q

echo "[pre-push] validate-registry..."
uv run delete-me validate-registry

echo "[pre-push] all checks passed."
HOOK

chmod +x "$hooks_dir/pre-push"
echo "Installed pre-push hook at $hooks_dir/pre-push"
