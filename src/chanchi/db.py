"""Template and operational databases: bootstrap, pragmas and migrations."""

from __future__ import annotations

import importlib.resources
import os
import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from chanchi.errors import ChanchiError

BACKUPS_KEPT = 3


def operational_path() -> Path:
    override = os.environ.get("CHANCHI_DB")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "chanchi" / "chanchi.db"


def template_path() -> Path:
    override = os.environ.get("CHANCHI_TEMPLATE_DB")
    if override:
        return Path(override).expanduser()
    return Path(str(importlib.resources.files("chanchi") / "data" / "template.db"))


def migrations() -> list[tuple[int, str, str]]:
    root = importlib.resources.files("chanchi") / "migrations"
    found = []
    for entry in root.iterdir():
        if entry.name.endswith(".sql"):
            version = int(entry.name.split("_", 1)[0])
            found.append((version, entry.name, entry.read_text(encoding="utf-8")))
    found.sort()
    numbers = [version for version, _, _ in found]
    if numbers != list(range(1, len(found) + 1)):
        raise ChanchiError(
            "internal", f"migrations must be numbered 001..N without gaps, found {numbers}"
        )
    return found


def latest_version() -> int:
    return len(migrations())


def connect(path: Path, *, wal: bool) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(f"PRAGMA journal_mode = {'WAL' if wal else 'DELETE'}")
    return conn


def user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _too_new(current: int, latest: int) -> ChanchiError:
    return ChanchiError(
        "schema_too_new",
        f"database schema is v{current} but this chanchi only knows v{latest}",
        hint="update the chanchi repository (git pull), then retry",
    )


def _statements(sql: str) -> Iterator[str]:
    """Split a migration into statements; full-line `--` comments are dropped."""
    buffer = ""
    for line in sql.splitlines(keepends=True):
        if line.lstrip().startswith("--"):
            continue
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                yield statement
            buffer = ""
    if buffer.strip():
        raise ChanchiError("internal", "migration ends with an incomplete SQL statement")


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply every pending migration, one transaction each. Returns the versions applied."""
    latest = latest_version()
    applied = []
    for version, _name, sql in migrations():
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = user_version(conn)
            if current > latest:
                raise _too_new(current, latest)
            if current >= version:
                conn.execute("COMMIT")
                continue
            for statement in _statements(sql):
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version}")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
        applied.append(version)
    return applied


def migrate_template(path: Path | None = None) -> dict:
    """Bring the committed template database to the latest migration (developer step)."""
    path = path or template_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path, wal=False)
    try:
        before = user_version(conn)
        applied = apply_migrations(conn)
        after = user_version(conn)
        conn.execute("VACUUM")
    finally:
        conn.close()
    return {"path": str(path), "from_version": before, "to_version": after, "applied": applied}


def _prune_backups(path: Path) -> None:
    pattern = re.compile(rf"{re.escape(path.name)}\.bak-v(\d+)")
    backups = []
    for candidate in path.parent.glob(f"{path.name}.bak-v*"):
        match = pattern.fullmatch(candidate.name)
        if match:
            backups.append((int(match.group(1)), candidate))
    backups.sort()
    for _, old in backups[:-BACKUPS_KEPT]:
        old.unlink()


def _backup(path: Path, version: int) -> str:
    dest = path.with_name(f"{path.name}.bak-v{version}")
    if dest.exists():
        dest.unlink()
    source = sqlite3.connect(str(path))
    target = sqlite3.connect(str(dest))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    _prune_backups(path)
    return str(dest)


def _create_from_template(template: Path, path: Path) -> bool:
    """Copy the template beside the target, switch it to WAL, then hard-link it into place atomically.

    Returns False when another process created the database first.
    """
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        shutil.copyfile(template, tmp)
        staging = sqlite3.connect(str(tmp))
        try:
            staging.execute("PRAGMA journal_mode = WAL")
        finally:
            staging.close()
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        for leftover in (tmp, tmp.with_name(tmp.name + "-wal"), tmp.with_name(tmp.name + "-shm")):
            leftover.unlink(missing_ok=True)


def bootstrap() -> dict:
    """Create the operational database from the template if missing, then migrate it."""
    path = operational_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if not path.exists():
        template = template_path()
        if not template.exists():
            raise ChanchiError(
                "internal",
                f"template database not found at {template}",
                hint="run `chanchi db migrate --template` in the chanchi repository",
            )
        created = _create_from_template(template, path)
    conn = connect(path, wal=True)
    try:
        current = user_version(conn)
        latest = latest_version()
        if current > latest:
            raise _too_new(current, latest)
        applied: list[int] = []
        backup = None
        if current < latest:
            if not created:
                conn.close()
                backup = _backup(path, current)
                conn = connect(path, wal=True)
            applied = apply_migrations(conn)
        return {
            "path": str(path),
            "created": created,
            "from_version": current,
            "to_version": user_version(conn),
            "applied": applied,
            "backup": backup,
        }
    finally:
        conn.close()


def open_operational() -> sqlite3.Connection:
    bootstrap()
    return connect(operational_path(), wal=True)


def _read_version(path: Path) -> int | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def status() -> dict:
    latest = latest_version()

    def info(path: Path) -> dict:
        version = _read_version(path)
        return {
            "path": str(path),
            "exists": version is not None,
            "version": version,
            "pending": None if version is None else max(latest - version, 0),
        }

    return {
        "latest_migration": latest,
        "template": info(template_path()),
        "operational": info(operational_path()),
    }
