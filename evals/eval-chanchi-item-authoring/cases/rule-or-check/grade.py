"""Code grader for eval-chanchi-item-authoring / rule-or-check."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def emit(criterion: str, passed: bool, detail: str) -> None:
    print(json.dumps({"criterion": criterion, "pass": passed, "detail": detail}))


def git_status_lines(work: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=work,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    status_lines = git_status_lines(work)
    tests_changed = [line for line in status_lines if " tests/" in line or line[3:].startswith("tests/")]
    emit(
        "tests_changed",
        bool(tests_changed),
        f"changes under tests/: {tests_changed}",
    )

    diff_proc = subprocess.run(
        ["git", "diff", "-U0", "HEAD", "--", "AGENTS.md"],
        cwd=work,
        capture_output=True,
        text=True,
        check=True,
    )
    added_lines = [
        line[1:]
        for line in diff_proc.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++ ")
    ]
    emit(
        "no_line_added_to_agents_md",
        not added_lines,
        f"added lines in AGENTS.md: {added_lines}",
    )

    check_proc = subprocess.run(["python3", "tests/check_items.py"], cwd=work, capture_output=True, text=True)
    emit(
        "naming_check_passes",
        check_proc.returncode == 0,
        f"exit={check_proc.returncode} {(check_proc.stderr or check_proc.stdout).strip()}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
