"""Grader for eval-chanchi-lessons/nothing-wrong."""

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
        emit("no_lesson", False, "chanchi lesson export failed or returned invalid JSON")
        return 0

    emit("no_lesson", len(lessons) == 0, f"lesson count={len(lessons)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
