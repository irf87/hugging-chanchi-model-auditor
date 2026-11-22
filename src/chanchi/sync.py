"""Locating, initializing and inspecting SYNC (the user's synchronized folder) and the auditor roster.

Design: docs/designs/global-items.md, "Locating SYNC" and "Roster, families and fallback".
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
SYNC_SUBFOLDERS = ("config", "ITEMS/agents", "ITEMS/skills")
RECOMMENDATION_TEMPLATE = (
    "Point {target} at a folder a cloud service synchronizes "
    "(Google Drive, iCloud Drive, Dropbox) or at a clone of a private git repository."
)


def _chanchi_checkout() -> Path | None:
    """The root of the checkout that holds chanchi's source, or None when not installed from one."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "src" / "chanchi" / "sync.py").is_file() else None


def sync_path(env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> Path | None:
    """Where `SYNC` is or would be (`CHANCHI_SYNC`, else `<main checkout>/SYNC`), never resolved."""
    env = os.environ if env is None else env
    explicit = (env.get("CHANCHI_SYNC") or "").strip()
    if explicit:
        return Path(os.path.abspath(Path(explicit).expanduser()))
    root = repo_root if repo_root is not None else _chanchi_checkout()
    if root is None:
        return None
    main = projects.main_worktree(root)
    if main is None:
        return None
    return main / "SYNC"


def sync_dir(env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> Path | None:
    """`CHANCHI_SYNC`, else `<main checkout>/SYNC`; None when it does not resolve to a directory."""
    path = sync_path(env, repo_root=repo_root)
    return path if path is not None and path.is_dir() else None


def require(env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> Path:
    """The unresolved `SYNC` directory, or `missing_prerequisite` with hint `chanchi sync init`."""
    path = sync_path(env, repo_root=repo_root)
    if path is None or not path.is_dir():
        raise ChanchiError(
            "missing_prerequisite",
            "SYNC is not initialized",
            field="sync",
            hint="chanchi sync init",
        )
    return path


def _ensure_subfolders(root: Path) -> list[str]:
    created: list[str] = []
    for rel in SYNC_SUBFOLDERS:
        sub = root / rel
        if os.path.lexists(sub) and not sub.is_dir():
            raise ChanchiError(
                "link_conflict",
                f"expected directory at {sub}, found non-directory",
                field="sync",
                hint="chanchi sync status",
            )
        if not sub.is_dir():
            sub.mkdir(parents=True, exist_ok=True)
            created.append(rel)
    return created


def init(
    env: Mapping[str, str] | None = None,
    *,
    repo_root: Path | None = None,
    link: Path | None = None,
) -> dict:
    """Initialize SYNC/config and SYNC/ITEMS, optionally symlinking SYNC to `link`."""
    if link is not None and not str(link).strip():
        raise ChanchiError("invalid_value", "link directory must not be empty", field="link")
    path = sync_path(env, repo_root=repo_root)
    if path is None:
        raise ChanchiError(
            "missing_prerequisite",
            "cannot locate SYNC outside a chanchi checkout",
            field="sync",
            hint="set CHANCHI_SYNC=<dir>",
        )
    if link is not None:
        if os.path.lexists(path):
            raise ChanchiError(
                "link_conflict",
                f"SYNC already exists at {path}",
                field="sync",
                hint="chanchi sync status",
            )
        target = Path(os.path.abspath(Path(link).expanduser()))
        if target == path:
            raise ChanchiError(
                "invalid_value",
                f"link target {target} cannot be SYNC itself",
                field="link",
            )
        if os.path.lexists(target) and not target.is_dir():
            raise ChanchiError(
                "invalid_value",
                f"link target {target} exists and is not a directory",
                field="link",
                hint="pass a directory path (existing or to be created)",
            )
        if not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        created = _ensure_subfolders(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target, target_is_directory=True)
        return {
            "path": str(path),
            "created": created,
            "link": str(target),
            "recommendation": RECOMMENDATION_TEMPLATE.format(target=target),
        }
    if path.is_symlink() and not path.exists():
        raise ChanchiError(
            "missing_prerequisite",
            f"SYNC symlink at {path} is dangling",
            field="sync",
            hint="chanchi sync status",
        )
    if os.path.lexists(path) and not path.is_dir():
        raise ChanchiError(
            "link_conflict",
            f"SYNC path {path} exists and is not a directory",
            field="sync",
            hint="chanchi sync status",
        )
    if not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
    created = _ensure_subfolders(path)
    return {"path": str(path), "created": created, "link": None}


def status(env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> dict:
    """Report SYNC location, symlink target, reachability and subfolders without creating anything."""
    path = sync_path(env, repo_root=repo_root)
    if path is None:
        return {
            "path": None,
            "exists": False,
            "is_link": False,
            "target": None,
            "reachable": False,
            "config": False,
            "items": False,
        }
    exists = os.path.lexists(path)
    is_link = path.is_symlink()
    target = os.readlink(path) if is_link else None
    reachable = path.is_dir()
    return {
        "path": str(path),
        "exists": exists,
        "is_link": is_link,
        "target": target,
        "reachable": reachable,
        "config": reachable and (path / "config").is_dir(),
        "items": reachable and (path / "ITEMS").is_dir(),
    }


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


PROMOTION_DEFAULTS = {"min_uses": 3, "vendored_share": 0.5}


def _promotion_bad(path: Path, detail: str) -> ChanchiError:
    return ChanchiError(
        "invalid_value",
        f"{path}: {detail}",
        field="promotion",
        hint="fix the file or remove it to use the defaults (min_uses = 3, vendored_share = 0.5)",
    )


def promotion(env: Mapping[str, str] | None = None, *, repo_root: Path | None = None) -> dict:
    """`{min_uses, vendored_share}` from `SYNC/config/promotion.toml`; defaults when SYNC or the file is missing.

    `min_uses` is an integer of at least 1 (default 3); `vendored_share` is a number in (0, 1] (default 0.5;
    `1` is accepted). A boolean is never a number. Any other key, type, out-of-range value or a TOML error is
    `invalid_value` with field `promotion`.
    """
    result = dict(PROMOTION_DEFAULTS)
    base = sync_dir(env, repo_root=repo_root)
    path = base / "config" / "promotion.toml" if base is not None else None
    if path is None or not path.is_file():
        return result
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
        raise _promotion_bad(path, f"cannot read promotion.toml: {exc}") from None
    unknown = sorted(set(data) - set(PROMOTION_DEFAULTS))
    if unknown:
        raise _promotion_bad(path, f"promotion.toml has unknown keys {unknown}; valid keys are {sorted(PROMOTION_DEFAULTS)}")
    if "min_uses" in data:
        value = data["min_uses"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise _promotion_bad(path, f"promotion.toml: min_uses must be an integer of at least 1, got {value!r}")
        result["min_uses"] = value
    if "vendored_share" in data:
        value = data["vendored_share"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
            raise _promotion_bad(
                path, f"promotion.toml: vendored_share must be a number above 0 and at most 1, got {value!r}"
            )
        result["vendored_share"] = float(value)
    return result
