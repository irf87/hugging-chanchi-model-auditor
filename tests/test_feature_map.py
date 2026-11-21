"""Check 3: every CLI command is in FEATURE_MAP.md and every covering test exists."""

import argparse
import re
from pathlib import Path

from chanchi import cli

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "FEATURE_MAP.md"
COVERED = re.compile(r"^Covered by: (.+)$", re.MULTILINE)


def _subparsers(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def commands() -> list[str]:
    found = []
    for group, sub in _subparsers(cli.build_parser()).items():
        leaves = _subparsers(sub)
        found += [f"{group} {name}" for name in leaves] if leaves else [group]
    return sorted(found)


def test_every_command_has_an_entry():
    text = MAP.read_text(encoding="utf-8")
    missing = [c for c in commands() if f"`{c}`" not in text]
    assert not missing, (
        f"FEATURE_MAP.md has no entry for {missing}. Add each under its group's Sub-features, "
        "with how to reach it, how to drive it, the evidence and the covering tests."
    )


def test_covering_tests_exist():
    text = MAP.read_text(encoding="utf-8")
    entries = COVERED.findall(text)
    assert entries, "FEATURE_MAP.md lists no `Covered by:` lines"
    missing = [f for line in entries for f in (s.strip() for s in line.split(",")) if not (ROOT / f).is_file()]
    assert not missing, f"FEATURE_MAP.md names test files that do not exist: {missing}"
