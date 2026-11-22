import pytest
from helpers import FAMILY_CASES

from chanchi import taxonomy as tx
from chanchi.errors import ERROR_CODES, EXIT_INTERNAL, EXIT_VALIDATION, ChanchiError
from chanchi.timeutil import parse, since_to_iso, utc_now


def test_error_envelope_includes_only_given_fields():
    err = ChanchiError("invalid_value", "bad", field="complexity", valid_values=("low",), hint="h")
    assert err.to_dict() == {
        "ok": False,
        "error": {
            "code": "invalid_value",
            "message": "bad",
            "field": "complexity",
            "valid_values": ["low"],
            "hint": "h",
        },
    }
    assert ChanchiError("duplicate", "x").to_dict() == {
        "ok": False,
        "error": {"code": "duplicate", "message": "x"},
    }


def test_exit_codes():
    assert ChanchiError("invalid_value", "x").exit_code == EXIT_VALIDATION
    assert ChanchiError("internal", "x").exit_code == EXIT_INTERNAL


def test_unknown_error_code_is_a_programming_error():
    with pytest.raises(ValueError):
        ChanchiError("nope", "x")


def test_validate_choice_lists_valid_values():
    assert tx.validate_choice("complexity", "low", tx.COMPLEXITIES) == "low"
    with pytest.raises(ChanchiError) as info:
        tx.validate_choice("complexity", "huge", tx.COMPLEXITIES)
    assert info.value.code == "invalid_value"
    assert info.value.field == "complexity"
    assert info.value.valid_values == ["low", "medium", "high"]


def test_resolve_role_fixed_codes():
    assert tx.resolve_role("plan_gap", None) == "planner"
    assert tx.resolve_role("correct_stop", None) == "executor"
    assert tx.resolve_role("human_scope_addition", None) == "human"
    assert tx.resolve_role("env_issue", None) == "none"


def test_resolve_role_rejects_role_on_fixed_codes():
    with pytest.raises(ChanchiError) as info:
        tx.resolve_role("plan_gap", "executor")
    assert info.value.field == "role"


def test_hallucination_requires_explicit_role():
    with pytest.raises(ChanchiError) as info:
        tx.resolve_role("hallucination", None)
    assert info.value.valid_values == ["planner", "executor"]
    assert tx.resolve_role("hallucination", "planner") == "planner"
    with pytest.raises(ChanchiError):
        tx.resolve_role("hallucination", "human")


def test_unknown_code_is_invalid():
    with pytest.raises(ChanchiError) as info:
        tx.resolve_role("made_up", None)
    assert info.value.field == "code"


def test_confidence_thresholds():
    assert [tx.confidence(n) for n in (0, 2, 3, 9, 10, 50)] == [
        "insufficient",
        "insufficient",
        "low",
        "low",
        "ok",
        "ok",
    ]


def test_weights_only_reference_known_codes():
    assert set(tx.EXECUTOR_WEIGHTS) <= set(tx.INCIDENT_CODES)
    assert set(tx.PLANNER_WEIGHTS) <= set(tx.INCIDENT_CODES)


def test_task_type_codes_are_kebab_case():
    for code, description in tx.TASK_TYPES:
        assert tx.TASK_TYPE_PATTERN.match(code), code
        assert description


def test_describe_lists_every_incident_code():
    described = tx.describe()
    assert [c["code"] for c in described["incident_codes"]] == list(tx.INCIDENT_CODES)
    hallucination = next(c for c in described["incident_codes"] if c["code"] == "hallucination")
    assert hallucination["role"] == "planner|executor"
    assert hallucination["executor_weight"] == 3.0


def test_new_quality_codes_are_executor_codes_with_weights():
    assert tx.INCIDENT_CODES["architecture_violation"][0] == "executor"
    assert tx.INCIDENT_CODES["code_smell"][0] == "executor"
    assert tx.EXECUTOR_WEIGHTS["architecture_violation"] == 2.0
    assert tx.EXECUTOR_WEIGHTS["code_smell"] == 1.0
    assert tx.resolve_role("architecture_violation", None) == "executor"
    assert tx.resolve_role("code_smell", None) == "executor"


def test_describe_lists_new_quality_codes():
    described = {c["code"]: c for c in tx.describe()["incident_codes"]}
    assert described["architecture_violation"]["role"] == "executor"
    assert described["architecture_violation"]["executor_weight"] == 2.0
    assert described["code_smell"]["role"] == "executor"
    assert described["code_smell"]["executor_weight"] == 1.0


# --- dimensions ------------------------------------------------------------


def test_every_executor_weight_code_is_in_exactly_one_dimension():
    seen = [code for codes in tx.DIMENSIONS.values() for code in codes]
    assert sorted(seen) == sorted(tx.EXECUTOR_WEIGHTS)
    assert len(seen) == len(set(seen))
    assert set(tx.DIMENSION_OF) == set(tx.EXECUTOR_WEIGHTS)
    for code in tx.EXECUTOR_WEIGHTS:
        assert tx.DIMENSION_OF[code] in tx.DIMENSIONS


def test_dimension_codes_are_executor_codes():
    for dimension, codes in tx.DIMENSIONS.items():
        for code in codes:
            assert code in tx.INCIDENT_CODES, code
            role = tx.INCIDENT_CODES[code][0]
            assert role not in ("planner", "human"), (dimension, code, role)
            assert tx.resolve_role(code, "executor" if role is None else None) == "executor"


def test_correct_stop_belongs_to_no_dimension():
    assert "correct_stop" not in tx.DIMENSION_OF
    assert "correct_stop" not in [code for codes in tx.DIMENSIONS.values() for code in codes]


def test_describe_lists_every_dimension_in_order():
    described = tx.describe()["dimensions"]
    assert [d["dimension"] for d in described] == [
        "correctness",
        "architecture",
        "clean-code",
        "honesty",
        "discipline",
    ]
    assert described[0]["codes"] == ["quality_defect", "incomplete_work"]
    assert {d["dimension"]: d["codes"] for d in described} == {
        dimension: list(codes) for dimension, codes in tx.DIMENSIONS.items()
    }


def test_timeutil_roundtrip_and_since():
    ts = utc_now()
    assert parse(ts).strftime("%Y-%m-%dT%H:%M:%SZ") == ts
    assert since_to_iso("2026-09-01") == "2026-09-01T00:00:00Z"
    with pytest.raises(ChanchiError) as info:
        since_to_iso("yesterday")
    assert info.value.field == "since"


def test_since_to_iso_normalises_unpadded_dates():
    assert since_to_iso("2026-9-1") == "2026-09-01T00:00:00Z"


# --- lessons ----------------------------------------------------------------


def test_describe_lists_lesson_sets():
    lessons = tx.describe()["lessons"]
    assert lessons == {
        "target_kinds": [
            "role", "skill", "wrapper", "rules-file", "hook", "permission", "workflow", "tool",
        ],
        "generalities": ["agnostic", "project", "particular"],
        "severities": ["critical", "high", "medium", "low"],
        "statuses": ["pending", "approved", "rejected", "postponed", "duplicate"],
        "decisions": ["approve", "reject", "postpone", "duplicate"],
        "reason_codes": ["model_weakness", "covered", "too_costly", "symptom_only"],
        "site_states": ["applied", "declined", "not_applicable", "retired"],
        "locator_kinds": ["path"],
        "default_writer_roles": ["planner"],
    }


def test_lesson_sets_are_tuples_of_unique_strings():
    sets = (
        tx.LESSON_TARGET_KINDS,
        tx.LESSON_GENERALITIES,
        tx.LESSON_SEVERITIES,
        tx.LESSON_STATUSES,
        tx.LESSON_DECISIONS,
        tx.LESSON_REASON_CODES,
        tx.LESSON_SITE_STATES,
        tx.LOCATOR_KINDS,
        tx.DEFAULT_WRITER_ROLES,
    )
    for values in sets:
        assert all(isinstance(v, str) for v in values)
        assert len(values) == len(set(values))


def test_lesson_severity_uses_critical_not_blocking():
    # Lesson severity and incident severity are different scales (design, Vocabulary and states).
    assert "critical" in tx.LESSON_SEVERITIES
    assert "blocking" not in tx.LESSON_SEVERITIES
    assert "blocking" in tx.SEVERITIES


def test_existing_sets_are_unchanged_by_lessons():
    described = tx.describe()
    assert described["agents"] == ["claude", "agy", "opencode"]
    assert described["severities"][-1] == {"value": "blocking", "multiplier": 5}


# --- error envelope details and lesson codes --------------------------------


def test_details_appear_in_envelope_only_when_set():
    with_details = ChanchiError("duplicate_lesson", "x", details={"id": 4})
    assert with_details.to_dict() == {
        "ok": False,
        "error": {"code": "duplicate_lesson", "message": "x", "details": {"id": 4}},
    }
    assert "details" not in ChanchiError("duplicate", "x").to_dict()["error"]


@pytest.mark.parametrize(
    ("code", "kwargs", "expected"),
    [
        (
            "project_not_registered",
            {
                "field": "project",
                "hint": "chanchi project register",
            },
            {"field": "project", "hint": "chanchi project register"},
        ),
        (
            "not_a_writer",
            {
                "field": "as",
                "valid_values": ("planner",),
                "hint": "chanchi project writers <scope> --set ...",
            },
            {"field": "as", "valid_values": ["planner"], "hint": "chanchi project writers <scope> --set ..."},
        ),
        (
            "self_review",
            {
                "field": "conversation",
                "hint": "review it from another conversation",
            },
            {"field": "conversation", "hint": "review it from another conversation"},
        ),
        (
            "duplicate_lesson",
            {
                "field": "general_rule",
                "details": {"id": 4, "status": "approved", "general_rule": "r", "shared": True, "test": "t"},
                "hint": "chanchi lesson repeat 4 --evidence ...",
            },
            {
                "field": "general_rule",
                "details": {"id": 4, "status": "approved", "general_rule": "r", "shared": True, "test": "t"},
                "hint": "chanchi lesson repeat 4 --evidence ...",
            },
        ),
        (
            "invalid_transition",
            {
                "field": "status",
                "valid_values": ("pending", "postponed"),
                "hint": "chanchi lesson reopen 4",
            },
            {
                "field": "status",
                "valid_values": ["pending", "postponed"],
                "hint": "chanchi lesson reopen 4",
            },
        ),
        (
            "lesson_not_found",
            {
                "field": "id",
                "hint": "chanchi lesson list",
            },
            {"field": "id", "hint": "chanchi lesson list"},
        ),
    ],
)
def test_lesson_error_codes_build_the_table_envelope(code, kwargs, expected):
    message = f"{code} message"
    err = ChanchiError(code, message, **kwargs)
    assert err.exit_code == EXIT_VALIDATION
    assert err.to_dict() == {"ok": False, "error": {"code": code, "message": message, **expected}}


def test_new_error_codes_are_registered():
    for code in (
        "project_not_registered",
        "not_a_writer",
        "self_review",
        "duplicate_lesson",
        "invalid_transition",
        "lesson_not_found",
    ):
        assert code in ERROR_CODES
        ChanchiError(code, "x")



@pytest.mark.parametrize("model,expected", FAMILY_CASES)
def test_family_for(model, expected):
    assert tx.family_for(model) == expected


def test_audit_sets_are_listed_and_unchanged_elsewhere():
    assert tx.AUDIT_SUBJECT_KINDS == ("design", "item", "adoption", "replication", "other")
    assert tx.AUDIT_VERDICTS == ("pass", "pass_with_fixes", "fail")
    assert tx.AUDIT_SEVERITIES == ("blocking", "major", "minor")
    assert tx.DISSENT_DECISIONS == ("confirmed", "rejected")
    assert tx.AUDIT_OUTCOMES == ("accepted", "fix", "rework", "escalated")
    assert tx.AUDIT_ESCALATIONS == ("quorum", "round_cap")
    assert tx.SEAT_STATUSES == ("assigned", "voted", "unavailable")
    audits = tx.describe()["audits"]
    assert audits == {
        "subject_kinds": list(tx.AUDIT_SUBJECT_KINDS),
        "verdicts": list(tx.AUDIT_VERDICTS),
        "severities": list(tx.AUDIT_SEVERITIES),
        "dissent_decisions": list(tx.DISSENT_DECISIONS),
        "outcomes": list(tx.AUDIT_OUTCOMES),
        "escalations": list(tx.AUDIT_ESCALATIONS),
        "seat_statuses": list(tx.SEAT_STATUSES),
    }
