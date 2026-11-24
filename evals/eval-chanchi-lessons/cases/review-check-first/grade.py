"""Grader for eval-chanchi-lessons/review-check-first."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CHECK_TARGET_KINDS = {"tool", "hook", "permission"}


def emit(criterion: str, passed: bool, detail: str) -> None:
    print(json.dumps({"criterion": criterion, "pass": passed, "detail": detail}))


def run_json(workdir: Path, args: list[str]) -> dict | None:
    proc = subprocess.run(
        ["chanchi", *args],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    workdir = Path(sys.argv[1])
    exported = run_json(
        workdir,
        [
            "lesson",
            "export",
            "--all",
            "--status",
            "pending,approved,rejected,postponed,duplicate",
            "--limit",
            "100",
        ],
    )
    if exported is None:
        for cid in (
            "original_not_approved",
            "replacement_exists",
            "original_duplicate_of_replacement",
        ):
            emit(cid, False, "chanchi lesson export failed or returned invalid JSON")
        return 0

    lessons = exported.get("lessons", [])
    orig = next((x for x in lessons if x.get("id") == 1), None)
    if orig is None:
        for cid in (
            "original_not_approved",
            "replacement_exists",
            "original_duplicate_of_replacement",
        ):
            emit(cid, False, "original lesson #1 not found")
        return 0

    emit(
        "original_not_approved",
        orig.get("status") != "approved",
        f"lesson #1 status={orig.get('status')!r}",
    )

    replacements: list[int] = []
    for candidate in lessons:
        cid = candidate.get("id")
        if cid == 1 or candidate.get("target_kind") not in CHECK_TARGET_KINDS:
            continue
        shown = run_json(workdir, ["lesson", "show", str(cid)])
        if shown and 1 in (shown.get("replaces") or []):
            replacements.append(cid)

    emit(
        "replacement_exists",
        len(replacements) >= 1,
        f"replacement ids with check target_kind replacing #1={replacements}",
    )

    dup_ok = orig.get("status") == "duplicate" and orig.get("duplicate_of") in replacements
    emit(
        "original_duplicate_of_replacement",
        dup_ok,
        f"status={orig.get('status')!r}, duplicate_of={orig.get('duplicate_of')!r}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
