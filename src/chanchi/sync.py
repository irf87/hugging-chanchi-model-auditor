"""Locating SYNC (the user's synchronized folder) and the auditor roster (phase 1 of global items).

`sync init` and `sync status` belong to phase 2. Design: docs/designs/global-items.md, "Locating SYNC"
and "Roster, families and fallback".
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path

from chanchi import harnesses, projects, taxonomy
from chanchi.errors import ChanchiError

BUILTIN_ROSTER: list[dict] = [
    {"harness": "claude", "model": "sonnet", "effort": "medium"},
    {"harness": "agy", "model": "gemini-4-neon-high", "effort": "high"},
    {"harness": "opencode", "model": "opencode-go/minimax-m3", "effort": None},
    {"harness": "agy", "model": "gemini-4-hydrogen-high", "effort": "high"},
]

_ENTRY_KEYS = {"harness", "model", "effort"}


def _chanchi_checkout() -> Path | None:
    """The root of the checkout that holds chanchi's source, or None when not installed from one."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "src" / "chanchi" / "sync.py").is_file() else None


def sync_dir(env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> Path | None:
    """`CHANCHI_SYNC`, else `<main checkout>/SYNC`; None when it does not resolve to a directory."""
    env = os.environ if env is None else env
    explicit = env.get("CHANCHI_SYNC")
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_dir() else None
    root = repo_root if repo_root is not None else _chanchi_checkout()
    if root is None:
        return None
    main = projects.main_worktree(root)
    if main is None:
        return None
    path = main / "SYNC"
    return path if path.is_dir() else None


def _bad(path: Path, detail: str, **kwargs) -> ChanchiError:
    return ChanchiError("invalid_value", f"{path}: {detail}", field="auditors", **kwargs)


def _entry(path: Path, index: int, raw: object) -> dict:
    where = f"[[auditor]] entry {index}"
    if not isinstance(raw, dict):
        raise _bad(path, f"{where} must be a table")
    unknown = sorted(set(raw) - _ENTRY_KEYS)
    if unknown:
        raise _bad(path, f"{where} has unknown keys {unknown}", valid_values=sorted(_ENTRY_KEYS))
    harness = raw.get("harness")
    if harness not in harnesses.KEYS:
        raise _bad(path, f"{where} has harness {harness!r}", valid_values=harnesses.KEYS)
    model = raw.get("model")
    if not isinstance(model, str) or not model.strip():
        raise _bad(path, f"{where} needs a non-empty string model")
    effort = raw.get("effort")
    if effort is not None and effort not in taxonomy.LAUNCH_EFFORTS:
        raise _bad(path, f"{where} has effort {effort!r}", valid_values=taxonomy.LAUNCH_EFFORTS)
    return {"harness": harness, "model": model.strip(), "effort": effort}


def roster(env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> list[dict]:
    """Auditors in order of preference: `SYNC/config/auditors.toml` when present, else the built-in list."""
    base = sync_dir(env, repo_root=repo_root)
    path = base / "config" / "auditors.toml" if base is not None else None
    if path is None or not path.is_file():
        return [dict(entry) for entry in BUILTIN_ROSTER]
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
        raise _bad(path, f"cannot read the roster: {exc}", hint="fix the file or remove it to use the built-in roster") from None
    entries = data.get("auditor")
    if not isinstance(entries, list) or not entries:
        raise _bad(path, "needs at least one [[auditor]] table", hint="or remove the file to use the built-in roster")
    return [_entry(path, index, raw) for index, raw in enumerate(entries, 1)]
