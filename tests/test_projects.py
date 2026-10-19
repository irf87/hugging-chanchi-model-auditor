import pytest

from chanchi import db, projects
from chanchi.errors import ChanchiError


def test_detect_uses_git_toplevel(git_repo):
    (git_repo / "sub").mkdir()
    slug, path = projects.detect(git_repo / "sub")
    assert slug == "demo-app"
    assert path.endswith("demo-app")


def test_detect_in_worktree_derives_slug_from_main_repo(tmp_path):
    import subprocess

    repo = tmp_path / "demo-app"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "file.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
    )
    worktree = tmp_path / "demo-app-feature"
    subprocess.run(["git", "worktree", "add", "../demo-app-feature"], cwd=repo, check=True)
    slug, path = projects.detect(worktree)
    assert slug == "demo-app"
    assert path.endswith("demo-app-feature")


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
