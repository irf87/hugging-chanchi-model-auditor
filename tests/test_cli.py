import json

import pytest

from chanchi import cli


def run(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def ok(capsys, *argv):
    code, out, err = run(capsys, *argv)
    assert code == 0, err
    payload = json.loads(out)
    assert payload["ok"] is True
    return payload


def fail(capsys, *argv, exit_code=2):
    code, out, err = run(capsys, *argv)
    assert code == exit_code
    assert out == ""
    payload = json.loads(err)
    assert payload["ok"] is False
    return payload["error"]


@pytest.fixture
def ready(db_env, git_repo, capsys):
    ok(capsys, "models", "add", "--agent", "claude", "--model", "opus", "--cost", "3", "--efforts", "high,xhigh")
    ok(capsys, "models", "add", "--agent", "agy", "--model", "gemini-3.8-flash-high", "--cost", "1", "--efforts", "low,medium,high")
    return capsys


def test_help_exits_zero(capsys):
    code, out, _ = run(capsys, "--help")
    assert code == 0 and "chanchi" in out


def test_version(capsys):
    code, out, _ = run(capsys, "--version")
    assert code == 0 and "0.1.0" in out


def test_parse_errors_are_json(capsys, db_env):
    error = fail(capsys, "session")
    assert error["code"] == "invalid_value"
    error = fail(capsys, "models", "add", "--agent", "claude")
    assert "--model" in error["message"]


def test_db_status_and_migrate(capsys, db_env):
    status = ok(capsys, "db", "status")
    assert status["operational"]["exists"] is False
    migrated = ok(capsys, "db", "migrate")
    assert migrated["created"] is True
    assert ok(capsys, "db", "status")["operational"]["pending"] == 0


def test_models_and_taxonomy(ready):
    capsys = ready
    models = ok(capsys, "models", "list")["models"]
    assert {m["spec"] for m in models} == {"agy:gemini-3.8-flash-high", "claude:opus", "human:human"}
    updated = ok(capsys, "models", "set", "claude:opus", "--active", "0")["model"]
    assert updated["active"] is False
    assert len(ok(capsys, "models", "list", "--all")["models"]) == 3
    taxonomy = ok(capsys, "taxonomy", "list")
    assert "hallucination" in [c["code"] for c in taxonomy["taxonomy"]["incident_codes"]]
    assert taxonomy["task_types"][0]["code"] == "ui-component"
    added = ok(capsys, "taxonomy", "add-type", "mobile-native", "--description", "Native code")
    assert added["task_type"]["code"] == "mobile-native"


def test_validation_error_envelope(ready):
    error = fail(ready, "models", "add", "--agent", "claude", "--model", "x", "--cost", "9")
    assert error["field"] == "cost" and error["valid_values"] == [1, 2, 3]
    error = fail(ready, "models", "add", "--agent", "claude", "--model", "x", "--cost", "two")
    assert error["code"] == "invalid_value"


def test_full_flow(ready):
    capsys = ready
    change = ok(capsys, "change", "open", "add-login", "--kind", "openspec", "--planner", "claude:opus:xhigh")["change"]
    assert change["orchestrator"] == "claude:opus:xhigh"
    session = ok(
        capsys, "session", "start", "add-login", "S1", "--executor", "agy:gemini-3.8-flash-high:high",
        "--task-type", "ui-component", "--complexity", "medium", "--tasks", "6", "--groups", "1,2", "--tags", "react",
    )["session"]
    assert session["attempt"] == 1 and session["tags"] == ["react"]
    ok(capsys, "session", "report", "add-login", "S1", "--status", "STOPPED")
    gap = ok(
        capsys, "incident", "add", "add-login", "--code", "plan_gap", "--severity", "blocking",
        "--detected-by", "executor_stop", "--desc", "no sort order", "--evidence", "tasks.md 2.3", "--task", "2.3",
    )["incident"]
    assert gap["role"] == "planner" and gap["task_ref"] == "2.3"
    ok(
        capsys, "incident", "add", "add-login", "--session", "S1", "--code", "correct_stop", "--severity", "low",
        "--detected-by", "executor_stop", "--desc", "stopped at 2.3", "--evidence", "report S1",
    )
    ok(capsys, "session", "report", "add-login", "S1", "--status", "COMPLETE")
    ok(capsys, "session", "update", "add-login", "S1", "--complexity", "high")
    audited = ok(capsys, "session", "audit", "add-login", "S1", "--verdict", "accepted")["session"]
    assert audited["verdict"] == "accepted"
    voided = ok(capsys, "incident", "void", str(gap["id"]), "--reason", "it was a human change")["incident"]
    assert voided["voided_at"]
    shown = ok(capsys, "show", "add-login")
    assert shown["sessions"][0]["score"] == 100
    closed = ok(capsys, "change", "close", "add-login")["change"]
    assert closed["closed_at"]
    stats = ok(capsys, "stats")
    assert stats["rows"][0]["spec"] == "agy:gemini-3.8-flash-high:high"
    assert ok(capsys, "stats", "--role", "planner", "--by", "project")["rows"][0]["project"] == "demo-app"
    assert ok(capsys, "stats", "--role", "human", "--project", "demo-app")["rows"][0]["stops_total"] == 0
    assert ok(capsys, "stats", "--since", "2026-01-01")["rows"]
    rec = ok(
        capsys, "recommend", "--task-type", "ui-component", "--complexity", "high",
        "--available", "agy:gemini-3.8-flash-high:high, claude:opus:high",
    )
    assert rec["reason"] == "insufficient_data"
    assert [c["spec"] for c in rec["candidates"]] == ["agy:gemini-3.8-flash-high:high", "claude:opus:high"]


def test_inactive_candidate_is_an_error(ready):
    ok(ready, "models", "set", "claude:opus", "--active", "0")
    error = fail(
        ready, "recommend", "--task-type", "ui-component", "--complexity", "high", "--available", "claude:opus:high"
    )
    assert "--active 1" in error["hint"]


def test_unknown_change_and_project(ready):
    error = fail(ready, "show", "nope")
    assert error["field"] == "project"  # project has no changes yet
    ok(ready, "change", "open", "c1", "--kind", "adhoc", "--planner", "human")
    error = fail(ready, "show", "nope")
    assert error["code"] == "unknown_change" and error["valid_values"] == ["c1"]


def test_text_format(ready):
    code, out, _ = run(ready, "models", "list", "--format", "text")
    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("models:")
    assert "spec" in lines[1] and "cost_tier" in lines[1]
    code, _, err = run(ready, "models", "add", "--agent", "claude", "--model", "x", "--cost", "9", "--format", "text")
    assert code == 2
    assert err.startswith("error:")


def test_scoring_explain(capsys, db_env):
    explained = ok(capsys, "scoring", "explain")
    assert explained["smoothing"]["k"] == 3


def test_skills_link_command(capsys, tmp_path, db_env):
    target = tmp_path / "proj"
    target.mkdir()
    result = ok(capsys, "skills", "link", str(target))
    assert result["base"] == str(target.resolve())
    assert ok(capsys, "skills", "unlink", str(target))["base"] == str(target.resolve())


def test_internal_errors_are_wrapped(capsys, db_env, monkeypatch):
    from chanchi import scoring

    def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(scoring, "explain", boom)
    error = fail(capsys, "scoring", "explain", exit_code=1)
    assert error["code"] == "internal" and "kaboom" in error["message"]


def test_database_busy_maps_to_code_and_exit_two(capsys, db_env, monkeypatch):
    import sqlite3
    from chanchi import scoring

    def locked(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(scoring, "explain", locked)
    error = fail(capsys, "scoring", "explain", exit_code=2)
    assert error["code"] == "database_busy"
    assert error["message"] == "the database is busy; another chanchi process is writing"
    assert error["hint"] == "retry the same command in a few seconds"


def test_abbreviated_options_are_rejected(ready):
    error = fail(ready, "models", "list", "--form", "text")
    assert error["code"] == "invalid_value"
