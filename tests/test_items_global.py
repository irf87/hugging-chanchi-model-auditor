"""Global items in SYNC/ITEMS: frontmatter, content hash, check, list, audits, publish and retire."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from chanchi import audits, catalog, cli, items, sync
from chanchi.errors import ChanchiError

NAME_SKILL = "skill-chanchi-global-demo"
NAME_AGENT = "agent-chanchi-global-demo"

SKILL = """---
name: {name}
description: Demo skill.
metadata:
  version: "{version}"
  status: "{status}"
---

# Demo

Do the demo work.
"""

AGENT = """---
name: {name}
description: Demo agent.
scope: both
profile: read-only
skills: [skill-chanchi-global-demo]
version: {version}
status: {status}
---

# Demo

State your agent name.
"""

CHANGELOG = "# Changelog\n\n## {version} — 2026-11-22\n\n- First draft.\n"


@pytest.fixture
def root(tmp_path):
    """A SYNC directory with empty ITEMS/agents and ITEMS/skills."""
    base = tmp_path / "SYNC"
    (base / "ITEMS" / "agents").mkdir(parents=True)
    (base / "ITEMS" / "skills").mkdir(parents=True)
    return base


def make_skill(root, name=NAME_SKILL, *, version="0.1.0", status="draft", changelog=True, folder="skills"):
    item = root / "ITEMS" / folder / name
    item.mkdir(parents=True)
    (item / "SKILL.md").write_text(SKILL.format(name=name, version=version, status=status), encoding="utf-8")
    if changelog:
        (item / "CHANGELOG.md").write_text(CHANGELOG.format(version=version), encoding="utf-8")
    return item


def make_agent(root, name=NAME_AGENT, *, version="0.1.0", status="draft", changelog=True):
    item = root / "ITEMS" / "agents" / name
    item.mkdir(parents=True)
    (item / "AGENT.md").write_text(AGENT.format(name=name, version=version, status=status), encoding="utf-8")
    if changelog:
        (item / "CHANGELOG.md").write_text(CHANGELOG.format(version=version), encoding="utf-8")
    return item


def codes(result):
    return sorted((p["item"], p["code"]) for p in result["problems"])


def problems_for(root, *, own=()):
    return items.check(root, own_names=list(own))


def frame(rel: str, data: bytes) -> bytes:
    return rel.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0" + data


# --- frontmatter ------------------------------------------------------------


def test_read_frontmatter_flat_and_metadata_block():
    text = SKILL.format(name=NAME_SKILL, version="1.2.3", status="published")
    assert items.read_frontmatter(text) == {
        "name": NAME_SKILL,
        "description": "Demo skill.",
        "metadata": {"version": "1.2.3", "status": "published"},
    }


def test_read_frontmatter_strips_one_pair_of_quotes():
    text = "---\nname: 'x'\ndescription: \"y\"\nmetadata:\n  version: '1.0.0'\n  status: draft\n---\nbody\n"
    fm = items.read_frontmatter(text)
    assert fm["name"] == "x" and fm["description"] == "y"
    assert fm["metadata"] == {"version": "1.0.0", "status": "draft"}


@pytest.mark.parametrize(
    "text",
    [
        "no frontmatter\n",
        "---\nname x\n---\n",
        "---\nname: x\ndescription: >\n  folded\n---\n",
        "---\nname: x\ndescription: |\n  literal\n---\n",
        "---\nname: x\ndescription: one\n  two\n---\n",
        "---\nname: x\nmetadata:\n  a:\n    b: c\n---\n",
        "---\nname: x\nmetadata: inline\n---\n",
        "---\nname: x\nname: y\n---\n",
        "---\nname: x\n- a\n---\n",
    ],
)
def test_read_frontmatter_rejects_other_shapes(text):
    with pytest.raises(ChanchiError) as exc:
        items.read_frontmatter(text)
    assert exc.value.code == "invalid_value" and exc.value.field == "frontmatter"


def test_read_frontmatter_accepts_a_closing_line_at_the_end_of_the_file():
    assert items.read_frontmatter("---\nname: x\n---") == {"name": "x"}


# --- content hash -----------------------------------------------------------


def test_content_hash_matches_hand_computed_framing(root):
    item = root / "ITEMS" / "skills" / NAME_SKILL
    (item / "references").mkdir(parents=True)
    (item / "SKILL.md").write_bytes(b"alpha\n")
    (item / "references" / "a.md").write_bytes(b"\x00bytes\r\n")
    (item / "CHANGELOG.md").write_bytes(b"ignored")
    expected = hashlib.sha256()
    expected.update(b"SKILL.md\x006\x00alpha\n")
    expected.update(b"references/a.md\x008\x00\x00bytes\r\n")
    assert items.content_hash(item) == expected.hexdigest()


def test_content_hash_sorts_by_whole_relative_path(root):
    # `a.txt` sorts before `a/b` as whole paths ('.' < '/'), unlike a directory-first walk.
    item = root / "ITEMS" / "skills" / NAME_SKILL
    (item / "a").mkdir(parents=True)
    (item / "a.txt").write_bytes(b"1")
    (item / "a" / "b").write_bytes(b"22")
    expected = hashlib.sha256()
    expected.update(frame("a.txt", b"1"))
    expected.update(frame("a/b", b"22"))
    assert items.content_hash(item) == expected.hexdigest()


def test_content_hash_ignores_changelog_dotfiles_and_conflict_copies(root):
    item = make_skill(root)
    before = items.content_hash(item)
    (item / "CHANGELOG.md").write_text("changed", encoding="utf-8")
    (item / ".DS_Store").write_bytes(b"x")
    (item / ".hidden").mkdir()
    (item / ".hidden" / "f").write_bytes(b"x")
    (item / "x.icloud").write_bytes(b"x")
    (item / "SKILL (conflicted copy).md").write_bytes(b"x")
    (item / "notes (conflict 2).md").write_bytes(b"x")
    assert items.content_hash(item) == before


def test_content_hash_changes_on_edit_and_on_rename(root):
    item = make_skill(root)
    before = items.content_hash(item)
    (item / "extra.md").write_bytes(b"a")
    with_extra = items.content_hash(item)
    assert with_extra != before
    (item / "extra.md").rename(item / "renamed.md")
    assert items.content_hash(item) not in (before, with_extra)
    (item / "renamed.md").write_bytes(b"b")
    assert items.content_hash(item) != with_extra
    text = (item / "SKILL.md").read_bytes()
    (item / "SKILL.md").write_bytes(text + b" ")
    assert items.content_hash(item) != before


def test_content_hash_refuses_a_symlink(root, tmp_path):
    item = make_skill(root)
    (tmp_path / "outside.md").write_text("x")
    (item / "link.md").symlink_to(tmp_path / "outside.md")
    with pytest.raises(ChanchiError) as exc:
        items.content_hash(item)
    assert exc.value.code == "invalid_value" and exc.value.field == "path"


# --- check ------------------------------------------------------------------


def test_valid_agent_and_skill_pass_with_retired_json_and_dotfiles(root):
    make_skill(root)
    make_agent(root)
    (root / "ITEMS" / "retired.json").write_text("[]\n", encoding="utf-8")
    (root / "ITEMS" / ".DS_Store").write_bytes(b"x")
    (root / "ITEMS" / "skills" / ".DS_Store").write_bytes(b"x")
    result = problems_for(root)
    assert result["problems"] == []
    assert [i.name for i in result["items"]] == [NAME_AGENT, NAME_SKILL]
    skill = next(i for i in result["items"] if i.kind == "skill")
    assert (skill.version, skill.status, skill.published_hash) == ("0.1.0", "draft", None)
    assert skill.hash == items.content_hash(skill.path)


def test_check_on_a_sync_without_items_is_empty(tmp_path):
    (tmp_path / "SYNC").mkdir()
    assert items.check(tmp_path / "SYNC", own_names=[]) == {"items": [], "problems": []}


def test_bad_directory_name(root):
    make_skill(root, "my-skill")
    assert codes(problems_for(root)) == [("my-skill", "bad_name")]


def test_skill_under_agents_folder_is_wrong_folder(root):
    make_skill(root, folder="agents")
    assert codes(problems_for(root)) == [(NAME_SKILL, "wrong_folder")]


def test_frontmatter_name_differs_from_directory(root):
    item = make_skill(root)
    text = (item / "SKILL.md").read_text().replace(f"name: {NAME_SKILL}", "name: skill-chanchi-global-other")
    (item / "SKILL.md").write_text(text)
    assert codes(problems_for(root)) == [(NAME_SKILL, "name_mismatch")]


def test_agent_name_mismatch_is_not_bad_frontmatter(root):
    item = make_agent(root)
    text = (item / "AGENT.md").read_text().replace(f"name: {NAME_AGENT}", "name: agent-chanchi-global-other")
    (item / "AGENT.md").write_text(text)
    assert codes(problems_for(root)) == [(NAME_AGENT, "name_mismatch")]


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0-rc1", ""])
def test_bad_version(root, version):
    make_skill(root, version=version)
    found = codes(problems_for(root))
    assert (NAME_SKILL, "bad_version") in found


def test_bad_status(root):
    make_skill(root, status="live")
    assert codes(problems_for(root)) == [(NAME_SKILL, "bad_status")]


def test_missing_status_line_is_bad_status(root):
    item = make_skill(root)
    text = (item / "SKILL.md").read_text().replace('  status: "draft"\n', "")
    (item / "SKILL.md").write_text(text)
    assert codes(problems_for(root)) == [(NAME_SKILL, "bad_status")]
    agent = make_agent(root)
    text = (agent / "AGENT.md").read_text().replace("status: draft\n", "")
    (agent / "AGENT.md").write_text(text)
    assert (NAME_AGENT, "bad_status") in codes(problems_for(root))


def test_missing_changelog_section_for_the_current_version(root):
    item = make_skill(root, version="0.2.0")
    (item / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0 — 2026-11-01\n\n- old\n")
    assert codes(problems_for(root)) == [(NAME_SKILL, "missing_changelog")]
    (item / "CHANGELOG.md").unlink()
    assert codes(problems_for(root)) == [(NAME_SKILL, "missing_changelog")]


def test_conflict_copy_is_reported(root):
    item = make_skill(root)
    (item / "SKILL (conflicted copy).md").write_text("x")
    (item / "y.icloud").write_text("x")
    found = problems_for(root)["problems"]
    assert [p["code"] for p in found] == ["conflict_copy", "conflict_copy"]
    assert any("SKILL (conflicted copy).md" in p["detail"] for p in found)


def test_retired_json_name_must_be_retired(root):
    make_skill(root)
    (root / "ITEMS" / "retired.json").write_text(
        json.dumps([{"name": NAME_SKILL, "version": "0.1.0", "replaced_by": None, "date": "2026-11-22", "reason": "x"}])
    )
    assert codes(problems_for(root)) == [(NAME_SKILL, "retired_not_retired")]


@pytest.mark.parametrize("raw", ["{not json", '{"a": 1}', "[1, 2]", '[{"version": "1.0.0"}]'])
def test_malformed_retired_json(root, raw):
    make_skill(root)
    (root / "ITEMS" / "retired.json").write_text(raw)
    assert codes(problems_for(root)) == [("retired.json", "bad_retired_json")]


def test_own_item_collision(root):
    make_skill(root)
    assert codes(problems_for(root, own=[NAME_SKILL])) == [(NAME_SKILL, "own_item_collision")]


def test_stray_entries_in_items_and_in_kind_folders(root):
    make_skill(root)
    (root / "ITEMS" / "notes.txt").write_text("x")
    (root / "ITEMS" / "skills" / "README.md").write_text("x")
    assert codes(problems_for(root)) == [("README.md", "unexpected_entry"), ("notes.txt", "unexpected_entry")]


def test_symlink_inside_an_item_is_a_problem_not_an_exception(root, tmp_path):
    item = make_skill(root)
    (tmp_path / "outside.md").write_text("x")
    (item / "link.md").symlink_to(tmp_path / "outside.md")
    result = problems_for(root)
    assert codes(result) == [(NAME_SKILL, "symlink")]
    assert result["items"][0].hash is None


def test_agent_with_unknown_profile_is_bad_frontmatter(root):
    item = make_agent(root)
    text = (item / "AGENT.md").read_text().replace("profile: read-only", "profile: root")
    (item / "AGENT.md").write_text(text)
    assert codes(problems_for(root)) == [(NAME_AGENT, "bad_frontmatter")]


def test_skill_without_or_with_multiline_description_is_bad_frontmatter(root):
    item = make_skill(root)
    (item / "SKILL.md").write_text(
        SKILL.format(name=NAME_SKILL, version="0.1.0", status="draft").replace("description: Demo skill.\n", "")
    )
    assert codes(problems_for(root)) == [(NAME_SKILL, "bad_frontmatter")]
    (item / "SKILL.md").write_text(
        SKILL.format(name=NAME_SKILL, version="0.1.0", status="draft").replace(
            "description: Demo skill.\n", "description: >\n  folded\n  text\n"
        )
    )
    assert codes(problems_for(root)) == [(NAME_SKILL, "bad_frontmatter")]


def test_missing_manifest_file_is_bad_frontmatter(root):
    item = make_skill(root)
    (item / "SKILL.md").unlink()
    assert codes(problems_for(root)) == [(NAME_SKILL, "bad_frontmatter")]


def test_published_item_without_record_or_edited_after_publish(root):
    item = make_skill(root, status="published")
    assert codes(problems_for(root)) == [(NAME_SKILL, "published_without_record")]
    digest = items.content_hash(item)
    changelog = item / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text() + f"\nPublished: 2026-11-22 · audit 1 · audited {'a' * 64} · sha256 {digest}\n"
    )
    assert problems_for(root)["problems"] == []
    (item / "extra.md").write_text("edited")
    assert codes(problems_for(root)) == [(NAME_SKILL, "edited_after_publish")]


def test_retired_item_is_exempt_from_published_checks(root):
    make_skill(root, status="retired")
    assert problems_for(root)["problems"] == []


def test_agent_version_and_status_do_not_change_the_rendered_wrapper(tmp_path):
    from chanchi import agents_sync

    plain = AGENT.replace("version: {version}\nstatus: {status}\n", "").format(name="agent-chanchi-demo")
    versioned = AGENT.format(name="agent-chanchi-demo", version="0.1.0", status="published")
    rendered = []
    for number, text in enumerate((plain, versioned)):
        src = tmp_path / str(number) / "agents" / "agent-chanchi-demo"
        src.mkdir(parents=True)
        (src / "AGENT.md").write_text(text)
        (source,) = agents_sync.load_sources(src.parent)
        rendered.append(agents_sync.render(source))
    assert rendered[0] == rendered[1]
    assert (source.version, source.status) == ("0.1.0", "published")


# --- list ---------------------------------------------------------------------


def test_list_items_reports_fields_and_nulls_for_broken_items(root):
    make_skill(root)
    make_agent(root, version="0.3.0", status="published")
    broken = make_skill(root, "skill-chanchi-global-broken")
    (broken / "SKILL.md").write_text("no frontmatter")
    (root / "ITEMS" / "retired.json").write_text("{not json")
    listed = {row["name"]: row for row in items.list_items(root)}
    assert set(listed) == {NAME_SKILL, NAME_AGENT, "skill-chanchi-global-broken"}
    assert listed[NAME_SKILL]["version"] == "0.1.0" and listed[NAME_SKILL]["status"] == "draft"
    assert listed[NAME_SKILL]["hash"] == items.content_hash(root / "ITEMS" / "skills" / NAME_SKILL)
    assert listed[NAME_AGENT]["kind"] == "agent" and listed[NAME_AGENT]["published_hash"] is None
    row = listed["skill-chanchi-global-broken"]
    assert (row["version"], row["status"]) == (None, None)
    assert all(listed[n]["retired"] is None for n in listed)


def test_list_items_marks_retired_names(root):
    make_skill(root, status="retired")
    make_agent(root)
    (root / "ITEMS" / "retired.json").write_text(
        json.dumps([{"name": NAME_SKILL, "version": "0.1.0", "replaced_by": None, "date": "2026-11-22", "reason": "x"}])
    )
    listed = {row["name"]: row for row in items.list_items(root)}
    assert listed[NAME_SKILL]["retired"] is True and listed[NAME_AGENT]["retired"] is False


def test_list_items_survives_a_symlink(root, tmp_path):
    item = make_skill(root)
    (tmp_path / "o.md").write_text("x")
    (item / "l.md").symlink_to(tmp_path / "o.md")
    (row,) = items.list_items(root)
    assert row["hash"] is None and row["version"] == "0.1.0"


def test_own_names_come_from_the_checkout():
    names = items.own_names()
    assert "agent-chanchi-executor" in names and "skill-chanchi-verify" in names
    assert not any("-chanchi-global-" in n for n in names)


# --- item audits (D6) -----------------------------------------------------------

ALL = ["low", "medium", "high"]


@pytest.fixture
def cat(conn):
    catalog.add_model(conn, agent="claude", model="sonnet", cost_tier=2, efforts=ALL)
    catalog.add_model(conn, agent="agy", model="gemini-4-neon-high", cost_tier=2, efforts=["high"])
    catalog.add_model(conn, agent="opencode", model="opencode-go/minimax-m3", cost_tier=1)
    catalog.add_model(conn, agent="agy", model="gemini-4-hydrogen-high", cost_tier=1, efforts=["high"])
    return conn


def which(name):
    return f"/bin/{name}"


def open_item_audit(conn, root, name=NAME_SKILL, version="0.1.0", **kw):
    return audits.open_audit(
        conn, kind=kw.pop("kind", "item"), ref=name, author="claude:opus:high", version=version,
        roster=sync.BUILTIN_ROSTER, which=which, sync_root=root, **kw,
    )


def vote_all(conn, audit_id, *, round=1, verdict="pass"):
    for seat in (1, 2, 3):
        audits.vote(conn, audit_id, round=round, seat=seat, verdict=verdict, blocking=0, major=0, minor=0,
                    report="fixture")
    return audits.close_round(conn, audit_id, round=round)


def accepted_audit(conn, root, name=NAME_SKILL, version="0.1.0"):
    aid = open_item_audit(conn, root, name, version)["audit_id"]
    assert vote_all(conn, aid)["outcome"] == "accepted"
    return aid


def test_item_audit_records_version_at_hash(cat, root):
    item = make_skill(root)
    result = open_item_audit(cat, root)
    stored = cat.execute("SELECT subject_at FROM audit_rounds WHERE audit_id = ?", (result["audit_id"],)).fetchone()
    assert stored["subject_at"] == f"0.1.0@{items.content_hash(item)}"
    assert items.subject_at(root, NAME_SKILL, "0.1.0") == stored["subject_at"]


def test_item_audit_refusals(cat, root, tmp_path):
    make_skill(root)
    with pytest.raises(ChanchiError) as wrong_version:
        open_item_audit(cat, root, version="0.2.0")
    assert wrong_version.value.code == "invalid_value" and wrong_version.value.field == "version"
    with pytest.raises(ChanchiError) as unknown:
        open_item_audit(cat, root, name="skill-chanchi-global-nope")
    assert unknown.value.code == "invalid_value" and unknown.value.field == "ref"
    with pytest.raises(ChanchiError) as not_global:
        open_item_audit(cat, root, name="skill-chanchi-verify")
    assert not_global.value.field == "ref"
    with pytest.raises(ChanchiError) as commit:
        audits.open_audit(cat, kind="item", ref=NAME_SKILL, author="human", commit="abc123",
                          roster=sync.BUILTIN_ROSTER, which=which, sync_root=root)
    assert commit.value.code == "invalid_value" and commit.value.field == "commit"
    with pytest.raises(ChanchiError) as no_sync:
        audits.open_audit(cat, kind="item", ref=NAME_SKILL, author="human", version="0.1.0",
                          roster=sync.BUILTIN_ROSTER, which=which, sync_root=None)
    assert no_sync.value.code == "missing_prerequisite" and no_sync.value.hint == "chanchi sync init"
    assert cat.execute("SELECT count(*) FROM audits").fetchone()[0] == 0


def test_other_kinds_ignore_sync_root(cat):
    result = audits.open_audit(cat, kind="other", ref="x", author="human", version="9.9.9",
                               roster=sync.BUILTIN_ROSTER, which=which, sync_root=None)
    stored = cat.execute("SELECT subject_at FROM audit_rounds WHERE audit_id = ?", (result["audit_id"],)).fetchone()
    assert stored["subject_at"] == "9.9.9"


def test_next_round_of_an_item_audit_records_the_new_hash(cat, root):
    item = make_skill(root)
    aid = open_item_audit(cat, root)["audit_id"]
    assert vote_all(cat, aid, verdict="fail")["outcome"] == "rework"
    (item / "extra.md").write_text("fix")
    audits.next_round(cat, aid, version="0.1.0", roster=sync.BUILTIN_ROSTER, which=which, sync_root=root)
    subject = cat.execute(
        "SELECT subject_at FROM audit_rounds WHERE audit_id = ? AND round = 2", (aid,)
    ).fetchone()["subject_at"]
    assert subject == f"0.1.0@{items.content_hash(item)}"
    assert vote_all(cat, aid, round=2, verdict="fail")["outcome"] == "rework"
    with pytest.raises(ChanchiError) as wrong:
        audits.next_round(cat, aid, version="0.2.0", roster=sync.BUILTIN_ROSTER, which=which, sync_root=root)
    assert wrong.value.field == "version"


# --- publish (D10, D5) ------------------------------------------------------------


def publish(conn, root, name=NAME_SKILL, audit_id=1, today="2026-11-23", own=()):
    return items.publish(conn, root, name, audit_id=audit_id, own_names=list(own), today=today)


def refused(conn, root, code, **kw):
    with pytest.raises(ChanchiError) as exc:
        publish(conn, root, **kw)
    assert exc.value.code == code, exc.value
    return exc.value


def test_publish_flips_status_records_the_line_and_check_passes(cat, root):
    item = make_skill(root)
    audited = items.content_hash(item)
    aid = accepted_audit(cat, root)
    result = publish(cat, root, audit_id=aid)
    published = items.content_hash(item)
    assert published != audited
    assert result == {"name": NAME_SKILL, "version": "0.1.0", "status": "published", "audit_id": aid,
                      "audited_hash": audited, "hash": published}
    text = (item / "SKILL.md").read_text()
    assert 'status: "published"' in text and 'status: "draft"' not in text
    assert text == SKILL.format(name=NAME_SKILL, version="0.1.0", status="published")
    changelog = (item / "CHANGELOG.md").read_text()
    assert f"Published: 2026-11-23 · audit {aid} · audited {audited} · sha256 {published}" in changelog
    assert changelog.index("## 0.1.0") < changelog.index("Published:")
    assert items.check(root, own_names=[])["problems"] == []
    (row,) = items.list_items(root)
    assert row["status"] == "published" and row["published_hash"] == published


def test_publish_an_agent_keeps_the_unquoted_form(cat, root):
    item = make_agent(root)
    aid = accepted_audit(cat, root, NAME_AGENT)
    publish(cat, root, NAME_AGENT, aid)
    assert (item / "AGENT.md").read_text() == AGENT.format(name=NAME_AGENT, version="0.1.0", status="published")
    assert items.check(root, own_names=[])["problems"] == []


def test_publish_requires_an_audit(cat, root):
    make_skill(root)
    err = refused(cat, root, "unknown_audit", audit_id=99)
    assert err.field == "audit"


def test_publish_refuses_a_design_audit_and_another_items_audit(cat, root):
    make_skill(root)
    make_agent(root)
    design = audits.open_audit(cat, kind="design", ref=NAME_SKILL, author="human", commit="abc",
                               roster=sync.BUILTIN_ROSTER, which=which)["audit_id"]
    vote_all(cat, design)
    assert refused(cat, root, "invalid_value", audit_id=design).field == "audit"
    other = accepted_audit(cat, root, NAME_AGENT)
    assert refused(cat, root, "invalid_value", audit_id=other).field == "audit"


def test_publish_refuses_a_fix_round_and_an_open_round(cat, root):
    make_skill(root)
    aid = open_item_audit(cat, root)["audit_id"]
    err = refused(cat, root, "invalid_transition", audit_id=aid)  # round still open
    assert "round" in err.hint
    for seat, verdict in ((1, "pass_with_fixes"), (2, "pass_with_fixes"), (3, "pass_with_fixes")):
        audits.vote(cat, aid, round=1, seat=seat, verdict=verdict, blocking=0, major=1, minor=0, report="f")
    assert audits.close_round(cat, aid, round=1)["outcome"] == "fix"
    refused(cat, root, "invalid_transition", audit_id=aid)


def test_publish_refuses_an_edit_made_after_the_audit(cat, root):
    item = make_skill(root)
    aid = accepted_audit(cat, root)
    (item / "SKILL.md").write_bytes((item / "SKILL.md").read_bytes() + b".")
    err = refused(cat, root, "invalid_transition", audit_id=aid)
    assert "new round" in err.hint or "new version" in err.hint
    assert 'status: "draft"' in (item / "SKILL.md").read_text()


def test_publish_refuses_an_already_published_item(cat, root):
    make_skill(root)
    aid = accepted_audit(cat, root)
    publish(cat, root, audit_id=aid)
    err = refused(cat, root, "invalid_transition", audit_id=aid)
    assert "draft" in err.hint


def test_publish_refuses_a_retired_item(cat, root):
    make_skill(root)
    aid = accepted_audit(cat, root)
    items.retire(root, NAME_SKILL, reason="obsolete", today="2026-11-23")
    refused(cat, root, "invalid_transition", audit_id=aid)


def test_publish_refuses_a_name_listed_in_retired_json_even_when_draft(cat, root):
    make_skill(root)
    aid = accepted_audit(cat, root)
    (root / "ITEMS" / "retired.json").write_text(
        json.dumps([{"name": NAME_SKILL, "version": "0.1.0", "replaced_by": None, "date": "2026-11-22", "reason": "x"}])
    )
    refused(cat, root, "invalid_transition", audit_id=aid)


def test_publish_unknown_item_and_check_problems(cat, root):
    refused(cat, root, "invalid_value", name="skill-chanchi-global-nope")
    refused(cat, root, "invalid_value", name="not-an-item")
    item = make_skill(root)
    aid = accepted_audit(cat, root)
    text = (item / "SKILL.md").read_text().replace('  status: "draft"\n', "")
    (item / "SKILL.md").write_text(text)
    err = refused(cat, root, "invalid_value", audit_id=aid)
    assert any(p["code"] == "bad_status" for p in err.details["problems"])
    assert "status" not in (item / "SKILL.md").read_text().split("---")[1]


def test_publish_is_blocked_by_a_malformed_retired_json(cat, root):
    make_skill(root)
    aid = accepted_audit(cat, root)
    (root / "ITEMS" / "retired.json").write_text("{not json")
    err = refused(cat, root, "invalid_value", audit_id=aid)
    assert any(p["code"] == "bad_retired_json" for p in err.details["problems"])


def test_publish_second_version_writes_into_its_own_section(cat, root):
    item = make_skill(root, version="0.2.0")
    (item / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.2.0 — 2026-11-22\n\n- Second.\n\n## 0.1.0 — 2026-11-01\n\n- First.\n"
    )
    aid = accepted_audit(cat, root, version="0.2.0")
    audited = items.content_hash(item)
    publish(cat, root, audit_id=aid)
    published = items.content_hash(item)
    changelog = (item / "CHANGELOG.md").read_text()
    line = f"Published: 2026-11-23 · audit {aid} · audited {audited} · sha256 {published}"
    assert changelog == (
        "# Changelog\n\n## 0.2.0 — 2026-11-22\n\n- Second.\n\n" + line + "\n\n## 0.1.0 — 2026-11-01\n\n- First.\n"
    )
    (row,) = items.list_items(root)
    assert row["published_hash"] == published and row["version"] == "0.2.0"
    assert items.check(root, own_names=[])["problems"] == []


def test_publish_inserts_after_a_header_only_section(cat, root):
    item = make_skill(root)
    (item / "CHANGELOG.md").write_text("## 0.1.0 — 2026-11-22\n")
    aid = accepted_audit(cat, root)
    publish(cat, root, audit_id=aid)
    lines = (item / "CHANGELOG.md").read_text().split("\n")
    assert lines[0] == "## 0.1.0 — 2026-11-22" and lines[1] == "" and lines[2].startswith("Published: ")
    assert items.check(root, own_names=[])["problems"] == []


def test_publish_inserts_a_missing_status_line_only_when_total(root):
    # The writers are total: a text with no status line gets one right after version, in the same form.
    skill = SKILL.format(name=NAME_SKILL, version="0.1.0", status="draft").replace('  status: "draft"\n', "")
    assert '  version: "0.1.0"\n  status: "published"\n' in items.set_status(skill, "skill", "published")
    agent = AGENT.format(name=NAME_AGENT, version="0.1.0", status="draft").replace("status: draft\n", "")
    assert "version: 0.1.0\nstatus: published\n" in items.set_status(agent, "agent", "published")


# --- retire (D9) --------------------------------------------------------------------


def test_retire_sets_status_and_appends_an_entry(root):
    item = make_skill(root)
    other = make_skill(root, "skill-chanchi-global-next")
    existing = '[\n  {"name": "skill-chanchi-global-old", "version": "1.0.0",   "replaced_by": null, "date": "2026-01-01", "reason": "hand"}\n]\n'
    (root / "ITEMS" / "retired.json").write_text(existing)
    result = items.retire(root, NAME_SKILL, reason="superseded", replaced_by="skill-chanchi-global-next",
                          today="2026-11-23")
    assert result == {"name": NAME_SKILL, "version": "0.1.0", "status": "retired",
                      "replaced_by": "skill-chanchi-global-next", "reason": "superseded", "date": "2026-11-23"}
    assert 'status: "retired"' in (item / "SKILL.md").read_text()
    raw = (root / "ITEMS" / "retired.json").read_text()
    assert raw.startswith(existing[: existing.rindex("}") + 1])  # earlier entries byte for byte
    entries = json.loads(raw)
    assert entries[1] == {"name": NAME_SKILL, "version": "0.1.0", "replaced_by": "skill-chanchi-global-next",
                          "date": "2026-11-23", "reason": "superseded"}
    assert list(entries[1]) == ["name", "version", "replaced_by", "date", "reason"]
    assert [p["code"] for p in items.check(root, own_names=[])["problems"]] == []
    assert other.is_dir()


def test_retire_creates_retired_json_and_exempts_a_published_item(cat, root):
    item = make_skill(root)
    aid = accepted_audit(cat, root)
    publish(cat, root, audit_id=aid)
    (item / "extra.md").write_text("edited after publish")
    assert [p["code"] for p in items.check(root, own_names=[])["problems"]] == ["edited_after_publish"]
    items.retire(root, NAME_SKILL, reason="gone", today="2026-11-23")
    assert json.loads((root / "ITEMS" / "retired.json").read_text()) == [
        {"name": NAME_SKILL, "version": "0.1.0", "replaced_by": None, "date": "2026-11-23", "reason": "gone"}
    ]
    assert items.check(root, own_names=[])["problems"] == []
    (row,) = items.list_items(root)
    assert row["status"] == "retired" and row["retired"] is True


def test_retire_refusals(root):
    make_skill(root)
    make_agent(root)
    make_skill(root, "skill-chanchi-global-gone", status="retired")
    retired_entry = [{"name": "skill-chanchi-global-gone", "version": "0.1.0", "replaced_by": None,
                      "date": "2026-11-22", "reason": "x"}]
    (root / "ITEMS" / "retired.json").write_text(json.dumps(retired_entry))

    def attempt(name=NAME_SKILL, **kw):
        kw.setdefault("reason", "why")
        with pytest.raises(ChanchiError) as exc:
            items.retire(root, name, **kw)
        return exc.value

    assert attempt(reason="  ").code == "invalid_value" and attempt(reason="  ").field == "reason"
    assert attempt(replaced_by=NAME_SKILL).field == "replaced_by"
    assert attempt(replaced_by="skill-chanchi-global-nope").field == "replaced_by"
    assert attempt(replaced_by="skill-chanchi-global-gone").field == "replaced_by"  # retired replacement
    assert attempt(name="skill-chanchi-global-nope").code == "invalid_value"
    assert attempt(name="skill-chanchi-global-gone").code == "invalid_transition"
    # nothing changed
    assert json.loads((root / "ITEMS" / "retired.json").read_text()) == retired_entry
    assert 'status: "draft"' in (root / "ITEMS" / "skills" / NAME_SKILL / "SKILL.md").read_text()


def test_retire_replacement_of_another_kind_is_refused(root):
    make_skill(root)
    make_agent(root)
    with pytest.raises(ChanchiError) as exc:
        items.retire(root, NAME_SKILL, reason="x", replaced_by=NAME_AGENT)
    assert exc.value.code == "invalid_value" and exc.value.field == "replaced_by"


def test_retire_twice_is_invalid_transition(root):
    make_skill(root)
    items.retire(root, NAME_SKILL, reason="once", today="2026-11-23")
    with pytest.raises(ChanchiError) as exc:
        items.retire(root, NAME_SKILL, reason="twice", today="2026-11-23")
    assert exc.value.code == "invalid_transition"
    assert len(json.loads((root / "ITEMS" / "retired.json").read_text())) == 1


def test_retire_refuses_an_item_whose_status_cannot_be_read(root):
    item = make_skill(root)
    (item / "SKILL.md").write_text((item / "SKILL.md").read_text().replace('  status: "draft"\n', ""))
    with pytest.raises(ChanchiError) as exc:
        items.retire(root, NAME_SKILL, reason="x")
    assert exc.value.code == "invalid_value"
    assert any(p["code"] == "bad_status" for p in exc.value.details["problems"])
    assert not (root / "ITEMS" / "retired.json").exists()


def test_retired_name_set_back_to_draft_fails_check(root):
    item = make_skill(root)
    items.retire(root, NAME_SKILL, reason="x", today="2026-11-23")
    (item / "SKILL.md").write_text((item / "SKILL.md").read_text().replace('"retired"', '"draft"'))
    assert codes(problems_for(root)) == [(NAME_SKILL, "retired_not_retired")]


# --- CLI ---------------------------------------------------------------------------


@pytest.fixture
def cli_env(db_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CHANCHI_SYNC", str(tmp_path / "SYNC"))
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    for agent, model, efforts in (
        ("claude", "sonnet", "low,medium,high"),
        ("agy", "gemini-4-neon-high", "high"),
        ("opencode", "opencode-go/minimax-m3", None),
    ):
        argv = ["models", "add", "--agent", agent, "--model", model, "--cost", "1"]
        assert cli.main(argv + (["--efforts", efforts] if efforts else [])) == 0
    capsys.readouterr()
    return capsys


def run(capsys, *argv, expect=0):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    assert code == expect, err or out
    return json.loads(out if expect == 0 else err)


def test_cli_items_need_sync(cli_env):
    error = run(cli_env, "items", "check", expect=2)["error"]
    assert error["code"] == "missing_prerequisite" and error["hint"] == "chanchi sync init"
    assert run(cli_env, "items", "list", expect=2)["error"]["code"] == "missing_prerequisite"


def test_cli_check_fails_once_with_every_problem(cli_env, tmp_path):
    root = tmp_path / "SYNC"
    (root / "ITEMS" / "skills").mkdir(parents=True)
    make_skill(root, "skill-chanchi-global-a", version="1.0")
    make_skill(root, "bad-name")
    error = run(cli_env, "items", "check", expect=2)["error"]
    assert error["code"] == "invalid_value" and error["field"] == "items"
    assert {(p["item"], p["code"]) for p in error["details"]["problems"]} >= {
        ("skill-chanchi-global-a", "bad_version"), ("bad-name", "bad_name")}


def test_cli_full_flow_open_vote_close_publish_list_retire(cli_env, tmp_path):
    root = tmp_path / "SYNC"
    (root / "ITEMS" / "agents").mkdir(parents=True)
    item = make_skill(root)
    checked = run(cli_env, "items", "check")
    assert checked["problems"] == [] and checked["items"][0]["name"] == NAME_SKILL
    opened = run(cli_env, "audit", "open", "--kind", "item", "--ref", NAME_SKILL, "--author", "claude:opus:unknown",
                 "--version", "0.1.0")
    aid = opened["audit_id"]
    for seat in (1, 2, 3):
        run(cli_env, "audit", "vote", str(aid), "--round", "1", "--seat", str(seat), "--verdict", "pass",
            "--blocking", "0", "--major", "0", "--minor", "0", "--report", "fixture")
    assert run(cli_env, "audit", "close", str(aid), "--round", "1")["outcome"] == "accepted"
    published = run(cli_env, "items", "publish", NAME_SKILL, "--audit", str(aid))
    assert published["status"] == "published" and published["hash"] == items.content_hash(item)
    listed = run(cli_env, "items", "list")["items"]
    assert [(r["name"], r["status"], r["retired"]) for r in listed] == [(NAME_SKILL, "published", False)]
    assert listed[0]["published_hash"] == published["hash"]
    retired = run(cli_env, "items", "retire", NAME_SKILL, "--reason", "done")
    assert retired["status"] == "retired"
    assert run(cli_env, "items", "list")["items"][0]["retired"] is True
    again = run(cli_env, "items", "publish", NAME_SKILL, "--audit", str(aid), expect=2)["error"]
    assert again["code"] == "invalid_transition"


def test_cli_item_audit_without_sync_is_refused(cli_env):
    error = run(cli_env, "audit", "open", "--kind", "item", "--ref", NAME_SKILL, "--author", "human",
                "--version", "0.1.0", expect=2)["error"]
    assert error["code"] == "missing_prerequisite" and error["hint"] == "chanchi sync init"


def test_taxonomy_lists_item_statuses_and_kinds():
    from chanchi import taxonomy

    described = taxonomy.describe()["items"]
    assert described["statuses"] == ["draft", "published", "retired"]
    assert described["kinds"] == {"agents": "agent", "skills": "skill"}


def test_layers_items_never_imports_audits():
    imports = Path(items.__file__).read_text(encoding="utf-8")
    assert "import audits" not in imports and "from chanchi.audits" not in imports
