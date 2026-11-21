import pytest
from helpers import inc

from chanchi import catalog, record, scoring

ARGON = "agy:gemini-4-argon-high:high"
FLASH = "agy:gemini-3.8-flash-high:high"
FLASH_MEDIUM = "agy:gemini-3.8-flash-medium:medium"
SONNET = "claude:sonnet:medium"
CHANGE = "reference-change-replay"

# session, executor, task type, complexity, tasks
SESSIONS = [
    ("S1", ARGON, "business-logic", "high", 14),
    ("S2", ARGON, "ui-layout-styling", "medium", 9),
    ("S3", FLASH, "ui-component", "medium", 10),
    ("S4", FLASH, "ui-component", "medium", 12),
    ("S5", FLASH, "tests", "low", 3),
    ("S6", FLASH, "ui-component", "medium", 11),
    ("S7", FLASH, "tests", "low", 2),
    ("S8", FLASH, "ui-component", "medium", 8),
    ("S9", FLASH, "tests", "low", 2),
    ("S10", FLASH_MEDIUM, "docs", "low", 3),
]


@pytest.fixture
def history(recorder):
    conn = recorder.conn
    catalog.add_model(conn, agent="agy", model="gemini-4-argon-high", cost_tier=2, efforts=["high"])
    catalog.add_model(conn, agent="agy", model="gemini-3.8-flash-medium", cost_tier=1, efforts=["medium"])
    recorder.change(CHANGE)
    for session_ref, executor, task_type, complexity, tasks in SESSIONS:
        incidents = []
        if session_ref == "S2":
            incidents = [inc("correct_stop", detected_by="executor_stop")]
        if session_ref == "S4":
            incidents = [inc("rule_violation")]
        recorder.session(CHANGE, session_ref, executor, task_type=task_type, complexity=complexity,
                         tasks=tasks, incidents=incidents)
    record.add_incident(
        conn, project_id=recorder.pid, ref=CHANGE,
        **inc("plan_wrong_expectation", "low", "executor_stop"),
    )
    recorder.change("synthetic-sonnet-baseline")
    for session_ref in ("S1", "S2", "S3"):
        recorder.session("synthetic-sonnet-baseline", session_ref, SONNET)
    return recorder


def test_planner_score_of_the_replayed_change(history):
    shown = scoring.show_change(history.conn, project_id=history.pid, ref=CHANGE)
    assert len(shown["sessions"]) == 10
    assert shown["planner_score"] == pytest.approx(99.32, abs=0.01)


def test_recommend_prefers_cheap_flash_for_ui_components(history):
    result = scoring.recommend(
        history.conn, task_type="ui-component", complexity="medium", available=[SONNET, FLASH, ARGON]
    )
    by_spec = {c["spec"]: c for c in result["candidates"]}
    assert by_spec[FLASH]["n"] == 4
    assert by_spec[FLASH]["smoothed_score"] == pytest.approx(99.69, abs=0.01)
    assert by_spec[SONNET]["smoothed_score"] == pytest.approx(99.89, abs=0.01)
    assert by_spec[ARGON]["level"] == "complexity"
    assert by_spec[ARGON]["confidence"] == "insufficient"
    assert result["recommendation"]["spec"] == FLASH


def test_planner_stats_cover_both_changes(history):
    rows = scoring.stats(history.conn, role="planner")["rows"]
    assert rows[0]["spec"] == "claude:opus:xhigh"
    assert rows[0]["n"] == 2
    assert rows[0]["mean_score"] == pytest.approx(99.66, abs=0.01)
    assert rows[0]["confidence"] == "insufficient"


def test_recommend_golden_g2_unchanged(history):
    ui = scoring.recommend(
        history.conn, task_type="ui-component", complexity="medium", available=[SONNET, FLASH, ARGON]
    )
    assert ui["recommendation"] == {
        "confidence": "low",
        "cost_tier": 1,
        "level": "task_type+complexity",
        "smoothed_score": 99.69,
        "spec": "agy:gemini-3.8-flash-high:high",
    }
    assert ui["reason"] is None
    assert ui["window"] == 5.0
    assert ui["candidates"] == [
        {
            "agent": "claude",
            "clean_rate": 1.0,
            "confidence": "low",
            "cost_tier": 2,
            "effort": "medium",
            "first_attempt_acceptance": 1.0,
            "honesty_flags_per_session": 0.0,
            "level": "task_type+complexity",
            "mean_duration_s": 3600.0,
            "mean_score": 100.0,
            "model": "sonnet",
            "n": 3,
            "prior": 99.79,
            "red_flag": False,
            "retry_rate": 0.0,
            "smoothed_score": 99.89,
            "spec": "claude:sonnet:medium",
            "top_codes": [],
        },
        {
            "agent": "agy",
            "clean_rate": 1.0,
            "confidence": "insufficient",
            "cost_tier": 2,
            "effort": "high",
            "first_attempt_acceptance": 1.0,
            "honesty_flags_per_session": 0.0,
            "level": "complexity",
            "mean_duration_s": 3600.0,
            "mean_score": 100.0,
            "model": "gemini-4-argon-high",
            "n": 1,
            "prior": 99.81,
            "red_flag": False,
            "retry_rate": 0.0,
            "smoothed_score": 99.86,
            "spec": "agy:gemini-4-argon-high:high",
            "top_codes": ["correct_stop"],
        },
        {
            "agent": "agy",
            "clean_rate": 1.0,
            "confidence": "low",
            "cost_tier": 1,
            "effort": "high",
            "first_attempt_acceptance": 1.0,
            "honesty_flags_per_session": 0.0,
            "level": "task_type+complexity",
            "mean_duration_s": 3600.0,
            "mean_score": 99.62,
            "model": "gemini-3.8-flash-high",
            "n": 4,
            "prior": 99.79,
            "red_flag": False,
            "retry_rate": 0.0,
            "smoothed_score": 99.69,
            "spec": "agy:gemini-3.8-flash-high:high",
            "top_codes": ["rule_violation"],
        },
    ]

    tests_rec = scoring.recommend(
        history.conn, task_type="tests", complexity="low", available=[SONNET, FLASH, ARGON]
    )
    assert tests_rec["recommendation"] == {
        "confidence": "low",
        "cost_tier": 1,
        "level": "task_type+complexity",
        "smoothed_score": 100.0,
        "spec": "agy:gemini-3.8-flash-high:high",
    }
    assert tests_rec["reason"] is None
    assert tests_rec["window"] == 5.0
    assert tests_rec["candidates"] == [
        {
            "agent": "agy",
            "clean_rate": 1.0,
            "confidence": "low",
            "cost_tier": 1,
            "effort": "high",
            "first_attempt_acceptance": 1.0,
            "honesty_flags_per_session": 0.0,
            "level": "task_type+complexity",
            "mean_duration_s": 3600.0,
            "mean_score": 100.0,
            "model": "gemini-3.8-flash-high",
            "n": 3,
            "prior": 100.0,
            "red_flag": False,
            "retry_rate": 0.0,
            "smoothed_score": 100.0,
            "spec": "agy:gemini-3.8-flash-high:high",
            "top_codes": [],
        },
        {
            "agent": "claude",
            "clean_rate": 1.0,
            "confidence": "low",
            "cost_tier": 2,
            "effort": "medium",
            "first_attempt_acceptance": 1.0,
            "honesty_flags_per_session": 0.0,
            "level": "global",
            "mean_duration_s": 3600.0,
            "mean_score": 100.0,
            "model": "sonnet",
            "n": 3,
            "prior": 99.88,
            "red_flag": False,
            "retry_rate": 0.0,
            "smoothed_score": 99.94,
            "spec": "claude:sonnet:medium",
            "top_codes": [],
        },
        {
            "agent": "agy",
            "clean_rate": 1.0,
            "confidence": "insufficient",
            "cost_tier": 2,
            "effort": "high",
            "first_attempt_acceptance": 1.0,
            "honesty_flags_per_session": 0.0,
            "level": "global",
            "mean_duration_s": 3600.0,
            "mean_score": 100.0,
            "model": "gemini-4-argon-high",
            "n": 2,
            "prior": 99.88,
            "red_flag": False,
            "retry_rate": 0.0,
            "smoothed_score": 99.93,
            "spec": "agy:gemini-4-argon-high:high",
            "top_codes": ["correct_stop"],
        },
    ]
