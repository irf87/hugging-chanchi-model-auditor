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


# --- registration, locators and scope ---------------------------------------------------------


def _git(cwd, *args):
    import subprocess

    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    (path / "file.txt").write_text("initial")
    _git(path, "add", ".")
    _git(path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "init")
    return path


def _row(conn, slug):
    return conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()


def test_main_worktree_from_linked_worktree_returns_main_path(tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    worktree = tmp_path / "demo-app-feature"
    _git(repo, "worktree", "add", "../demo-app-feature")
    assert projects.main_worktree(worktree) == repo.resolve()
    assert projects.main_worktree(repo) == repo.resolve()


def test_main_worktree_outside_repository_is_none(tmp_path):
    assert projects.main_worktree(tmp_path) is None


def test_git_head_returns_commit_and_none_outside_repository(registered_repo, tmp_path_factory):
    import subprocess

    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=registered_repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert projects.git_head(registered_repo) == expected
    assert projects.git_head(tmp_path_factory.mktemp("plain")) is None


def test_git_head_is_none_in_a_repository_without_commits(git_repo):
    assert projects.git_head(git_repo) is None


def test_register_creates_a_row(conn, tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    result = projects.register(conn, repo)
    assert result["already_registered"] is False and result["adopted"] is False
    project = result["project"]
    assert project["slug"] == "demo-app"
    assert project["path"] == str(repo.resolve())
    assert project["registered_at"]
    assert project["locators"] == [str(repo.resolve())]
    assert project["writers"] == {"roles": ["planner"], "default": True}
    assert project["lessons"]["pending"] == 0


def test_register_adopts_an_unregistered_row_with_the_same_slug(conn, tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    with db.transaction(conn):
        old_id = projects.ensure(conn, "demo-app", None)
    result = projects.register(conn, repo)
    assert result["adopted"] is True and result["already_registered"] is False
    assert result["project"]["id"] == old_id
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
    assert _row(conn, "demo-app")["registered_at"] is not None


def test_register_twice_is_a_no_op(conn, tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    first = projects.register(conn, repo)
    second = projects.register(conn, repo)
    assert second["already_registered"] is True and second["adopted"] is False
    assert second["project"] == first["project"]
    assert conn.execute("SELECT COUNT(*) FROM project_locators").fetchone()[0] == 1


def test_register_from_a_linked_worktree_registers_the_main_path(conn, tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    worktree = tmp_path / "demo-app-feature"
    _git(repo, "worktree", "add", "../demo-app-feature")
    result = projects.register(conn, worktree)
    assert result["project"]["path"] == str(repo.resolve())


def test_register_refuses_a_slug_owned_by_another_registered_project(conn, tmp_path):
    first = _init_repo(tmp_path / "one" / "demo-app")
    second = _init_repo(tmp_path / "two" / "demo-app")
    projects.register(conn, first)
    with pytest.raises(ChanchiError) as info:
        projects.register(conn, second)
    assert info.value.code == "invalid_value"
    assert str(first.resolve()) in info.value.message
    assert info.value.hint == "--name <other slug>"
    assert conn.execute("SELECT COUNT(*) FROM project_locators").fetchone()[0] == 1
    assert projects.register(conn, second, name="demo-app-two")["project"]["slug"] == "demo-app-two"


def test_register_outside_a_repository_fails(conn, tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    with pytest.raises(ChanchiError) as info:
        projects.register(conn, outside)
    assert info.value.code == "project_not_detected"


def test_register_with_name_leaves_an_unregistered_folder_slug_row_alone(conn, tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    with db.transaction(conn):
        projects.ensure(conn, "demo-app", None)
    result = projects.register(conn, repo, name="other-name")
    assert result["adopted"] is False
    assert result["project"]["slug"] == "other-name"
    untouched = _row(conn, "demo-app")
    assert untouched["registered_at"] is None and untouched["path"] is None


def test_relink_adds_a_path_and_is_a_no_op_for_a_path_the_project_owns(conn, tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    projects.register(conn, repo)
    moved = _init_repo(tmp_path / "moved" / "demo-app")
    added = projects.relink(conn, "demo-app", moved)
    assert added["added"] is True and added["locator"] == str(moved.resolve())
    assert added["project"]["locators"] == [str(repo.resolve()), str(moved.resolve())]
    again = projects.relink(conn, "demo-app", moved)
    assert again["added"] is False
    own = projects.relink(conn, "demo-app", repo)
    assert own["added"] is False
    assert conn.execute("SELECT COUNT(*) FROM project_locators").fetchone()[0] == 2


def test_relink_refuses_a_path_owned_by_another_project(conn, tmp_path):
    first = _init_repo(tmp_path / "one" / "alpha")
    second = _init_repo(tmp_path / "two" / "beta")
    projects.register(conn, first)
    projects.register(conn, second)
    with pytest.raises(ChanchiError) as info:
        projects.relink(conn, "alpha", second)
    assert info.value.code == "invalid_value"
    assert "beta" in info.value.message
    assert conn.execute("SELECT COUNT(*) FROM project_locators").fetchone()[0] == 2


def test_relink_requires_a_registered_project_and_a_repository(conn, tmp_path):
    repo = _init_repo(tmp_path / "demo-app")
    with pytest.raises(ChanchiError) as info:
        projects.relink(conn, "demo-app", repo)
    assert info.value.code == "project_not_registered"
    projects.register(conn, repo)
    outside = tmp_path / "plain"
    outside.mkdir()
    with pytest.raises(ChanchiError) as info:
        projects.relink(conn, "demo-app", outside)
    assert info.value.code == "project_not_detected"


def _add_locator(conn, slug, path):
    with db.transaction(conn):
        pid = projects.ensure(conn, slug, str(path))
        conn.execute("UPDATE projects SET registered_at = '2026-01-01T00:00:00Z' WHERE id = ?", (pid,))
        conn.execute(
            "INSERT INTO project_locators (project_id, kind, value, created_at) VALUES (?, 'path', ?, 'x')",
            (pid, str(path)),
        )


def test_locate_picks_the_longest_prefix_on_whole_segments(conn, tmp_path):
    (tmp_path / "work" / "b" / "sub").mkdir(parents=True)
    (tmp_path / "work" / "bb").mkdir()
    (tmp_path / "work" / "b" / "inner").mkdir()
    _add_locator(conn, "outer", tmp_path / "work")
    _add_locator(conn, "b", tmp_path / "work" / "b")
    assert projects.locate(conn, tmp_path / "work" / "b" / "sub")["slug"] == "b"
    assert projects.locate(conn, tmp_path / "work" / "b")["slug"] == "b"
    assert projects.locate(conn, tmp_path / "work" / "bb")["slug"] == "outer"
    assert projects.locate(conn, tmp_path / "elsewhere") is None


def test_locate_does_not_match_a_sibling_with_a_shared_name_prefix(conn, tmp_path):
    (tmp_path / "work" / "b").mkdir(parents=True)
    (tmp_path / "work" / "bb").mkdir()
    _add_locator(conn, "b", tmp_path / "work" / "b")
    assert projects.locate(conn, tmp_path / "work" / "bb") is None


def test_locate_resolves_symlinks_on_both_sides(conn, tmp_path):
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    _add_locator(conn, "linked", link)
    assert projects.locate(conn, real / "sub")["slug"] == "linked"
    assert projects.locate(conn, link / "sub")["slug"] == "linked"
    other = tmp_path / "other"
    other.symlink_to(real / "sub", target_is_directory=True)
    assert projects.locate(conn, other)["slug"] == "linked"


def test_identify_from_nested_repository_returns_the_outer_project(nested_repo, conn):
    inner = nested_repo / "inner"
    slug, path = projects.identify(cwd=inner, conn=conn)
    assert slug == "outer-app"
    assert path == str(nested_repo.resolve())
    assert projects.identify("outer-app", inner, conn=conn) == ("outer-app", str(nested_repo.resolve()))
    assert projects.identify("other", inner, conn=conn) == ("other", None)
    assert projects.detect(inner)[0] == "inner"


def test_commands_from_a_nested_repository_resolve_to_the_outer_project(
    nested_repo, seeded, capsys, monkeypatch
):
    import json

    from chanchi import cli

    def run(*argv):
        code = cli.main(list(argv))
        out, err = capsys.readouterr()
        assert code == 0, err
        return json.loads(out)

    monkeypatch.chdir(nested_repo / "inner")
    change = run("change", "open", "add-login", "--kind", "openspec", "--planner", "claude:opus:xhigh")
    assert change["change"]["project"] == "outer-app"
    session = run(
        "session", "start", "add-login", "S1", "--executor", "claude:sonnet:high",
        "--task-type", "ui-component", "--complexity", "medium", "--tasks", "3",
    )
    assert session["session"]["attempt"] == 1
    run(
        "incident", "add", "add-login", "--code", "plan_gap", "--severity", "blocking",
        "--detected-by", "planner_audit", "--desc", "gap", "--evidence", "tasks.md",
    )
    shown = run("show", "add-login")
    assert shown["change"]["project"] == "outer-app"
    assert [r["slug"] for r in seeded.execute("SELECT slug FROM projects")] == ["outer-app"]


def test_explicit_project_wins_over_the_locator(registered_repo, conn):
    with db.transaction(conn):
        projects.ensure(conn, "other", None)
    assert projects.identify("other", conn=conn) == ("other", None)
    assert projects.resolve_project(conn, "other")["slug"] == "other"
    assert projects.identify(conn=conn)[0] == "demo-app"


def test_resolve_scope_outside_any_registered_project_fails(conn, git_repo):
    with pytest.raises(ChanchiError) as info:
        projects.resolve_scope(conn)
    assert info.value.code == "project_not_registered"
    assert info.value.field == "project"
    assert "chanchi project register" in info.value.hint


def test_resolve_scope_variants(registered_repo, conn, tmp_path):
    scope = projects.resolve_scope(conn)
    assert scope.slug == "demo-app" and scope.project_id == _row(conn, "demo-app")["id"]
    assert projects.resolve_scope(conn, project="demo-app") == scope
    assert projects.resolve_scope(conn, global_=True) == projects.Scope(None, None)
    with pytest.raises(ChanchiError) as info:
        projects.resolve_scope(conn, project="nope")
    assert info.value.code == "project_not_registered"
    with db.transaction(conn):
        projects.ensure(conn, "unregistered", None)
    with pytest.raises(ChanchiError) as info:
        projects.resolve_scope(conn, project="unregistered")
    assert info.value.code == "project_not_registered"


def test_resolve_scope_global_with_project_fails(registered_repo, conn):
    with pytest.raises(ChanchiError) as info:
        projects.resolve_scope(conn, project="demo-app", global_=True)
    assert info.value.code == "invalid_value"


def test_resolve_project_hint_mentions_register(conn, git_repo):
    with pytest.raises(ChanchiError) as info:
        projects.resolve_project(conn)
    assert "chanchi project register" in info.value.hint


def test_identify_on_an_unregistered_repository_is_unchanged(conn, git_repo):
    assert projects.identify(conn=conn) == projects.detect(git_repo)
    slug, path = projects.identify(conn=conn)
    assert slug == "demo-app" and path.endswith("demo-app")
    assert projects.identify("demo-app", conn=conn) == projects.identify("demo-app")
    assert conn.execute("SELECT COUNT(*) FROM project_locators").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_unregistered_change_keeps_registered_at_null(seeded, recorder):
    recorder.change("add-login")
    row = _row(seeded, "demo-app")
    assert row["registered_at"] is None
    assert row["path"].endswith("demo-app")
    assert seeded.execute("SELECT COUNT(*) FROM project_locators").fetchone()[0] == 0


def test_recorder_change_uses_the_registered_project(registered_repo, seeded):
    from helpers import Recorder

    Recorder(seeded).change("add-login")
    assert [r["slug"] for r in seeded.execute("SELECT slug FROM projects")] == ["demo-app"]
    assert _row(seeded, "demo-app")["registered_at"] is not None


def test_writer_roles_default_and_replace(registered_repo, conn):
    pid = _row(conn, "demo-app")["id"]
    assert projects.writer_roles(conn, pid) == ("planner",)
    assert projects.writer_roles(conn, None) == ("planner",)
    projects.set_writer_roles(conn, pid, ["planner", "human"])
    assert projects.writer_roles(conn, pid) == ("planner", "human")
    assert projects.writer_roles(conn, None) == ("planner",)
    projects.set_writer_roles(conn, pid, ["executor"])
    assert projects.writer_roles(conn, pid) == ("executor",)
    projects.set_writer_roles(conn, None, ["human"])
    assert projects.writer_roles(conn, None) == ("human",)
    assert projects.writer_roles(conn, pid) == ("executor",)
    assert projects.show(conn, "demo-app")["writers"] == {"roles": ["executor"], "default": False}


def test_set_writer_roles_joins_an_open_transaction(registered_repo, conn):
    pid = _row(conn, "demo-app")["id"]
    with db.transaction(conn):
        projects.set_writer_roles(conn, pid, ["human"])
    assert projects.writer_roles(conn, pid) == ("human",)


def test_list_and_show(registered_repo, conn):
    with db.transaction(conn):
        projects.ensure(conn, "unregistered", None)
    listed = projects.list_projects(conn)
    assert [p["slug"] for p in listed] == ["demo-app"]
    shown = projects.show(conn, "demo-app")
    assert shown == listed[0]
    assert set(shown["lessons"]) == {"pending", "approved", "rejected", "postponed", "duplicate"}
    with pytest.raises(ChanchiError) as info:
        projects.show(conn, "unregistered")
    assert info.value.code == "project_not_registered"


def test_show_counts_lessons_by_status(registered_repo, conn):
    pid = _row(conn, "demo-app")["id"]
    now = "2026-10-01T00:00:00Z"
    for status in ("pending", "pending", "approved"):
        conn.execute(
            "INSERT INTO lessons (origin_project_id, author_role, author_agent, author_model_raw, "
            "author_conversation, target_kind, target, what_happened, evidence, cause, prevention, "
            "proposal, general_rule, generality, severity, status, reviewed_at, created_at, updated_at) "
            "VALUES (?, 'planner', 'claude', 'opus', 'c1', 'role', 't', 'w', 'e', 'c', 'p', 'pr', 'g', "
            "'agnostic', 'low', ?, ?, ?, ?)",
            (pid, status, None if status == "pending" else now, now, now),
        )
    counts = projects.show(conn, "demo-app")["lessons"]
    assert counts["pending"] == 2 and counts["approved"] == 1 and counts["rejected"] == 0


def test_identify_explicit_folder_slug_keeps_path_in_an_unregistered_repository(conn, git_repo):
    slug, path = projects.identify("demo-app", conn=conn)
    assert slug == "demo-app"
    assert path == str(git_repo.resolve())
    slug, path = projects.identify("other", conn=conn)
    assert (slug, path) == ("other", None)


def test_reserved_slug_global_refused_in_register_ensure_and_change_open(
    conn, tmp_path, db_env, capsys, monkeypatch
):
    import json
    from chanchi import cli

    assert "global" in projects.RESERVED_SLUGS
    with pytest.raises(ChanchiError) as info:
        projects.check_slug("global")
    assert (info.value.code, info.value.field) == ("invalid_value", "slug")
    assert "chanchi project register --name" in info.value.hint

    global_repo = _init_repo(tmp_path / "global")
    with pytest.raises(ChanchiError) as info:
        projects.register(conn, global_repo)
    assert (info.value.code, info.value.field) == ("invalid_value", "slug")
    assert "chanchi project register --name" in info.value.hint

    normal_repo = _init_repo(tmp_path / "normal")
    with pytest.raises(ChanchiError) as info:
        projects.register(conn, normal_repo, name="global")
    assert (info.value.code, info.value.field) == ("invalid_value", "slug")

    with pytest.raises(ChanchiError) as info:
        with db.transaction(conn):
            projects.ensure(conn, "global", str(global_repo))
    assert (info.value.code, info.value.field) == ("invalid_value", "slug")

    # Registering global/ with --name other succeeds; re-running without --name answers already_registered;
    # re-running with --name global is refused before the locator lookup.
    reg = projects.register(conn, global_repo, name="other")
    assert reg["project"]["slug"] == "other"
    again = projects.register(conn, global_repo)
    assert again["already_registered"] is True and again["project"]["slug"] == "other"
    with pytest.raises(ChanchiError) as info:
        projects.register(conn, global_repo, name="global")
    assert (info.value.code, info.value.field) == ("invalid_value", "slug")

    # change open inside an unregistered folder named global and with --project global are both refused
    other_global = _init_repo(tmp_path / "nested" / "global")
    monkeypatch.chdir(other_global)
    assert cli.main(["models", "add", "--agent", "claude", "--model", "opus", "--cost", "3"]) == 0
    capsys.readouterr()

    code = cli.main(["change", "open", "c1", "--kind", "adhoc", "--planner", "claude:opus"])
    _, err = capsys.readouterr()
    assert code == 2
    err_obj = json.loads(err)["error"]
    assert (err_obj["code"], err_obj["field"]) == ("invalid_value", "slug")
    assert "chanchi project register --name" in err_obj["hint"]

    monkeypatch.chdir(normal_repo)
    code = cli.main(["change", "open", "c1", "--kind", "adhoc", "--planner", "claude:opus", "--project", "global"])
    _, err = capsys.readouterr()
    assert code == 2
    err_obj = json.loads(err)["error"]
    assert (err_obj["code"], err_obj["field"]) == ("invalid_value", "slug")
    assert "chanchi project register --name" in err_obj["hint"]
