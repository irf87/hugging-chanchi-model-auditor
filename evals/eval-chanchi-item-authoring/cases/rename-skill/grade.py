"""Code grader for eval-chanchi-item-authoring / rename-skill."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

OLD_NAME = "skill-chanchi-release-notes"
NEW_NAME = "skill-chanchi-changelog"
OPERATIONAL_ROOTS = (
    "AGENTS.md",
    "README.md",
    "agents/",
    "skills/",
    "evals/",
    "hooks/",
    ".claude/agents/",
    ".opencode/agents/",
    ".agents/agents/",
)


def emit(criterion: str, passed: bool, detail: str) -> None:
    print(json.dumps({"criterion": criterion, "pass": passed, "detail": detail}))


def git_files(work: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=work,
        capture_output=True,
        check=True,
    )
    return [p for p in proc.stdout.decode("utf-8").split("\0") if p]


def frontmatter_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return None
    for line in text[4:].split("\n---\n", 1)[0].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "name":
            return value.strip()
    return None


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    files = git_files(work)

    new_skill = f"skills/{NEW_NAME}/SKILL.md"
    new_exists = new_skill in files and (work / new_skill).is_file()
    new_fm_ok = new_exists and frontmatter_name(work / new_skill) == NEW_NAME
    old_left = [f for f in files if f.startswith(f"skills/{OLD_NAME}/") and (work / f).exists()]
    emit(
        "new_skill_exists",
        new_fm_ok and not old_left,
        f"new_exists={new_exists}, frontmatter_ok={new_fm_ok}, old_remaining={old_left}",
    )

    hits: list[str] = []
    for rel in files:
        if not (rel in {"AGENTS.md", "README.md"} or rel.startswith(OPERATIONAL_ROOTS[2:])):
            continue
        path = work / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if OLD_NAME in text:
            hits.append(rel)
    emit(
        "no_old_name_in_operational_files",
        not hits,
        f"operational files still naming {OLD_NAME}: {hits}",
    )

    check_proc = subprocess.run(["python3", "tests/check_items.py"], cwd=work, capture_output=True, text=True)
    emit(
        "naming_check_passes",
        check_proc.returncode == 0,
        f"exit={check_proc.returncode} {(check_proc.stderr or check_proc.stdout).strip()}",
    )

    sync_proc = subprocess.run(
        ["chanchi", "agents", "sync", "--check"], cwd=work, capture_output=True, text=True
    )
    emit(
        "agents_sync_check",
        sync_proc.returncode == 0,
        f"exit={sync_proc.returncode} {(sync_proc.stderr or sync_proc.stdout).strip()}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
