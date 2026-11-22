"""Item proposals: `items propose`, `items proposals`, `items proposal-status` and `promotion.toml`.

Design: docs/designs/global-items.md, "C. Propose" and "Data model (migration 006)".
"""

import json
import os
import shutil
import subprocess

import pytest

from chanchi import cli, inventory, projects
from chanchi.errors import ChanchiError

CONFIG = {"min_uses": 3, "vendored_share": 0.5}
T1 = "2026-11-22T10:00:00Z"
T2 = "2026-11-22T11:00:00Z"
T3 = "2026-11-22T12:00:00Z"

# --- helpers -------------------------------------------------------------------------


def git_project(tmp_path, conn, name):
    """A temporary git repository registered on the scratch database."""
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    projects.register(conn, repo)
    return repo.resolve()


def put(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def doc(name, description, *, tag, before, shared, after):
    """A skill main file whose only lines in common with another `doc` are the `shared` ones."""
    lines = ["---", f"name: {name}", f"description: {description}", "---", ""]
    lines += [f"{tag} before {i}" for i in range(before)]
    lines += [f"shared {i}" for i in range(shared)]
    lines += [f"{tag} after {i}" for i in range(after)]
    return "\n".join(lines) + "\n"


def vendored(name, tag, *, before=5):
    """55 lines for `before=5`: 40 shared lines starting at line `before + 6` (1-based)."""
    return doc(name, f"{tag} copy.", tag=tag, before=before, shared=40, after=5)


def independent(name, tag):
    """About 53 lines of which only 8 are shared with `vendored`: below the default share."""
    return doc(name, f"{tag} copy.", tag=tag, before=20, shared=8, after=20)


def skill_text(name, description="Does the thing.", body=3):
    lines = "\n".join(f"Step {i}." for i in range(body))
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{lines}\n"


def pid_of(conn, slug):
    return conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()["id"]


def lesson(conn, slug, target, *, status="approved", generality="agnostic", target_kind="skill"):
    reviewed = None if status == "pending" else T1
    cursor = conn.execute(
        "INSERT INTO lessons (origin_project_id, author_role, author_agent, author_model_raw, "
        "author_conversation, target_kind, target, what_happened, evidence, cause, prevention, "
        "proposal, general_rule, generality, severity, status, reviewed_at, created_at, updated_at) "
        "VALUES (?, 'planner', 'claude', 'opus', 'c1', ?, ?, 'w', 'e', 'c', 'p', 'pr', 'g', ?, 'low', ?, ?, ?, ?)",
        (pid_of(conn, slug), target_kind, target, generality, status, reviewed, T1, T1),
    )
    return cursor.lastrowid


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


def propose(conn, *, now=T1, config=CONFIG, own=(), owner_promote=None):
    return inventory.propose(conn, own_names=list(own), config=config, owner_promote=owner_promote, now=now)


def by_name(result):
    return {p["name"]: p for p in result["proposals"]}


def stored(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM item_proposals ORDER BY id")]


@pytest.fixture
def world(conn, tmp_path):
    """Project A (canonical + stub tool-x), B (vendored tool-x), C (release-verify) on a scanned database."""
    a = git_project(tmp_path, conn, "project-a")
    put(a, ".agents/skills/tool-x/SKILL.md", vendored("tool-x", "a"))
    put(a, ".claude/skills/tool-x/SKILL.md", skill_text("tool-x", "Stub.", body=2))
    put(a, ".agents/skills/deploy-check/SKILL.md", doc(
        "deploy-check", "Verify release artifacts before deploy completes successfully.",
        tag="a", before=3, shared=0, after=25))
    b = git_project(tmp_path, conn, "project-b")
    put(b, "agents/skills/tool-x/SKILL.md", vendored("tool-x", "b", before=7))
    c = git_project(tmp_path, conn, "project-c")
    put(c, ".claude/skills/release-verify/SKILL.md", doc(
        "release-verify", "Verify release artifacts before deploy completes safely.",
        tag="c", before=3, shared=0, after=10))
    inventory.scan(conn, now=T1)
    return {"a": a, "b": b, "c": c, "root": tmp_path}


def scan(conn):
    inventory.scan(conn, now=T1)


# --- longest_shared_block ------------------------------------------------------------


def test_longest_shared_block_returns_zero_based_starts_and_the_size():
    a = ["x", "a", "b", "c", "y"]
    b = ["q", "q", "a", "b", "c", "z"]
    assert inventory.longest_shared_block(a, b) == (1, 2, 3)


def test_longest_shared_block_prefers_the_longest_of_several():
    a = ["a", "b", "x", "p", "q", "r", "s"]
    b = ["p", "q", "r", "s", "x", "a", "b"]
    assert inventory.longest_shared_block(a, b) == (3, 0, 4)


def test_longest_shared_block_of_unrelated_or_empty_lists_has_size_zero():
    assert inventory.longest_shared_block(["a", "b"], ["c", "d"])[2] == 0
    assert inventory.longest_shared_block([], ["a"])[2] == 0
    assert inventory.longest_shared_block(["a"], [])[2] == 0
    assert inventory.longest_shared_block([], [])[2] == 0


# --- same name -----------------------------------------------------------------------


def test_same_name_in_two_projects_is_one_candidate_and_vendored_copies_count_once(conn, world):
    result = propose(conn)
    assert sorted(by_name(result)) == [
        "skill-chanchi-global-deploy-check", "skill-chanchi-global-tool-x"]
    p = by_name(result)["skill-chanchi-global-tool-x"]
    assert (p["kind"], p["status"], p["uses"], p["eligible"], p["owner_promoted"]) == ("skill", "open", 1, False, False)
    ev = p["evidence"]
    assert ev["rules"] == ["same_name"]
    assert ev["clusters"] == [["project-a:.agents/skills/tool-x", "project-b:agents/skills/tool-x"]]
    assert ev["lessons"] == []
    assert (ev["min_uses"], ev["vendored_share"]) == (3, 0.5)
    [pair] = ev["pairs"]
    assert pair["a"] == "project-a:.agents/skills/tool-x" and pair["b"] == "project-b:agents/skills/tool-x"
    assert (pair["block_lines"], pair["a_start"], pair["b_start"]) == (40, 11, 13)
    assert pair["share"] == pytest.approx(40 / 55)


def test_the_stub_copy_is_an_alias_never_the_canonical_copy(conn, world):
    ev = by_name(propose(conn))["skill-chanchi-global-tool-x"]["evidence"]
    copies = {c["project"]: c for c in ev["copies"]}
    assert sorted(copies) == ["project-a", "project-b"]
    a = copies["project-a"]
    assert (a["kind"], a["name"], a["path"], a["lines"]) == ("skill", "tool-x", ".agents/skills/tool-x", 55)
    assert a["aliases"] == [".claude/skills/tool-x"]
    assert len(a["sha256"]) == 64
    assert copies["project-b"]["aliases"] == []


def test_equal_line_counts_choose_the_shortest_path_then_the_alphabetical_one(conn, tmp_path):
    a = git_project(tmp_path, conn, "project-a")
    for rel in (".claude/skills/zz/tool-x", ".agents/skills/tool-x", ".claude/skills/aa/tool-x"):
        put(a, f"{rel}/SKILL.md", skill_text("tool-x", "Same.", body=4))
    b = git_project(tmp_path, conn, "project-b")
    put(b, "agents/skills/tool-x/SKILL.md", skill_text("tool-x", "Same.", body=4))
    scan(conn)
    copies = by_name(propose(conn))["skill-chanchi-global-tool-x"]["evidence"]["copies"]
    first = copies[0]
    assert first["path"] == ".agents/skills/tool-x"
    assert first["aliases"] == [".claude/skills/aa/tool-x", ".claude/skills/zz/tool-x"]


def test_copies_below_the_vendored_share_are_independent_uses(conn, world):
    put(world["b"], "agents/skills/tool-x/SKILL.md", independent("tool-x", "b"))
    scan(conn)
    p = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    assert p["uses"] == 2 and p["eligible"] is False
    assert p["evidence"]["clusters"] == [["project-a:.agents/skills/tool-x"], ["project-b:agents/skills/tool-x"]]
    [pair] = p["evidence"]["pairs"]
    assert pair["block_lines"] == 8 and pair["share"] < 0.5


def test_min_uses_two_makes_two_independent_uses_eligible(conn, world):
    put(world["b"], "agents/skills/tool-x/SKILL.md", independent("tool-x", "b"))
    scan(conn)
    p = by_name(propose(conn, config={"min_uses": 2, "vendored_share": 0.5}))["skill-chanchi-global-tool-x"]
    assert p["uses"] == 2 and p["eligible"] is True
    assert (p["evidence"]["min_uses"], p["evidence"]["vendored_share"]) == (2, 0.5)


def test_vendored_share_decides_which_copies_join(conn, world):
    # 40 shared lines of 55: share 0.727 joins at 0.5 and 0.7 but not at 0.8.
    strict = by_name(propose(conn, config={"min_uses": 3, "vendored_share": 0.8}))["skill-chanchi-global-tool-x"]
    assert strict["uses"] == 2
    exact = by_name(propose(conn, config={"min_uses": 3, "vendored_share": 40 / 55}))["skill-chanchi-global-tool-x"]
    assert exact["uses"] == 1


def test_vendored_copies_are_joined_transitively_across_three_projects(conn, world):
    put(world["c"], "agents/tool-x/SKILL.md", vendored("tool-x", "c", before=9))
    scan(conn)
    p = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    assert p["uses"] == 1
    assert len(p["evidence"]["clusters"]) == 1 and len(p["evidence"]["clusters"][0]) == 3
    assert len(p["evidence"]["pairs"]) == 3


def test_a_third_independent_copy_makes_the_candidate_eligible(conn, world):
    put(world["c"], "agents/tool-x/SKILL.md", independent("tool-x", "c"))
    scan(conn)
    p = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    assert p["uses"] == 2  # a and b are one vendored use, c is independent
    put(world["b"], "agents/skills/tool-x/SKILL.md", independent("tool-x", "b"))
    scan(conn)
    p = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    assert p["uses"] == 3 and p["eligible"] is True


def test_an_empty_main_file_shares_nothing(conn, world):
    put(world["b"], "agents/skills/tool-x/SKILL.md", "")
    scan(conn)
    p = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    [pair] = p["evidence"]["pairs"]
    assert (pair["block_lines"], pair["share"]) == (0, 0.0)
    assert p["uses"] == 2


# --- names that are never candidates -------------------------------------------------


def test_a_name_in_only_one_project_is_not_a_candidate(conn, world):
    put(world["a"], ".agents/skills/solo/SKILL.md", skill_text("solo", "Only here."))
    scan(conn)
    assert "skill-chanchi-global-solo" not in by_name(propose(conn))


@pytest.mark.parametrize(
    "name",
    ["skill-chanchi-verify", "agent-chanchi-auditor", "skill-chanchi-global-foo", "skill-chanchi-app-foo",
     "agent-chanchi-global-bar", "x-chanchi-global-y", "my-own"],
)
def test_chanchi_names_and_given_own_names_are_never_candidates(conn, tmp_path, name):
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    for repo in (a, b):
        put(repo, f".agents/skills/{name}/SKILL.md", skill_text(name))
    scan(conn)
    result = propose(conn, own=["my-own"])
    assert result["proposals"] == [] and result["skipped_names"] == []


def test_names_are_compared_by_slug(conn, tmp_path):
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    put(a, ".agents/skills/x/SKILL.md", skill_text("tool_x"))
    put(b, ".agents/skills/y/SKILL.md", skill_text("Tool-X"))
    scan(conn)
    [p] = propose(conn)["proposals"]
    assert p["name"] == "skill-chanchi-global-tool-x"
    assert sorted(c["name"] for c in p["evidence"]["copies"]) == ["Tool-X", "tool_x"]


def test_a_name_with_an_empty_slug_is_listed_and_never_a_candidate(conn, tmp_path):
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    put(a, ".agents/skills/x/SKILL.md", skill_text("___"))
    put(b, ".agents/skills/y/SKILL.md", skill_text("___"))
    scan(conn)
    result = propose(conn)
    assert result["proposals"] == []
    assert result["skipped_names"] == [
        {"project": "project-a", "kind": "skill", "name": "___"},
        {"project": "project-b", "kind": "skill", "name": "___"},
    ]


def test_the_same_name_with_different_kinds_is_not_a_candidate(conn, tmp_path):
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    put(a, ".agents/skills/helper/SKILL.md", skill_text("helper"))
    put(b, ".claude/agents/helper.md", "---\nname: helper\ndescription: Helps.\n---\nHelp.\n")
    scan(conn)
    assert propose(conn)["proposals"] == []


def test_agents_with_the_same_name_make_an_agent_candidate(conn, tmp_path):
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    put(a, ".claude/agents/helper.md", "---\nname: helper\ndescription: Helps.\n---\nHelp.\n")
    put(b, "agents/helper/AGENT.md", "---\nname: helper\ndescription: Helps.\n---\nHelp more.\n")
    scan(conn)
    [p] = propose(conn)["proposals"]
    assert (p["kind"], p["name"]) == ("agent", "agent-chanchi-global-helper")
    assert sorted(c["path"] for c in p["evidence"]["copies"]) == [".claude/agents/helper.md", "agents/helper"]


def test_hook_and_rule_inventory_rows_are_never_copies(conn, tmp_path):
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    scan(conn)
    for repo in (a, b):
        conn.execute(
            "INSERT INTO project_items (project_id, kind, name, path, sha256, lines, description, scanned_at) "
            "VALUES (?, 'hook', 'guard', 'hooks/guard', ?, 3, NULL, ?)",
            (pid_of(conn, repo.name), "0" * 64, T1),
        )
    assert propose(conn)["proposals"] == []


# --- description overlap -------------------------------------------------------------


def test_description_overlap_makes_a_candidate_named_after_the_longer_copy(conn, world):
    p = by_name(propose(conn))["skill-chanchi-global-deploy-check"]
    assert p["evidence"]["rules"] == ["description_overlap"]
    assert sorted(c["name"] for c in p["evidence"]["copies"]) == ["deploy-check", "release-verify"]
    assert p["uses"] == 2  # two different texts: two clusters
    assert "skill-chanchi-global-release-verify" not in by_name(propose(conn))


@pytest.mark.parametrize(
    "other",
    [
        "Verify release artifacts.",  # under 5 tokens
        "Verify release notes changelog entries published.",  # Jaccard below 0.5
    ],
)
def test_description_overlap_needs_five_tokens_and_a_jaccard_of_half(conn, world, other):
    put(world["c"], ".claude/skills/release-verify/SKILL.md", doc(
        "release-verify", other, tag="c", before=3, shared=0, after=10))
    scan(conn)
    assert "skill-chanchi-global-deploy-check" not in by_name(propose(conn))


def test_description_overlap_needs_different_projects(conn, world):
    shutil.rmtree(world["c"] / ".claude")
    put(world["a"], ".claude/skills/release-verify/SKILL.md", doc(
        "release-verify", "Verify release artifacts before deploy completes safely.",
        tag="a", before=3, shared=0, after=10))
    scan(conn)
    assert "skill-chanchi-global-deploy-check" not in by_name(propose(conn))


def test_description_overlap_needs_the_same_kind(conn, world):
    shutil.rmtree(world["c"] / ".claude")
    put(world["c"], ".claude/agents/release-verify.md",
        "---\nname: release-verify\ndescription: Verify release artifacts before deploy completes safely.\n---\nGo.\n")
    scan(conn)
    assert propose(conn)["proposals"][0]["name"] == "skill-chanchi-global-tool-x"
    assert "skill-chanchi-global-deploy-check" not in by_name(propose(conn))


def test_description_overlap_skips_copies_already_in_a_same_name_candidate(conn, world):
    put(world["b"], "agents/skills/deploy-check/SKILL.md", doc(
        "deploy-check", "Something else entirely about unrelated matters.", tag="b", before=3, shared=0, after=5))
    scan(conn)
    result = by_name(propose(conn))
    p = result["skill-chanchi-global-deploy-check"]
    assert p["evidence"]["rules"] == ["same_name"]
    assert sorted(c["project"] for c in p["evidence"]["copies"]) == ["project-a", "project-b"]


def test_description_overlap_groups_are_transitive(conn, world):
    put(world["b"], "agents/skills/ship-check/SKILL.md", doc(
        "ship-check", "Verify release artifacts before deploy completes properly.", tag="b", before=3, shared=0, after=40))
    scan(conn)
    p = by_name(propose(conn))["skill-chanchi-global-ship-check"]
    assert sorted(c["name"] for c in p["evidence"]["copies"]) == ["deploy-check", "release-verify", "ship-check"]


# --- lessons -------------------------------------------------------------------------


def test_two_agnostic_approved_lessons_from_two_projects_make_a_candidate(conn, world):
    one = lesson(conn, "project-a", "skill tool-y (new)")
    two = lesson(conn, "project-b", "skill tool-y (new)")
    p = by_name(propose(conn))["skill-chanchi-global-tool-y"]
    assert (p["kind"], p["uses"], p["eligible"]) == ("skill", 2, False)
    assert p["evidence"]["rules"] == ["lessons"]
    assert p["evidence"]["copies"] == [] and p["evidence"]["clusters"] == []
    assert p["evidence"]["lessons"] == [
        {"id": one, "project": "project-a", "status": "approved"},
        {"id": two, "project": "project-b", "status": "approved"},
    ]


def test_pending_lessons_create_the_candidate_but_add_no_use(conn, world):
    lesson(conn, "project-a", "skill tool-y", status="pending")
    lesson(conn, "project-b", "Skill TOOL-Y (new)", status="approved")
    p = by_name(propose(conn))["skill-chanchi-global-tool-y"]
    assert p["uses"] == 1
    assert [x["status"] for x in p["evidence"]["lessons"]] == ["pending", "approved"]
    lesson(conn, "project-c", "skill tool-y", status="pending")
    assert by_name(propose(conn))["skill-chanchi-global-tool-y"]["uses"] == 1


def test_only_pending_lessons_make_a_candidate_with_no_uses(conn, world):
    lesson(conn, "project-a", "skill tool-y", status="pending")
    lesson(conn, "project-b", "skill tool-y", status="pending")
    assert by_name(propose(conn))["skill-chanchi-global-tool-y"]["uses"] == 0


@pytest.mark.parametrize(
    "second",
    [
        {"slug": "project-a"},  # one project only
        {"slug": "project-b", "generality": "project"},
        {"slug": "project-b", "target_kind": "hook"},
        {"slug": "project-b", "status": "rejected"},
        {"slug": "project-b", "status": "postponed"},
        {"slug": "project-b", "target": "skill tool y"},  # not a single name
        {"slug": "project-b", "target": "hook tool-y"},
    ],
)
def test_lessons_that_do_not_qualify_make_no_candidate(conn, world, second):
    lesson(conn, "project-a", "skill tool-y")
    slug = second.pop("slug")
    target = second.pop("target", "skill tool-y")
    lesson(conn, slug, target, **second)
    assert "skill-chanchi-global-tool-y" not in by_name(propose(conn))


@pytest.mark.parametrize("target", ["skill skill-chanchi-verify", "skill a-chanchi-global-b", "agent agent-chanchi-auditor",
                                    "skill my-own", "role skill-chanchi-x"])
def test_lessons_naming_chanchi_or_own_items_make_no_candidate(conn, world, target):
    kind = "role" if target.startswith(("role", "agent")) else "skill"
    lesson(conn, "project-a", target, target_kind=kind)
    lesson(conn, "project-b", target, target_kind=kind)
    proposals = propose(conn, own=["my-own"])["proposals"]
    assert sorted(p["name"] for p in proposals) == [
        "skill-chanchi-global-deploy-check", "skill-chanchi-global-tool-x"]
    assert all("lessons" not in p["evidence"]["rules"] for p in proposals)


def test_lessons_naming_the_same_skill_join_the_same_name_candidate(conn, world):
    lesson(conn, "project-a", "skill tool-x")
    lesson(conn, "project-b", "skill tool-x (new)")
    p = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    assert p["evidence"]["rules"] == ["same_name", "lessons"]
    assert p["uses"] == 3 and p["eligible"] is True  # one vendored cluster + two approved lessons
    assert len(p["evidence"]["lessons"]) == 2


def test_lessons_naming_a_role_form_their_own_agent_candidate(conn, world):
    lesson(conn, "project-a", "role tool-x", target_kind="role")
    lesson(conn, "project-b", "agent tool-x", target_kind="role")
    result = by_name(propose(conn))
    assert result["skill-chanchi-global-tool-x"]["evidence"]["rules"] == ["same_name"]
    p = result["agent-chanchi-global-tool-x"]
    assert (p["kind"], p["uses"], p["evidence"]["rules"]) == ("agent", 2, ["lessons"])


def test_lessons_join_a_description_overlap_candidate_only_by_its_name(conn, world):
    lesson(conn, "project-a", "skill deploy-check")
    lesson(conn, "project-b", "skill deploy-check")
    lesson(conn, "project-a", "skill release-verify")
    lesson(conn, "project-c", "skill release-verify")
    result = by_name(propose(conn))
    assert result["skill-chanchi-global-deploy-check"]["evidence"]["rules"] == ["description_overlap", "lessons"]
    # the shorter copy's own name is not the candidate's name: its lessons are a candidate of their own
    assert result["skill-chanchi-global-release-verify"]["evidence"]["rules"] == ["lessons"]


def test_a_lesson_without_an_origin_project_does_not_count(conn, world):
    lesson(conn, "project-a", "skill tool-y")
    other = lesson(conn, "project-b", "skill tool-y")
    conn.execute("UPDATE lessons SET origin_project_id = NULL WHERE id = ?", (other,))
    assert "skill-chanchi-global-tool-y" not in by_name(propose(conn))


# --- storage -------------------------------------------------------------------------


def test_a_second_run_updates_the_same_row(conn, world):
    first = by_name(propose(conn, now=T1))["skill-chanchi-global-tool-x"]
    put(world["b"], "agents/skills/tool-x/SKILL.md", independent("tool-x", "b"))
    scan(conn)
    second = by_name(propose(conn, now=T2))["skill-chanchi-global-tool-x"]
    assert second["id"] == first["id"]
    assert (second["created_at"], second["updated_at"]) == (T1, T2)
    assert (first["uses"], second["uses"]) == (1, 2)
    rows = [r for r in stored(conn) if r["name"] == "skill-chanchi-global-tool-x"]
    assert len(rows) == 1 and rows[0]["uses"] == 2 and rows[0]["status"] == "open"
    assert json.loads(rows[0]["evidence"])["clusters"] == second["evidence"]["clusters"]


def test_an_unchanged_second_run_keeps_the_ids_and_the_evidence(conn, world):
    first = propose(conn, now=T1)
    second = propose(conn, now=T2)
    assert [p["id"] for p in first["proposals"]] == [p["id"] for p in second["proposals"]]
    assert len(stored(conn)) == 2
    assert [p["evidence"] for p in first["proposals"]] == [p["evidence"] for p in second["proposals"]]


def test_owner_promotion_sets_the_flag_and_makes_the_candidate_eligible_for_good(conn, world):
    p = by_name(propose(conn, owner_promote="skill-chanchi-global-tool-x"))["skill-chanchi-global-tool-x"]
    assert p["owner_promoted"] is True and p["eligible"] is True and p["uses"] == 1
    again = by_name(propose(conn, now=T2))["skill-chanchi-global-tool-x"]
    assert again["owner_promoted"] is True and again["eligible"] is True
    other = by_name(propose(conn, now=T2))["skill-chanchi-global-deploy-check"]
    assert other["owner_promoted"] is False


def test_owner_promotion_of_an_unknown_candidate_is_refused_and_stores_nothing(conn, world):
    with pytest.raises(ChanchiError) as exc:
        propose(conn, owner_promote="skill-chanchi-global-nope")
    assert exc.value.code == "invalid_value" and exc.value.field == "owner_promote"
    assert stored(conn) == []


def test_a_closed_candidate_is_listed_under_closed_and_not_stored_again(conn, world, tmp_path):
    first = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    sync_root = tmp_path / "SYNC"
    (sync_root / "ITEMS/skills/skill-chanchi-global-tool-x").mkdir(parents=True)
    inventory.set_proposal_status(conn, sync_root, first["id"], status="built", global_item="skill-chanchi-global-tool-x")
    again = propose(conn, now=T2)
    assert again["closed"] == [{
        "id": first["id"], "kind": "skill", "name": "skill-chanchi-global-tool-x",
        "status": "built", "global_item": "skill-chanchi-global-tool-x"}]
    assert [p["name"] for p in again["proposals"]] == ["skill-chanchi-global-deploy-check"]
    assert len([r for r in stored(conn) if r["name"] == "skill-chanchi-global-tool-x"]) == 1
    with pytest.raises(ChanchiError) as exc:
        propose(conn, owner_promote="skill-chanchi-global-tool-x")
    assert exc.value.field == "owner_promote"


def test_a_rejected_candidate_is_closed_too(conn, world):
    first = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    inventory.set_proposal_status(conn, None, first["id"], status="rejected")
    again = propose(conn, now=T2)
    assert [(c["name"], c["status"], c["global_item"]) for c in again["closed"]] == [
        ("skill-chanchi-global-tool-x", "rejected", None)]


def test_an_open_row_this_run_did_not_produce_is_listed_and_left_unchanged(conn, world):
    first = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    before = [r for r in stored(conn) if r["id"] == first["id"]]
    shutil.rmtree(world["b"] / "agents")
    scan(conn)
    result = propose(conn, now=T2)
    assert result["not_found"] == [{"id": first["id"], "kind": "skill", "name": "skill-chanchi-global-tool-x"}]
    assert [r for r in stored(conn) if r["id"] == first["id"]] == before


def test_propose_with_no_candidates_stores_nothing(conn, tmp_path):
    git_project(tmp_path, conn, "project-a")
    result = propose(conn)
    assert result == {"proposals": [], "closed": [], "not_found": [], "missing": [], "skipped_names": [],
                      "min_uses": 3, "vendored_share": 0.5}
    assert stored(conn) == []


def test_unregistered_projects_are_not_read(conn, world):
    conn.execute("UPDATE projects SET registered_at = NULL WHERE slug = 'project-b'")
    assert "skill-chanchi-global-tool-x" not in by_name(propose(conn))


# --- proposal-status -----------------------------------------------------------------


@pytest.fixture
def sync_root(tmp_path):
    root = tmp_path / "SYNC"
    (root / "ITEMS/skills/skill-chanchi-global-tool-x").mkdir(parents=True)
    (root / "ITEMS/agents/agent-chanchi-global-tool-x").mkdir(parents=True)
    (root / "ITEMS/skills/skill-chanchi-global-draft").mkdir(parents=True)
    return root


def open_id(conn, name="skill-chanchi-global-tool-x"):
    return by_name(propose(conn))[name]["id"]


def test_built_links_the_proposal_to_its_global_item(conn, world, sync_root):
    pid = open_id(conn)
    result = inventory.set_proposal_status(
        conn, sync_root, pid, status="built", global_item="skill-chanchi-global-tool-x")
    assert (result["id"], result["status"], result["global_item"]) == (pid, "built", "skill-chanchi-global-tool-x")
    [row] = [r for r in stored(conn) if r["id"] == pid]
    assert (row["status"], row["global_item"]) == ("built", "skill-chanchi-global-tool-x")


def test_built_accepts_a_global_item_of_any_name_of_the_same_kind(conn, world, sync_root):
    pid = open_id(conn)
    inventory.set_proposal_status(conn, sync_root, pid, status="built", global_item="skill-chanchi-global-draft")
    assert [r["global_item"] for r in stored(conn) if r["id"] == pid] == ["skill-chanchi-global-draft"]


@pytest.mark.parametrize(
    "global_item, field",
    [
        ("skill-chanchi-global-missing", "global_item"),
        ("agent-chanchi-global-tool-x", "global_item"),  # another kind
        ("tool-x", "global_item"),
        ("skill-chanchi-tool-x", "global_item"),
        (None, "global_item"),
    ],
)
def test_built_refuses_a_missing_or_wrong_global_item(conn, world, sync_root, global_item, field):
    pid = open_id(conn)
    with pytest.raises(ChanchiError) as exc:
        inventory.set_proposal_status(conn, sync_root, pid, status="built", global_item=global_item)
    assert exc.value.code == "invalid_value" and exc.value.field == field
    assert [r["status"] for r in stored(conn) if r["id"] == pid] == ["open"]


def test_built_needs_sync(conn, world):
    pid = open_id(conn)
    with pytest.raises(ChanchiError) as exc:
        inventory.set_proposal_status(conn, None, pid, status="built", global_item="skill-chanchi-global-tool-x")
    assert exc.value.code == "missing_prerequisite" and exc.value.hint == "chanchi sync init"


def test_rejected_works_without_sync_and_refuses_a_global_item(conn, world, sync_root):
    pid = open_id(conn)
    with pytest.raises(ChanchiError) as exc:
        inventory.set_proposal_status(conn, None, pid, status="rejected", global_item="skill-chanchi-global-tool-x")
    assert exc.value.code == "invalid_value" and exc.value.field == "global_item"
    result = inventory.set_proposal_status(conn, None, pid, status="rejected")
    assert (result["status"], result["global_item"]) == ("rejected", None)
    assert [r["status"] for r in stored(conn) if r["id"] == pid] == ["rejected"]


@pytest.mark.parametrize("first", ["built", "rejected"])
@pytest.mark.parametrize("second", ["built", "rejected"])
def test_a_built_or_rejected_row_never_changes(conn, world, sync_root, first, second):
    pid = open_id(conn)
    item = "skill-chanchi-global-tool-x"
    inventory.set_proposal_status(conn, sync_root, pid, status=first, global_item=item if first == "built" else None)
    before = [r for r in stored(conn) if r["id"] == pid]
    with pytest.raises(ChanchiError) as exc:
        inventory.set_proposal_status(conn, sync_root, pid, status=second, global_item=item if second == "built" else None)
    assert exc.value.code == "invalid_transition"
    assert [r for r in stored(conn) if r["id"] == pid] == before


def test_proposal_status_refuses_an_unknown_id_and_a_bad_status(conn, world, sync_root):
    with pytest.raises(ChanchiError) as exc:
        inventory.set_proposal_status(conn, sync_root, 999, status="rejected")
    assert exc.value.code == "invalid_value" and exc.value.field == "id"
    pid = open_id(conn)
    for status in ("open", "nope", None):
        with pytest.raises(ChanchiError) as exc:
            inventory.set_proposal_status(conn, sync_root, pid, status=status)
        assert exc.value.code == "invalid_value" and exc.value.field == "status"
        assert exc.value.valid_values == ["built", "rejected"]


# --- freshness -----------------------------------------------------------------------


def test_an_edit_after_the_scan_makes_propose_fail_and_store_nothing(conn, world):
    put(world["a"], ".agents/skills/tool-x/notes.md", "added after the scan\n")
    with pytest.raises(ChanchiError) as exc:
        propose(conn)
    assert exc.value.code == "missing_prerequisite"
    assert exc.value.hint == "chanchi items scan"
    assert exc.value.details["stale"] == [
        {"project": "project-a", "path": ".agents/skills/tool-x", "reason": "changed"}]
    assert stored(conn) == []


def test_a_rescan_clears_the_stale_state(conn, world):
    put(world["a"], ".agents/skills/tool-x/notes.md", "added after the scan\n")
    scan(conn)
    assert "skill-chanchi-global-tool-x" in by_name(propose(conn))


def test_a_vanished_copy_is_stale_with_reason_missing(conn, world):
    shutil.rmtree(world["a"] / ".agents/skills/tool-x")
    with pytest.raises(ChanchiError) as exc:
        propose(conn)
    assert exc.value.details["stale"] == [
        {"project": "project-a", "path": ".agents/skills/tool-x", "reason": "missing"}]


def test_a_copy_replaced_by_a_link_is_stale_with_reason_symlink(conn, world):
    target = world["root"] / "elsewhere"
    shutil.copytree(world["a"] / ".agents/skills/tool-x", target)
    shutil.rmtree(world["a"] / ".agents/skills/tool-x")
    os.symlink(target, world["a"] / ".agents/skills/tool-x")
    with pytest.raises(ChanchiError) as exc:
        propose(conn)
    assert exc.value.details["stale"] == [
        {"project": "project-a", "path": ".agents/skills/tool-x", "reason": "symlink"}]


def test_a_copy_behind_a_linked_ancestor_is_stale_with_reason_symlink(conn, world):
    target = world["root"] / "agents-skills"
    shutil.copytree(world["b"] / "agents/skills", target)
    shutil.rmtree(world["b"] / "agents/skills")
    os.symlink(target, world["b"] / "agents/skills")
    with pytest.raises(ChanchiError) as exc:
        propose(conn)
    assert exc.value.details["stale"] == [
        {"project": "project-b", "path": "agents/skills/tool-x", "reason": "symlink"}]


def test_a_main_file_that_stops_being_utf8_is_stale(conn, world):
    (world["a"] / ".agents/skills/tool-x/SKILL.md").write_bytes(b"\xff\xfe broken\n")
    with pytest.raises(ChanchiError) as exc:
        propose(conn)
    assert exc.value.details["stale"] == [
        {"project": "project-a", "path": ".agents/skills/tool-x", "reason": "unreadable"}]


def test_every_stale_copy_is_listed(conn, world):
    put(world["a"], ".agents/skills/tool-x/notes.md", "x\n")
    put(world["b"], "agents/skills/tool-x/notes.md", "y\n")
    with pytest.raises(ChanchiError) as exc:
        propose(conn)
    assert [(s["project"], s["reason"]) for s in exc.value.details["stale"]] == [
        ("project-a", "changed"), ("project-b", "changed")]


def test_an_alias_that_changed_is_not_stale_because_it_is_not_counted(conn, world):
    put(world["a"], ".claude/skills/tool-x/notes.md", "alias edit\n")
    assert "skill-chanchi-global-tool-x" in by_name(propose(conn))


def test_a_copy_outside_every_candidate_is_not_checked(conn, world):
    put(world["a"], ".agents/skills/solo/SKILL.md", skill_text("solo"))
    scan(conn)
    put(world["a"], ".agents/skills/solo/notes.md", "x\n")
    assert "skill-chanchi-global-tool-x" in by_name(propose(conn))


def test_a_missing_root_leaves_its_copies_out_and_stores_the_rest(conn, world):
    shutil.rmtree(world["b"])
    result = propose(conn)
    assert result["missing"] == ["project-b"]
    assert sorted(by_name(result)) == ["skill-chanchi-global-deploy-check"]
    assert [r["name"] for r in stored(conn)] == ["skill-chanchi-global-deploy-check"]


def test_a_single_file_agent_is_fingerprinted_from_its_file(conn, tmp_path):
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    put(a, ".claude/agents/helper.md", "---\nname: helper\ndescription: Helps.\n---\nHelp.\n")
    put(b, ".opencode/agents/helper.md", "---\nname: helper\ndescription: Helps.\n---\nHelp.\n")
    scan(conn)
    assert [p["name"] for p in propose(conn)["proposals"]] == ["agent-chanchi-global-helper"]
    (a / ".claude/agents/helper.md").write_text("---\nname: helper\n---\nchanged\n")
    with pytest.raises(ChanchiError) as exc:
        propose(conn)
    assert exc.value.details["stale"] == [{"project": "project-a", "path": ".claude/agents/helper.md", "reason": "changed"}]


# --- printed shape and proposals -----------------------------------------------------

SHAPE = {"id", "kind", "name", "status", "uses", "owner_promoted", "eligible", "global_item",
         "created_at", "updated_at", "evidence"}
EVIDENCE = {"rules", "copies", "pairs", "clusters", "lessons", "min_uses", "vendored_share"}


def test_propose_and_proposals_print_the_same_shape(conn, world):
    proposed = by_name(propose(conn))["skill-chanchi-global-tool-x"]
    assert set(proposed) == SHAPE and set(proposed["evidence"]) == EVIDENCE
    assert isinstance(proposed["evidence"], dict)
    listed = {p["name"]: p for p in inventory.proposals(conn, config=CONFIG)}
    assert set(listed["skill-chanchi-global-tool-x"]) == SHAPE
    assert listed["skill-chanchi-global-tool-x"] == proposed
    [single] = inventory.proposals(conn, config=CONFIG, proposal_id=proposed["id"])
    assert set(single) == SHAPE and isinstance(single["evidence"], dict)


def test_proposals_filter_by_status_and_are_ordered_by_id(conn, world):
    ids = [p["id"] for p in propose(conn)["proposals"]]
    assert [p["id"] for p in inventory.proposals(conn, config=CONFIG)] == sorted(ids)
    inventory.set_proposal_status(conn, None, ids[0], status="rejected")
    assert [p["id"] for p in inventory.proposals(conn, config=CONFIG, status="open")] == ids[1:]
    assert [p["id"] for p in inventory.proposals(conn, config=CONFIG, status="rejected")] == ids[:1]
    assert inventory.proposals(conn, config=CONFIG, status="built") == []


def test_eligible_is_computed_with_the_current_config(conn, world):
    pid = open_id(conn)
    [loose] = inventory.proposals(conn, config={"min_uses": 1, "vendored_share": 0.5}, proposal_id=pid)
    [strict] = inventory.proposals(conn, config=CONFIG, proposal_id=pid)
    assert (loose["eligible"], strict["eligible"]) == (True, False)


def test_proposals_refuses_an_unknown_id_a_bad_status_and_both_together(conn, world):
    pid = open_id(conn)
    with pytest.raises(ChanchiError) as exc:
        inventory.proposals(conn, config=CONFIG, proposal_id=999)
    assert exc.value.code == "invalid_value" and exc.value.field == "id"
    with pytest.raises(ChanchiError) as exc:
        inventory.proposals(conn, config=CONFIG, proposal_id=pid, status="open")
    assert exc.value.code == "invalid_value"
    with pytest.raises(ChanchiError) as exc:
        inventory.proposals(conn, config=CONFIG, status="nope")
    assert exc.value.field == "status" and exc.value.valid_values == ["open", "built", "rejected"]


def test_proposals_with_an_id_resolve_absolute_paths_at_print_time(conn, world):
    pid = open_id(conn)
    [one] = inventory.proposals(conn, config=CONFIG, proposal_id=pid)
    copies = {c["project"]: c for c in one["evidence"]["copies"]}
    assert copies["project-a"]["abs_path"] == str(world["a"] / ".agents/skills/tool-x")
    assert copies["project-a"]["alias_abs_paths"] == [str(world["a"] / ".claude/skills/tool-x")]
    assert copies["project-b"]["abs_path"] == str(world["b"] / "agents/skills/tool-x")
    assert copies["project-b"]["alias_abs_paths"] == []
    [plain] = [p for p in inventory.proposals(conn, config=CONFIG) if p["id"] == pid]
    assert "abs_path" not in plain["evidence"]["copies"][0]


def test_abs_path_is_null_when_the_root_is_missing(conn, world):
    pid = open_id(conn)
    shutil.rmtree(world["b"])
    [one] = inventory.proposals(conn, config=CONFIG, proposal_id=pid)
    copies = {c["project"]: c for c in one["evidence"]["copies"]}
    assert copies["project-b"]["abs_path"] is None and copies["project-b"]["alias_abs_paths"] == []
    assert copies["project-a"]["abs_path"] is not None


def test_abs_path_is_null_for_every_alias_when_the_root_is_missing(conn, world):
    pid = open_id(conn)
    shutil.rmtree(world["a"])
    [one] = inventory.proposals(conn, config=CONFIG, proposal_id=pid)
    copies = {c["project"]: c for c in one["evidence"]["copies"]}
    assert copies["project-a"]["abs_path"] is None
    assert copies["project-a"]["alias_abs_paths"] == [None]


# --- read-only on projects -----------------------------------------------------------


def test_propose_and_proposals_never_write_into_a_project(conn, world):
    outside = world["root"] / "outside"
    put(outside, "skills/leak/SKILL.md", skill_text("leak"))
    os.symlink(outside, world["c"] / ".agents-linked")
    roots = (world["a"], world["b"], world["c"], outside)
    before = snapshot(*roots)
    propose(conn)
    propose(conn, owner_promote="skill-chanchi-global-tool-x", now=T2)
    inventory.proposals(conn, config=CONFIG, proposal_id=1)
    assert snapshot(*roots) == before


# --- CLI -----------------------------------------------------------------------------


def test_cli_propose_proposals_and_proposal_status(conn, world, capsys, monkeypatch):
    monkeypatch.setenv("CHANCHI_SYNC", str(world["root"] / "no-sync"))
    out = run(capsys, "items", "propose")
    names = [p["name"] for p in out["proposals"]]
    assert names == ["skill-chanchi-global-deploy-check", "skill-chanchi-global-tool-x"]
    assert (out["closed"], out["not_found"], out["missing"], out["skipped_names"]) == ([], [], [], [])
    assert (out["min_uses"], out["vendored_share"]) == (3, 0.5)
    pid = {p["name"]: p["id"] for p in out["proposals"]}["skill-chanchi-global-tool-x"]

    listed = run(capsys, "items", "proposals")["proposals"]
    assert [p["id"] for p in listed] == sorted(p["id"] for p in out["proposals"])
    assert [p["name"] for p in run(capsys, "items", "proposals", "--status", "open")["proposals"]] == names
    [one] = run(capsys, "items", "proposals", "--id", str(pid))["proposals"]
    assert one["evidence"]["copies"][0]["abs_path"].endswith(".agents/skills/tool-x")

    refused = run(capsys, "items", "proposals", "--id", str(pid), "--status", "open", expect=2)["error"]
    assert refused["code"] == "invalid_value"
    assert run(capsys, "items", "proposals", "--id", "999", expect=2)["error"]["field"] == "id"

    # `rejected` works without SYNC and refuses a global item
    with_item = run(capsys, "items", "proposal-status", str(pid), "--status", "rejected",
                    "--global-item", "skill-chanchi-global-tool-x", expect=2)["error"]
    assert (with_item["code"], with_item["field"]) == ("invalid_value", "global_item")
    done = run(capsys, "items", "proposal-status", str(pid), "--status", "rejected")
    assert (done["id"], done["status"], done["global_item"]) == (pid, "rejected", None)
    again = run(capsys, "items", "proposal-status", str(pid), "--status", "rejected", expect=2)["error"]
    assert again["code"] == "invalid_transition"
    after = run(capsys, "items", "propose")
    assert [c["id"] for c in after["closed"]] == [pid]


def test_cli_proposal_status_built_needs_sync_and_an_existing_item(conn, world, capsys, monkeypatch, sync_root):
    pid = open_id(conn)
    monkeypatch.setenv("CHANCHI_SYNC", str(world["root"] / "no-sync"))
    error = run(capsys, "items", "proposal-status", str(pid), "--status", "built",
                "--global-item", "skill-chanchi-global-tool-x", expect=2)["error"]
    assert error["code"] == "missing_prerequisite" and error["hint"] == "chanchi sync init"
    monkeypatch.setenv("CHANCHI_SYNC", str(sync_root))
    error = run(capsys, "items", "proposal-status", str(pid), "--status", "built", expect=2)["error"]
    assert (error["code"], error["field"]) == ("invalid_value", "global_item")
    done = run(capsys, "items", "proposal-status", str(pid), "--status", "built",
               "--global-item", "skill-chanchi-global-tool-x")
    assert (done["status"], done["global_item"]) == ("built", "skill-chanchi-global-tool-x")


def test_cli_propose_owner_promote_and_promotion_toml(conn, world, capsys, monkeypatch, sync_root):
    monkeypatch.setenv("CHANCHI_SYNC", str(sync_root))
    (sync_root / "config").mkdir()
    (sync_root / "config" / "promotion.toml").write_text("min_uses = 1\nvendored_share = 0.9\n", encoding="utf-8")
    out = run(capsys, "items", "propose")
    assert (out["min_uses"], out["vendored_share"]) == (1, 0.9)
    tool = {p["name"]: p for p in out["proposals"]}["skill-chanchi-global-tool-x"]
    assert tool["uses"] == 2 and tool["eligible"] is True
    (sync_root / "config" / "promotion.toml").write_text("min_uses = 5\n", encoding="utf-8")
    promoted = run(capsys, "items", "propose", "--owner-promote", "skill-chanchi-global-tool-x")
    tool = {p["name"]: p for p in promoted["proposals"]}["skill-chanchi-global-tool-x"]
    assert (tool["owner_promoted"], tool["eligible"]) == (True, True)
    refused = run(capsys, "items", "propose", "--owner-promote", "skill-chanchi-global-nope", expect=2)["error"]
    assert (refused["code"], refused["field"]) == ("invalid_value", "owner_promote")
    listed = run(capsys, "items", "proposals")["proposals"]
    assert {p["name"]: p["eligible"] for p in listed}["skill-chanchi-global-tool-x"] is True


def test_cli_propose_refuses_a_broken_promotion_file_before_touching_anything(conn, world, capsys, monkeypatch, sync_root):
    monkeypatch.setenv("CHANCHI_SYNC", str(sync_root))
    (sync_root / "config").mkdir()
    (sync_root / "config" / "promotion.toml").write_text("min_uses = 0\n", encoding="utf-8")
    error = run(capsys, "items", "propose", expect=2)["error"]
    assert (error["code"], error["field"]) == ("invalid_value", "promotion")
    assert stored(conn) == []


def test_cli_propose_reports_stale_copies(conn, world, capsys, monkeypatch):
    monkeypatch.setenv("CHANCHI_SYNC", str(world["root"] / "no-sync"))
    put(world["a"], ".agents/skills/tool-x/notes.md", "late\n")
    error = run(capsys, "items", "propose", expect=2)["error"]
    assert error["code"] == "missing_prerequisite" and error["hint"] == "chanchi items scan"
    assert error["details"]["stale"][0]["project"] == "project-a"


def test_cli_propose_excludes_chanchi_s_own_items(conn, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("CHANCHI_SYNC", str(tmp_path / "no-sync"))
    a = git_project(tmp_path, conn, "project-a")
    b = git_project(tmp_path, conn, "project-b")
    for repo in (a, b):
        put(repo, ".agents/skills/skill-chanchi-verify/SKILL.md", skill_text("skill-chanchi-verify"))
        put(repo, ".agents/skills/plain/SKILL.md", skill_text("plain"))
    scan(conn)
    out = run(capsys, "items", "propose")
    assert [p["name"] for p in out["proposals"]] == ["skill-chanchi-global-plain"]
