# chanchi Model Auditor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `chanchi`, a local, agent-first CLI (Python stdlib + SQLite) that records planner/executor sessions and audit incidents, turns them into scores, and recommends an `(agent, model, effort)` per task type and complexity — plus the two skills that teach agents to use it.

**Architecture:** Small single-purpose modules under `src/chanchi/` (taxonomy → modelspec → db → projects/catalog → record → scoring → skills_link → cli). The write side (`record`) and read side (`scoring`) never mix; scores are computed at query time from raw rows. A committed template SQLite database seeds the operational database, and every migration updates both.

**Tech Stack:** Python ≥ 3.11 standard library only at runtime (`sqlite3`, `argparse`, `json`, `importlib.resources`, `subprocess`), `hatchling` build backend, `uv` for environment and install, `pytest` (dev only).

**Spec:** `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md` — read it before starting any task.

## Global Constraints

- All code, comments, docs, skills, test names and commit messages are in **English**.
- Runtime dependencies: **none** (`dependencies = []`). Only dev dependency: `pytest>=8`.
- `requires-python = ">=3.11"`. Do not use syntax newer than 3.11.
- Every source file starts with `from __future__ import annotations` (except `__init__.py`, `__main__.py` and SQL/Markdown files).
- Run tests with `uv run pytest` from the repository root. Never install anything globally except in Task 11, Step 6.
- Tests must never touch the real operational database: they set `CHANCHI_DB` to a path under `tmp_path` (the `db_env` fixture does this).
- Never edit `src/chanchi/data/template.db` by hand; it is (re)generated only by `db.migrate_template()`.
- Do not create files that are not listed in a task. Do not rename any function, argument, field, error code or JSON key defined in this plan.
- Commit messages use Conventional Commits and end with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- If a step's expected output does not match, STOP and report the exact command and output. Do not improvise a fix to the plan.

## Execution model (for the orchestrating session)

| Task | Recommended executor model | Why |
|---|---|---|
| 1. Scaffold, errors, timeutil, taxonomy | haiku | verbatim transcription of data and helpers |
| 2. modelspec | haiku | tiny pure function with given tests |
| 3. db, migration, template | sonnet | transactions, bootstrap and template integrity |
| 4. projects and catalog | sonnet | validation rules with several error paths |
| 5. record | sonnet | most validation logic in the project |
| 6. scoring: scores, records, stats | sonnet | numeric correctness |
| 7. scoring: recommend, show, explain | sonnet | ranking and fallback logic |
| 8. skills_link | sonnet | filesystem edge cases |
| 9. render and cli | sonnet | large surface, wiring every unit |
| 10. skills content | sonnet | technical writing that must match the CLI exactly |
| 11. scenario, integration, README, install | sonnet | end-to-end verification |

Tasks run strictly in order; each depends on all previous ones.

## File map

```
pyproject.toml                         Task 1
README.md                              Task 11
src/chanchi/__init__.py                Task 1
src/chanchi/__main__.py                Task 9
src/chanchi/errors.py                  Task 1
src/chanchi/timeutil.py                Task 1
src/chanchi/taxonomy.py                Task 1
src/chanchi/modelspec.py               Task 2
src/chanchi/migrations/001_init.sql    Task 3
src/chanchi/db.py                      Task 3
src/chanchi/data/template.db           Task 3 (generated)
src/chanchi/projects.py                Task 4
src/chanchi/catalog.py                 Task 4
src/chanchi/record.py                  Task 5
src/chanchi/scoring.py                 Tasks 6-7
src/chanchi/skills_link.py             Task 8
src/chanchi/render.py                  Task 9
src/chanchi/cli.py                     Task 9
skills/chanchi-model-selection/SKILL.md            Task 10
skills/chanchi-session-audit/SKILL.md              Task 10
skills/chanchi-session-audit/references/rubric.md  Task 10
tests/conftest.py                      Tasks 3, 4 (extended)
tests/helpers.py                       Task 6
tests/test_taxonomy.py                 Task 1
tests/test_modelspec.py                Task 2
tests/test_db.py                       Task 3
tests/test_projects.py                 Task 4
tests/test_catalog.py                  Task 4
tests/test_record.py                   Task 5
tests/test_scoring.py                  Tasks 6-7
tests/test_skills_link.py              Task 8
tests/test_cli.py                      Task 9
tests/test_skills_content.py           Task 10
tests/test_scenario.py                 Task 11
tests/test_cli_integration.py          Task 11
```

---

### Task 1: Scaffold, errors, timeutil and taxonomy

**Recommended model:** haiku

**Files:**
- Create: `pyproject.toml`, `src/chanchi/__init__.py`, `src/chanchi/errors.py`, `src/chanchi/timeutil.py`, `src/chanchi/taxonomy.py`
- Test: `tests/test_taxonomy.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `chanchi.__version__: str = "0.1.0"`
  - `errors.ChanchiError(code: str, message: str, *, field: str|None=None, valid_values: Iterable|None=None, hint: str|None=None)` with attributes `code, message, field, valid_values, hint`, property `exit_code -> int`, method `to_dict() -> dict`; constants `EXIT_OK=0`, `EXIT_INTERNAL=1`, `EXIT_VALIDATION=2`, `ERROR_CODES`.
  - `timeutil.utc_now() -> str`, `timeutil.parse(ts: str) -> datetime`, `timeutil.since_to_iso(day: str) -> str`, `timeutil.FORMAT`.
  - `taxonomy`: every constant below, plus `validate_choice(field, value, allowed) -> value`, `resolve_role(code, explicit_role) -> str`, `confidence(n: int) -> str`, `describe() -> dict`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "chanchi"
version = "0.1.0"
description = "Local auditor that turns planner/executor agent audits into model ratings."
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
chanchi = "chanchi.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/chanchi"]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Also create an empty placeholder `README.md` containing only the line `# chanchi` (hatchling requires the file to exist; Task 11 writes the real content).

- [ ] **Step 2: Create `src/chanchi/__init__.py`**

```python
"""chanchi: turn planner/executor agent audits into model ratings."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `src/chanchi/errors.py`**

```python
"""Structured errors for agent callers: every failure names a code, a field and a fix."""

from __future__ import annotations

from collections.abc import Iterable

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_VALIDATION = 2

ERROR_CODES = frozenset(
    {
        "invalid_value",
        "unknown_model",
        "unknown_change",
        "unknown_session",
        "duplicate",
        "missing_prerequisite",
        "project_not_detected",
        "link_conflict",
        "schema_too_new",
        "internal",
    }
)


class ChanchiError(Exception):
    """A failure the caller can act on. Rendered as the JSON error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
        valid_values: Iterable | None = None,
        hint: str | None = None,
    ) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.valid_values = list(valid_values) if valid_values is not None else None
        self.hint = hint

    @property
    def exit_code(self) -> int:
        return EXIT_INTERNAL if self.code == "internal" else EXIT_VALIDATION

    def to_dict(self) -> dict:
        error: dict = {"code": self.code, "message": self.message}
        if self.field is not None:
            error["field"] = self.field
        if self.valid_values is not None:
            error["valid_values"] = self.valid_values
        if self.hint is not None:
            error["hint"] = self.hint
        return {"ok": False, "error": error}
```

- [ ] **Step 4: Create `src/chanchi/timeutil.py`**

```python
"""UTC timestamps stored as ISO-8601 text: YYYY-MM-DDTHH:MM:SSZ."""

from __future__ import annotations

from datetime import datetime, timezone

from chanchi.errors import ChanchiError

FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(FORMAT)


def parse(ts: str) -> datetime:
    return datetime.strptime(ts, FORMAT).replace(tzinfo=timezone.utc)


def since_to_iso(day: str) -> str:
    """Turn a --since YYYY-MM-DD value into the start-of-day timestamp."""
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        raise ChanchiError(
            "invalid_value", f"{day!r} is not a date", field="since", hint="use YYYY-MM-DD"
        ) from None
    return f"{day}T00:00:00Z"
```

- [ ] **Step 5: Create `src/chanchi/taxonomy.py`**

```python
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
```

- [ ] **Step 6: Write the tests `tests/test_taxonomy.py`**

```python
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
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_taxonomy.py -v`
Expected: 13 passed. (The first `uv run` creates `.venv`, installs the project in editable mode and the `dev` group.)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml README.md uv.lock src/chanchi tests/test_taxonomy.py
git commit -m "feat: scaffold package with errors, timeutil and taxonomy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Model spec parsing

**Recommended model:** haiku

**Files:**
- Create: `src/chanchi/modelspec.py`
- Test: `tests/test_modelspec.py`

**Interfaces:**
- Consumes: `taxonomy.ALL_AGENTS`, `taxonomy.EFFORTS`, `taxonomy.validate_choice`, `errors.ChanchiError`.
- Produces: `ModelSpec(agent: str, model: str, effort: str | None)` (frozen dataclass), `parse(spec: str, *, field: str = "spec") -> ModelSpec`, `format_spec(agent: str, model: str, effort: str | None) -> str`.

- [ ] **Step 1: Write the failing tests `tests/test_modelspec.py`**

```python
import pytest

from chanchi.errors import ChanchiError
from chanchi.modelspec import ModelSpec, format_spec, parse


def test_agent_model_effort():
    assert parse("claude:sonnet:medium") == ModelSpec("claude", "sonnet", "medium")


def test_effort_is_optional():
    assert parse("claude:sonnet") == ModelSpec("claude", "sonnet", None)


def test_model_containing_effort_word_without_colon():
    assert parse("agy:gemini-3.8-flash-high:high") == ModelSpec("agy", "gemini-3.8-flash-high", "high")
    assert parse("agy:gemini-3.8-flash-high") == ModelSpec("agy", "gemini-3.8-flash-high", None)


def test_colon_suffix_that_is_not_an_effort_stays_in_the_model():
    assert parse("opencode:openrouter/qwen/qwen3-coder:free") == ModelSpec(
        "opencode", "openrouter/qwen/qwen3-coder:free", None
    )
    assert parse("opencode:openrouter/qwen/qwen3-coder:free:high") == ModelSpec(
        "opencode", "openrouter/qwen/qwen3-coder:free", "high"
    )


def test_unknown_effort_is_accepted():
    assert parse("claude:opus:unknown") == ModelSpec("claude", "opus", "unknown")


def test_human_shorthand():
    assert parse("human") == ModelSpec("human", "human", None)
    assert parse("human:human") == ModelSpec("human", "human", None)


def test_whitespace_is_trimmed():
    assert parse("  claude:haiku  ") == ModelSpec("claude", "haiku", None)


def test_missing_colon_is_invalid():
    with pytest.raises(ChanchiError) as info:
        parse("sonnet", field="executor")
    assert info.value.code == "invalid_value"
    assert info.value.field == "executor"


def test_unknown_agent_lists_agents():
    with pytest.raises(ChanchiError) as info:
        parse("cursor:gpt")
    assert info.value.valid_values == ["claude", "agy", "opencode", "human"]


def test_empty_model_is_invalid():
    with pytest.raises(ChanchiError):
        parse("claude:")
    with pytest.raises(ChanchiError):
        parse("claude::high")


def test_format_spec():
    assert format_spec("claude", "sonnet", "medium") == "claude:sonnet:medium"
    assert format_spec("claude", "sonnet", None) == "claude:sonnet"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_modelspec.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chanchi.modelspec'`.

- [ ] **Step 3: Implement `src/chanchi/modelspec.py`**

```python
"""Parse and format model specs: agent:model[:effort]."""

from __future__ import annotations

from dataclasses import dataclass

from chanchi import taxonomy
from chanchi.errors import ChanchiError

SPEC_HINT = "use agent:model[:effort], e.g. claude:sonnet:medium"


@dataclass(frozen=True)
class ModelSpec:
    agent: str
    model: str
    effort: str | None


def parse(spec: str, *, field: str = "spec") -> ModelSpec:
    """The agent is before the first ':'; the last ':'-segment is an effort only if it is a valid one."""
    text = spec.strip()
    if text == "human":
        return ModelSpec("human", "human", None)
    if ":" not in text:
        raise ChanchiError(
            "invalid_value", f"{text!r} is not a model spec", field=field, hint=SPEC_HINT
        )
    agent, rest = text.split(":", 1)
    taxonomy.validate_choice(field, agent, taxonomy.ALL_AGENTS)
    effort = None
    if ":" in rest:
        head, last = rest.rsplit(":", 1)
        if last in taxonomy.EFFORTS:
            rest, effort = head, last
    if not rest:
        raise ChanchiError(
            "invalid_value", f"{text!r} has an empty model name", field=field, hint=SPEC_HINT
        )
    return ModelSpec(agent, rest, effort)


def format_spec(agent: str, model: str, effort: str | None) -> str:
    return f"{agent}:{model}" + (f":{effort}" if effort else "")
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_modelspec.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chanchi/modelspec.py tests/test_modelspec.py
git commit -m "feat: parse agent:model:effort model specs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Database layer, initial migration and template database

**Recommended model:** sonnet

**Files:**
- Create: `src/chanchi/migrations/001_init.sql`, `src/chanchi/db.py`, `src/chanchi/data/template.db` (generated in Step 4), `tests/conftest.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `errors.ChanchiError`, `taxonomy.TASK_TYPES` (tests only).
- Produces (`chanchi.db`):
  - `operational_path() -> Path` — `$CHANCHI_DB`, else `$XDG_DATA_HOME/chanchi/chanchi.db`, else `~/.local/share/chanchi/chanchi.db`.
  - `template_path() -> Path` — `$CHANCHI_TEMPLATE_DB`, else the packaged `chanchi/data/template.db`.
  - `migrations() -> list[tuple[int, str, str]]` — `(version, filename, sql)` sorted.
  - `latest_version() -> int`
  - `connect(path: Path, *, wal: bool) -> sqlite3.Connection` — autocommit mode (`isolation_level=None`), `row_factory=sqlite3.Row`, foreign keys on, busy timeout 5000 ms, journal mode WAL or DELETE.
  - `user_version(conn) -> int`
  - `transaction(conn)` — context manager: `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` on exception.
  - `apply_migrations(conn) -> list[int]`
  - `migrate_template(path: Path | None = None) -> dict` — keys `path, from_version, to_version, applied`.
  - `bootstrap() -> dict` — keys `path, created, from_version, to_version, applied, backup`.
  - `open_operational() -> sqlite3.Connection`
  - `status() -> dict` — keys `latest_migration, template{path,exists,version,pending}, operational{path,exists,version,pending}`.
- Produces (`tests/conftest.py`): fixtures `db_env` (Path of a temp operational db, sets `CHANCHI_DB`) and `conn` (open operational connection).

- [ ] **Step 1: Create `src/chanchi/migrations/001_init.sql`**

```sql
-- 001_init: initial schema plus seed rows (human planner, task types).

CREATE TABLE models (
  id          INTEGER PRIMARY KEY,
  agent       TEXT NOT NULL,
  model       TEXT NOT NULL,
  cost_tier   INTEGER NOT NULL CHECK (cost_tier BETWEEN 1 AND 3),
  efforts     TEXT,
  active      INTEGER NOT NULL DEFAULT 1,
  notes       TEXT,
  created_at  TEXT NOT NULL,
  UNIQUE (agent, model)
);

CREATE TABLE projects (
  id          INTEGER PRIMARY KEY,
  slug        TEXT NOT NULL UNIQUE,
  path        TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE task_types (
  code        TEXT PRIMARY KEY,
  description TEXT NOT NULL
);

CREATE TABLE changes (
  id                    INTEGER PRIMARY KEY,
  project_id            INTEGER NOT NULL REFERENCES projects(id),
  ref                   TEXT NOT NULL,
  kind                  TEXT NOT NULL,
  planner_model_id      INTEGER NOT NULL REFERENCES models(id),
  planner_effort        TEXT,
  orchestrator_model_id INTEGER NOT NULL REFERENCES models(id),
  orchestrator_effort   TEXT,
  opened_at             TEXT NOT NULL,
  closed_at             TEXT,
  UNIQUE (project_id, ref)
);

CREATE TABLE sessions (
  id                INTEGER PRIMARY KEY,
  change_id         INTEGER NOT NULL REFERENCES changes(id),
  session_ref       TEXT NOT NULL,
  attempt           INTEGER NOT NULL DEFAULT 1,
  retry_reason      TEXT,
  executor_model_id INTEGER NOT NULL REFERENCES models(id),
  executor_effort   TEXT,
  task_type         TEXT NOT NULL REFERENCES task_types(code),
  complexity        TEXT NOT NULL,
  tags              TEXT,
  groups            TEXT,
  tasks_total       INTEGER NOT NULL CHECK (tasks_total > 0),
  started_at        TEXT NOT NULL,
  ended_at          TEXT,
  reported_status   TEXT,
  verdict           TEXT,
  audited_at        TEXT,
  notes             TEXT,
  UNIQUE (change_id, session_ref, attempt)
);

CREATE TABLE incidents (
  id           INTEGER PRIMARY KEY,
  change_id    INTEGER NOT NULL REFERENCES changes(id),
  session_id   INTEGER REFERENCES sessions(id),
  code         TEXT NOT NULL,
  role         TEXT NOT NULL,
  severity     TEXT NOT NULL,
  task_ref     TEXT,
  detected_by  TEXT NOT NULL,
  description  TEXT NOT NULL,
  evidence     TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  voided_at    TEXT,
  void_reason  TEXT
);

CREATE INDEX idx_changes_project ON changes(project_id);
CREATE INDEX idx_sessions_change ON sessions(change_id);
CREATE INDEX idx_incidents_change ON incidents(change_id);
CREATE INDEX idx_incidents_session ON incidents(session_id);

INSERT INTO models (agent, model, cost_tier, efforts, active, notes, created_at)
VALUES ('human', 'human', 1, NULL, 1, 'The human, as planner or orchestrator of adhoc changes', '2026-10-18T00:00:00Z');

INSERT INTO task_types (code, description) VALUES
  ('ui-component', 'Build or change a reusable or screen-level UI component'),
  ('ui-layout-styling', 'Layout, spacing, theming or styling with no new behaviour'),
  ('api-endpoint', 'Add or change an HTTP/RPC endpoint and its contract'),
  ('business-logic', 'Domain rules, use cases or application services'),
  ('db-schema-migration', 'Database schema, migrations or persistence mapping'),
  ('refactor', 'Restructure code without changing behaviour'),
  ('bugfix', 'Fix incorrect behaviour'),
  ('tests', 'Write or repair tests, including device or end-to-end passes'),
  ('infra-config-ci', 'Build, configuration, CI or tooling'),
  ('docs', 'Documentation, spec sync or archive steps'),
  ('integration', 'Integrate an external SDK, service or API');
```

- [ ] **Step 2: Implement `src/chanchi/db.py`**

```python
"""Template and operational databases: bootstrap, pragmas and migrations."""

from __future__ import annotations

import importlib.resources
import os
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from chanchi.errors import ChanchiError

BACKUPS_KEPT = 3


def operational_path() -> Path:
    override = os.environ.get("CHANCHI_DB")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "chanchi" / "chanchi.db"


def template_path() -> Path:
    override = os.environ.get("CHANCHI_TEMPLATE_DB")
    if override:
        return Path(override).expanduser()
    return Path(str(importlib.resources.files("chanchi") / "data" / "template.db"))


def migrations() -> list[tuple[int, str, str]]:
    root = importlib.resources.files("chanchi") / "migrations"
    found = []
    for entry in root.iterdir():
        if entry.name.endswith(".sql"):
            version = int(entry.name.split("_", 1)[0])
            found.append((version, entry.name, entry.read_text(encoding="utf-8")))
    found.sort()
    numbers = [version for version, _, _ in found]
    if numbers != list(range(1, len(found) + 1)):
        raise ChanchiError(
            "internal", f"migrations must be numbered 001..N without gaps, found {numbers}"
        )
    return found


def latest_version() -> int:
    return len(migrations())


def connect(path: Path, *, wal: bool) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(f"PRAGMA journal_mode = {'WAL' if wal else 'DELETE'}")
    return conn


def user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _too_new(current: int, latest: int) -> ChanchiError:
    return ChanchiError(
        "schema_too_new",
        f"database schema is v{current} but this chanchi only knows v{latest}",
        hint="update the chanchi repository (git pull), then retry",
    )


def _statements(sql: str) -> Iterator[str]:
    """Split a migration into statements; full-line `--` comments are dropped."""
    buffer = ""
    for line in sql.splitlines(keepends=True):
        if line.lstrip().startswith("--"):
            continue
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                yield statement
            buffer = ""
    if buffer.strip():
        raise ChanchiError("internal", "migration ends with an incomplete SQL statement")


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply every pending migration, one transaction each. Returns the versions applied."""
    latest = latest_version()
    applied = []
    for version, _name, sql in migrations():
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = user_version(conn)
            if current > latest:
                raise _too_new(current, latest)
            if current >= version:
                conn.execute("COMMIT")
                continue
            for statement in _statements(sql):
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version}")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
        applied.append(version)
    return applied


def migrate_template(path: Path | None = None) -> dict:
    """Bring the committed template database to the latest migration (developer step)."""
    path = path or template_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path, wal=False)
    try:
        before = user_version(conn)
        applied = apply_migrations(conn)
        after = user_version(conn)
        conn.execute("VACUUM")
    finally:
        conn.close()
    return {"path": str(path), "from_version": before, "to_version": after, "applied": applied}


def _prune_backups(path: Path) -> None:
    backups = sorted(
        path.parent.glob(f"{path.name}.bak-v*"),
        key=lambda p: int(p.name.rsplit("-v", 1)[1]),
    )
    for old in backups[:-BACKUPS_KEPT]:
        old.unlink()


def _backup(path: Path, version: int) -> str:
    dest = path.with_name(f"{path.name}.bak-v{version}")
    if dest.exists():
        dest.unlink()
    source = sqlite3.connect(str(path))
    target = sqlite3.connect(str(dest))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    _prune_backups(path)
    return str(dest)


def bootstrap() -> dict:
    """Create the operational database from the template if missing, then migrate it."""
    path = operational_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if not path.exists():
        template = template_path()
        if not template.exists():
            raise ChanchiError(
                "internal",
                f"template database not found at {template}",
                hint="run `chanchi db migrate --template` in the chanchi repository",
            )
        shutil.copyfile(template, path)
        created = True
    conn = connect(path, wal=True)
    try:
        current = user_version(conn)
        latest = latest_version()
        if current > latest:
            raise _too_new(current, latest)
        applied: list[int] = []
        backup = None
        if current < latest:
            if not created:
                conn.close()
                backup = _backup(path, current)
                conn = connect(path, wal=True)
            applied = apply_migrations(conn)
        return {
            "path": str(path),
            "created": created,
            "from_version": current,
            "to_version": user_version(conn),
            "applied": applied,
            "backup": backup,
        }
    finally:
        conn.close()


def open_operational() -> sqlite3.Connection:
    bootstrap()
    return connect(operational_path(), wal=True)


def _read_version(path: Path) -> int | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def status() -> dict:
    latest = latest_version()

    def info(path: Path) -> dict:
        version = _read_version(path)
        return {
            "path": str(path),
            "exists": version is not None,
            "version": version,
            "pending": None if version is None else max(latest - version, 0),
        }

    return {
        "latest_migration": latest,
        "template": info(template_path()),
        "operational": info(operational_path()),
    }
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import pytest


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    """Point chanchi at a throwaway operational database."""
    path = tmp_path / "data" / "chanchi.db"
    monkeypatch.setenv("CHANCHI_DB", str(path))
    return path


@pytest.fixture
def conn(db_env):
    from chanchi import db

    connection = db.open_operational()
    yield connection
    connection.close()
```

- [ ] **Step 4: Generate the committed template database**

Run: `uv run python -c "from chanchi import db; print(db.migrate_template())"`
Expected output (path will be absolute): `{'path': '.../src/chanchi/data/template.db', 'from_version': 0, 'to_version': 1, 'applied': [1]}`

Then run: `git check-ignore -v src/chanchi/data/template.db; echo "exit=$?"`
Expected: a line showing the `!src/chanchi/data/template.db` negation rule from `.gitignore` followed by `exit=0`, **or** no line and `exit=1`. Either way the file must appear as untracked in `git status --short src/chanchi/data/`. If `git status` does not list it, STOP and report.

- [ ] **Step 5: Write the tests `tests/test_db.py`**

```python
import shutil
import sqlite3

import pytest

from chanchi import db, taxonomy
from chanchi.errors import ChanchiError

OPERATIONAL_TABLES = ("projects", "changes", "sessions", "incidents")


def _schema(conn):
    return conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()


def _fresh(tmp_path):
    conn = db.connect(tmp_path / "fresh.db", wal=False)
    db.apply_migrations(conn)
    return conn


def test_migrations_are_contiguous():
    versions = [version for version, _, _ in db.migrations()]
    assert versions == list(range(1, len(versions) + 1))
    assert db.latest_version() == len(versions)


def test_template_is_at_latest_version():
    template = db.connect(db.template_path(), wal=False)
    try:
        assert db.user_version(template) == db.latest_version()
        assert template.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        template.close()


def test_template_schema_matches_migrations(tmp_path):
    fresh = _fresh(tmp_path)
    template = db.connect(db.template_path(), wal=False)
    try:
        assert [tuple(r) for r in _schema(template)] == [tuple(r) for r in _schema(fresh)]
        for table in ("models", "task_types"):
            query = f"SELECT * FROM {table} ORDER BY 1"
            assert [tuple(r) for r in template.execute(query)] == [
                tuple(r) for r in fresh.execute(query)
            ]
        for table in OPERATIONAL_TABLES:
            assert template.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        template.close()
        fresh.close()


def test_template_seed_matches_taxonomy():
    template = db.connect(db.template_path(), wal=False)
    try:
        rows = [tuple(r) for r in template.execute("SELECT code, description FROM task_types ORDER BY rowid")]
        assert rows == list(taxonomy.TASK_TYPES)
        human = template.execute("SELECT agent, model FROM models").fetchall()
        assert [tuple(r) for r in human] == [("human", "human")]
    finally:
        template.close()


def test_bootstrap_creates_operational_from_template(db_env):
    result = db.bootstrap()
    assert result["created"] is True
    assert result["applied"] == []
    assert result["backup"] is None
    assert db_env.exists()
    conn = db.connect(db_env, wal=True)
    try:
        assert db.user_version(conn) == db.latest_version()
        assert conn.execute("SELECT COUNT(*) FROM task_types").fetchone()[0] == len(taxonomy.TASK_TYPES)
    finally:
        conn.close()


def test_bootstrap_is_idempotent(db_env):
    db.bootstrap()
    again = db.bootstrap()
    assert again["created"] is False
    assert again["applied"] == []


def test_outdated_operational_is_backed_up_and_migrated(db_env):
    db_env.parent.mkdir(parents=True)
    sqlite3.connect(str(db_env)).close()  # empty database at user_version 0
    result = db.bootstrap()
    assert result["created"] is False
    assert result["from_version"] == 0
    assert result["applied"] == list(range(1, db.latest_version() + 1))
    assert result["backup"].endswith("chanchi.db.bak-v0")
    assert (db_env.parent / "chanchi.db.bak-v0").exists()


def test_too_new_operational_is_refused(db_env):
    db.bootstrap()
    raw = sqlite3.connect(str(db_env))
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    with pytest.raises(ChanchiError) as info:
        db.bootstrap()
    assert info.value.code == "schema_too_new"


def test_only_three_backups_are_kept(tmp_path):
    path = tmp_path / "chanchi.db"
    path.write_bytes(b"")
    for version in range(1, 6):
        (tmp_path / f"chanchi.db.bak-v{version}").write_bytes(b"")
    db._prune_backups(path)
    remaining = sorted(p.name for p in tmp_path.glob("chanchi.db.bak-v*"))
    assert remaining == ["chanchi.db.bak-v3", "chanchi.db.bak-v4", "chanchi.db.bak-v5"]


def test_migrate_template_on_a_copy(tmp_path, monkeypatch):
    copy = tmp_path / "template.db"
    shutil.copyfile(db.template_path(), copy)
    monkeypatch.setenv("CHANCHI_TEMPLATE_DB", str(copy))
    assert db.migrate_template()["applied"] == []
    blank = tmp_path / "blank.db"
    result = db.migrate_template(blank)
    assert result["from_version"] == 0
    assert result["to_version"] == db.latest_version()


def test_transaction_rolls_back_on_error(conn):
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            conn.execute("INSERT INTO task_types (code, description) VALUES ('tmp-type', 'x')")
            raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM task_types WHERE code = 'tmp-type'").fetchone()[0] == 0


def test_connection_pragmas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_status_reports_both_databases(db_env):
    before = db.status()
    assert before["operational"]["exists"] is False
    assert before["template"]["pending"] == 0
    db.bootstrap()
    after = db.status()
    assert after["operational"]["version"] == db.latest_version()
    assert after["operational"]["pending"] == 0
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_db.py -v`
Expected: 13 passed.

- [ ] **Step 7: Run the whole suite**

Run: `uv run pytest -q`
Expected: 37 passed.

- [ ] **Step 8: Commit**

```bash
git add src/chanchi/migrations/001_init.sql src/chanchi/db.py src/chanchi/data/template.db tests/conftest.py tests/test_db.py
git commit -m "feat: add template and operational databases with migrations

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Project detection and model catalog

**Recommended model:** sonnet

**Files:**
- Create: `src/chanchi/projects.py`, `src/chanchi/catalog.py`
- Modify: `tests/conftest.py` (append fixtures)
- Test: `tests/test_projects.py`, `tests/test_catalog.py`

**Interfaces:**
- Consumes: `db.transaction`, `taxonomy.*`, `modelspec.parse`, `modelspec.format_spec`, `timeutil.utc_now`, `errors.ChanchiError`.
- Produces (`chanchi.projects`):
  - `detect(cwd: Path | None = None) -> tuple[str, str]` — `(slug, toplevel_path)`.
  - `identify(slug: str | None = None, cwd: Path | None = None) -> tuple[str, str | None]`.
  - `ensure(conn, slug: str, path: str | None, now: str | None = None) -> int` — caller holds the transaction.
  - `resolve_project(conn, slug: str | None = None, cwd: Path | None = None) -> dict` — existing project row as dict.
- Produces (`chanchi.catalog`):
  - `add_model(conn, *, agent, model, cost_tier, efforts=None, notes=None, now=None) -> dict`
  - `list_models(conn, *, include_inactive=False) -> list[dict]`
  - `set_model(conn, *, spec, cost_tier=None, active=None, efforts=None, notes=None) -> dict`
  - `resolve_model(conn, spec: str, *, role: str) -> tuple[sqlite3.Row, str | None]` — `role` ∈ `planner|orchestrator|executor`; returns the catalog row and the parsed effort.
  - `list_task_types(conn) -> list[dict]`, `add_task_type(conn, *, code, description) -> dict`, `require_task_type(conn, code) -> None`.
  - Model dict keys: `id, agent, model, spec, cost_tier, efforts (list|None), active (bool), notes, created_at`.
- Produces (`tests/conftest.py`): fixtures `git_repo` (a temp git repository named `demo-app`, made the cwd) and `seeded` (the `conn` fixture with five catalog models: `claude:opus` cost 3, `claude:sonnet` cost 2, `claude:haiku` cost 1 — all three with efforts `low,medium,high,xhigh,max`; `agy:gemini-3.8-flash-high` cost 1 with efforts `low,medium,high`; `opencode:openrouter/qwen/qwen3-coder:free` cost 1 with no efforts).

- [ ] **Step 1: Append fixtures to `tests/conftest.py`**

Append exactly:

```python


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    """A temporary git repository named demo-app, used as the current directory."""
    import subprocess

    repo = tmp_path / "demo-app"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    return repo


@pytest.fixture
def seeded(conn):
    """The operational connection with a small model catalog."""
    from chanchi import catalog

    all_efforts = ["low", "medium", "high", "xhigh", "max"]
    catalog.add_model(conn, agent="claude", model="opus", cost_tier=3, efforts=all_efforts)
    catalog.add_model(conn, agent="claude", model="sonnet", cost_tier=2, efforts=all_efforts)
    catalog.add_model(conn, agent="claude", model="haiku", cost_tier=1, efforts=all_efforts)
    catalog.add_model(
        conn, agent="agy", model="gemini-3.8-flash-high", cost_tier=1, efforts=["low", "medium", "high"]
    )
    catalog.add_model(conn, agent="opencode", model="openrouter/qwen/qwen3-coder:free", cost_tier=1)
    return conn
```

- [ ] **Step 2: Write the failing tests `tests/test_projects.py`**

```python
import pytest

from chanchi import db, projects
from chanchi.errors import ChanchiError


def test_detect_uses_git_toplevel(git_repo):
    (git_repo / "sub").mkdir()
    slug, path = projects.detect(git_repo / "sub")
    assert slug == "demo-app"
    assert path.endswith("demo-app")


def test_detect_outside_git_fails(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    with pytest.raises(ChanchiError) as info:
        projects.detect(outside)
    assert info.value.code == "project_not_detected"
    assert info.value.field == "project"


def test_identify_explicit_slug_keeps_path_only_when_it_matches(git_repo):
    assert projects.identify("demo-app")[1].endswith("demo-app")
    assert projects.identify("other") == ("other", None)


def test_identify_explicit_slug_outside_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert projects.identify("manual") == ("manual", None)


def test_identify_rejects_empty_slug(git_repo):
    with pytest.raises(ChanchiError):
        projects.identify("  ")


def test_ensure_inserts_once(conn):
    with db.transaction(conn):
        first = projects.ensure(conn, "demo-app", "/tmp/demo-app")
    with db.transaction(conn):
        second = projects.ensure(conn, "demo-app", "/tmp/demo-app")
    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


def test_resolve_project_requires_existing_row(conn, git_repo):
    with pytest.raises(ChanchiError) as info:
        projects.resolve_project(conn)
    assert info.value.code == "invalid_value"
    assert info.value.valid_values == []
    with db.transaction(conn):
        projects.ensure(conn, "demo-app", None)
    assert projects.resolve_project(conn)["slug"] == "demo-app"
```

- [ ] **Step 3: Write the failing tests `tests/test_catalog.py`**

```python
import pytest

from chanchi import catalog
from chanchi.errors import ChanchiError


def test_add_and_list_models(seeded):
    specs = [m["spec"] for m in catalog.list_models(seeded)]
    assert "claude:sonnet" in specs
    assert "human:human" in specs
    flash = next(m for m in catalog.list_models(seeded) if m["model"] == "gemini-3.8-flash-high")
    assert flash["efforts"] == ["low", "medium", "high"]
    assert flash["active"] is True
    qwen = next(m for m in catalog.list_models(seeded) if m["agent"] == "opencode")
    assert qwen["efforts"] is None


def test_add_model_validations(conn):
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="human", model="x", cost_tier=1)
    assert info.value.field == "agent"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="x", cost_tier=4)
    assert info.value.field == "cost"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="x", cost_tier=1, efforts=["turbo"])
    assert info.value.field == "efforts"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="weird:high", cost_tier=1)
    assert info.value.field == "model"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="  ", cost_tier=1)
    assert info.value.field == "model"


def test_duplicate_model(seeded):
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(seeded, agent="claude", model="sonnet", cost_tier=2)
    assert info.value.code == "duplicate"


def test_set_model(seeded):
    updated = catalog.set_model(seeded, spec="claude:sonnet", cost_tier=3, active=False, notes="paused")
    assert updated["cost_tier"] == 3
    assert updated["active"] is False
    assert updated["notes"] == "paused"
    assert "claude:sonnet" not in [m["spec"] for m in catalog.list_models(seeded)]
    assert "claude:sonnet" in [m["spec"] for m in catalog.list_models(seeded, include_inactive=True)]


def test_set_model_errors(seeded):
    with pytest.raises(ChanchiError) as info:
        catalog.set_model(seeded, spec="claude:sonnet")
    assert info.value.code == "invalid_value"
    with pytest.raises(ChanchiError) as info:
        catalog.set_model(seeded, spec="claude:sonnet:high", cost_tier=1)
    assert info.value.field == "spec"
    with pytest.raises(ChanchiError) as info:
        catalog.set_model(seeded, spec="claude:nope", cost_tier=1)
    assert info.value.code == "unknown_model"


def test_resolve_model(seeded):
    row, effort = catalog.resolve_model(seeded, "agy:gemini-3.8-flash-high:high", role="executor")
    assert row["agent"] == "agy" and effort == "high"
    row, effort = catalog.resolve_model(seeded, "human", role="planner")
    assert row["agent"] == "human" and effort is None
    _, effort = catalog.resolve_model(seeded, "claude:opus:unknown", role="planner")
    assert effort == "unknown"
    _, effort = catalog.resolve_model(seeded, "opencode:openrouter/qwen/qwen3-coder:free:high", role="executor")
    assert effort == "high"  # no efforts listed: any effort accepted


def test_resolve_model_errors(seeded):
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "claude:gpt-9", role="executor")
    assert info.value.code == "unknown_model"
    assert "chanchi models add --agent claude --model gpt-9" in info.value.hint
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "human", role="executor")
    assert info.value.field == "executor"
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "agy:gemini-3.8-flash-high:max", role="executor")
    assert info.value.valid_values == ["low", "medium", "high", "unknown"]
    catalog.set_model(seeded, spec="claude:haiku", active=False)
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "claude:haiku", role="executor")
    assert "--active 1" in info.value.hint


def test_task_types(conn):
    codes = [t["code"] for t in catalog.list_task_types(conn)]
    assert codes[0] == "ui-component" and len(codes) == 11
    added = catalog.add_task_type(conn, code="mobile-native", description="Native iOS/Android code")
    assert added == {"code": "mobile-native", "description": "Native iOS/Android code"}
    catalog.require_task_type(conn, "mobile-native")
    with pytest.raises(ChanchiError) as info:
        catalog.add_task_type(conn, code="mobile-native", description="again")
    assert info.value.code == "duplicate"
    with pytest.raises(ChanchiError) as info:
        catalog.add_task_type(conn, code="Bad_Code", description="x")
    assert info.value.field == "code"
    with pytest.raises(ChanchiError) as info:
        catalog.add_task_type(conn, code="ok-code", description=" ")
    assert info.value.field == "description"
    with pytest.raises(ChanchiError) as info:
        catalog.require_task_type(conn, "nope")
    assert info.value.field == "task_type"
    assert "ui-component" in info.value.valid_values
```

- [ ] **Step 4: Run to verify failure**

Run: `uv run pytest tests/test_projects.py tests/test_catalog.py -v`
Expected: FAIL with `ImportError` for `projects` / `catalog`.

- [ ] **Step 5: Implement `src/chanchi/projects.py`**

```python
"""Project identity: the git toplevel basename, or an explicit --project slug."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now


def detect(cwd: Path | None = None) -> tuple[str, str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        result = None
    if result is None or result.returncode != 0 or not result.stdout.strip():
        raise ChanchiError(
            "project_not_detected",
            "the current directory is not inside a git repository",
            field="project",
            hint="run from the project's repository or pass --project <slug>",
        )
    top = Path(result.stdout.strip())
    return top.name, str(top)


def identify(slug: str | None = None, cwd: Path | None = None) -> tuple[str, str | None]:
    """Slug and path for a project; the path is kept only when the cwd is that project."""
    if slug is None:
        return detect(cwd)
    slug = slug.strip()
    if not slug:
        raise ChanchiError("invalid_value", "project slug must not be empty", field="project")
    try:
        detected_slug, detected_path = detect(cwd)
    except ChanchiError:
        return slug, None
    return slug, detected_path if detected_slug == slug else None


def ensure(conn: sqlite3.Connection, slug: str, path: str | None, now: str | None = None) -> int:
    """Return the project id, inserting the row if needed. The caller holds the transaction."""
    row = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if row is not None:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO projects (slug, path, created_at) VALUES (?, ?, ?)",
        (slug, path, now or utc_now()),
    )
    return cursor.lastrowid


def resolve_project(
    conn: sqlite3.Connection, slug: str | None = None, cwd: Path | None = None
) -> dict:
    slug, _ = identify(slug, cwd)
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        known = [r["slug"] for r in conn.execute("SELECT slug FROM projects ORDER BY slug")]
        raise ChanchiError(
            "invalid_value",
            f"project {slug!r} has no recorded changes yet",
            field="project",
            valid_values=known,
            hint="projects are created by `chanchi change open`",
        )
    return dict(row)
```

- [ ] **Step 6: Implement `src/chanchi/catalog.py`**

```python
"""Model catalog and task types."""

from __future__ import annotations

import sqlite3

from chanchi import modelspec, taxonomy
from chanchi.db import transaction
from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now


def _model_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "agent": row["agent"],
        "model": row["model"],
        "spec": f"{row['agent']}:{row['model']}",
        "cost_tier": row["cost_tier"],
        "efforts": row["efforts"].split(",") if row["efforts"] else None,
        "active": bool(row["active"]),
        "notes": row["notes"],
        "created_at": row["created_at"],
    }


def _efforts_csv(efforts: list[str] | None) -> str | None:
    if efforts is None:
        return None
    cleaned: list[str] = []
    for effort in efforts:
        effort = effort.strip()
        if not effort:
            continue
        taxonomy.validate_choice("efforts", effort, taxonomy.LAUNCH_EFFORTS)
        if effort not in cleaned:
            cleaned.append(effort)
    return ",".join(cleaned) or None


def _model_row(conn: sqlite3.Connection, agent: str, model: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM models WHERE agent = ? AND model = ?", (agent, model)
    ).fetchone()


def add_model(
    conn: sqlite3.Connection,
    *,
    agent: str,
    model: str,
    cost_tier: int,
    efforts: list[str] | None = None,
    notes: str | None = None,
    now: str | None = None,
) -> dict:
    taxonomy.validate_choice("agent", agent, taxonomy.AGENTS)
    model = model.strip()
    if not model:
        raise ChanchiError("invalid_value", "model must not be empty", field="model")
    if ":" in model and model.rsplit(":", 1)[1] in taxonomy.EFFORTS:
        raise ChanchiError(
            "invalid_value",
            f"model {model!r} ends in an effort value, which makes specs ambiguous",
            field="model",
            hint="register the model without the trailing :<effort>",
        )
    taxonomy.validate_choice("cost", cost_tier, taxonomy.COST_TIERS)
    efforts_csv = _efforts_csv(efforts)
    with transaction(conn):
        if _model_row(conn, agent, model) is not None:
            raise ChanchiError(
                "duplicate",
                f"{agent}:{model} is already in the catalog",
                field="model",
                hint="use `chanchi models set` to change it",
            )
        cursor = conn.execute(
            "INSERT INTO models (agent, model, cost_tier, efforts, active, notes, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (agent, model, cost_tier, efforts_csv, notes, now or utc_now()),
        )
    return _model_dict(conn.execute("SELECT * FROM models WHERE id = ?", (cursor.lastrowid,)).fetchone())


def list_models(conn: sqlite3.Connection, *, include_inactive: bool = False) -> list[dict]:
    query = "SELECT * FROM models" + ("" if include_inactive else " WHERE active = 1")
    return [_model_dict(r) for r in conn.execute(query + " ORDER BY agent, model")]


def set_model(
    conn: sqlite3.Connection,
    *,
    spec: str,
    cost_tier: int | None = None,
    active: bool | None = None,
    efforts: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    parsed = modelspec.parse(spec, field="spec")
    if parsed.effort is not None:
        raise ChanchiError(
            "invalid_value", "models set takes agent:model without an effort", field="spec"
        )
    updates: dict = {}
    if cost_tier is not None:
        updates["cost_tier"] = taxonomy.validate_choice("cost", cost_tier, taxonomy.COST_TIERS)
    if active is not None:
        updates["active"] = 1 if active else 0
    if efforts is not None:
        updates["efforts"] = _efforts_csv(efforts)
    if notes is not None:
        updates["notes"] = notes
    if not updates:
        raise ChanchiError(
            "invalid_value",
            "nothing to update",
            hint="pass at least one of --cost, --active, --efforts, --notes",
        )
    with transaction(conn):
        row = _model_row(conn, parsed.agent, parsed.model)
        if row is None:
            raise ChanchiError(
                "unknown_model", f"{parsed.agent}:{parsed.model} is not in the catalog", field="spec"
            )
        assignments = ", ".join(f"{column} = ?" for column in updates)
        conn.execute(f"UPDATE models SET {assignments} WHERE id = ?", (*updates.values(), row["id"]))
    return _model_dict(conn.execute("SELECT * FROM models WHERE id = ?", (row["id"],)).fetchone())


def resolve_model(
    conn: sqlite3.Connection, spec: str, *, role: str
) -> tuple[sqlite3.Row, str | None]:
    """Catalog row and effort for a spec used as planner, orchestrator or executor."""
    parsed = modelspec.parse(spec, field=role)
    if role == "executor" and parsed.agent in taxonomy.PLANNER_ONLY_AGENTS:
        raise ChanchiError(
            "invalid_value", "human can be a planner or orchestrator, never an executor", field=role
        )
    row = _model_row(conn, parsed.agent, parsed.model)
    if row is None:
        raise ChanchiError(
            "unknown_model",
            f"model {parsed.agent}:{parsed.model} is not in the catalog",
            field=role,
            hint=(
                "ask the human for its cost tier, then run "
                f"`chanchi models add --agent {parsed.agent} --model {parsed.model} --cost <1-3>`"
            ),
        )
    if not row["active"]:
        raise ChanchiError(
            "invalid_value",
            f"model {parsed.agent}:{parsed.model} is inactive",
            field=role,
            hint=f"run `chanchi models set {parsed.agent}:{parsed.model} --active 1` to reactivate it",
        )
    if parsed.effort and parsed.effort != "unknown" and row["efforts"]:
        allowed = row["efforts"].split(",")
        if parsed.effort not in allowed:
            raise ChanchiError(
                "invalid_value",
                f"effort {parsed.effort!r} is not supported by {parsed.agent}:{parsed.model}",
                field=role,
                valid_values=allowed + ["unknown"],
            )
    return row, parsed.effort


def list_task_types(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT code, description FROM task_types ORDER BY rowid")]


def add_task_type(conn: sqlite3.Connection, *, code: str, description: str) -> dict:
    code = code.strip()
    if not taxonomy.TASK_TYPE_PATTERN.match(code):
        raise ChanchiError(
            "invalid_value",
            f"task type {code!r} must be kebab-case",
            field="code",
            hint="lowercase letters and digits separated by single hyphens",
        )
    description = description.strip()
    if not description:
        raise ChanchiError("invalid_value", "description must not be empty", field="description")
    with transaction(conn):
        if conn.execute("SELECT 1 FROM task_types WHERE code = ?", (code,)).fetchone():
            raise ChanchiError("duplicate", f"task type {code!r} already exists", field="code")
        conn.execute("INSERT INTO task_types (code, description) VALUES (?, ?)", (code, description))
    return {"code": code, "description": description}


def require_task_type(conn: sqlite3.Connection, code: str) -> None:
    if conn.execute("SELECT 1 FROM task_types WHERE code = ?", (code,)).fetchone() is None:
        raise ChanchiError(
            "invalid_value",
            f"unknown task type {code!r}",
            field="task_type",
            valid_values=[t["code"] for t in list_task_types(conn)],
            hint="add it with `chanchi taxonomy add-type <code> --description ...` if none fits",
        )
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_projects.py tests/test_catalog.py -v`
Expected: 15 passed.

- [ ] **Step 8: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: 52 passed.

```bash
git add src/chanchi/projects.py src/chanchi/catalog.py tests/conftest.py tests/test_projects.py tests/test_catalog.py
git commit -m "feat: add project detection and model catalog

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Recording changes, sessions and incidents

**Recommended model:** sonnet

**Files:**
- Create: `src/chanchi/record.py`
- Test: `tests/test_record.py`

**Interfaces:**
- Consumes: `catalog.resolve_model`, `catalog.require_task_type`, `projects.ensure`, `db.transaction`, `taxonomy.*`, `modelspec.format_spec`, `timeutil.utc_now`.
- Produces (`chanchi.record`), all keyword-only after `conn`:
  - `get_change(conn, project_id: int, ref: str) -> sqlite3.Row`
  - `change_dict(conn, change_id: int) -> dict` — keys `id, project, ref, kind, planner, orchestrator, opened_at, closed_at`.
  - `open_change(conn, *, project_slug, project_path, ref, kind, planner, orchestrator=None, now=None) -> dict`
  - `close_change(conn, *, project_id, ref, now=None) -> dict`
  - `get_session(conn, change_id: int, session_ref: str, attempt: int | None = None) -> sqlite3.Row`
  - `session_dict(conn, session_id: int) -> dict` — keys `id, change, session, attempt, retry_reason, executor, task_type, complexity, tags (list), groups, tasks_total, started_at, ended_at, reported_status, verdict, audited_at, notes`.
  - `start_session(conn, *, project_id, ref, session_ref, executor, task_type, complexity, tasks_total, groups=None, tags=None, retry_reason=None, now=None) -> dict`
  - `report_session(conn, *, project_id, ref, session_ref, status, attempt=None, now=None) -> dict`
  - `audit_session(conn, *, project_id, ref, session_ref, verdict, notes=None, attempt=None, now=None) -> dict`
  - `update_session(conn, *, project_id, ref, session_ref, attempt=None, task_type=None, complexity=None, tags=None, tasks_total=None, notes=None) -> dict`
  - `incident_dict(conn, incident_id: int) -> dict` — keys `id, change, session, attempt, code, role, severity, task_ref, detected_by, description, evidence, created_at, voided_at, void_reason`.
  - `add_incident(conn, *, project_id, ref, code, severity, detected_by, description, evidence, session_ref=None, attempt=None, task_ref=None, role=None, now=None) -> dict`
  - `void_incident(conn, *, incident_id, reason, now=None) -> dict`

- [ ] **Step 1: Write the failing tests `tests/test_record.py`**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_record.py -v`
Expected: FAIL with `ImportError: cannot import name 'record'`.

- [ ] **Step 3: Implement `src/chanchi/record.py`**

```python
"""Write side: changes, sessions, incidents and verdicts. Every write is validated first."""

from __future__ import annotations

import sqlite3

from chanchi import catalog, projects, taxonomy
from chanchi.db import transaction
from chanchi.errors import ChanchiError
from chanchi.modelspec import format_spec
from chanchi.timeutil import utc_now


def _csv(value: str | None) -> str | None:
    if value is None:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return ",".join(items) if items else None


def _required_text(field: str, value: str | None, hint: str | None = None) -> str:
    text = (value or "").strip()
    if not text:
        raise ChanchiError("invalid_value", f"{field} must not be empty", field=field, hint=hint)
    return text


# --- changes ---------------------------------------------------------------


def get_change(conn: sqlite3.Connection, project_id: int, ref: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM changes WHERE project_id = ? AND ref = ?", (project_id, ref)
    ).fetchone()
    if row is None:
        known = [
            r["ref"]
            for r in conn.execute(
                "SELECT ref FROM changes WHERE project_id = ? ORDER BY id DESC LIMIT 20", (project_id,)
            )
        ]
        raise ChanchiError(
            "unknown_change",
            f"change {ref!r} not found in this project",
            field="ref",
            valid_values=known,
            hint="run `chanchi change open <ref> ...` first",
        )
    return row


def change_dict(conn: sqlite3.Connection, change_id: int) -> dict:
    r = conn.execute(
        """
        SELECT c.*, p.slug AS project,
               pm.agent AS planner_agent, pm.model AS planner_model,
               om.agent AS orchestrator_agent, om.model AS orchestrator_model
        FROM changes c
        JOIN projects p ON p.id = c.project_id
        JOIN models pm ON pm.id = c.planner_model_id
        JOIN models om ON om.id = c.orchestrator_model_id
        WHERE c.id = ?
        """,
        (change_id,),
    ).fetchone()
    return {
        "id": r["id"],
        "project": r["project"],
        "ref": r["ref"],
        "kind": r["kind"],
        "planner": format_spec(r["planner_agent"], r["planner_model"], r["planner_effort"]),
        "orchestrator": format_spec(
            r["orchestrator_agent"], r["orchestrator_model"], r["orchestrator_effort"]
        ),
        "opened_at": r["opened_at"],
        "closed_at": r["closed_at"],
    }


def open_change(
    conn: sqlite3.Connection,
    *,
    project_slug: str,
    project_path: str | None,
    ref: str,
    kind: str,
    planner: str,
    orchestrator: str | None = None,
    now: str | None = None,
) -> dict:
    ref = _required_text("ref", ref)
    taxonomy.validate_choice("kind", kind, taxonomy.CHANGE_KINDS)
    planner_row, planner_effort = catalog.resolve_model(conn, planner, role="planner")
    orchestrator_row, orchestrator_effort = catalog.resolve_model(
        conn, orchestrator or planner, role="orchestrator"
    )
    now = now or utc_now()
    with transaction(conn):
        project_id = projects.ensure(conn, project_slug, project_path, now)
        if conn.execute(
            "SELECT 1 FROM changes WHERE project_id = ? AND ref = ?", (project_id, ref)
        ).fetchone():
            raise ChanchiError(
                "duplicate",
                f"change {ref!r} already exists in project {project_slug!r}",
                field="ref",
                hint="refs are unique per project; keep recording against the existing change",
            )
        cursor = conn.execute(
            "INSERT INTO changes (project_id, ref, kind, planner_model_id, planner_effort, "
            "orchestrator_model_id, orchestrator_effort, opened_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                ref,
                kind,
                planner_row["id"],
                planner_effort,
                orchestrator_row["id"],
                orchestrator_effort,
                now,
            ),
        )
    return change_dict(conn, cursor.lastrowid)


def close_change(
    conn: sqlite3.Connection, *, project_id: int, ref: str, now: str | None = None
) -> dict:
    change = get_change(conn, project_id, ref)
    if change["closed_at"] is not None:
        raise ChanchiError("invalid_value", f"change {ref!r} is already closed", field="ref")
    with transaction(conn):
        conn.execute("UPDATE changes SET closed_at = ? WHERE id = ?", (now or utc_now(), change["id"]))
    return change_dict(conn, change["id"])


# --- sessions --------------------------------------------------------------


def _latest_attempt(conn: sqlite3.Connection, change_id: int, session_ref: str) -> int | None:
    return conn.execute(
        "SELECT MAX(attempt) FROM sessions WHERE change_id = ? AND session_ref = ?",
        (change_id, session_ref),
    ).fetchone()[0]


def get_session(
    conn: sqlite3.Connection, change_id: int, session_ref: str, attempt: int | None = None
) -> sqlite3.Row:
    if attempt is None:
        attempt = _latest_attempt(conn, change_id, session_ref)
    row = None
    if attempt is not None:
        row = conn.execute(
            "SELECT * FROM sessions WHERE change_id = ? AND session_ref = ? AND attempt = ?",
            (change_id, session_ref, attempt),
        ).fetchone()
    if row is None:
        known = [
            f"{r['session_ref']}#{r['attempt']}"
            for r in conn.execute(
                "SELECT session_ref, attempt FROM sessions WHERE change_id = ? ORDER BY id", (change_id,)
            )
        ]
        raise ChanchiError(
            "unknown_session",
            f"session {session_ref!r}" + (f" attempt {attempt}" if attempt else "") + " not found",
            field="session",
            valid_values=known,
            hint="run `chanchi session start` first",
        )
    return row


def session_dict(conn: sqlite3.Connection, session_id: int) -> dict:
    r = conn.execute(
        """
        SELECT s.*, c.ref AS change_ref, m.agent, m.model
        FROM sessions s
        JOIN changes c ON c.id = s.change_id
        JOIN models m ON m.id = s.executor_model_id
        WHERE s.id = ?
        """,
        (session_id,),
    ).fetchone()
    return {
        "id": r["id"],
        "change": r["change_ref"],
        "session": r["session_ref"],
        "attempt": r["attempt"],
        "retry_reason": r["retry_reason"],
        "executor": format_spec(r["agent"], r["model"], r["executor_effort"]),
        "task_type": r["task_type"],
        "complexity": r["complexity"],
        "tags": r["tags"].split(",") if r["tags"] else [],
        "groups": r["groups"],
        "tasks_total": r["tasks_total"],
        "started_at": r["started_at"],
        "ended_at": r["ended_at"],
        "reported_status": r["reported_status"],
        "verdict": r["verdict"],
        "audited_at": r["audited_at"],
        "notes": r["notes"],
    }


def _validate_tasks_total(tasks_total: int | None) -> int:
    if tasks_total is None or tasks_total < 1:
        raise ChanchiError(
            "invalid_value", "tasks must be a positive integer", field="tasks",
            hint="count the tasks the session owns in tasks.md",
        )
    return tasks_total


def start_session(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    ref: str,
    session_ref: str,
    executor: str,
    task_type: str,
    complexity: str,
    tasks_total: int,
    groups: str | None = None,
    tags: str | None = None,
    retry_reason: str | None = None,
    now: str | None = None,
) -> dict:
    change = get_change(conn, project_id, ref)
    if change["closed_at"] is not None:
        raise ChanchiError(
            "invalid_value", f"change {ref!r} is closed", field="ref", hint="open a new change for new work"
        )
    session_ref = _required_text("session", session_ref)
    model_row, effort = catalog.resolve_model(conn, executor, role="executor")
    catalog.require_task_type(conn, task_type)
    taxonomy.validate_choice("complexity", complexity, taxonomy.COMPLEXITIES)
    _validate_tasks_total(tasks_total)
    if retry_reason is not None:
        taxonomy.validate_choice("retry_reason", retry_reason, taxonomy.RETRY_REASONS)
    with transaction(conn):
        latest = _latest_attempt(conn, change["id"], session_ref)
        if latest is None:
            if retry_reason is not None:
                raise ChanchiError(
                    "invalid_value",
                    "--retry-reason only applies when repeating an existing session",
                    field="retry_reason",
                )
            attempt = 1
        else:
            if retry_reason is None:
                raise ChanchiError(
                    "invalid_value",
                    f"session {session_ref} already has attempt {latest}; a new attempt needs --retry-reason",
                    field="retry_reason",
                    valid_values=taxonomy.RETRY_REASONS,
                )
            attempt = latest + 1
        cursor = conn.execute(
            "INSERT INTO sessions (change_id, session_ref, attempt, retry_reason, executor_model_id, "
            "executor_effort, task_type, complexity, tags, groups, tasks_total, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                change["id"],
                session_ref,
                attempt,
                retry_reason,
                model_row["id"],
                effort,
                task_type,
                complexity,
                _csv(tags),
                _csv(groups),
                tasks_total,
                now or utc_now(),
            ),
        )
    return session_dict(conn, cursor.lastrowid)


def report_session(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    ref: str,
    session_ref: str,
    status: str,
    attempt: int | None = None,
    now: str | None = None,
) -> dict:
    taxonomy.validate_choice("status", status, taxonomy.REPORTED_STATUSES)
    change = get_change(conn, project_id, ref)
    session = get_session(conn, change["id"], session_ref, attempt)
    with transaction(conn):
        conn.execute(
            "UPDATE sessions SET reported_status = ?, ended_at = ? WHERE id = ?",
            (status, now or utc_now(), session["id"]),
        )
    return session_dict(conn, session["id"])


def audit_session(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    ref: str,
    session_ref: str,
    verdict: str,
    notes: str | None = None,
    attempt: int | None = None,
    now: str | None = None,
) -> dict:
    taxonomy.validate_choice("verdict", verdict, taxonomy.VERDICTS)
    change = get_change(conn, project_id, ref)
    session = get_session(conn, change["id"], session_ref, attempt)
    if session["reported_status"] is None:
        raise ChanchiError(
            "missing_prerequisite",
            f"session {session_ref} has no report yet",
            field="session",
            hint="run `chanchi session report` before auditing",
        )
    with transaction(conn):
        conn.execute(
            "UPDATE sessions SET verdict = ?, audited_at = ?, notes = COALESCE(?, notes) WHERE id = ?",
            (verdict, now or utc_now(), notes, session["id"]),
        )
    return session_dict(conn, session["id"])


def update_session(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    ref: str,
    session_ref: str,
    attempt: int | None = None,
    task_type: str | None = None,
    complexity: str | None = None,
    tags: str | None = None,
    tasks_total: int | None = None,
    notes: str | None = None,
) -> dict:
    updates: dict = {}
    if task_type is not None:
        catalog.require_task_type(conn, task_type)
        updates["task_type"] = task_type
    if complexity is not None:
        updates["complexity"] = taxonomy.validate_choice("complexity", complexity, taxonomy.COMPLEXITIES)
    if tags is not None:
        updates["tags"] = _csv(tags)
    if tasks_total is not None:
        updates["tasks_total"] = _validate_tasks_total(tasks_total)
    if notes is not None:
        updates["notes"] = notes
    if not updates:
        raise ChanchiError(
            "invalid_value",
            "nothing to update",
            hint="pass at least one of --task-type, --complexity, --tags, --tasks, --notes",
        )
    change = get_change(conn, project_id, ref)
    session = get_session(conn, change["id"], session_ref, attempt)
    assignments = ", ".join(f"{column} = ?" for column in updates)
    with transaction(conn):
        conn.execute(f"UPDATE sessions SET {assignments} WHERE id = ?", (*updates.values(), session["id"]))
    return session_dict(conn, session["id"])


# --- incidents -------------------------------------------------------------


def incident_dict(conn: sqlite3.Connection, incident_id: int) -> dict:
    r = conn.execute(
        """
        SELECT i.*, s.session_ref, s.attempt, c.ref AS change_ref
        FROM incidents i
        JOIN changes c ON c.id = i.change_id
        LEFT JOIN sessions s ON s.id = i.session_id
        WHERE i.id = ?
        """,
        (incident_id,),
    ).fetchone()
    return {
        "id": r["id"],
        "change": r["change_ref"],
        "session": r["session_ref"],
        "attempt": r["attempt"],
        "code": r["code"],
        "role": r["role"],
        "severity": r["severity"],
        "task_ref": r["task_ref"],
        "detected_by": r["detected_by"],
        "description": r["description"],
        "evidence": r["evidence"],
        "created_at": r["created_at"],
        "voided_at": r["voided_at"],
        "void_reason": r["void_reason"],
    }


def add_incident(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    ref: str,
    code: str,
    severity: str,
    detected_by: str,
    description: str,
    evidence: str,
    session_ref: str | None = None,
    attempt: int | None = None,
    task_ref: str | None = None,
    role: str | None = None,
    now: str | None = None,
) -> dict:
    role = taxonomy.resolve_role(code, role)
    taxonomy.validate_choice("severity", severity, taxonomy.SEVERITIES)
    taxonomy.validate_choice("detected_by", detected_by, taxonomy.DETECTED_BY)
    description = _required_text("desc", description)
    evidence = _required_text("evidence", evidence, hint="no evidence, no incident")
    change = get_change(conn, project_id, ref)
    session_id = None
    if session_ref is not None:
        session_id = get_session(conn, change["id"], session_ref, attempt)["id"]
    elif attempt is not None:
        raise ChanchiError("invalid_value", "--attempt requires --session", field="attempt")
    if role == "executor" and session_id is None:
        raise ChanchiError(
            "invalid_value",
            f"{code} is an executor incident and requires --session",
            field="session",
        )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO incidents (change_id, session_id, code, role, severity, task_ref, "
            "detected_by, description, evidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                change["id"],
                session_id,
                code,
                role,
                severity,
                (task_ref or "").strip() or None,
                detected_by,
                description,
                evidence,
                now or utc_now(),
            ),
        )
    return incident_dict(conn, cursor.lastrowid)


def void_incident(
    conn: sqlite3.Connection, *, incident_id: int, reason: str, now: str | None = None
) -> dict:
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if row is None:
        raise ChanchiError("invalid_value", f"incident {incident_id} does not exist", field="id")
    if row["voided_at"] is not None:
        raise ChanchiError("invalid_value", f"incident {incident_id} is already voided", field="id")
    reason = _required_text("reason", reason)
    with transaction(conn):
        conn.execute(
            "UPDATE incidents SET voided_at = ?, void_reason = ? WHERE id = ?",
            (now or utc_now(), reason, incident_id),
        )
    return incident_dict(conn, incident_id)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_record.py -v`
Expected: 16 passed.

- [ ] **Step 5: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: 68 passed.

```bash
git add src/chanchi/record.py tests/test_record.py
git commit -m "feat: record changes, sessions and incidents

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Scoring — session/change scores, records and stats

**Recommended model:** sonnet

**Files:**
- Create: `src/chanchi/scoring.py`, `tests/helpers.py`
- Modify: `tests/conftest.py` (append the `recorder` fixture)
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `taxonomy.*`, `modelspec.format_spec`, `timeutil.parse`, `record.*` (tests only via `Recorder`).
- Produces (`chanchi.scoring`):
  - `session_score(verdict: str | None, incidents: list[dict]) -> float | None` — incidents are dicts with `code, role, severity, detected_by`.
  - `planner_change_score(tasks: int, incidents: list[dict]) -> float`
  - `smoothed(mean: float, n: int, prior: float) -> float`
  - `executor_records(conn, *, project_id=None, since=None) -> list[dict]` — each record has keys `id, change_id, session_ref, attempt, retry_reason, effort, task_type, complexity, tasks_total, started_at, ended_at, verdict, agent, model, cost_tier, project, project_id, score, clean, honesty_flags, failed_attempt, duration_s, codes`.
  - `prior_for(records: list[dict], task_type: str | None = None, complexity: str | None = None) -> float`
  - `summarize(records: list[dict], prior: float) -> dict` — keys `n, mean_score, smoothed_score, prior, confidence, clean_rate, first_attempt_acceptance, honesty_flags_per_session, red_flag, retry_rate, mean_duration_s, top_codes`.
  - `planner_records(conn, *, project_id=None, since=None) -> list[dict]`
  - `stats(conn, *, role="executor", by="model", project_id=None, since=None) -> dict` — keys `role, by, rows`.
- Produces (`tests/helpers.py`): `inc(code, severity="low", detected_by="planner_audit", role=None) -> dict`, class `Recorder(conn)` with `change(ref, planner="claude:opus:xhigh", kind="openspec") -> dict`, property `pid -> int`, and `session(ref, session_ref, executor, *, task_type="ui-component", complexity="medium", tasks=5, verdict="accepted", status="COMPLETE", retry_reason=None, started="2026-10-01T10:00:00Z", ended="2026-10-01T11:00:00Z", incidents=()) -> dict`.
- Produces (`tests/conftest.py`): fixture `recorder` (a `Recorder` over `seeded`, inside `git_repo`).

- [ ] **Step 1: Create `tests/helpers.py`**

```python
"""Test helpers to build realistic audit histories quickly."""

from chanchi import projects, record


def inc(code, severity="low", detected_by="planner_audit", role=None):
    data = {
        "code": code,
        "severity": severity,
        "detected_by": detected_by,
        "description": f"{code} observed",
        "evidence": "test evidence",
    }
    if role is not None:
        data["role"] = role
    return data


class Recorder:
    def __init__(self, conn):
        self.conn = conn

    def change(self, ref, planner="claude:opus:xhigh", kind="openspec"):
        slug, path = projects.identify()
        return record.open_change(
            self.conn, project_slug=slug, project_path=path, ref=ref, kind=kind, planner=planner
        )

    @property
    def pid(self):
        return projects.resolve_project(self.conn)["id"]

    def session(
        self,
        ref,
        session_ref,
        executor,
        *,
        task_type="ui-component",
        complexity="medium",
        tasks=5,
        verdict="accepted",
        status="COMPLETE",
        retry_reason=None,
        started="2026-10-01T10:00:00Z",
        ended="2026-10-01T11:00:00Z",
        incidents=(),
    ):
        pid = self.pid
        created = record.start_session(
            self.conn,
            project_id=pid,
            ref=ref,
            session_ref=session_ref,
            executor=executor,
            task_type=task_type,
            complexity=complexity,
            tasks_total=tasks,
            retry_reason=retry_reason,
            now=started,
        )
        if status is not None:
            record.report_session(
                self.conn, project_id=pid, ref=ref, session_ref=session_ref, status=status, now=ended
            )
        for incident in incidents:
            record.add_incident(self.conn, project_id=pid, ref=ref, session_ref=session_ref, **incident)
        if verdict is not None:
            record.audit_session(self.conn, project_id=pid, ref=ref, session_ref=session_ref, verdict=verdict)
        return created
```

- [ ] **Step 2: Append the `recorder` fixture to `tests/conftest.py`**

```python


@pytest.fixture
def recorder(seeded, git_repo):
    from helpers import Recorder

    return Recorder(seeded)
```

- [ ] **Step 3: Write the failing tests `tests/test_scoring.py`**

```python
import pytest
from helpers import inc

from chanchi import record, scoring
from chanchi.errors import ChanchiError

FLASH = "agy:gemini-3.8-flash-high:high"
SONNET = "claude:sonnet:medium"


def i(code, severity="low", detected_by="planner_audit", role=None):
    from chanchi import taxonomy

    return {"code": code, "role": role or taxonomy.resolve_role(code, None), "severity": severity,
            "detected_by": detected_by}


# --- pure scores -----------------------------------------------------------


def test_session_score_base_values():
    assert scoring.session_score(None, []) is None
    assert scoring.session_score("accepted", []) == 100
    assert scoring.session_score("accepted_with_fixes", []) == 70
    assert scoring.session_score("rejected", []) == 0


def test_session_score_penalties_and_credit():
    assert scoring.session_score("accepted_with_fixes", [i("rule_violation", "medium")]) == pytest.approx(67)
    late = [i("false_claim", "high", detected_by="post_merge")]
    assert scoring.session_score("accepted", late) == pytest.approx(86.5)
    assert scoring.session_score("rejected", [i("correct_stop")]) == pytest.approx(5)
    assert scoring.session_score("accepted", [i("correct_stop"), i("correct_stop")]) == 100
    assert scoring.session_score("accepted", [i("plan_gap", "blocking")]) == 100
    assert scoring.session_score("accepted", [i("hallucination", "high", role="planner")]) == 100
    assert scoring.session_score("accepted", [i("hallucination", "high", role="executor")]) == pytest.approx(91)


def test_planner_change_score():
    assert scoring.planner_change_score(74, [i("plan_wrong_expectation")]) == pytest.approx(99.3243, abs=1e-4)
    assert scoring.planner_change_score(5, [i("plan_gap", "blocking")]) == pytest.approx(50)
    assert scoring.planner_change_score(20, [i("hallucination", "high", role="planner")]) == pytest.approx(77.5)
    assert scoring.planner_change_score(20, [i("hallucination", "high", role="executor")]) == 100
    assert scoring.planner_change_score(1, [i("plan_delegated_decision", "blocking")] * 3) == 0


def test_smoothed():
    assert scoring.smoothed(100, 1, 70) == pytest.approx(77.5)
    assert scoring.smoothed(80, 0, 70) == pytest.approx(70)


# --- records ---------------------------------------------------------------


def test_executor_records_basic_fields(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, incidents=[inc("rule_violation", "medium"), inc("correct_stop")])
    recorder.session("c1", "S2", FLASH, verdict=None)
    records = scoring.executor_records(recorder.conn)
    assert len(records) == 1
    rec = records[0]
    assert rec["score"] == 100  # 100 - 3 (rule_violation medium) + 5 (correct_stop), clamped
    assert rec["clean"] is False
    assert rec["honesty_flags"] == 0
    assert rec["duration_s"] == 3600
    assert rec["codes"] == ["rule_violation", "correct_stop"]
    assert (rec["agent"], rec["model"], rec["effort"], rec["cost_tier"]) == ("agy", "gemini-3.8-flash-high", "high", 1)


def test_superseded_attempts(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, verdict="rejected")
    recorder.session("c1", "S1", FLASH, retry_reason="human_change")
    recorder.session("c1", "S2", FLASH, verdict="rejected")
    recorder.session("c1", "S2", FLASH, retry_reason="executor_failure")
    records = scoring.executor_records(recorder.conn)
    keys = sorted((r["session_ref"], r["attempt"], r["failed_attempt"]) for r in records)
    assert keys == [("S1", 2, False), ("S2", 1, True), ("S2", 2, False)]


def test_voided_incidents_are_ignored(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, incidents=[inc("false_claim", "high")])
    incident_id = recorder.conn.execute("SELECT id FROM incidents").fetchone()[0]
    assert scoring.executor_records(recorder.conn)[0]["score"] == pytest.approx(91)
    record.void_incident(recorder.conn, incident_id=incident_id, reason="re-run passed")
    assert scoring.executor_records(recorder.conn)[0]["score"] == 100


def test_since_filter(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, started="2026-08-01T10:00:00Z", ended="2026-08-01T11:00:00Z")
    recorder.session("c1", "S2", FLASH)
    assert len(scoring.executor_records(recorder.conn, since="2026-09-01T00:00:00Z")) == 1


def test_summarize_metrics(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH)
    recorder.session("c1", "S2", FLASH, verdict="accepted_with_fixes", incidents=[inc("false_claim")])
    recorder.session("c1", "S3", FLASH, verdict="rejected")
    recorder.session("c1", "S3", FLASH, retry_reason="executor_failure")
    records = scoring.executor_records(recorder.conn)
    summary = scoring.summarize(records, prior=70)
    assert summary["n"] == 4
    assert summary["mean_score"] == pytest.approx((100 + 67 + 0 + 100) / 4)
    assert summary["clean_rate"] == pytest.approx(0.5)
    assert summary["first_attempt_acceptance"] == pytest.approx(2 / 3, abs=1e-3)
    assert summary["honesty_flags_per_session"] == pytest.approx(0.25)
    assert summary["red_flag"] is True
    assert summary["retry_rate"] == pytest.approx(0.25)
    assert summary["confidence"] == "low"
    assert summary["top_codes"] == ["false_claim"]


def test_summarize_empty():
    summary = scoring.summarize([], prior=80)
    assert summary["n"] == 0
    assert summary["mean_score"] is None
    assert summary["smoothed_score"] == 80
    assert summary["confidence"] == "insufficient"
    assert summary["red_flag"] is False
    assert summary["top_codes"] == []


def test_prior_fallbacks(recorder):
    assert scoring.prior_for([]) == 70
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, task_type="tests", complexity="low", verdict="accepted_with_fixes")
    records = scoring.executor_records(recorder.conn)
    assert scoring.prior_for(records, "tests", "low") == 70
    assert scoring.prior_for(records, "ui-component", "medium") == 70
    recorder.session("c1", "S2", FLASH)
    records = scoring.executor_records(recorder.conn)
    assert scoring.prior_for(records, "ui-component", "medium") == 100
    assert scoring.prior_for(records, "docs", "high") == pytest.approx(85)


# --- stats -----------------------------------------------------------------


def test_executor_stats_by_model(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH)
    recorder.session("c1", "S2", FLASH, verdict="accepted_with_fixes", incidents=[inc("rule_violation", "medium")])
    recorder.session("c1", "S3", SONNET)
    result = scoring.stats(recorder.conn, role="executor", by="model")
    assert result["role"] == "executor" and result["by"] == "model"
    rows = result["rows"]
    assert [r["spec"] for r in rows] == [SONNET, FLASH]
    assert rows[0]["smoothed_score"] == pytest.approx(91.75)
    assert rows[1]["smoothed_score"] == pytest.approx(86.8)
    assert rows[1]["cost_tier"] == 1


def test_executor_stats_by_task_type_and_project(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, task_type="tests", complexity="low")
    recorder.session("c1", "S2", FLASH)
    by_type = scoring.stats(recorder.conn, by="task-type")["rows"]
    assert sorted((r["task_type"], r["complexity"]) for r in by_type) == [("tests", "low"), ("ui-component", "medium")]
    by_project = scoring.stats(recorder.conn, by="project")["rows"]
    assert by_project[0]["project"] == "demo-app" and by_project[0]["n"] == 2
    with pytest.raises(ChanchiError) as info:
        scoring.stats(recorder.conn, by="color")
    assert info.value.field == "by"
    with pytest.raises(ChanchiError) as info:
        scoring.stats(recorder.conn, role="robot")
    assert info.value.field == "role"


def test_planner_stats(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, tasks=10)
    record.add_incident(recorder.conn, project_id=recorder.pid, ref="c1", **inc("plan_gap", "blocking", "executor_stop"))
    recorder.change("c2")
    recorder.session("c2", "S1", FLASH, verdict=None)
    recorder.change("c3", planner="human", kind="adhoc")
    recorder.session("c3", "S1", FLASH)
    planners = scoring.planner_records(recorder.conn)
    assert [(p["ref"], p["score"]) for p in planners] == [("c1", pytest.approx(50))]
    rows = scoring.stats(recorder.conn, role="planner", by="model")["rows"]
    assert rows[0]["spec"] == "claude:opus:xhigh"
    assert rows[0]["n"] == 1 and rows[0]["mean_score"] == pytest.approx(50)
    assert rows[0]["plan_incidents_per_change"] == 1
    with pytest.raises(ChanchiError) as info:
        scoring.stats(recorder.conn, role="planner", by="task-type")
    assert info.value.valid_values == ["model", "project"]


def test_planner_tasks_use_latest_attempt(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, tasks=4, verdict="rejected")
    recorder.session("c1", "S1", FLASH, tasks=20, retry_reason="executor_failure")
    assert scoring.planner_records(recorder.conn)[0]["tasks"] == 20


def test_human_stats(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, incidents=[inc("correct_stop", detected_by="executor_stop")])
    pid = recorder.pid
    record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("plan_gap", "high", "executor_stop"))
    record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("human_unclear_requirement", "high", "executor_stop"))
    record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("human_scope_addition", "medium", "human"))
    rows = scoring.stats(recorder.conn, role="human")["rows"]
    assert rows == [
        {
            "project": "demo-app",
            "human_incidents": {"human_unclear_requirement": 1, "human_scope_addition": 1},
            "stops_total": 2,
            "stops_by_human": 1,
            "human_stop_share": 0.5,
        }
    ]
```

- [ ] **Step 4: Run to verify failure**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: FAIL with `ImportError: cannot import name 'scoring'`.

- [ ] **Step 5: Implement `src/chanchi/scoring.py`**

```python
"""Read side: scores, stats and recommendations. Never writes; scores are never stored."""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict

from chanchi import taxonomy as tx
from chanchi.modelspec import format_spec
from chanchi.timeutil import parse as parse_ts

EXECUTOR_GROUPINGS = {
    "model": ("agent", "model", "effort"),
    "task-type": ("agent", "model", "effort", "task_type", "complexity"),
    "project": ("project", "agent", "model", "effort"),
}
PLANNER_GROUPINGS = {
    "model": ("agent", "model", "effort"),
    "project": ("project", "agent", "model", "effort"),
}
STATS_ROLES = ("executor", "planner", "human")


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _penalty(incidents: list[dict], weights: dict) -> float:
    total = 0.0
    for incident in incidents:
        weight = weights.get(incident["code"])
        if weight is None:
            continue
        late = tx.LATE_DETECTION_MULT if incident["detected_by"] in tx.LATE_DETECTION else 1.0
        total += weight * tx.SEVERITY_MULT[incident["severity"]] * late
    return total


def session_score(verdict: str | None, incidents: list[dict]) -> float | None:
    if verdict is None:
        return None
    executor = [i for i in incidents if i["role"] == "executor"]
    penalty = _penalty([i for i in executor if i["code"] != "correct_stop"], tx.EXECUTOR_WEIGHTS)
    credit = tx.CORRECT_STOP_CREDIT * sum(1 for i in executor if i["code"] == "correct_stop")
    return _clamp(tx.VERDICT_BASE[verdict] - penalty + credit)


def planner_change_score(tasks: int, incidents: list[dict]) -> float:
    planner = [i for i in incidents if i["role"] == "planner"]
    density = _penalty(planner, tx.PLANNER_WEIGHTS) / max(tasks, tx.PLANNER_MIN_TASKS) * 10
    return _clamp(100 - tx.PLANNER_DENSITY_FACTOR * density)


def smoothed(mean: float, n: int, prior: float) -> float:
    return (n * mean + tx.SMOOTHING_K * prior) / (n + tx.SMOOTHING_K)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


# --- executor --------------------------------------------------------------

_SESSIONS_SQL = """
SELECT s.id, s.change_id, s.session_ref, s.attempt, s.retry_reason, s.executor_effort AS effort,
       s.task_type, s.complexity, s.tasks_total, s.started_at, s.ended_at, s.verdict,
       m.agent, m.model, m.cost_tier, p.slug AS project, p.id AS project_id
FROM sessions s
JOIN changes c ON c.id = s.change_id
JOIN models m ON m.id = s.executor_model_id
JOIN projects p ON p.id = c.project_id
ORDER BY s.id
"""


def _incidents_by(conn: sqlite3.Connection, column: str) -> dict:
    grouped: dict = defaultdict(list)
    for row in conn.execute(
        f"SELECT {column}, code, role, severity, detected_by FROM incidents "
        f"WHERE voided_at IS NULL AND {column} IS NOT NULL ORDER BY id"
    ):
        grouped[row[column]].append(
            {"code": row["code"], "role": row["role"], "severity": row["severity"],
             "detected_by": row["detected_by"]}
        )
    return grouped


def executor_records(
    conn: sqlite3.Connection, *, project_id: int | None = None, since: str | None = None
) -> list[dict]:
    """One record per audited session that is not superseded by a non-executor retry."""
    incidents = _incidents_by(conn, "session_id")
    rows = [dict(r) for r in conn.execute(_SESSIONS_SQL)]
    next_reason = {(r["change_id"], r["session_ref"], r["attempt"] - 1): r["retry_reason"] for r in rows}
    records = []
    for r in rows:
        reason_after = next_reason.get((r["change_id"], r["session_ref"], r["attempt"]))
        if reason_after in tx.NON_EXECUTOR_RETRY_REASONS or r["verdict"] is None:
            continue
        if project_id is not None and r["project_id"] != project_id:
            continue
        if since is not None and r["started_at"] < since:
            continue
        session_incidents = incidents.get(r["id"], [])
        executor = [i for i in session_incidents if i["role"] == "executor"]
        r["score"] = session_score(r["verdict"], session_incidents)
        r["clean"] = r["verdict"] == "accepted" and not any(
            i["code"] != "correct_stop" and i["severity"] in tx.CLEAN_BLOCKING_SEVERITIES for i in executor
        )
        r["honesty_flags"] = sum(1 for i in executor if i["code"] in tx.HONESTY_CODES)
        r["failed_attempt"] = reason_after == "executor_failure"
        r["duration_s"] = (
            (parse_ts(r["ended_at"]) - parse_ts(r["started_at"])).total_seconds() if r["ended_at"] else None
        )
        r["codes"] = [i["code"] for i in executor]
        records.append(r)
    return records


def prior_for(records: list[dict], task_type: str | None = None, complexity: str | None = None) -> float:
    subset = [
        r["score"]
        for r in records
        if (task_type is None or r["task_type"] == task_type)
        and (complexity is None or r["complexity"] == complexity)
    ]
    for candidate in (_mean(subset), _mean([r["score"] for r in records])):
        if candidate is not None:
            return candidate
    return tx.DEFAULT_PRIOR


def _top_codes(codes) -> list[str]:
    return [code for code, _ in Counter(codes).most_common(3)]


def summarize(records: list[dict], prior: float) -> dict:
    n = len(records)
    if n == 0:
        return {
            "n": 0, "mean_score": None, "smoothed_score": round(prior, 2), "prior": round(prior, 2),
            "confidence": tx.confidence(0), "clean_rate": None, "first_attempt_acceptance": None,
            "honesty_flags_per_session": None, "red_flag": False, "retry_rate": None,
            "mean_duration_s": None, "top_codes": [],
        }
    mean = sum(r["score"] for r in records) / n
    first = [r for r in records if r["attempt"] == 1]
    accepted_first = sum(
        1 for r in first if r["verdict"] in ("accepted", "accepted_with_fixes") and not r["failed_attempt"]
    )
    durations = [r["duration_s"] for r in records if r["duration_s"] is not None]
    honesty = sum(r["honesty_flags"] for r in records) / n
    return {
        "n": n,
        "mean_score": round(mean, 2),
        "smoothed_score": round(smoothed(mean, n, prior), 2),
        "prior": round(prior, 2),
        "confidence": tx.confidence(n),
        "clean_rate": round(sum(1 for r in records if r["clean"]) / n, 3),
        "first_attempt_acceptance": round(accepted_first / len(first), 3) if first else None,
        "honesty_flags_per_session": round(honesty, 3),
        "red_flag": honesty > tx.HONESTY_RED_FLAG,
        "retry_rate": round(sum(1 for r in records if r["failed_attempt"]) / n, 3),
        "mean_duration_s": round(sum(durations) / len(durations), 1) if durations else None,
        "top_codes": _top_codes(code for r in records for code in r["codes"]),
    }


def _executor_stats(conn, by, project_id, since) -> list[dict]:
    tx.validate_choice("by", by, EXECUTOR_GROUPINGS)
    records = executor_records(conn, project_id=project_id, since=since)
    keys = EXECUTOR_GROUPINGS[by]
    groups: dict = defaultdict(list)
    for r in records:
        groups[tuple(r[k] for k in keys)].append(r)
    rows = []
    for key, members in groups.items():
        entry = dict(zip(keys, key))
        entry["spec"] = format_spec(entry["agent"], entry["model"], entry["effort"])
        entry["cost_tier"] = members[0]["cost_tier"]
        entry.update(summarize(members, prior_for(records, entry.get("task_type"), entry.get("complexity"))))
        rows.append(entry)
    rows.sort(key=lambda e: (-e["smoothed_score"], e["spec"], e.get("project") or "", e.get("task_type") or ""))
    return rows


# --- planner ---------------------------------------------------------------


def planner_records(
    conn: sqlite3.Connection, *, project_id: int | None = None, since: str | None = None
) -> list[dict]:
    """One record per change with at least one audited session, excluding human planners."""
    tasks = {
        r["change_id"]: r["tasks"]
        for r in conn.execute(
            """
            SELECT s.change_id, SUM(s.tasks_total) AS tasks
            FROM sessions s
            JOIN (SELECT change_id, session_ref, MAX(attempt) AS attempt
                  FROM sessions GROUP BY change_id, session_ref) latest
              ON latest.change_id = s.change_id AND latest.session_ref = s.session_ref
             AND latest.attempt = s.attempt
            GROUP BY s.change_id
            """
        )
    }
    audited = {r[0] for r in conn.execute("SELECT DISTINCT change_id FROM sessions WHERE verdict IS NOT NULL")}
    incidents = _incidents_by(conn, "change_id")
    records = []
    for r in conn.execute(
        """
        SELECT c.id AS change_id, c.ref, c.opened_at, c.planner_effort AS effort,
               m.agent, m.model, m.cost_tier, p.slug AS project, p.id AS project_id
        FROM changes c
        JOIN models m ON m.id = c.planner_model_id
        JOIN projects p ON p.id = c.project_id
        ORDER BY c.id
        """
    ):
        r = dict(r)
        if r["agent"] in tx.PLANNER_ONLY_AGENTS or r["change_id"] not in audited:
            continue
        if project_id is not None and r["project_id"] != project_id:
            continue
        if since is not None and r["opened_at"] < since:
            continue
        planner_incidents = [i for i in incidents.get(r["change_id"], []) if i["role"] == "planner"]
        r["tasks"] = tasks.get(r["change_id"], 0)
        r["score"] = planner_change_score(r["tasks"], planner_incidents)
        r["incident_count"] = len(planner_incidents)
        r["codes"] = [i["code"] for i in planner_incidents]
        records.append(r)
    return records


def _planner_stats(conn, by, project_id, since) -> list[dict]:
    tx.validate_choice("by", by, PLANNER_GROUPINGS)
    records = planner_records(conn, project_id=project_id, since=since)
    prior = _mean([r["score"] for r in records])
    prior = tx.DEFAULT_PRIOR if prior is None else prior
    keys = PLANNER_GROUPINGS[by]
    groups: dict = defaultdict(list)
    for r in records:
        groups[tuple(r[k] for k in keys)].append(r)
    rows = []
    for key, members in groups.items():
        n = len(members)
        mean = sum(m["score"] for m in members) / n
        entry = dict(zip(keys, key))
        entry["spec"] = format_spec(entry["agent"], entry["model"], entry["effort"])
        entry.update(
            {
                "n": n,
                "mean_score": round(mean, 2),
                "smoothed_score": round(smoothed(mean, n, prior), 2),
                "prior": round(prior, 2),
                "confidence": tx.confidence(n),
                "plan_incidents_per_change": round(sum(m["incident_count"] for m in members) / n, 3),
                "top_codes": _top_codes(code for m in members for code in m["codes"]),
            }
        )
        rows.append(entry)
    rows.sort(key=lambda e: (-e["smoothed_score"], e["spec"], e.get("project") or ""))
    return rows


# --- human -----------------------------------------------------------------


def _human_stats(conn, project_id, since) -> list[dict]:
    query = (
        "SELECT i.code, i.role, i.detected_by, p.slug AS project FROM incidents i "
        "JOIN changes c ON c.id = i.change_id JOIN projects p ON p.id = c.project_id "
        "WHERE i.voided_at IS NULL"
    )
    params: list = []
    if project_id is not None:
        query += " AND p.id = ?"
        params.append(project_id)
    if since is not None:
        query += " AND i.created_at >= ?"
        params.append(since)
    per_project: dict = defaultdict(list)
    for row in conn.execute(query + " ORDER BY i.id", params):
        per_project[row["project"]].append(dict(row))
    rows = []
    for project in sorted(per_project):
        incidents = per_project[project]
        stops = [i for i in incidents if i["detected_by"] == "executor_stop" and i["code"] != "correct_stop"]
        human_stops = sum(1 for i in stops if i["role"] == "human")
        rows.append(
            {
                "project": project,
                "human_incidents": dict(Counter(i["code"] for i in incidents if i["role"] == "human")),
                "stops_total": len(stops),
                "stops_by_human": human_stops,
                "human_stop_share": round(human_stops / len(stops), 3) if stops else None,
            }
        )
    return rows


def stats(
    conn: sqlite3.Connection,
    *,
    role: str = "executor",
    by: str = "model",
    project_id: int | None = None,
    since: str | None = None,
) -> dict:
    tx.validate_choice("role", role, STATS_ROLES)
    if role == "executor":
        rows = _executor_stats(conn, by, project_id, since)
    elif role == "planner":
        rows = _planner_stats(conn, by, project_id, since)
    else:
        rows = _human_stats(conn, project_id, since)
    return {"role": role, "by": by if role != "human" else "project", "rows": rows}
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: 16 passed.

- [ ] **Step 7: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: 84 passed.

```bash
git add src/chanchi/scoring.py tests/helpers.py tests/conftest.py tests/test_scoring.py
git commit -m "feat: compute session, change and aggregate scores

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Scoring — recommend, show and explain

**Recommended model:** sonnet

**Files:**
- Modify: `src/chanchi/scoring.py` (append)
- Test: `tests/test_scoring.py` (append)

**Interfaces:**
- Consumes: everything in `scoring` from Task 6, `catalog.resolve_model`, `catalog.require_task_type`, `record.get_change`, `record.change_dict`, `record.session_dict`, `record.incident_dict`.
- Produces (`chanchi.scoring`):
  - `LEVELS` — `(("task_type+complexity", True, True), ("task_type", True, False), ("complexity", False, True), ("global", False, False))`.
  - `recommend(conn, *, task_type: str, complexity: str, available: list[str]) -> dict` — keys `task_type, complexity, recommendation (dict|None: spec, cost_tier, smoothed_score, confidence, level), reason (None|"insufficient_data"|"all_candidates_red_flagged"), window, candidates (list)`. Each candidate has `spec, agent, model, effort, cost_tier, level` plus every `summarize` key.
  - `show_change(conn, *, project_id: int, ref: str) -> dict` — keys `change, sessions (each session_dict + "score"), incidents (all, including voided), planner_score (float|None), incident_counts_by_role`.
  - `explain() -> dict`.

- [ ] **Step 1: Append the failing tests to `tests/test_scoring.py`**

```python


# --- recommend -------------------------------------------------------------


def test_recommend_without_data(recorder):
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    assert result["recommendation"] is None
    assert result["reason"] == "insufficient_data"
    assert [c["level"] for c in result["candidates"]] == [None, None]
    assert all(c["n"] == 0 for c in result["candidates"])


def test_recommend_prefers_cheapest_within_window(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, SONNET)
    recorder.session("c1", "S4", FLASH)
    recorder.session("c1", "S5", FLASH)
    recorder.session("c1", "S6", FLASH, incidents=[inc("rule_violation")])
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[SONNET, FLASH])
    by_spec = {c["spec"]: c for c in result["candidates"]}
    assert by_spec[SONNET]["smoothed_score"] == pytest.approx(99.88, abs=0.01)
    assert by_spec[FLASH]["smoothed_score"] == pytest.approx(99.62, abs=0.01)
    assert result["candidates"][0]["spec"] == SONNET
    assert result["recommendation"]["spec"] == FLASH
    assert result["recommendation"]["level"] == "task_type+complexity"
    assert result["reason"] is None


def test_recommend_outside_window_picks_best(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, SONNET)
    for ref in ("S4", "S5", "S6"):
        recorder.session("c1", ref, FLASH, verdict="accepted_with_fixes")
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    by_spec = {c["spec"]: c for c in result["candidates"]}
    assert by_spec[FLASH]["smoothed_score"] == pytest.approx(77.5)
    assert by_spec[SONNET]["smoothed_score"] == pytest.approx(92.5)
    assert result["recommendation"]["spec"] == SONNET


def test_recommend_excludes_red_flagged(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, FLASH, incidents=[inc("false_claim")])
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    flash = next(c for c in result["candidates"] if c["spec"] == FLASH)
    assert flash["red_flag"] is True and flash["confidence"] == "low"
    assert result["recommendation"] is None
    assert result["reason"] == "all_candidates_red_flagged"


def test_recommend_fallback_levels(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, FLASH, complexity="high")
    recorder.session("c1", "S4", SONNET, task_type="docs", complexity="medium")
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, SONNET])
    by_spec = {c["spec"]: c for c in result["candidates"]}
    assert by_spec[FLASH]["level"] == "task_type"
    assert by_spec[FLASH]["n"] == 3
    assert by_spec[SONNET]["level"] == "complexity"
    assert by_spec[SONNET]["confidence"] == "insufficient"
    assert result["recommendation"]["spec"] == FLASH


def test_recommend_matches_effort_exactly(recorder):
    recorder.change("c1")
    for ref in ("S1", "S2", "S3"):
        recorder.session("c1", ref, FLASH)
    result = scoring.recommend(
        recorder.conn, task_type="ui-component", complexity="medium", available=["agy:gemini-3.8-flash-high:medium"]
    )
    assert result["candidates"][0]["n"] == 0


def test_recommend_validations(recorder):
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=["claude:gpt-9"])
    assert info.value.code == "unknown_model"
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=["human"])
    assert info.value.field == "executor"
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[])
    assert info.value.field == "available"
    with pytest.raises(ChanchiError) as info:
        scoring.recommend(recorder.conn, task_type="nope", complexity="medium", available=[FLASH])
    assert info.value.field == "task_type"


def test_recommend_deduplicates_candidates(recorder):
    result = scoring.recommend(recorder.conn, task_type="ui-component", complexity="medium", available=[FLASH, FLASH])
    assert len(result["candidates"]) == 1


# --- show / explain --------------------------------------------------------


def test_show_change(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, tasks=10, incidents=[inc("correct_stop", detected_by="executor_stop")])
    pid = recorder.pid
    gap = record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("plan_gap", "blocking", "executor_stop"))
    extra = record.add_incident(recorder.conn, project_id=pid, ref="c1", **inc("plan_conflict", "high"))
    record.void_incident(recorder.conn, incident_id=extra["id"], reason="duplicate of the gap")
    shown = scoring.show_change(recorder.conn, project_id=pid, ref="c1")
    assert shown["change"]["ref"] == "c1"
    assert shown["sessions"][0]["score"] == 100
    assert [i["id"] for i in shown["incidents"]] == [1, gap["id"], extra["id"]]
    assert shown["incidents"][-1]["voided_at"] is not None
    assert shown["planner_score"] == pytest.approx(50)
    assert shown["incident_counts_by_role"] == {"executor": 1, "planner": 1}


def test_show_change_without_audit_has_no_planner_score(recorder):
    recorder.change("c1")
    recorder.session("c1", "S1", FLASH, verdict=None)
    assert scoring.show_change(recorder.conn, project_id=recorder.pid, ref="c1")["planner_score"] is None


def test_explain_reflects_taxonomy():
    from chanchi import taxonomy

    explained = scoring.explain()
    assert explained["executor_session_score"]["weights"] == taxonomy.EXECUTOR_WEIGHTS
    assert explained["planner_change_score"]["weights"] == taxonomy.PLANNER_WEIGHTS
    assert explained["severity_multipliers"] == taxonomy.SEVERITY_MULT
    assert explained["smoothing"]["k"] == 3
    assert explained["recommendation"]["window"] == 5.0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: the 11 new tests FAIL with `AttributeError: module 'chanchi.scoring' has no attribute 'recommend'` (or `show_change` / `explain`); the 16 earlier tests still pass.

- [ ] **Step 3: Append to `src/chanchi/scoring.py`**

Add these imports to the existing import block at the top of the file (keep alphabetical order):

```python
from chanchi import catalog, record
from chanchi.errors import ChanchiError
```

Then append at the end of the file:

```python


# --- recommend -------------------------------------------------------------

LEVELS = (
    ("task_type+complexity", True, True),
    ("task_type", True, False),
    ("complexity", False, True),
    ("global", False, False),
)


def _level_subset(records, task_type, complexity, use_type, use_complexity):
    return [
        r
        for r in records
        if (not use_type or r["task_type"] == task_type)
        and (not use_complexity or r["complexity"] == complexity)
    ]


def recommend(
    conn: sqlite3.Connection, *, task_type: str, complexity: str, available: list[str]
) -> dict:
    catalog.require_task_type(conn, task_type)
    tx.validate_choice("complexity", complexity, tx.COMPLEXITIES)
    if not available:
        raise ChanchiError(
            "invalid_value",
            "--available must list at least one agent:model[:effort]",
            field="available",
            hint="take the list from the human's prompt; never assume availability",
        )
    records = executor_records(conn)
    candidates = []
    seen = set()
    for spec in available:
        row, effort = catalog.resolve_model(conn, spec, role="executor")
        key = (row["agent"], row["model"], effort)
        if key in seen:
            continue
        seen.add(key)
        own = [r for r in records if (r["agent"], r["model"], r["effort"]) == key]
        chosen = None
        for name, use_type, use_complexity in LEVELS:
            subset = _level_subset(own, task_type, complexity, use_type, use_complexity)
            if len(subset) >= tx.CONFIDENCE_LOW_MIN:
                chosen = (name, subset, use_type, use_complexity)
                break
        if chosen is None:
            for name, use_type, use_complexity in LEVELS:
                subset = _level_subset(own, task_type, complexity, use_type, use_complexity)
                if subset:
                    chosen = (name, subset, use_type, use_complexity)
                    break
        if chosen is None:
            level, subset = None, []
            prior = prior_for(records, task_type, complexity)
        else:
            level, subset, use_type, use_complexity = chosen
            prior = prior_for(
                records, task_type if use_type else None, complexity if use_complexity else None
            )
        entry = {
            "spec": format_spec(*key),
            "agent": key[0],
            "model": key[1],
            "effort": key[2],
            "cost_tier": row["cost_tier"],
            "level": level,
        }
        entry.update(summarize(subset, prior))
        candidates.append(entry)
    eligible = [c for c in candidates if c["confidence"] in ("low", "ok") and not c["red_flag"]]
    recommendation = None
    reason = None
    if eligible:
        best = max(c["smoothed_score"] for c in eligible)
        window = [c for c in eligible if c["smoothed_score"] >= best - tx.RECOMMEND_WINDOW]
        pick = min(window, key=lambda c: (c["cost_tier"], -c["smoothed_score"], c["spec"]))
        recommendation = {k: pick[k] for k in ("spec", "cost_tier", "smoothed_score", "confidence", "level")}
    elif any(c["confidence"] in ("low", "ok") for c in candidates):
        reason = "all_candidates_red_flagged"
    else:
        reason = "insufficient_data"
    candidates.sort(key=lambda c: (-c["smoothed_score"], c["spec"]))
    return {
        "task_type": task_type,
        "complexity": complexity,
        "recommendation": recommendation,
        "reason": reason,
        "window": tx.RECOMMEND_WINDOW,
        "candidates": candidates,
    }


# --- show / explain --------------------------------------------------------


def show_change(conn: sqlite3.Connection, *, project_id: int, ref: str) -> dict:
    change = record.get_change(conn, project_id, ref)
    by_session = _incidents_by(conn, "session_id")
    sessions = []
    for row in conn.execute("SELECT id, verdict FROM sessions WHERE change_id = ? ORDER BY id", (change["id"],)):
        entry = record.session_dict(conn, row["id"])
        score = session_score(row["verdict"], by_session.get(row["id"], []))
        entry["score"] = None if score is None else round(score, 2)
        sessions.append(entry)
    incidents = [
        record.incident_dict(conn, r["id"])
        for r in conn.execute("SELECT id FROM incidents WHERE change_id = ? ORDER BY id", (change["id"],))
    ]
    active = [i for i in incidents if i["voided_at"] is None]
    planner_score = None
    if any(s["verdict"] is not None for s in sessions):
        latest: dict = {}
        for s in sessions:
            latest[s["session"]] = s["tasks_total"]
        planner_score = round(planner_change_score(sum(latest.values()), active), 2)
    return {
        "change": record.change_dict(conn, change["id"]),
        "sessions": sessions,
        "incidents": incidents,
        "planner_score": planner_score,
        "incident_counts_by_role": dict(Counter(i["role"] for i in active)),
    }


def explain() -> dict:
    return {
        "executor_session_score": {
            "formula": "clamp(base - penalty + credit, 0, 100)",
            "base": tx.VERDICT_BASE,
            "weights": tx.EXECUTOR_WEIGHTS,
            "correct_stop_credit": tx.CORRECT_STOP_CREDIT,
        },
        "planner_change_score": {
            "formula": "clamp(100 - 5 * (penalty / max(tasks, 10) * 10), 0, 100)",
            "weights": tx.PLANNER_WEIGHTS,
            "density_factor": tx.PLANNER_DENSITY_FACTOR,
            "min_tasks": tx.PLANNER_MIN_TASKS,
        },
        "severity_multipliers": tx.SEVERITY_MULT,
        "late_detection": {"detected_by": list(tx.LATE_DETECTION), "multiplier": tx.LATE_DETECTION_MULT},
        "smoothing": {
            "formula": "(n * mean + k * prior) / (n + k)",
            "k": tx.SMOOTHING_K,
            "default_prior": tx.DEFAULT_PRIOR,
        },
        "confidence": {"insufficient": "n < 3", "low": "3 <= n < 10", "ok": "n >= 10"},
        "recommendation": {
            "levels": [name for name, _, _ in LEVELS],
            "window": tx.RECOMMEND_WINDOW,
            "honesty_red_flag_above": tx.HONESTY_RED_FLAG,
        },
        "retry_reasons_excluded_from_executor_metrics": list(tx.NON_EXECUTOR_RETRY_REASONS),
    }
```

Note on `show_change`: sessions are iterated in id order, so `latest[session_ref]` ends with the tasks of the latest attempt.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_scoring.py -v`
Expected: 27 passed.

- [ ] **Step 5: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: 95 passed.

```bash
git add src/chanchi/scoring.py tests/test_scoring.py
git commit -m "feat: recommend models and show change timelines

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Skills mirroring

**Recommended model:** sonnet

**Files:**
- Create: `src/chanchi/skills_link.py`
- Test: `tests/test_skills_link.py`

**Interfaces:**
- Consumes: `errors.ChanchiError`.
- Produces (`chanchi.skills_link`):
  - `SKILL_PREFIX = "chanchi-"`, `SUGGESTED_CONFIG_LINE: str`.
  - `repo_skills_dir() -> Path` — `<repo>/skills` (requires the editable install).
  - `available_skills(skills_dir: Path) -> list[str]`
  - `plan_targets(base: Path, *, global_: bool) -> tuple[Path, list[Path]]` — `(primary, secondaries)`.
  - `link(base: Path, *, global_: bool = False, skills_dir: Path | None = None) -> dict` — keys `base, skills, created, existing, suggested_config_line`; raises `link_conflict` after creating every non-conflicting link.
  - `unlink(base: Path, *, global_: bool = False, skills_dir: Path | None = None) -> dict` — keys `base, removed`.

- [ ] **Step 1: Write the failing tests `tests/test_skills_link.py`**

```python
import os

import pytest

from chanchi import skills_link
from chanchi.errors import ChanchiError


@pytest.fixture
def skills_dir(tmp_path):
    root = tmp_path / "repo" / "skills"
    for name in ("chanchi-a", "chanchi-b", "other"):
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n")
    (root / "chanchi-empty").mkdir()  # no SKILL.md: ignored
    return root


@pytest.fixture
def project(tmp_path):
    base = tmp_path / "project"
    base.mkdir()
    return base


def test_available_skills(skills_dir):
    assert skills_link.available_skills(skills_dir) == ["chanchi-a", "chanchi-b"]


def test_repo_skills_dir_points_at_repository():
    assert skills_link.repo_skills_dir().name == "skills"
    assert (skills_link.repo_skills_dir().parent / "pyproject.toml").exists()


def test_link_creates_primary_and_relative_secondary(project, skills_dir):
    result = skills_link.link(project, skills_dir=skills_dir)
    primary = project / ".agents" / "skills" / "chanchi-a"
    secondary = project / ".claude" / "skills" / "chanchi-a"
    assert os.readlink(primary) == str(skills_dir.resolve() / "chanchi-a")
    assert os.readlink(secondary) == os.path.join("..", "..", ".agents", "skills", "chanchi-a")
    assert secondary.resolve() == (skills_dir / "chanchi-a").resolve()
    assert result["skills"] == ["chanchi-a", "chanchi-b"]
    assert len(result["created"]) == 4
    assert result["existing"] == []
    assert "chanchi-session-audit" in result["suggested_config_line"]
    assert not (project / ".agent").exists()
    assert not (project / ".opencode").exists()


def test_link_is_idempotent(project, skills_dir):
    skills_link.link(project, skills_dir=skills_dir)
    again = skills_link.link(project, skills_dir=skills_dir)
    assert again["created"] == []
    assert len(again["existing"]) == 4


def test_link_reports_conflicts_without_overwriting(project, skills_dir):
    blocker = project / ".claude" / "skills" / "chanchi-a"
    blocker.mkdir(parents=True)
    with pytest.raises(ChanchiError) as info:
        skills_link.link(project, skills_dir=skills_dir)
    assert info.value.code == "link_conflict"
    assert str(blocker.resolve()) in info.value.message
    assert blocker.is_dir() and not blocker.is_symlink()
    assert (project / ".claude" / "skills" / "chanchi-b").is_symlink()


def test_global_link_adds_agy_cli_dir_only_when_present(tmp_path, skills_dir):
    home = tmp_path / "home"
    home.mkdir()
    skills_link.link(home, global_=True, skills_dir=skills_dir)
    assert not (home / ".gemini").exists()
    (home / ".gemini" / "antigravity-cli").mkdir(parents=True)
    result = skills_link.link(home, global_=True, skills_dir=skills_dir)
    agy = home / ".gemini" / "antigravity-cli" / "skills" / "chanchi-a"
    assert agy.is_symlink() and agy.resolve() == (skills_dir / "chanchi-a").resolve()
    assert len(result["created"]) == 2


def test_unlink_removes_only_own_links(project, skills_dir, tmp_path):
    skills_link.link(project, skills_dir=skills_dir)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    foreign = project / ".claude" / "skills" / "chanchi-zzz"
    foreign.symlink_to(elsewhere)
    plain = project / ".agents" / "skills" / "chanchi-plain"
    plain.mkdir()
    result = skills_link.unlink(project, skills_dir=skills_dir)
    assert len(result["removed"]) == 4
    assert foreign.is_symlink()
    assert plain.is_dir()
    assert not (project / ".agents" / "skills" / "chanchi-a").exists()


def test_unlink_removes_dangling_secondary(project, skills_dir):
    skills_link.link(project, skills_dir=skills_dir)
    (project / ".agents" / "skills" / "chanchi-a").unlink()
    result = skills_link.unlink(project, skills_dir=skills_dir)
    assert str(project.resolve() / ".claude" / "skills" / "chanchi-a") in result["removed"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills_link.py -v`
Expected: FAIL with `ImportError: cannot import name 'skills_link'`.

- [ ] **Step 3: Implement `src/chanchi/skills_link.py`**

```python
"""Mirror chanchi skills into projects (or ~) with symlinks. Never overwrites anything."""

from __future__ import annotations

import os
from pathlib import Path

from chanchi.errors import ChanchiError

SKILL_PREFIX = "chanchi-"
SUGGESTED_CONFIG_LINE = (
    "When assigning sessions use the `chanchi-model-selection` skill; when orchestrating and "
    "auditing sessions use the `chanchi-session-audit` skill."
)


def repo_skills_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "skills"
    if not path.is_dir():
        raise ChanchiError(
            "internal",
            f"skills directory not found at {path}",
            hint="install chanchi from its repository with `uv tool install --editable .`",
        )
    return path


def available_skills(skills_dir: Path) -> list[str]:
    return sorted(
        entry.name
        for entry in skills_dir.iterdir()
        if entry.is_dir() and entry.name.startswith(SKILL_PREFIX) and (entry / "SKILL.md").is_file()
    )


def plan_targets(base: Path, *, global_: bool) -> tuple[Path, list[Path]]:
    """Primary dir (absolute links into the repo) and secondary dirs (relative links to primary)."""
    primary = base / ".agents" / "skills"
    secondaries = [base / ".claude" / "skills"]
    if global_ and (base / ".gemini" / "antigravity-cli").is_dir():
        secondaries.append(base / ".gemini" / "antigravity-cli" / "skills")
    return primary, secondaries


def _ensure(link_path: Path, target: Path, *, absolute: bool, created: list, existing: list, conflicts: list) -> None:
    desired = str(target) if absolute else os.path.relpath(target, link_path.parent)
    if link_path.is_symlink():
        if os.readlink(link_path) == desired or link_path.resolve() == target.resolve():
            existing.append(str(link_path))
        else:
            conflicts.append(str(link_path))
        return
    if link_path.exists():
        conflicts.append(str(link_path))
        return
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(desired)
    created.append(str(link_path))


def link(base: Path, *, global_: bool = False, skills_dir: Path | None = None) -> dict:
    base = Path(base).expanduser().resolve()
    skills_dir = (skills_dir or repo_skills_dir()).resolve()
    names = available_skills(skills_dir)
    primary, secondaries = plan_targets(base, global_=global_)
    created: list[str] = []
    existing: list[str] = []
    conflicts: list[str] = []
    for name in names:
        _ensure(primary / name, skills_dir / name, absolute=True, created=created, existing=existing, conflicts=conflicts)
        for secondary in secondaries:
            _ensure(secondary / name, primary / name, absolute=False, created=created, existing=existing, conflicts=conflicts)
    if conflicts:
        raise ChanchiError(
            "link_conflict",
            "these paths already exist and were left untouched: " + ", ".join(conflicts),
            field="path",
            hint="remove or rename the conflicting entries, then run `chanchi skills link` again",
        )
    return {
        "base": str(base),
        "skills": names,
        "created": created,
        "existing": existing,
        "suggested_config_line": SUGGESTED_CONFIG_LINE,
    }


def _is_own(entry: Path, primary: Path, skills_dir: Path) -> bool:
    if not entry.is_symlink() or not entry.name.startswith(SKILL_PREFIX):
        return False
    if os.readlink(entry) == os.path.relpath(primary / entry.name, entry.parent):
        return True
    try:
        return entry.resolve().is_relative_to(skills_dir)
    except OSError:
        return False


def unlink(base: Path, *, global_: bool = False, skills_dir: Path | None = None) -> dict:
    base = Path(base).expanduser().resolve()
    skills_dir = (skills_dir or repo_skills_dir()).resolve()
    primary, secondaries = plan_targets(base, global_=global_)
    removed: list[str] = []
    for directory in [*secondaries, primary]:
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            if _is_own(entry, primary, skills_dir):
                entry.unlink()
                removed.append(str(entry))
    return {"base": str(base), "removed": removed}
```

- [ ] **Step 4: Create the `skills/` directory so `repo_skills_dir()` resolves**

Run: `mkdir -p skills && touch skills/.gitkeep`

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_skills_link.py -v`
Expected: 8 passed.

- [ ] **Step 6: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: 103 passed.

```bash
git add src/chanchi/skills_link.py tests/test_skills_link.py skills/.gitkeep
git commit -m "feat: mirror chanchi skills into projects with symlinks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Text rendering and CLI

**Recommended model:** sonnet

**Files:**
- Create: `src/chanchi/render.py`, `src/chanchi/cli.py`, `src/chanchi/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: every module above.
- Produces:
  - `render.render_text(payload: dict) -> str`
  - `cli.build_parser() -> argparse.ArgumentParser`, `cli.main(argv: list[str] | None = None) -> int`
  - `python -m chanchi` entry point.
  - Command surface exactly as in spec §7 (and `db status|migrate [--template]` from §3.1).

- [ ] **Step 1: Write the failing tests `tests/test_cli.py`**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name 'cli'`.

- [ ] **Step 3: Implement `src/chanchi/render.py`**

```python
"""Compact text rendering (--format text) for humans reading agent output."""

from __future__ import annotations


def render_text(payload: dict) -> str:
    lines: list[str] = []
    _render(payload, lines, 0)
    return "\n".join(lines) + "\n"


def _scalar(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        return ", ".join(_scalar(item) for item in value) or "-"
    return str(value)


def _is_flat(value) -> bool:
    if isinstance(value, dict):
        return False
    if isinstance(value, list):
        return all(not isinstance(item, (dict, list)) for item in value)
    return True


def _render(value, lines: list[str], indent: int) -> None:
    pad = "  " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "ok":
                continue
            if _is_flat(item):
                lines.append(f"{pad}{key}: {_scalar(item)}")
            else:
                lines.append(f"{pad}{key}:")
                _render(item, lines, indent + 1)
    elif isinstance(value, list):
        if not value:
            lines.append(f"{pad}(none)")
        elif all(isinstance(item, dict) and all(_is_flat(v) for v in item.values()) for item in value):
            _table(value, lines, pad)
        else:
            for number, item in enumerate(value, 1):
                lines.append(f"{pad}- [{number}]")
                _render(item, lines, indent + 1)
    else:
        lines.append(f"{pad}{_scalar(value)}")


def _table(rows: list[dict], lines: list[str], pad: str) -> None:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    cells = [[_scalar(row.get(column)) for column in columns] for row in rows]
    widths = [max(len(column), *(len(row[i]) for row in cells)) for i, column in enumerate(columns)]
    lines.append(pad + "  ".join(c.ljust(w) for c, w in zip(columns, widths)).rstrip())
    lines.append(pad + "  ".join("-" * w for w in widths))
    for row in cells:
        lines.append(pad + "  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip())
```

- [ ] **Step 4: Implement `src/chanchi/cli.py`**

```python
"""Command-line interface. JSON by default; every failure is a structured error envelope."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from pathlib import Path

from chanchi import __version__, catalog, db, projects, record, scoring, skills_link, taxonomy
from chanchi.errors import EXIT_INTERNAL, EXIT_OK, ChanchiError
from chanchi.render import render_text
from chanchi.timeutil import since_to_iso

FORMATS = ("json", "text")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # argparse calls this on bad input
        raise ChanchiError("invalid_value", message, hint=f"run `{self.prog} --help`")


def _int(field: str):
    def convert(value: str) -> int:
        try:
            return int(value)
        except ValueError:
            raise ChanchiError("invalid_value", f"{field} must be an integer, got {value!r}", field=field) from None

    return convert


def _split(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _conn():
    return closing(db.open_operational())


def _pid(conn, args) -> int:
    return projects.resolve_project(conn, args.project)["id"]


# --- handlers --------------------------------------------------------------


def cmd_db_status(args):
    return db.status()


def cmd_db_migrate(args):
    return db.migrate_template() if args.template else db.bootstrap()


def cmd_models_add(args):
    with _conn() as conn:
        return {
            "model": catalog.add_model(
                conn, agent=args.agent, model=args.model, cost_tier=args.cost,
                efforts=_split(args.efforts), notes=args.notes,
            )
        }


def cmd_models_list(args):
    with _conn() as conn:
        return {"models": catalog.list_models(conn, include_inactive=args.include_inactive)}


def cmd_models_set(args):
    active = None if args.active is None else bool(taxonomy.validate_choice("active", args.active, (0, 1)))
    with _conn() as conn:
        return {
            "model": catalog.set_model(
                conn, spec=args.spec, cost_tier=args.cost, active=active,
                efforts=_split(args.efforts), notes=args.notes,
            )
        }


def cmd_taxonomy_list(args):
    with _conn() as conn:
        return {"taxonomy": taxonomy.describe(), "task_types": catalog.list_task_types(conn)}


def cmd_taxonomy_add_type(args):
    with _conn() as conn:
        return {"task_type": catalog.add_task_type(conn, code=args.code, description=args.description)}


def _skills_base(args) -> Path:
    return Path.home() if args.global_ else Path(args.path)


def cmd_skills_link(args):
    return skills_link.link(_skills_base(args), global_=args.global_)


def cmd_skills_unlink(args):
    return skills_link.unlink(_skills_base(args), global_=args.global_)


def cmd_change_open(args):
    slug, path = projects.identify(args.project)
    with _conn() as conn:
        return {
            "change": record.open_change(
                conn, project_slug=slug, project_path=path, ref=args.ref, kind=args.kind,
                planner=args.planner, orchestrator=args.orchestrator,
            )
        }


def cmd_change_close(args):
    with _conn() as conn:
        return {"change": record.close_change(conn, project_id=_pid(conn, args), ref=args.ref)}


def cmd_session_start(args):
    with _conn() as conn:
        return {
            "session": record.start_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                executor=args.executor, task_type=args.task_type, complexity=args.complexity,
                tasks_total=args.tasks_total, groups=args.groups, tags=args.tags,
                retry_reason=args.retry_reason,
            )
        }


def cmd_session_report(args):
    with _conn() as conn:
        return {
            "session": record.report_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                status=args.status, attempt=args.attempt,
            )
        }


def cmd_session_audit(args):
    with _conn() as conn:
        return {
            "session": record.audit_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                verdict=args.verdict, notes=args.notes, attempt=args.attempt,
            )
        }


def cmd_session_update(args):
    with _conn() as conn:
        return {
            "session": record.update_session(
                conn, project_id=_pid(conn, args), ref=args.ref, session_ref=args.session,
                attempt=args.attempt, task_type=args.task_type, complexity=args.complexity,
                tags=args.tags, tasks_total=args.tasks_total, notes=args.notes,
            )
        }


def cmd_incident_add(args):
    with _conn() as conn:
        return {
            "incident": record.add_incident(
                conn, project_id=_pid(conn, args), ref=args.ref, code=args.code,
                severity=args.severity, detected_by=args.detected_by, description=args.description,
                evidence=args.evidence, session_ref=args.session, attempt=args.attempt,
                task_ref=args.task_ref, role=args.role,
            )
        }


def cmd_incident_void(args):
    with _conn() as conn:
        return {"incident": record.void_incident(conn, incident_id=args.id, reason=args.reason)}


def cmd_recommend(args):
    with _conn() as conn:
        return scoring.recommend(
            conn, task_type=args.task_type, complexity=args.complexity, available=_split(args.available) or []
        )


def cmd_stats(args):
    since = since_to_iso(args.since) if args.since else None
    with _conn() as conn:
        project_id = projects.resolve_project(conn, args.project)["id"] if args.project else None
        return scoring.stats(conn, role=args.role, by=args.by, project_id=project_id, since=since)


def cmd_show(args):
    with _conn() as conn:
        return scoring.show_change(conn, project_id=_pid(conn, args), ref=args.ref)


def cmd_scoring_explain(args):
    return scoring.explain()


# --- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=FORMATS, default="json", help="output format (default: json)")
    common.add_argument("--project", default=None, help="project slug (default: git toplevel name)")

    parser = _Parser(prog="chanchi", description="Turn planner/executor agent audits into model ratings.")
    parser.add_argument("--version", action="version", version=f"chanchi {__version__}")
    top = parser.add_subparsers(dest="group", required=True, metavar="<command>")

    def group(name: str, help_text: str):
        return top.add_parser(name, help=help_text, description=help_text).add_subparsers(
            dest="command", required=True, metavar="<subcommand>"
        )

    def leaf(subparsers, name: str, handler, help_text: str):
        p = subparsers.add_parser(name, parents=[common], help=help_text, description=help_text)
        p.set_defaults(handler=handler)
        return p

    g = group("db", "template and operational databases")
    leaf(g, "status", cmd_db_status, "show database paths, versions and pending migrations")
    p = leaf(g, "migrate", cmd_db_migrate, "apply pending migrations (operational database by default)")
    p.add_argument("--template", action="store_true", help="migrate the committed template (developer step)")

    g = group("models", "model catalog")
    p = leaf(g, "add", cmd_models_add, "register a model in the catalog")
    p.add_argument("--agent", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--cost", required=True, type=_int("cost"), help="1=$ 2=$$ 3=$$$")
    p.add_argument("--efforts", help="comma list of supported efforts, e.g. low,medium,high")
    p.add_argument("--notes")
    p = leaf(g, "list", cmd_models_list, "list active catalog models")
    p.add_argument("--all", dest="include_inactive", action="store_true", help="include inactive models")
    p = leaf(g, "set", cmd_models_set, "update a catalog model")
    p.add_argument("spec", help="agent:model (no effort)")
    p.add_argument("--cost", type=_int("cost"))
    p.add_argument("--active", type=_int("active"), help="0 or 1")
    p.add_argument("--efforts")
    p.add_argument("--notes")

    g = group("taxonomy", "enums, incident codes and task types")
    leaf(g, "list", cmd_taxonomy_list, "list every enum, incident code, role, weight and task type")
    p = leaf(g, "add-type", cmd_taxonomy_add_type, "add a task type")
    p.add_argument("code")
    p.add_argument("--description", required=True)

    g = group("skills", "mirror chanchi skills into a project or ~")
    for name, handler in (("link", cmd_skills_link), ("unlink", cmd_skills_unlink)):
        p = leaf(g, name, handler, f"{name} the chanchi skills")
        p.add_argument("path", nargs="?", default=".", help="project directory (default: cwd)")
        p.add_argument("--global", dest="global_", action="store_true", help="target ~ instead of a project")

    g = group("change", "OpenSpec or adhoc changes")
    p = leaf(g, "open", cmd_change_open, "open a change (creates the project on first use)")
    p.add_argument("ref")
    p.add_argument("--kind", required=True, help="openspec | adhoc")
    p.add_argument("--planner", required=True, help="agent:model[:effort] or human")
    p.add_argument("--orchestrator", help="defaults to --planner")
    p = leaf(g, "close", cmd_change_close, "close a change")
    p.add_argument("ref")

    g = group("session", "executor sessions")
    p = leaf(g, "start", cmd_session_start, "record the start of an executor session")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--executor", required=True, help="agent:model[:effort]")
    p.add_argument("--task-type", required=True)
    p.add_argument("--complexity", required=True)
    p.add_argument("--tasks", dest="tasks_total", required=True, type=_int("tasks"))
    p.add_argument("--groups")
    p.add_argument("--tags")
    p.add_argument("--retry-reason")
    p = leaf(g, "report", cmd_session_report, "record the executor's reported status")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--status", required=True, help="COMPLETE | STOPPED | BLOCKED")
    p.add_argument("--attempt", type=_int("attempt"))
    p = leaf(g, "audit", cmd_session_audit, "record the audit verdict")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--verdict", required=True, help="accepted | accepted_with_fixes | rejected")
    p.add_argument("--notes")
    p.add_argument("--attempt", type=_int("attempt"))
    p = leaf(g, "update", cmd_session_update, "correct a session's classification")
    p.add_argument("ref")
    p.add_argument("session")
    p.add_argument("--attempt", type=_int("attempt"), help="selects, never changes, the attempt")
    p.add_argument("--task-type")
    p.add_argument("--complexity")
    p.add_argument("--tags")
    p.add_argument("--tasks", dest="tasks_total", type=_int("tasks"))
    p.add_argument("--notes")

    g = group("incident", "audit incidents")
    p = leaf(g, "add", cmd_incident_add, "record an incident with evidence")
    p.add_argument("ref")
    p.add_argument("--session")
    p.add_argument("--attempt", type=_int("attempt"))
    p.add_argument("--code", required=True)
    p.add_argument("--severity", required=True)
    p.add_argument("--detected-by", required=True)
    p.add_argument("--desc", dest="description", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--task", dest="task_ref")
    p.add_argument("--role", help="only for hallucination: planner | executor")
    p = leaf(g, "void", cmd_incident_void, "void an incident without deleting it")
    p.add_argument("id", type=_int("id"))
    p.add_argument("--reason", required=True)

    p = leaf(top, "recommend", cmd_recommend, "recommend a model for a task type and complexity")
    p.add_argument("--task-type", required=True)
    p.add_argument("--complexity", required=True)
    p.add_argument("--available", required=True, help="comma list of agent:model[:effort]")

    p = leaf(top, "stats", cmd_stats, "aggregate scores")
    p.add_argument("--role", default="executor", help="executor | planner | human")
    p.add_argument("--by", default="model", help="model | task-type | project")
    p.add_argument("--since", help="YYYY-MM-DD")

    p = leaf(top, "show", cmd_show, "timeline of one change: sessions, incidents, scores")
    p.add_argument("ref")

    g = group("scoring", "scoring formulas")
    leaf(g, "explain", cmd_scoring_explain, "show current weights and formulas")
    return parser


# --- entry point -----------------------------------------------------------


def _sniff_format(argv: list[str]) -> str:
    for index, arg in enumerate(argv):
        if arg == "--format" and index + 1 < len(argv):
            return argv[index + 1] if argv[index + 1] in FORMATS else "json"
        if arg.startswith("--format="):
            value = arg.split("=", 1)[1]
            return value if value in FORMATS else "json"
    return "json"


def _emit(payload: dict, fmt: str, stream) -> None:
    if fmt == "text":
        stream.write(render_text(payload))
    else:
        stream.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    fmt = _sniff_format(argv)
    try:
        args = build_parser().parse_args(argv)
        payload = args.handler(args)
        _emit({"ok": True, **payload}, fmt, sys.stdout)
        return EXIT_OK
    except SystemExit as exc:  # --help and --version
        return exc.code if isinstance(exc.code, int) else EXIT_OK
    except ChanchiError as exc:
        _emit(exc.to_dict(), fmt, sys.stderr)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 - every failure must reach the caller as JSON
        error = ChanchiError(
            "internal",
            f"{type(exc).__name__}: {exc}",
            hint="this is a chanchi bug; report the command you ran",
        )
        _emit(error.to_dict(), fmt, sys.stderr)
        return EXIT_INTERNAL
```

Note: `test_validation_error_envelope` expects `"valid_values": [1, 2, 3]` for `--cost 9`; this comes from `taxonomy.validate_choice("cost", ...)` inside `catalog.add_model`, so the CLI must not restrict `--cost` with argparse `choices`.

- [ ] **Step 5: Implement `src/chanchi/__main__.py`**

```python
from chanchi.cli import main

raise SystemExit(main())
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 13 passed.

- [ ] **Step 7: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: 116 passed.

```bash
git add src/chanchi/render.py src/chanchi/cli.py src/chanchi/__main__.py tests/test_cli.py
git commit -m "feat: add agent-first CLI with JSON and text output

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Skills content

**Recommended model:** sonnet

**Files:**
- Create: `skills/chanchi-model-selection/SKILL.md`, `skills/chanchi-session-audit/SKILL.md`, `skills/chanchi-session-audit/references/rubric.md`
- Delete: `skills/.gitkeep`
- Test: `tests/test_skills_content.py`

**Interfaces:**
- Consumes: `cli.main`, `taxonomy.INCIDENT_CODES`.
- Produces: the two skills; a test that every `chanchi ...` command written in them exists, and that frontmatter follows the Agent Skills rules (name regex `^[a-z0-9]+(-[a-z0-9]+)*$`, equal to its directory, description 1–1024 characters).

- [ ] **Step 1: Write the failing tests `tests/test_skills_content.py`**

```python
import re
from pathlib import Path

import pytest

from chanchi import cli, taxonomy

SKILLS = Path(__file__).resolve().parents[1] / "skills"
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TOP_LEVEL = {"recommend", "stats", "show"}
COMMAND = re.compile(r"`chanchi ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?")
SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    block = text.split("---\n", 2)[1]
    fields = {}
    for line in block.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_both_skills_exist():
    assert [p.parent.name for p in SKILL_FILES] == ["chanchi-model-selection", "chanchi-session-audit"]


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_frontmatter(path):
    fields = frontmatter(path)
    assert NAME.match(fields["name"])
    assert fields["name"] == path.parent.name
    assert 1 <= len(fields["description"]) <= 1024


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_documented_commands_exist(path, capsys):
    commands = set(COMMAND.findall(path.read_text(encoding="utf-8")))
    assert commands, f"{path} documents no chanchi command"
    for group, sub in commands:
        argv = [group, "--help"] if group in TOP_LEVEL or not sub else [group, sub, "--help"]
        assert cli.main(argv) == 0, f"{path}: `chanchi {group} {sub}` does not exist"
    capsys.readouterr()


def test_rubric_covers_every_incident_code():
    rubric = (SKILLS / "chanchi-session-audit" / "references" / "rubric.md").read_text(encoding="utf-8")
    for code in taxonomy.INCIDENT_CODES:
        assert f"`{code}`" in rubric, code
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_skills_content.py -v`
Expected: FAIL — `test_both_skills_exist` fails because no `SKILL.md` exists, and `rubric.md` is missing.

- [ ] **Step 3: Create `skills/chanchi-model-selection/SKILL.md`**

````markdown
---
name: chanchi-model-selection
description: Use when planning an OpenSpec change or any multi-session work and you must assign an agent, model and effort to each executor session. Queries the local chanchi rating for the best-value model per task type and complexity, and opens the change record.
---

# chanchi — model selection

`chanchi` is a local CLI that rates `(agent, model, effort)` triples from past audits. Use it while
planning, at the moment you assign an executor to each session. It never decides for you: it gives
evidence, you choose, and your choice becomes future data.

All commands print JSON. On failure they print `{"ok": false, "error": {...}}` to stderr with
`field`, `valid_values` and `hint` — read them and correct the call instead of guessing.

## Before you start

1. Confirm the tool works: `chanchi db status`.
2. Get the list of available executors **from the human's prompt**, as `agent:model[:effort]`
   (agents: `claude`, `agy`, `opencode`). Never assume a model is available. If the prompt does not
   list them, ask.
3. Make sure each one is in the catalog: `chanchi models list`. For a missing model, ask the human
   for its cost tier (1 = $, 2 = $$, 3 = $$$) and register it:
   `chanchi models add --agent agy --model gemini-3.8-flash-high --cost 1 --efforts low,medium,high`
   (omit `--efforts` when the agent has no effort flag).

## Steps

1. **Open the change** with your own identity (use effort `unknown` if you do not know yours; use
   `human` as planner when the human gave the instructions directly):
   `chanchi change open <change-ref> --kind openspec --planner claude:opus:high`
   For work outside OpenSpec use `--kind adhoc` and a short free ref.
2. **Classify every planned session**: one `task_type` (list them with `chanchi taxonomy list`) and
   one `complexity`:
   - `low` — one layer, ≤ 3 files, no domain ambiguity, mechanical.
   - `medium` — 2 layers or 4–10 files, or one non-trivial domain rule.
   - `high` — ≥ 3 layers, > 10 files, cross-cutting concerns (sync, migrations, concurrency), or
     meaningful domain ambiguity.
   Pick the type that dominates the session's work. If none fits, ask the human before adding one
   with `chanchi taxonomy add-type <code> --description "..."`.
3. **Ask for a recommendation per session**:
   `chanchi recommend --task-type ui-component --complexity medium --available "agy:gemini-3.8-flash-high:high,claude:sonnet:medium"`
4. **Read the result**:
   - `recommendation.spec` is the cheapest candidate within 5 points of the best smoothed score,
     excluding candidates with an honesty red flag. It is `null` when there is not enough data
     (`reason: insufficient_data`) or every candidate is red-flagged (`reason: all_candidates_red_flagged`).
   - Each candidate shows `level` (how specific the data is: `task_type+complexity`, `task_type`,
     `complexity`, `global`), `n`, `confidence` (`insufficient` < 3, `low` < 10, `ok`),
     `clean_rate`, `honesty_flags_per_session`, `retry_rate` and `top_codes`.
   - With `null`, choose by judgement — that choice is how data accumulates.
5. **Write it into the session protocol** of the plan, one line per session, e.g.:
   `chanchi: recommended agy:gemini-3.8-flash-high:high (99.6, low confidence, task_type+complexity) · chosen agy:gemini-3.8-flash-high:high`
   If you deviate, add `· reason: <why>`.
6. Hand the change over to orchestration; the `chanchi-session-audit` skill takes it from there.

## Catalog maintenance (when the human asks)

- `chanchi models set claude:sonnet --cost 2` — change a cost tier.
- `chanchi models set claude:haiku --active 0` — retire a model without losing its history.
- `chanchi stats --by task-type` — see how every model performs per task type.
- `chanchi stats --role planner` — see how planners perform.
- `chanchi scoring explain` — show the formulas and weights behind every number.
````

- [ ] **Step 4: Create `skills/chanchi-session-audit/SKILL.md`**

````markdown
---
name: chanchi-session-audit
description: Use when orchestrating executor sessions of an OpenSpec change (or adhoc work) and when auditing their reports or handoffs. Records each session, every stop and audit finding as evidence-backed incidents, and the verdict, so chanchi can turn audits into model ratings.
---

# chanchi — session audit

You are the orchestrator: the only writer of audit data. Executors never rate anyone; when they hit
something undefined they stop and hand off, and you record what happened. Record facts with
evidence, not impressions. Read `references/rubric.md` before classifying anything.

The project is detected from the git repository you run in (`--project <slug>` overrides it). All
commands print JSON; errors carry `field`, `valid_values` and `hint`.

## Session lifecycle

1. **Before launching a session**:
   `chanchi session start <change-ref> S1 --executor agy:gemini-3.8-flash-high:high --task-type ui-component --complexity medium --tasks 10 --groups 8,9,10`
   Use the executor, task type and complexity written in the session protocol. `--tasks` is the
   number of tasks the session owns. Re-running a session creates a new attempt and requires
   `--retry-reason executor_failure|plan_fix|human_change|env`.
2. **When the report or handoff arrives**:
   `chanchi session report <change-ref> S1 --status STOPPED`
   (`COMPLETE`, `STOPPED` or `BLOCKED`, exactly as the executor reported). Report again with the new
   status if the same session resumes after you resolve a stop.
3. **Classify every stop** (see the rubric). A stop at a real plan gap is two incidents:
   `chanchi incident add <change-ref> --code plan_gap --severity blocking --detected-by executor_stop --task 7.3 --desc "design does not define the sort order" --evidence "report S1: STOP at 7.3"`
   `chanchi incident add <change-ref> --session S1 --code correct_stop --severity low --detected-by executor_stop --desc "stopped instead of choosing an order" --evidence "report S1: STOP at 7.3"`
   A stop caused by the human is `human_*`; an environment problem is `env_issue`.
4. **Audit the turn** — the executor's numbers are claims:
   - re-run every verification command; a number that does not reproduce → `false_claim`;
   - check the diff against the session's scope → `scope_drift`;
   - check the project's rules → `rule_violation`;
   - "choices the plan left open" in the report → `plan_delegated_decision`, plus
     `improvised_decision` on the session when the protocol required a stop;
   - invented files, APIs, flags or rules → `hallucination` with `--role executor` (or
     `--role planner` when the plan invented it).
5. **Record the verdict**:
   `chanchi session audit <change-ref> S1 --verdict accepted`
   - `accepted` — nothing had to be corrected.
   - `accepted_with_fixes` — accepted after small corrections within the turn.
   - `rejected` — the turn's work is discarded or redone as a new attempt.
6. **At archive time**: `chanchi change close <change-ref>`, then `chanchi show <change-ref>` and give
   the human the summary (session scores, planner score, incidents by role).

## Corrections and late findings

- Wrong incident: `chanchi incident void <id> --reason "..."` (nothing is ever deleted).
- Wrong classification: `chanchi session update <change-ref> S1 --complexity high`.
- A defect found after the change closed still belongs to the original session:
  `chanchi incident add <change-ref> --session S3 --code quality_defect --severity high --detected-by post_merge --desc "..." --evidence "..."`

## Rules

- No evidence, no incident. `--evidence` names the command and its output, a path, or a quote.
- One incident per distinct fault, not one per symptom.
- Apply the planner-vs-human test before blaming the plan.
- Never answer a product or plan decision on the executor's behalf; surface it to the human.
````

- [ ] **Step 5: Create `skills/chanchi-session-audit/references/rubric.md`**

````markdown
# Audit rubric

## Complexity

| Level | Criteria |
|---|---|
| `low` | one layer, ≤ 3 files, no domain ambiguity, mechanical |
| `medium` | 2 layers or 4–10 files, or one non-trivial domain rule |
| `high` | ≥ 3 layers, > 10 files, cross-cutting concerns (sync, migrations, concurrency), or meaningful domain ambiguity |

## Planner vs human test

> Could the planner have detected this from what it had — the requirement plus the codebase and
> project rules?

- **Yes** → a `plan_*` code (the planner is accountable).
- **No, or the human changed their mind** → a `human_*` code (no model is penalised).

## From observation to incident code

| Observation | Code | Role |
|---|---|---|
| Executor stopped: something was not defined | `plan_gap` (+ `correct_stop` on the session) | planner (+ executor credit) |
| Report lists choices the plan left open | `plan_delegated_decision` | planner |
| A value, path or baseline in the plan was wrong (e.g. expected lint count off by one) | `plan_wrong_expectation` | planner |
| The plan contradicts existing code, rules or behaviour | `plan_conflict` | planner |
| A project rule was broken (`any`, hex colours, forbidden API…) | `rule_violation` | executor |
| Files or groups outside the session were touched, or planning files edited | `scope_drift` | executor |
| The executor decided where the protocol required a stop | `improvised_decision` | executor |
| A reported number or status did not reproduce | `false_claim` | executor |
| Work marked done was not done or was wrong | `incomplete_work` | executor |
| Bug, weak test or wrong implementation that passed verification | `quality_defect` | executor |
| The executor stopped at a real gap instead of improvising | `correct_stop` | executor (positive) |
| Something that does not exist was invented (file, hook, API, flag, rule, domain fact) | `hallucination` + `--role planner` or `--role executor` | whoever invented it |
| The requirement was ambiguous or incomplete at its origin | `human_unclear_requirement` | human |
| The human asked for the wrong thing | `human_wrong_requirement` | human |
| The human added new or unrelated work mid-change | `human_scope_addition` | human |
| Tooling or environment failed (watchman, emulator, CLI) | `env_issue` | none |
| The bug already existed before the change | `preexisting_defect` | none |

`hallucination` vs `false_claim`: a hallucination invents something that does not exist; a false
claim misreports a result (e.g. "tests PASS" when they fail).

## Severity

| Severity | Use when |
|---|---|
| `low` | cosmetic or trivially fixed; no rework |
| `medium` | rework inside the same session |
| `high` | rework across sessions, or wrong behaviour reached the audit |
| `blocking` | execution could not continue until someone decided or fixed something |

Findings with `--detected-by human` or `--detected-by post_merge` weigh 1.5× because the audit
missed them.

## Detected by

| Value | Meaning |
|---|---|
| `executor_stop` | surfaced by the executor's stop or handoff |
| `planner_audit` | found by the orchestrator while auditing the turn |
| `human` | found by the human |
| `post_merge` | found after the change was merged or closed |

## Evidence rules

- Every incident carries evidence: the command and its output, a file path, or a quote from the
  report.
- One incident per distinct fault. Three failing tests caused by one wrong import are one
  `quality_defect`.
- No evidence, no incident. If you only have an impression, investigate first or leave it out.

## Worked examples

1. Report: `STOPPED`, "lint prints 2079 problems, expected 2078". The plan's baseline was stale:
   `plan_wrong_expectation` (low, `executor_stop`) and `correct_stop` on the session.
2. Report: `COMPLETE`, with "Choices the plan left open: the rate metric is % of body weight per
   week". `plan_delegated_decision` (medium, `planner_audit`). If the protocol said to stop on
   undefined behaviour, add `improvised_decision` (medium) on the session.
3. Report: `yarn test: PASS`, but your re-run fails two suites: `false_claim` (high, `planner_audit`).
4. The design cites a hook that does not exist in the codebase: `hallucination --role planner`.
5. Halfway through, the human asks to also fix an unrelated screen: `human_scope_addition`; the new
   attempt uses `--retry-reason human_change`.
````

- [ ] **Step 6: Remove the placeholder**

Run: `git rm -q skills/.gitkeep`

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_skills_content.py -v`
Expected: 6 passed.

- [ ] **Step 8: Run the whole suite and commit**

Run: `uv run pytest -q` — Expected: 122 passed.

```bash
git add skills tests/test_skills_content.py
git commit -m "feat: add model-selection and session-audit skills

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Scenario test, CLI integration test, README and install

**Recommended model:** sonnet

**Files:**
- Create: `tests/test_scenario.py`, `tests/test_cli_integration.py`
- Modify: `README.md` (replace the placeholder entirely)

**Interfaces:**
- Consumes: `helpers.Recorder`, `helpers.inc`, the `recorder` fixture, `scoring.*`, `python -m chanchi`.
- Produces: end-to-end evidence that the spec's flow works; user-facing README.

- [ ] **Step 1: Write `tests/test_scenario.py`**

This replays DATEMApp's `clinical-summary-doctor-addressee-and-polish` change with data embedded here (it never reads that repository), plus one synthetic change.

```python
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
```

- [ ] **Step 2: Write `tests/test_cli_integration.py`**

```python
import json
import os
import subprocess
import sys


def chanchi(cwd, env, *args):
    result = subprocess.run(
        [sys.executable, "-m", "chanchi", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False
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
```

- [ ] **Step 3: Run the new tests**

Run: `uv run pytest tests/test_scenario.py tests/test_cli_integration.py -v`
Expected: 4 passed.

- [ ] **Step 4: Replace `README.md`**

````markdown
# chanchi

A local, agent-first auditor for multi-agent coding work. The orchestrating agent records every
executor session and every incident found while auditing it; `chanchi` turns those audits into
scores and recommends which `(agent, model, effort)` to use for a given task type and complexity.

- **Local only:** one SQLite database at `~/.local/share/chanchi/chanchi.db` (override with
  `CHANCHI_DB`). Nothing leaves the machine.
- **Agent-first:** JSON output by default (`--format text` for humans), structured errors with
  `field`, `valid_values` and `hint`.
- **No runtime dependencies:** Python ≥ 3.11 standard library.

Design: `docs/superpowers/specs/2026-10-18-chanchi-model-auditor-design.md`.

## Install

```bash
uv tool install --editable .
```

`--editable` keeps this checkout as the live source, which the skill symlinks rely on. The first
command creates the operational database by copying the committed template.

## Give the skills to a project

```bash
chanchi skills link /path/to/project
```

This creates `.agents/skills/chanchi-*` (read by opencode and agy) and `.claude/skills/chanchi-*`
(read by Claude Code) as symlinks to this repository, and prints a line to add to the project's
`openspec/config.yaml`. `chanchi skills link --global` does the same in your home directory;
`chanchi skills unlink` removes only the links it created.

- `chanchi-model-selection` — used while planning: asks `chanchi recommend` for each session.
- `chanchi-session-audit` — used while orchestrating: records sessions, incidents and verdicts.

## Everyday commands

```bash
chanchi models add --agent agy --model gemini-3.8-flash-high --cost 1 --efforts low,medium,high
chanchi recommend --task-type ui-component --complexity medium --available "agy:gemini-3.8-flash-high:high,claude:sonnet:medium"
chanchi stats --by task-type
chanchi show <change-ref>
chanchi scoring explain
chanchi taxonomy list
```

## Databases and migrations

| | Template | Operational |
|---|---|---|
| Path | `src/chanchi/data/template.db` | `~/.local/share/chanchi/chanchi.db` |
| Content | schema + seed rows | your data |
| In git | committed | never |

Every migration affects both. To add one:

1. Add `src/chanchi/migrations/NNN_<name>.sql`.
2. Run `uv run chanchi db migrate --template` and commit the SQL file and `template.db` together.
3. The operational database migrates itself on its next command, after a `chanchi.db.bak-v<N>`
   backup (the three most recent are kept).

`tests/test_db.py` fails if the template drifts from the migrations.

## Development

```bash
uv run pytest
```
````

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: 126 passed.

- [ ] **Step 6: Install the tool and smoke-test it**

Run: `uv tool install --editable . && chanchi --version && chanchi db status`
Expected: `chanchi 0.1.0`, then a JSON object whose `template.version` equals `latest_migration` (1) and whose `operational.path` is `~/.local/share/chanchi/chanchi.db` (expanded). Do **not** run any recording command against the real database.

- [ ] **Step 7: Commit**

```bash
git add tests/test_scenario.py tests/test_cli_integration.py README.md
git commit -m "test: replay a real change end to end and document usage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
