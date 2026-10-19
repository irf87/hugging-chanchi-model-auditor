"""Mirror chanchi skills into projects (or ~) with symlinks. Never overwrites anything."""

from __future__ import annotations

import os
from pathlib import Path

from chanchi.errors import ChanchiError

SKILL_PREFIX = "chanchi-"
SUGGESTED_CONFIG_LINE = (
    "When assigning sessions use the `chanchi-model-selection` skill; when orchestrating and "
    "auditing sessions use the `chanchi-session-audit` skill."
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


def link(base: Path, *, global_: bool = False, skills_dir: Path | None = None) -> dict:
    base = Path(base).expanduser().resolve()
    skills_dir = (skills_dir or repo_skills_dir()).resolve()
    names = available_skills(skills_dir)
    primary, secondaries = plan_targets(base, global_=global_)
    created: list[str] = []
    existing: list[str] = []
    conflicts: list[str] = []
    for name in names:
        _ensure(primary / name, skills_dir / name, absolute=True, created=created, existing=existing, conflicts=conflicts)
        for secondary in secondaries:
            _ensure(secondary / name, primary / name, absolute=False, created=created, existing=existing, conflicts=conflicts)
    if conflicts:
        raise ChanchiError(
            "link_conflict",
            "these paths already exist and were left untouched: " + ", ".join(conflicts),
            field="path",
            hint="remove or rename the conflicting entries, then run `chanchi skills link` again",
        )
    return {
        "base": str(base),
        "skills": names,
        "created": created,
        "existing": existing,
        "suggested_config_line": SUGGESTED_CONFIG_LINE,
    }


def _is_own(entry: Path, primary: Path, skills_dir: Path) -> bool:
    if not entry.is_symlink() or not entry.name.startswith(SKILL_PREFIX):
        return False
    if os.readlink(entry) == os.path.relpath(primary / entry.name, entry.parent):
        return True
    try:
        return entry.resolve().is_relative_to(skills_dir)
    except OSError:
        return False


def unlink(base: Path, *, global_: bool = False, skills_dir: Path | None = None) -> dict:
    base = Path(base).expanduser().resolve()
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
