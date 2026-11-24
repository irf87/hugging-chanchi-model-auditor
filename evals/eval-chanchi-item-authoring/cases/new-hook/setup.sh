#!/usr/bin/env bash
set -euo pipefail

mkdir -p agents/agent-chanchi-reader skills/skill-chanchi-base evals tests

cat > AGENTS.md <<'EOF'
# Project Rules

Items use `<item>-chanchi-<name>` (kebab-case) and match their directory name.
Verify naming and wrappers before handing off:
- `python3 tests/check_items.py`
- `chanchi agents sync --check`
EOF

cat > README.md <<'EOF'
# Sample Repository

Starter items:
- `agent-chanchi-reader`
- `skill-chanchi-base`
EOF

cat > agents/agent-chanchi-reader/AGENT.md <<'EOF'
---
name: agent-chanchi-reader
description: Reads files and summarizes findings without editing anything.
scope: both
profile: read-only
skills: [skill-chanchi-base]
---

# Reader

Read the requested files and report what you find.
EOF

cat > skills/skill-chanchi-base/SKILL.md <<'EOF'
---
name: skill-chanchi-base
description: Baseline repository conventions for starter workflows.
---

# Base Conventions

Follow repository rules and keep outputs concise.
EOF

printf "id\tdate\titem\titem_sha\thypothesis\tchange\tarm\tcandidate\truns\tmedian_pass\tbefore\tafter\tdelta\tverdict\tnote\n" > evals/ledger.tsv

cat > tests/check_items.py <<'EOF'
"""Standard-library item naming and reference check."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ITEM_DIRS = {"agents": "agent", "skills": "skill", "evals": "eval", "hooks": "hook"}
ITEM_FILE = {"agent": "AGENT.md", "skill": "SKILL.md"}
NAME = re.compile(r"^(agent|skill|eval|hook)-chanchi-[a-z0-9]+(-[a-z0-9]+)*$")
REFERENCE = re.compile(r"\b(?:agent|skill|eval|hook)-chanchi-[a-z0-9]+(?:-[a-z0-9]+)*")


def frontmatter_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    for line in text.split("---\n", 2)[1].splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "name":
            return value.strip()
    return None


def skip_eval_file(path: Path, evals_root: Path) -> bool:
    rel = path.relative_to(evals_root)
    return len(rel.parts) >= 2 and (rel.parts[1] == "cases" or rel.parts[1] == "triggers.md")


def main() -> int:
    errors: list[str] = []
    known: set[str] = set()
    for folder, kind in ITEM_DIRS.items():
        base = ROOT / folder
        if not base.is_dir():
            continue
        for entry in sorted(p for p in base.iterdir() if p.is_dir()):
            if not NAME.match(entry.name) or not entry.name.startswith(f"{kind}-chanchi-"):
                errors.append(
                    f"{entry.relative_to(ROOT)}: directory must be named {kind}-chanchi-<name> (kebab-case). "
                    f"Rename the directory and update references."
                )
                continue
            known.add(entry.name)
            if kind in ITEM_FILE:
                manifest = entry / ITEM_FILE[kind]
                if not manifest.is_file():
                    errors.append(f"{entry.relative_to(ROOT)}: missing {ITEM_FILE[kind]}. Create it.")
                elif frontmatter_name(manifest) != entry.name:
                    errors.append(
                        f"{manifest.relative_to(ROOT)}: frontmatter name must equal directory {entry.name!r}."
                    )

    op_files: list[Path] = []
    for name in ("AGENTS.md", "README.md"):
        p = ROOT / name
        if p.is_file():
            op_files.append(p)
    for folder in ITEM_DIRS:
        base = ROOT / folder
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in {".md", ".toml"}:
                if folder == "evals" and skip_eval_file(p, base):
                    continue
                op_files.append(p)

    for path in op_files:
        text = path.read_text(encoding="utf-8")
        for ref in sorted(set(REFERENCE.findall(text))):
            if ref not in known:
                errors.append(
                    f"{path.relative_to(ROOT)}: references missing item {ref!r}. Fix the name or create the item."
                )

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
EOF

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"
chanchi agents sync > /dev/null
python3 tests/check_items.py > /dev/null
git add .
git commit -q -m "Initial repository"
