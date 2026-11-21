"""Mirror chanchi skills into projects (or ~) with symlinks. Never overwrites anything."""

from __future__ import annotations

import os
from pathlib import Path

from chanchi.errors import ChanchiError

SKILL_PREFIX = "skill-chanchi-"
LEGACY_PREFIX = "chanchi-"
COMPAT_DIRS = (Path(".agents") / "skills", Path(".claude") / "skills")
SUGGESTED_CONFIG_LINE = (
    "When assigning sessions use the `skill-chanchi-model-selection` skill; when orchestrating and "
    "auditing sessions use the `skill-chanchi-session-audit` skill; at the end of each conversation, "
    "writer roles use the `skill-chanchi-lessons` skill."
)


def repo_skills_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "skills"
    if not path.is_dir():
        raise ChanchiError(
            "internal",
            f"skills directory not found at {path}",
            hint="install chanchi from its repository with `uv tool install --editable .`",
        )
    return path


def available_skills(skills_dir: Path) -> list[str]:
    return sorted(
        entry.name
        for entry in skills_dir.iterdir()
        if entry.is_dir() and entry.name.startswith(SKILL_PREFIX) and (entry / "SKILL.md").is_file()
    )


def plan_targets(base: Path, *, global_: bool) -> tuple[Path, list[Path]]:
    """Primary dir (absolute links into the repo) and secondary dirs (relative links to primary)."""
    primary = base / ".agents" / "skills"
    secondaries = [base / ".claude" / "skills"]
    if global_ and (base / ".gemini" / "antigravity-cli").is_dir():
        secondaries.append(base / ".gemini" / "antigravity-cli" / "skills")
    return primary, secondaries


def _ensure(link_path: Path, target: Path, *, absolute: bool, created: list, existing: list, conflicts: list) -> None:
    desired = str(target) if absolute else os.path.relpath(target, link_path.parent)
    if link_path.is_symlink():
        if os.readlink(link_path) == desired or link_path.resolve() == target.resolve():
            existing.append(str(link_path))
        else:
            conflicts.append(str(link_path))
        return
    if link_path.exists():
        conflicts.append(str(link_path))
        return
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(desired)
    created.append(str(link_path))


def _points_into_repo(entry: Path, skills_dir: Path) -> bool:
    """A symlink whose target (resolved or not) lies inside this repository's skills directory."""
    if not entry.is_symlink():
        return False
    raw = Path(os.readlink(entry))
    target = raw if raw.is_absolute() else entry.parent / raw
    try:
        return Path(os.path.normpath(target)).is_relative_to(skills_dir) or entry.resolve().is_relative_to(skills_dir)
    except OSError:
        return False


def _is_compat(entry: Path) -> bool:
    """A compatibility link chanchi-<n> -> skill-chanchi-<n> (relative, same directory)."""
    if not entry.is_symlink() or not entry.name.startswith(LEGACY_PREFIX):
        return False
    return os.readlink(entry) == f"{SKILL_PREFIX}{entry.name[len(LEGACY_PREFIX):]}"


def _is_legacy(entry: Path, skills_dir: Path, primary: Path) -> bool:
    """A link an older chanchi created: chanchi-<n> pointing into skills/, or a secondary chaining to a
    primary chanchi-<n> that is itself chanchi's (or already gone). Never a foreign file."""
    if not entry.is_symlink() or not entry.name.startswith(LEGACY_PREFIX) or _is_compat(entry):
        return False
    if _points_into_repo(entry, skills_dir):
        return True
    target = primary / entry.name
    chained = os.readlink(entry) == os.path.relpath(target, entry.parent)
    return chained and (not os.path.lexists(target) or _points_into_repo(target, skills_dir))


def link(base: Path, *, global_: bool = False, skills_dir: Path | None = None, compat: bool = True) -> dict:
    base = Path(base).expanduser().resolve()
    if not base.is_dir():
        raise ChanchiError(
            "invalid_value",
            f"path {base} does not exist or is not a directory",
            field="path",
            hint="pass an existing project directory",
        )
    skills_dir = (skills_dir or repo_skills_dir()).resolve()
    names = available_skills(skills_dir)
    primary, secondaries = plan_targets(base, global_=global_)
    created: list[str] = []
    existing: list[str] = []
    conflicts: list[str] = []
    repaired: list[str] = []
    removed: list[str] = []

    for directory in [*secondaries, primary]:
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            if _is_legacy(entry, skills_dir, primary):
                entry.unlink()
                repaired.append(str(entry))

    for name in names:
        _ensure(primary / name, skills_dir / name, absolute=True, created=created, existing=existing, conflicts=conflicts)
        for secondary in secondaries:
            _ensure(secondary / name, primary / name, absolute=False, created=created, existing=existing, conflicts=conflicts)

    if global_:
        for rel_dir in COMPAT_DIRS:
            directory = base / rel_dir
            for name in names:
                legacy_name = f"{LEGACY_PREFIX}{name.removeprefix(SKILL_PREFIX)}"
                compat_path = directory / legacy_name
                if compat:
                    _ensure(
                        compat_path,
                        directory / name,
                        absolute=False,
                        created=created,
                        existing=existing,
                        conflicts=conflicts,
                    )
                elif _is_compat(compat_path):
                    compat_path.unlink()
                    removed.append(str(compat_path))

    if conflicts:
        raise ChanchiError(
            "link_conflict",
            f"created: {', '.join(created)}; conflicts: {', '.join(conflicts)}",
            field="path",
            hint="remove or rename the conflicting entries, then run `chanchi skills link` again",
        )
    return {
        "base": str(base),
        "skills": names,
        "created": created,
        "existing": existing,
        "repaired": repaired,
        "removed": removed,
        "suggested_config_line": SUGGESTED_CONFIG_LINE,
    }


def _is_own(entry: Path, primary: Path, skills_dir: Path) -> bool:
    if _is_legacy(entry, skills_dir, primary) or _is_compat(entry):
        return True
    if not entry.is_symlink() or not entry.name.startswith(SKILL_PREFIX):
        return False
    relative_to_primary = os.path.relpath(primary / entry.name, entry.parent)
    if os.readlink(entry) == relative_to_primary and not os.path.lexists(primary / entry.name):
        return True  # dangling secondary left behind after its primary was removed
    try:
        return entry.resolve().is_relative_to(skills_dir)
    except OSError:
        return False


def unlink(base: Path, *, global_: bool = False, skills_dir: Path | None = None) -> dict:
    base = Path(base).expanduser().resolve()
    if not base.is_dir():
        raise ChanchiError(
            "invalid_value",
            f"path {base} does not exist or is not a directory",
            field="path",
            hint="pass an existing project directory",
        )
    skills_dir = (skills_dir or repo_skills_dir()).resolve()
    primary, secondaries = plan_targets(base, global_=global_)
    removed: list[str] = []
    for directory in [*secondaries, primary]:
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            if _is_own(entry, primary, skills_dir):
                entry.unlink()
                removed.append(str(entry))
    return {"base": str(base), "removed": removed}
