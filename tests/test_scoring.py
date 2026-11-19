import pytest
from helpers import inc

from chanchi import catalog, record, scoring
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


def test_session_score_architecture_violation():
    incident = i("architecture_violation", "medium", detected_by="planner_audit")
    assert scoring.session_score("accepted_with_fixes", [incident]) == pytest.approx(66)


def test_session_score_code_smell():
    incident = i("code_smell", "low", detected_by="planner_audit")
    assert scoring.session_score("accepted", [incident]) == pytest.approx(99)


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


# --- dimensions ------------------------------------------------------------


def test_dimension_score_penalises_only_its_own_codes():
    incident = i("architecture_violation", "medium")
    assert scoring.dimension_score("architecture", [incident]) == pytest.approx(96)
    assert scoring.dimension_score("clean-code", [incident]) == 100
    assert scoring.dimension_score("discipline", [incident]) == 100


def test_dimension_score_counts_late_detection():
    late = [i("false_claim", "high", detected_by="post_merge")]
    assert scoring.dimension_score("honesty", late) == pytest.approx(86.5)
    assert scoring.dimension_score("correctness", late) == 100


def test_dimension_score_ignores_correct_stop_and_planner_incidents():
    assert scoring.dimension_score("discipline", [i("correct_stop")]) == 100
    assert scoring.dimension_score("honesty", [i("hallucination", "high", role="planner")]) == 100


def test_stats_by_dimension(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, incidents=[inc("architecture_violation", "medium")])
    recorder.session("c1", "S2", FLASH, incidents=[inc("code_smell", "low")])
    recorder.session("c1", "S3", FLASH, incidents=[inc("rule_violation", "medium")])
    result = scoring.stats(recorder.conn, role="executor", by="dimension")
    assert result["role"] == "executor" and result["by"] == "dimension"
    assert result["note"] == scoring.DIMENSION_NOTE
    rows = {r["dimension"]: r for r in result["rows"]}
    assert [r["dimension"] for r in result["rows"]] == [
        "correctness",
        "architecture",
        "clean-code",
        "honesty",
        "discipline",
    ]
    assert rows["architecture"]["mean_score"] == pytest.approx(98.67, abs=0.01)
    assert rows["clean-code"]["mean_score"] == pytest.approx(99.67, abs=0.01)
    assert rows["discipline"]["mean_score"] == pytest.approx(99.0, abs=0.01)
    assert rows["correctness"]["mean_score"] == 100.0
    assert rows["honesty"]["mean_score"] == 100.0
    for row in rows.values():
        assert row["n"] == 3
        assert row["spec"] == FLASH
        assert row["cost_tier"] == 1
        assert row["confidence"] == "low"
    assert rows["architecture"]["incident_count"] == 1
    assert rows["clean-code"]["incident_count"] == 1
    assert rows["discipline"]["incident_count"] == 1
    assert rows["correctness"]["incident_count"] == 0
    assert rows["honesty"]["incident_count"] == 0
    assert rows["architecture"]["sessions_with_incidents"] == 1
    assert rows["architecture"]["incidents_per_session"] == pytest.approx(0.333)
    assert rows["correctness"]["sessions_with_incidents"] == 0
    assert rows["architecture"]["top_codes"] == ["architecture_violation"]
    assert rows["correctness"]["top_codes"] == []
    assert rows["honesty"]["top_codes"] == []
    assert rows["architecture"]["prior"] == pytest.approx(98.67, abs=0.01)
    assert rows["architecture"]["smoothed_score"] == pytest.approx(
        scoring.smoothed(rows["architecture"]["mean_score"], 3, rows["architecture"]["prior"]), abs=0.01
    )


def test_stats_by_dimension_is_executor_only(recorder):
    with pytest.raises(ChanchiError) as info:
        scoring.stats(recorder.conn, role="planner", by="dimension")
    assert info.value.field == "by"
    assert info.value.valid_values == ["model", "project"]


def test_stats_by_dimension_has_no_note_in_other_views(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH)
    assert "note" not in scoring.stats(recorder.conn, role="executor", by="model")
    assert "note" not in scoring.stats(recorder.conn, role="planner", by="model")
    assert "note" not in scoring.stats(recorder.conn, role="human")


def test_executor_records_keep_executor_incidents(recorder):
    recorder.change("c1")
    recorder.session(
        "c1", "S1", FLASH, incidents=[inc("rule_violation", "medium"), inc("correct_stop")]
    )
    executor_record = scoring.executor_records(recorder.conn)[0]
    assert [i["code"] for i in executor_record["executor_incidents"]] == [
        "rule_violation",
        "correct_stop",
    ]


def test_explain_has_dimension_score():
    from chanchi import taxonomy

    explained = scoring.explain()["dimension_score"]
    assert explained["formula"] == "clamp(100 - penalty, 0, 100)"
    assert explained["correct_stop_excluded"] is True
    assert explained["note"] == scoring.DIMENSION_NOTE
    assert [d["dimension"] for d in explained["dimensions"]] == list(taxonomy.DIMENSIONS)


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
    assert explained["exploration"]["complexities"] == ["low", "medium"]
    assert explained["exploration"]["max"] == 3
    assert explained["exploration"]["min_task_type_sessions"] == 3


# --- exploration -----------------------------------------------------------

GLM_LOW = "opencode:opencode-go/glm-5.3:low"
GLM_MEDIUM = "opencode:opencode-go/glm-5.3:medium"
GLM_HIGH = "opencode:opencode-go/glm-5.3:high"
KIMI = "opencode:opencode-go/kimi-k3"
MINIMAX = "opencode:opencode-go/minimax-m3"


@pytest.fixture
def explore_catalog(recorder):
    conn = recorder.conn
    catalog.add_model(
        conn, agent="opencode", model="opencode-go/glm-5.3", cost_tier=1, efforts=["low", "medium", "high"]
    )
    catalog.add_model(conn, agent="opencode", model="opencode-go/kimi-k3", cost_tier=1)
    catalog.add_model(conn, agent="opencode", model="opencode-go/minimax-m3", cost_tier=2)
    return recorder


def test_explore_complexity_gate(explore_catalog):
    for complexity in ("low", "medium"):
        result = scoring.recommend(
            explore_catalog.conn, task_type="ui-component", complexity=complexity, available=[GLM_LOW]
        )
        assert result["explore"] == [
            {
                "spec": GLM_LOW,
                "cost_tier": 1,
                "n_task_type": 0,
                "deprioritized": None,
                "external_signals": None,
            }
        ]
        assert result["explore_reason"] is None

    high = scoring.recommend(
        explore_catalog.conn, task_type="ui-component", complexity="high", available=[GLM_LOW]
    )
    assert high["explore"] == []
    assert high["explore_reason"] == "complexity_not_explorable"


def test_explore_counts_requested_task_type_only(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(5):
        explore_catalog.session(
            "c1", f"S{idx + 1}", GLM_LOW, task_type="bugfix", verdict="accepted_with_fixes"
        )
    for idx in range(3):
        explore_catalog.session("c1", f"F{idx + 1}", FLASH, task_type="ui-component")

    ui = scoring.recommend(
        explore_catalog.conn,
        task_type="ui-component",
        complexity="medium",
        available=[FLASH, GLM_LOW, KIMI],
    )
    assert ui["recommendation"]["spec"] == FLASH
    assert [e["spec"] for e in ui["explore"]] == [GLM_LOW, KIMI]
    assert ui["explore"][0]["n_task_type"] == 0

    bugfix = scoring.recommend(
        explore_catalog.conn,
        task_type="bugfix",
        complexity="medium",
        available=[FLASH, GLM_LOW, KIMI],
    )
    assert bugfix["recommendation"]["spec"] == FLASH
    assert [e["spec"] for e in bugfix["explore"]] == [KIMI]


def test_explore_excludes_recommendation_model(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session("c1", f"S{idx + 1}", GLM_MEDIUM, task_type="bugfix")

    result = scoring.recommend(
        explore_catalog.conn,
        task_type="ui-component",
        complexity="medium",
        available=[GLM_MEDIUM, GLM_LOW, KIMI],
    )
    assert result["recommendation"]["spec"] == GLM_MEDIUM
    assert [e["spec"] for e in result["explore"]] == [KIMI]


def test_explore_excludes_model_red_flagged_on_three_or_more_sessions(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session(
            "c1", f"S{idx + 1}", GLM_HIGH, task_type="bugfix", incidents=[inc("false_claim")]
        )

    result = scoring.recommend(
        explore_catalog.conn,
        task_type="ui-component",
        complexity="medium",
        available=[GLM_LOW, GLM_HIGH, KIMI],
    )
    assert [e["spec"] for e in result["explore"]] == [KIMI]


def test_explore_low_data_red_flag_deprioritizes_model(explore_catalog):
    explore_catalog.change("c1")
    explore_catalog.session("c1", "S1", GLM_LOW, task_type="ui-component", incidents=[inc("false_claim")])
    explore_catalog.session("c1", "S2", GLM_HIGH, task_type="ui-component")
    explore_catalog.session("c1", "S3", GLM_HIGH, task_type="ui-component")

    for order in ([GLM_LOW, GLM_HIGH, MINIMAX], [GLM_HIGH, GLM_LOW, MINIMAX]):
        result = scoring.recommend(
            explore_catalog.conn, task_type="ui-component", complexity="medium", available=order
        )
        assert [e["spec"] for e in result["explore"]] == [MINIMAX, GLM_HIGH]
        assert result["explore"][1]["deprioritized"] == "red_flag_low_data"

    # Both weak_start and low-data red flag -> red_flag_low_data wins.
    explore_catalog.change("c2")
    for idx in range(3):
        explore_catalog.session("c2", f"A{idx + 1}", KIMI, task_type="docs")
    explore_catalog.session(
        "c2", "B1", MINIMAX, task_type="docs", verdict="rejected", incidents=[inc("false_claim")]
    )
    both = scoring.recommend(
        explore_catalog.conn, task_type="docs", complexity="medium", available=[MINIMAX]
    )
    assert both["explore"][0]["deprioritized"] == "red_flag_low_data"


def test_explore_weak_start_and_boundary(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session("c1", f"S{idx + 1}", KIMI, task_type="ui-component")
    explore_catalog.session("c1", "G1", GLM_LOW, task_type="ui-component", verdict="rejected")

    result = scoring.recommend(
        explore_catalog.conn, task_type="ui-component", complexity="medium", available=[GLM_LOW, MINIMAX]
    )
    assert [e["spec"] for e in result["explore"]] == [MINIMAX, GLM_LOW]
    assert result["explore"][1]["deprioritized"] == "weak_start"

    # Boundary: mean exactly 5 points below prior is not weak_start.
    # 2 sessions at 100 + 1 session at 92.5 (100 - 1.5*5 blocking rule_violation) -> prior 97.5, diff = 5.0.
    explore_catalog.change("c2")
    explore_catalog.session("c2", "K1", KIMI, task_type="refactor")
    explore_catalog.session("c2", "K2", KIMI, task_type="refactor")
    explore_catalog.session(
        "c2", "G1", GLM_LOW, task_type="refactor", incidents=[inc("rule_violation", severity="blocking")]
    )
    boundary = scoring.recommend(
        explore_catalog.conn, task_type="refactor", complexity="medium", available=[GLM_LOW, MINIMAX]
    )
    by_spec = {e["spec"]: e for e in boundary["explore"]}
    assert by_spec[GLM_LOW]["deprioritized"] is None


def test_explore_deprioritized_sort_among_themselves(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session("c1", f"R{idx + 1}", FLASH, task_type="ui-component")
    explore_catalog.session("c1", "M1", MINIMAX, task_type="ui-component", verdict="rejected")
    explore_catalog.session("c1", "K1", KIMI, task_type="ui-component", verdict="rejected")
    explore_catalog.session("c1", "G1", GLM_LOW, task_type="ui-component", verdict="rejected")
    explore_catalog.session("c1", "G2", GLM_LOW, task_type="ui-component", verdict="rejected")

    result = scoring.recommend(
        explore_catalog.conn,
        task_type="ui-component",
        complexity="medium",
        available=[MINIMAX, KIMI, GLM_LOW],
    )
    # All three are weak_start; tier 1 (GLM n=2, KIMI n=1) before tier 2 (MINIMAX n=1).
    assert [e["spec"] for e in result["explore"]] == [GLM_LOW, KIMI, MINIMAX]
    assert all(e["deprioritized"] == "weak_start" for e in result["explore"])


def test_explore_sort_order_cost_then_n_then_spec(explore_catalog):
    explore_catalog.change("c1")
    explore_catalog.session("c1", "S1", GLM_LOW, task_type="bugfix")
    explore_catalog.session("c1", "S2", GLM_LOW, task_type="bugfix")

    result = scoring.recommend(
        explore_catalog.conn,
        task_type="bugfix",
        complexity="medium",
        available=[MINIMAX, KIMI, GLM_LOW],
    )
    assert [e["spec"] for e in result["explore"]] == [GLM_LOW, KIMI, MINIMAX]


def test_explore_keeps_one_spec_per_model(explore_catalog):
    first = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="medium", available=[GLM_LOW, GLM_HIGH]
    )
    assert [e["spec"] for e in first["explore"]] == [GLM_LOW]

    explore_catalog.change("c1")
    explore_catalog.session("c1", "S1", GLM_HIGH, task_type="bugfix")
    second = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="medium", available=[GLM_LOW, GLM_HIGH]
    )
    assert [e["spec"] for e in second["explore"]] == [GLM_HIGH]


def test_explore_split_efforts_and_listed_only(explore_catalog):
    explore_catalog.change("c1")
    explore_catalog.session("c1", "S1", GLM_LOW, task_type="bugfix")
    explore_catalog.session("c1", "S2", GLM_LOW, task_type="bugfix")
    explore_catalog.session("c1", "S3", GLM_HIGH, task_type="bugfix")

    split = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="medium", available=[GLM_LOW, GLM_HIGH]
    )
    assert [e["spec"] for e in split["explore"]] == [GLM_LOW]

    explore_catalog.session("c1", "S4", GLM_LOW, task_type="bugfix")
    # 3 bugfix audits at :low, but only :high is listed -> :high is explorable.
    unlisted = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="medium", available=[GLM_HIGH]
    )
    assert [e["spec"] for e in unlisted["explore"]] == [GLM_HIGH]

    # When :low is listed too, the model is no longer explorable for bugfix.
    listed = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="medium", available=[GLM_LOW, GLM_HIGH]
    )
    assert listed["explore"] == []
    assert listed["explore_reason"] == "no_explorable_candidates"


def test_explore_three_audits_at_high_blocks_model(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session("c1", f"S{idx + 1}", GLM_HIGH, task_type="bugfix")

    result = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="medium", available=[GLM_LOW, GLM_HIGH]
    )
    assert result["explore"] == []
    assert result["explore_reason"] == "no_explorable_candidates"


def test_explore_caps_at_three_and_exact_keys(explore_catalog):
    result = scoring.recommend(
        explore_catalog.conn,
        task_type="ui-component",
        complexity="medium",
        available=[GLM_LOW, KIMI, MINIMAX, FLASH, SONNET],
    )
    assert len(result["explore"]) == 3
    for entry in result["explore"]:
        assert set(entry) == {"spec", "cost_tier", "n_task_type", "deprioritized", "external_signals"}


def test_explore_no_explorable_candidates_reason(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session("c1", f"S{idx + 1}", KIMI, task_type="bugfix")

    result = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="medium", available=[KIMI]
    )
    assert result["explore"] == []
    assert result["explore_reason"] == "no_explorable_candidates"


def test_recommend_high_complexity_leak_pin(explore_catalog):
    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session("c1", f"S{idx + 1}", GLM_LOW, task_type="bugfix", complexity="low")

    result = scoring.recommend(
        explore_catalog.conn, task_type="bugfix", complexity="high", available=[GLM_LOW]
    )
    assert result["recommendation"]["spec"] == GLM_LOW
    assert result["recommendation"]["level"] == "task_type"


def test_show_change_exploration_budget(recorder):
    # 4 sessions with 2 tagged explore -> allowed 1, over_budget True once closed.
    recorder.change("c4")
    pid = recorder.pid
    recorder.session("c4", "S1", FLASH, tags="explore")
    recorder.session("c4", "S2", FLASH, tags="ui,explore")
    recorder.session("c4", "S3", FLASH, tags="exploreish")
    recorder.session("c4", "S4", FLASH)
    open_shown = scoring.show_change(recorder.conn, project_id=pid, ref="c4")
    assert open_shown["exploration"] == {
        "sessions": 4,
        "exploratory": 2,
        "allowed": 1,
        "over_budget": None,
    }
    record.close_change(recorder.conn, project_id=pid, ref="c4")
    closed_4 = scoring.show_change(recorder.conn, project_id=pid, ref="c4")
    assert closed_4["exploration"] == {
        "sessions": 4,
        "exploratory": 2,
        "allowed": 1,
        "over_budget": True,
    }

    # 2 sessions with 1 tagged -> allowed 1, over_budget False; retry without tag still counts once.
    recorder.change("c2")
    recorder.session("c2", "S1", FLASH, tags="explore", verdict="rejected")
    recorder.session("c2", "S1", FLASH, retry_reason="executor_failure")
    recorder.session("c2", "S2", FLASH)
    record.close_change(recorder.conn, project_id=pid, ref="c2")
    closed_2 = scoring.show_change(recorder.conn, project_id=pid, ref="c2")
    assert closed_2["exploration"] == {
        "sessions": 2,
        "exploratory": 1,
        "allowed": 1,
        "over_budget": False,
    }

    # 1 session with 1 tagged -> allowed 0, over_budget True.
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, tags="explore")
    record.close_change(recorder.conn, project_id=pid, ref="c1")
    closed_1 = scoring.show_change(recorder.conn, project_id=pid, ref="c1")
    assert closed_1["exploration"] == {
        "sessions": 1,
        "exploratory": 1,
        "allowed": 0,
        "over_budget": True,
    }


def test_recommend_require_filters_and_preserves_scores(explore_catalog):
    conn = explore_catalog.conn
    catalog.set_model(conn, spec="claude:sonnet", capabilities={"vision": "yes"})
    catalog.set_model(conn, spec="opencode:opencode-go/glm-5.3", capabilities={"vision": "yes"})
    catalog.set_model(conn, spec="opencode:opencode-go/kimi-k3", capabilities={"vision": "no"})
    # opencode:opencode-go/minimax-m3 stays unknown

    explore_catalog.change("c1")
    for idx in range(3):
        explore_catalog.session("c1", f"S{idx + 1}", SONNET, task_type="ui-component", verdict="accepted")
    for idx in range(3):
        explore_catalog.session("c1", f"K{idx + 1}", KIMI, task_type="ui-component", verdict="rejected")

    unfiltered = scoring.recommend(
        conn,
        task_type="ui-component",
        complexity="medium",
        available=[SONNET, GLM_LOW, KIMI, MINIMAX],
    )
    assert unfiltered["excluded"] == []

    filtered = scoring.recommend(
        conn,
        task_type="ui-component",
        complexity="medium",
        available=[SONNET, GLM_LOW, KIMI, MINIMAX, KIMI],
        require=["", " vision ", "vision", "  "],
    )
    assert [c["spec"] for c in filtered["candidates"]] == [SONNET, GLM_LOW]
    assert filtered["recommendation"]["spec"] == SONNET
    assert [e["spec"] for e in filtered["explore"]] == [GLM_LOW]
    assert filtered["excluded"] == [
        {"spec": KIMI, "missing": [{"capability": "vision", "value": "no"}]},
        {"spec": MINIMAX, "missing": [{"capability": "vision", "value": "unknown"}]},
    ]
    # Scores of remaining candidates equal the scores without --require (prior still uses all records).
    unfiltered_by_spec = {c["spec"]: c for c in unfiltered["candidates"]}
    for cand in filtered["candidates"]:
        assert cand == unfiltered_by_spec[cand["spec"]]


def test_recommend_require_all_excluded(explore_catalog):
    conn = explore_catalog.conn
    catalog.set_model(conn, spec="opencode:opencode-go/kimi-k3", capabilities={"vision": "no"})

    medium = scoring.recommend(
        conn,
        task_type="ui-component",
        complexity="medium",
        available=[KIMI, MINIMAX],
        require=["vision"],
    )
    assert medium["recommendation"] is None
    assert medium["reason"] == "no_capable_candidates"
    assert medium["candidates"] == []
    assert medium["explore"] == []
    assert medium["explore_reason"] == "no_explorable_candidates"
    assert medium["excluded"] == [
        {"spec": KIMI, "missing": [{"capability": "vision", "value": "no"}]},
        {"spec": MINIMAX, "missing": [{"capability": "vision", "value": "unknown"}]},
    ]

    high = scoring.recommend(
        conn,
        task_type="ui-component",
        complexity="high",
        available=[KIMI, MINIMAX],
        require=["vision"],
    )
    assert high["recommendation"] is None
    assert high["reason"] == "no_capable_candidates"
    assert high["candidates"] == []
    assert high["explore"] == []
    assert high["explore_reason"] == "complexity_not_explorable"
    assert high["excluded"] == medium["excluded"]


def test_recommend_require_validation_error(explore_catalog):
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(
            explore_catalog.conn,
            task_type="ui-component",
            complexity="medium",
            available=[KIMI],
            require=["vision", "audio"],
        )
    assert info.value.code == "invalid_value"
    assert info.value.field == "require"
    assert info.value.valid_values == ["vision"]

    explain_data = scoring.explain()
    assert explain_data["require"]["capabilities"] == ["vision"]
    assert explain_data["require"]["values"] == ["yes", "no", "unknown"]
