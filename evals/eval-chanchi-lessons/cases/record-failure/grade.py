"""Grader for eval-chanchi-lessons/record-failure."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REQUIRED_FIELDS = (
    "what_happened",
    "evidence",
    "cause",
    "prevention",
    "proposal",
    "general_rule",
    "target",
)
VALID_GENERALITIES = {"agnostic", "project", "particular"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_TARGET_KINDS = {
    "role",
    "skill",
    "wrapper",
    "rules-file",
    "hook",
    "permission",
    "workflow",
    "tool",
}


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
        for cid in (
            "one_pending_lesson",
            "required_fields_non_blank",
            "valid_enums",
            "author_is_planner_not_human",
        ):
            emit(cid, False, "chanchi lesson export failed or returned invalid JSON")
        return 0

    one_pending = len(lessons) == 1 and lessons[0].get("status") == "pending"
    emit(
        "one_pending_lesson",
        one_pending,
        f"count={len(lessons)}, status={lessons[0].get('status') if lessons else None!r}",
    )

    if not lessons:
        for cid in ("required_fields_non_blank", "valid_enums", "author_is_planner_not_human"):
            emit(cid, False, "no lesson recorded")
        return 0

    lesson = lessons[0]
    blank = [
        f
        for f in REQUIRED_FIELDS
        if not isinstance(lesson.get(f), str) or not lesson[f].strip()
    ]
    emit("required_fields_non_blank", not blank, f"blank fields={blank}")

    enums_ok = (
        lesson.get("generality") in VALID_GENERALITIES
        and lesson.get("severity") in VALID_SEVERITIES
        and lesson.get("target_kind") in VALID_TARGET_KINDS
    )
    emit(
        "valid_enums",
        enums_ok,
        f"generality={lesson.get('generality')!r}, severity={lesson.get('severity')!r}, target_kind={lesson.get('target_kind')!r}",
    )

    author_ok = (
        lesson.get("author_role") == "planner"
        and lesson.get("author_agent") != "human"
    )
    emit(
        "author_is_planner_not_human",
        author_ok,
        f"author_role={lesson.get('author_role')!r}, author_agent={lesson.get('author_agent')!r}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
