import pytest
from helpers import inc

from chanchi import catalog, record, scoring

ARGON = "agy:gemini-4-argon-high:high"
FLASH = "agy:gemini-3.8-flash-high:high"
FLASH_MEDIUM = "agy:gemini-3.8-flash-medium:medium"
SONNET = "claude:sonnet:medium"
CHANGE = "clinical-summary-doctor-addressee-and-polish"

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
