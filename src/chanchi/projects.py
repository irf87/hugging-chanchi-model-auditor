"""Project identity: the git toplevel basename, or an explicit --project slug."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now


def detect(cwd: Path | None = None) -> tuple[str, str]:
    target_cwd = cwd or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=target_cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        result = None
    if result is None or result.returncode != 0 or not result.stdout.strip():
        raise ChanchiError(
            "project_not_detected",
            "the current directory is not inside a git repository",
            field="project",
            hint="run from the project's repository or pass --project <slug>",
        )
    top = Path(result.stdout.strip())
    slug = top.name
    try:
        common_res = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=target_cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if common_res.returncode == 0:
            common_dir = common_res.stdout.strip()
            if common_dir.endswith("/.git"):
                slug = Path(common_dir).parent.name
    except FileNotFoundError:
        pass
    return slug, str(top)


def identify(slug: str | None = None, cwd: Path | None = None) -> tuple[str, str | None]:
    """Slug and path for a project; the path is kept only when the cwd is that project."""
    if slug is None:
        return detect(cwd)
    slug = slug.strip()
    if not slug:
        raise ChanchiError("invalid_value", "project slug must not be empty", field="project")
    try:
        detected_slug, detected_path = detect(cwd)
    except ChanchiError:
        return slug, None
    return slug, detected_path if detected_slug == slug else None


def ensure(conn: sqlite3.Connection, slug: str, path: str | None, now: str | None = None) -> int:
    """Return the project id, inserting the row if needed. The caller holds the transaction."""
    row = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if row is not None:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO projects (slug, path, created_at) VALUES (?, ?, ?)",
        (slug, path, now or utc_now()),
    )
    return cursor.lastrowid


def resolve_project(
    conn: sqlite3.Connection, slug: str | None = None, cwd: Path | None = None
) -> dict:
    slug, _ = identify(slug, cwd)
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        known = [r["slug"] for r in conn.execute("SELECT slug FROM projects ORDER BY slug")]
        raise ChanchiError(
            "invalid_value",
            f"project {slug!r} has no recorded changes yet",
            field="project",
            valid_values=known,
            hint="projects are created by `chanchi change open`",
        )
    return dict(row)
