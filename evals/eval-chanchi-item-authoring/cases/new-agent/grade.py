"""Code grader for eval-chanchi-item-authoring / new-agent."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

AGENT_PATH_RE = re.compile(r"^agents/(agent-chanchi-[a-z0-9]+(?:-[a-z0-9]+)*)/AGENT\.md$")
MODEL_NAME_RE = re.compile(
    r"\b(?:sonnet|opus|haiku|gemini-[a-z0-9.-]+|gpt-[a-z0-9.-]+|claude-[a-z0-9.-]+|minimax-[a-z0-9.-]+)\b",
    re.IGNORECASE,
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
    new_agents: list[tuple[str, str]] = []
    for rel in files:
        m = AGENT_PATH_RE.match(rel)
        if m and m.group(1) != "agent-chanchi-reader":
            new_agents.append((rel, m.group(1)))

    emit(
        "agent_created",
        len(new_agents) == 1,
        f"found {len(new_agents)} new agent(s): {[a[1] for a in new_agents]}",
    )

    if len(new_agents) != 1:
        emit("frontmatter_valid", False, "no single new agent to inspect")
    else:
        rel, dir_name = new_agents[0]
        text = (work / rel).read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        skills_val = fm.get("skills", "")
        has_skills_list = skills_val.startswith("[") and skills_val.endswith("]")
        model_hit = MODEL_NAME_RE.search(text)
        valid = (
            fm.get("name") == dir_name
            and bool(fm.get("description"))
            and fm.get("scope") in {"main", "subagent", "both"}
            and fm.get("profile") == "read-only"
            and has_skills_list
            and "model" not in fm
            and model_hit is None
        )
        emit(
            "frontmatter_valid",
            valid,
            f"fields={sorted(fm.keys())}, name={fm.get('name')!r}, scope={fm.get('scope')!r}, "
            f"profile={fm.get('profile')!r}, model_hit={model_hit.group(0) if model_hit else None}",
        )

    sync_proc = subprocess.run(
        ["chanchi", "agents", "sync", "--check"], cwd=work, capture_output=True, text=True
    )
    emit(
        "agents_sync_check",
        sync_proc.returncode == 0,
        f"exit={sync_proc.returncode} {(sync_proc.stderr or sync_proc.stdout).strip()}",
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
