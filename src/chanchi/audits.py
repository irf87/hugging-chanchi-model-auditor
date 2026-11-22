"""Redundant audits: open an audit, seat three auditors of different model families, show it.

Design: docs/designs/global-items.md, "Redundant audits". This module opens audits and rounds,
fills seats from the roster, refills a seat whose auditor could not run, and reads audits back.
chanchi never launches a harness: `launch` is a line for the orchestrator to run.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable

from chanchi import harnesses, modelspec, projects, taxonomy
from chanchi.db import transaction
from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now

SEATS = (1, 2, 3)
AUDITOR_AGENT = "agent-chanchi-auditor"
PROMPT = "<prompt>"
MIN_VOTERS = 2
DISTINCT_FAMILIES = 3

Which = Callable[[str], str | None]


def _text(field: str, value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        raise ChanchiError("invalid_value", f"{field} must not be empty", field=field)
    return text


def _spec(agent: str, model: str, effort: str | None) -> str:
    return modelspec.format_spec(agent, model, effort)


def _audit_row(conn: sqlite3.Connection, audit_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM audits WHERE id = ?", (audit_id,)).fetchone()
    if row is None:
        raise ChanchiError(
            "unknown_audit",
            f"audit {audit_id} does not exist",
            field="audit",
            hint="run `chanchi audit list` to see the audits",
        )
    return row


# --- project and change (decision D5) ---------------------------------------


def resolve_project_id(conn: sqlite3.Connection, slug: str | None) -> int | None:
    """An explicit slug must exist; without one, the project detected from git when it has a row, else None."""
    if slug is not None:
        return projects.resolve_project(conn, slug)["id"]
    try:
        detected, _ = projects.identify(None, conn=conn)
    except ChanchiError:
        return None
    row = conn.execute("SELECT id FROM projects WHERE slug = ?", (detected,)).fetchone()
    return row["id"] if row is not None else None


def _change_id(conn: sqlite3.Connection, project_id: int | None, ref: str) -> int:
    ref = _text("change", ref)
    if project_id is None:
        raise ChanchiError(
            "missing_prerequisite",
            "--change needs a project and none was found",
            field="change",
            hint="pass --project <slug> (a project is created by `chanchi change open` or `chanchi project register`)",
        )
    row = conn.execute(
        "SELECT id FROM changes WHERE project_id = ? AND ref = ?", (project_id, ref)
    ).fetchone()
    if row is None:
        known = [
            r["ref"] for r in conn.execute("SELECT ref FROM changes WHERE project_id = ? ORDER BY ref", (project_id,))
        ]
        raise ChanchiError(
            "unknown_change",
            f"change {ref!r} does not exist in this project",
            field="change",
            valid_values=known,
            hint="open it with `chanchi change open`",
        )
    return row["id"]


def _author_model_id(conn: sqlite3.Connection, author: str) -> int | None:
    """The catalog row of the author's spec, or None (decision D6: never an error)."""
    try:
        parsed = modelspec.parse(author, field="author")
    except ChanchiError:
        return None
    row = conn.execute(
        "SELECT id FROM models WHERE agent = ? AND model = ? AND active = 1", (parsed.agent, parsed.model)
    ).fetchone()
    return row["id"] if row is not None else None


# --- seats -------------------------------------------------------------------


def _active_seats(conn: sqlite3.Connection, round_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT s.*, m.agent, m.model, m.family FROM audit_seats s JOIN models m ON m.id = s.model_id "
        "WHERE s.round_id = ? AND s.status != 'unavailable' ORDER BY s.seat",
        (round_id,),
    ).fetchall()


def _unavailable_specs(conn: sqlite3.Connection, audit_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT m.agent, m.model, s.effort FROM audit_seats s "
        "JOIN audit_rounds r ON r.id = s.round_id JOIN models m ON m.id = s.model_id "
        "WHERE r.audit_id = ? AND s.status = 'unavailable'",
        (audit_id,),
    ).fetchall()
    return {_spec(r["agent"], r["model"], r["effort"]) for r in rows}


def is_degraded(conn: sqlite3.Connection, round_id: int) -> bool:
    """Fewer than three distinct known families among the seats that are not unavailable (decision D8)."""
    families = {row["family"] for row in _active_seats(conn, round_id) if row["family"]}
    return len(families) < DISTINCT_FAMILIES


def refresh_degraded(conn: sqlite3.Connection, round_id: int) -> bool:
    degraded = is_degraded(conn, round_id)
    conn.execute("UPDATE audit_rounds SET degraded = ? WHERE id = ?", (int(degraded), round_id))
    return degraded


def _family_hint(agent: str, model: str) -> str:
    return f"chanchi models set {agent}:{model} --family <name>"


def _candidates(
    conn: sqlite3.Connection, roster: list[dict], taken: set[str], blocked: set[str], which: Which
) -> tuple[list[dict], list[dict]]:
    """Split the roster into usable entries (in order) and skipped ones with their reason."""
    usable: list[dict] = []
    skipped: list[dict] = []
    seen: set[str] = set()
    for entry in roster:
        harness, model, effort = entry["harness"], entry["model"], entry.get("effort")
        spec = _spec(harness, model, effort)
        skip: dict | None = None
        row = conn.execute("SELECT * FROM models WHERE agent = ? AND model = ?", (harness, model)).fetchone()
        if not harnesses.available(harness, which):
            skip = {"reason": "not_on_path", "hint": f"install {harness} or put it on PATH"}
        elif row is None:
            skip = {
                "reason": "not_in_catalog",
                "hint": f"chanchi models add --agent {harness} --model {model} --cost <1-3>",
            }
        elif not row["active"]:
            skip = {"reason": "inactive", "hint": f"chanchi models set {harness}:{model} --active 1"}
        elif spec in blocked:
            skip = {"reason": "unavailable", "hint": "this auditor was marked unavailable in this audit"}
        elif spec in taken or spec in seen:
            skip = {"reason": "already_seated", "hint": "one spec never holds two seats of a round"}
        if skip is not None:
            item = {"spec": spec, **skip}
            if row is not None and row["family"] is None:
                item["family_hint"] = _family_hint(harness, model)
            skipped.append(item)
            continue
        seen.add(spec)
        usable.append({"entry": entry, "spec": spec, "row": row})
    return usable, skipped


def _fill(
    conn: sqlite3.Connection,
    round_id: int,
    seat_numbers: list[int],
    roster: list[dict],
    *,
    audit_id: int,
    which: Which = shutil.which,
    now: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Seat the given numbers from the roster, preferring families not yet seated.

    First pass: usable entries of a known family that is not seated yet. Second pass: the next
    usable entries in roster order. Returns (seated, skipped); fewer seats than asked means the
    roster is exhausted. The caller holds the transaction.
    """
    existing = _active_seats(conn, round_id)
    taken = {_spec(r["agent"], r["model"], r["effort"]) for r in existing}
    blocked = _unavailable_specs(conn, audit_id)
    usable, skipped = _candidates(conn, roster, taken, blocked, which)
    families = {r["family"] for r in existing if r["family"]}
    chosen: list[dict] = []
    for cand in usable:
        family = cand["row"]["family"]
        if len(chosen) < len(seat_numbers) and family and family not in families:
            chosen.append(cand)
            families.add(family)
    for cand in usable:
        if len(chosen) < len(seat_numbers) and cand not in chosen:
            chosen.append(cand)
    stamp = now or utc_now()
    seated: list[dict] = []
    for seat, cand in zip(seat_numbers, chosen):
        entry, row = cand["entry"], cand["row"]
        launch = harnesses.launch(
            entry["harness"], agent=AUDITOR_AGENT, model=entry["model"], effort=entry.get("effort"), prompt=PROMPT
        )
        conn.execute(
            "INSERT INTO audit_seats (round_id, seat, model_id, effort, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'assigned', ?, ?)",
            (round_id, seat, row["id"], entry.get("effort"), stamp, stamp),
        )
        view = {
            "seat": seat,
            "spec": cand["spec"],
            "family": row["family"],
            "effort": entry.get("effort"),
            "status": "assigned",
            "launch": launch,
        }
        if row["family"] is None:
            view["hint"] = _family_hint(entry["harness"], entry["model"])
        seated.append(view)
    return seated, skipped


def _seat_view(row: sqlite3.Row, *, launch: bool) -> dict:
    view = {
        "seat": row["seat"],
        "spec": _spec(row["agent"], row["model"], row["effort"]),
        "family": row["family"],
        "effort": row["effort"],
        "status": row["status"],
        "launch": None,
    }
    if launch and row["status"] == "assigned":
        view["launch"] = harnesses.launch(
            row["agent"], agent=AUDITOR_AGENT, model=row["model"], effort=row["effort"], prompt=PROMPT
        )
    if row["family"] is None:
        view["hint"] = _family_hint(row["agent"], row["model"])
    return view


# --- open --------------------------------------------------------------------


def open_audit(
    conn: sqlite3.Connection,
    *,
    kind: str,
    ref: str,
    author: str,
    commit: str | None = None,
    version: str | None = None,
    change: str | None = None,
    project_id: int | None = None,
    roster: list[dict],
    which: Which = shutil.which,
    now: str | None = None,
) -> dict:
    """Create an audit and its round 1, then fill the three seats from the roster."""
    taxonomy.validate_choice("kind", kind, taxonomy.AUDIT_SUBJECT_KINDS)
    ref = _text("ref", ref)
    author = _text("author", author)
    if (commit is None) == (version is None):
        raise ChanchiError(
            "invalid_value",
            "pass exactly one of --commit and --version",
            field="commit",
            hint="--commit <sha> for a repository subject, --version <x.y.z> for an item",
        )
    subject_at = _text("commit" if commit is not None else "version", commit if commit is not None else version)
    stamp = now or utc_now()
    with transaction(conn):
        change_id = _change_id(conn, project_id, change) if change is not None else None
        audit_id = conn.execute(
            "INSERT INTO audits (subject_kind, subject_ref, project_id, change_id, author_raw, "
            "author_model_id, opened_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, ref, project_id, change_id, author, _author_model_id(conn, author), stamp),
        ).lastrowid
        round_id = conn.execute(
            "INSERT INTO audit_rounds (audit_id, round, subject_at, opened_at) VALUES (?, 1, ?, ?)",
            (audit_id, subject_at, stamp),
        ).lastrowid
        seated, skipped = _fill(
            conn, round_id, list(SEATS), roster, audit_id=audit_id, which=which, now=stamp
        )
        degraded = refresh_degraded(conn, round_id)
        outcome = escalation = None
        if len(seated) < MIN_VOTERS:
            outcome, escalation = "escalated", "quorum"
            conn.execute(
                "UPDATE audit_rounds SET outcome = ?, escalation = ?, closed_at = ? WHERE id = ?",
                (outcome, escalation, stamp, round_id),
            )
            conn.execute(
                "UPDATE audits SET outcome = ?, closed_at = ? WHERE id = ?", (outcome, stamp, audit_id)
            )
        seats = [_seat_view(r, launch=outcome is None) for r in _active_seats(conn, round_id)]
    return {
        "audit_id": audit_id,
        "round": 1,
        "degraded": degraded,
        "outcome": outcome,
        "escalation": escalation,
        "skipped": skipped,
        "seats": seats,
    }


# --- unavailable ---------------------------------------------------------------


def mark_unavailable(
    conn: sqlite3.Connection,
    audit_id: int,
    *,
    round: int,  # noqa: A002 - the CLI flag is --round
    seat: int,
    reason: str,
    roster: list[dict],
    which: Which = shutil.which,
    now: str | None = None,
) -> dict:
    """Record that a seat's auditor could not run and refill the seat from the roster."""
    _audit_row(conn, audit_id)
    reason = _text("reason", reason)
    taxonomy.validate_choice("seat", seat, SEATS)
    stamp = now or utc_now()
    with transaction(conn):
        rnd = conn.execute(
            "SELECT * FROM audit_rounds WHERE audit_id = ? AND round = ?", (audit_id, round)
        ).fetchone()
        if rnd is None:
            known = [r["round"] for r in conn.execute(
                "SELECT round FROM audit_rounds WHERE audit_id = ? ORDER BY round", (audit_id,))]
            raise ChanchiError(
                "invalid_value", f"audit {audit_id} has no round {round}", field="round", valid_values=known
            )
        if rnd["closed_at"] is not None:
            raise ChanchiError(
                "invalid_transition",
                f"round {round} of audit {audit_id} is closed",
                field="round",
                hint="open the next round with `chanchi audit round`, or ask the human when it is escalated",
            )
        current = next((r for r in _active_seats(conn, rnd["id"]) if r["seat"] == seat), None)
        if current is None:
            raise ChanchiError(
                "invalid_transition",
                f"seat {seat} of round {round} is empty",
                field="seat",
                hint="the roster had no auditor left for it",
            )
        if current["status"] != "assigned":
            raise ChanchiError(
                "invalid_transition",
                f"seat {seat} is {current['status']}, only an assigned seat can become unavailable",
                field="seat",
            )
        conn.execute(
            "UPDATE audit_seats SET status = 'unavailable', reason = ?, updated_at = ? WHERE id = ?",
            (reason, stamp, current["id"]),
        )
        seated, skipped = _fill(conn, rnd["id"], [seat], roster, audit_id=audit_id, which=which, now=stamp)
        degraded = refresh_degraded(conn, rnd["id"])
    return {
        "audit_id": audit_id,
        "round": round,
        "unavailable": {
            "seat": seat,
            "spec": _spec(current["agent"], current["model"], current["effort"]),
            "reason": reason,
        },
        "seat": seated[0] if seated else None,
        "degraded": degraded,
        "skipped": skipped,
    }


# --- read ----------------------------------------------------------------------


def _round_view(conn: sqlite3.Connection, rnd: sqlite3.Row) -> dict:
    seats = []
    rows = conn.execute(
        "SELECT s.*, m.agent, m.model, m.family FROM audit_seats s JOIN models m ON m.id = s.model_id "
        "WHERE s.round_id = ? ORDER BY s.seat, s.id",
        (rnd["id"],),
    ).fetchall()
    for row in rows:
        seat = {
            "seat": row["seat"],
            "spec": _spec(row["agent"], row["model"], row["effort"]),
            "family": row["family"],
            "effort": row["effort"],
            "status": row["status"],
            "verdict": row["verdict"],
            "blocking": row["blocking"],
            "major": row["major"],
            "minor": row["minor"],
            "report": row["report"],
            "reason": row["reason"],
            "dissents": [
                {k: d[k] for k in ("finding", "severity", "decision", "evidence")}
                for d in conn.execute(
                    "SELECT * FROM audit_dissents WHERE seat_id = ? ORDER BY id", (row["id"],)
                )
            ],
        }
        seats.append(seat)
    return {
        "round": rnd["round"],
        "subject_at": rnd["subject_at"],
        "degraded": bool(rnd["degraded"]),
        "outcome": rnd["outcome"],
        "escalation": rnd["escalation"],
        "opened_at": rnd["opened_at"],
        "closed_at": rnd["closed_at"],
        "seats": seats,
    }


def show(conn: sqlite3.Connection, audit_id: int) -> dict:
    """Every round, seat (unavailable ones too), vote, dissent and outcome of one audit."""
    audit = _audit_row(conn, audit_id)
    project = conn.execute("SELECT slug FROM projects WHERE id = ?", (audit["project_id"],)).fetchone()
    change = conn.execute("SELECT ref FROM changes WHERE id = ?", (audit["change_id"],)).fetchone()
    author = conn.execute(
        "SELECT agent, model FROM models WHERE id = ?", (audit["author_model_id"],)
    ).fetchone()
    rounds = conn.execute(
        "SELECT * FROM audit_rounds WHERE audit_id = ? ORDER BY round", (audit_id,)
    ).fetchall()
    return {
        "audit": {
            "id": audit["id"],
            "kind": audit["subject_kind"],
            "ref": audit["subject_ref"],
            "project": project["slug"] if project else None,
            "change": change["ref"] if change else None,
            "author": audit["author_raw"],
            "author_model": f"{author['agent']}:{author['model']}" if author else None,
            "outcome": audit["outcome"],
            "opened_at": audit["opened_at"],
            "closed_at": audit["closed_at"],
        },
        "rounds": [_round_view(conn, r) for r in rounds],
    }


def list_audits(conn: sqlite3.Connection, *, kind: str | None = None, ref: str | None = None) -> list[dict]:
    if kind is not None:
        taxonomy.validate_choice("kind", kind, taxonomy.AUDIT_SUBJECT_KINDS)
    query = (
        "SELECT a.*, (SELECT COUNT(*) FROM audit_rounds r WHERE r.audit_id = a.id) AS rounds "
        "FROM audits a WHERE 1 = 1"
    )
    params: list = []
    if kind is not None:
        query += " AND a.subject_kind = ?"
        params.append(kind)
    if ref is not None:
        query += " AND a.subject_ref = ?"
        params.append(ref)
    return [
        {
            "id": r["id"],
            "kind": r["subject_kind"],
            "ref": r["subject_ref"],
            "rounds": r["rounds"],
            "outcome": r["outcome"],
            "opened_at": r["opened_at"],
            "closed_at": r["closed_at"],
        }
        for r in conn.execute(query + " ORDER BY a.id", params)
    ]
