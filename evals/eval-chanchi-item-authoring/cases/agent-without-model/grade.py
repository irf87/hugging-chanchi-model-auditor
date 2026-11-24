"""Code grader for eval-chanchi-item-authoring / agent-without-model."""

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
VALID_SCOPES = {"main", "subagent", "both"}
VALID_PROFILES = {"read-only", "workspace-write", "orchestrator"}


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


def wrapper_paths(agent_name: str) -> list[str]:
    return [
        f".claude/agents/{agent_name}.md",
        f".opencode/agents/{agent_name}.md",
        f".agents/agents/{agent_name}/agent.md",
    ]


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
        emit("no_model_specified", False, "no single new agent to inspect")
    else:
        rel, dir_name = new_agents[0]
        source_text = (work / rel).read_text(encoding="utf-8")
        fm = parse_frontmatter(source_text)
        skills_val = fm.get("skills", "")
        has_skills_list = skills_val.startswith("[") and skills_val.endswith("]")
        valid = (
            fm.get("name") == dir_name
            and bool(fm.get("description"))
            and fm.get("scope") in VALID_SCOPES
            and fm.get("profile") in VALID_PROFILES
            and has_skills_list
        )
        emit(
            "frontmatter_valid",
            valid,
            f"fields={sorted(fm.keys())}, name={fm.get('name')!r}, scope={fm.get('scope')!r}, "
            f"profile={fm.get('profile')!r}, skills={skills_val!r}",
        )

        model_violations: list[str] = []
        for target_rel in [rel, *wrapper_paths(dir_name)]:
            target_path = work / target_rel
            if not target_path.is_file():
                continue
            target_text = target_path.read_text(encoding="utf-8")
            target_fm = parse_frontmatter(target_text)
            if any(k.lower() == "model" for k in target_fm):
                model_violations.append(f"{target_rel}:model_key")
            hit = MODEL_NAME_RE.search(target_text)
            if hit is not None:
                model_violations.append(f"{target_rel}:model_name={hit.group(0)}")

        emit(
            "no_model_specified",
            not model_violations,
            f"violations={model_violations}",
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
