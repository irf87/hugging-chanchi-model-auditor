"""audit open | unavailable | show | list: seat filling, degraded rounds, quorum and the CLI."""

import json
import shutil

import pytest

from chanchi import audits, catalog, cli, sync
from chanchi.errors import ChanchiError

ALL = ["low", "medium", "high"]
ON_PATH = {"claude", "agy", "opencode"}


def which_with(*present):
    return lambda name: f"/bin/{name}" if name in present else None


ALL_BINARIES = which_with(*ON_PATH)


@pytest.fixture
def cat(conn):
    """The four built-in roster models in the catalog."""
    catalog.add_model(conn, agent="claude", model="sonnet", cost_tier=2, efforts=ALL)
    catalog.add_model(conn, agent="agy", model="gemini-4-neon-high", cost_tier=2, efforts=["high"])
    catalog.add_model(conn, agent="opencode", model="opencode-go/minimax-m3", cost_tier=1)
    catalog.add_model(conn, agent="agy", model="gemini-4-hydrogen-high", cost_tier=1, efforts=["high"])
    return conn


def open_(conn, roster=None, which=ALL_BINARIES, **kw):
    args = {"kind": "design", "ref": "docs/designs/x.md", "author": "claude:opus:high", "commit": "abc123"}
    args.update(kw)
    return audits.open_audit(conn, roster=sync.BUILTIN_ROSTER if roster is None else roster, which=which, **args)


def specs(result):
    return [s["spec"] for s in result["seats"]]


def test_three_families_seat_three_distinct_families(cat):
    result = open_(cat)
    assert specs(result) == [
        "claude:sonnet:medium",
        "agy:gemini-4-neon-high:high",
        "opencode:opencode-go/minimax-m3",
    ]
    assert [s["family"] for s in result["seats"]] == ["anthropic", "google", "minimax"]
    assert [s["seat"] for s in result["seats"]] == [1, 2, 3]
    assert result["degraded"] is False and result["outcome"] is None and result["round"] == 1
    assert result["skipped"] == []
    assert result["seats"][0]["launch"] == (
        'claude -p --agent agent-chanchi-auditor --model sonnet --effort medium "<prompt>" < /dev/null'
    )
    assert result["seats"][1]["launch"].startswith("agy --agent agent-chanchi-auditor --model gemini-4-neon --effort high")
    assert result["seats"][2]["launch"].startswith(
        "opencode run --agent agent-chanchi-auditor -m opencode-go/minimax-m3"
    )
    row = cat.execute("SELECT * FROM audit_rounds WHERE audit_id = ?", (result["audit_id"],)).fetchone()
    assert (row["round"], row["subject_at"], row["degraded"], row["closed_at"]) == (1, "abc123", 0, None)


def test_version_subject_and_author_resolution(cat):
    cat.execute("INSERT INTO models (agent, model, cost_tier, active, created_at) VALUES ('claude','opus',3,1,'t')")
    result = open_(cat, commit=None, version="1.2.0", kind="item", ref="skill-chanchi-global-x")
    audit = cat.execute("SELECT * FROM audits WHERE id = ?", (result["audit_id"],)).fetchone()
    assert audit["author_raw"] == "claude:opus:high" and audit["author_model_id"] is not None
    rnd = cat.execute("SELECT subject_at FROM audit_rounds WHERE audit_id = ?", (audit["id"],)).fetchone()
    assert rnd["subject_at"] == "1.2.0"
    unknown = open_(cat, author="agy:not-in-catalog:high")
    stored = cat.execute("SELECT * FROM audits WHERE id = ?", (unknown["audit_id"],)).fetchone()
    assert stored["author_raw"] == "agy:not-in-catalog:high" and stored["author_model_id"] is None
    garbage = open_(cat, author="whoever")
    assert cat.execute("SELECT author_model_id FROM audits WHERE id = ?", (garbage["audit_id"],)).fetchone()[0] is None


def test_exactly_one_of_commit_and_version(cat):
    for kw in ({"commit": None}, {"version": "1.0.0"}):
        with pytest.raises(ChanchiError) as exc:
            open_(cat, **kw)
        assert exc.value.code == "invalid_value"
    with pytest.raises(ChanchiError):
        open_(cat, kind="poem")
    assert cat.execute("SELECT COUNT(*) FROM audits").fetchone()[0] == 0


def test_missing_binary_degrades_the_round(cat):
    result = open_(cat, which=which_with("claude", "agy"))
    assert specs(result) == [
        "claude:sonnet:medium",
        "agy:gemini-4-neon-high:high",
        "agy:gemini-4-hydrogen-high:high",
    ]
    assert result["degraded"] is True
    assert [(s["spec"], s["reason"]) for s in result["skipped"]] == [
        ("opencode:opencode-go/minimax-m3", "not_on_path")
    ]
    assert cat.execute("SELECT degraded FROM audit_rounds").fetchone()[0] == 1


def test_unknown_family_never_counts_as_distinct(cat):
    catalog.add_model(cat, agent="opencode", model="opencode-go/hy4", cost_tier=1)
    roster = [
        {"harness": "claude", "model": "sonnet", "effort": "medium"},
        {"harness": "opencode", "model": "opencode-go/hy4", "effort": None},
        {"harness": "agy", "model": "gemini-4-neon-high", "effort": "high"},
    ]
    result = open_(cat, roster)
    assert specs(result) == ["claude:sonnet:medium", "agy:gemini-4-neon-high:high", "opencode:opencode-go/hy4"]
    unknown = result["seats"][2]
    assert unknown["family"] is None
    assert unknown["hint"] == "chanchi models set opencode:opencode-go/hy4 --family <name>"
    assert result["degraded"] is True


def test_known_families_are_preferred_over_an_earlier_unknown_family(cat):
    catalog.add_model(cat, agent="opencode", model="opencode-go/hy4", cost_tier=1)
    roster = [
        {"harness": "opencode", "model": "opencode-go/hy4", "effort": None},
        *sync.BUILTIN_ROSTER[:3],
    ]
    result = open_(cat, roster)
    assert "opencode:opencode-go/hy4" not in specs(result)
    assert result["degraded"] is False


def test_entry_not_in_catalog_is_skipped_with_the_models_add_hint(conn):
    catalog.add_model(conn, agent="claude", model="sonnet", cost_tier=2)
    catalog.add_model(conn, agent="agy", model="gemini-4-neon-high", cost_tier=2)
    result = open_(conn)
    assert specs(result) == ["claude:sonnet:medium", "agy:gemini-4-neon-high:high"]
    skipped = {s["spec"]: s for s in result["skipped"]}
    minimax = skipped["opencode:opencode-go/minimax-m3"]
    assert minimax["reason"] == "not_in_catalog"
    assert minimax["hint"] == "chanchi models add --agent opencode --model opencode-go/minimax-m3 --cost <1-3>"
    assert skipped["agy:gemini-4-hydrogen-high:high"]["reason"] == "not_in_catalog"
    assert result["degraded"] is True and result["outcome"] is None


def test_inactive_model_is_skipped(cat):
    catalog.set_model(cat, spec="opencode:opencode-go/minimax-m3", active=False)
    result = open_(cat)
    assert {s["spec"]: s["reason"] for s in result["skipped"]} == {"opencode:opencode-go/minimax-m3": "inactive"}


def test_one_usable_spec_never_seats_twice_and_escalates_on_quorum(cat):
    roster = [{"harness": "claude", "model": "sonnet", "effort": "medium"}] * 2
    result = open_(cat, roster)
    assert specs(result) == ["claude:sonnet:medium"]
    assert [s["reason"] for s in result["skipped"]] == ["already_seated"]
    assert result["outcome"] == "escalated" and result["escalation"] == "quorum"
    assert result["seats"][0]["launch"] is None
    audit = cat.execute("SELECT * FROM audits WHERE id = ?", (result["audit_id"],)).fetchone()
    rnd = cat.execute("SELECT * FROM audit_rounds WHERE audit_id = ?", (audit["id"],)).fetchone()
    assert audit["outcome"] == "escalated" and audit["closed_at"] is not None
    assert (rnd["outcome"], rnd["escalation"]) == ("escalated", "quorum")
    assert rnd["closed_at"] is not None and rnd["degraded"] == 1


def test_empty_catalog_escalates_with_no_seats(conn):
    result = open_(conn)
    assert result["seats"] == [] and result["outcome"] == "escalated"
    assert {s["reason"] for s in result["skipped"]} == {"not_in_catalog"}


def test_unavailable_refills_the_same_seat_number(cat):
    opened = open_(cat)
    result = audits.mark_unavailable(
        cat, opened["audit_id"], round=1, seat=2, reason="quota exceeded",
        roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES,
    )
    assert result["unavailable"] == {"seat": 2, "spec": "agy:gemini-4-neon-high:high", "reason": "quota exceeded"}
    assert result["seat"]["seat"] == 2
    assert result["seat"]["spec"] == "agy:gemini-4-hydrogen-high:high"
    assert result["degraded"] is False  # still anthropic, google, minimax
    shown = audits.show(cat, opened["audit_id"])["rounds"][0]
    seat2 = [s for s in shown["seats"] if s["seat"] == 2]
    assert [(s["spec"], s["status"], s["reason"]) for s in seat2] == [
        ("agy:gemini-4-neon-high:high", "unavailable", "quota exceeded"),
        ("agy:gemini-4-hydrogen-high:high", "assigned", None),
    ]


def test_unavailable_recomputes_degraded_and_never_reseats_a_spec(cat):
    opened = open_(cat)
    first = audits.mark_unavailable(
        cat, opened["audit_id"], round=1, seat=3, reason="binary crashed",
        roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES,
    )
    assert first["seat"]["spec"] == "agy:gemini-4-hydrogen-high:high"
    assert first["degraded"] is True  # two google seats now
    assert cat.execute("SELECT degraded FROM audit_rounds").fetchone()[0] == 1
    second = audits.mark_unavailable(
        cat, opened["audit_id"], round=1, seat=3, reason="crashed again",
        roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES,
    )
    assert second["seat"] is None  # roster exhausted: minimax is unavailable, the rest are seated
    reasons = {s["spec"]: s["reason"] for s in second["skipped"]}
    assert reasons["opencode:opencode-go/minimax-m3"] == "unavailable"
    assert reasons["claude:sonnet:medium"] == "already_seated"
    with pytest.raises(ChanchiError) as exc:  # the empty seat cannot be marked again
        audits.mark_unavailable(
            cat, opened["audit_id"], round=1, seat=3, reason="x", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES
        )
    assert exc.value.code == "invalid_transition"


def test_unavailable_refused_on_voted_seat_closed_round_and_bad_numbers(cat):
    opened = open_(cat)
    cat.execute("UPDATE audit_seats SET status = 'voted' WHERE seat = 1")
    kw = {"roster": sync.BUILTIN_ROSTER, "which": ALL_BINARIES}
    with pytest.raises(ChanchiError) as voted:
        audits.mark_unavailable(cat, opened["audit_id"], round=1, seat=1, reason="x", **kw)
    assert voted.value.code == "invalid_transition"
    with pytest.raises(ChanchiError) as bad_seat:
        audits.mark_unavailable(cat, opened["audit_id"], round=1, seat=4, reason="x", **kw)
    assert bad_seat.value.code == "invalid_value"
    with pytest.raises(ChanchiError) as bad_round:
        audits.mark_unavailable(cat, opened["audit_id"], round=2, seat=2, reason="x", **kw)
    assert bad_round.value.code == "invalid_value"
    with pytest.raises(ChanchiError) as no_reason:
        audits.mark_unavailable(cat, opened["audit_id"], round=1, seat=2, reason="  ", **kw)
    assert no_reason.value.code == "invalid_value"
    cat.execute("UPDATE audit_rounds SET closed_at = 't', outcome = 'accepted'")
    with pytest.raises(ChanchiError) as closed:
        audits.mark_unavailable(cat, opened["audit_id"], round=1, seat=2, reason="x", **kw)
    assert closed.value.code == "invalid_transition"
    with pytest.raises(ChanchiError) as unknown:
        audits.mark_unavailable(cat, 99, round=1, seat=2, reason="x", **kw)
    assert unknown.value.code == "unknown_audit"


def test_change_needs_a_project(cat):
    with pytest.raises(ChanchiError) as exc:
        open_(cat, change="c1")
    assert exc.value.code == "missing_prerequisite" and "--project" in exc.value.hint
    assert cat.execute("SELECT COUNT(*) FROM audits").fetchone()[0] == 0


def test_change_and_project_are_linked(cat):
    from chanchi import record

    record.open_change(cat, project_slug="demo", project_path=None, ref="c1", kind="adhoc", planner="human")
    pid = cat.execute("SELECT id FROM projects WHERE slug = 'demo'").fetchone()[0]
    with pytest.raises(ChanchiError) as unknown:
        open_(cat, change="nope", project_id=pid)
    assert unknown.value.code == "unknown_change"
    result = open_(cat, change="c1", project_id=pid)
    audit = audits.show(cat, result["audit_id"])["audit"]
    assert (audit["project"], audit["change"]) == ("demo", "c1")
    assert audits.show(cat, open_(cat)["audit_id"])["audit"]["project"] is None


def test_resolve_project_id(cat):
    from chanchi import record

    record.open_change(cat, project_slug="demo", project_path=None, ref="c1", kind="adhoc", planner="human")
    assert audits.resolve_project_id(cat, "demo") == cat.execute("SELECT id FROM projects").fetchone()[0]
    with pytest.raises(ChanchiError) as exc:
        audits.resolve_project_id(cat, "ghost")
    assert exc.value.code == "invalid_value"


def test_show_unknown_audit(cat):
    with pytest.raises(ChanchiError) as exc:
        audits.show(cat, 7)
    assert exc.value.code == "unknown_audit"


def test_list_filters(cat):
    a = open_(cat)
    b = open_(cat, kind="item", ref="skill-chanchi-global-x", commit=None, version="0.1.0")
    assert [r["id"] for r in audits.list_audits(cat)] == [a["audit_id"], b["audit_id"]]
    only = audits.list_audits(cat, kind="item")
    assert [(r["id"], r["rounds"], r["outcome"]) for r in only] == [(b["audit_id"], 1, None)]
    assert [r["id"] for r in audits.list_audits(cat, ref="docs/designs/x.md")] == [a["audit_id"]]
    with pytest.raises(ChanchiError):
        audits.list_audits(cat, kind="poem")


# --- CLI ---------------------------------------------------------------------


@pytest.fixture
def cli_env(db_env, tmp_path, monkeypatch, capsys):
    """A scratch database with the roster models, no SYNC and every binary on PATH."""
    monkeypatch.setenv("CHANCHI_SYNC", str(tmp_path / "no-sync"))
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}")
    for agent, model, efforts in (
        ("claude", "sonnet", "low,medium,high"),
        ("agy", "gemini-4-neon-high", "high"),
        ("opencode", "opencode-go/minimax-m3", None),
        ("agy", "gemini-4-hydrogen-high", "high"),
    ):
        argv = ["models", "add", "--agent", agent, "--model", model, "--cost", "1"]
        assert cli.main(argv + (["--efforts", efforts] if efforts else [])) == 0
    capsys.readouterr()
    return capsys


def ok(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    assert code == 0, err
    return json.loads(out)


def fail(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    assert code == 2 and out == ""
    return json.loads(err)["error"]


def test_cli_open_show_list_and_unavailable(cli_env):
    opened = ok(
        cli_env, "audit", "open", "--kind", "design", "--ref", "docs/designs/x.md",
        "--author", "claude:opus:high", "--commit", "abc123",
    )
    assert opened["audit_id"] == 1 and opened["degraded"] is False
    assert [s["family"] for s in opened["seats"]] == ["anthropic", "google", "minimax"]
    assert opened["seats"][0]["launch"].startswith("claude -p --agent agent-chanchi-auditor")
    moved = ok(cli_env, "audit", "unavailable", "1", "--round", "1", "--seat", "2", "--reason", "quota")
    assert moved["seat"]["spec"] == "agy:gemini-4-hydrogen-high:high"
    shown = ok(cli_env, "audit", "show", "1")
    assert [(s["seat"], s["status"]) for s in shown["rounds"][0]["seats"]] == [
        (1, "assigned"), (2, "unavailable"), (2, "assigned"), (3, "assigned"),
    ]
    listed = ok(cli_env, "audit", "list", "--kind", "design")
    assert [(a["id"], a["rounds"]) for a in listed["audits"]] == [(1, 1)]
    assert ok(cli_env, "audit", "list", "--ref", "other")["audits"] == []


def test_cli_roster_comes_from_sync_when_present(cli_env, tmp_path, monkeypatch):
    sync_dir = tmp_path / "sync"
    (sync_dir / "config").mkdir(parents=True)
    (sync_dir / "config" / "auditors.toml").write_text(
        '[[auditor]]\nharness = "agy"\nmodel = "gemini-4-hydrogen-high"\neffort = "high"\n\n'
        '[[auditor]]\nharness = "claude"\nmodel = "sonnet"\neffort = "low"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CHANCHI_SYNC", str(sync_dir))
    opened = ok(
        cli_env, "audit", "open", "--kind", "item", "--ref", "x", "--author", "human", "--version", "0.1.0"
    )
    assert [s["spec"] for s in opened["seats"]] == ["agy:gemini-4-hydrogen-high:high", "claude:sonnet:low"]
    assert opened["outcome"] is None and opened["degraded"] is True


def test_cli_change_without_a_project_is_refused(cli_env, git_repo):
    error = fail(
        cli_env, "audit", "open", "--kind", "design", "--ref", "x", "--author", "human",
        "--commit", "abc", "--change", "c1",
    )
    assert error["code"] == "missing_prerequisite" and "--project" in error["hint"]


def test_cli_project_detected_from_a_recorded_change(cli_env, git_repo):
    ok(cli_env, "change", "open", "c1", "--kind", "adhoc", "--planner", "human")
    opened = ok(
        cli_env, "audit", "open", "--kind", "design", "--ref", "x", "--author", "human",
        "--commit", "abc", "--change", "c1",
    )
    audit = ok(cli_env, "audit", "show", str(opened["audit_id"]))["audit"]
    assert (audit["project"], audit["change"]) == ("demo-app", "c1")
    error = fail(
        cli_env, "audit", "open", "--kind", "design", "--ref", "x", "--author", "human",
        "--commit", "abc", "--project", "ghost",
    )
    assert error["code"] == "invalid_value"
    error = fail(cli_env, "audit", "show", "42")
    assert error["code"] == "unknown_audit"
