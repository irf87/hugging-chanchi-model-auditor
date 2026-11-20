import subprocess

import pytest

from chanchi import lessons, projects, record
from chanchi.errors import ChanchiError
from helpers import Recorder, inc

SUFFIXES = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")


def text(tag):
    """Six tokens that no other tag shares, so lessons with different tags never match."""
    return " ".join(f"{tag}{suffix}" for suffix in SUFFIXES)


def body(tag="zork", **over):
    data = {
        "what_happened": text(tag),
        "evidence": f"evidence of {tag}",
        "cause": f"cause of {tag}",
        "prevention": f"prevention of {tag}",
        "proposal": text(tag),
        "general_rule": text(tag),
        "target": "role executor",
        "target_kind": "role",
        "generality": "agnostic",
        "severity": "high",
    }
    data.update(over)
    return data


@pytest.fixture
def env(seeded, registered_repo):
    return seeded


@pytest.fixture
def scope(env):
    return projects.resolve_scope(env)


def actor(conn, role="planner", conversation="conv-1", author="claude:opus:high"):
    return lessons.make_actor(conn, role, author, conversation)


def reviewer(conn, role="planner"):
    return actor(conn, role, "conv-review")


def record_lesson(conn, scope, tag="zork", conversation="conv-1", **over):
    return lessons.add(conn, scope, actor(conn, conversation=conversation), body(tag, **over))["lesson"]


def approved(conn, scope, tag="zork", **over):
    lesson = record_lesson(conn, scope, tag, **over)
    lessons.review(conn, reviewer(conn), lesson["id"], "approve", "good rule")
    return lesson["id"]


def events(conn, lesson_id):
    return conn.execute("SELECT * FROM lesson_events WHERE lesson_id = ? ORDER BY id", (lesson_id,)).fetchall()


def refused(code, field=None):
    class Check:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            assert exc_type is not None, "expected a ChanchiError"
            assert issubclass(exc_type, ChanchiError), repr(exc)
            assert exc.code == code, f"{exc.code}: {exc.message}"
            if field is not None:
                assert exc.field == field, f"{exc.field}: {exc.message}"
            self.error = exc
            return True

    return Check()


def other_project(conn, tmp_path, name="other-app"):
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    projects.register(conn, repo)
    return projects.resolve_scope(conn, project=name)


def change_with_incidents(conn, ref, count=1):
    recorder = Recorder(conn)
    recorder.change(ref)
    recorder.session(
        ref, "S1", "claude:sonnet:medium", incidents=[inc("plan_gap") for _ in range(count)], verdict=None
    )
    rows = conn.execute(
        "SELECT i.id FROM incidents i JOIN changes c ON c.id = i.change_id WHERE c.ref = ? ORDER BY i.id",
        (ref,),
    ).fetchall()
    return [row["id"] for row in rows]


# --- body validation -----------------------------------------------------------------


def test_add_records_pending_lesson_with_event_and_git_head(env, scope):
    result = lessons.add(env, scope, actor(env), body(tags=["a", "b"]))
    lesson = result["lesson"]
    assert lesson["status"] == "pending"
    assert lesson["origin"] == "demo-app"
    assert lesson["occurrences"] == 1
    assert lesson["tags"] == ["a", "b"]
    assert lesson["git_head"] == projects.git_head()
    assert lesson["git_head"]
    assert result["warnings"] == []


def test_missing_general_rule_is_refused(env, scope):
    data = body()
    del data["general_rule"]
    with refused("invalid_value", "general_rule"):
        lessons.add(env, scope, actor(env), data)
    assert env.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 0


def test_particular_rules(env, scope):
    with refused("invalid_value", "severity"):
        lessons.add(
            env, scope, actor(env), body(generality="particular", severity="medium", particular_justification="why")
        )
    with refused("invalid_value", "particular_justification"):
        lessons.add(env, scope, actor(env), body(generality="particular", severity="high"))
    with refused("invalid_value", "particular_justification"):
        lessons.add(
            env, scope, actor(env), body(generality="particular", severity="high", particular_justification="  ")
        )
    lesson = lessons.add(
        env,
        scope,
        actor(env),
        body(generality="particular", severity="critical", particular_justification="only this case"),
    )["lesson"]
    assert lesson["generality"] == "particular"
    assert lesson["particular_justification"] == "only this case"


def test_blocking_severity_is_refused_with_hint(env, scope):
    with refused("invalid_value", "severity") as check:
        lessons.add(env, scope, actor(env), body(severity="blocking"))
    assert "critical" in check.error.hint


def test_unknown_key_is_refused(env, scope):
    with refused("invalid_value", "mood") as check:
        lessons.add(env, scope, actor(env), body(mood="sad"))
    assert "what_happened" in check.error.valid_values


def test_session_without_change_is_refused(env, scope):
    with refused("invalid_value", "session"):
        lessons.add(env, scope, actor(env), body(session="S1"))


def test_incidents_without_change_is_refused(env, scope):
    with refused("invalid_value", "incidents"):
        lessons.add(env, scope, actor(env), body(incidents=[1]))


def test_incident_from_another_change_is_refused(env, scope):
    first = change_with_incidents(env, "c1")
    second = change_with_incidents(env, "c2")
    with refused("invalid_value", "incidents"):
        lessons.add(env, scope, actor(env), body(change="c1", incidents=second))
    lesson = lessons.add(env, scope, actor(env), body(change="c1", session="S1", incidents=first))["lesson"]
    assert lesson["change_id"] is not None
    assert lesson["session_id"] is not None
    shown = lessons.show(env, lesson["id"])
    assert [i["id"] for i in shown["incidents"]] == first
    assert shown["incidents"][0]["session"] == "S1"


def test_voided_incident_is_refused(env, scope):
    ids = change_with_incidents(env, "c1")
    record.void_incident(env, incident_id=ids[0], reason="wrong")
    with refused("invalid_value", "incidents"):
        lessons.add(env, scope, actor(env), body(change="c1", incidents=ids))


def test_unknown_change_and_session(env, scope):
    with refused("unknown_change"):
        lessons.add(env, scope, actor(env), body(change="nope"))
    change_with_incidents(env, "c1")
    with refused("unknown_session"):
        lessons.add(env, scope, actor(env), body(change="c1", session="S9"))


def test_global_lesson_rules(env):
    global_scope = projects.Scope(None, None)
    with refused("invalid_value", "generality"):
        lessons.add(env, global_scope, actor(env), body(generality="project"))
    change_with_incidents(env, "c1")
    with refused("invalid_value", "change"):
        lessons.add(env, global_scope, actor(env), body(change="c1"))
    lesson = lessons.add(env, global_scope, actor(env), body())["lesson"]
    assert lesson["origin"] == "global"
    assert lesson["origin_project_id"] is None


def test_tags_normalization(env, scope):
    as_list = record_lesson(env, scope, "alfa", tags=["x", " y "])
    as_text = record_lesson(env, scope, "beta", tags="x, y")
    assert as_list["tags"] == as_text["tags"] == ["x", "y"]
    stored = lambda lid: env.execute("SELECT tags FROM lessons WHERE id = ?", (lid,)).fetchone()[0]
    assert stored(as_list["id"]) == stored(as_text["id"]) == "x,y"
    missing = record_lesson(env, scope, "gamma")
    empty_list = record_lesson(env, scope, "delt", tags=[])
    empty_text = record_lesson(env, scope, "epsi", tags="")
    for lesson in (missing, empty_list, empty_text):
        assert stored(lesson["id"]) == ""
        assert lesson["tags"] == []


def test_wrong_json_types_are_refused_before_other_rules(env, scope):
    data = body(cause=3)
    del data["general_rule"]
    with refused("invalid_value", "cause"):
        lessons.add(env, scope, actor(env), data)
    with refused("invalid_value", "incidents"):
        lessons.add(env, scope, actor(env), body(incidents="1,2"))
    with refused("invalid_value", "incidents"):
        lessons.add(env, scope, actor(env), body(incidents=[True]))
    with refused("invalid_value", "tags"):
        lessons.add(env, scope, actor(env), body(tags=[1]))
    with refused("invalid_value", "json"):
        lessons.add(env, scope, actor(env), ["not", "an", "object"])
    assert env.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 0


def test_replaces_is_stored_and_checked(env, scope):
    first = record_lesson(env, scope, "zork")
    second = lessons.add(env, scope, actor(env), body("blip", replaces=[first["id"]]))["lesson"]
    assert lessons.show(env, second["id"])["replaces"] == [first["id"]]
    with refused("lesson_not_found"):
        lessons.add(env, scope, actor(env), body("quux", replaces=[999]))


# --- actor ---------------------------------------------------------------------------


def test_author_model_id_is_set_on_exact_catalog_match_only(env, scope):
    before = env.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    known = record_lesson(env, scope, "zork")
    assert known["author_model_id"] is not None
    assert known["author_model_raw"] == "opus"
    assert known["author_effort"] == "high"
    unknown = lessons.add(env, scope, lessons.make_actor(env, "planner", "claude:brand-new", "c"), body("blip"))["lesson"]
    assert unknown["author_model_id"] is None
    assert unknown["author_effort"] is None
    assert env.execute("SELECT COUNT(*) FROM models").fetchone()[0] == before


def test_author_human_uses_seeded_row(env):
    made = lessons.make_actor(env, "planner", "human", "c")
    row = env.execute("SELECT id FROM models WHERE agent = 'human' AND model = 'human'").fetchone()
    assert (made.agent, made.model_raw, made.model_id) == ("human", "human", row["id"])


def test_mistyped_effort_is_refused(env):
    with refused("invalid_value", "author") as check:
        lessons.make_actor(env, "planner", "claude:opus:hgh", "c")
    assert "high" in check.error.valid_values
    assert "chanchi models add" in check.error.hint


def test_model_names_with_colons(env):
    catalogued = lessons.make_actor(env, "planner", "opencode:openrouter/qwen/qwen3-coder:free", "c")
    assert catalogued.model_raw == "openrouter/qwen/qwen3-coder:free"
    assert catalogued.model_id is not None
    far = lessons.make_actor(env, "planner", "opencode:vendor/model:beta", "c")
    assert far.model_id is None


def test_actor_requires_role_conversation_and_valid_agent(env):
    with refused("invalid_value", "as"):
        lessons.make_actor(env, " ", "claude:opus", "c")
    with refused("invalid_value", "conversation"):
        lessons.make_actor(env, "planner", "claude:opus", "")
    with refused("invalid_value", "author"):
        lessons.make_actor(env, "planner", "robot:x", "c")


# --- writers -------------------------------------------------------------------------


def test_non_writer_is_refused_and_nothing_is_written(env, scope):
    with refused("not_a_writer", "as") as check:
        lessons.add(env, scope, actor(env, role="executor"), body())
    assert check.error.valid_values == ["planner"]
    assert env.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 0


def test_human_passes_whatever_the_role(env, scope):
    human = lessons.make_actor(env, "anything", "human", "c")
    assert lessons.add(env, scope, human, body())["lesson"]["author_role"] == "anything"


def test_custom_writer_role(env, scope):
    projects.set_writer_roles(env, scope.project_id, ["curator"])
    lessons.add(env, scope, actor(env, role="curator"), body())
    with refused("not_a_writer"):
        lessons.add(env, scope, actor(env, role="planner"), body("blip"))


def test_global_lesson_uses_global_writer_roles(env, scope):
    global_scope = projects.Scope(None, None)
    projects.set_writer_roles(env, None, ["steward"])
    projects.set_writer_roles(env, scope.project_id, ["curator"])
    lessons.add(env, global_scope, actor(env, role="steward"), body())
    with refused("not_a_writer"):
        lessons.add(env, global_scope, actor(env, role="curator"), body("blip"))


def test_agnostic_lesson_is_reviewed_under_its_origin_project_roles(env, scope):
    lesson = record_lesson(env, scope)
    projects.set_writer_roles(env, scope.project_id, ["lead"])
    projects.set_writer_roles(env, None, ["steward"])
    with refused("not_a_writer"):
        lessons.review(env, actor(env, "steward", "conv-review"), lesson["id"], "approve", "ok")
    result = lessons.review(env, actor(env, "lead", "conv-review"), lesson["id"], "approve", "ok")
    assert result["lesson"]["status"] == "approved"


def test_set_writers_rules(env, scope):
    with refused("not_a_writer"):
        lessons.set_writers(env, scope, actor(env, role="executor"), ["executor"])
    assert projects.writer_roles(env, scope.project_id) == ("planner",)
    result = lessons.set_writers(env, scope, actor(env), [" planner ", "planner", "curator"])
    assert result == {"scope": "demo-app", "roles": ["planner", "curator"], "default": False}
    assert projects.writer_roles(env, scope.project_id) == ("planner", "curator")
    stored = env.execute("SELECT COUNT(*) FROM writer_roles WHERE project_id = ?", (scope.project_id,)).fetchone()[0]
    assert stored == 2
    lessons.set_writers(env, scope, lessons.make_actor(env, "x", "human", "c"), ["lead"])
    assert projects.writer_roles(env, scope.project_id) == ("lead",)
    assert env.execute("SELECT COUNT(*) FROM lesson_events").fetchone()[0] == 0


def test_set_writers_refuses_blank_role_and_empty_list(env, scope):
    for roles in ([], ["planner", "  "], [""]):
        with refused("invalid_value", "set"):
            lessons.set_writers(env, scope, actor(env), roles)
    assert projects.writer_roles(env, scope.project_id) == ("planner",)


def test_set_writers_single_role_dedup_and_scope_isolation(env, scope):
    lessons.set_writers(env, scope, actor(env), ["planner", "planner"])
    assert env.execute("SELECT COUNT(*) FROM writer_roles WHERE project_id = ?", (scope.project_id,)).fetchone()[0] == 1
    glob = projects.Scope(None, None)
    result = lessons.set_writers(env, glob, actor(env), ["steward"])
    assert result["scope"] == "global"
    # the global list changed; the project's list did not
    assert projects.writer_roles(env, None) == ("steward",)
    assert projects.writer_roles(env, scope.project_id) == ("planner",)
    with refused("not_a_writer"):
        lessons.set_writers(env, glob, actor(env), ["planner"])


# --- review and reopen ----------------------------------------------------------------


def test_self_review_is_refused_other_conversation_passes(env, scope):
    lesson = record_lesson(env, scope)
    with refused("self_review", "conversation"):
        lessons.review(env, actor(env, conversation="conv-1"), lesson["id"], "approve", "ok")
    assert lessons.show(env, lesson["id"])["lesson"]["status"] == "pending"
    result = lessons.review(env, reviewer(env), lesson["id"], "approve", "ok")
    assert result["lesson"]["status"] == "approved"
    assert result["lesson"]["reviewed_by_role"] == "planner"
    assert result["lesson"]["review_conversation"] == "conv-review"
    assert result["repointed"] == []


def test_review_argument_rules(env, scope):
    lesson = record_lesson(env, scope)
    for decision, kwargs, field in (
        ("approve", {"reason_code": "covered"}, "reason_code"),
        ("duplicate", {}, "of"),
        ("approve", {"of": 1}, "of"),
        ("reject", {"reason_code": "bogus"}, "reason_code"),
        ("bogus", {}, "decision"),
    ):
        with refused("invalid_value", field):
            lessons.review(env, reviewer(env), lesson["id"], decision, "r", **kwargs)
    with refused("invalid_value", "reason"):
        lessons.review(env, reviewer(env), lesson["id"], "approve", " ")
    with refused("lesson_not_found"):
        lessons.review(env, reviewer(env), 999, "approve", "r")


def test_reject_stores_reason_and_code(env, scope):
    lesson = record_lesson(env, scope)
    result = lessons.review(env, reviewer(env), lesson["id"], "reject", "too rare", reason_code="too_costly")["lesson"]
    assert (result["status"], result["decision_reason"], result["reason_code"]) == ("rejected", "too rare", "too_costly")


def test_postpone_rules(env, scope):
    lesson = record_lesson(env, scope)
    lessons.review(env, reviewer(env), lesson["id"], "postpone", "later")
    with refused("invalid_transition", "status"):
        lessons.review(env, reviewer(env), lesson["id"], "postpone", "later again")
    assert lessons.review(env, reviewer(env), lesson["id"], "approve", "now")["lesson"]["status"] == "approved"


def test_approved_cannot_be_reopened_or_reviewed_again(env, scope):
    lesson_id = approved(env, scope)
    with refused("invalid_transition", "status"):
        lessons.reopen(env, reviewer(env), lesson_id, "second thoughts")
    with refused("invalid_transition", "status"):
        lessons.review(env, reviewer(env), lesson_id, "reject", "r")


def test_reopen_from_rejected_clears_review_fields(env, scope):
    lesson = record_lesson(env, scope)
    lessons.review(env, reviewer(env), lesson["id"], "reject", "no", reason_code="covered")
    reopened = lessons.reopen(env, reviewer(env), lesson["id"], "new evidence")["lesson"]
    assert reopened["status"] == "pending"
    for column in (
        "reviewed_at",
        "reviewed_by_role",
        "review_conversation",
        "decision_reason",
        "reason_code",
        "duplicate_of",
    ):
        assert reopened[column] is None
    with refused("invalid_value", "reason"):
        lessons.reopen(env, reviewer(env), lesson["id"], "")


def test_duplicate_moves_occurrences(env, scope):
    first = record_lesson(env, scope, "zork")
    second = record_lesson(env, scope, "blip")
    lessons.repeat(env, actor(env), second["id"], "again")
    lessons.repeat(env, actor(env), second["id"], "and again")
    result = lessons.review(env, reviewer(env), second["id"], "duplicate", "same thing", of=first["id"])
    assert result["lesson"]["status"] == "duplicate"
    assert result["lesson"]["duplicate_of"] == first["id"]
    assert lessons.show(env, first["id"])["lesson"]["occurrences"] == 4
    note = events(env, second["id"])[-1]["note"]
    assert note == f"moved=3 to=#{first['id']}"


def test_duplicate_of_refusals(env, scope):
    first = record_lesson(env, scope, "zork")
    second = record_lesson(env, scope, "blip")
    third = record_lesson(env, scope, "quux")
    with refused("invalid_value", "of"):
        lessons.review(env, reviewer(env), second["id"], "duplicate", "r", of=second["id"])
    with refused("lesson_not_found"):
        lessons.review(env, reviewer(env), second["id"], "duplicate", "r", of=999)
    lessons.review(env, reviewer(env), third["id"], "duplicate", "r", of=first["id"])
    with refused("invalid_value", "of"):
        lessons.review(env, reviewer(env), second["id"], "duplicate", "r", of=third["id"])
    assert lessons.show(env, second["id"])["lesson"]["status"] == "pending"


def test_duplicate_repoints_earlier_duplicates(env, scope):
    first = record_lesson(env, scope, "zork")
    second = record_lesson(env, scope, "blip")
    third = record_lesson(env, scope, "quux")
    lessons.review(env, reviewer(env), third["id"], "duplicate", "r", of=second["id"])
    result = lessons.review(env, reviewer(env), second["id"], "duplicate", "r", of=first["id"])
    assert result["repointed"] == [third["id"]]
    assert lessons.show(env, third["id"])["lesson"]["duplicate_of"] == first["id"]
    # the re-pointed lesson's own event note is unchanged
    assert events(env, third["id"])[-1]["note"] == f"moved=1 to=#{second['id']}"


def test_reopen_from_duplicate_gives_occurrences_back(env, scope):
    first = record_lesson(env, scope, "zork")
    second = record_lesson(env, scope, "blip")
    lessons.repeat(env, actor(env), second["id"], "again")
    lessons.review(env, reviewer(env), second["id"], "duplicate", "same", of=first["id"])
    assert lessons.show(env, first["id"])["lesson"]["occurrences"] == 3
    reopened = lessons.reopen(env, reviewer(env), second["id"], "not the same")["lesson"]
    assert reopened["status"] == "pending"
    assert reopened["duplicate_of"] is None
    assert reopened["reviewed_at"] is None
    assert lessons.show(env, first["id"])["lesson"]["occurrences"] == 1


def test_reopen_from_duplicate_never_goes_below_one(env, scope):
    first = record_lesson(env, scope, "zork")
    second = record_lesson(env, scope, "blip")
    lessons.review(env, reviewer(env), second["id"], "duplicate", "same", of=first["id"])
    env.execute("UPDATE lessons SET occurrences = 1 WHERE id = ?", (first["id"],))
    lessons.reopen(env, reviewer(env), second["id"], "not the same")
    assert lessons.show(env, first["id"])["lesson"]["occurrences"] == 1


def test_model_weakness_needs_a_linked_session(env, scope):
    plain = record_lesson(env, scope, "zork")
    with refused("invalid_value", "reason_code"):
        lessons.review(env, reviewer(env), plain["id"], "reject", "weak model", reason_code="model_weakness")
    change_with_incidents(env, "c1")
    linked = record_lesson(env, scope, "blip", change="c1", session="S1")
    result = lessons.review(env, reviewer(env), linked["id"], "reject", "weak model", reason_code="model_weakness")
    assert result["lesson"]["reason_code"] == "model_weakness"


# --- repeat -------------------------------------------------------------------------


def test_repeat_adds_one_occurrence(env, scope):
    lesson = record_lesson(env, scope)
    result = lessons.repeat(env, actor(env, conversation="conv-9"), lesson["id"], "happened again")
    assert result["lesson"]["occurrences"] == 2
    assert result["warnings"] == []
    event = events(env, lesson["id"])[-1]
    assert (event["action"], event["note"], event["conversation"]) == ("repeated", "happened again", "conv-9")
    with refused("invalid_value", "evidence"):
        lessons.repeat(env, actor(env), lesson["id"], " ")


def test_repeat_is_refused_on_duplicate_and_warns_on_rejected(env, scope):
    first = record_lesson(env, scope, "zork")
    second = record_lesson(env, scope, "blip")
    lessons.review(env, reviewer(env), second["id"], "duplicate", "same", of=first["id"])
    with refused("invalid_transition", "status") as check:
        lessons.repeat(env, actor(env), second["id"], "again")
    assert str(first["id"]) in check.error.hint
    lessons.review(env, reviewer(env), first["id"], "reject", "not worth it", reason_code="too_costly")
    result = lessons.repeat(env, actor(env), first["id"], "again")
    assert result["lesson"]["occurrences"] == 3  # 1 + 1 moved from the duplicate + this one
    assert result["warnings"] == [
        {"kind": "rejected_recurs", "id": first["id"], "reason_code": "too_costly", "decision_reason": "not worth it"}
    ]


def test_repeat_incident_rules(env, scope):
    ids = change_with_incidents(env, "c1", count=2)
    other = change_with_incidents(env, "c2")
    plain = record_lesson(env, scope, "zork")
    with refused("invalid_value", "incident"):
        lessons.repeat(env, actor(env), plain["id"], "again", incident=ids[0])
    linked = record_lesson(env, scope, "blip", change="c1", session="S1", incidents=[ids[0]])
    with refused("invalid_value", "incident"):
        lessons.repeat(env, actor(env), linked["id"], "again", incident=other[0])
    record.void_incident(env, incident_id=ids[1], reason="wrong")
    with refused("invalid_value", "incidents"):
        lessons.repeat(env, actor(env), linked["id"], "again", incident=ids[1])
    assert lessons.show(env, linked["id"])["lesson"]["occurrences"] == 1
    env.execute("UPDATE incidents SET voided_at = NULL, void_reason = NULL WHERE id = ?", (ids[1],))
    lessons.repeat(env, actor(env), linked["id"], "again", incident=ids[1])
    assert [i["id"] for i in lessons.show(env, linked["id"])["incidents"]] == ids


# --- modify -------------------------------------------------------------------------


def test_modify_replaces_content(env, scope):
    lesson = record_lesson(env, scope, "zork", tags="a")
    new = body("zork", cause="a better cause", severity="medium", tags=["b"])
    result = lessons.modify(env, actor(env), lesson["id"], new)["lesson"]
    assert result["cause"] == "a better cause"
    assert result["severity"] == "medium"
    assert result["tags"] == ["b"]
    assert result["status"] == "pending"
    assert result["git_head"] == lesson["git_head"]


def test_modify_refusals(env, scope):
    lesson = record_lesson(env, scope)
    with refused("invalid_value", "conversation"):
        lessons.modify(env, actor(env, conversation="conv-other"), lesson["id"], body())
    lessons.review(env, reviewer(env), lesson["id"], "approve", "ok")
    with refused("invalid_transition", "status"):
        lessons.modify(env, actor(env), lesson["id"], body())
    with refused("lesson_not_found"):
        lessons.modify(env, actor(env), 999, body())


def test_modify_keeps_change_and_session(env, scope):
    change_with_incidents(env, "c1")
    change_with_incidents(env, "c2")
    lesson = record_lesson(env, scope, "zork", change="c1", session="S1")
    with refused("invalid_value", "change"):
        lessons.modify(env, actor(env), lesson["id"], body("zork", change="c2"))
    with refused("invalid_value", "session"):
        lessons.modify(env, actor(env), lesson["id"], body("zork", change="c1", session="S2"))
    kept = lessons.modify(env, actor(env), lesson["id"], body("zork", change="c1", session="S1"))["lesson"]
    assert (kept["change_id"], kept["session_id"]) == (lesson["change_id"], lesson["session_id"])
    plain = record_lesson(env, scope, "blip")
    with refused("invalid_value", "change"):
        lessons.modify(env, actor(env), plain["id"], body("blip", change="c1"))


def test_modify_replaces_incident_and_replaces_links(env, scope):
    ids = change_with_incidents(env, "c1", count=2)
    other = record_lesson(env, scope, "quux")
    lesson = record_lesson(env, scope, "zork", change="c1", incidents=[ids[0]], replaces=[other["id"]])
    lessons.modify(env, actor(env), lesson["id"], body("zork", incidents=[ids[1]]))
    shown = lessons.show(env, lesson["id"])
    assert [i["id"] for i in shown["incidents"]] == [ids[1]]
    assert shown["replaces"] == []
    with refused("invalid_value", "replaces"):
        lessons.modify(env, actor(env), lesson["id"], body("zork", replaces=[lesson["id"]]))


def test_modify_reruns_duplicate_check_without_matching_itself(env, scope):
    lesson = record_lesson(env, scope, "zork")
    lessons.modify(env, actor(env), lesson["id"], body("zork", cause="different cause"))
    record_lesson(env, scope, "blip")
    with refused("duplicate_lesson") as check:
        lessons.modify(env, actor(env), lesson["id"], body("blip"))
    assert check.error.details["id"] != lesson["id"]


# --- apply and retire -----------------------------------------------------------------


def where_for(lesson_id, path="roles/executor.md"):
    return f"{path} [lesson #{lesson_id}] @ abc123"


def test_apply_needs_an_approved_lesson(env, scope):
    lesson = record_lesson(env, scope)
    with refused("invalid_transition", "status") as check:
        lessons.apply(env, reviewer(env), lesson["id"], "project", where_for(lesson["id"]), project_scope=scope)
    assert "review" in check.error.hint
    lessons.review(env, reviewer(env), lesson["id"], "reject", "no")
    with refused("invalid_transition", "status") as check:
        lessons.apply(env, reviewer(env), lesson["id"], "project", where_for(lesson["id"]), project_scope=scope)
    assert "reopen" in check.error.hint


def test_apply_where_must_carry_the_tag(env, scope):
    lesson_id = approved(env, scope)
    for where in ("roles/executor.md", f"roles/executor.md [lesson #{lesson_id + 1}]", " "):
        with refused("invalid_value", "where"):
            lessons.apply(env, reviewer(env), lesson_id, "project", where, project_scope=scope)


def test_apply_records_site_and_event(env, scope):
    lesson_id = approved(env, scope)
    result = lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    assert result["site"] == {
        "site": "project",
        "project": "demo-app",
        "state": "applied",
        "where_": where_for(lesson_id),
        "reason": None,
        "decided_conversation": "conv-review",
        "decided_at": result["site"]["decided_at"],
    }
    assert result["lesson"]["status"] == "approved"


def test_apply_site_arguments(env, scope):
    lesson_id = approved(env, scope)
    with refused("invalid_value", "site"):
        lessons.apply(env, reviewer(env), lesson_id, "everywhere", where_for(lesson_id))
    with refused("invalid_value", "project"):
        lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id))
    with refused("lesson_not_found"):
        lessons.apply(env, reviewer(env), 999, "global", where_for(999))


def test_project_lesson_applies_only_at_its_origin_project(env, scope, tmp_path):
    lesson_id = approved(env, scope, generality="project")
    other = other_project(env, tmp_path)
    with refused("invalid_value", "site"):
        lessons.apply(env, reviewer(env), lesson_id, "global", where_for(lesson_id))
    with refused("invalid_value", "project"):
        lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=other)
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    particular = approved(
        env, scope, "blip", generality="particular", particular_justification="one case", severity="critical"
    )
    with refused("invalid_value", "site"):
        lessons.apply(env, reviewer(env), particular, "global", where_for(particular))


def test_agnostic_lesson_applies_anywhere(env, scope, tmp_path):
    lesson_id = approved(env, scope)
    other = other_project(env, tmp_path)
    lessons.apply(env, reviewer(env), lesson_id, "global", where_for(lesson_id))
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=other)
    assert len(lessons.show(env, lesson_id)["sites"]) == 2


def test_apply_site_checks_the_sites_writer_roles(env, scope):
    lesson_id = approved(env, scope)
    projects.set_writer_roles(env, None, ["steward"])
    with refused("not_a_writer"):
        lessons.apply(env, reviewer(env), lesson_id, "global", where_for(lesson_id))
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)


def test_reapply_updates_where_and_restores_retired(env, scope):
    lesson_id = approved(env, scope)
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id, "a.md"), project_scope=scope)
    updated = lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id, "b.md"), project_scope=scope)
    assert updated["site"]["where_"] == where_for(lesson_id, "b.md")
    lessons.retire(env, reviewer(env), lesson_id, "project", "obsolete", project_scope=scope)
    restored = lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id, "c.md"), project_scope=scope)
    assert restored["site"]["state"] == "applied"
    assert restored["site"]["reason"] is None
    assert len(lessons.show(env, lesson_id)["sites"]) == 1
    states = [(e["action"], e["from_state"], e["to_state"]) for e in events(env, lesson_id)[2:]]
    assert states == [
        ("applied", None, "applied"),
        ("applied", "applied", "applied"),
        ("retired", "applied", "retired"),
        ("applied", "retired", "applied"),
    ]


def test_apply_on_declined_site_points_to_reopen_site(env, scope):
    lesson_id = approved(env, scope)
    env.execute(
        "INSERT INTO lesson_sites (lesson_id, site, project_id, state, decided_conversation, decided_at) "
        "VALUES (?, 'project', ?, 'declined', 'c', '2026-01-01T00:00:00Z')",
        (lesson_id, scope.project_id),
    )
    with refused("invalid_transition", "state") as check:
        lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    assert "reopen-site" in check.error.hint


def test_retire_touches_one_site_only(env, scope):
    lesson_id = approved(env, scope)
    lessons.apply(env, reviewer(env), lesson_id, "global", where_for(lesson_id, "~/skill.md"))
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    result = lessons.retire(env, reviewer(env), lesson_id, "project", "replaced by a hook", project_scope=scope)
    assert result["site"]["state"] == "retired"
    assert result["site"]["reason"] == "replaced by a hook"
    states = {s["site"]: s["state"] for s in lessons.show(env, lesson_id)["sites"]}
    assert states == {"global": "applied", "project": "retired"}


def test_retire_refusals(env, scope):
    lesson_id = approved(env, scope)
    with refused("invalid_transition", "state"):
        lessons.retire(env, reviewer(env), lesson_id, "project", "r", project_scope=scope)
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    with refused("invalid_value", "reason"):
        lessons.retire(env, reviewer(env), lesson_id, "project", " ", project_scope=scope)
    lessons.retire(env, reviewer(env), lesson_id, "project", "r", project_scope=scope)
    with refused("invalid_transition", "state"):
        lessons.retire(env, reviewer(env), lesson_id, "project", "again", project_scope=scope)
    with refused("not_a_writer"):
        lessons.retire(env, actor(env, role="executor"), lesson_id, "project", "r", project_scope=scope)


# --- events --------------------------------------------------------------------------


def last_events(conn, count):
    return [dict(row) for row in conn.execute("SELECT * FROM lesson_events ORDER BY id DESC LIMIT ?", (count,))][::-1]


def test_every_write_writes_exactly_one_event(env, scope):
    me, other = actor(env), reviewer(env)

    def one(call, **expected):
        before = env.execute("SELECT COUNT(*) FROM lesson_events").fetchone()[0]
        result = call()
        after = env.execute("SELECT COUNT(*) FROM lesson_events").fetchone()[0]
        assert after == before + 1
        event = last_events(env, 1)[0]
        for key, value in expected.items():
            assert event[key] == value, (key, event)
        assert event["at"]
        return result

    created = one(
        lambda: lessons.add(env, scope, me, body()), action="created", from_state=None, to_state="pending",
        site=None, site_project_id=None, actor_role="planner", actor_agent="claude", conversation="conv-1",
    )["lesson"]
    lid = created["id"]
    one(lambda: lessons.repeat(env, me, lid, "again"), action="repeated", from_state="pending", to_state="pending", site=None)
    one(lambda: lessons.modify(env, me, lid, body()), action="modified", from_state="pending", to_state="pending", site=None)
    one(lambda: lessons.review(env, other, lid, "postpone", "later"), action="reviewed", from_state="pending", to_state="postponed", site=None)
    one(lambda: lessons.reopen(env, other, lid, "now"), action="reopened", from_state="postponed", to_state="pending", site=None)
    one(lambda: lessons.review(env, other, lid, "approve", "ok"), action="reviewed", from_state="pending", to_state="approved", site=None, conversation="conv-review")
    one(
        lambda: lessons.apply(env, other, lid, "project", where_for(lid), project_scope=scope),
        action="applied", from_state=None, to_state="applied", site="project", site_project_id=scope.project_id,
    )
    one(
        lambda: lessons.apply(env, other, lid, "global", where_for(lid)),
        action="applied", from_state=None, to_state="applied", site="global", site_project_id=None,
    )
    one(
        lambda: lessons.retire(env, other, lid, "project", "done", project_scope=scope),
        action="retired", from_state="applied", to_state="retired", site="project", site_project_id=scope.project_id,
    )
    second = record_lesson(env, scope, "blip")
    one(lambda: lessons.review(env, other, second["id"], "duplicate", "same", of=lid), action="reviewed", to_state="duplicate")
    one(lambda: lessons.reopen(env, other, second["id"], "no"), action="reopened", from_state="duplicate", to_state="pending")


def test_failed_writes_leave_no_event(env, scope):
    lesson = record_lesson(env, scope)
    count = env.execute("SELECT COUNT(*) FROM lesson_events").fetchone()[0]
    with refused("self_review"):
        lessons.review(env, actor(env), lesson["id"], "approve", "ok")
    with refused("not_a_writer"):
        lessons.repeat(env, actor(env, role="executor"), lesson["id"], "again")
    assert env.execute("SELECT COUNT(*) FROM lesson_events").fetchone()[0] == count
    assert lessons.show(env, lesson["id"])["lesson"]["occurrences"] == 1


# --- duplicate classes ------------------------------------------------------------------


def test_pending_lesson_blocks_with_details(env, scope):
    first = record_lesson(env, scope, "zork")
    with refused("duplicate_lesson", "general_rule") as check:
        lessons.add(env, scope, actor(env), body("zork", what_happened="something else entirely"))
    details = check.error.details
    assert details["id"] == first["id"]
    assert details["status"] == "pending"
    assert details["general_rule"] == first["general_rule"]
    assert details["test"] in ("full", "rule")
    assert details["shared"] == sorted(f"zork{s}" for s in SUFFIXES)
    assert f"chanchi lesson repeat {first['id']}" in check.error.hint
    assert env.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 1


def test_approved_without_sites_blocks_but_fully_retired_only_warns(env, scope):
    lesson_id = approved(env, scope, "zork")
    with refused("duplicate_lesson"):
        lessons.add(env, scope, actor(env), body("zork"))
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    with refused("duplicate_lesson"):
        lessons.add(env, scope, actor(env), body("zork"))
    lessons.retire(env, reviewer(env), lesson_id, "project", "obsolete", project_scope=scope)
    result = lessons.add(env, scope, actor(env), body("zork"))
    assert [w["kind"] for w in result["warnings"]] == ["retired"]
    assert result["warnings"][0]["id"] == lesson_id
    assert result["warnings"][0]["general_rule"] == text("zork")
    assert result["warnings"][0]["shared"]


def test_approved_with_a_retired_and_an_applied_site_still_blocks(env, scope):
    lesson_id = approved(env, scope, "zork")
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    lessons.apply(env, reviewer(env), lesson_id, "global", where_for(lesson_id))
    lessons.retire(env, reviewer(env), lesson_id, "project", "r", project_scope=scope)
    with refused("duplicate_lesson"):
        lessons.add(env, scope, actor(env), body("zork"))


def test_rejected_and_duplicate_lessons_only_warn(env, scope):
    first = record_lesson(env, scope, "zork")
    lessons.review(env, reviewer(env), first["id"], "reject", "no")
    second = lessons.add(env, scope, actor(env), body("zork"))
    assert [w["kind"] for w in second["warnings"]] == ["rejected"]
    third_id = second["lesson"]["id"]
    fourth = record_lesson(env, scope, "blip")
    lessons.review(env, reviewer(env), fourth["id"], "duplicate", "same", of=third_id)
    fifth = lessons.add(env, scope, actor(env), body("blip"))
    assert [w["kind"] for w in fifth["warnings"]] == ["duplicate"]


def test_project_lesson_of_another_project_warns_possibly_agnostic(env, scope, tmp_path):
    other = other_project(env, tmp_path)
    mine = lessons.add(env, other, actor(env), body("zork", generality="project"))["lesson"]
    result = lessons.add(env, scope, actor(env), body("zork"))
    assert [(w["id"], w["kind"]) for w in result["warnings"]] == [(mine["id"], "possibly_agnostic")]
    # a particular lesson of another project is ignored
    particular = lessons.add(
        env, other, actor(env),
        body("blip", generality="particular", severity="high", particular_justification="one case"),
    )["lesson"]
    assert particular["id"]
    assert lessons.add(env, scope, actor(env), body("blip"))["warnings"] == []


def test_agnostic_lesson_of_another_project_is_in_scope_and_blocks(env, scope, tmp_path):
    other = other_project(env, tmp_path)
    lessons.add(env, other, actor(env), body("zork"))
    with refused("duplicate_lesson"):
        lessons.add(env, scope, actor(env), body("zork"))
    with refused("duplicate_lesson"):
        lessons.add(env, projects.Scope(None, None), actor(env), body("zork"))


def test_same_text_in_a_project_scope_does_not_block_a_project_lesson_elsewhere(env, scope, tmp_path):
    other = other_project(env, tmp_path)
    lessons.add(env, other, actor(env), body("zork", generality="project"))
    mine = lessons.add(env, scope, actor(env), body("zork", generality="project"))
    assert [w["kind"] for w in mine["warnings"]] == ["possibly_agnostic"]


def test_warnings_are_limited_to_five(env, scope, tmp_path):
    other = other_project(env, tmp_path)
    for index in range(7):
        lessons.add(
            env, other, actor(env), body("zork", generality="project"), force_new=True
        )
    result = lessons.add(env, scope, actor(env), body("zork"))
    assert len(result["warnings"]) == 5


def test_force_new_records_the_match_in_the_event(env, scope):
    first = record_lesson(env, scope, "zork")
    forced = lessons.add(env, scope, actor(env), body("zork"), force_new=True)["lesson"]
    assert forced["id"] != first["id"]
    event = events(env, forced["id"])[-1]
    assert event["action"] == "force_new"
    assert event["from_state"] is None and event["to_state"] == "pending"
    assert event["note"].startswith(f"matched=#{first['id']} coverage=")
    assert "shared=6" in event["note"]
    # force-new with no match is an ordinary creation
    plain = lessons.add(env, scope, actor(env), body("blip"), force_new=True)["lesson"]
    assert events(env, plain["id"])[-1]["action"] == "created"


# --- reads -------------------------------------------------------------------------------


def test_list_reports_scope_filters_and_site_counts(env, scope, tmp_path):
    other = other_project(env, tmp_path)
    mine = record_lesson(env, scope, "zork")
    lessons.add(env, other, actor(env), body("blip", generality="project"))
    lessons.add(env, projects.Scope(None, None), actor(env), body("quux", target_kind="skill"))
    listed = lessons.list_lessons(env, scope)
    assert listed["scope"] == "demo-app"
    assert [row["id"] for row in listed["lessons"]] == [mine["id"]]
    row = listed["lessons"][0]
    assert row["origin"] == "demo-app"
    assert row["sites"] == {"applied": 0, "declined": 0, "not_applicable": 0, "retired": 0}
    assert set(row) == {
        "id", "status", "generality", "severity", "occurrences", "target_kind", "target",
        "general_rule", "origin", "sites",
    }
    assert lessons.list_lessons(env, projects.Scope(None, None))["scope"] == "global"
    everything = lessons.list_lessons(env, None)
    assert everything["scope"] == "all"
    assert len(everything["lessons"]) == 3
    assert [r["origin"] for r in lessons.list_lessons(env, None, target_kind="skill")["lessons"]] == ["global"]
    assert len(lessons.list_lessons(env, None, generality="project")["lessons"]) == 1
    assert lessons.list_lessons(env, None, status="approved")["lessons"] == []
    assert len(lessons.list_lessons(env, None, limit=2)["lessons"]) == 2
    with refused("invalid_value", "status"):
        lessons.list_lessons(env, None, status="bogus")


def test_show_returns_everything_and_unknown_lesson_fails(env, scope):
    lesson_id = approved(env, scope)
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    shown = lessons.show(env, lesson_id)
    assert set(shown) == {"lesson", "sites", "replaces", "incidents", "events"}
    assert [e["action"] for e in shown["events"]] == ["created", "reviewed", "applied"]
    assert shown["sites"][0]["project"] == "demo-app"
    with refused("lesson_not_found", "id"):
        lessons.show(env, 999)


def test_similar_searches_every_scope(env, scope, tmp_path):
    other = other_project(env, tmp_path)
    mine = lessons.add(env, other, actor(env), body("zork", generality="project"))["lesson"]
    result = lessons.similar(env, text("zork"))
    assert result["scope"] == "all"
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["id"] == mine["id"]
    assert (match["status"], match["generality"], match["origin"]) == ("pending", "project", "other-app")
    assert match["coverage"] == 1.0
    assert match["shared"] == 6
    assert lessons.similar(env, text("nothing"))["matches"] == []
    with refused("invalid_value", "text"):
        lessons.similar(env, " ")


def test_summary_counts_and_force_new_rate(env, scope):
    empty = lessons.summary(env, scope)
    assert empty["scope"] == "demo-app"
    assert empty["force_new_rate"] is None
    assert empty["by_status"] == {"pending": 0, "approved": 0, "rejected": 0, "postponed": 0, "duplicate": 0}
    lesson_id = approved(env, scope, "zork")
    record_lesson(env, scope, "blip", generality="project")
    lessons.add(env, scope, actor(env), body("zork"), force_new=True)
    lessons.apply(env, reviewer(env), lesson_id, "project", where_for(lesson_id), project_scope=scope)
    lessons.apply(env, reviewer(env), lesson_id, "global", where_for(lesson_id))
    result = lessons.summary(env, scope)
    assert result["by_status"]["approved"] == 1
    assert result["by_status"]["pending"] == 2
    assert result["by_generality"] == {"agnostic": 2, "project": 1, "particular": 0}
    assert result["applied_sites"] == {"demo-app": 1, "global": 1}
    assert result["force_new_rate"] == pytest.approx(1 / 3)
    assert lessons.summary(env, None)["scope"] == "all"
    glob = lessons.summary(env, projects.Scope(None, None))
    assert glob["scope"] == "global"
    assert glob["by_status"]["pending"] == 0


def test_export_order_limit_since_and_filters(env, scope):
    plan = [
        # tag, generality, severity, occurrences
        ("t1", "project", "critical", 1),
        ("t2", "agnostic", "low", 1),
        ("t3", "agnostic", "critical", 1),
        ("t4", "agnostic", "critical", 3),
        ("t5", "agnostic", "high", 1),
        ("t6", "project", "low", 1),
    ]
    ids = {}
    for tag, generality, severity, occurrences in plan:
        lesson = record_lesson(env, scope, tag, generality=generality, severity=severity)
        ids[tag] = lesson["id"]
        for _ in range(occurrences - 1):
            lessons.repeat(env, actor(env), lesson["id"], "again")
    order = [row["id"] for row in lessons.export(env, scope)["lessons"]]
    assert order == [ids[t] for t in ("t4", "t3", "t5", "t2", "t1", "t6")]
    only_project = lessons.export(env, scope, generality="project")["lessons"]
    assert [row["id"] for row in only_project] == [ids["t1"], ids["t6"]]
    assert len(lessons.export(env, scope, limit=2)["lessons"]) == 2
    lessons.review(env, reviewer(env), ids["t4"], "approve", "ok")
    default_status = [row["id"] for row in lessons.export(env, scope)["lessons"]]
    assert ids["t4"] not in default_status
    approved_only = lessons.export(env, scope, status=("approved",))["lessons"]
    assert [row["id"] for row in approved_only] == [ids["t4"]]
    assert len(lessons.export(env, scope, status=None)["lessons"]) == 6
    env.execute("UPDATE lessons SET created_at = '2020-01-01T00:00:00Z' WHERE id = ?", (ids["t1"],))
    since = [row["id"] for row in lessons.export(env, scope, since="2021-01-01")["lessons"]]
    assert ids["t1"] not in since and ids["t2"] in since
    with refused("invalid_value", "since"):
        lessons.export(env, scope, since="yesterday")


def test_export_default_limit_is_twenty(env, scope):
    for index in range(22):
        record_lesson(env, scope, f"w{index:02d}x")
    result = lessons.export(env, scope)
    assert len(result["lessons"]) == 20
    assert result["scope"] == "demo-app"
    assert len(lessons.export(env, scope, limit=25)["lessons"]) == 22


def test_export_markdown_has_one_heading_per_lesson(env, scope):
    ids = change_with_incidents(env, "c1")
    first = record_lesson(env, scope, "zork", severity="critical", change="c1", session="S1", incidents=ids, tags="a,b")
    second = record_lesson(env, scope, "blip", generality="project", severity="low")
    lessons.review(env, reviewer(env), second["id"], "approve", "ok")
    lessons.apply(env, reviewer(env), second["id"], "project", where_for(second["id"]), project_scope=scope)
    rows = lessons.export(env, scope, status=None)["lessons"]
    markdown = lessons.export_markdown(rows)
    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings == [
        f"## #{first['id']} · agnostic · critical · ×1",
        f"## #{second['id']} · project · low · ×1",
    ]
    assert "- **general_rule:** " + text("zork") in markdown
    assert "- **tags:** a, b" in markdown
    assert "**incident #" in markdown
    assert "**site demo-app:** applied" in markdown
    assert "[lesson #" in markdown
    assert lessons.export_markdown([]).strip() == "_No lessons._"


def test_read_commands_need_no_writer_or_registered_project(env, scope, tmp_path, monkeypatch):
    record_lesson(env, scope)
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert len(lessons.list_lessons(env, None)["lessons"]) == 1
    assert lessons.show(env, 1)["lesson"]["id"] == 1
    assert lessons.summary(env, None)["scope"] == "all"
    assert len(lessons.export(env, None)["lessons"]) == 1


def test_lessons_module_does_not_import_subprocess():
    import ast
    from pathlib import Path

    source = Path(lessons.__file__).read_text(encoding="utf-8")
    imported = {
        alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for alias in node.names
    }
    assert "subprocess" not in imported
