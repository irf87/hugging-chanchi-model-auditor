"""Code grader for eval-chanchi-item-adoption / propose-new."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ITEM = "skill-chanchi-global-release-checklist"
VERSION = "0.1.0"
DECISION_RE = re.compile(r"\b(adopt|wrap|keep|deprecate)\b", re.IGNORECASE)
TABLE_RE = re.compile(r"(?m)^\|.+\|\s*\n\|[\s:|-]+\|\s*\n\|.+\|")


def emit(criterion: str, passed: bool, detail: str) -> None:
    print(json.dumps({"criterion": criterion, "pass": passed, "detail": detail}))


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    db_path = Path(os.environ["CHANCHI_DB"])
    sync_root = Path(os.environ["CHANCHI_SYNC"])

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT slug FROM projects ORDER BY id LIMIT 1").fetchone()
        slug = row[0] if row else "demo-app"
        decision_count = conn.execute("SELECT COUNT(*) FROM item_decisions").fetchone()[0]

    expected_proposal = sync_root / "reviews" / ITEM / VERSION / f"adoption-{slug}.md"
    reviews_root = sync_root / "reviews"
    found_proposals = (
        sorted(str(p.relative_to(reviews_root)) for p in reviews_root.rglob("*.md") if p.is_file())
        if reviews_root.is_dir()
        else []
    )
    exists = expected_proposal.is_file() and bool(expected_proposal.read_text(encoding="utf-8").strip())
    emit(
        "proposal_file_exists",
        exists and len(found_proposals) == 1,
        f"expected={expected_proposal.relative_to(sync_root)}, found={found_proposals}",
    )

    if exists:
        text = expected_proposal.read_text(encoding="utf-8")
        decisions = sorted({m.group(1).lower() for m in DECISION_RE.finditer(text)})
        emit(
            "names_valid_decision",
            bool(decisions),
            f"decision keyword(s) found: {decisions}",
        )
        has_table = TABLE_RE.search(text) is not None
        emit(
            "has_comparison_table",
            has_table,
            "comparison markdown table present" if has_table else "no markdown table found in proposal",
        )
    else:
        emit("names_valid_decision", False, "proposal file missing")
        emit("has_comparison_table", False, "proposal file missing")

    status_proc = subprocess.run(
        ["git", "status", "--porcelain"], cwd=work, capture_output=True, text=True, check=True
    )
    dirty = [line for line in status_proc.stdout.splitlines() if line.strip()]
    emit(
        "no_project_changes",
        not dirty,
        f"git status dirty entries: {dirty}",
    )

    emit(
        "no_item_decisions_row",
        decision_count == 0,
        f"item_decisions count={decision_count} (expected 0)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
