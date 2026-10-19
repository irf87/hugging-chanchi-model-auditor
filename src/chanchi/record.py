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
