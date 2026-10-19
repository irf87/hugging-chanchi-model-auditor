import pytest

from chanchi import projects, record
from chanchi.errors import ChanchiError

REF = "add-login"


@pytest.fixture
def opened(seeded, git_repo):
    slug, path = projects.identify()
    change = record.open_change(
        seeded, project_slug=slug, project_path=path, ref=REF, kind="openspec", planner="claude:opus:xhigh"
    )
    pid = projects.resolve_project(seeded)["id"]
    return seeded, pid, change


def _start(conn, pid, session_ref="S1", **overrides):
    args = dict(
        project_id=pid,
        ref=REF,
        session_ref=session_ref,
        executor="agy:gemini-3.8-flash-high:high",
        task_type="ui-component",
        complexity="medium",
        tasks_total=5,
    )
    args.update(overrides)
    return record.start_session(conn, **args)


def _incident(conn, pid, **overrides):
    args = dict(
        project_id=pid,
        ref=REF,
        code="plan_gap",
        severity="blocking",
        detected_by="executor_stop",
        description="design does not say which list to sort",
        evidence="tasks.md 7.3",
    )
    args.update(overrides)
    return record.add_incident(conn, **args)


def test_open_change_defaults_orchestrator_to_planner(opened):
    _, _, change = opened
    assert change["project"] == "demo-app"
    assert change["planner"] == "claude:opus:xhigh"
    assert change["orchestrator"] == "claude:opus:xhigh"
    assert change["closed_at"] is None


def test_open_change_duplicate(opened):
    conn, _, _ = opened
    slug, path = projects.identify()
    with pytest.raises(ChanchiError) as info:
        record.open_change(conn, project_slug=slug, project_path=path, ref=REF, kind="openspec", planner="human")
    assert info.value.code == "duplicate"


def test_failed_open_change_leaves_no_project(seeded, git_repo):
    slug, path = projects.identify()
    with pytest.raises(ChanchiError) as info:
        record.open_change(seeded, project_slug=slug, project_path=path, ref="x", kind="openspec", planner="claude:nope")
    assert info.value.code == "unknown_model"
    assert seeded.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
    with pytest.raises(ChanchiError) as info:
        record.open_change(seeded, project_slug=slug, project_path=path, ref="x", kind="big", planner="human")
    assert info.value.field == "kind"


def test_unknown_change(opened):
    conn, pid, _ = opened
    with pytest.raises(ChanchiError) as info:
        record.get_change(conn, pid, "nope")
    assert info.value.code == "unknown_change"
    assert info.value.valid_values == [REF]


def test_session_attempts(opened):
    conn, pid, _ = opened
    first = _start(conn, pid, tags=" react-native , watermelondb ", groups="8,9")
    assert first["attempt"] == 1
    assert first["executor"] == "agy:gemini-3.8-flash-high:high"
    assert first["tags"] == ["react-native", "watermelondb"]
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid)
    assert info.value.field == "retry_reason"
    assert info.value.valid_values == ["executor_failure", "plan_fix", "human_change", "env"]
    second = _start(conn, pid, retry_reason="plan_fix")
    assert second["attempt"] == 2 and second["retry_reason"] == "plan_fix"


def test_retry_reason_on_first_attempt_is_invalid(opened):
    conn, pid, _ = opened
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid, retry_reason="env")
    assert info.value.field == "retry_reason"


def test_start_session_validations(opened):
    conn, pid, _ = opened
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid, executor="human")
    assert info.value.field == "executor"
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid, executor="agy:gemini-3.8-flash-high:max")
    assert info.value.valid_values == ["low", "medium", "high", "unknown"]
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid, complexity="huge")
    assert info.value.field == "complexity"
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid, task_type="cooking")
    assert info.value.field == "task_type"
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid, tasks_total=0)
    assert info.value.field == "tasks"
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid, session_ref=" ")
    assert info.value.field == "session"


def test_report_audit_flow(opened):
    conn, pid, _ = opened
    _start(conn, pid)
    with pytest.raises(ChanchiError) as info:
        record.audit_session(conn, project_id=pid, ref=REF, session_ref="S1", verdict="accepted")
    assert info.value.code == "missing_prerequisite"
    reported = record.report_session(conn, project_id=pid, ref=REF, session_ref="S1", status="STOPPED")
    assert reported["reported_status"] == "STOPPED" and reported["ended_at"]
    reported = record.report_session(conn, project_id=pid, ref=REF, session_ref="S1", status="COMPLETE")
    assert reported["reported_status"] == "COMPLETE"
    with pytest.raises(ChanchiError) as info:
        record.report_session(conn, project_id=pid, ref=REF, session_ref="S1", status="DONE")
    assert info.value.field == "status"
    audited = record.audit_session(
        conn, project_id=pid, ref=REF, session_ref="S1", verdict="accepted_with_fixes", notes="fixed import"
    )
    assert audited["verdict"] == "accepted_with_fixes" and audited["audited_at"]
    with pytest.raises(ChanchiError) as info:
        record.audit_session(conn, project_id=pid, ref=REF, session_ref="S1", verdict="great")
    assert info.value.field == "verdict"


def test_unknown_session_lists_known(opened):
    conn, pid, _ = opened
    _start(conn, pid)
    with pytest.raises(ChanchiError) as info:
        record.report_session(conn, project_id=pid, ref=REF, session_ref="S9", status="COMPLETE")
    assert info.value.code == "unknown_session"
    assert info.value.valid_values == ["S1#1"]


def test_attempt_targeting(opened):
    conn, pid, _ = opened
    _start(conn, pid)
    _start(conn, pid, retry_reason="executor_failure")
    record.report_session(conn, project_id=pid, ref=REF, session_ref="S1", status="BLOCKED", attempt=1)
    first = record.get_session(conn, record.get_change(conn, pid, REF)["id"], "S1", 1)
    latest = record.get_session(conn, record.get_change(conn, pid, REF)["id"], "S1")
    assert first["reported_status"] == "BLOCKED"
    assert latest["attempt"] == 2 and latest["reported_status"] is None


def test_update_session(opened):
    conn, pid, _ = opened
    _start(conn, pid)
    updated = record.update_session(
        conn, project_id=pid, ref=REF, session_ref="S1", complexity="high", tasks_total=7, tags="a,b"
    )
    assert updated["complexity"] == "high" and updated["tasks_total"] == 7 and updated["tags"] == ["a", "b"]
    with pytest.raises(ChanchiError) as info:
        record.update_session(conn, project_id=pid, ref=REF, session_ref="S1")
    assert info.value.code == "invalid_value"


def test_close_change_blocks_new_sessions(opened):
    conn, pid, _ = opened
    closed = record.close_change(conn, project_id=pid, ref=REF)
    assert closed["closed_at"]
    with pytest.raises(ChanchiError) as info:
        record.close_change(conn, project_id=pid, ref=REF)
    assert info.value.field == "ref"
    with pytest.raises(ChanchiError) as info:
        _start(conn, pid)
    assert info.value.field == "ref"


def test_add_incident_roles(opened):
    conn, pid, _ = opened
    _start(conn, pid)
    gap = _incident(conn, pid, task_ref="7.3")
    assert gap["role"] == "planner" and gap["session"] is None and gap["task_ref"] == "7.3"
    stop = _incident(conn, pid, code="correct_stop", severity="low", session_ref="S1")
    assert stop["role"] == "executor" and stop["session"] == "S1" and stop["attempt"] == 1
    hallucination = _incident(conn, pid, code="hallucination", severity="high", role="planner")
    assert hallucination["role"] == "planner"


def test_add_incident_validations(opened):
    conn, pid, _ = opened
    _start(conn, pid)
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, code="false_claim")
    assert info.value.field == "session"
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, code="hallucination")
    assert info.value.field == "role"
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, role="executor")
    assert info.value.field == "role"
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, evidence="  ")
    assert info.value.field == "evidence"
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, description="")
    assert info.value.field == "desc"
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, severity="huge")
    assert info.value.field == "severity"
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, detected_by="magic")
    assert info.value.field == "detected_by"
    with pytest.raises(ChanchiError) as info:
        _incident(conn, pid, attempt=1)
    assert info.value.field == "attempt"


def test_incidents_allowed_on_closed_change(opened):
    conn, pid, _ = opened
    _start(conn, pid)
    record.close_change(conn, project_id=pid, ref=REF)
    late = _incident(conn, pid, code="quality_defect", severity="high", detected_by="post_merge", session_ref="S1")
    assert late["detected_by"] == "post_merge"


def test_void_incident(opened):
    conn, pid, _ = opened
    gap = _incident(conn, pid)
    voided = record.void_incident(conn, incident_id=gap["id"], reason="was a human change")
    assert voided["voided_at"] and voided["void_reason"] == "was a human change"
    with pytest.raises(ChanchiError) as info:
        record.void_incident(conn, incident_id=gap["id"], reason="again")
    assert info.value.field == "id"
    with pytest.raises(ChanchiError) as info:
        record.void_incident(conn, incident_id=999, reason="x")
    assert info.value.field == "id"
    other = _incident(conn, pid)
    with pytest.raises(ChanchiError) as info:
        record.void_incident(conn, incident_id=other["id"], reason=" ")
    assert info.value.field == "reason"
