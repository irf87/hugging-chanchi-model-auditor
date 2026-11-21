import io
import json
import subprocess

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
    assert "dimensions" in taxonomy["taxonomy"]
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
    dimensions = ok(capsys, "stats", "--by", "dimension")
    assert dimensions["rows"]
    assert all(row["dimension"] for row in dimensions["rows"])
    assert dimensions["note"]
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
    assert "spec" in lines[1] and "cost_tier" in lines[1] and "capabilities" in lines[1]
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
    assert "skill-chanchi-lessons" in result["skills"]
    assert (target / ".agents" / "skills" / "skill-chanchi-lessons" / "SKILL.md").is_file()
    assert "`skill-chanchi-lessons`" in result["suggested_config_line"]
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


def test_oversized_integer_is_rejected(ready):
    ok(ready, "change", "open", "add-login", "--kind", "openspec", "--planner", "claude:opus:high")
    error = fail(
        ready, "session", "start", "add-login", "S1", "--executor", "agy:gemini-3.8-flash-high:high",
        "--task-type", "ui-component", "--complexity", "medium", "--tasks", "99999999999999999999",
    )
    assert error["code"] == "invalid_value"
    assert error["field"] == "tasks"
    assert error["hint"] == "use an integer between 0 and 1000000"


def test_abbreviated_options_are_rejected(ready):
    error = fail(ready, "models", "list", "--form", "text")
    assert error["code"] == "invalid_value"


def test_capabilities_cli_and_require_text_format(ready):
    added = ok(
        ready,
        "models",
        "add",
        "--agent",
        "claude",
        "--model",
        "sonnet",
        "--cost",
        "2",
        "--capability",
        "vision=yes",
    )["model"]
    assert added["capabilities"] == "vision=yes"

    updated = ok(ready, "models", "set", "claude:opus", "--capability", "vision=no")["model"]
    assert updated["capabilities"] == "vision=no"

    repeated = fail(
        ready,
        "models",
        "set",
        "claude:opus",
        "--capability",
        "vision=yes",
        "--capability",
        "vision=no",
    )
    assert repeated["code"] == "invalid_value"
    assert repeated["field"] == "capability"

    tax = ok(ready, "taxonomy", "list")["taxonomy"]
    assert tax["capabilities"] == {"names": ["vision"], "values": ["yes", "no", "unknown"]}

    code, out, err = run(
        ready,
        "recommend",
        "--task-type",
        "ui-component",
        "--complexity",
        "medium",
        "--available",
        "claude:sonnet,claude:opus,agy:gemini-3.8-flash-high:high",
        "--require",
        "vision",
        "--format",
        "text",
    )
    assert code == 0, err
    assert "excluded:" in out
    assert "claude:opus" in out
    assert "agy:gemini-3.8-flash-high:high" in out
    assert "unknown" in out


# --- projects and lessons --------------------------------------------------

IDENTITY = ("--as", "planner", "--author", "claude:opus:high")


def lesson_body(tag="zork", **over):
    text = " ".join(f"{tag}{suffix}" for suffix in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot"))
    data = {
        "what_happened": text, "evidence": f"evidence of {tag}", "cause": f"cause of {tag}",
        "prevention": f"prevention of {tag}", "proposal": text, "general_rule": text,
        "target": "role executor", "target_kind": "role", "generality": "agnostic", "severity": "high",
    }
    data.update(over)
    return data


def stdin(monkeypatch, data):
    monkeypatch.setattr("sys.stdin", io.StringIO(data if isinstance(data, str) else json.dumps(data)))


def add_lesson(capsys, monkeypatch, tag="zork", conversation="conv-1", *extra, **over):
    stdin(monkeypatch, lesson_body(tag, **over))
    return ok(capsys, "lesson", "add", *IDENTITY, "--conversation", conversation, "--json", "-", *extra)["lesson"]


def review(capsys, lesson_id, decision="approve", conversation="conv-2", *extra):
    return ok(
        capsys, "lesson", "review", str(lesson_id), *IDENTITY, "--conversation", conversation,
        "--decision", decision, "--reason", "good rule", *extra,
    )["lesson"]


NEW_COMMANDS = [
    ["project", "register"],
    ["project", "register", "--name", "x"],
    ["project", "relink", "demo-app"],
    ["project", "list"],
    ["project", "show"],
    ["project", "show", "demo-app"],
    ["project", "writers"],
    ["project", "writers", "demo-app", "--set", "planner,reviewer", *IDENTITY, "--conversation", "c"],
    ["project", "writers", "--global"],
    ["lesson", "add", *IDENTITY, "--conversation", "c", "--json", "-"],
    ["lesson", "add", *IDENTITY, "--conversation", "c", "--json", "f.json", "--force-new", "--global"],
    ["lesson", "repeat", "1", *IDENTITY, "--conversation", "c", "--evidence", "e", "--incident", "2"],
    ["lesson", "modify", "1", *IDENTITY, "--conversation", "c", "--json", "-"],
    ["lesson", "review", "1", *IDENTITY, "--conversation", "c", "--decision", "duplicate", "--reason", "r", "--of", "2"],
    ["lesson", "review", "1", *IDENTITY, "--conversation", "c", "--decision", "reject", "--reason", "r",
     "--reason-code", "covered"],
    ["lesson", "reopen", "1", *IDENTITY, "--conversation", "c", "--reason", "r"],
    ["lesson", "apply", "1", *IDENTITY, "--conversation", "c", "--site", "project", "--where", "x [lesson #1]"],
    ["lesson", "retire", "1", *IDENTITY, "--conversation", "c", "--site", "global", "--reason", "r"],
    ["lesson", "similar", "some text", "--limit", "3"],
    ["lesson", "list", "--status", "pending", "--generality", "agnostic", "--target-kind", "role", "--limit", "5", "--global"],
    ["lesson", "show", "1"],
    ["lesson", "summary", "--project", "demo-app"],
    ["lesson", "export", "--status", "pending,postponed", "--since", "2026-01-01", "--limit", "5", "--all", "--format", "md"],
]


@pytest.mark.parametrize("argv", NEW_COMMANDS, ids=lambda a: " ".join(a[:2]))
def test_every_new_command_parses(argv):
    args = cli.build_parser().parse_args(argv)
    assert callable(args.handler)


def test_identity_flags_are_required_and_named():
    args = cli.build_parser().parse_args(
        ["lesson", "reopen", "4", "--as", "planner", "--author", "human", "--conversation", "c", "--reason", "r"]
    )
    assert (args.as_role, args.author, args.conversation, args.id) == ("planner", "human", "c", 4)


@pytest.mark.parametrize("missing", ["--as", "--author", "--conversation"])
def test_missing_identity_flag_is_a_parse_error(capsys, db_env, missing):
    flags = {"--as": "planner", "--author": "human", "--conversation": "c"}
    del flags[missing]
    argv = ["lesson", "reopen", "1", "--reason", "r"] + [x for kv in flags.items() for x in kv]
    error = fail(capsys, *argv)
    assert error["code"] == "invalid_value" and missing in error["message"]


@pytest.mark.parametrize("command", ["repeat", "modify", "review", "reopen"])
def test_lesson_level_writes_take_no_scope_flags(capsys, db_env, command):
    extra = {
        "repeat": ["--evidence", "e"], "modify": ["--json", "-"],
        "review": ["--decision", "approve", "--reason", "r"], "reopen": ["--reason", "r"],
    }[command]
    for flag in (["--global"], ["--project", "demo-app"]):
        error = fail(capsys, "lesson", command, "1", *IDENTITY, "--conversation", "c", *extra, *flag)
        assert error["code"] == "invalid_value"


def test_review_decision_is_a_choice(capsys, db_env):
    error = fail(capsys, "lesson", "review", "1", *IDENTITY, "--conversation", "c", "--decision", "maybe", "--reason", "r")
    assert error["code"] == "invalid_value"


def test_all_and_global_are_mutually_exclusive(capsys, db_env):
    assert fail(capsys, "lesson", "list", "--all", "--global")["code"] == "invalid_value"


def test_project_register_list_show_relink(capsys, db_env, git_repo):
    registered = ok(capsys, "project", "register")
    assert registered["already_registered"] is False and registered["project"]["slug"] == "demo-app"
    assert ok(capsys, "project", "register")["already_registered"] is True
    assert [p["slug"] for p in ok(capsys, "project", "list")["projects"]] == ["demo-app"]
    shown = ok(capsys, "project", "show")
    assert shown["slug"] == "demo-app" and shown["writers"] == {"roles": ["planner"], "default": True}
    assert ok(capsys, "project", "show", "demo-app")["slug"] == "demo-app"
    assert ok(capsys, "project", "show", "demo-app", "--project", "demo-app")["slug"] == "demo-app"
    assert ok(capsys, "project", "relink", "demo-app")["added"] is False
    assert ok(capsys, "project", "register", "--name", "other")["already_registered"] is True


def test_project_show_with_a_different_project_flag_fails(capsys, db_env, git_repo, monkeypatch):
    ok(capsys, "project", "register", "--name", "a")
    other = git_repo.parent / "b-app"
    other.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=other, check=True)
    monkeypatch.chdir(other)
    ok(capsys, "project", "register", "--name", "b")
    error = fail(capsys, "project", "show", "a", "--project", "b")
    assert error["code"] == "invalid_value" and error["field"] == "project"
    assert ok(capsys, "project", "show", "--project", "a")["slug"] == "a"
    clash = git_repo.parent / "c-app"
    clash.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=clash, check=True)
    monkeypatch.chdir(clash)
    assert fail(capsys, "project", "register", "--name", "a")["field"] == "name"


def test_project_show_outside_a_registered_project(capsys, db_env, git_repo):
    error = fail(capsys, "project", "show")
    assert error["code"] == "project_not_registered"
    assert error["field"] == "project" and "chanchi project register" in error["hint"]
    error = fail(capsys, "project", "show", "nope")
    assert error["code"] == "project_not_registered"


def test_project_writers_show_and_set(registered_repo, capsys):
    shown = ok(capsys, "project", "writers")
    assert shown == {"ok": True, "scope": "demo-app", "roles": ["planner"], "default": True}
    assert ok(capsys, "project", "writers", "--global")["scope"] == "global"
    changed = ok(
        capsys, "project", "writers", "demo-app", "--set", "planner, reviewer", *IDENTITY, "--conversation", "c"
    )
    assert changed["roles"] == ["planner", "reviewer"] and changed["default"] is False
    assert ok(capsys, "project", "writers")["default"] is False
    assert ok(capsys, "project", "writers", "--global")["default"] is True


def test_project_writers_argument_rules(registered_repo, capsys):
    for flag in ("as", "author", "conversation"):
        flags = {"--as": "planner", "--author": "human", "--conversation": "c"}
        del flags[f"--{flag}"]
        error = fail(capsys, "project", "writers", "--set", "planner", *[x for kv in flags.items() for x in kv])
        assert error["code"] == "invalid_value" and error["field"] == flag
    error = fail(capsys, "project", "writers", "demo-app", "--global")
    assert error["code"] == "invalid_value" and error["field"] == "global"
    error = fail(capsys, "project", "writers", "demo-app", "--project", "other")
    assert error["field"] == "project"
    error = fail(capsys, "project", "writers", "--global", "--project", "demo-app")
    assert error["code"] == "invalid_value"
    error = fail(capsys, "project", "writers", "--set", "x", "--as", "executor", "--author", "claude:opus", "--conversation", "c")
    assert error["code"] == "not_a_writer"
    assert ok(capsys, "project", "writers")["roles"] == ["planner"]


def test_lesson_add_reads_stdin_or_a_file(registered_repo, capsys, monkeypatch, tmp_path):
    first = add_lesson(capsys, monkeypatch)
    assert first["status"] == "pending" and first["origin"] == "demo-app"
    path = tmp_path / "body.json"
    path.write_text(json.dumps(lesson_body("quux")))
    second = ok(capsys, "lesson", "add", *IDENTITY, "--conversation", "conv-1", "--json", str(path))["lesson"]
    assert second["id"] == first["id"] + 1


def test_invalid_json_is_invalid_value_on_field_json(registered_repo, capsys, monkeypatch, tmp_path):
    stdin(monkeypatch, "{not json")
    error = fail(capsys, "lesson", "add", *IDENTITY, "--conversation", "c", "--json", "-")
    assert error["code"] == "invalid_value" and error["field"] == "json"
    error = fail(capsys, "lesson", "add", *IDENTITY, "--conversation", "c", "--json", str(tmp_path / "missing.json"))
    assert error["code"] == "invalid_value" and error["field"] == "json"
    stdin(monkeypatch, "{not json")
    error = fail(capsys, "lesson", "modify", "1", *IDENTITY, "--conversation", "c", "--json", "-")
    assert error["field"] == "json"
    stdin(monkeypatch, "[1, 2]")
    assert fail(capsys, "lesson", "add", *IDENTITY, "--conversation", "c", "--json", "-")["code"] == "invalid_value"


def test_global_flag_records_a_global_lesson_from_anywhere(db_env, git_repo, capsys, monkeypatch):
    stdin(monkeypatch, lesson_body("glob"))
    error = fail(capsys, "lesson", "add", *IDENTITY, "--conversation", "c", "--json", "-")
    assert error["code"] == "project_not_registered"
    stdin(monkeypatch, lesson_body("glob"))
    lesson = ok(capsys, "lesson", "add", *IDENTITY, "--conversation", "c", "--json", "-", "--global")["lesson"]
    assert lesson["origin"] == "global" and lesson["origin_project_id"] is None
    stdin(monkeypatch, lesson_body("glob2"))
    error = fail(capsys, "lesson", "add", *IDENTITY, "--conversation", "c", "--json", "-", "--global", "--project", "demo-app")
    assert error["code"] == "invalid_value"


def test_not_a_writer_reaches_stderr_with_its_fields(registered_repo, capsys, monkeypatch):
    stdin(monkeypatch, lesson_body())
    error = fail(
        capsys, "lesson", "add", "--as", "executor", "--author", "claude:opus", "--conversation", "c", "--json", "-"
    )
    assert error["code"] == "not_a_writer" and error["field"] == "as"
    assert error["valid_values"] == ["planner"]
    assert "executor" in error["message"] and "chanchi project writers demo-app --set" in error["hint"]
    assert ok(capsys, "lesson", "list")["lessons"] == []


def test_self_review_and_transition_errors(registered_repo, capsys, monkeypatch):
    lesson = add_lesson(capsys, monkeypatch)
    error = fail(
        capsys, "lesson", "review", str(lesson["id"]), *IDENTITY, "--conversation", "conv-1",
        "--decision", "approve", "--reason", "r",
    )
    assert error["code"] == "self_review" and error["field"] == "conversation" and error["hint"]
    review(capsys, lesson["id"])
    error = fail(
        capsys, "lesson", "reopen", str(lesson["id"]), *IDENTITY, "--conversation", "conv-2", "--reason", "r"
    )
    assert error["code"] == "invalid_transition" and error["field"] == "status"
    assert error["valid_values"] and error["hint"]


def test_lesson_not_found_and_duplicate_lesson(registered_repo, capsys, monkeypatch):
    error = fail(capsys, "lesson", "show", "99")
    assert error["code"] == "lesson_not_found" and error["field"] == "id" and "chanchi lesson list" in error["hint"]
    first = add_lesson(capsys, monkeypatch)
    stdin(monkeypatch, lesson_body())
    error = fail(capsys, "lesson", "add", *IDENTITY, "--conversation", "conv-1", "--json", "-")
    assert error["code"] == "duplicate_lesson" and error["field"] == "general_rule"
    assert error["details"]["id"] == first["id"]
    assert set(error["details"]) == {"id", "status", "general_rule", "shared", "test"}
    assert "--force-new" in error["hint"]
    stdin(monkeypatch, lesson_body())
    forced = ok(capsys, "lesson", "add", *IDENTITY, "--conversation", "conv-1", "--json", "-", "--force-new")
    assert forced["lesson"]["id"] == first["id"] + 1


def test_lesson_apply_repeat_modify_retire(registered_repo, capsys, monkeypatch):
    lesson = add_lesson(capsys, monkeypatch)
    lid = str(lesson["id"])
    repeated = ok(capsys, "lesson", "repeat", lid, *IDENTITY, "--conversation", "c", "--evidence", "again")
    assert repeated["lesson"]["occurrences"] == 2
    stdin(monkeypatch, lesson_body("zork", severity="critical"))
    modified = ok(capsys, "lesson", "modify", lid, *IDENTITY, "--conversation", "conv-1", "--json", "-")
    assert modified["lesson"]["severity"] == "critical"
    review(capsys, lid)
    where = f"roles/executor.md [lesson #{lid}] @ abc123"
    applied = ok(capsys, "lesson", "apply", lid, *IDENTITY, "--conversation", "c", "--site", "project", "--where", where)
    assert applied["site"]["state"] == "applied" and applied["site"]["project"] == "demo-app"
    error = fail(capsys, "lesson", "apply", lid, *IDENTITY, "--conversation", "c", "--site", "nowhere", "--where", where)
    assert error["code"] == "invalid_value" and error["field"] == "site"
    retired = ok(capsys, "lesson", "retire", lid, *IDENTITY, "--conversation", "c", "--site", "project", "--reason", "gone")
    assert retired["site"]["state"] == "retired"


def test_apply_site_project_needs_a_project_outside_one(registered_repo, capsys, monkeypatch, tmp_path):
    lesson = add_lesson(capsys, monkeypatch)
    review(capsys, lesson["id"])
    where = f"x.md [lesson #{lesson['id']}]"
    monkeypatch.chdir(tmp_path)
    error = fail(
        capsys, "lesson", "apply", str(lesson["id"]), *IDENTITY, "--conversation", "c", "--site", "project", "--where", where
    )
    assert error["code"] == "project_not_registered"
    applied = ok(
        capsys, "lesson", "apply", str(lesson["id"]), *IDENTITY, "--conversation", "c", "--site", "project",
        "--where", where, "--project", "demo-app",
    )
    assert applied["site"]["project"] == "demo-app"
    glob = ok(
        capsys, "lesson", "apply", str(lesson["id"]), *IDENTITY, "--conversation", "c", "--site", "global", "--where", where
    )
    assert glob["site"]["site"] == "global"


def test_read_commands_scope(registered_repo, capsys, monkeypatch, tmp_path):
    add_lesson(capsys, monkeypatch)
    stdin(monkeypatch, lesson_body("glob"))
    ok(capsys, "lesson", "add", *IDENTITY, "--conversation", "c", "--json", "-", "--global")
    listed = ok(capsys, "lesson", "list")
    assert listed["scope"] == "demo-app" and [x["origin"] for x in listed["lessons"]] == ["demo-app"]
    assert ok(capsys, "lesson", "list", "--global")["scope"] == "global"
    assert ok(capsys, "lesson", "list", "--project", "demo-app")["scope"] == "demo-app"
    everything = ok(capsys, "lesson", "list", "--all")
    assert everything["scope"] == "all" and len(everything["lessons"]) == 2
    assert fail(capsys, "lesson", "list", "--all", "--project", "demo-app")["field"] == "project"
    assert fail(capsys, "lesson", "list", "--global", "--project", "demo-app")["code"] == "invalid_value"
    assert fail(capsys, "lesson", "list", "--project", "nope")["code"] == "project_not_registered"
    monkeypatch.chdir(tmp_path)
    outside = ok(capsys, "lesson", "list")
    assert outside["scope"] == "all" and len(outside["lessons"]) == 2
    assert ok(capsys, "lesson", "summary")["scope"] == "all"
    assert ok(capsys, "lesson", "export")["scope"] == "all"


def test_similar_show_and_summary(registered_repo, capsys, monkeypatch):
    lesson = add_lesson(capsys, monkeypatch)
    similar = ok(capsys, "lesson", "similar", "zorkalpha zorkbravo zorkcharlie zorkdelta")
    assert similar["scope"] == "all" and [m["id"] for m in similar["matches"]] == [lesson["id"]]
    assert ok(capsys, "lesson", "similar", "nothing related whatsoever")["matches"] == []
    shown = ok(capsys, "lesson", "show", str(lesson["id"]))
    assert [e["action"] for e in shown["events"]] == ["created"]
    summary = ok(capsys, "lesson", "summary")
    assert summary["by_status"]["pending"] == 1 and summary["force_new_rate"] == 0
    assert fail(capsys, "lesson", "list", "--status", "bogus")["code"] == "invalid_value"
    assert fail(capsys, "lesson", "export", "--since", "yesterday")["field"] == "since"


def test_export_markdown_format(registered_repo, capsys, monkeypatch):
    lesson = add_lesson(capsys, monkeypatch)
    code, out, err = run(capsys, "lesson", "export", "--format", "md")
    assert code == 0, err
    assert out.startswith(f"## #{lesson['id']} \u00b7 agnostic \u00b7 high \u00b7 \u00d71\n")
    assert "- **general_rule:** zorkalpha" in out
    assert "{" not in out.splitlines()[0]
    payload = ok(capsys, "lesson", "export")
    assert "markdown" not in payload
    code, out, _ = run(capsys, "lesson", "export", "--format", "text")
    assert code == 0 and out.startswith("scope: demo-app") and "## #" not in out


def test_md_format_falls_back_to_text_elsewhere(registered_repo, capsys, monkeypatch):
    add_lesson(capsys, monkeypatch)
    code, out, _ = run(capsys, "lesson", "list", "--format", "md")
    assert code == 0 and out.startswith("scope: demo-app")
    code, out, _ = run(capsys, "models", "list", "--format", "md")
    assert code == 0 and out.startswith("models:")
    code, _, err = run(capsys, "lesson", "show", "99", "--format", "md")
    assert code == 2 and err.startswith("error:")


def test_project_help_text_names_the_registered_project(capsys):
    code, out, _ = run(capsys, "change", "close", "--help")
    assert code == 0 and "registered project for this directory" in " ".join(out.split())
