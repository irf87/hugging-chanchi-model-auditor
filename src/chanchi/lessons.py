"""Lessons: record, review, apply and retire improvement lessons, and the read commands.

Every write runs in one `db.transaction` and writes exactly the `lesson_events` rows of the design's
events table. Duplicate detection text processing lives in `dedup.py`; this module sorts each stored
lesson into a class first. Project resolution and git access live in `projects.py`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from chanchi import catalog, dedup, modelspec, projects, record, taxonomy, timeutil
from chanchi.db import transaction
from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now

SITES = ("global", "project")
BODY_TEXT_KEYS = (
    "what_happened",
    "evidence",
    "cause",
    "prevention",
    "proposal",
    "general_rule",
    "target",
)
BODY_ENUM_KEYS = ("generality", "severity", "target_kind")
BODY_OPTIONAL_TEXT_KEYS = ("particular_justification", "change", "session")
BODY_KEYS = (
    BODY_TEXT_KEYS
    + BODY_ENUM_KEYS
    + BODY_OPTIONAL_TEXT_KEYS
    + ("tags", "incidents", "replaces")
)
MAX_WARNINGS = 5
_REVIEW_ALLOWED = {
    "approve": ("pending", "postponed"),
    "reject": ("pending", "postponed"),
    "postpone": ("pending",),
    "duplicate": ("pending", "postponed"),
}
_NEW_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "postpone": "postponed",
    "duplicate": "duplicate",
}


# --- actor -------------------------------------------------------------------


@dataclass(frozen=True)
class Actor:
    role: str
    agent: str
    model_raw: str
    model_id: int | None
    effort: str | None
    conversation: str


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance; the inputs are short (effort names and one model-name segment)."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def make_actor(
    conn: sqlite3.Connection, as_role: str, author_spec: str, conversation: str
) -> Actor:
    """Build the declared actor of a write command: role, harness, model, effort, conversation."""
    role = record._required_text("as", as_role)
    conversation = record._required_text("conversation", conversation)
    parsed = modelspec.parse(author_spec or "", field="author")
    row = catalog._model_row(conn, parsed.agent, parsed.model)
    if row is None and ":" in parsed.model:
        last = parsed.model.rsplit(":", 1)[1]
        if any(_edit_distance(last, effort) <= 2 for effort in taxonomy.EFFORTS):
            raise ChanchiError(
                "invalid_value",
                f"{author_spec!r} ends in {last!r}, which looks like a mistyped effort",
                field="author",
                valid_values=taxonomy.EFFORTS,
                hint=(
                    "use agent:model[:effort] with a valid effort; a real model name ending in "
                    f":{last} is accepted once it is in the catalog (`chanchi models add`)"
                ),
            )
    return Actor(
        role=role,
        agent=parsed.agent,
        model_raw=parsed.model,
        model_id=row["id"] if row is not None else None,
        effort=parsed.effort,
        conversation=conversation,
    )


def check_writer(
    conn: sqlite3.Connection, scope_project_id: int | None, actor: Actor
) -> None:
    """Pass for `human` or for a role in the scope's writer roles; otherwise `not_a_writer`."""
    if actor.agent == "human":
        return
    roles = projects.writer_roles(conn, scope_project_id)
    if actor.role in roles:
        return
    scope_name = _scope_name(conn, scope_project_id)
    raise ChanchiError(
        "not_a_writer",
        f"role {actor.role} cannot write lessons in {scope_name}",
        field="as",
        valid_values=roles,
        hint=(
            f"report the failure instead; writer roles are changed with "
            f"`chanchi project writers {scope_name} --set ...`"
        ),
    )


def _scope_name(conn: sqlite3.Connection, project_id: int | None) -> str:
    if project_id is None:
        return "global"
    row = conn.execute("SELECT slug FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row["slug"] if row is not None else f"project #{project_id}"


def set_writers(
    conn: sqlite3.Connection, scope: projects.Scope, actor: Actor, roles: list[str]
) -> dict:
    """Replace the scope's writer roles; only a current writer role of that scope or `human` may."""
    with transaction(conn):
        check_writer(conn, scope.project_id, actor)
        cleaned: list[str] = []
        for role in roles:
            text = (role or "").strip() if isinstance(role, str) else ""
            if not text:
                raise ChanchiError(
                    "invalid_value", "a writer role must not be blank", field="set"
                )
            if text not in cleaned:
                cleaned.append(text)
        if not cleaned:
            raise ChanchiError(
                "invalid_value", "at least one writer role is required", field="set"
            )
        projects.set_writer_roles(conn, scope.project_id, cleaned)
    return {"scope": scope.slug or "global", "roles": cleaned, "default": False}


# --- shared helpers ------------------------------------------------------------


def _split_tags(text: str) -> list[str]:
    return [part for part in text.split(",") if part]


def _lesson_row(conn: sqlite3.Connection, lesson_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT l.*, p.slug AS origin_slug FROM lessons l "
        "LEFT JOIN projects p ON p.id = l.origin_project_id WHERE l.id = ?",
        (lesson_id,),
    ).fetchone()
    if row is None:
        raise ChanchiError(
            "lesson_not_found",
            f"no lesson #{lesson_id}",
            field="id",
            hint="chanchi lesson list",
        )
    return row


def _row_to_lesson(row: sqlite3.Row) -> dict:
    data = {key: row[key] for key in row.keys() if key != "origin_slug"}
    data["tags"] = _split_tags(row["tags"])
    data["origin"] = row["origin_slug"] or "global"
    return data


def lesson_dict(conn: sqlite3.Connection, lesson_id: int) -> dict:
    return _row_to_lesson(_lesson_row(conn, lesson_id))


def _site_dict(row: sqlite3.Row) -> dict:
    return {
        "site": row["site"],
        "project": row["project_slug"],
        "state": row["state"],
        "where_": row["where_"],
        "reason": row["reason"],
        "decided_conversation": row["decided_conversation"],
        "decided_at": row["decided_at"],
    }


def _site_dicts(conn: sqlite3.Connection, lesson_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT s.*, p.slug AS project_slug FROM lesson_sites s "
        "LEFT JOIN projects p ON p.id = s.project_id WHERE s.lesson_id = ? ORDER BY s.id",
        (lesson_id,),
    ).fetchall()
    return [_site_dict(row) for row in rows]


def _event(
    conn: sqlite3.Connection,
    lesson_id: int,
    actor: Actor,
    action: str,
    from_state: str | None,
    to_state: str | None,
    *,
    note: str = "",
    site: str | None = None,
    site_project_id: int | None = None,
    now: str,
) -> None:
    conn.execute(
        "INSERT INTO lesson_events (lesson_id, site, site_project_id, at, actor_role, actor_agent, "
        "conversation, action, from_state, to_state, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            lesson_id,
            site,
            site_project_id,
            now,
            actor.role,
            actor.agent,
            actor.conversation,
            action,
            from_state,
            to_state,
            note,
        ),
    )


def _transition_error(
    lesson: sqlite3.Row, command: str, allowed: tuple[str, ...], hint: str | None
) -> ChanchiError:
    return ChanchiError(
        "invalid_transition",
        f"lesson #{lesson['id']} is {lesson['status']}; {command} needs {', '.join(allowed)}",
        field="status",
        valid_values=allowed,
        hint=hint,
    )


def _state_hint(lesson: sqlite3.Row, wants_pending: bool = True) -> str | None:
    """The command that moves a lesson out of a state a command refuses."""
    status = lesson["status"]
    if status == "approved":
        return "an approved lesson cannot go back; withdraw it with `chanchi lesson retire` at every site"
    if status in ("rejected", "postponed", "duplicate") and wants_pending:
        return f"chanchi lesson reopen {lesson['id']}"
    return None


# --- body validation -------------------------------------------------------------


def _bad(field: str, message: str, **kwargs) -> ChanchiError:
    return ChanchiError("invalid_value", message, field=field, **kwargs)


def _check_body_types(body: object) -> dict:
    if not isinstance(body, dict):
        raise _bad("json", "the lesson body must be a JSON object")
    unknown = [key for key in body if key not in BODY_KEYS]
    if unknown:
        raise _bad(
            str(unknown[0]),
            f"unknown key {unknown[0]!r} in the lesson body",
            valid_values=BODY_KEYS,
        )
    for key in BODY_KEYS:
        if key not in body:
            continue
        value = body[key]
        if key in ("incidents", "replaces"):
            ok = isinstance(value, list) and all(
                isinstance(item, int) and not isinstance(item, bool) for item in value
            )
            expected = "a list of integers"
        elif key == "tags":
            ok = isinstance(value, str) or (
                isinstance(value, list) and all(isinstance(item, str) for item in value)
            )
            expected = "a list of strings or one comma-separated string"
        else:
            ok = isinstance(value, str)
            expected = "a string"
        if not ok:
            raise _bad(key, f"{key} must be {expected}")
    return body


def _validate_body(
    conn: sqlite3.Connection,
    body: object,
    origin_project_id: int | None,
    *,
    lesson: sqlite3.Row | None = None,
) -> dict:
    """Validate an add or modify body; return the normalized values to store."""
    body = _check_body_types(body)
    data: dict = {}
    for key in BODY_TEXT_KEYS:
        data[key] = record._required_text(key, body.get(key))
    severity = body.get("severity")
    if severity == "blocking":
        raise ChanchiError(
            "invalid_value",
            "severity 'blocking' belongs to incidents, not lessons",
            field="severity",
            valid_values=taxonomy.LESSON_SEVERITIES,
            hint="use critical for a lesson about data loss, production or secrets",
        )
    data["generality"] = taxonomy.validate_choice(
        "generality", body.get("generality"), taxonomy.LESSON_GENERALITIES
    )
    data["severity"] = taxonomy.validate_choice(
        "severity", severity, taxonomy.LESSON_SEVERITIES
    )
    data["target_kind"] = taxonomy.validate_choice(
        "target_kind", body.get("target_kind"), taxonomy.LESSON_TARGET_KINDS
    )
    justification = (body.get("particular_justification") or "").strip() or None
    if data["generality"] == "particular":
        if data["severity"] not in ("high", "critical"):
            raise ChanchiError(
                "invalid_value",
                "a particular lesson must be high or critical",
                field="severity",
                valid_values=("high", "critical"),
                hint="a rule for one case is worth the context only when the risk is high",
            )
        if justification is None:
            raise _bad(
                "particular_justification",
                "a particular lesson needs a justification",
                hint="say why this case cannot be stated as a general rule",
            )
    data["particular_justification"] = justification

    is_global = origin_project_id is None
    if is_global:
        if data["generality"] != "agnostic":
            raise ChanchiError(
                "invalid_value",
                "a global lesson must be agnostic",
                field="generality",
                valid_values=("agnostic",),
                hint="a rule that belongs to one project is recorded inside that project",
            )
        for key in ("change", "session", "incidents"):
            if key in body:
                raise _bad(key, f"a global lesson cannot carry {key}; it belongs to a project")

    tags = body.get("tags", "")
    data["tags"] = record._csv(",".join(tags) if isinstance(tags, list) else tags) or ""

    change_id: int | None = None
    session_id: int | None = None
    if lesson is not None:
        change_id, session_id = lesson["change_id"], lesson["session_id"]
        if "change" in body:
            stored = _stored_ref(conn, "changes", "ref", change_id)
            if body["change"] != stored:
                raise _bad("change", "change cannot be changed by modify", hint="it stays as recorded")
        if "session" in body:
            stored = _stored_ref(conn, "sessions", "session_ref", session_id)
            if body["session"] != stored:
                raise _bad("session", "session cannot be changed by modify", hint="it stays as recorded")
    else:
        if "change" in body:
            change_id = record.get_change(conn, origin_project_id, body["change"].strip())["id"]
        if "session" in body:
            if change_id is None:
                raise _bad("session", "session requires change")
            session_id = record.get_session(conn, change_id, body["session"].strip())["id"]
    data["change_id"], data["session_id"] = change_id, session_id

    incident_ids = list(dict.fromkeys(body.get("incidents", [])))
    if incident_ids:
        if change_id is None:
            raise _bad("incidents", "incidents require change")
        for incident_id in incident_ids:
            _check_incident(conn, incident_id, change_id, "incidents")
    data["incidents"] = incident_ids

    replaces = list(dict.fromkeys(body.get("replaces", [])))
    for replaced in replaces:
        if lesson is not None and replaced == lesson["id"]:
            raise _bad("replaces", "a lesson cannot replace itself")
        _lesson_row(conn, replaced)
    data["replaces"] = replaces
    return data


def _stored_ref(conn: sqlite3.Connection, table: str, column: str, row_id: int | None) -> str | None:
    if row_id is None:
        return None
    return conn.execute(f"SELECT {column} FROM {table} WHERE id = ?", (row_id,)).fetchone()[0]


def _check_incident(
    conn: sqlite3.Connection, incident_id: int, change_id: int, field: str, *, flag: str | None = None
) -> None:
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    name = flag or field
    if row is None or row["change_id"] != change_id:
        raise _bad(name, f"incident #{incident_id} does not belong to this lesson's change")
    if row["voided_at"] is not None:
        raise _bad(field, f"incident #{incident_id} is voided and cannot be linked")


# --- duplicate detection -----------------------------------------------------------


def _candidates(conn: sqlite3.Connection, exclude_id: int | None) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, status, generality, origin_project_id, what_happened, general_rule, proposal "
        "FROM lessons WHERE id IS NOT ? ORDER BY id",
        (exclude_id,),
    ).fetchall()


def _candidate(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "full": f"{row['what_happened']} {row['general_rule']} {row['proposal']}",
        "rule": row["general_rule"],
    }


def _dup_check(
    conn: sqlite3.Connection, data: dict, origin_project_id: int | None, exclude_id: int | None
) -> tuple[dict | None, list[dict]]:
    """Return the blocking match (with its lesson row) and the warnings for a new lesson text."""
    new = {
        "id": None,
        "full": f"{data['what_happened']} {data['general_rule']} {data['proposal']}",
        "rule": data["general_rule"],
    }
    fully_retired = {
        row["lesson_id"]
        for row in conn.execute(
            "SELECT lesson_id FROM lesson_sites GROUP BY lesson_id "
            "HAVING SUM(state <> 'retired') = 0"
        )
    }
    blocking: list[dict] = []
    by_id: dict[int, sqlite3.Row] = {}
    warnings: list[tuple[float, int, dict]] = []
    for row in _candidates(conn, exclude_id):
        by_id[row["id"]] = row
        in_scope = row["origin_project_id"] == origin_project_id or row["generality"] == "agnostic"
        if row["status"] == "approved" and row["id"] in fully_retired:
            kind = "retired"
        elif in_scope and row["status"] in ("pending", "postponed", "approved"):
            blocking.append(_candidate(row))
            continue
        elif in_scope:
            kind = row["status"]
        elif row["generality"] == "project":
            kind = "possibly_agnostic"
        else:
            continue
        found = dedup.matches(new, _candidate(row))
        if found is not None:
            warnings.append(
                (
                    -found["coverage"],
                    row["id"],
                    {
                        "id": row["id"],
                        "kind": kind,
                        "general_rule": row["general_rule"],
                        "shared": found["shared"],
                    },
                )
            )
    warnings.sort(key=lambda item: item[:2])
    found = dedup.blocking_match(new, blocking)
    if found is not None:
        row = by_id[found["id"]]
        found = {**found, "status": row["status"], "general_rule": row["general_rule"]}
    return found, [item[2] for item in warnings[:MAX_WARNINGS]]


def _block_error(found: dict) -> ChanchiError:
    return ChanchiError(
        "duplicate_lesson",
        f"lesson looks like #{found['id']}",
        field="general_rule",
        hint=f"chanchi lesson repeat {found['id']} --evidence ..., or --force-new",
        details={
            "id": found["id"],
            "status": found["status"],
            "general_rule": found["general_rule"],
            "shared": found["shared"],
            "test": found["test"],
        },
    )


# --- writes ------------------------------------------------------------------------


def _replace_links(conn: sqlite3.Connection, lesson_id: int, data: dict) -> None:
    conn.execute("DELETE FROM lesson_incidents WHERE lesson_id = ?", (lesson_id,))
    conn.execute("DELETE FROM lesson_replaces WHERE lesson_id = ?", (lesson_id,))
    for incident_id in data["incidents"]:
        conn.execute(
            "INSERT INTO lesson_incidents (lesson_id, incident_id) VALUES (?, ?)",
            (lesson_id, incident_id),
        )
    for replaced in data["replaces"]:
        conn.execute(
            "INSERT INTO lesson_replaces (lesson_id, replaced_id) VALUES (?, ?)",
            (lesson_id, replaced),
        )


def add(
    conn: sqlite3.Connection,
    scope: projects.Scope,
    actor: Actor,
    body: object,
    *,
    force_new: bool = False,
    cwd: Path | None = None,
) -> dict:
    """Record a new pending lesson in the scope (a project, or global)."""
    head = projects.git_head(cwd)
    now = utc_now()
    with transaction(conn):
        check_writer(conn, scope.project_id, actor)
        data = _validate_body(conn, body, scope.project_id)
        found, warnings = _dup_check(conn, data, scope.project_id, None)
        action, note = "created", ""
        if found is not None:
            if not force_new:
                raise _block_error(found)
            action = "force_new"
            note = (
                f"matched=#{found['id']} coverage={found['coverage']:.2f} "
                f"shared={len(found['shared'])}"
            )
        cursor = conn.execute(
            "INSERT INTO lessons (origin_project_id, author_role, author_agent, author_model_raw, "
            "author_model_id, author_effort, author_conversation, git_head, change_id, session_id, "
            "target_kind, target, what_happened, evidence, cause, prevention, proposal, "
            "general_rule, generality, severity, particular_justification, tags, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (
                scope.project_id,
                actor.role,
                actor.agent,
                actor.model_raw,
                actor.model_id,
                actor.effort,
                actor.conversation,
                head,
                data["change_id"],
                data["session_id"],
                data["target_kind"],
                data["target"],
                data["what_happened"],
                data["evidence"],
                data["cause"],
                data["prevention"],
                data["proposal"],
                data["general_rule"],
                data["generality"],
                data["severity"],
                data["particular_justification"],
                data["tags"],
                now,
                now,
            ),
        )
        lesson_id = cursor.lastrowid
        _replace_links(conn, lesson_id, data)
        _event(conn, lesson_id, actor, action, None, "pending", note=note, now=now)
    return {"lesson": lesson_dict(conn, lesson_id), "warnings": warnings}


def repeat(
    conn: sqlite3.Connection,
    actor: Actor,
    lesson_id: int,
    evidence: str,
    *,
    incident: int | None = None,
) -> dict:
    """Count one more occurrence of a lesson, with the new evidence in the event note."""
    now = utc_now()
    with transaction(conn):
        lesson = _lesson_row(conn, lesson_id)
        check_writer(conn, lesson["origin_project_id"], actor)
        evidence = record._required_text("evidence", evidence)
        if lesson["status"] == "duplicate":
            raise _transition_error(
                lesson,
                "repeat",
                tuple(s for s in taxonomy.LESSON_STATUSES if s != "duplicate"),
                f"repeat the lesson it duplicates: chanchi lesson repeat {lesson['duplicate_of']} "
                "--evidence ...",
            )
        if incident is not None:
            if lesson["change_id"] is None:
                raise _bad("incident", "this lesson has no change, so it cannot link an incident")
            _check_incident(conn, incident, lesson["change_id"], "incidents", flag="incident")
            conn.execute(
                "INSERT OR IGNORE INTO lesson_incidents (lesson_id, incident_id) VALUES (?, ?)",
                (lesson_id, incident),
            )
        conn.execute(
            "UPDATE lessons SET occurrences = occurrences + 1, updated_at = ? WHERE id = ?",
            (now, lesson_id),
        )
        _event(
            conn, lesson_id, actor, "repeated", lesson["status"], lesson["status"], note=evidence, now=now
        )
    warnings = []
    if lesson["status"] == "rejected":
        warnings.append(
            {
                "kind": "rejected_recurs",
                "id": lesson_id,
                "reason_code": lesson["reason_code"],
                "decision_reason": lesson["decision_reason"],
            }
        )
    return {"lesson": lesson_dict(conn, lesson_id), "warnings": warnings}


def modify(conn: sqlite3.Connection, actor: Actor, lesson_id: int, body: object) -> dict:
    """Replace the content of a pending or postponed lesson, from its author conversation."""
    now = utc_now()
    with transaction(conn):
        lesson = _lesson_row(conn, lesson_id)
        check_writer(conn, lesson["origin_project_id"], actor)
        if lesson["status"] not in ("pending", "postponed"):
            raise _transition_error(lesson, "modify", ("pending", "postponed"), _state_hint(lesson))
        if actor.conversation != lesson["author_conversation"]:
            raise _bad(
                "conversation",
                f"lesson #{lesson_id} can only be modified from the conversation that recorded it",
                hint=f"use --conversation {lesson['author_conversation']!r}",
            )
        data = _validate_body(conn, body, lesson["origin_project_id"], lesson=lesson)
        found, warnings = _dup_check(conn, data, lesson["origin_project_id"], lesson_id)
        if found is not None:
            raise _block_error(found)
        conn.execute(
            "UPDATE lessons SET target_kind = ?, target = ?, what_happened = ?, evidence = ?, "
            "cause = ?, prevention = ?, proposal = ?, general_rule = ?, generality = ?, "
            "severity = ?, particular_justification = ?, tags = ?, updated_at = ? WHERE id = ?",
            (
                data["target_kind"],
                data["target"],
                data["what_happened"],
                data["evidence"],
                data["cause"],
                data["prevention"],
                data["proposal"],
                data["general_rule"],
                data["generality"],
                data["severity"],
                data["particular_justification"],
                data["tags"],
                now,
                lesson_id,
            ),
        )
        _replace_links(conn, lesson_id, data)
        _event(conn, lesson_id, actor, "modified", lesson["status"], lesson["status"], now=now)
    return {"lesson": lesson_dict(conn, lesson_id), "warnings": warnings}


def review(
    conn: sqlite3.Connection,
    actor: Actor,
    lesson_id: int,
    decision: str,
    reason: str,
    *,
    reason_code: str | None = None,
    of: int | None = None,
) -> dict:
    """Approve, reject, postpone or mark a lesson duplicate, from a conversation other than its author's."""
    taxonomy.validate_choice("decision", decision, taxonomy.LESSON_DECISIONS)
    reason = record._required_text("reason", reason)
    if reason_code is not None:
        taxonomy.validate_choice("reason_code", reason_code, taxonomy.LESSON_REASON_CODES)
        if decision != "reject":
            raise _bad("reason_code", "--reason-code is only allowed with --decision reject")
    if decision == "duplicate" and of is None:
        raise _bad("of", "--of is required with --decision duplicate")
    if decision != "duplicate" and of is not None:
        raise _bad("of", "--of is only allowed with --decision duplicate")
    now = utc_now()
    repointed: list[int] = []
    with transaction(conn):
        lesson = _lesson_row(conn, lesson_id)
        check_writer(conn, lesson["origin_project_id"], actor)
        allowed = _REVIEW_ALLOWED[decision]
        if lesson["status"] not in allowed:
            hint = _state_hint(lesson, wants_pending=lesson["status"] != "postponed")
            if decision == "postpone" and lesson["status"] == "postponed":
                hint = f"approve or reject it: chanchi lesson review {lesson_id} --decision approve"
            raise _transition_error(lesson, f"review --decision {decision}", allowed, hint)
        if actor.conversation == lesson["author_conversation"]:
            raise ChanchiError(
                "self_review",
                f"lesson #{lesson_id} was recorded in this conversation",
                field="conversation",
                hint="review it from another conversation",
            )
        if reason_code == "model_weakness" and lesson["session_id"] is None:
            raise _bad(
                "reason_code",
                "model_weakness needs a lesson that links a session",
                hint="record an incident on the session instead, or use another reason code",
            )
        new_status = _NEW_STATUS[decision]
        note = reason
        duplicate_of = None
        if decision == "duplicate":
            target = _lesson_row(conn, of)
            if of == lesson_id:
                raise _bad("of", "a lesson cannot be a duplicate of itself")
            if target["status"] == "duplicate":
                raise _bad(
                    "of",
                    f"lesson #{of} is itself a duplicate of #{target['duplicate_of']}",
                    hint=f"use --of {target['duplicate_of']}",
                )
            duplicate_of = of
            moved = lesson["occurrences"]
            conn.execute(
                "UPDATE lessons SET occurrences = occurrences + ?, updated_at = ? WHERE id = ?",
                (moved, now, of),
            )
            repointed = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM lessons WHERE duplicate_of = ? ORDER BY id", (lesson_id,)
                )
            ]
            conn.execute(
                "UPDATE lessons SET duplicate_of = ?, updated_at = ? WHERE duplicate_of = ?",
                (of, now, lesson_id),
            )
            note = f"moved={moved} to=#{of}"
        conn.execute(
            "UPDATE lessons SET status = ?, reviewed_at = ?, reviewed_by_role = ?, "
            "review_conversation = ?, decision_reason = ?, reason_code = ?, duplicate_of = ?, "
            "updated_at = ? WHERE id = ?",
            (
                new_status,
                now,
                actor.role,
                actor.conversation,
                reason,
                reason_code,
                duplicate_of,
                now,
                lesson_id,
            ),
        )
        _event(conn, lesson_id, actor, "reviewed", lesson["status"], new_status, note=note, now=now)
    return {"lesson": lesson_dict(conn, lesson_id), "repointed": repointed}


def reopen(conn: sqlite3.Connection, actor: Actor, lesson_id: int, reason: str) -> dict:
    """Send a rejected, postponed or duplicate lesson back to pending."""
    reason = record._required_text("reason", reason)
    now = utc_now()
    with transaction(conn):
        lesson = _lesson_row(conn, lesson_id)
        check_writer(conn, lesson["origin_project_id"], actor)
        allowed = ("rejected", "postponed", "duplicate")
        if lesson["status"] not in allowed:
            hint = _state_hint(lesson) if lesson["status"] == "approved" else None
            raise _transition_error(lesson, "reopen", allowed, hint)
        if lesson["status"] == "duplicate":
            moved_event = conn.execute(
                "SELECT note FROM lesson_events WHERE lesson_id = ? AND action = 'reviewed' "
                "AND note LIKE 'moved=%' ORDER BY id DESC LIMIT 1",
                (lesson_id,),
            ).fetchone()
            if moved_event is not None and lesson["duplicate_of"] is not None:
                moved = int(moved_event["note"].split()[0].split("=", 1)[1])
                conn.execute(
                    "UPDATE lessons SET occurrences = MAX(1, occurrences - ?), updated_at = ? "
                    "WHERE id = ?",
                    (moved, now, lesson["duplicate_of"]),
                )
        conn.execute(
            "UPDATE lessons SET status = 'pending', reviewed_at = NULL, reviewed_by_role = NULL, "
            "review_conversation = NULL, decision_reason = NULL, reason_code = NULL, "
            "duplicate_of = NULL, updated_at = ? WHERE id = ?",
            (now, lesson_id),
        )
        _event(conn, lesson_id, actor, "reopened", lesson["status"], "pending", note=reason, now=now)
    return {"lesson": lesson_dict(conn, lesson_id)}


def _site_scope(site: str, project_scope: projects.Scope | None) -> int | None:
    taxonomy.validate_choice("site", site, SITES)
    if site == "global":
        return None
    if project_scope is None or project_scope.project_id is None:
        raise _bad("project", "--site project needs a registered project")
    return project_scope.project_id


def _site_row(conn: sqlite3.Connection, lesson_id: int, site: str, project_id: int | None):
    return conn.execute(
        "SELECT * FROM lesson_sites WHERE lesson_id = ? AND site = ? "
        "AND COALESCE(project_id, 0) = COALESCE(?, 0)",
        (lesson_id, site, project_id),
    ).fetchone()


def _site_result(conn: sqlite3.Connection, lesson_id: int, site: str, project_id: int | None) -> dict:
    row = conn.execute(
        "SELECT s.*, p.slug AS project_slug FROM lesson_sites s "
        "LEFT JOIN projects p ON p.id = s.project_id WHERE s.lesson_id = ? AND s.site = ? "
        "AND COALESCE(s.project_id, 0) = COALESCE(?, 0)",
        (lesson_id, site, project_id),
    ).fetchone()
    return _site_dict(row)


def apply(
    conn: sqlite3.Connection,
    actor: Actor,
    lesson_id: int,
    site: str,
    where: str,
    *,
    project_scope: projects.Scope | None = None,
) -> dict:
    """Mark an approved lesson as applied at one site, with where the rule now lives."""
    project_id = _site_scope(site, project_scope)
    where = record._required_text("where", where)
    tag = f"[lesson #{lesson_id}]"
    if tag not in where:
        raise _bad(
            "where",
            f"where must contain {tag}",
            hint=f'"<path> {tag} @ <commit>"',
        )
    now = utc_now()
    with transaction(conn):
        lesson = _lesson_row(conn, lesson_id)
        check_writer(conn, project_id, actor)
        if lesson["status"] != "approved":
            hint = (
                f"chanchi lesson review {lesson_id} --decision approve --reason ..."
                if lesson["status"] in ("pending", "postponed")
                else f"chanchi lesson reopen {lesson_id}"
            )
            raise _transition_error(lesson, "apply", ("approved",), hint)
        if lesson["generality"] != "agnostic":
            if site != "project":
                raise ChanchiError(
                    "invalid_value",
                    f"a {lesson['generality']} lesson can only be applied at its origin project",
                    field="site",
                    valid_values=("project",),
                )
            if project_id != lesson["origin_project_id"]:
                raise _bad(
                    "project",
                    f"a {lesson['generality']} lesson can only be applied at its origin project "
                    f"({lesson['origin_slug']})",
                )
        existing = _site_row(conn, lesson_id, site, project_id)
        from_state = existing["state"] if existing is not None else None
        if from_state in ("declined", "not_applicable"):
            raise ChanchiError(
                "invalid_transition",
                f"lesson #{lesson_id} is {from_state} at this site; apply needs applied, retired or no row",
                field="state",
                valid_values=("applied", "retired"),
                hint=f"chanchi lesson reopen-site {lesson_id}",
            )
        if existing is None:
            conn.execute(
                "INSERT INTO lesson_sites (lesson_id, site, project_id, state, where_, "
                "decided_conversation, decided_at) VALUES (?, ?, ?, 'applied', ?, ?, ?)",
                (lesson_id, site, project_id, where, actor.conversation, now),
            )
        else:
            conn.execute(
                "UPDATE lesson_sites SET state = 'applied', where_ = ?, reason = NULL, "
                "decided_conversation = ?, decided_at = ? WHERE id = ?",
                (where, actor.conversation, now, existing["id"]),
            )
        conn.execute("UPDATE lessons SET updated_at = ? WHERE id = ?", (now, lesson_id))
        _event(
            conn,
            lesson_id,
            actor,
            "applied",
            from_state,
            "applied",
            note=where,
            site=site,
            site_project_id=project_id,
            now=now,
        )
    return {
        "lesson": lesson_dict(conn, lesson_id),
        "site": _site_result(conn, lesson_id, site, project_id),
    }


def retire(
    conn: sqlite3.Connection,
    actor: Actor,
    lesson_id: int,
    site: str,
    reason: str,
    *,
    project_scope: projects.Scope | None = None,
) -> dict:
    """Retire an applied lesson at one site; the other sites are not touched."""
    project_id = _site_scope(site, project_scope)
    reason = record._required_text("reason", reason)
    now = utc_now()
    with transaction(conn):
        _lesson_row(conn, lesson_id)
        check_writer(conn, project_id, actor)
        existing = _site_row(conn, lesson_id, site, project_id)
        if existing is None or existing["state"] != "applied":
            state = existing["state"] if existing is not None else "not applied"
            raise ChanchiError(
                "invalid_transition",
                f"lesson #{lesson_id} is {state} at this site; retire needs applied",
                field="state",
                valid_values=("applied",),
                hint=(
                    f"chanchi lesson apply {lesson_id} --site {site} --where ..."
                    if existing is None or existing["state"] == "retired"
                    else f"chanchi lesson reopen-site {lesson_id}"
                ),
            )
        conn.execute(
            "UPDATE lesson_sites SET state = 'retired', reason = ?, decided_conversation = ?, "
            "decided_at = ? WHERE id = ?",
            (reason, actor.conversation, now, existing["id"]),
        )
        conn.execute("UPDATE lessons SET updated_at = ? WHERE id = ?", (now, lesson_id))
        _event(
            conn,
            lesson_id,
            actor,
            "retired",
            "applied",
            "retired",
            note=reason,
            site=site,
            site_project_id=project_id,
            now=now,
        )
    return {
        "lesson": lesson_dict(conn, lesson_id),
        "site": _site_result(conn, lesson_id, site, project_id),
    }


# --- reads -------------------------------------------------------------------------


def _scope_filter(scope: projects.Scope | None, alias: str = "l") -> tuple[str, list, str]:
    if scope is None:
        return "1 = 1", [], "all"
    if scope.project_id is None:
        return f"{alias}.origin_project_id IS NULL", [], "global"
    return f"{alias}.origin_project_id = ?", [scope.project_id], scope.slug or "global"


def _positive(field: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _bad(field, f"{field} must be a positive integer")
    return value


def similar(conn: sqlite3.Connection, text: str, *, limit: int = 5) -> dict:
    """Existing lessons that look like the text, whatever their scope."""
    text = record._required_text("text", text)
    limit = _positive("limit", limit)
    rows = conn.execute(
        "SELECT l.*, p.slug AS origin_slug FROM lessons l "
        "LEFT JOIN projects p ON p.id = l.origin_project_id ORDER BY l.id"
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    found = dedup.similar(text, [_candidate(row) for row in rows], limit=limit)
    matches = []
    for item in found:
        row = by_id[item["id"]]
        matches.append(
            {
                "id": row["id"],
                "status": row["status"],
                "generality": row["generality"],
                "origin": row["origin_slug"] or "global",
                "general_rule": row["general_rule"],
                "coverage": item["coverage"],
                "shared": item["shared"],
            }
        )
    return {"scope": "all", "matches": matches}


def _site_counts(conn: sqlite3.Connection, lesson_ids: list[int]) -> dict[int, dict[str, int]]:
    counts = {lid: dict.fromkeys(taxonomy.LESSON_SITE_STATES, 0) for lid in lesson_ids}
    if lesson_ids:
        marks = ",".join("?" * len(lesson_ids))
        for row in conn.execute(
            f"SELECT lesson_id, state, COUNT(*) AS n FROM lesson_sites "
            f"WHERE lesson_id IN ({marks}) GROUP BY lesson_id, state",
            lesson_ids,
        ):
            counts[row["lesson_id"]][row["state"]] = row["n"]
    return counts


def list_lessons(
    conn: sqlite3.Connection,
    scope: projects.Scope | None,
    *,
    status: str | None = None,
    generality: str | None = None,
    target_kind: str | None = None,
    limit: int = 50,
) -> dict:
    """One row per lesson of the scope (all lessons when scope is None), oldest first."""
    clause, params, label = _scope_filter(scope)
    if status is not None:
        taxonomy.validate_choice("status", status, taxonomy.LESSON_STATUSES)
        clause += " AND l.status = ?"
        params.append(status)
    if generality is not None:
        taxonomy.validate_choice("generality", generality, taxonomy.LESSON_GENERALITIES)
        clause += " AND l.generality = ?"
        params.append(generality)
    if target_kind is not None:
        taxonomy.validate_choice("target_kind", target_kind, taxonomy.LESSON_TARGET_KINDS)
        clause += " AND l.target_kind = ?"
        params.append(target_kind)
    limit = _positive("limit", limit)
    rows = conn.execute(
        "SELECT l.*, p.slug AS origin_slug FROM lessons l "
        f"LEFT JOIN projects p ON p.id = l.origin_project_id WHERE {clause} ORDER BY l.id LIMIT ?",
        (*params, limit),
    ).fetchall()
    sites = _site_counts(conn, [row["id"] for row in rows])
    lessons = [
        {
            "id": row["id"],
            "status": row["status"],
            "generality": row["generality"],
            "severity": row["severity"],
            "occurrences": row["occurrences"],
            "target_kind": row["target_kind"],
            "target": row["target"],
            "general_rule": row["general_rule"],
            "origin": row["origin_slug"] or "global",
            "sites": sites[row["id"]],
        }
        for row in rows
    ]
    return {"scope": label, "lessons": lessons}


def show(conn: sqlite3.Connection, lesson_id: int) -> dict:
    """One lesson with its sites, replaced lessons, incidents and full event history."""
    lesson = lesson_dict(conn, lesson_id)
    replaces = [
        row["replaced_id"]
        for row in conn.execute(
            "SELECT replaced_id FROM lesson_replaces WHERE lesson_id = ? ORDER BY replaced_id",
            (lesson_id,),
        )
    ]
    incidents = [
        record.incident_dict(conn, row["incident_id"])
        for row in conn.execute(
            "SELECT incident_id FROM lesson_incidents WHERE lesson_id = ? ORDER BY incident_id",
            (lesson_id,),
        )
    ]
    events = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM lesson_events WHERE lesson_id = ? ORDER BY id", (lesson_id,)
        )
    ]
    return {
        "lesson": lesson,
        "sites": _site_dicts(conn, lesson_id),
        "replaces": replaces,
        "incidents": incidents,
        "events": events,
    }


def summary(conn: sqlite3.Connection, scope: projects.Scope | None) -> dict:
    """Counts by status and generality, applied sites per place and the force_new rate."""
    clause, params, label = _scope_filter(scope)
    by_status = dict.fromkeys(taxonomy.LESSON_STATUSES, 0)
    by_generality = dict.fromkeys(taxonomy.LESSON_GENERALITIES, 0)
    for row in conn.execute(
        f"SELECT l.status, l.generality FROM lessons l WHERE {clause}", params
    ):
        by_status[row["status"]] += 1
        by_generality[row["generality"]] += 1
    applied_sites: dict[str, int] = {}
    for row in conn.execute(
        "SELECT s.site, p.slug, COUNT(*) AS n FROM lesson_sites s "
        "JOIN lessons l ON l.id = s.lesson_id LEFT JOIN projects p ON p.id = s.project_id "
        f"WHERE s.state = 'applied' AND {clause} GROUP BY s.site, p.slug",
        params,
    ):
        applied_sites[row["slug"] if row["site"] == "project" else "global"] = row["n"]
    forced = created = 0
    for row in conn.execute(
        "SELECT e.action, COUNT(*) AS n FROM lesson_events e JOIN lessons l ON l.id = e.lesson_id "
        f"WHERE e.action IN ('created', 'force_new') AND {clause} GROUP BY e.action",
        params,
    ):
        if row["action"] == "force_new":
            forced = row["n"]
        else:
            created = row["n"]
    total = forced + created
    return {
        "scope": label,
        "by_status": by_status,
        "by_generality": by_generality,
        "applied_sites": applied_sites,
        "force_new_rate": forced / total if total else None,
    }


def export(
    conn: sqlite3.Connection,
    scope: projects.Scope | None,
    *,
    status: tuple[str, ...] | list[str] | None = ("pending", "postponed"),
    generality: str | None = None,
    target_kind: str | None = None,
    since: str | None = None,
    limit: int = 20,
) -> dict:
    """Lessons for a review conversation, most urgent first; each carries its sites and incidents.

    `since` is a YYYY-MM-DD date (or a full UTC timestamp) compared with `created_at`.
    """
    clause, params, label = _scope_filter(scope)
    if status:
        for value in status:
            taxonomy.validate_choice("status", value, taxonomy.LESSON_STATUSES)
        clause += f" AND l.status IN ({','.join('?' * len(status))})"
        params.extend(status)
    if generality is not None:
        taxonomy.validate_choice("generality", generality, taxonomy.LESSON_GENERALITIES)
        clause += " AND l.generality = ?"
        params.append(generality)
    if target_kind is not None:
        taxonomy.validate_choice("target_kind", target_kind, taxonomy.LESSON_TARGET_KINDS)
        clause += " AND l.target_kind = ?"
        params.append(target_kind)
    if since is not None:
        try:
            timeutil.parse(since)
            floor = since
        except ValueError:
            floor = timeutil.since_to_iso(since)
        clause += " AND l.created_at >= ?"
        params.append(floor)
    limit = _positive("limit", limit)
    rows = conn.execute(
        "SELECT l.*, p.slug AS origin_slug FROM lessons l "
        f"LEFT JOIN projects p ON p.id = l.origin_project_id WHERE {clause}",
        params,
    ).fetchall()
    rank_g = {value: i for i, value in enumerate(taxonomy.LESSON_GENERALITIES)}
    rank_s = {value: i for i, value in enumerate(taxonomy.LESSON_SEVERITIES)}
    rows = sorted(
        rows,
        key=lambda r: (rank_g[r["generality"]], rank_s[r["severity"]], -r["occurrences"], r["id"]),
    )[:limit]
    lessons = []
    for row in rows:
        item = _row_to_lesson(row)
        item["sites"] = _site_dicts(conn, row["id"])
        item["incidents"] = [
            record.incident_dict(conn, r["incident_id"])
            for r in conn.execute(
                "SELECT incident_id FROM lesson_incidents WHERE lesson_id = ? ORDER BY incident_id",
                (row["id"],),
            )
        ]
        lessons.append(item)
    return {"scope": label, "lessons": lessons}


_MD_FIELDS = (
    "status",
    "origin",
    "target_kind",
    "target",
    "what_happened",
    "evidence",
    "cause",
    "prevention",
    "proposal",
    "general_rule",
    "particular_justification",
    "tags",
)


def export_markdown(rows: list[dict]) -> str:
    """Markdown for exported lessons: one heading per lesson, then its fields, sites and incidents."""
    if not rows:
        return "_No lessons._\n"
    blocks = []
    for row in rows:
        lines = [
            f"## #{row['id']} · {row['generality']} · {row['severity']} · ×{row['occurrences']}"
        ]
        for field in _MD_FIELDS:
            value = row.get(field)
            if isinstance(value, list):
                value = ", ".join(value)
            if value in (None, ""):
                continue
            lines.append(f"- **{field}:** {value}")
        for site in row.get("sites", []):
            place = site["project"] if site["site"] == "project" else "global"
            detail = site["where_"] or site["reason"] or ""
            lines.append(f"- **site {place}:** {site['state']}" + (f" ({detail})" if detail else ""))
        for incident in row.get("incidents", []):
            session = f" {incident['session']}" if incident.get("session") else ""
            lines.append(
                f"- **incident #{incident['id']}:** {incident['change']}{session} "
                f"{incident['code']} {incident['severity']}: {incident['description']}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"
