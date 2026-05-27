"""Post-process audit-adapter-health JSON into GitHub issues + YAML date bumps.

Called by `.github/workflows/audit-adapter-health.yml` after
`delete-me audit-adapter-health --json` runs. For each row:

- `status == "healthy"`: bump audit_sources_last_pass[source_id] in the
  broker's YAML to today's UTC date. The workflow batches all bumps into
  a single bot commit.
- `status != "healthy"`: ensure an open GitHub issue exists titled
  `[audit-adapter] <source_id> regressed`. Idempotent via `gh issue
  list --search`; re-runs don't dupe. Labels `audit-adapter-broken`
  (label is created idempotently before issue creation).

YAML bumps use a regex that preserves comments and formatting
(round-tripping via PyYAML would alphabetize keys and lose comments —
same pattern as automation_health_followup.py).

Runs in the workflow with `GH_TOKEN` set; uses the `gh` CLI for issue
work and direct file IO for YAML date bumps.

Usage:
    python audit_adapter_health_followup.py <path-to-audit-health.json>
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


def bump_last_pass(broker_id: str, source_id: str, today: str) -> bool:
    """Bump audit_sources_last_pass[source_id] in the broker YAML.

    Returns True if the file was changed. Uses regex (not PyYAML round-trip)
    to preserve comments and key order.

    Three cases handled:
      1. The block exists and has this source_id — replace the date.
      2. The block exists without this source_id — insert the key/value
         line, preserving the block's indentation.
      3. The block doesn't exist — create it as a sibling of audit_sources.
    """
    path = BROKERS_DIR / f"{broker_id}.yaml"
    if not path.is_file():
        print(f"WARN: broker YAML not found for {broker_id}", file=sys.stderr)
        return False

    text = path.read_text()

    # Find the audit_sources_last_pass block (if any). The block is a
    # mapping under the top-level key, so its sub-lines are indented.
    block_re = re.compile(
        r"^audit_sources_last_pass:\s*\n((?:[ \t]+\S.*\n)*)", re.MULTILINE,
    )
    block_match = block_re.search(text)

    if block_match:
        block_body = block_match.group(1)
        # Determine indent from the first sub-line.
        indent_match = re.match(r"^([ \t]+)", block_body)
        indent = indent_match.group(1) if indent_match else "  "

        # Case 1: source_id already in block — replace its date.
        key_re = re.compile(
            rf"^({re.escape(indent)}{re.escape(source_id)}:\s+)\S+",
            re.MULTILINE,
        )
        if key_re.search(block_body):
            if f"{indent}{source_id}: {today}" in block_body:
                return False  # already today
            new_block_body = key_re.sub(rf"\g<1>{today}", block_body, count=1)
        else:
            # Case 2: append source_id to existing block.
            new_block_body = block_body + f"{indent}{source_id}: {today}\n"

        new = text[: block_match.start(1)] + new_block_body + text[block_match.end(1) :]
        if new == text:
            return False
        path.write_text(new)
        return True

    # Case 3: no block — insert under audit_sources.
    sources_re = re.compile(
        r"^audit_sources:\s*\n((?:[ \t]+-\s+\S.*\n)*)",
        re.MULTILINE,
    )
    sources_match = sources_re.search(text)
    if sources_match is None:
        # The broker doesn't declare audit_sources at all; nothing to bump.
        # (Shouldn't happen — a healthy adapter implies the source is wired.)
        print(
            f"WARN: {broker_id} reported healthy for {source_id} but YAML "
            "has no audit_sources block; refusing to invent one",
            file=sys.stderr,
        )
        return False

    insertion_point = sources_match.end()
    insertion = (
        "audit_sources_last_pass:\n"
        f"  {source_id}: {today}\n"
    )
    new = text[:insertion_point] + insertion + text[insertion_point:]
    path.write_text(new)
    return True


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

    bumped: list[str] = []
    for r in rows:
        if r["status"] != "healthy":
            continue
        broker_id = r.get("broker_id")
        if not broker_id:
            print(
                f"WARN: healthy adapter {r['source_id']} has no broker_id in "
                "the health-check output; cannot bump date",
                file=sys.stderr,
            )
            continue
        if bump_last_pass(broker_id, r["source_id"], today):
            bumped.append(f"{broker_id}/{r['source_id']}")

    print(
        f"\nsummary: {len(rows)} adapter(s) total, "
        f"{len(failures)} regression(s) (issues ensured), "
        f"{len(bumped)} date(s) bumped: {', '.join(bumped) or '(none)'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
