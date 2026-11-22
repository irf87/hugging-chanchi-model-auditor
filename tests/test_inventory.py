"""Project item inventory: `project items-dirs`, `items scan` and the lenient frontmatter reader.

Design: docs/designs/global-items.md, "B. Capture" and "Data model (migration 006)".
"""

import json
import os
import shutil
import subprocess

import pytest

from chanchi import cli, db, inventory, items, projects, taxonomy
from chanchi.errors import ChanchiError

# --- helpers -------------------------------------------------------------------------


def git_project(tmp_path, conn, name):
    """A temporary git repository registered on the scratch database."""
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    projects.register(conn, repo)
    return repo.resolve()


def put(root, rel, text="", *, data=None):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if data is not None:
        path.write_bytes(data)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def skill_text(name, description="Does the thing.", body=3):
    lines = "\n".join(f"Step {i}." for i in range(body))
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{lines}\n"


def pid_of(conn, slug):
    return conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()["id"]


def rows(conn, slug):
    return {
        r["path"]: dict(r)
        for r in conn.execute(
            "SELECT i.* FROM project_items i JOIN projects p ON p.id = i.project_id WHERE p.slug = ?",
            (slug,),
        )
    }


def snapshot(*roots):
    """Every path under the roots with its type, size and mtime_ns, never following links."""
    seen = {}
    for root in roots:
        for here, dirs, files in os.walk(root, followlinks=False):
            for name in [*dirs, *files]:
                path = os.path.join(here, name)
                st = os.lstat(path)
                seen[path] = (st.st_mode, st.st_size, st.st_mtime_ns)
        st = os.lstat(root)
        seen[str(root)] = (st.st_mode, st.st_size, st.st_mtime_ns)
    return seen


def run(capsys, *argv, expect=0):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    assert code == expect, err or out
    return json.loads(out if expect == 0 else err)


# --- taxonomy ------------------------------------------------------------------------


def test_taxonomy_lists_the_project_item_enumerations():
    assert taxonomy.PROJECT_ITEM_KINDS == ("agent", "skill", "hook", "rule")
    assert taxonomy.PROPOSAL_STATUSES == ("open", "built", "rejected")
    described = taxonomy.describe()["items"]
    assert described["project_item_kinds"] == list(taxonomy.PROJECT_ITEM_KINDS)
    assert described["proposal_statuses"] == list(taxonomy.PROPOSAL_STATUSES)


# --- project_root --------------------------------------------------------------------


def test_project_root_is_the_lowest_id_existing_locator(conn, tmp_path):
    first = git_project(tmp_path, conn, "app")
    second = tmp_path / "second"
    second.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=second, check=True)
    projects.relink(conn, "app", second)
    pid = pid_of(conn, "app")
    assert inventory.project_root(conn, pid) == first
    shutil.rmtree(first)
    assert inventory.project_root(conn, pid) == second.resolve()
    shutil.rmtree(second)
    assert inventory.project_root(conn, pid) is None


def test_project_root_ignores_a_locator_that_is_a_file(conn, tmp_path):
    repo = git_project(tmp_path, conn, "app")
    pid = pid_of(conn, "app")
    shutil.rmtree(repo)
    repo.write_text("not a folder")
    assert inventory.project_root(conn, pid) is None


# --- project items-dirs (module) -----------------------------------------------------


def test_defaults_are_the_seven_roots_in_order():
    assert inventory.DEFAULT_ROOTS == (
        ".agents/skills", ".claude/skills", ".opencode/skills", "agents",
        ".claude/agents", ".opencode/agents", ".agents/agents",
    )
    assert inventory.AGENT_FILE_ROOTS == (".claude/agents", ".opencode/agents")


def test_a_fresh_project_has_no_item_dirs(conn, tmp_path):
    git_project(tmp_path, conn, "app")
    assert inventory.item_dirs(conn, pid_of(conn, "app")) == []


def test_add_item_dir_stores_the_normalized_path_once(conn, tmp_path):
    repo = git_project(tmp_path, conn, "app")
    (repo / "docs" / "agents").mkdir(parents=True)
    pid = pid_of(conn, "app")
    assert inventory.add_item_dir(conn, pid, repo, "docs/agents") == {"path": "docs/agents", "added": True}
    assert inventory.add_item_dir(conn, pid, repo, "docs/agents") == {"path": "docs/agents", "added": False}
    assert inventory.add_item_dir(conn, pid, repo, "./docs//agents/") == {"path": "docs/agents", "added": False}
    assert inventory.item_dirs(conn, pid) == ["docs/agents"]


@pytest.mark.parametrize(
    "path",
    ["/etc", "../x", "a/../b", "", "   ", ".", "./", ".claude/skills", "agents", "missing", "notes.md", "linked",
     "linked/x", "docs/alink"],
)
def test_add_item_dir_refusals(conn, tmp_path, path):
    repo = git_project(tmp_path, conn, "app")
    outside = tmp_path / "outside"
    (outside / "x").mkdir(parents=True)
    (repo / ".claude" / "skills").mkdir(parents=True)
    (repo / "agents").mkdir()
    (repo / "docs").mkdir()
    (repo / "notes.md").write_text("x")
    os.symlink(outside, repo / "linked")
    os.symlink(outside, repo / "docs" / "alink")
    pid = pid_of(conn, "app")
    with pytest.raises(ChanchiError) as info:
        inventory.add_item_dir(conn, pid, repo, path)
    assert info.value.code == "invalid_value" and info.value.field == "path"
    assert inventory.item_dirs(conn, pid) == []


def test_remove_item_dir(conn, tmp_path):
    repo = git_project(tmp_path, conn, "app")
    (repo / "docs").mkdir()
    pid = pid_of(conn, "app")
    inventory.add_item_dir(conn, pid, repo, "docs")
    assert inventory.remove_item_dir(conn, pid, "docs") == {"path": "docs", "removed": True}
    assert inventory.item_dirs(conn, pid) == []
    with pytest.raises(ChanchiError) as info:
        inventory.remove_item_dir(conn, pid, "docs")
    assert info.value.code == "invalid_value" and info.value.field == "path"


# --- project items-dirs (CLI) --------------------------------------------------------


@pytest.fixture
def one_project(conn, tmp_path, monkeypatch):
    repo = git_project(tmp_path, conn, "app")
    (repo / "docs" / "agents").mkdir(parents=True)
    monkeypatch.chdir(repo)
    return repo


def test_cli_items_dirs_lists_defaults_then_adds_and_removes(one_project, capsys):
    listed = run(capsys, "project", "items-dirs")
    assert listed["project"] == "app" and listed["dirs"] == []
    assert listed["defaults"] == list(inventory.DEFAULT_ROOTS)
    added = run(capsys, "project", "items-dirs", "--add", "docs/agents")
    assert added["added"] is True and added["dirs"] == ["docs/agents"]
    again = run(capsys, "project", "items-dirs", "--add", "docs/agents")
    assert again["added"] is False and again["dirs"] == ["docs/agents"]
    removed = run(capsys, "project", "items-dirs", "--remove", "docs/agents")
    assert removed["removed"] is True and removed["dirs"] == []
    error = run(capsys, "project", "items-dirs", "--remove", "docs/agents", expect=2)["error"]
    assert error["code"] == "invalid_value" and error["field"] == "path"


def test_cli_items_dirs_refuses_both_flags_and_bad_paths(one_project, capsys):
    assert run(capsys, "project", "items-dirs", "--add", "a", "--remove", "a", expect=2)["error"]["code"] == "invalid_value"
    error = run(capsys, "project", "items-dirs", "--add", "../x", expect=2)["error"]
    assert error["code"] == "invalid_value" and error["field"] == "path"


def test_cli_items_dirs_project_flag_overrides_the_working_directory(one_project, tmp_path, monkeypatch, capsys):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert run(capsys, "project", "items-dirs", expect=2)["error"]["code"] == "project_not_registered"
    assert run(capsys, "project", "items-dirs", "--project", "app")["project"] == "app"
    error = run(capsys, "project", "items-dirs", "--project", "nope", expect=2)["error"]
    assert error["code"] == "project_not_registered"


def test_cli_items_dirs_needs_an_existing_root_to_add(one_project, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    shutil.rmtree(one_project)
    error = run(capsys, "project", "items-dirs", "--project", "app", "--add", "docs/agents", expect=2)["error"]
    assert error["code"] == "missing_prerequisite"
    assert run(capsys, "project", "items-dirs", "--project", "app")["dirs"] == []


# --- frontmatter ---------------------------------------------------------------------


def test_frontmatter_reads_name_and_description():
    text = "---\nname: tool-x\ndescription: Does the thing.\nversion: 1\n---\nbody\n"
    assert inventory.frontmatter(text) == {"name": "tool-x", "description": "Does the thing."}
    assert inventory.description(text) == "Does the thing."


@pytest.mark.parametrize("marker", [">", ">-", "|", "|-", ""])
def test_frontmatter_joins_block_values_with_single_spaces(marker):
    text = f"---\nname: t\ndescription: {marker}\n  First line\n\n    second line\nother: x\n---\n"
    assert inventory.description(text) == "First line second line"


def test_frontmatter_strips_one_pair_of_quotes_and_ignores_comments():
    text = "---\n# generated by chanchi agents sync\nname: 'q'\ndescription: \"He said 'hi'\"\n---\n"
    assert inventory.frontmatter(text) == {"name": "q", "description": "He said 'hi'"}


def test_frontmatter_tolerates_crlf_and_a_bom():
    text = "﻿---\r\nname: t\r\ndescription: >\r\n  a\r\n  b\r\n---\r\n"
    assert inventory.frontmatter(text) == {"name": "t", "description": "a b"}


@pytest.mark.parametrize(
    "text",
    ["", "no frontmatter\n", "---\nname: x\nnever closed\n", "---\n---\n", "---\nname:\ndescription:\n---\n"],
)
def test_frontmatter_never_raises_and_returns_none_for_absent_values(text):
    assert inventory.frontmatter(text) == {"name": None, "description": None}


def test_frontmatter_ignores_nested_keys():
    text = "---\nmetadata:\n  name: nested\n  description: nested\n---\n"
    assert inventory.frontmatter(text) == {"name": None, "description": None}


# --- walk ----------------------------------------------------------------------------


def paths(found):
    return sorted((i["kind"], i["name"], i["path"]) for i in found)


def test_walk_finds_nested_skills_and_agents_and_stores_each_path_once(tmp_path):
    put(tmp_path, ".claude/skills/workflow/tool-x/SKILL.md", skill_text("tool-x"))
    put(tmp_path, "agents/skills/tool-x/SKILL.md", skill_text("tool-x"))
    put(tmp_path, "agents/reviewer/AGENT.md", "---\nname: reviewer\ndescription: R.\n---\nbody\n")
    put(tmp_path, ".claude/agents/helper.md", "no frontmatter\n")
    found, skipped = inventory.walk(tmp_path, [*inventory.DEFAULT_ROOTS, "agents/skills"])
    assert paths(found) == [
        ("agent", "helper", ".claude/agents/helper.md"),
        ("agent", "reviewer", "agents/reviewer"),
        ("skill", "tool-x", ".claude/skills/workflow/tool-x"),
        ("skill", "tool-x", "agents/skills/tool-x"),
    ]
    assert skipped == []


def test_walk_name_falls_back_to_the_folder_or_the_file_stem(tmp_path):
    put(tmp_path, ".agents/skills/no-name/SKILL.md", "---\ndescription: d\n---\n")
    put(tmp_path, ".agents/skills/empty-name/SKILL.md", "---\nname:\n---\n")
    put(tmp_path, ".opencode/agents/stem.md", "---\nname: \"\"\n---\n")
    found, _ = inventory.walk(tmp_path, list(inventory.DEFAULT_ROOTS))
    assert paths(found) == [
        ("agent", "stem", ".opencode/agents/stem.md"),
        ("skill", "empty-name", ".agents/skills/empty-name"),
        ("skill", "no-name", ".agents/skills/no-name"),
    ]


def test_walk_fingerprint_is_the_content_hash_and_the_line_count(tmp_path):
    folder = put(tmp_path, ".claude/skills/t/SKILL.md", skill_text("t", body=5)).parent
    put(tmp_path, ".claude/skills/t/references/extra.md", "extra\n")
    put(tmp_path, ".claude/agents/a.md", "---\nname: a\n---\nline\n")
    found, _ = inventory.walk(tmp_path, list(inventory.DEFAULT_ROOTS))
    by_path = {i["path"]: i for i in found}
    skill = by_path[".claude/skills/t"]
    assert skill["sha256"] == items.content_hash(folder)
    assert skill["lines"] == len((folder / "SKILL.md").read_text().splitlines())
    assert skill["description"] == "Does the thing."
    import hashlib

    single = by_path[".claude/agents/a.md"]
    assert single["sha256"] == hashlib.sha256((tmp_path / ".claude/agents/a.md").read_bytes()).hexdigest()
    assert single["lines"] == 4 and single["description"] is None


def test_walk_does_not_descend_into_an_item_and_skips_hidden_and_node_modules(tmp_path):
    put(tmp_path, ".claude/skills/outer/SKILL.md", skill_text("outer"))
    put(tmp_path, ".claude/skills/outer/inner/SKILL.md", skill_text("inner"))
    put(tmp_path, ".claude/skills/node_modules/x/SKILL.md", skill_text("x"))
    put(tmp_path, ".claude/skills/.hidden/SKILL.md", skill_text("h"))
    put(tmp_path, ".claude/skills/cat/.draft/SKILL.md", skill_text("d"))
    found, skipped = inventory.walk(tmp_path, list(inventory.DEFAULT_ROOTS))
    assert paths(found) == [("skill", "outer", ".claude/skills/outer")]
    assert skipped == []


def test_walk_depth_limit_is_four_directory_levels_below_the_root(tmp_path):
    put(tmp_path, ".claude/skills/a/b/c/d/SKILL.md", skill_text("four"))
    put(tmp_path, ".claude/skills/a/b/c/d2/e/SKILL.md", skill_text("five"))
    found, _ = inventory.walk(tmp_path, list(inventory.DEFAULT_ROOTS))
    assert paths(found) == [("skill", "four", ".claude/skills/a/b/c/d")]


def test_walk_skips_links_generated_wrappers_and_unreadable_files(tmp_path):
    outside = tmp_path / "outside" / "skill-chanchi-verify"
    put(outside, "SKILL.md", skill_text("skill-chanchi-verify"))
    root = tmp_path / "proj"
    put(root, "agents/reviewer/AGENT.md", "---\nname: reviewer\n---\nbody\n")
    put(root, ".claude/agents/reviewer.md",
        "---\n# generated by chanchi agents sync from agents/reviewer/AGENT.md; do not edit\nname: reviewer\n---\n")
    put(root, ".agents/agents/reviewer/agent.md",
        "---\n# generated by chanchi agents sync from agents/reviewer/AGENT.md; do not edit\nname: reviewer\n---\n")
    put(root, ".agents/agents/planner/agent.md", "---\nname: planner\ndescription: P.\n---\nbody\n")
    put(root, ".claude/skills/bad/SKILL.md", data=b"---\nname: bad\n---\n\xff\xfe broken\n")
    os.symlink(outside, root / ".claude/skills/skill-chanchi-verify")
    os.symlink(outside / "SKILL.md", root / ".claude/agents/linked.md")
    put(root, ".claude/skills/inner-link/SKILL.md", skill_text("inner-link"))
    os.symlink(outside, root / ".claude/skills/inner-link/extra")
    real_main = put(root, ".opencode/skills/main-link/real.md", "x")
    os.symlink(real_main, root / ".opencode/skills/main-link/SKILL.md")
    found, skipped = inventory.walk(root, list(inventory.DEFAULT_ROOTS))
    assert paths(found) == [
        ("agent", "planner", ".agents/agents/planner"),
        ("agent", "reviewer", "agents/reviewer"),
    ]
    assert sorted((s["path"], s["reason"]) for s in skipped) == [
        (".agents/agents/reviewer", "generated"),
        (".claude/agents/linked.md", "symlink"),
        (".claude/agents/reviewer.md", "generated"),
        (".claude/skills/bad", "unreadable"),
        (".claude/skills/inner-link", "symlink"),
        (".claude/skills/skill-chanchi-verify", "symlink"),
        (".opencode/skills/main-link", "symlink"),
    ]


def test_walk_never_enters_a_linked_ancestor_of_a_root(tmp_path):
    outside = tmp_path / "outside"
    put(outside, "skills/x/SKILL.md", skill_text("x"))
    root = tmp_path / "proj"
    root.mkdir()
    os.symlink(outside, root / ".claude")
    found, skipped = inventory.walk(root, list(inventory.DEFAULT_ROOTS))
    assert found == []
    assert {(s["path"], s["reason"]) for s in skipped} == {
        (".claude/skills", "symlink"), (".claude/agents", "symlink")}


def test_walk_never_enters_a_linked_root(tmp_path):
    outside = tmp_path / "outside"
    put(outside, "x/SKILL.md", skill_text("x"))
    root = tmp_path / "proj"
    (root / ".agents").mkdir(parents=True)
    os.symlink(outside, root / ".agents/skills")
    found, skipped = inventory.walk(root, list(inventory.DEFAULT_ROOTS))
    assert found == [] and skipped == [{"path": ".agents/skills", "reason": "symlink"}]


def test_walk_compares_names_exactly(tmp_path):
    put(tmp_path, ".claude/skills/lower/skill.md", skill_text("lower"))
    put(tmp_path, ".claude/agents/Upper.MD", "x\n")
    found, _ = inventory.walk(tmp_path, list(inventory.DEFAULT_ROOTS))
    assert found == []


def test_agent_md_counts_only_directly_under_agents_agents(tmp_path):
    put(tmp_path, ".agents/agents/planner/agent.md", "---\nname: planner\n---\n")
    put(tmp_path, ".agents/skills/s/agent.md", "---\nname: not-an-agent\n---\n")
    put(tmp_path, "agents/deep/er/agent.md", "---\nname: not-an-agent\n---\n")
    found, _ = inventory.walk(tmp_path, list(inventory.DEFAULT_ROOTS))
    assert paths(found) == [("agent", "planner", ".agents/agents/planner")]


# --- scan ----------------------------------------------------------------------------


@pytest.fixture
def world(conn, tmp_path):
    """Projects A and B as in the plan, plus project C whose .claude is a link."""
    a = git_project(tmp_path, conn, "project-a")
    put(a, ".agents/skills/workflow/tool-x/SKILL.md", skill_text("tool-x", "Canonical tool-x.", body=30))
    put(a, ".claude/skills/workflow/tool-x/SKILL.md", skill_text("tool-x", "Stub.", body=2))
    put(a, ".claude/agents/helper.md", "---\ndescription: Helps.\n---\nHelp.\n")
    outside = tmp_path / "outside" / "skill-chanchi-verify"
    put(outside, "SKILL.md", skill_text("skill-chanchi-verify"))
    os.symlink(outside, a / ".claude/skills/skill-chanchi-verify")

    b = git_project(tmp_path, conn, "project-b")
    put(b, "agents/skills/tool-x/SKILL.md",
        "---\nname: tool-x\ndescription: >-\n  Run tool-x on a\n  project and report.\n---\n\n# tool-x\n\nBody.\n")
    put(b, "agents/reviewer/AGENT.md", "---\nname: reviewer\ndescription: Reviews.\n---\n\nReview.\n")
    gen = "---\n# generated by chanchi agents sync from agents/reviewer/AGENT.md; do not edit\nname: reviewer\n---\n"
    put(b, ".claude/agents/reviewer.md", gen)
    put(b, ".agents/agents/reviewer/agent.md", gen)
    put(b, ".agents/agents/planner/agent.md", "---\nname: planner\ndescription: Plans.\n---\nPlan.\n")
    put(b, ".claude/skills/node_modules/x/SKILL.md", skill_text("x"))
    put(b, ".claude/skills/.hidden/SKILL.md", skill_text("h"))

    c = git_project(tmp_path, conn, "project-c")
    put(tmp_path / "c-outside", "skills/leak/SKILL.md", skill_text("leak"))
    os.symlink(tmp_path / "c-outside", c / ".claude")
    return {"a": a, "b": b, "c": c, "root": tmp_path}


def by_slug(result):
    return {p["project"]: p for p in result["projects"]}


def test_scan_records_every_item_of_every_registered_project(conn, world):
    result = inventory.scan(conn, now="2026-11-22T10:00:00Z")
    assert result["missing"] == []
    summary = by_slug(result)
    assert set(summary) == {"project-a", "project-b", "project-c"}
    assert summary["project-a"]["root"] == str(world["a"])

    a = rows(conn, "project-a")
    assert {(r["kind"], r["name"], p) for p, r in a.items()} == {
        ("skill", "tool-x", ".agents/skills/workflow/tool-x"),
        ("skill", "tool-x", ".claude/skills/workflow/tool-x"),
        ("agent", "helper", ".claude/agents/helper.md"),
    }
    assert summary["project-a"]["skipped"] == [{"path": ".claude/skills/skill-chanchi-verify", "reason": "symlink"}]
    assert (summary["project-a"]["items"], summary["project-a"]["added"]) == (3, 3)
    canonical = a[".agents/skills/workflow/tool-x"]
    assert canonical["sha256"] == items.content_hash(world["a"] / ".agents/skills/workflow/tool-x")
    assert canonical["lines"] == len((world["a"] / ".agents/skills/workflow/tool-x/SKILL.md").read_text().splitlines())
    assert canonical["description"] == "Canonical tool-x." and canonical["scanned_at"] == "2026-11-22T10:00:00Z"

    b = rows(conn, "project-b")
    assert {(r["kind"], r["name"], p) for p, r in b.items()} == {
        ("skill", "tool-x", "agents/skills/tool-x"),
        ("agent", "reviewer", "agents/reviewer"),
        ("agent", "planner", ".agents/agents/planner"),
    }
    assert b["agents/skills/tool-x"]["description"] == "Run tool-x on a project and report."
    assert sorted((s["path"], s["reason"]) for s in summary["project-b"]["skipped"]) == [
        (".agents/agents/reviewer", "generated"), (".claude/agents/reviewer.md", "generated")]

    assert rows(conn, "project-c") == {}
    assert {(s["path"], s["reason"]) for s in summary["project-c"]["skipped"]} == {
        (".claude/skills", "symlink"), (".claude/agents", "symlink")}
    assert inventory.project_item_names(conn) == ["helper", "planner", "reviewer", "tool-x"]


def test_a_second_scan_changes_nothing(conn, world):
    inventory.scan(conn, now="2026-11-22T10:00:00Z")
    before = {s: rows(conn, s) for s in ("project-a", "project-b")}
    again = inventory.scan(conn, now="2026-11-22T11:00:00Z")
    for project in again["projects"]:
        assert (project["added"], project["changed"], project["removed"]) == (0, 0, 0)
    assert again["projects"][0]["items"] == 3
    for slug, before_rows in before.items():
        after_rows = rows(conn, slug)
        assert set(after_rows) == set(before_rows)
        for path, row in after_rows.items():
            assert row["scanned_at"] == "2026-11-22T11:00:00Z"
            assert {k: v for k, v in row.items() if k != "scanned_at"} == {
                k: v for k, v in before_rows[path].items() if k != "scanned_at"}


def test_scan_reports_an_edit_as_one_changed_row_and_a_deletion_as_one_removed_row(conn, world):
    inventory.scan(conn)
    old = rows(conn, "project-a")[".claude/agents/helper.md"]["sha256"]
    put(world["a"], ".claude/agents/helper.md", "---\ndescription: Helps more.\n---\nHelp.\nMore.\n")
    result = by_slug(inventory.scan(conn))["project-a"]
    assert (result["added"], result["changed"], result["removed"]) == (0, 1, 0)
    row = rows(conn, "project-a")[".claude/agents/helper.md"]
    assert row["sha256"] != old and row["description"] == "Helps more." and row["lines"] == 5

    shutil.rmtree(world["a"] / ".claude/skills/workflow")
    result = by_slug(inventory.scan(conn))["project-a"]
    assert (result["added"], result["changed"], result["removed"]) == (0, 0, 1)
    assert ".claude/skills/workflow/tool-x" not in rows(conn, "project-a")


def test_scan_picks_up_a_new_item_and_a_registered_item_dir(conn, world):
    inventory.scan(conn)
    put(world["a"], "docs/agents/extra/SKILL.md", skill_text("extra"))
    assert by_slug(inventory.scan(conn))["project-a"]["added"] == 0
    inventory.add_item_dir(conn, pid_of(conn, "project-a"), world["a"], "docs/agents")
    result = by_slug(inventory.scan(conn))["project-a"]
    assert result["added"] == 1 and "docs/agents/extra" in rows(conn, "project-a")


def test_an_item_dir_that_overlaps_a_default_root_stores_each_path_once(conn, world):
    inventory.add_item_dir(conn, pid_of(conn, "project-b"), world["b"], "agents/skills")
    result = by_slug(inventory.scan(conn))["project-b"]
    assert result["items"] == 3 and result["added"] == 3


def test_scan_keeps_the_rows_of_a_project_whose_root_is_gone(conn, world):
    inventory.scan(conn)
    kept = rows(conn, "project-b")
    shutil.rmtree(world["b"])
    result = inventory.scan(conn)
    assert result["missing"] == ["project-b"]
    assert "project-b" not in by_slug(result)
    assert rows(conn, "project-b") == kept


def test_scan_project_limits_the_scan(conn, world):
    result = inventory.scan(conn, project="project-b")
    assert [p["project"] for p in result["projects"]] == ["project-b"]
    assert rows(conn, "project-a") == {}
    with pytest.raises(ChanchiError) as info:
        inventory.scan(conn, project="nope")
    assert info.value.code == "project_not_registered"


def test_scan_ignores_unregistered_projects(conn, world):
    other = world["root"] / "stray"
    other.mkdir()
    conn.execute("INSERT INTO projects (slug, path, created_at) VALUES ('stray', ?, 't')", (str(other),))
    put(other, ".claude/skills/s/SKILL.md", skill_text("s"))
    result = inventory.scan(conn)
    assert "stray" not in by_slug(result) and result["missing"] == []


def test_scan_never_writes_into_a_project(conn, world):
    before = snapshot(world["a"], world["b"], world["c"], world["root"] / "outside", world["root"] / "c-outside")
    inventory.scan(conn)
    inventory.scan(conn)
    assert snapshot(world["a"], world["b"], world["c"], world["root"] / "outside", world["root"] / "c-outside") == before


def test_scan_keeps_a_failed_project_transaction_atomic(conn, world, monkeypatch):
    inventory.scan(conn, now="2026-11-22T10:00:00Z")
    before = rows(conn, "project-a")
    put(world["a"], ".claude/agents/new.md", "x\n")
    shutil.rmtree(world["a"] / ".claude/skills/workflow")
    real = conn.execute

    class Boom:
        def __getattr__(self, name):
            return getattr(conn, name)

        def execute(self, sql, *args):
            if sql.startswith("DELETE FROM project_items"):
                raise RuntimeError("boom")
            return real(sql, *args)

    with pytest.raises(RuntimeError):
        inventory.scan(Boom(), project="project-a")
    assert rows(conn, "project-a") == before


# --- scan (CLI) ----------------------------------------------------------------------


def test_cli_items_scan_twice_and_with_project(conn, world, capsys):
    first = run(capsys, "items", "scan")
    summary = by_slug(first)
    assert summary["project-a"]["added"] == 3 and summary["project-b"]["added"] == 3
    second = run(capsys, "items", "scan")
    assert all((p["added"], p["changed"], p["removed"]) == (0, 0, 0) for p in second["projects"])
    only = run(capsys, "items", "scan", "--project", "project-a")
    assert [p["project"] for p in only["projects"]] == ["project-a"]
    error = run(capsys, "items", "scan", "--project", "nope", expect=2)["error"]
    assert error["code"] == "project_not_registered"


def test_cli_items_scan_does_not_need_sync(conn, world, capsys, monkeypatch):
    monkeypatch.setenv("CHANCHI_SYNC", str(world["root"] / "no-sync"))
    assert run(capsys, "items", "scan")["missing"] == []


def test_the_operational_database_is_at_the_latest_version(conn):
    assert db.user_version(conn) == db.latest_version() >= 6
