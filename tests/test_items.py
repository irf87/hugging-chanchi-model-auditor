"""Check 1: item names and references (docs/designs/chanchi-agents-mvp.md, Items and naming)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ITEM_DIRS = {"agents": "agent", "skills": "skill", "evals": "eval", "hooks": "hook"}
ITEM_FILE = {"agent": "AGENT.md", "skill": "SKILL.md"}
NAME = re.compile(r"^(agent|skill|eval|hook)-chanchi-[a-z0-9]+(-[a-z0-9]+)*$")
REFERENCE = re.compile(r"\b(?:agent|skill|eval|hook)-chanchi-[a-z0-9]+(?:-[a-z0-9]+)*")
OPERATIONAL = ["AGENTS.md", "CLAUDE.md", "README.md", "FEATURE_MAP.md", "agents", "skills", "evals", "hooks"]


def items():
    for folder, kind in ITEM_DIRS.items():
        base = ROOT / folder
        if base.is_dir():
            for entry in sorted(p for p in base.iterdir() if p.is_dir()):
                yield kind, entry


def existing_names():
    return {entry.name for _, entry in items()}


def frontmatter_name(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    for line in text.split("---\n", 2)[1].splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "name":
            return value.strip()
    return None


@pytest.mark.parametrize("kind,entry", list(items()), ids=lambda v: getattr(v, "name", v))
def test_item_name(kind, entry):
    assert NAME.match(entry.name) and entry.name.startswith(f"{kind}-chanchi-"), (
        f"{entry.relative_to(ROOT)}: items in {entry.parent.name}/ are named {kind}-chanchi-<name> "
        "(kebab-case). Rename the directory and every reference to it."
    )
    if kind in ITEM_FILE:
        manifest = entry / ITEM_FILE[kind]
        assert manifest.is_file(), f"{entry.relative_to(ROOT)} has no {ITEM_FILE[kind]}"
        assert frontmatter_name(manifest) == entry.name, (
            f"{manifest.relative_to(ROOT)}: frontmatter name must equal the directory name {entry.name!r}"
        )


def operational_files():
    for item in OPERATIONAL:
        path = ROOT / item
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(p for p in path.rglob("*") if p.is_file() and p.suffix in {".md", ".toml"})


def test_references_resolve():
    known = existing_names()
    dangling = [
        f"{path.relative_to(ROOT)}: {ref}"
        for path in operational_files()
        for ref in sorted(set(REFERENCE.findall(path.read_text(encoding="utf-8"))))
        if ref not in known
    ]
    assert not dangling, (
        f"references to items that do not exist: {dangling}. Fix the name, create the item, "
        "or move planned names to docs/ (excluded from this check)."
    )
