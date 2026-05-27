"""Post-process audit-adapter-health JSON into GitHub issues.

Called by `.github/workflows/audit-adapter-health.yml` after
`delete-me audit-adapter-health --json` runs. For each row:

- `status == "healthy"`: nothing to do.
- `status != "healthy"`: ensure an open GitHub issue exists titled
  `[audit-adapter] <source_id> regressed`. Idempotent via `gh issue
  list --search`; re-runs don't dupe. Labels `audit-adapter-broken`
  (label is created idempotently before issue creation).

Runs in the workflow with `GH_TOKEN` set; uses the `gh` CLI.

Usage:
    python audit_adapter_health_followup.py <path-to-audit-health.json>
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

LABEL = "audit-adapter-broken"


def ensure_label() -> None:
    """Create the label if it doesn't exist. Idempotent."""
    existing = subprocess.run(
        ["gh", "label", "list", "--limit", "200", "--json", "name", "-q", ".[].name"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    if LABEL in existing:
        return
    subprocess.run(
        ["gh", "label", "create", LABEL,
         "--color", "d73a4a",
         "--description", "An audit adapter's weekly health check failed"],
        check=True,
    )


def open_issue_if_missing(source_id: str, row: dict, today: str) -> None:
    title = f"[audit-adapter] {source_id} regressed"
    existing = subprocess.run(
        ["gh", "issue", "list",
         "--state", "open",
         "--search", f'in:title "{title}"',
         "--json", "number,title"],
        capture_output=True, text=True, check=True,
    )
    matches = [
        i for i in json.loads(existing.stdout)
        if i["title"] == title
    ]
    if matches:
        print(f"existing issue #{matches[0]['number']} for {source_id}, skipping")
        return

    body = (
        f"**Status**: `{row['status']}`\n"
        f"**Notes**: {row.get('notes') or '(none)'}\n"
        f"**Listings URL**: {row.get('listings_url') or '(none)'}\n\n"
        f"Detected by the weekly `audit-adapter-health` workflow on {today}.\n\n"
        "Possible causes (by status):\n"
        "- `blocked` — anti-bot tightened (Cloudflare/PerimeterX/etc.) or "
        "the site returned 4xx/5xx for our request shape.\n"
        "- `false_positive` — our card-class regex now matches non-result "
        "HTML; the adapter's CARD_CLASS_PATTERN or name-match heuristic "
        "needs tightening.\n"
        "- `error` — adapter raised; likely httpx config or a parsing bug.\n\n"
        "This issue was opened automatically. Re-runs of the workflow won't "
        "dupe it; close it when the adapter is fixed."
    )
    subprocess.run(
        ["gh", "issue", "create",
         "--title", title,
         "--body", body,
         "--label", LABEL],
        check=True,
    )
    print(f"opened issue for {source_id}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: audit_adapter_health_followup.py <path-to-audit-health.json>", file=sys.stderr)
        return 2

    data = json.loads(Path(argv[1]).read_text())
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rows = data.get("rows", [])
    if not rows:
        print("no rows to process")
        return 0

    failures = [r for r in rows if r["status"] != "healthy"]
    if failures:
        ensure_label()
        for r in failures:
            open_issue_if_missing(r["source_id"], r, today)

    print(
        f"\nsummary: {len(rows)} adapter(s) total, "
        f"{len(failures)} regression(s) (issues ensured), "
        f"{len(rows) - len(failures)} healthy"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
