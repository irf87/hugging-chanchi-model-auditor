import shutil
import sqlite3

import pytest

from chanchi import db, taxonomy
from chanchi.errors import ChanchiError

OPERATIONAL_TABLES = ("projects", "changes", "sessions", "incidents")


def _schema(conn):
    return conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()


def _fresh(tmp_path):
    conn = db.connect(tmp_path / "fresh.db", wal=False)
    db.apply_migrations(conn)
    return conn


def test_migrations_are_contiguous():
    versions = [version for version, _, _ in db.migrations()]
    assert versions == list(range(1, len(versions) + 1))
    assert db.latest_version() == len(versions)


def test_template_is_at_latest_version():
    template = db.connect(db.template_path(), wal=False)
    try:
        assert db.user_version(template) == db.latest_version()
        assert template.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        template.close()


def test_template_schema_matches_migrations(tmp_path):
    fresh = _fresh(tmp_path)
    template = db.connect(db.template_path(), wal=False)
    try:
        assert [tuple(r) for r in _schema(template)] == [tuple(r) for r in _schema(fresh)]
        for table in ("models", "task_types"):
            query = f"SELECT * FROM {table} ORDER BY 1"
            assert [tuple(r) for r in template.execute(query)] == [
                tuple(r) for r in fresh.execute(query)
            ]
        for table in OPERATIONAL_TABLES:
            assert template.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        template.close()
        fresh.close()


def test_template_seed_matches_taxonomy():
    template = db.connect(db.template_path(), wal=False)
    try:
        rows = [tuple(r) for r in template.execute("SELECT code, description FROM task_types ORDER BY rowid")]
        assert rows == list(taxonomy.TASK_TYPES)
        human = template.execute("SELECT agent, model FROM models").fetchall()
        assert [tuple(r) for r in human] == [("human", "human")]
    finally:
        template.close()


def test_bootstrap_creates_operational_from_template(db_env):
    result = db.bootstrap()
    assert result["created"] is True
    assert result["applied"] == []
    assert result["backup"] is None
    assert db_env.exists()
    conn = db.connect(db_env, wal=True)
    try:
        assert db.user_version(conn) == db.latest_version()
        assert conn.execute("SELECT COUNT(*) FROM task_types").fetchone()[0] == len(taxonomy.TASK_TYPES)
    finally:
        conn.close()


def test_bootstrap_is_idempotent(db_env):
    db.bootstrap()
    again = db.bootstrap()
    assert again["created"] is False
    assert again["applied"] == []


def test_outdated_operational_is_backed_up_and_migrated(db_env):
    db_env.parent.mkdir(parents=True)
    sqlite3.connect(str(db_env)).close()  # empty database at user_version 0
    result = db.bootstrap()
    assert result["created"] is False
    assert result["from_version"] == 0
    assert result["applied"] == list(range(1, db.latest_version() + 1))
    assert result["backup"].endswith("chanchi.db.bak-v0")
    assert (db_env.parent / "chanchi.db.bak-v0").exists()


def test_too_new_operational_is_refused(db_env):
    db.bootstrap()
    raw = sqlite3.connect(str(db_env))
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    with pytest.raises(ChanchiError) as info:
        db.bootstrap()
    assert info.value.code == "schema_too_new"


def test_only_three_backups_are_kept(tmp_path):
    path = tmp_path / "chanchi.db"
    path.write_bytes(b"")
    for version in range(1, 6):
        (tmp_path / f"chanchi.db.bak-v{version}").write_bytes(b"")
    db._prune_backups(path)
    remaining = sorted(p.name for p in tmp_path.glob("chanchi.db.bak-v*"))
    assert remaining == ["chanchi.db.bak-v3", "chanchi.db.bak-v4", "chanchi.db.bak-v5"]


def test_migrate_template_on_a_copy(tmp_path, monkeypatch):
    copy = tmp_path / "template.db"
    shutil.copyfile(db.template_path(), copy)
    monkeypatch.setenv("CHANCHI_TEMPLATE_DB", str(copy))
    assert db.migrate_template()["applied"] == []
    blank = tmp_path / "blank.db"
    result = db.migrate_template(blank)
    assert result["from_version"] == 0
    assert result["to_version"] == db.latest_version()


def test_transaction_rolls_back_on_error(conn):
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            conn.execute("INSERT INTO task_types (code, description) VALUES ('tmp-type', 'x')")
            raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM task_types WHERE code = 'tmp-type'").fetchone()[0] == 0


def test_connection_pragmas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_status_reports_both_databases(db_env):
    before = db.status()
    assert before["operational"]["exists"] is False
    assert before["template"]["pending"] == 0
    db.bootstrap()
    after = db.status()
    assert after["operational"]["version"] == db.latest_version()
    assert after["operational"]["pending"] == 0
