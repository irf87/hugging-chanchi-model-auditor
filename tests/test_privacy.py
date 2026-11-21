"""Committed files must not leak private details (AGENTS.md § Working Conventions).

Two rules: no home path of a real user, and no name of a reference project (the local
symlinks under external-references/). The reference rule only runs where that directory
exists, so it is skipped in CI; the home-path rule always runs.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s<>`'\"*]+/")
MIN_SEGMENT = 5
FIX = "describe it generically (a consumer project); see AGENTS.md"


def _tracked_files():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    ).stdout
    return [p for p in out.decode().split("\0") if p]


def _lines(rel):
    """Yield (number, line) for a tracked UTF-8 text file; nothing for binaries."""
    path = ROOT / rel
    if not path.is_file():  # deleted in the working tree, or a symlink target gone
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    yield from enumerate(text.splitlines(), 1)


def _reference_tokens():
    refs = ROOT / "external-references"
    if not refs.exists():
        return []
    tokens = set()
    for entry in refs.iterdir():
        name = entry.name.lower()
        squashed = re.sub(r"[^a-z0-9]", "", name)
        if squashed:
            tokens.add(squashed)
        first = name.split("-")[0]
        if len(first) >= MIN_SEGMENT:
            tokens.add(re.sub(r"[^a-z0-9]", "", first))
    return sorted(tokens)


def test_no_home_paths_in_tracked_files():
    hits = []
    for rel in _tracked_files():
        for number, line in _lines(rel):
            match = HOME_PATH.search(line)
            if match:
                hits.append(f"{rel}:{number}: home path {match.group(0)!r}")
    assert not hits, (
        f"Home paths are private. Fix: write ~/... and {FIX}.\n" + "\n".join(hits)
    )


def test_no_reference_project_names_in_tracked_files():
    tokens = _reference_tokens()
    if not tokens:
        pytest.skip("external-references/ is absent (CI)")
    patterns = [(t, re.compile(r"(?<![a-z0-9])" + re.escape(t))) for t in tokens]
    hits = []
    for rel in _tracked_files():
        for number, line in _lines(rel):
            lowered = line.lower()
            for token, pattern in patterns:
                if pattern.search(lowered):
                    hits.append(f"{rel}:{number}: reference token {token!r}")
    assert not hits, f"Reference project names are private. Fix: {FIX}.\n" + "\n".join(
        hits
    )
