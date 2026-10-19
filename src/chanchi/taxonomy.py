"""Every closed set and every scoring weight. Pure data plus validation helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from chanchi.errors import ChanchiError

AGENTS = ("claude", "agy", "opencode")
PLANNER_ONLY_AGENTS = ("human",)
ALL_AGENTS = AGENTS + PLANNER_ONLY_AGENTS
LAUNCH_EFFORTS = ("low", "medium", "high", "xhigh", "max")
EFFORTS = LAUNCH_EFFORTS + ("unknown",)
COST_TIERS = (1, 2, 3)
CHANGE_KINDS = ("openspec", "adhoc")
COMPLEXITIES = ("low", "medium", "high")
REPORTED_STATUSES = ("COMPLETE", "STOPPED", "BLOCKED")
VERDICTS = ("accepted", "accepted_with_fixes", "rejected")
RETRY_REASONS = ("executor_failure", "plan_fix", "human_change", "env")
NON_EXECUTOR_RETRY_REASONS = ("plan_fix", "human_change", "env")
SEVERITIES = ("low", "medium", "high", "blocking")
DETECTED_BY = ("executor_stop", "planner_audit", "human", "post_merge")
ROLES = ("planner", "executor", "human", "none")
HALLUCINATION_ROLES = ("planner", "executor")
TASK_TYPE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

COMPLEXITY_CRITERIA = {
    "low": "one layer, <= 3 files, no domain ambiguity, mechanical",
    "medium": "2 layers or 4-10 files, or one non-trivial domain rule",
    "high": ">= 3 layers, > 10 files, cross-cutting concerns (sync, migrations, concurrency), "
    "or meaningful domain ambiguity",
}

# Seed rows for the task_types table. Migration 001 inserts exactly these.
TASK_TYPES = (
    ("ui-component", "Build or change a reusable or screen-level UI component"),
    ("ui-layout-styling", "Layout, spacing, theming or styling with no new behaviour"),
    ("api-endpoint", "Add or change an HTTP/RPC endpoint and its contract"),
    ("business-logic", "Domain rules, use cases or application services"),
    ("db-schema-migration", "Database schema, migrations or persistence mapping"),
    ("refactor", "Restructure code without changing behaviour"),
    ("bugfix", "Fix incorrect behaviour"),
    ("tests", "Write or repair tests, including device or end-to-end passes"),
    ("infra-config-ci", "Build, configuration, CI or tooling"),
    ("docs", "Documentation, spec sync or archive steps"),
    ("integration", "Integrate an external SDK, service or API"),
)

# code -> (fixed role, or None when the caller must pass --role; description)
INCIDENT_CODES = {
    "plan_gap": ("planner", "Something was not defined; the executor had to stop."),
    "plan_delegated_decision": (
        "planner",
        "The plan left a decision open and the executor made it.",
    ),
    "plan_wrong_expectation": (
        "planner",
        "An expected value, path or baseline in the plan was wrong.",
    ),
    "plan_conflict": ("planner", "The plan contradicts existing code, rules or behaviour."),
    "rule_violation": ("executor", "Broke a project rule."),
    "scope_drift": (
        "executor",
        "Touched files/groups outside its session, or edited planning artifacts.",
    ),
    "improvised_decision": ("executor", "Decided on its own where the protocol required a stop."),
    "false_claim": ("executor", "Reported a number or status that did not reproduce on audit."),
    "incomplete_work": ("executor", "Marked work done that was not done or was wrong."),
    "quality_defect": (
        "executor",
        "Bug, weak test or incorrect implementation despite passing verification.",
    ),
    "correct_stop": ("executor", "Positive: stopped at a real gap instead of improvising."),
    "hallucination": (
        None,
        "Invented something that does not exist: file, hook, function, library API, CLI flag, "
        "project rule or domain fact.",
    ),
    "human_unclear_requirement": (
        "human",
        "The requirement was ambiguous or incomplete at its origin.",
    ),
    "human_wrong_requirement": (
        "human",
        "The human asked for the wrong thing and it had to be corrected.",
    ),
    "human_scope_addition": (
        "human",
        "The human added new or unrelated work after the change started.",
    ),
    "env_issue": ("none", "Tooling or environment problem (watchman, emulator, CLI)."),
    "preexisting_defect": ("none", "A bug that already existed in the app."),
}

EXECUTOR_WEIGHTS = {
    "false_claim": 3.0,
    "hallucination": 3.0,
    "improvised_decision": 2.5,
    "scope_drift": 2.0,
    "incomplete_work": 2.0,
    "rule_violation": 1.5,
    "quality_defect": 1.5,
}
PLANNER_WEIGHTS = {
    "hallucination": 3.0,
    "plan_delegated_decision": 2.5,
    "plan_gap": 2.0,
    "plan_conflict": 2.0,
    "plan_wrong_expectation": 1.0,
}
SEVERITY_MULT = {"low": 1, "medium": 2, "high": 3, "blocking": 5}
LATE_DETECTION = ("human", "post_merge")
LATE_DETECTION_MULT = 1.5
VERDICT_BASE = {"accepted": 100.0, "accepted_with_fixes": 70.0, "rejected": 0.0}
CORRECT_STOP_CREDIT = 5.0
PLANNER_DENSITY_FACTOR = 5.0
PLANNER_MIN_TASKS = 10
SMOOTHING_K = 3
DEFAULT_PRIOR = 70.0
CONFIDENCE_LOW_MIN = 3
CONFIDENCE_OK_MIN = 10
RECOMMEND_WINDOW = 5.0
HONESTY_RED_FLAG = 0.2
HONESTY_CODES = ("false_claim", "hallucination")
CLEAN_BLOCKING_SEVERITIES = ("medium", "high", "blocking")


def validate_choice(field: str, value, allowed: Iterable):
    """Return value if it is allowed; otherwise raise an invalid_value error listing the options."""
    allowed = tuple(allowed)
    if value not in allowed:
        raise ChanchiError(
            "invalid_value",
            f"{field} must be one of the listed values, got {value!r}",
            field=field,
            valid_values=allowed,
            hint="run `chanchi taxonomy list` to see every enum",
        )
    return value


def resolve_role(code: str, explicit_role: str | None) -> str:
    """Role of an incident: fixed by its code, except hallucination which needs --role."""
    validate_choice("code", code, INCIDENT_CODES)
    fixed, _ = INCIDENT_CODES[code]
    if fixed is None:
        if explicit_role is None:
            raise ChanchiError(
                "invalid_value",
                f"{code} requires --role to say who hallucinated",
                field="role",
                valid_values=HALLUCINATION_ROLES,
            )
        return validate_choice("role", explicit_role, HALLUCINATION_ROLES)
    if explicit_role is not None:
        raise ChanchiError(
            "invalid_value",
            f"--role is only accepted for hallucination; {code} is always {fixed}",
            field="role",
        )
    return fixed


def confidence(n: int) -> str:
    if n < CONFIDENCE_LOW_MIN:
        return "insufficient"
    if n < CONFIDENCE_OK_MIN:
        return "low"
    return "ok"


def describe() -> dict:
    """Every enum, incident code and weight, for `chanchi taxonomy list`."""
    return {
        "agents": list(AGENTS),
        "planner_only_agents": list(PLANNER_ONLY_AGENTS),
        "efforts": list(EFFORTS),
        "cost_tiers": list(COST_TIERS),
        "change_kinds": list(CHANGE_KINDS),
        "complexities": [
            {"value": value, "criteria": criteria} for value, criteria in COMPLEXITY_CRITERIA.items()
        ],
        "reported_statuses": list(REPORTED_STATUSES),
        "verdicts": list(VERDICTS),
        "retry_reasons": list(RETRY_REASONS),
        "severities": [{"value": s, "multiplier": SEVERITY_MULT[s]} for s in SEVERITIES],
        "detected_by": list(DETECTED_BY),
        "roles": list(ROLES),
        "incident_codes": [
            {
                "code": code,
                "role": role if role is not None else "planner|executor",
                "description": description,
                "executor_weight": EXECUTOR_WEIGHTS.get(code),
                "planner_weight": PLANNER_WEIGHTS.get(code),
            }
            for code, (role, description) in INCIDENT_CODES.items()
        ],
    }
