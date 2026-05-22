"""Post-process automation-health JSON into GitHub-side side effects.

Called by `.github/workflows/automation-health.yml` after `delete-me
automation-health --json` runs. For each row:

- `status == "submitted"`: bump `automation.last_automation_pass` in
  the broker YAML to today's UTC date. The workflow batches all date
  bumps into a single bot commit.
- `status != "submitted"`: ensure an open GitHub issue exists titled
  `[automation] <broker_id> script broken`. Idempotent via `gh issue
  list --search`; re-runs don't dupe. Labels `automation-broken`
  (label is created idempotently before issue creation).

Runs in the workflow with `GH_TOKEN` set; uses the `gh` CLI for issue
work and direct file IO for YAML date bumps. YAML bumps use a regex
that preserves comments and formatting (round-tripping via PyYAML
would alphabetize keys and lose comments).

Usage:
    python automation_health_followup.py <path-to-health.json>
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BROKERS_DIR = REPO_ROOT / "registry" / "brokers"
LABEL = "automation-broken"


def ensure_label() -> None:
    """Create the automation-broken label if it doesn't exist. Idempotent."""
    existing = subprocess.run(
        ["gh", "label", "list", "--limit", "200", "--json", "name", "-q", ".[].name"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    if LABEL in existing:
        return
    subprocess.run(
        ["gh", "label", "create", LABEL,
         "--color", "d73a4a",
         "--description", "An automation script's dry-run failed in the weekly health check"],
        check=True,
    )


def open_issue_if_missing(broker_id: str, row: dict, today: str) -> None:
    title = f"[automation] {broker_id} script broken"
    existing = subprocess.run(
        ["gh", "issue", "list",
         "--state", "open",
         "--search", f'in:title "{title}"',
         "--json", "number,title"],
        capture_output=True, text=True, check=True,
    )
    matches = [
        i for i in json.loads(existing.stdout)
        if i["title"] == title  # gh search is fuzzy; require exact-title match
    ]
    if matches:
        print(f"existing issue #{matches[0]['number']} for {broker_id}, skipping")
        return

    body = (
        f"**Status**: `{row['status']}`\n"
        f"**Tier**: `{row['tier']}`\n"
        f"**Fallback reason**: {row['fallback_reason'] or '(none)'}\n\n"
        f"Detected by the weekly `automation-health` workflow on {today}.\n\n"
        "Screenshot, if any, is uploaded as a workflow artifact "
        "(`automation-screenshots/<broker_id>.png`).\n\n"
        "This issue was opened automatically. Re-runs of the workflow won't "
        "dupe it; close it when the script is fixed."
    )
    subprocess.run(
        ["gh", "issue", "create",
         "--title", title,
         "--body", body,
         "--label", LABEL],
        check=True,
    )
    print(f"opened issue for {broker_id}")


def bump_last_pass(broker_id: str, today: str) -> bool:
    """Bump automation.last_automation_pass in the broker YAML.

    Returns True if the file was changed. Uses a regex that targets the
    last_automation_pass line (or adds one inside the automation: block
    if missing) to preserve formatting and comments.
    """
    path = BROKERS_DIR / f"{broker_id}.yaml"
    if not path.is_file():
        print(f"WARN: broker YAML not found for {broker_id}", file=sys.stderr)
        return False

    text = path.read_text()
    # Case 1: line already exists — replace the date.
    line_re = re.compile(
        r"^(\s+last_automation_pass:\s+)\S+", re.MULTILINE,
    )
    if line_re.search(text):
        if f"last_automation_pass: {today}" in text:
            return False  # already today, nothing to do
        new = line_re.sub(rf"\g<1>{today}", text, count=1)
    else:
        # Case 2: append the field at the end of the automation: block.
        block_re = re.compile(
            r"(^automation:\n(?:[ \t]+\S+:.*\n)+)", re.MULTILINE,
        )
        m = block_re.search(text)
        if not m:
            print(
                f"WARN: {broker_id} reported submitted but has no automation: "
                "block in YAML; refusing to invent one",
                file=sys.stderr,
            )
            return False
        # Indentation of existing sub-keys (assume 2 spaces, matches existing files).
        new = block_re.sub(
            lambda m: m.group(1) + f"  last_automation_pass: {today}\n",
            text, count=1,
        )

    if new == text:
        return False
    path.write_text(new)
    return True


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: automation_health_followup.py <path-to-health.json>", file=sys.stderr)
        return 2

    data = json.loads(Path(argv[1]).read_text())
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rows = data.get("rows", [])
    if not rows:
        print("no rows to process")
        return 0

    failures = [r for r in rows if r["status"] != "submitted"]
    if failures:
        ensure_label()
        for r in failures:
            open_issue_if_missing(r["broker_id"], r, today)

    bumped: list[str] = []
    for r in rows:
        if r["status"] == "submitted":
            if bump_last_pass(r["broker_id"], today):
                bumped.append(r["broker_id"])

    summary = (
        f"\nsummary: {len(rows)} script(s) total, "
        f"{len(failures)} failure(s) (issues ensured), "
        f"{len(bumped)} date(s) bumped: {', '.join(bumped) or '(none)'}"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
