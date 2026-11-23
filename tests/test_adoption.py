"""Adoption inbox and decisions: `items inbox` and `items decide`.

Design: docs/designs/global-items.md, "D. Adopt" and "Data model (migration 006)".
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from chanchi import adoption, audits, catalog, cli, inventory, items, projects, sync, taxonomy
from chanchi.errors import ChanchiError

SKILL_NAME = "skill-chanchi-global-tool-x"
DRAFT_NAME = "skill-chanchi-global-draft-only"
AGENT_NAME = "agent-chanchi-global-helper"
T1 = "2026-11-23T10:00:00Z"

SKILL_MD = """---
name: {name}
description: Global tool-x skill.
metadata:
  version: "{version}"
  status: "{status}"
---

# {name}

Shared instructions.
"""

AGENT_MD = """---
name: {name}
description: Global helper agent.
scope: both
profile: read-only
skills: []
version: {version}
status: {status}
---

# {name}

State your agent name.
"""

CHANGELOG_MD = "# Changelog\n\n## {version} — 2026-11-23\n\n- Release {version}.\n"


def which(name: str) -> str:
    return f"/bin/{name}"


def write_skill(root: Path, name: str = SKILL_NAME, *, version: str = "0.1.0", status: str = "draft") -> Path:
    item = root / "ITEMS" / "skills" / name
    item.mkdir(parents=True, exist_ok=True)
    (item / "SKILL.md").write_text(SKILL_MD.format(name=name, version=version, status=status), encoding="utf-8")
    (item / "CHANGELOG.md").write_text(CHANGELOG_MD.format(version=version), encoding="utf-8")
    return item


def write_agent(root: Path, name: str = AGENT_NAME, *, version: str = "0.1.0", status: str = "draft") -> Path:
    item = root / "ITEMS" / "agents" / name
    item.mkdir(parents=True, exist_ok=True)
    (item / "AGENT.md").write_text(AGENT_MD.format(name=name, version=version, status=status), encoding="utf-8")
    (item / "CHANGELOG.md").write_text(CHANGELOG_MD.format(version=version), encoding="utf-8")
    return item


def vote_all(conn, audit_id: int, *, verdict: str = "pass", major: int = 0) -> dict:
    for seat in (1, 2, 3):
        audits.vote(conn, audit_id, round=1, seat=seat, verdict=verdict, blocking=0, major=major, minor=0, report="f")
    return audits.close_round(conn, audit_id, round=1)


def publish_skill(conn, root: Path, name: str = SKILL_NAME, version: str = "0.1.0") -> Path:
    item = write_skill(root, name, version=version, status="draft")
    aid = audits.open_audit(
        conn, kind="item", ref=name, author="claude:opus:high", version=version,
        roster=sync.BUILTIN_ROSTER, which=which, sync_root=root,
    )["audit_id"]
    assert vote_all(conn, aid)["outcome"] == "accepted"
    items.publish(conn, root, name, audit_id=aid, own_names=[])
    return item


def publish_agent(conn, root: Path, name: str = AGENT_NAME, version: str = "0.1.0") -> Path:
    item = write_agent(root, name, version=version, status="draft")
    aid = audits.open_audit(
        conn, kind="item", ref=name, author="claude:opus:high", version=version,
        roster=sync.BUILTIN_ROSTER, which=which, sync_root=root,
    )["audit_id"]
    assert vote_all(conn, aid)["outcome"] == "accepted"
    items.publish(conn, root, name, audit_id=aid, own_names=[])
    return item


def accepted_adoption_audit(conn, project_slug: str, item_name: str, *, commit: str = "abc1234") -> int:
    aid = audits.open_audit(
        conn,
        kind="adoption",
        ref=f"{project_slug}:{item_name}",
        project_id=audits.resolve_project_id(conn, project_slug),
        author="claude:opus:high",
        commit=commit,
        roster=sync.BUILTIN_ROSTER,
        which=which,
    )["audit_id"]
    assert vote_all(conn, aid)["outcome"] == "accepted"
    return aid


def git_project(tmp_path: Path, conn, name: str) -> tuple[Path, int]:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    info = projects.register(conn, repo)
    return repo.resolve(), info["project"]["id"]


def put(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def snapshot(root: Path) -> dict:
    seen = {}
    for here, dirs, files in os.walk(root, followlinks=False):
        for name in [*dirs, *files]:
            path = os.path.join(here, name)
            st = os.lstat(path)
            seen[path] = (st.st_mode, st.st_size, st.st_mtime_ns)
    return seen


def run_cli(capsys, *argv, expect: int = 0) -> dict:
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    assert code == expect, err or out
    return json.loads(out if expect == 0 else err)


@pytest.fixture
def env(conn, tmp_path, monkeypatch):
    """Scratch SYNC (1 published skill, 1 draft skill, 1 published agent) and registered projects A and B."""
    for agent, model, efforts in (
        ("claude", "sonnet", ["low", "medium", "high"]),
        ("agy", "gemini-4-neon-high", ["high"]),
        ("opencode", "opencode-go/minimax-m3", None),
        ("agy", "gemini-4-hydrogen-high", ["high"]),
    ):
        catalog.add_model(conn, agent=agent, model=model, cost_tier=2, efforts=efforts)

    sync_root = tmp_path / "SYNC"
    monkeypatch.setenv("CHANCHI_SYNC", str(sync_root))
    sync.init({"CHANCHI_SYNC": str(sync_root)})

    publish_skill(conn, sync_root, SKILL_NAME, "0.1.0")
    write_skill(sync_root, DRAFT_NAME, version="0.1.0", status="draft")
    publish_agent(conn, sync_root, AGENT_NAME, "0.1.0")

    proj_a, pid_a = git_project(tmp_path, conn, "project-a")
    proj_b, pid_b = git_project(tmp_path, conn, "project-b")

    put(proj_a, ".agents/skills/tool-x/SKILL.md", "---\nname: tool-x\ndescription: A tool.\n---\nBody\n")
    inventory.scan(conn)

    return {
        "conn": conn,
        "sync": sync_root,
        "tmp": tmp_path,
        "a": proj_a,
        "a_id": pid_a,
        "a_slug": "project-a",
        "b": proj_b,
        "b_id": pid_b,
        "b_slug": "project-b",
    }


# --- inbox: states, problems, similar, independence ---------------------------


def test_inbox_lists_published_as_new_never_draft_and_populates_similar(env):
    conn, sync_root = env["conn"], env["sync"]
    before_a = snapshot(env["a"])

    inbox_a = adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])
    assert inbox_a["project"] == "project-a"
    assert inbox_a["problems"] == []
    assert [e["item"] for e in inbox_a["entries"]] == [AGENT_NAME, SKILL_NAME]

    agent_entry, skill_entry = inbox_a["entries"]
    assert agent_entry["kind"] == "agent"
    assert agent_entry["state"] == "new"
    assert agent_entry["version"] == "0.1.0"
    assert agent_entry["status"] == "published"
    assert agent_entry["version_changed"] is False
    assert agent_entry["replaced_by"] is None
    assert agent_entry["decision"] is None
    assert agent_entry["similar"] == []
    assert agent_entry["path"] == str(sync_root / "ITEMS" / "agents" / AGENT_NAME)

    assert skill_entry["kind"] == "skill"
    assert skill_entry["state"] == "new"
    assert skill_entry["path"] == str(sync_root / "ITEMS" / "skills" / SKILL_NAME)
    assert len(skill_entry["similar"]) == 1
    sim = skill_entry["similar"][0]
    assert sim["kind"] == "skill"
    assert sim["name"] == "tool-x"
    assert sim["path"] == ".agents/skills/tool-x"
    assert sim["abs_path"] == str(env["a"] / ".agents/skills/tool-x")
    assert sim["lines"] > 0
    assert len(sim["sha256"]) == 64

    # Inbox never touches project files.
    assert snapshot(env["a"]) == before_a


def test_inbox_unreadable_item_goes_to_problems_and_bad_retired_json_fails(env):
    conn, sync_root = env["conn"], env["sync"]
    broken = write_skill(sync_root, "skill-chanchi-global-broken", status="published")
    (broken / "link.md").symlink_to(broken / "SKILL.md")

    res = adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])
    assert [e["item"] for e in res["entries"]] == [AGENT_NAME, SKILL_NAME]
    assert res["problems"] == [{"item": "skill-chanchi-global-broken", "hint": "chanchi items check"}]

    (sync_root / "ITEMS" / "retired.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ChanchiError) as exc:
        adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])
    assert exc.value.code == "invalid_value"
    assert exc.value.field == "items"
    assert exc.value.hint == "chanchi items check"


def test_inbox_similar_proposal_evidence_kind_filter_sorting_and_rescan(env):
    conn, sync_root = env["conn"], env["sync"]
    # Add: (1) a second skill with the same slug at an earlier path,
    # (2) a project agent named like the global skill (must be filtered by kind),
    # (3) a differently named skill referenced in a built proposal's evidence + aliases.
    put(env["a"], ".agents/skills/alt-tool-x/SKILL.md", "---\nname: tool-x\ndescription: Second.\n---\nBody\n")
    put(env["a"], ".claude/agents/tool-x.md", "---\nname: tool-x\ndescription: Agent.\n---\nBody\n")
    put(env["a"], ".agents/skills/custom-alias/SKILL.md", "---\nname: custom-alias\ndescription: Alias.\n---\nBody\n")
    inventory.scan(conn, project="project-a")

    evidence = {
        "rules": ["same_name"],
        "copies": [
            {
                "project": "project-a",
                "kind": "skill",
                "name": "tool-x",
                "path": ".agents/skills/tool-x",  # matches both name and proposal -> must appear once
                "sha256": "0" * 64,
                "lines": 5,
                "aliases": [".agents/skills/custom-alias"],  # different name -> matched via proposal evidence
            }
        ],
    }
    conn.execute(
        "INSERT INTO item_proposals (kind, name, evidence, uses, owner_promoted, status, global_item, "
        "created_at, updated_at) VALUES ('skill', ?, ?, 1, 1, 'built', ?, ?, ?)",
        (SKILL_NAME, json.dumps(evidence), SKILL_NAME, T1, T1),
    )

    entry = next(
        e for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
        if e["item"] == SKILL_NAME
    )
    assert [s["path"] for s in entry["similar"]] == [
        ".agents/skills/alt-tool-x",
        ".agents/skills/custom-alias",
        ".agents/skills/tool-x",
    ]
    assert all(s["kind"] == "skill" for s in entry["similar"])

    # Remove the alias copy and re-scan -> it disappears from similar.
    (env["a"] / ".agents/skills/custom-alias/SKILL.md").unlink()
    (env["a"] / ".agents/skills/custom-alias").rmdir()
    inventory.scan(conn, project="project-a")

    entry_after = next(
        e for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
        if e["item"] == SKILL_NAME
    )
    assert [s["path"] for s in entry_after["similar"]] == [
        ".agents/skills/alt-tool-x",
        ".agents/skills/tool-x",
    ]


def test_inbox_similar_abs_path_null_when_project_root_missing(env):
    conn, sync_root = env["conn"], env["sync"]
    import shutil

    shutil.rmtree(env["a"])
    entry = next(
        e for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
        if e["item"] == SKILL_NAME
    )
    assert len(entry["similar"]) == 1
    assert entry["similar"][0]["abs_path"] is None


def test_inbox_uses_unresolved_sync_path(conn, tmp_path, monkeypatch):
    for agent, model, efforts in (
        ("claude", "sonnet", ["low", "medium", "high"]),
        ("agy", "gemini-4-neon-high", ["high"]),
        ("opencode", "opencode-go/minimax-m3", None),
        ("agy", "gemini-4-hydrogen-high", ["high"]),
    ):
        catalog.add_model(conn, agent=agent, model=model, cost_tier=2, efforts=efforts)
    real_sync = tmp_path / "cloud-sync"
    link_sync = tmp_path / "SYNC"
    sync.init({"CHANCHI_SYNC": str(link_sync)}, link=real_sync)
    publish_skill(conn, link_sync, SKILL_NAME, "0.1.0")
    _, pid = git_project(tmp_path, conn, "project-a")

    inbox = adoption.inbox(conn, link_sync, project_id=pid, slug="project-a")
    assert inbox["entries"][0]["path"] == str(link_sync / "ITEMS" / "skills" / SKILL_NAME)


def test_decide_and_inbox_lifecycle_and_project_independence(env):
    conn, sync_root = env["conn"], env["sync"]
    item_dir = sync_root / "ITEMS" / "skills" / SKILL_NAME
    expected_hash = items.content_hash(item_dir)

    aid = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME)
    decided = adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="adopt", version="0.1.0",
        reason="covered by global", audit_id=aid, local="tool-x", now=T1,
    )
    assert decided == {
        "id": 1,
        "project": "project-a",
        "item": SKILL_NAME,
        "version": "0.1.0",
        "hash": expected_hash,
        "decision": "adopt",
        "local_item": "tool-x",
        "reason": "covered by global",
        "audit_id": aid,
        "decided_at": T1,
        "state": "up_to_date",
    }

    # Without --all, A's inbox hides up_to_date; with --all it includes it.
    inbox_a = adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])
    assert [e["item"] for e in inbox_a["entries"]] == [AGENT_NAME]
    inbox_a_all = adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"], all_=True)
    assert [e["item"] for e in inbox_a_all["entries"]] == [AGENT_NAME, SKILL_NAME]
    skill_row = inbox_a_all["entries"][1]
    assert skill_row["state"] == "up_to_date"
    assert skill_row["decision"]["hash"] == expected_hash
    assert skill_row["decision"]["audit_id"] == aid

    # Project B's inbox is completely independent of A's decision.
    inbox_b = adoption.inbox(conn, sync_root, project_id=env["b_id"], slug=env["b_slug"])
    assert [(e["item"], e["state"]) for e in inbox_b["entries"]] == [(AGENT_NAME, "new"), (SKILL_NAME, "new")]

    # New published version 0.2.0 makes A's entry `changed`, cleared by deciding 0.2.0.
    publish_skill(conn, sync_root, SKILL_NAME, "0.2.0")
    changed = next(
        e for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
        if e["item"] == SKILL_NAME
    )
    assert changed["state"] == "changed"
    assert changed["version_changed"] is True
    assert changed["version"] == "0.2.0"

    aid2 = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME, commit="def5678")
    adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="adopt", version="0.2.0",
        reason="updated to 0.2.0", audit_id=aid2,
    )
    assert [e["item"] for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]] == [
        AGENT_NAME
    ]


def test_deprecate_and_version_change_stay_deprecate_pending_until_resolved(env):
    conn, sync_root = env["conn"], env["sync"]
    aid = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME)
    res = adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="deprecate", version="0.1.0",
        local="tool-x", reason="remove in next cleanup", audit_id=aid,
    )
    assert res["state"] == "deprecate_pending"

    entry = next(
        e for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
        if e["item"] == SKILL_NAME
    )
    assert entry["state"] == "deprecate_pending"
    assert entry["version_changed"] is False

    # A new version keeps deprecate_pending with version_changed=True.
    publish_skill(conn, sync_root, SKILL_NAME, "0.2.0")
    entry_v2 = next(
        e for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
        if e["item"] == SKILL_NAME
    )
    assert entry_v2["state"] == "deprecate_pending"
    assert entry_v2["version_changed"] is True

    # A later keep/adopt/wrap clears deprecate_pending.
    aid2 = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME, commit="bbb2222")
    res2 = adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="wrap", version="0.2.0",
        local="skill-chanchi-project-a-tool-x", reason="wrapped now", audit_id=aid2,
    )
    assert res2["state"] == "up_to_date"
    assert [e["item"] for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]] == [
        AGENT_NAME
    ]


def test_retirement_flow_replaced_by_last_entry_and_never_decided_omitted(env):
    conn, sync_root = env["conn"], env["sync"]
    replacement = "skill-chanchi-global-tool-v2"
    publish_skill(conn, sync_root, replacement, "0.1.0")
    replacement2 = "skill-chanchi-global-tool-v3"
    publish_skill(conn, sync_root, replacement2, "0.1.0")

    # Project A adopts SKILL_NAME; Project B never decides SKILL_NAME.
    aid_a = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME)
    adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="adopt", version="0.1.0",
        reason="adopted", audit_id=aid_a,
    )

    items.retire(sync_root, SKILL_NAME, reason="superseded", replaced_by=replacement)
    # Append a second retired.json entry for the same name to verify the last entry wins for replaced_by.
    retired_path = sync_root / "ITEMS" / "retired.json"
    entries = json.loads(retired_path.read_text(encoding="utf-8"))
    entries.append({
        "name": SKILL_NAME, "version": "0.1.0", "replaced_by": replacement2,
        "date": "2026-11-24", "reason": "newer replacement",
    })
    retired_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    # Project A sees SKILL_NAME as `retired` with replaced_by = replacement2.
    inbox_a = adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])
    retired_entry = next(e for e in inbox_a["entries"] if e["item"] == SKILL_NAME)
    assert retired_entry["state"] == "retired"
    assert retired_entry["replaced_by"] == replacement2

    # Project B never decided SKILL_NAME -> absent even with --all!
    inbox_b_all = adoption.inbox(conn, sync_root, project_id=env["b_id"], slug=env["b_slug"], all_=True)
    assert SKILL_NAME not in [e["item"] for e in inbox_b_all["entries"]]

    # On retired item: adopt and wrap are refused (invalid_transition); deprecate -> deprecate_pending; keep clears it.
    aid_bad = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME, commit="c1")
    for forbidden in ("adopt", "wrap"):
        with pytest.raises(ChanchiError) as exc:
            adoption.decide(
                conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
                item=SKILL_NAME, decision=forbidden, version="0.1.0",
                local="skill-chanchi-project-a-x" if forbidden == "wrap" else None,
                reason="try forbidden", audit_id=aid_bad,
            )
        assert exc.value.code == "invalid_transition"
        assert "replaced_by" in exc.value.hint or replacement2 in exc.value.hint

    # deprecate on retired item (without --local is allowed) -> deprecate_pending
    aid_dep = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME, commit="c2")
    dep = adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="deprecate", version="0.1.0",
        reason="drop refs later", audit_id=aid_dep,
    )
    assert dep["state"] == "deprecate_pending"
    assert any(
        e["item"] == SKILL_NAME and e["state"] == "deprecate_pending"
        for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
    )

    # keep without --local on retired item clears it -> up_to_date (only shown with --all)
    aid_keep = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME, commit="c3")
    kept = adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="keep", version="0.1.0",
        reason="acknowledged retirement", audit_id=aid_keep,
    )
    assert kept["state"] == "up_to_date"
    assert kept["local_item"] is None
    assert SKILL_NAME not in [
        e["item"] for e in adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"])["entries"]
    ]
    all_a = adoption.inbox(conn, sync_root, project_id=env["a_id"], slug=env["a_slug"], all_=True)
    kept_entry = next(e for e in all_a["entries"] if e["item"] == SKILL_NAME)
    assert kept_entry["state"] == "up_to_date"


# --- decide refusals (D5-D7) -------------------------------------------------


def test_decide_refusals_in_order(env):
    conn, sync_root = env["conn"], env["sync"]
    valid_audit = accepted_adoption_audit(conn, env["a_slug"], SKILL_NAME)

    def fail(**kw):
        defaults = dict(
            project_id=env["a_id"], slug=env["a_slug"], item=SKILL_NAME, decision="adopt",
            version="0.1.0", reason="why", audit_id=valid_audit, local=None,
        )
        defaults.update(kw)
        with pytest.raises(ChanchiError) as exc:
            adoption.decide(conn, sync_root, **defaults)
        return exc.value

    # 1. Unknown global item
    err = fail(item="skill-chanchi-global-nope")
    assert err.code == "invalid_value" and err.field == "item"
    err = fail(item="not-a-global-name")
    assert err.code == "invalid_value" and err.field == "item"

    # 2. Unreadable item (symlink inside it) & malformed retired.json
    broken = write_skill(sync_root, "skill-chanchi-global-broken", status="published")
    (broken / "sym.md").symlink_to(broken / "SKILL.md")
    err = fail(item="skill-chanchi-global-broken")
    assert err.code == "invalid_value" and err.hint == "chanchi items check"

    retired_path = sync_root / "ITEMS" / "retired.json"
    retired_path.write_text("{bad", encoding="utf-8")
    err = fail()
    assert err.code == "invalid_value" and err.hint == "chanchi items check"
    retired_path.unlink()

    # 3. Draft item
    err = fail(item=DRAFT_NAME)
    assert err.code == "invalid_transition"

    # 4. Unknown decision (even on a retired item: invalid_value BEFORE invalid_transition!)
    ret_skill = "skill-chanchi-global-old"
    publish_skill(conn, sync_root, ret_skill, "0.1.0")
    items.retire(sync_root, ret_skill, reason="old")
    err = fail(item=ret_skill, decision="bogus")
    assert err.code == "invalid_value" and err.field == "decision"
    assert err.valid_values == list(taxonomy.ADOPTION_DECISIONS)

    # 5. Wrong version
    err = fail(version="9.9.9")
    assert err.code == "invalid_value" and err.field == "version"

    # 6. Retired item refuses adopt and wrap
    err = fail(item=ret_skill, decision="adopt")
    assert err.code == "invalid_transition"

    # 7. Blank reason
    err = fail(reason="   ")
    assert err.code == "invalid_value" and err.field == "reason"

    # 8. --local rules (D6)
    err = fail(decision="wrap", local=None)
    assert err.code == "invalid_value" and err.field == "local"
    err = fail(decision="wrap", local="skill-chanchi-other-x")
    assert err.code == "invalid_value" and err.field == "local"
    assert "skill-chanchi-project-a-" in err.hint
    err = fail(decision="keep", local=None)
    assert err.code == "invalid_value" and err.field == "local"
    err = fail(decision="deprecate", local=None)
    assert err.code == "invalid_value" and err.field == "local"
    err = fail(decision="adopt", local="  ")
    assert err.code == "invalid_value" and err.field == "local"

    # 9. Audit rules (D7)
    err = fail(audit_id=9999)
    assert err.code == "unknown_audit" and err.field == "audit"

    design_audit = audits.open_audit(
        conn, kind="design", ref=f"{env['a_slug']}:{SKILL_NAME}", project_id=env["a_id"],
        author="claude:opus:high", commit="aaa", roster=sync.BUILTIN_ROSTER, which=which,
    )["audit_id"]
    vote_all(conn, design_audit)
    err = fail(audit_id=design_audit)
    assert err.code == "invalid_value" and err.field == "audit"

    wrong_ref_audit = accepted_adoption_audit(conn, env["a_slug"], AGENT_NAME)
    err = fail(audit_id=wrong_ref_audit)
    assert err.code == "invalid_value" and err.field == "audit"

    other_proj_audit = accepted_adoption_audit(conn, env["b_slug"], SKILL_NAME)
    err = fail(audit_id=other_proj_audit)
    assert err.code == "invalid_value" and err.field == "audit"

    fix_audit = audits.open_audit(
        conn, kind="adoption", ref=f"{env['a_slug']}:{SKILL_NAME}", project_id=env["a_id"],
        author="claude:opus:high", commit="bbb", roster=sync.BUILTIN_ROSTER, which=which,
    )["audit_id"]
    vote_all(conn, fix_audit, verdict="pass_with_fixes", major=1)
    err = fail(audit_id=fix_audit)
    assert err.code == "invalid_transition" and err.field == "audit"

    # Valid wrap with right prefix succeeds, then reusing its audit fails.
    ok = adoption.decide(
        conn, sync_root, project_id=env["a_id"], slug=env["a_slug"],
        item=SKILL_NAME, decision="wrap", version="0.1.0",
        local="skill-chanchi-project-a-tool-x", reason="particular rules", audit_id=valid_audit,
    )
    assert ok["local_item"] == "skill-chanchi-project-a-tool-x"
    assert ok["state"] == "up_to_date"

    err = fail(audit_id=valid_audit)
    assert err.code == "invalid_value" and err.field == "audit"


# --- CLI scope, hash match and missing prerequisites -------------------------


def test_cli_scope_detection_and_flag_equivalence_and_errors(env, capsys, monkeypatch):
    # Outside any project with --project vs inside project without --project
    outside = env["tmp"] / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    err_unreg = run_cli(capsys, "items", "inbox", expect=2)["error"]
    assert err_unreg["code"] == "project_not_registered"

    via_flag = run_cli(capsys, "items", "inbox", "--project", "project-a")
    monkeypatch.chdir(env["a"])
    via_cwd = run_cli(capsys, "items", "inbox")
    assert via_flag == via_cwd

    # Decide via CLI and verify stored hash matches items.content_hash
    aid = accepted_adoption_audit(env["conn"], "project-a", SKILL_NAME)
    monkeypatch.chdir(outside)
    decided = run_cli(
        capsys, "items", "decide", SKILL_NAME,
        "--decision", "adopt", "--version", "0.1.0", "--reason", "cli ok", "--audit", str(aid),
        "--project", "project-a",
    )
    expected_hash = items.content_hash(env["sync"] / "ITEMS" / "skills" / SKILL_NAME)
    assert decided["hash"] == expected_hash
    assert decided["state"] == "up_to_date"

    after = run_cli(capsys, "items", "inbox", "--project", "project-a")
    assert [e["item"] for e in after["entries"]] == [AGENT_NAME]
    after_all = run_cli(capsys, "items", "inbox", "--all", "--project", "project-a")
    assert [e["item"] for e in after_all["entries"]] == [AGENT_NAME, SKILL_NAME]

    # Without SYNC -> missing_prerequisite
    monkeypatch.setenv("CHANCHI_SYNC", str(env["tmp"] / "missing-sync"))
    monkeypatch.chdir(env["a"])
    no_sync_inbox = run_cli(capsys, "items", "inbox", expect=2)["error"]
    assert no_sync_inbox["code"] == "missing_prerequisite"
    no_sync_decide = run_cli(
        capsys, "items", "decide", SKILL_NAME,
        "--decision", "adopt", "--version", "0.1.0", "--reason", "x", "--audit", str(aid),
        expect=2,
    )["error"]
    assert no_sync_decide["code"] == "missing_prerequisite"
