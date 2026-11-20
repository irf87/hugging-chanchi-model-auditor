"""Project identity: registered path locators, the git toplevel basename, or an explicit slug."""

from __future__ import annotations

import sqlite3
import subprocess
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from chanchi import db
from chanchi.errors import ChanchiError
from chanchi.taxonomy import DEFAULT_WRITER_ROLES, LESSON_STATUSES
from chanchi.timeutil import utc_now


@dataclass(frozen=True)
class Scope:
    """A lesson or project command scope. `project_id` is None for the global scope."""

    project_id: int | None
    slug: str | None


def _git(cwd: Path | str, *args: str) -> str | None:
    """Run one git command; return its stripped stdout, or None when git is missing or fails."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _not_detected() -> ChanchiError:
    return ChanchiError(
        "project_not_detected",
        "the current directory is not inside a git repository",
        field="project",
        hint="run from the project's repository or pass --project <slug>",
    )


def main_worktree(cwd: Path | None = None) -> Path | None:
    """The canonical main worktree of the repository containing cwd, or None outside one."""
    target = cwd or Path.cwd()
    common_dir = _git(target, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common_dir and common_dir.endswith("/.git"):
        return Path(common_dir).parent.resolve()
    top = _git(target, "rev-parse", "--show-toplevel")
    return Path(top).resolve() if top else None


def git_head(cwd: Path | None = None) -> str | None:
    """The HEAD commit of the repository containing cwd, or None (no repository, no commit)."""
    return _git(cwd or Path.cwd(), "rev-parse", "HEAD") or None


def detect(cwd: Path | None = None) -> tuple[str, str]:
    target_cwd = cwd or Path.cwd()
    top_out = _git(target_cwd, "rev-parse", "--show-toplevel")
    if not top_out:
        raise _not_detected()
    top = Path(top_out)
    slug = top.name
    common_dir = _git(target_cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common_dir and common_dir.endswith("/.git"):
        slug = Path(common_dir).parent.name
    return slug, str(top)


def _canonical(path: str | Path) -> Path:
    return Path(path).resolve()


def locate(conn: sqlite3.Connection, cwd: Path | None = None) -> sqlite3.Row | None:
    """The registered project whose path locator is the longest whole-segment prefix of cwd."""
    here = _canonical(cwd or Path.cwd())
    rows = conn.execute(
        "SELECT p.*, l.value AS locator_value FROM project_locators l "
        "JOIN projects p ON p.id = l.project_id WHERE l.kind = 'path'"
    ).fetchall()
    best: sqlite3.Row | None = None
    best_len = -1
    for row in rows:
        locator = _canonical(row["locator_value"])
        if here == locator or locator in here.parents:
            if len(locator.parts) > best_len:
                best, best_len = row, len(locator.parts)
    return best


def identify(
    slug: str | None = None, cwd: Path | None = None, *, conn: sqlite3.Connection | None = None
) -> tuple[str, str | None]:
    """Slug and path for a project.

    An explicit slug wins. Without one, a registered path locator is tried when `conn` is given,
    then today's folder slug from `detect()`.
    """
    if slug is not None:
        slug = slug.strip()
        if not slug:
            raise ChanchiError("invalid_value", "project slug must not be empty", field="project")
        if conn is not None:
            found = locate(conn, cwd)
            if found is not None:
                return slug, found["path"] if found["slug"] == slug else None
        try:
            detected_slug, detected_path = detect(cwd)
        except ChanchiError:
            return slug, None
        return slug, detected_path if detected_slug == slug else None
    if conn is not None:
        found = locate(conn, cwd)
        if found is not None:
            return found["slug"], found["path"]
    return detect(cwd)


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
    slug, _ = identify(slug, cwd, conn=conn)
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        known = [r["slug"] for r in conn.execute("SELECT slug FROM projects ORDER BY slug")]
        raise ChanchiError(
            "invalid_value",
            f"project {slug!r} has no recorded changes yet",
            field="project",
            valid_values=known,
            hint="projects are created by `chanchi change open` or `chanchi project register`",
        )
    return dict(row)


_NOT_REGISTERED_HINT = "chanchi project register (or --global where the command allows it)"


@contextmanager
def _write(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One write transaction; joins the caller's transaction when one is already open."""
    if conn.in_transaction:
        yield conn
    else:
        with db.transaction(conn):
            yield conn


def _registered_row(conn: sqlite3.Connection, slug: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM projects WHERE slug = ? AND registered_at IS NOT NULL", (slug,)
    ).fetchone()
    if row is None:
        raise ChanchiError(
            "project_not_registered",
            f"project {slug!r} is not registered",
            field="project",
            hint=_NOT_REGISTERED_HINT,
        )
    return row


def resolve_scope(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    global_: bool = False,
    cwd: Path | None = None,
) -> Scope:
    """The scope of a lesson or project command: global, an explicit slug, or the working directory."""
    if global_:
        if project is not None:
            raise ChanchiError(
                "invalid_value", "--global cannot be combined with --project", field="project"
            )
        return Scope(None, None)
    if project is not None:
        slug = project.strip()
        if not slug:
            raise ChanchiError("invalid_value", "project slug must not be empty", field="project")
        row = _registered_row(conn, slug)
        return Scope(row["id"], row["slug"])
    found = locate(conn, cwd)
    if found is None:
        raise ChanchiError(
            "project_not_registered",
            "this directory is not inside a registered project",
            field="project",
            hint=_NOT_REGISTERED_HINT,
        )
    return Scope(found["id"], found["slug"])


def writer_roles(conn: sqlite3.Connection, project_id: int | None) -> tuple[str, ...]:
    """The scope's writer roles, or the default when it has none stored."""
    rows = conn.execute(
        "SELECT role FROM writer_roles WHERE COALESCE(project_id, 0) = COALESCE(?, 0) ORDER BY id",
        (project_id,),
    ).fetchall()
    return tuple(r["role"] for r in rows) or DEFAULT_WRITER_ROLES


def set_writer_roles(
    conn: sqlite3.Connection, project_id: int | None, roles: Sequence[str]
) -> tuple[str, ...]:
    """Replace the scope's writer roles. No actor check: `lessons.set_writers` guards this."""
    now = utc_now()
    with _write(conn):
        conn.execute(
            "DELETE FROM writer_roles WHERE COALESCE(project_id, 0) = COALESCE(?, 0)", (project_id,)
        )
        for role in roles:
            conn.execute(
                "INSERT INTO writer_roles (project_id, role, created_at) VALUES (?, ?, ?)",
                (project_id, role, now),
            )
    return tuple(roles)


def _describe(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    pid = row["id"]
    locators = [
        r["value"]
        for r in conn.execute(
            "SELECT value FROM project_locators WHERE project_id = ? AND kind = 'path' ORDER BY id",
            (pid,),
        )
    ]
    stored = conn.execute(
        "SELECT COUNT(*) FROM writer_roles WHERE project_id = ?", (pid,)
    ).fetchone()[0]
    counts = dict.fromkeys(LESSON_STATUSES, 0)
    for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM lessons WHERE origin_project_id = ? GROUP BY status",
        (pid,),
    ):
        counts[r["status"]] = r["n"]
    return {
        "id": pid,
        "slug": row["slug"],
        "path": row["path"],
        "registered_at": row["registered_at"],
        "locators": locators,
        "writers": {"roles": list(writer_roles(conn, pid)), "default": stored == 0},
        "lessons": counts,
    }


def list_projects(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM projects WHERE registered_at IS NOT NULL ORDER BY slug"
    ).fetchall()
    return [_describe(conn, row) for row in rows]


def show(conn: sqlite3.Connection, slug: str) -> dict:
    return _describe(conn, _registered_row(conn, slug.strip()))


def register(conn: sqlite3.Connection, cwd: Path | None = None, name: str | None = None) -> dict:
    """Register the project whose main worktree contains cwd."""
    main = main_worktree(cwd)
    if main is None:
        raise _not_detected()
    if name is not None:
        name = name.strip()
        if not name:
            raise ChanchiError("invalid_value", "project name must not be empty", field="name")
    slug = name or main.name
    now = utc_now()
    with _write(conn):
        owner = conn.execute(
            "SELECT p.* FROM project_locators l JOIN projects p ON p.id = l.project_id "
            "WHERE l.kind = 'path' AND l.value = ?",
            (str(main),),
        ).fetchone()
        if owner is not None:
            return {
                "project": _describe(conn, owner),
                "already_registered": True,
                "adopted": False,
            }
        row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
        adopted = False
        if row is not None:
            if row["registered_at"] is not None:
                raise ChanchiError(
                    "invalid_value",
                    f"project {slug!r} is already registered at {row['path']}",
                    field="name",
                    hint="--name <other slug>",
                )
            adopted = True
            conn.execute(
                "UPDATE projects SET registered_at = ?, path = ? WHERE id = ?",
                (now, str(main), row["id"]),
            )
            pid = row["id"]
        else:
            pid = conn.execute(
                "INSERT INTO projects (slug, path, created_at, registered_at) VALUES (?, ?, ?, ?)",
                (slug, str(main), now, now),
            ).lastrowid
        conn.execute(
            "INSERT INTO project_locators (project_id, kind, value, created_at) "
            "VALUES (?, 'path', ?, ?)",
            (pid, str(main), now),
        )
        described = _describe(
            conn, conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        )
    return {"project": described, "already_registered": False, "adopted": adopted}


def relink(conn: sqlite3.Connection, slug: str, cwd: Path | None = None) -> dict:
    """Add the canonical git toplevel of cwd as a path locator of a registered project."""
    top = _git(cwd or Path.cwd(), "rev-parse", "--show-toplevel")
    if not top:
        raise _not_detected()
    value = str(Path(top).resolve())
    now = utc_now()
    with _write(conn):
        row = _registered_row(conn, slug.strip())
        owner = conn.execute(
            "SELECT p.slug, p.id FROM project_locators l JOIN projects p ON p.id = l.project_id "
            "WHERE l.kind = 'path' AND l.value = ?",
            (value,),
        ).fetchone()
        added = False
        if owner is not None and owner["id"] != row["id"]:
            raise ChanchiError(
                "invalid_value",
                f"{value} already belongs to project {owner['slug']!r}",
                field="project",
            )
        if owner is None:
            conn.execute(
                "INSERT INTO project_locators (project_id, kind, value, created_at) "
                "VALUES (?, 'path', ?, ?)",
                (row["id"], value, now),
            )
            added = True
        described = _describe(conn, row)
    return {"project": described, "locator": value, "added": added}
