import pytest

from chanchi import taxonomy as tx
from chanchi.errors import EXIT_INTERNAL, EXIT_VALIDATION, ChanchiError
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


def test_timeutil_roundtrip_and_since():
    ts = utc_now()
    assert parse(ts).strftime("%Y-%m-%dT%H:%M:%SZ") == ts
    assert since_to_iso("2026-09-01") == "2026-09-01T00:00:00Z"
    with pytest.raises(ChanchiError) as info:
        since_to_iso("yesterday")
    assert info.value.field == "since"


def test_since_to_iso_normalises_unpadded_dates():
    assert since_to_iso("2026-9-1") == "2026-09-01T00:00:00Z"
