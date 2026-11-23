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
        "claude -p --agent agent-chanchi-auditor --model sonnet --effort medium "
        '--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob" '
        '--add-dir "<report-dir>" -- "<prompt>" < /dev/null'
    )
    assert result["seats"][1]["launch"] == (
        "agy --agent agent-chanchi-auditor --model gemini-4-neon --effort high "
        '--dangerously-skip-permissions --add-dir "<report-dir>" -p="<prompt>" < /dev/null'
    )
    assert result["seats"][2]["launch"] == (
        'opencode run --agent agent-chanchi-auditor -m opencode-go/minimax-m3 --auto "<prompt>" < /dev/null'
    )
    row = cat.execute("SELECT * FROM audit_rounds WHERE audit_id = ?", (result["audit_id"],)).fetchone()
    assert (row["round"], row["subject_at"], row["degraded"], row["closed_at"]) == (1, "abc123", 0, None)


def test_version_subject_and_author_resolution(cat):
    cat.execute("INSERT INTO models (agent, model, cost_tier, active, created_at) VALUES ('claude','opus',3,1,'t')")
    result = open_(cat, commit=None, version="1.2.0", kind="other", ref="skill-chanchi-global-x")
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
    b = open_(cat, kind="other", ref="skill-chanchi-global-x", commit=None, version="0.1.0")
    assert [r["id"] for r in audits.list_audits(cat)] == [a["audit_id"], b["audit_id"]]
    only = audits.list_audits(cat, kind="other")
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
    assert opened["seats"][0]["launch"] == (
        "claude -p --agent agent-chanchi-auditor --model sonnet --effort medium "
        '--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob" '
        '--add-dir "<report-dir>" -- "<prompt>" < /dev/null'
    )
    moved = ok(cli_env, "audit", "unavailable", "1", "--round", "1", "--seat", "2", "--reason", "quota")
    assert moved["seat"]["spec"] == "agy:gemini-4-hydrogen-high:high"
    assert moved["seat"]["launch"] == (
        "agy --agent agent-chanchi-auditor --model gemini-4-hydrogen --effort high "
        '--dangerously-skip-permissions --add-dir "<report-dir>" -p="<prompt>" < /dev/null'
    )
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
        cli_env, "audit", "open", "--kind", "other", "--ref", "x", "--author", "human", "--version", "0.1.0"
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


# --- outcome (pure function) -------------------------------------------------


def _v(verdict, blocking=0, major=0, minor=0):
    return {"verdict": verdict, "blocking": blocking, "major": major, "minor": minor}


def _d(severity, decision):
    return {"severity": severity, "decision": decision}


@pytest.mark.parametrize(
    ("votes", "dissents", "round_no", "expected"),
    [
        # 1. fewer than two voted -> escalated / quorum, whatever the round
        ([], [], 1, ("escalated", "quorum")),
        ([_v("pass")], [], 1, ("escalated", "quorum")),
        ([_v("fail")], [], 2, ("escalated", "quorum")),
        ([_v("pass")], [], 3, ("escalated", "quorum")),
        # 2. at least two fail -> rework (round_cap on round 3)
        ([_v("fail"), _v("fail"), _v("pass")], [], 1, ("rework", None)),
        ([_v("fail"), _v("fail")], [], 2, ("rework", None)),
        ([_v("fail"), _v("fail"), _v("pass")], [], 3, ("escalated", "round_cap")),
        # 3. at least two approvals (pass, or pass_with_fixes 0/0/n) and no confirmed blocking/major dissent -> accepted
        ([_v("pass"), _v("pass"), _v("fail")], [], 1, ("accepted", None)),
        ([_v("pass_with_fixes", minor=4), _v("pass_with_fixes", minor=2), _v("pass_with_fixes", major=1)], [], 1, ("accepted", None)),
        ([_v("pass"), _v("pass_with_fixes", minor=1)], [], 1, ("accepted", None)),
        ([_v("pass"), _v("pass_with_fixes", minor=3), _v("pass_with_fixes", major=1)], [_d("major", "rejected")], 1, ("accepted", None)),
        ([_v("pass"), _v("pass"), _v("pass_with_fixes", minor=1)], [_d("minor", "confirmed")], 1, ("accepted", None)),
        ([_v("pass"), _v("pass_with_fixes", minor=2), _v("pass_with_fixes", major=1)], [], 3, ("accepted", None)),
        # 4. otherwise -> fix (round_cap on round 3)
        ([_v("pass"), _v("pass_with_fixes", minor=1), _v("pass_with_fixes", major=1)], [_d("major", "confirmed")], 1, ("fix", None)),
        ([_v("pass"), _v("pass"), _v("pass_with_fixes", blocking=1)], [_d("blocking", "confirmed")], 2, ("fix", None)),
        ([_v("pass"), _v("pass_with_fixes", major=1), _v("fail")], [], 1, ("fix", None)),
        ([_v("pass_with_fixes", major=2), _v("pass_with_fixes", major=1), _v("pass_with_fixes", major=1)], [], 1, ("fix", None)),
        ([_v("pass"), _v("pass_with_fixes", minor=6), _v("pass_with_fixes", major=2, minor=2)], [_d("major", "confirmed"), _d("major", "confirmed")], 3, ("escalated", "round_cap")),
    ],
)
def test_outcome_rules(votes, dissents, round_no, expected):
    assert audits.outcome(votes, dissents, round_no) == expected


# --- vote, dissent, close_round, next_round ----------------------------------


def _vote_all(conn, audit_id, *, round=1, specs_votes=None):
    default = ("pass", 0, 0, 0, "/tmp/r.md")
    for seat in (1, 2, 3):
        verdict, b, m, mn, rep = (specs_votes or {}).get(seat, default)
        audits.vote(conn, audit_id, round=round, seat=seat, verdict=verdict, blocking=b, major=m, minor=mn, report=rep)


def test_vote_validations_and_guards(cat):
    opened = open_(cat)
    aid = opened["audit_id"]
    with pytest.raises(ChanchiError) as pass_major:
        audits.vote(cat, aid, round=1, seat=1, verdict="pass", blocking=0, major=1, minor=0, report="/tmp/r1.md")
    assert pass_major.value.code == "invalid_value" and pass_major.value.field == "verdict"
    assert "pass_with_fixes" in pass_major.value.hint

    with pytest.raises(ChanchiError) as pass_blocking:
        audits.vote(cat, aid, round=1, seat=1, verdict="pass", blocking=1, major=0, minor=0, report="/tmp/r1.md")
    assert pass_blocking.value.code == "invalid_value" and pass_blocking.value.field == "verdict"

    with pytest.raises(ChanchiError) as neg:
        audits.vote(cat, aid, round=1, seat=1, verdict="fail", blocking=-1, major=0, minor=0, report="/tmp/r1.md")
    assert neg.value.code == "invalid_value"

    with pytest.raises(ChanchiError) as blank_rep:
        audits.vote(cat, aid, round=1, seat=1, verdict="pass", blocking=0, major=0, minor=0, report="   ")
    assert blank_rep.value.code == "invalid_value" and blank_rep.value.field == "report"

    res = audits.vote(cat, aid, round=1, seat=1, verdict="pass", blocking=0, major=0, minor=2, report="/tmp/r1.md")
    assert res["seat"]["status"] == "voted" and res["seat"]["minor"] == 2

    with pytest.raises(ChanchiError) as revote:
        audits.vote(cat, aid, round=1, seat=1, verdict="fail", blocking=1, major=0, minor=0, report="/tmp/r1.md")
    assert revote.value.code == "invalid_transition"

    audits.vote(cat, aid, round=1, seat=2, verdict="pass", blocking=0, major=0, minor=0, report="/tmp/r2.md")
    audits.vote(cat, aid, round=1, seat=3, verdict="pass", blocking=0, major=0, minor=0, report="/tmp/r3.md")
    audits.close_round(cat, aid, round=1)
    with pytest.raises(ChanchiError) as closed:
        audits.vote(cat, aid, round=1, seat=1, verdict="pass", blocking=0, major=0, minor=0, report="/tmp/r1.md")
    assert closed.value.code == "invalid_transition"


def test_dissent_validations_and_guards(cat):
    aid = open_(cat)["audit_id"]
    with pytest.raises(ChanchiError) as not_voted:
        audits.dissent(
            cat, aid, round=1, seat=1, finding="F1: gap", severity="major", decision="confirmed", evidence="checked"
        )
    assert not_voted.value.code == "invalid_transition"

    audits.vote(cat, aid, round=1, seat=1, verdict="pass_with_fixes", blocking=0, major=1, minor=0, report="/tmp/r1.md")
    with pytest.raises(ChanchiError) as blank:
        audits.dissent(cat, aid, round=1, seat=1, finding=" ", severity="major", decision="confirmed", evidence="ok")
    assert blank.value.code == "invalid_value" and blank.value.field == "finding"
    with pytest.raises(ChanchiError) as blank_ev:
        audits.dissent(cat, aid, round=1, seat=1, finding="F1: gap", severity="major", decision="confirmed", evidence="  ")
    assert blank_ev.value.code == "invalid_value" and blank_ev.value.field == "evidence"

    d = audits.dissent(
        cat, aid, round=1, seat=1, finding="F1: gap", severity="major", decision="confirmed", evidence="line 10"
    )
    assert d["dissent"]["decision"] == "confirmed"

    audits.vote(cat, aid, round=1, seat=2, verdict="pass", blocking=0, major=0, minor=0, report="/tmp/r2.md")
    audits.vote(cat, aid, round=1, seat=3, verdict="pass", blocking=0, major=0, minor=0, report="/tmp/r3.md")
    audits.close_round(cat, aid, round=1)
    with pytest.raises(ChanchiError) as closed:
        audits.dissent(
            cat, aid, round=1, seat=2, finding="F2: late", severity="minor", decision="rejected", evidence="no"
        )
    assert closed.value.code == "invalid_transition"


def test_close_round_guards_and_accepted_minors(cat):
    aid = open_(cat)["audit_id"]
    audits.vote(cat, aid, round=1, seat=1, verdict="pass_with_fixes", blocking=0, major=0, minor=3, report="/tmp/r1.md")
    audits.vote(cat, aid, round=1, seat=2, verdict="pass", blocking=0, major=0, minor=0, report="/tmp/r2.md")
    with pytest.raises(ChanchiError) as still_assigned:
        audits.close_round(cat, aid, round=1)
    assert still_assigned.value.code == "invalid_transition"

    audits.vote(cat, aid, round=1, seat=3, verdict="pass_with_fixes", blocking=0, major=1, minor=2, report="/tmp/r3.md")
    audits.dissent(
        cat, aid, round=1, seat=3, finding="M1: lone major", severity="major", decision="rejected", evidence="invalid"
    )
    audits.dissent(
        cat, aid, round=1, seat=3, finding="m1: lone minor", severity="minor", decision="confirmed", evidence="valid"
    )
    audits.dissent(
        cat, aid, round=1, seat=3, finding="m2: nope", severity="minor", decision="rejected", evidence="not needed"
    )
    closed = audits.close_round(cat, aid, round=1)
    assert closed["outcome"] == "accepted" and closed["escalation"] is None
    assert closed["audit_closed_at"] is not None
    assert closed["minor_fixes"] == [
        {"kind": "seat", "seat": 1, "spec": "claude:sonnet:medium", "minor": 3, "report": "/tmp/r1.md"},
        {
            "kind": "dissent",
            "seat": 3,
            "spec": "opencode:opencode-go/minimax-m3",
            "finding": "m1: lone minor",
            "evidence": "valid",
        },
    ]
    with pytest.raises(ChanchiError) as reclose:
        audits.close_round(cat, aid, round=1)
    assert reclose.value.code == "invalid_transition"
    with pytest.raises(ChanchiError) as after_accepted:
        audits.next_round(cat, aid, commit="def456", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    assert after_accepted.value.code == "invalid_transition"


def test_next_round_keeps_seats_refills_missing_and_enforces_cap(cat):
    aid = open_(cat)["audit_id"]
    with pytest.raises(ChanchiError) as open_round:
        audits.next_round(cat, aid, commit="def456", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    assert open_round.value.code == "invalid_transition"

    _vote_all(cat, aid, round=1, specs_votes={
        1: ("fail", 1, 0, 0, "/tmp/1.md"),
        2: ("fail", 2, 0, 0, "/tmp/2.md"),
        3: ("pass", 0, 0, 0, "/tmp/3.md"),
    })
    r1 = audits.close_round(cat, aid, round=1)
    assert r1["outcome"] == "rework" and r1["audit_closed_at"] is None

    # opencode goes off PATH before round 2 -> seat 3 refills with fallback (degraded) while seats 1 & 2 stay
    r2_open = audits.next_round(cat, aid, commit="def456", roster=sync.BUILTIN_ROSTER, which=which_with("claude", "agy"))
    assert r2_open["round"] == 2 and r2_open["degraded"] is True
    assert [(s["seat"], s["spec"]) for s in r2_open["seats"]] == [
        (1, "claude:sonnet:medium"),
        (2, "agy:gemini-4-neon-high:high"),
        (3, "agy:gemini-4-hydrogen-high:high"),
    ]
    _vote_all(cat, aid, round=2, specs_votes={
        1: ("pass_with_fixes", 0, 1, 0, "/tmp/21.md"),
        2: ("pass", 0, 0, 0, "/tmp/22.md"),
        3: ("pass_with_fixes", 0, 1, 0, "/tmp/23.md"),
    })
    assert audits.close_round(cat, aid, round=2)["outcome"] == "fix"

    r3_open = audits.next_round(cat, aid, commit="ghi789", roster=sync.BUILTIN_ROSTER, which=which_with("claude", "agy"))
    assert r3_open["round"] == 3
    _vote_all(cat, aid, round=3, specs_votes={
        1: ("pass_with_fixes", 0, 1, 0, "/tmp/31.md"),
        2: ("pass", 0, 0, 0, "/tmp/32.md"),
        3: ("pass", 0, 0, 0, "/tmp/33.md"),
    })
    audits.dissent(cat, aid, round=3, seat=1, finding="R3: lone", severity="major", decision="confirmed", evidence="yes")
    r3_close = audits.close_round(cat, aid, round=3)
    assert (r3_close["outcome"], r3_close["escalation"]) == ("escalated", "round_cap")
    assert r3_close["audit_closed_at"] is not None

    with pytest.raises(ChanchiError) as past_cap:
        audits.next_round(cat, aid, commit="jkl000", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    assert past_cap.value.code == "invalid_transition"


def test_next_round_quorum_escalation(cat):
    aid = open_(cat)["audit_id"]
    _vote_all(cat, aid, round=1, specs_votes={
        1: ("pass_with_fixes", 0, 1, 0, "/tmp/1.md"),
        2: ("pass_with_fixes", 0, 1, 0, "/tmp/2.md"),
        3: ("pass", 0, 0, 0, "/tmp/3.md"),
    })
    audits.close_round(cat, aid, round=1)
    r2 = audits.next_round(cat, aid, commit="def456", roster=sync.BUILTIN_ROSTER, which=which_with("claude"))
    assert r2["outcome"] == "escalated" and r2["escalation"] == "quorum"
    assert len(r2["seats"]) == 1 and r2["seats"][0]["launch"] is None
    assert cat.execute("SELECT closed_at FROM audits WHERE id = ?", (aid,)).fetchone()[0] is not None


def test_next_round_version_and_deactivated_model_refill(cat):
    aid = open_(cat, kind="other", ref="skill-chanchi-global-x", commit=None, version="0.1.0")["audit_id"]
    _vote_all(cat, aid, round=1, specs_votes={
        1: ("pass_with_fixes", 0, 1, 0, "/tmp/1.md"),
        2: ("pass_with_fixes", 0, 1, 0, "/tmp/2.md"),
        3: ("pass", 0, 0, 0, "/tmp/3.md"),
    })
    audits.close_round(cat, aid, round=1)
    catalog.set_model(cat, spec="opencode:opencode-go/minimax-m3", active=False)
    with pytest.raises(ChanchiError) as bad_subj:
        audits.next_round(cat, aid, commit="abc", version="0.1.1", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    assert bad_subj.value.code == "invalid_value"
    r2 = audits.next_round(cat, aid, version="0.1.1", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    assert [s["spec"] for s in r2["seats"]] == [
        "claude:sonnet:medium",
        "agy:gemini-4-neon-high:high",
        "agy:gemini-4-hydrogen-high:high",
    ]
    assert r2["degraded"] is True


def test_close_round_quorum_after_unavailable_exhaustion(cat):
    aid = open_(cat)["audit_id"]
    audits.mark_unavailable(cat, aid, round=1, seat=2, reason="err", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    audits.mark_unavailable(cat, aid, round=1, seat=2, reason="err", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    audits.mark_unavailable(cat, aid, round=1, seat=3, reason="err", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    audits.vote(cat, aid, round=1, seat=1, verdict="pass", blocking=0, major=0, minor=0, report="/tmp/1.md")
    closed = audits.close_round(cat, aid, round=1)
    assert (closed["outcome"], closed["escalation"]) == ("escalated", "quorum")
    assert closed["audit_closed_at"] is not None


def test_global_items_history_reproduction(cat):
    """Reproduce docs/designs/global-items.md rounds 1-3 from Task 8's table (decision D9)."""
    opened = audits.open_audit(
        cat,
        kind="design",
        ref="docs/designs/global-items.md",
        author="claude:opus:high",
        commit="953ac5a",
        roster=sync.BUILTIN_ROSTER,
        which=ALL_BINARIES,
    )
    aid = opened["audit_id"]
    assert [s["spec"] for s in opened["seats"]] == [
        "claude:sonnet:medium",
        "agy:gemini-4-neon-high:high",
        "opencode:opencode-go/minimax-m3",
    ]

    # Round 1 at 953ac5a -> fix
    _vote_all(cat, aid, round=1, specs_votes={
        1: ("pass_with_fixes", 0, 8, 12, "docs/designs/reviews/global-items/round1-claude-sonnet.md"),
        2: ("pass_with_fixes", 3, 5, 4, "docs/designs/reviews/global-items/round1-agy-gemini-4-neon.md"),
        3: ("pass_with_fixes", 2, 6, 10, "docs/designs/reviews/global-items/round1-opencode-minimax-m3.md"),
    })
    r1 = audits.close_round(cat, aid, round=1)
    assert (r1["outcome"], r1["escalation"]) == ("fix", None)

    # Round 2 at a7a1a20 -> fix (open counts after re-check, partial carry-overs at original severity)
    audits.next_round(cat, aid, commit="a7a1a20", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    _vote_all(cat, aid, round=2, specs_votes={
        1: ("pass_with_fixes", 0, 2, 8, "docs/designs/reviews/global-items/round2-claude-sonnet.md"),
        2: ("pass_with_fixes", 0, 5, 2, "docs/designs/reviews/global-items/round2-agy-gemini-4-neon.md"),
        3: ("pass_with_fixes", 1, 3, 6, "docs/designs/reviews/global-items/round2-opencode-minimax-m3.md"),
    })
    r2 = audits.close_round(cat, aid, round=2)
    assert (r2["outcome"], r2["escalation"]) == ("fix", None)

    # Round 3 at e40d275 -> escalated / round_cap due to seat 3's two confirmed lone major dissents
    audits.next_round(cat, aid, commit="e40d275", roster=sync.BUILTIN_ROSTER, which=ALL_BINARIES)
    _vote_all(cat, aid, round=3, specs_votes={
        1: ("pass_with_fixes", 0, 0, 6, "docs/designs/reviews/global-items/round3-claude-sonnet.md"),
        2: ("pass", 0, 0, 2, "docs/designs/reviews/global-items/round3-agy-gemini-4-neon.md"),
        3: ("pass_with_fixes", 0, 2, 2, "docs/designs/reviews/global-items/round3-opencode-minimax-m3.md"),
    })
    audits.dissent(
        cat, aid, round=3, seat=3,
        finding="R3-01: lesson apply --where syntax and precondition",
        severity="major", decision="confirmed",
        evidence="src/chanchi/lessons.py requires [lesson #<id>] and an approved agnostic lesson",
    )
    audits.dissent(
        cat, aid, round=3, seat=3,
        finding="R3-02: Principle 4 claims test_items.py check exists already",
        severity="major", decision="confirmed",
        evidence="tests/test_items.py does not enforce -chanchi-global- exclusion yet (phase 2)",
    )
    r3 = audits.close_round(cat, aid, round=3)
    assert (r3["outcome"], r3["escalation"]) == ("escalated", "round_cap")

    shown = audits.show(cat, aid)
    assert shown["audit"]["outcome"] == "escalated" and shown["audit"]["closed_at"] is not None
    assert [(r["round"], r["subject_at"], r["outcome"], r["escalation"]) for r in shown["rounds"]] == [
        (1, "953ac5a", "fix", None),
        (2, "a7a1a20", "fix", None),
        (3, "e40d275", "escalated", "round_cap"),
    ]
    assert len(shown["rounds"][2]["seats"][2]["dissents"]) == 2


def test_cli_vote_dissent_close_and_round(cli_env):
    ok(
        cli_env, "audit", "open", "--kind", "design", "--ref", "docs/designs/x.md",
        "--author", "claude:opus:high", "--commit", "abc123",
    )
    bad = fail(
        cli_env, "audit", "vote", "1", "--round", "1", "--seat", "1",
        "--verdict", "pass", "--blocking", "0", "--major", "1", "--minor", "0", "--report", "/tmp/r1.md",
    )
    assert bad["code"] == "invalid_value" and bad["field"] == "verdict"

    v1 = ok(
        cli_env, "audit", "vote", "1", "--round", "1", "--seat", "1",
        "--verdict", "pass_with_fixes", "--blocking", "0", "--major", "1", "--minor", "2", "--report", "/tmp/r1.md",
    )
    assert v1["seat"]["status"] == "voted"
    ok(
        cli_env, "audit", "vote", "1", "--round", "1", "--seat", "2",
        "--verdict", "pass", "--blocking", "0", "--major", "0", "--minor", "1", "--report", "/tmp/r2.md",
    )
    ok(
        cli_env, "audit", "vote", "1", "--round", "1", "--seat", "3",
        "--verdict", "pass", "--blocking", "0", "--major", "0", "--minor", "0", "--report", "/tmp/r3.md",
    )
    d1 = ok(
        cli_env, "audit", "dissent", "1", "--round", "1", "--seat", "1",
        "--finding", "F1: gap", "--severity", "major", "--decision", "confirmed", "--evidence", "verified",
    )
    assert d1["dissent"]["severity"] == "major"
    c1 = ok(cli_env, "audit", "close", "1", "--round", "1")
    assert c1["outcome"] == "fix"

    r2 = ok(cli_env, "audit", "round", "1", "--commit", "def456")
    assert r2["round"] == 2 and len(r2["seats"]) == 3
    for seat in ("1", "2", "3"):
        ok(
            cli_env, "audit", "vote", "1", "--round", "2", "--seat", seat,
            "--verdict", "pass_with_fixes", "--blocking", "0", "--major", "0", "--minor", "1",
            "--report", f"/tmp/r2-{seat}.md",
        )
    c2 = ok(cli_env, "audit", "close", "1", "--round", "2")
    assert c2["outcome"] == "accepted" and len(c2["minor_fixes"]) == 3
    shown = ok(cli_env, "audit", "show", "1")
    assert shown["audit"]["outcome"] == "accepted" and len(shown["rounds"]) == 2
