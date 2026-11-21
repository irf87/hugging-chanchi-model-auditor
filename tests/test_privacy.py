"""Committed files must not leak private details (AGENTS.md § Working Conventions).

Two rules: no home path of a real user, and no name of a reference project (the local
symlinks under external-references). Both apply to the content of tracked files, to
their paths and to the targets of tracked symlinks. The reference rule needs that
directory: it is looked up in the checkout and, for a git worktree, in the main
checkout; where neither has it (CI) the rule is skipped. The home-path rule always runs.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REFS = "external-references"
MIN_SEGMENT = 5
FIX = "describe it generically (a consumer project); see AGENTS.md"

# /Users/<name> or /home/<name>, with or without a trailing slash.
HOME_PATH = re.compile(
    r"/(?:Users|home)/(?P<name>[^/\s<>`'\"*,;:)\]]+)(?:/|(?=$|[\s'\"`,;:)\]]))"
)


def _git(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", *args], cwd=ROOT, env=env, check=True, capture_output=True
    ).stdout.decode()


def _tracked_files():
    return [p for p in _git("ls-files", "-z").split("\0") if p]


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


def _is_placeholder(name):
    return (
        not name.strip(".")
        or name.startswith("$")
        or (name.startswith("{") and name.endswith("}"))
    )


def _home_path(text):
    for match in HOME_PATH.finditer(text):
        if not _is_placeholder(match.group("name")):
            return match.group(0)
    return None


def _references_dir():
    """The reference projects directory: this checkout's, else the main checkout's."""
    here = ROOT / REFS
    if here.exists():
        return here
    common = Path(
        _git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    )
    main = common.parent / REFS
    return main if main.exists() else None


def _reference_patterns():
    """Return [(label, compiled regex)] for every non-hidden reference project."""
    refs = _references_dir()
    if refs is None:
        return []
    found = {}
    for entry in refs.iterdir():
        name = entry.name.lower()
        if name.startswith("."):
            continue
        runs = [r for r in re.split(r"[^a-z0-9]+", name) if r]
        if not runs:
            continue
        found[name] = "[-_ ]?".join(re.escape(r) for r in runs)
        first = re.sub(r"[^a-z0-9]", "", re.split(r"[-_]", name)[0])
        if len(first) >= MIN_SEGMENT:
            found.setdefault(first, re.escape(first))
    return [
        (label, re.compile(r"(?<![a-z0-9])" + body))
        for label, body in sorted(found.items())
    ]


def _symlink_target(rel):
    path = ROOT / rel
    return os.readlink(path) if path.is_symlink() else None


def test_no_tracked_path_is_the_references_directory():
    bad = [p for p in _tracked_files() if p == REFS or p.startswith(REFS + "/")]
    assert not bad, f"{REFS} must never be committed: {bad}"


def test_no_home_paths_in_tracked_files():
    hits = []
    for rel in _tracked_files():
        found = _home_path("/" + rel)
        if found:
            hits.append(f"{rel}: home path in the file name {found!r}")
        target = _symlink_target(rel)
        found = target and _home_path(target)
        if found:
            hits.append(f"{rel}: home path in the symlink target {found!r}")
        for number, line in _lines(rel):
            found = _home_path(line)
            if found:
                hits.append(f"{rel}:{number}: home path {found!r}")
    assert not hits, (
        f"Home paths are private. Fix: write ~/... and {FIX}.\n" + "\n".join(hits)
    )


def test_no_reference_project_names_in_tracked_files():
    patterns = _reference_patterns()
    if not patterns:
        pytest.skip(f"{REFS} is absent (CI)")
    hits = []
    for rel in _tracked_files():
        where = {"the file name": rel, "the symlink target": _symlink_target(rel)}
        for what, text in where.items():
            for label, pattern in patterns:
                if text and pattern.search(text.lower()):
                    hits.append(f"{rel}: reference token {label!r} in {what}")
        for number, line in _lines(rel):
            lowered = line.lower()
            for label, pattern in patterns:
                if pattern.search(lowered):
                    hits.append(f"{rel}:{number}: reference token {label!r}")
    assert not hits, f"Reference project names are private. Fix: {FIX}.\n" + "\n".join(
        hits
    )
