import json
import os
import subprocess
import sqlite3
import sys

import pytest


def chanchi(cwd, env, *args, stdin=None):
    result = subprocess.run(
        [sys.executable, "-m", "chanchi", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False,
        input=None if stdin is None else (stdin if isinstance(stdin, str) else json.dumps(stdin)),
    )
    return result.returncode, result.stdout, result.stderr


def test_end_to_end_through_a_subprocess(tmp_path):
    repo = tmp_path / "demo-app"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    env = {**os.environ, "CHANCHI_DB": str(tmp_path / "data" / "chanchi.db")}

    steps = [
        ("models", "add", "--agent", "claude", "--model", "opus", "--cost", "3"),
        ("models", "add", "--agent", "claude", "--model", "haiku", "--cost", "1"),
        ("change", "open", "c1", "--kind", "openspec", "--planner", "claude:opus:high"),
        ("session", "start", "c1", "S1", "--executor", "claude:haiku:low", "--task-type", "docs",
         "--complexity", "low", "--tasks", "2"),
        ("session", "report", "c1", "S1", "--status", "COMPLETE"),
        ("session", "audit", "c1", "S1", "--verdict", "accepted"),
        ("change", "close", "c1"),
    ]
    for step in steps:
        code, out, err = chanchi(repo, env, *step)
        assert code == 0, (step, err)
        assert json.loads(out)["ok"] is True

    code, out, _ = chanchi(repo, env, "show", "c1")
    assert code == 0
    assert json.loads(out)["sessions"][0]["score"] == 100

    code, out, _ = chanchi(repo, env, "show", "c1", "--format", "text")
    assert code == 0
    assert "exploration:" in out
    assert "over_budget:" in out

    code, out, _ = chanchi(
        repo,
        env,
        "recommend",
        "--task-type",
        "ui-component",
        "--complexity",
        "medium",
        "--available",
        "claude:haiku:low,claude:opus:high",
    )
    assert code == 0
    rec_json = json.loads(out)
    assert [e["spec"] for e in rec_json["explore"]] == ["claude:haiku:low", "claude:opus:high"]
    assert rec_json["explore_reason"] is None

    code, out, _ = chanchi(
        repo,
        env,
        "recommend",
        "--task-type",
        "ui-component",
        "--complexity",
        "medium",
        "--available",
        "claude:haiku:low,claude:opus:high",
        "--format",
        "text",
    )
    assert code == 0
    assert "explore:" in out
    assert "explore_reason:" in out

    code, out, err = chanchi(repo, env, "session", "start", "c1", "S2", "--executor", "claude:haiku",
                             "--task-type", "docs", "--complexity", "tiny", "--tasks", "1")
    assert code == 2 and out == ""
    assert json.loads(err)["error"]["code"] == "invalid_value"

    outside = tmp_path / "outside"
    outside.mkdir()
    code, _, err = chanchi(outside, env, "show", "c1")
    assert code == 2
    assert json.loads(err)["error"]["code"] == "project_not_detected"
    code, out, _ = chanchi(outside, env, "show", "c1", "--project", "demo-app")
    assert code == 0 and json.loads(out)["change"]["ref"] == "c1"


# --- continuous improvement: CUJs 1, 2, 3, 4 and 7 ------------------------------

WORDS = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")


def lesson_body(tag, **over):
    text = " ".join(f"{tag}{word}" for word in WORDS)
    data = {
        "what_happened": text, "evidence": f"evidence of {tag}", "cause": f"cause of {tag}",
        "prevention": f"prevention of {tag}", "proposal": text, "general_rule": text,
        "target": "role executor", "target_kind": "role", "generality": "agnostic", "severity": "high",
    }
    data.update(over)
    return data


def identity(role="planner", conversation="conv-plan", author="claude:opus:high"):
    return ("--as", role, "--author", author, "--conversation", conversation)


@pytest.fixture
def cli_env(db_env):
    return {**os.environ, "CHANCHI_DB": str(db_env)}


def run_ok(cwd, env, *args, stdin=None):
    code, out, err = chanchi(cwd, env, *args, stdin=stdin)
    assert code == 0, (args, err)
    return json.loads(out)


def run_fail(cwd, env, *args, stdin=None):
    code, out, err = chanchi(cwd, env, *args, stdin=stdin)
    assert code == 2 and out == "", (args, code, out)
    payload = json.loads(err)
    assert payload["ok"] is False
    return payload["error"]


def test_cuj1_planner_records_a_lesson_after_an_audit(registered_repo, cli_env):
    repo, env = registered_repo, cli_env
    run_ok(repo, env, "models", "add", "--agent", "claude", "--model", "opus", "--cost", "3", "--efforts", "high")
    run_ok(repo, env, "models", "add", "--agent", "claude", "--model", "haiku", "--cost", "1")
    run_ok(repo, env, "change", "open", "add-export", "--kind", "openspec", "--planner", "claude:opus:high")
    run_ok(
        repo, env, "session", "start", "add-export", "S3", "--executor", "claude:haiku", "--task-type", "docs",
        "--complexity", "low", "--tasks", "2",
    )
    incident = run_ok(
        repo, env, "incident", "add", "add-export", "--session", "S3", "--code", "false_claim",
        "--severity", "high", "--detected-by", "planner_audit", "--desc", "tests never ran in the package",
        "--evidence", "pytest output named no package",
    )["incident"]

    similar = run_ok(repo, env, "lesson", "similar", "test output evidence package skipped")
    assert similar["matches"] == []

    body = lesson_body(
        "evidence", general_rule="test output counts as evidence only if it names what ran and what was skipped",
        target="role executor", change="add-export", session="S3", incidents=[incident["id"]],
    )
    added = run_ok(repo, env, "lesson", "add", *identity(), "--json", "-", stdin=body)
    lesson = added["lesson"]
    assert added["warnings"] == []
    assert lesson["status"] == "pending" and lesson["origin"] == "demo-app"
    assert lesson["author_model_raw"] == "opus" and lesson["author_model_id"] is not None
    assert lesson["author_effort"] == "high" and lesson["git_head"]
    assert lesson["change_id"] is not None and lesson["session_id"] is not None

    shown = run_ok(repo, env, "lesson", "show", str(lesson["id"]))
    assert [e["action"] for e in shown["events"]] == ["created"]
    assert [i["id"] for i in shown["incidents"]] == [incident["id"]]


def test_cuj2_maintenance_conversation_reviews_and_applies(registered_repo, cli_env):
    repo, env = registered_repo, cli_env
    lesson = run_ok(repo, env, "lesson", "add", *identity(), "--json", "-", stdin=lesson_body("zork"))["lesson"]
    lid = str(lesson["id"])

    exported = run_ok(repo, env, "lesson", "export", "--generality", "agnostic")
    assert exported["scope"] == "demo-app" and [x["id"] for x in exported["lessons"]] == [lesson["id"]]
    code, out, _ = chanchi(repo, env, "lesson", "export", "--generality", "agnostic", "--format", "md")
    assert code == 0 and out.startswith(f"## #{lid} ")

    error = run_fail(repo, env, "lesson", "review", lid, *identity(), "--decision", "approve", "--reason", "ok")
    assert error["code"] == "self_review" and error["field"] == "conversation"

    other = identity(conversation="conv-maint")
    reviewed = run_ok(repo, env, "lesson", "review", lid, *other, "--decision", "approve", "--reason", "clear rule")
    assert reviewed["lesson"]["status"] == "approved"
    where = f".agents/roles/executor.md [lesson #{lid}] @ abc123"
    applied = run_ok(repo, env, "lesson", "apply", lid, *other, "--site", "project", "--where", where)
    assert applied["site"]["state"] == "applied" and applied["site"]["project"] == "demo-app"

    shown = run_ok(repo, env, "lesson", "show", lid)
    assert [e["action"] for e in shown["events"]] == ["created", "reviewed", "applied"]
    assert [s["state"] for s in shown["sites"]] == ["applied"]
    assert run_ok(repo, env, "lesson", "summary")["applied_sites"] == {"demo-app": 1}


def test_cuj3_an_executor_cannot_record_a_lesson(registered_repo, cli_env):
    repo, env = registered_repo, cli_env
    error = run_fail(
        repo, env, "lesson", "add", *identity(role="executor", author="claude:haiku"), "--json", "-",
        stdin=lesson_body("zork"),
    )
    assert error["code"] == "not_a_writer" and error["field"] == "as"
    assert error["valid_values"] == ["planner"]
    assert "executor" in error["message"] and "chanchi project writers demo-app --set" in error["hint"]
    assert run_ok(repo, env, "lesson", "list", "--all")["lessons"] == []


def test_cuj4_commands_from_a_nested_repository_belong_to_the_outer_project(nested_repo, cli_env):
    outer, env = nested_repo, cli_env
    inner = outer / "inner"
    run_ok(outer, env, "models", "add", "--agent", "claude", "--model", "opus", "--cost", "3", "--efforts", "high")
    run_ok(outer, env, "models", "add", "--agent", "claude", "--model", "haiku", "--cost", "1")

    lesson = run_ok(inner, env, "lesson", "add", *identity(), "--json", "-", stdin=lesson_body("zork"))["lesson"]
    assert lesson["origin"] == "outer-app"
    run_ok(inner, env, "change", "open", "fix-login", "--kind", "adhoc", "--planner", "claude:opus:high")
    run_ok(
        inner, env, "session", "start", "fix-login", "S1", "--executor", "claude:haiku", "--task-type", "docs",
        "--complexity", "low", "--tasks", "1",
    )

    assert run_ok(outer, env, "show", "fix-login")["change"]["ref"] == "fix-login"
    assert [p["slug"] for p in run_ok(inner, env, "project", "list")["projects"]] == ["outer-app"]
    with sqlite3.connect(env["CHANCHI_DB"]) as raw:
        slugs = [row[0] for row in raw.execute("SELECT slug FROM projects ORDER BY slug")]
        owners = {row[0] for row in raw.execute("SELECT project_id FROM changes")}
    assert slugs == ["outer-app"] and len(owners) == 1
    assert run_ok(inner, env, "lesson", "list")["scope"] == "outer-app"


def test_cuj7_a_global_lesson_from_outside_any_project(db_env, cli_env, tmp_path):
    env = cli_env
    home = tmp_path / "home"
    home.mkdir()
    glob = ("lesson", "add", "--global", "--json", "-")
    body = lesson_body(
        "skill", target_kind="skill", target="skill ~/.agents/skills/chanchi-session-audit"
    )

    error = run_fail(home, env, "lesson", "add", *identity(), "--json", "-", stdin=body)
    assert error["code"] == "project_not_registered" and "--global" in error["hint"]

    owner = run_ok(home, env, *glob, *identity(role="owner", author="human"), stdin=body)["lesson"]
    assert owner["origin"] == "global" and owner["origin_project_id"] is None

    other = lesson_body("skill2", target_kind="skill", target="skill ~/.agents/skills/other")
    assert run_ok(home, env, *glob, *identity(), stdin=other)["lesson"]["origin"] == "global"

    refused = run_fail(
        home, env, *glob, *identity(), stdin=lesson_body("proj", generality="project")
    )
    assert refused["code"] == "invalid_value"
    error = run_fail(home, env, *glob, *identity(role="executor"), stdin=lesson_body("third"))
    assert error["code"] == "not_a_writer" and "global" in error["message"]

    listed = run_ok(home, env, "lesson", "list")
    assert listed["scope"] == "all" and len(listed["lessons"]) == 2
    assert run_ok(home, env, "lesson", "list", "--global")["scope"] == "global"
    reviewed = run_ok(
        home, env, "lesson", "review", str(owner["id"]), *identity(conversation="conv-maint"),
        "--decision", "approve", "--reason", "good",
    )
    assert reviewed["lesson"]["status"] == "approved"
    applied = run_ok(
        home, env, "lesson", "apply", str(owner["id"]), *identity(conversation="conv-maint"), "--site", "global",
        "--where", f"~/.agents/skills/chanchi-session-audit/SKILL.md [lesson #{owner['id']}]",
    )
    assert applied["site"]["site"] == "global" and applied["site"]["project"] is None
