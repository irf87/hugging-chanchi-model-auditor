"""Code grader for eval-chanchi-item-adoption / retired-entry."""

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
EXPLICIT_DECISION_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:#{1,4}\s*(?:Proposed\s+)?(?:Decision|Recommendation)\s*\n+\s*"
    r"|[-*]?\s*\*{0,2}(?:Proposed\s+)?(?:Decision|Recommendation)\*{0,2}\s*:\*{0,2}\s*)"
    r"\*{0,2}`?(adopt|wrap|keep|deprecate)`?\*{0,2}\b"
)
ANY_DECISION_RE = re.compile(r"\b(adopt|wrap|keep|deprecate)\b", re.IGNORECASE)


def emit(criterion: str, passed: bool, detail: str) -> None:
    print(json.dumps({"criterion": criterion, "pass": passed, "detail": detail}))


def extract_decision(text: str) -> tuple[str | None, str]:
    match = EXPLICIT_DECISION_RE.search(text)
    if match:
        return match.group(1).lower(), f"explicit decision: {match.group(1).lower()}"
    tokens = [m.group(1).lower() for m in ANY_DECISION_RE.finditer(text)]
    if not tokens:
        return None, "no decision keyword found"
    unique = sorted(set(tokens))
    if len(unique) == 1:
        return unique[0], f"single decision keyword: {unique[0]}"
    return None, f"ambiguous decision keywords without explicit Decision header: {unique}"


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    db_path = Path(os.environ["CHANCHI_DB"])
    sync_root = Path(os.environ["CHANCHI_SYNC"])

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT slug FROM projects ORDER BY id LIMIT 1").fetchone()
        slug = row[0] if row else "demo-app"
        decision_count = conn.execute("SELECT COUNT(*) FROM item_decisions").fetchone()[0]

    expected_proposal = sync_root / "reviews" / ITEM / VERSION / f"adoption-{slug}.md"
    exists = expected_proposal.is_file() and bool(expected_proposal.read_text(encoding="utf-8").strip())
    emit(
        "proposal_file_exists",
        exists,
        f"expected={expected_proposal.relative_to(sync_root)}, exists={exists}",
    )

    if exists:
        text = expected_proposal.read_text(encoding="utf-8")
        decision, reason = extract_decision(text)
        emit(
            "decision_is_keep_or_deprecate",
            decision in {"keep", "deprecate"},
            reason,
        )
    else:
        emit("decision_is_keep_or_deprecate", False, "proposal file missing")

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
        "no_new_item_decisions_row",
        decision_count == 1,
        f"item_decisions count={decision_count} (expected 1 from setup)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
