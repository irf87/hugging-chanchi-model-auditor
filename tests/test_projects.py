import pytest

from chanchi import db, projects
from chanchi.errors import ChanchiError


def test_detect_uses_git_toplevel(git_repo):
    (git_repo / "sub").mkdir()
    slug, path = projects.detect(git_repo / "sub")
    assert slug == "demo-app"
    assert path.endswith("demo-app")


def test_detect_outside_git_fails(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    with pytest.raises(ChanchiError) as info:
        projects.detect(outside)
    assert info.value.code == "project_not_detected"
    assert info.value.field == "project"


def test_identify_explicit_slug_keeps_path_only_when_it_matches(git_repo):
    assert projects.identify("demo-app")[1].endswith("demo-app")
    assert projects.identify("other") == ("other", None)


def test_identify_explicit_slug_outside_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert projects.identify("manual") == ("manual", None)


def test_identify_rejects_empty_slug(git_repo):
    with pytest.raises(ChanchiError):
        projects.identify("  ")


def test_ensure_inserts_once(conn):
    with db.transaction(conn):
        first = projects.ensure(conn, "demo-app", "/tmp/demo-app")
    with db.transaction(conn):
        second = projects.ensure(conn, "demo-app", "/tmp/demo-app")
    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


def test_resolve_project_requires_existing_row(conn, git_repo):
    with pytest.raises(ChanchiError) as info:
        projects.resolve_project(conn)
    assert info.value.code == "invalid_value"
    assert info.value.valid_values == []
    with db.transaction(conn):
        projects.ensure(conn, "demo-app", None)
    assert projects.resolve_project(conn)["slug"] == "demo-app"
