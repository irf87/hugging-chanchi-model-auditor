import pytest
from helpers import inc

from chanchi import record, scoring
from chanchi.errors import ChanchiError

FLASH = "agy:gemini-3.8-flash-high:high"
SONNET = "claude:sonnet:medium"


def i(code, severity="low", detected_by="planner_audit", role=None):
    from chanchi import taxonomy

    return {"code": code, "role": role or taxonomy.resolve_role(code, None), "severity": severity,
            "detected_by": detected_by}


# --- pure scores -----------------------------------------------------------


def test_session_score_base_values():
    assert scoring.session_score(None, []) is None
    assert scoring.session_score("accepted", []) == 100
    assert scoring.session_score("accepted_with_fixes", []) == 70
    assert scoring.session_score("rejected", []) == 0


def test_session_score_penalties_and_credit():
    assert scoring.session_score("accepted_with_fixes", [i("rule_violation", "medium")]) == pytest.approx(67)
    late = [i("false_claim", "high", detected_by="post_merge")]
    assert scoring.session_score("accepted", late) == pytest.approx(86.5)
    assert scoring.session_score("rejected", [i("correct_stop")]) == pytest.approx(5)
    assert scoring.session_score("accepted", [i("correct_stop"), i("correct_stop")]) == 100
    assert scoring.session_score("accepted", [i("plan_gap", "blocking")]) == 100
    assert scoring.session_score("accepted", [i("hallucination", "high", role="planner")]) == 100
    assert scoring.session_score("accepted", [i("hallucination", "high", role="executor")]) == pytest.approx(91)


def test_planner_change_score():
    assert scoring.planner_change_score(74, [i("plan_wrong_expectation")]) == pytest.approx(99.3243, abs=1e-4)
    assert scoring.planner_change_score(5, [i("plan_gap", "blocking")]) == pytest.approx(50)
    assert scoring.planner_change_score(20, [i("hallucination", "high", role="planner")]) == pytest.approx(77.5)
    assert scoring.planner_change_score(20, [i("hallucination", "high", role="executor")]) == 100
    assert scoring.planner_change_score(1, [i("plan_delegated_decision", "blocking")] * 3) == 0


def test_smoothed():
    assert scoring.smoothed(100, 1, 70) == pytest.approx(77.5)
    assert scoring.smoothed(80, 0, 70) == pytest.approx(70)


# --- records ---------------------------------------------------------------


def test_executor_records_basic_fields(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, incidents=[inc("rule_violation", "medium"), inc("correct_stop")])
    recorder.session("c1", "S2", FLASH, verdict=None)
    records = scoring.executor_records(recorder.conn)
    assert len(records) == 1
    rec = records[0]
    assert rec["score"] == 100  # 100 - 3 (rule_violation medium) + 5 (correct_stop), clamped
    assert rec["clean"] is False
    assert rec["honesty_flags"] == 0
    assert rec["duration_s"] == 3600
    assert rec["codes"] == ["rule_violation", "correct_stop"]
    assert (rec["agent"], rec["model"], rec["effort"], rec["cost_tier"]) == ("agy", "gemini-3.8-flash-high", "high", 1)


def test_superseded_attempts(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, verdict="rejected")
    recorder.session("c1", "S1", FLASH, retry_reason="human_change")
    recorder.session("c1", "S2", FLASH, verdict="rejected")
    recorder.session("c1", "S2", FLASH, retry_reason="executor_failure")
    records = scoring.executor_records(recorder.conn)
    keys = sorted((r["session_ref"], r["attempt"], r["failed_attempt"]) for r in records)
    assert keys == [("S1", 2, False), ("S2", 1, True), ("S2", 2, False)]


def test_voided_incidents_are_ignored(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, incidents=[inc("false_claim", "high")])
    incident_id = recorder.conn.execute("SELECT id FROM incidents").fetchone()[0]
    assert scoring.executor_records(recorder.conn)[0]["score"] == pytest.approx(91)
    record.void_incident(recorder.conn, incident_id=incident_id, reason="re-run passed")
    assert scoring.executor_records(recorder.conn)[0]["score"] == 100


def test_since_filter(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, started="2026-08-01T10:00:00Z", ended="2026-08-01T11:00:00Z")
    recorder.session("c1", "S2", FLASH)
    assert len(scoring.executor_records(recorder.conn, since="2026-09-01T00:00:00Z")) == 1


def test_summarize_metrics(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH)
    recorder.session("c1", "S2", FLASH, verdict="accepted_with_fixes", incidents=[inc("false_claim")])
    recorder.session("c1", "S3", FLASH, verdict="rejected")
    recorder.session("c1", "S3", FLASH, retry_reason="executor_failure")
    records = scoring.executor_records(recorder.conn)
    summary = scoring.summarize(records, prior=70)
    assert summary["n"] == 4
    assert summary["mean_score"] == pytest.approx((100 + 67 + 0 + 100) / 4)
    assert summary["clean_rate"] == pytest.approx(0.5)
    assert summary["first_attempt_acceptance"] == pytest.approx(2 / 3, abs=1e-3)
    assert summary["honesty_flags_per_session"] == pytest.approx(0.25)
    assert summary["red_flag"] is True
    assert summary["retry_rate"] == pytest.approx(0.25)
    assert summary["confidence"] == "low"
    assert summary["top_codes"] == ["false_claim"]


def test_summarize_empty():
    summary = scoring.summarize([], prior=80)
    assert summary["n"] == 0
    assert summary["mean_score"] is None
    assert summary["smoothed_score"] == 80
    assert summary["confidence"] == "insufficient"
    assert summary["red_flag"] is False
    assert summary["top_codes"] == []


def test_prior_fallbacks(recorder):
    assert scoring.prior_for([]) == 70
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, task_type="tests", complexity="low", verdict="accepted_with_fixes")
    records = scoring.executor_records(recorder.conn)
    assert scoring.prior_for(records, "tests", "low") == 70
    assert scoring.prior_for(records, "ui-component", "medium") == 70
    recorder.session("c1", "S2", FLASH)
    records = scoring.executor_records(recorder.conn)
    assert scoring.prior_for(records, "ui-component", "medium") == 100
    assert scoring.prior_for(records, "docs", "high") == pytest.approx(85)


# --- stats -----------------------------------------------------------------


def test_executor_stats_by_model(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH)
    recorder.session("c1", "S2", FLASH, verdict="accepted_with_fixes", incidents=[inc("rule_violation", "medium")])
    recorder.session("c1", "S3", SONNET)
    result = scoring.stats(recorder.conn, role="executor", by="model")
    assert result["role"] == "executor" and result["by"] == "model"
    rows = result["rows"]
    assert [r["spec"] for r in rows] == [SONNET, FLASH]
    assert rows[0]["smoothed_score"] == pytest.approx(91.75)
    assert rows[1]["smoothed_score"] == pytest.approx(86.8)
    assert rows[1]["cost_tier"] == 1


def test_executor_stats_by_task_type_and_project(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, task_type="tests", complexity="low")
    recorder.session("c1", "S2", FLASH)
    by_type = scoring.stats(recorder.conn, by="task-type")["rows"]
    assert sorted((r["task_type"], r["complexity"]) for r in by_type) == [("tests", "low"), ("ui-component", "medium")]
    by_project = scoring.stats(recorder.conn, by="project")["rows"]
    assert by_project[0]["project"] == "demo-app" and by_project[0]["n"] == 2
    with pytest.raises(ChanchiError) as info:
        scoring.stats(recorder.conn, by="color")
    assert info.value.field == "by"
    with pytest.raises(ChanchiError) as info:
        scoring.stats(recorder.conn, role="robot")
    assert info.value.field == "role"


def test_planner_stats(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, tasks=10)
    record.add_incident(recorder.conn, project_id=recorder.pid, ref="c1", **inc("plan_gap", "blocking", "executor_stop"))
    recorder.change("c2")
    recorder.session("c2", "S1", FLASH, verdict=None)
    recorder.change("c3", planner="human", kind="adhoc")
    recorder.session("c3", "S1", FLASH)
    planners = scoring.planner_records(recorder.conn)
    assert [(p["ref"], p["score"]) for p in planners] == [("c1", pytest.approx(50))]
    rows = scoring.stats(recorder.conn, role="planner", by="model")["rows"]
    assert rows[0]["spec"] == "claude:opus:xhigh"
    assert rows[0]["n"] == 1 and rows[0]["mean_score"] == pytest.approx(50)
    assert rows[0]["plan_incidents_per_change"] == 1
    with pytest.raises(ChanchiError) as info:
        scoring.stats(recorder.conn, role="planner", by="task-type")
    assert info.value.valid_values == ["model", "project"]


def test_planner_tasks_use_latest_attempt(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, tasks=4, verdict="rejected")
    recorder.session("c1", "S1", FLASH, tasks=20, retry_reason="executor_failure")
    assert scoring.planner_records(recorder.conn)[0]["tasks"] == 20


def test_human_stats(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, incidents=[inc("correct_stop", detected_by="executor_stop")])
    pid = recorder.pid
    record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("plan_gap", "high", "executor_stop"))
    record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("human_unclear_requirement", "high", "executor_stop"))
    record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("human_scope_addition", "medium", "human"))
    rows = scoring.stats(recorder.conn, role="human")["rows"]
    assert rows == [
        {
            "project": "demo-app",
            "human_incidents": {"human_unclear_requirement": 1, "human_scope_addition": 1},
            "stops_total": 2,
            "stops_by_human": 1,
            "human_stop_share": 0.5,
        }
    ]


# --- recommend -------------------------------------------------------------


def test_recommend_without_data(recorder):
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    assert result["recommendation"] is None
    assert result["reason"] == "insufficient_data"
    assert [c["level"] for c in result["candidates"]] == [None, None]
    assert all(c["n"] == 0 for c in result["candidates"])


def test_recommend_prefers_cheapest_within_window(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, SONNET)
    recorder.session("c1", "S4", FLASH)
    recorder.session("c1", "S5", FLASH)
    recorder.session("c1", "S6", FLASH, incidents=[inc("rule_violation")])
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[SONNET, FLASH])
    by_spec = {c["spec"]: c for c in result["candidates"]}
    assert by_spec[SONNET]["smoothed_score"] == pytest.approx(99.88, abs=0.01)
    assert by_spec[FLASH]["smoothed_score"] == pytest.approx(99.62, abs=0.01)
    assert result["candidates"][0]["spec"] == SONNET
    assert result["recommendation"]["spec"] == FLASH
    assert result["recommendation"]["level"] == "task_type+complexity"
    assert result["reason"] is None


def test_recommend_outside_window_picks_best(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, SONNET)
    for ref in ("S4", "S5", "S6"):
        recorder.session("c1", ref, FLASH, verdict="accepted_with_fixes")
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    by_spec = {c["spec"]: c for c in result["candidates"]}
    assert by_spec[FLASH]["smoothed_score"] == pytest.approx(77.5)
    assert by_spec[SONNET]["smoothed_score"] == pytest.approx(92.5)
    assert result["recommendation"]["spec"] == SONNET


def test_recommend_excludes_red_flagged(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, FLASH, incidents=[inc("false_claim")])
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    flash = next(c for c in result["candidates"] if c["spec"] == FLASH)
    assert flash["red_flag"] is True and flash["confidence"] == "low"
    assert result["recommendation"] is None
    assert result["reason"] == "all_candidates_red_flagged"


def test_recommend_fallback_levels(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, FLASH, complexity="high")
    recorder.session("c1", "S4", SONNET, task_type="docs", complexity="medium")
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    by_spec = {c["spec"]: c for c in result["candidates"]}
    assert by_spec[FLASH]["level"] == "task_type"
    assert by_spec[FLASH]["n"] == 3
    assert by_spec[SONNET]["level"] == "complexity"
    assert by_spec[SONNET]["confidence"] == "insufficient"
    assert result["recommendation"]["spec"] == FLASH


def test_recommend_matches_effort_exactly(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, FLASH)
    result = scoring.recommend(
        recorder.conn, task_type="ui-component", complexity="medium", available=["agy:gemini-3.8-flash-high:medium"]
    )
    assert result["candidates"][0]["n"] == 0


def test_recommend_validations(recorder):
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=["claude:gpt-9"])
    assert info.value.code == "unknown_model"
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=["human"])
    assert info.value.field == "executor"
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[])
    assert info.value.field == "available"
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="nope", complexity="medium", available=[FLASH])
    assert info.value.field == "task_type"


def test_recommend_deduplicates_candidates(recorder):
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, FLASH])
    assert len(result["candidates"]) == 1


# --- show / explain --------------------------------------------------------


def test_show_change(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, tasks=10, incidents=[inc("correct_stop", detected_by="executor_stop")])
    pid = recorder.pid
    gap = record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("plan_gap", "blocking", "executor_stop"))
    extra = record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("plan_conflict", "high"))
    record.void_incident(recorder.conn, incident_id=extra["id"], reason="duplicate of the gap")
    shown = scoring.show_change(recorder.conn, project_id=pid, ref="c1")
    assert shown["change"]["ref"] == "c1"
    assert shown["sessions"][0]["score"] == 100
    assert [i["id"] for i in shown["incidents"]] == [1, gap["id"], extra["id"]]
    assert shown["incidents"][-1]["voided_at"] is not None
    assert shown["planner_score"] == pytest.approx(50)
    assert shown["incident_counts_by_role"] == {"executor": 1, "planner": 1}


def test_show_change_without_audit_has_no_planner_score(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, verdict=None)
    assert scoring.show_change(recorder.conn, project_id=recorder.pid, ref="c1")["planner_score"] is None


def test_explain_reflects_taxonomy():
    from chanchi import taxonomy

    explained = scoring.explain()
    assert explained["executor_session_score"]["weights"] == taxonomy.EXECUTOR_WEIGHTS
    assert explained["planner_change_score"]["weights"] == taxonomy.PLANNER_WEIGHTS
    assert explained["severity_multipliers"] == taxonomy.SEVERITY_MULT
    assert explained["smoothing"]["k"] == 3
    assert explained["recommendation"]["window"] == 5.0
