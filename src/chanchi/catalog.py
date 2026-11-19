"""Model catalog and task types."""

from __future__ import annotations

import sqlite3

from chanchi import modelspec, taxonomy
from chanchi.db import transaction
from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now


def capabilities_for(conn: sqlite3.Connection, model_id: int) -> dict[str, str]:
    rows = conn.execute(
        "SELECT capability, value FROM model_capabilities WHERE model_id = ? ORDER BY capability",
        (model_id,),
    ).fetchall()
    return {row["capability"]: row["value"] for row in rows}


def _validate_capabilities(capabilities: dict[str, str]) -> None:
    for name, value in capabilities.items():
        taxonomy.validate_choice("capability", name, taxonomy.CAPABILITIES)
        taxonomy.validate_choice("capability", value, taxonomy.CAPABILITY_VALUES)


def parse_capabilities(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ChanchiError(
                "invalid_value",
                f"capability {item!r} must be NAME=VALUE",
                field="capability",
                hint="use NAME=VALUE, for example vision=yes",
            )
        raw_name, raw_value = item.split("=", 1)
        name, value = raw_name.strip(), raw_value.strip()
        if not name or not value:
            raise ChanchiError(
                "invalid_value",
                f"capability {item!r} must be NAME=VALUE",
                field="capability",
                hint="use NAME=VALUE, for example vision=yes",
            )
        _validate_capabilities({name: value})
        if name in parsed:
            raise ChanchiError(
                "invalid_value",
                f"capability {name!r} was passed more than once (in {item!r})",
                field="capability",
            )
        parsed[name] = value
    return parsed


def _apply_capabilities(
    conn: sqlite3.Connection, model_id: int, capabilities: dict[str, str], timestamp: str
) -> None:
    for name, value in capabilities.items():
        if value == "unknown":
            conn.execute(
                "DELETE FROM model_capabilities WHERE model_id = ? AND capability = ?",
                (model_id, name),
            )
        else:
            conn.execute(
                "INSERT INTO model_capabilities (model_id, capability, value, set_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(model_id, capability) DO UPDATE SET "
                "value = excluded.value, set_at = excluded.set_at",
                (model_id, name, value, timestamp),
            )


def _model_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    caps = capabilities_for(conn, row["id"])
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
        "capabilities": ",".join(f"{name}={caps[name]}" for name in sorted(caps)),
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
    capabilities: dict[str, str] | None = None,
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
    if capabilities is not None:
        _validate_capabilities(capabilities)
    timestamp = now or utc_now()
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
            (agent, model, cost_tier, efforts_csv, notes, timestamp),
        )
        if capabilities:
            _apply_capabilities(conn, cursor.lastrowid, capabilities, timestamp)
    return _model_dict(
        conn, conn.execute("SELECT * FROM models WHERE id = ?", (cursor.lastrowid,)).fetchone()
    )


def list_models(conn: sqlite3.Connection, *, include_inactive: bool = False) -> list[dict]:
    query = "SELECT * FROM models" + ("" if include_inactive else " WHERE active = 1")
    return [_model_dict(conn, r) for r in conn.execute(query + " ORDER BY agent, model")]


def set_model(
    conn: sqlite3.Connection,
    *,
    spec: str,
    cost_tier: int | None = None,
    active: bool | None = None,
    efforts: list[str] | None = None,
    notes: str | None = None,
    capabilities: dict[str, str] | None = None,
    now: str | None = None,
) -> dict:
    parsed = modelspec.parse(spec, field="spec")
    if parsed.agent in taxonomy.PLANNER_ONLY_AGENTS:
        raise ChanchiError(
            "invalid_value", "the built-in human:human entry cannot be modified", field="spec"
        )
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
    if capabilities is not None:
        _validate_capabilities(capabilities)
    if not updates and not capabilities:
        raise ChanchiError(
            "invalid_value",
            "nothing to update",
            hint="pass at least one of --cost, --active, --efforts, --notes, --capability",
        )
    with transaction(conn):
        row = _model_row(conn, parsed.agent, parsed.model)
        if row is None:
            raise ChanchiError(
                "unknown_model", f"{parsed.agent}:{parsed.model} is not in the catalog", field="spec"
            )
        if updates:
            assignments = ", ".join(f"{column} = ?" for column in updates)
            conn.execute(f"UPDATE models SET {assignments} WHERE id = ?", (*updates.values(), row["id"]))
        if capabilities:
            _apply_capabilities(conn, row["id"], capabilities, now or utc_now())
    return _model_dict(conn, conn.execute("SELECT * FROM models WHERE id = ?", (row["id"],)).fetchone())


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
