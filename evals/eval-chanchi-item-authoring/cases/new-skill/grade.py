"""Code grader for eval-chanchi-item-authoring / new-skill."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_PATH_RE = re.compile(r"^skills/(skill-chanchi-([a-z0-9]+(?:-[a-z0-9]+)*))/SKILL\.md$")


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


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {}
    block = text[4:].split("\n---\n", 1)[0]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            fields[key.strip()] = value.strip()
    return fields


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    files = git_files(work)
    new_skills: list[tuple[str, str, str]] = []
    for rel in files:
        m = SKILL_PATH_RE.match(rel)
        if m and m.group(1) != "skill-chanchi-base":
            new_skills.append((rel, m.group(1), m.group(2)))

    emit(
        "skill_created",
        len(new_skills) == 1,
        f"found {len(new_skills)} new skill(s): {[s[1] for s in new_skills]}",
    )

    if len(new_skills) != 1:
        emit("frontmatter_name_matches_dir", False, "no single new skill to inspect")
        emit("within_line_budget", False, "no single new skill to inspect")
        emit("eval_dir_with_case", False, "no single new skill to inspect")
    else:
        rel, dir_name, suffix = new_skills[0]
        text = (work / rel).read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        emit(
            "frontmatter_name_matches_dir",
            fm.get("name") == dir_name and bool(fm.get("description")),
            f"name={fm.get('name')!r}, expected={dir_name!r}, has_description={bool(fm.get('description'))}",
        )
        lines = len(text.splitlines())
        emit("within_line_budget", lines <= 300, f"{rel} has {lines} lines (limit 300)")

        eval_prefix = f"evals/eval-chanchi-{suffix}/"
        has_toml = f"{eval_prefix}eval.toml" in files
        case_files: dict[str, set[str]] = {}
        for f in files:
            if f.startswith(f"{eval_prefix}cases/"):
                parts = f.split("/")
                if len(parts) == 5:
                    case_files.setdefault(parts[3], set()).add(parts[4])
        valid_cases = [c for c, fs in case_files.items() if {"prompt.md", "setup.sh", "grade.py"} <= fs]
        emit(
            "eval_dir_with_case",
            has_toml and len(valid_cases) >= 1,
            f"eval.toml={has_toml}, valid_cases={valid_cases}",
        )

    proc = subprocess.run(["python3", "tests/check_items.py"], cwd=work, capture_output=True, text=True)
    emit(
        "naming_check_passes",
        proc.returncode == 0,
        f"exit={proc.returncode} {(proc.stderr or proc.stdout).strip()}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
