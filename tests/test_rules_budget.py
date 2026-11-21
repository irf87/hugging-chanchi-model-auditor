"""Check 7: rules files stay short enough to be read (docs/designs/chanchi-agents-mvp.md)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUDGETS = {"AGENTS.md": 150, "skills/*/SKILL.md": 300, "agents/*/AGENT.md": 300}
FILES = [(path, limit) for pattern, limit in BUDGETS.items() for path in sorted(ROOT.glob(pattern))]


@pytest.mark.parametrize("path,limit", FILES, ids=[str(p.relative_to(ROOT)) for p, _ in FILES])
def test_rules_file_within_budget(path, limit):
    lines = len(path.read_text(encoding="utf-8").splitlines())
    assert lines <= limit, (
        f"{path.relative_to(ROOT)} has {lines} lines (budget {limit}). "
        "Move detail into docs/ or the item's references/ folder and link to it."
    )
