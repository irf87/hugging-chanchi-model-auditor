"""Code grader for eval-chanchi-item-authoring / new-hook."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HOOK_FILE_RE = re.compile(r"^hooks/(hook-chanchi-[a-z0-9]+(?:-[a-z0-9]+)*)/.+$")


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


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    files = git_files(work)

    hook_dirs = sorted({m.group(1) for rel in files if (m := HOOK_FILE_RE.match(rel))})
    other_hook_files = [rel for rel in files if rel.startswith("hooks/") and not HOOK_FILE_RE.match(rel)]
    emit(
        "hook_created",
        len(hook_dirs) == 1 and not other_hook_files,
        f"found {len(hook_dirs)} hook folder(s): {hook_dirs}, invalid={other_hook_files}",
    )

    githooks_dir = work / ".githooks"
    githooks = (
        sorted(str(p.relative_to(work)) for p in githooks_dir.rglob("*") if p.is_file() or p.is_symlink())
        if githooks_dir.is_dir()
        else []
    )
    git_hooks_dir = work / ".git" / "hooks"
    git_internal_hooks = (
        sorted(
            str(p.relative_to(work))
            for p in git_hooks_dir.rglob("*")
            if (p.is_file() or p.is_symlink()) and not p.name.endswith(".sample")
        )
        if git_hooks_dir.is_dir()
        else []
    )
    git_hooks_found = githooks + git_internal_hooks
    emit(
        "no_git_hooks",
        not git_hooks_found,
        f"git hook files found: {git_hooks_found}",
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
