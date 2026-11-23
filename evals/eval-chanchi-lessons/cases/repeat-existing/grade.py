"""Grader for eval-chanchi-lessons/repeat-existing."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def emit(criterion: str, passed: bool, detail: str) -> None:
    print(json.dumps({"criterion": criterion, "pass": passed, "detail": detail}))


def export_lessons(workdir: Path) -> list[dict] | None:
    proc = subprocess.run(
        [
            "chanchi",
            "lesson",
            "export",
            "--all",
            "--status",
            "pending,approved,rejected,postponed,duplicate",
            "--limit",
            "100",
        ],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout).get("lessons", [])
    except json.JSONDecodeError:
        return None


def main() -> int:
    workdir = Path(sys.argv[1])
    lessons = export_lessons(workdir)
    if lessons is None:
        for cid in ("no_new_lesson", "two_occurrences"):
            emit(cid, False, "chanchi lesson export failed or returned invalid JSON")
        return 0

    no_new = len(lessons) == 1 and lessons[0].get("id") == 1
    emit("no_new_lesson", no_new, f"lesson count={len(lessons)}")

    occ = lessons[0].get("occurrences") if lessons else None
    emit("two_occurrences", occ == 2, f"lesson #1 occurrences={occ!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
