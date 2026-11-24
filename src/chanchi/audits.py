"""Redundant audits: open an audit, seat three auditors of different model families, show it.

Design: docs/designs/global-items.md, "Redundant audits". This module opens audits and rounds,
fills seats from the roster, refills a seat whose auditor could not run, and reads audits back.
chanchi never launches a harness: `launch` is a line for the orchestrator to run.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path

from chanchi import harnesses, items, modelspec, projects, taxonomy
from chanchi.db import transaction
from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now

SEATS = (1, 2, 3)
AUDITOR_AGENT = "agent-chanchi-auditor"
PROMPT = "<prompt>"
REPORT_DIR = "<report-dir>"
MIN_VOTERS = 2
DISTINCT_FAMILIES = 3
MAX_ROUNDS = 3

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
        "SELECT s.*, m.agent, m.model, m.family, m.active FROM audit_seats s JOIN models m ON m.id = s.model_id "
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
            binary = harnesses.binary(harness)
            target = harness if binary == harness else f"{binary} ({harness})"
            skip = {"reason": "not_on_path", "hint": f"install {target} or put it on PATH"}
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
            entry["harness"],
            agent=AUDITOR_AGENT,
            model=entry["model"],
            effort=entry.get("effort"),
            prompt=PROMPT,
            profile="read-only",
            add_dirs=(REPORT_DIR,),
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
            row["agent"],
            agent=AUDITOR_AGENT,
            model=row["model"],
            effort=row["effort"],
            prompt=PROMPT,
            profile="read-only",
            add_dirs=(REPORT_DIR,),
        )
    if row["family"] is None:
        view["hint"] = _family_hint(row["agent"], row["model"])
    return view


# --- helpers -----------------------------------------------------------------


def _subject_at(commit: str | None, version: str | None) -> str:
    if (commit is None) == (version is None):
        raise ChanchiError(
            "invalid_value",
            "pass exactly one of --commit and --version",
            field="commit",
            hint="--commit <sha> for a repository subject, --version <x.y.z> for an item",
        )
    return _text("commit" if commit is not None else "version", commit if commit is not None else version)


def _round_subject(
    kind: str, ref: str, commit: str | None, version: str | None, sync_root: Path | None
) -> str:
    """`subject_at` of a round: `<version>@<content hash>` for an item (decision D6), else commit or version."""
    if kind != "item":
        return _subject_at(commit, version)
    if commit is not None:
        raise ChanchiError(
            "invalid_value",
            "an item audit takes --version, not --commit",
            field="commit",
            hint="--version <x.y.z> of the item; chanchi records the content hash",
        )
    if version is None:
        raise ChanchiError(
            "invalid_value", "an item audit needs --version <x.y.z>", field="version",
            hint="the item's current version: `chanchi items list`",
        )
    return items.subject_at(sync_root, ref, _text("version", version))


def _round_row(conn: sqlite3.Connection, audit_id: int, round_no: int) -> sqlite3.Row:
    rnd = conn.execute(
        "SELECT * FROM audit_rounds WHERE audit_id = ? AND round = ?", (audit_id, round_no)
    ).fetchone()
    if rnd is None:
        known = [
            r["round"]
            for r in conn.execute(
                "SELECT round FROM audit_rounds WHERE audit_id = ? ORDER BY round", (audit_id,)
            )
        ]
        raise ChanchiError(
            "invalid_value", f"audit {audit_id} has no round {round_no}", field="round", valid_values=known
        )
    return rnd


def _open_round(conn: sqlite3.Connection, audit_id: int, round_no: int) -> sqlite3.Row:
    rnd = _round_row(conn, audit_id, round_no)
    if rnd["closed_at"] is not None:
        raise ChanchiError(
            "invalid_transition",
            f"round {round_no} of audit {audit_id} is closed",
            field="round",
            hint="open the next round with `chanchi audit round`, or ask the human when it is escalated",
        )
    return rnd


def _require_seat(
    conn: sqlite3.Connection, round_id: int, round_no: int, seat: int, *, status: str, action: str
) -> sqlite3.Row:
    current = next((r for r in _active_seats(conn, round_id) if r["seat"] == seat), None)
    if current is None:
        raise ChanchiError(
            "invalid_transition",
            f"seat {seat} of round {round_no} is empty",
            field="seat",
            hint="the roster had no auditor left for it",
        )
    if current["status"] != status:
        article = "an" if status == "assigned" else "a"
        raise ChanchiError(
            "invalid_transition",
            f"seat {seat} is {current['status']}, only {article} {status} seat can {action}",
            field="seat",
        )
    return current


def _finalize_round_open(
    conn: sqlite3.Connection,
    audit_id: int,
    round_no: int,
    round_id: int,
    skipped: list[dict],
    stamp: str,
) -> dict:
    """Recompute degraded, apply the quorum escalation rule, and return the round-open payload."""
    degraded = refresh_degraded(conn, round_id)
    active = _active_seats(conn, round_id)
    outcome_val = escalation = None
    if len(active) < MIN_VOTERS:
        outcome_val, escalation = "escalated", "quorum"
        conn.execute(
            "UPDATE audit_rounds SET outcome = ?, escalation = ?, closed_at = ? WHERE id = ?",
            (outcome_val, escalation, stamp, round_id),
        )
        conn.execute(
            "UPDATE audits SET outcome = ?, closed_at = ? WHERE id = ?", (outcome_val, stamp, audit_id)
        )
    seats = [_seat_view(r, launch=outcome_val is None) for r in active]
    return {
        "audit_id": audit_id,
        "round": round_no,
        "degraded": degraded,
        "outcome": outcome_val,
        "escalation": escalation,
        "skipped": skipped,
        "seats": seats,
    }


def _non_negative(field: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ChanchiError("invalid_value", f"{field} must be a non-negative integer, got {value!r}", field=field)
    return value


def _field(row, key: str, default=None):
    try:
        val = row[key]
    except (KeyError, IndexError):
        return default
    return default if val is None else val


def _is_approval(vote_row) -> bool:
    verdict = _field(vote_row, "verdict")
    if verdict == "pass":
        return True
    if verdict == "pass_with_fixes":
        return _field(vote_row, "blocking", 0) == 0 and _field(vote_row, "major", 0) == 0
    return False


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
    sync_root: Path | None = None,
) -> dict:
    """Create an audit and its round 1, then fill the three seats from the roster."""
    taxonomy.validate_choice("kind", kind, taxonomy.AUDIT_SUBJECT_KINDS)
    ref = _text("ref", ref)
    author = _text("author", author)
    subject_at = _round_subject(kind, ref, commit, version, sync_root)
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
        _, skipped = _fill(
            conn, round_id, list(SEATS), roster, audit_id=audit_id, which=which, now=stamp
        )
        return _finalize_round_open(conn, audit_id, 1, round_id, skipped, stamp)


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
        rnd = _open_round(conn, audit_id, round)
        current = _require_seat(conn, rnd["id"], round, seat, status="assigned", action="become unavailable")
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


# --- vote, dissent, outcome, close, round ------------------------------------


def vote(
    conn: sqlite3.Connection,
    audit_id: int,
    *,
    round: int,  # noqa: A002 - the CLI flag is --round
    seat: int,
    verdict: str,
    blocking: int,
    major: int,
    minor: int,
    report: str,
    now: str | None = None,
) -> dict:
    """Record an auditor seat's verdict, severity counts and report path."""
    _audit_row(conn, audit_id)
    taxonomy.validate_choice("seat", seat, SEATS)
    taxonomy.validate_choice("verdict", verdict, taxonomy.AUDIT_VERDICTS)
    blocking = _non_negative("blocking", blocking)
    major = _non_negative("major", major)
    minor = _non_negative("minor", minor)
    report = _text("report", report)
    if verdict == "pass" and (blocking > 0 or major > 0):
        raise ChanchiError(
            "invalid_value",
            "a pass verdict cannot carry blocking or major findings",
            field="verdict",
            hint="vote pass_with_fixes",
        )
    stamp = now or utc_now()
    with transaction(conn):
        rnd = _open_round(conn, audit_id, round)
        current = _require_seat(conn, rnd["id"], round, seat, status="assigned", action="vote")
        conn.execute(
            "UPDATE audit_seats SET status = 'voted', verdict = ?, blocking = ?, major = ?, "
            "minor = ?, report = ?, updated_at = ? WHERE id = ?",
            (verdict, blocking, major, minor, report, stamp, current["id"]),
        )
    return {
        "audit_id": audit_id,
        "round": round,
        "seat": {
            "seat": seat,
            "spec": _spec(current["agent"], current["model"], current["effort"]),
            "family": current["family"],
            "effort": current["effort"],
            "status": "voted",
            "verdict": verdict,
            "blocking": blocking,
            "major": major,
            "minor": minor,
            "report": report,
        },
    }


def dissent(
    conn: sqlite3.Connection,
    audit_id: int,
    *,
    round: int,  # noqa: A002 - the CLI flag is --round
    seat: int,
    finding: str,
    severity: str,
    decision: str,
    evidence: str,
    now: str | None = None,
) -> dict:
    """Record the orchestrator's confirmed/rejected decision on a lone finding of a voted seat."""
    _audit_row(conn, audit_id)
    taxonomy.validate_choice("seat", seat, SEATS)
    taxonomy.validate_choice("severity", severity, taxonomy.AUDIT_SEVERITIES)
    taxonomy.validate_choice("decision", decision, taxonomy.DISSENT_DECISIONS)
    finding = _text("finding", finding)
    evidence = _text("evidence", evidence)
    stamp = now or utc_now()
    with transaction(conn):
        rnd = _open_round(conn, audit_id, round)
        current = _require_seat(conn, rnd["id"], round, seat, status="voted", action="record a dissent")
        dissent_id = conn.execute(
            "INSERT INTO audit_dissents (seat_id, finding, severity, decision, evidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (current["id"], finding, severity, decision, evidence, stamp),
        ).lastrowid
    return {
        "audit_id": audit_id,
        "round": round,
        "seat": seat,
        "dissent": {
            "id": dissent_id,
            "finding": finding,
            "severity": severity,
            "decision": decision,
            "evidence": evidence,
        },
    }


def outcome(votes: list, dissents: list, round_no: int) -> tuple[str, str | None]:
    """Compute (outcome, escalation) for a round from its voted seats, dissents and round number."""
    if len(votes) < MIN_VOTERS:
        return ("escalated", "quorum")
    fails = sum(1 for v in votes if _field(v, "verdict") == "fail")
    if fails >= 2:
        raw = "rework"
    else:
        approvals = sum(1 for v in votes if _is_approval(v))
        blocking_dissent = any(
            _field(d, "decision") == "confirmed" and _field(d, "severity") in ("blocking", "major")
            for d in dissents
        )
        raw = "accepted" if approvals >= 2 and not blocking_dissent else "fix"
    if raw in ("rework", "fix") and round_no == MAX_ROUNDS:
        return ("escalated", "round_cap")
    return (raw, None)


def close_round(
    conn: sqlite3.Connection,
    audit_id: int,
    *,
    round: int,  # noqa: A002 - the CLI flag is --round
    now: str | None = None,
) -> dict:
    """Close an open round once no seat is assigned, computing its outcome and escalation."""
    _audit_row(conn, audit_id)
    stamp = now or utc_now()
    with transaction(conn):
        rnd = _open_round(conn, audit_id, round)
        active = _active_seats(conn, rnd["id"])
        assigned = [r["seat"] for r in active if r["status"] == "assigned"]
        if assigned:
            raise ChanchiError(
                "invalid_transition",
                f"round {round} still has assigned seats: {assigned}",
                field="seat",
                hint="record each seat's vote with `chanchi audit vote` or mark it unavailable first",
            )
        votes = [r for r in active if r["status"] == "voted"]
        dissents = conn.execute(
            "SELECT d.*, s.seat, m.agent, m.model, s.effort FROM audit_dissents d "
            "JOIN audit_seats s ON s.id = d.seat_id JOIN models m ON m.id = s.model_id "
            "WHERE s.round_id = ? ORDER BY s.seat, d.id",
            (rnd["id"],),
        ).fetchall()
        round_outcome, escalation = outcome(votes, dissents, round)
        audit_closed_at = stamp if round_outcome in ("accepted", "escalated") else None
        conn.execute(
            "UPDATE audit_rounds SET outcome = ?, escalation = ?, closed_at = ? WHERE id = ?",
            (round_outcome, escalation, stamp, rnd["id"]),
        )
        conn.execute(
            "UPDATE audits SET outcome = ?, closed_at = ? WHERE id = ?",
            (round_outcome, audit_closed_at, audit_id),
        )
    result: dict = {
        "audit_id": audit_id,
        "round": round,
        "outcome": round_outcome,
        "escalation": escalation,
        "closed_at": stamp,
        "audit_closed_at": audit_closed_at,
    }
    if round_outcome == "accepted":
        minor_fixes: list[dict] = []
        for row in votes:
            if _is_approval(row) and (row["minor"] or 0) > 0:
                minor_fixes.append(
                    {
                        "kind": "seat",
                        "seat": row["seat"],
                        "spec": _spec(row["agent"], row["model"], row["effort"]),
                        "minor": row["minor"],
                        "report": row["report"],
                    }
                )
        for d in dissents:
            if d["decision"] == "confirmed" and d["severity"] == "minor":
                minor_fixes.append(
                    {
                        "kind": "dissent",
                        "seat": d["seat"],
                        "spec": _spec(d["agent"], d["model"], d["effort"]),
                        "finding": d["finding"],
                        "evidence": d["evidence"],
                    }
                )
        result["minor_fixes"] = minor_fixes
    return result


def next_round(
    conn: sqlite3.Connection,
    audit_id: int,
    *,
    commit: str | None = None,
    version: str | None = None,
    roster: list[dict],
    which: Which = shutil.which,
    now: str | None = None,
    sync_root: Path | None = None,
) -> dict:
    """Open the next round with the same seats when still available, refilling any gaps."""
    audit = _audit_row(conn, audit_id)
    subject_at = _round_subject(audit["subject_kind"], audit["subject_ref"], commit, version, sync_root)
    stamp = now or utc_now()
    with transaction(conn):
        last = conn.execute(
            "SELECT * FROM audit_rounds WHERE audit_id = ? ORDER BY round DESC LIMIT 1", (audit_id,)
        ).fetchone()
        if last is None or last["closed_at"] is None:
            round_label = last["round"] if last is not None else 1
            raise ChanchiError(
                "invalid_transition",
                f"round {round_label} of audit {audit_id} is not closed yet",
                field="round",
                hint="close it with `chanchi audit close` first",
            )
        if last["outcome"] not in ("fix", "rework"):
            raise ChanchiError(
                "invalid_transition",
                f"audit {audit_id} ended with {last['outcome']}; no next round is allowed",
                field="outcome",
            )
        if last["round"] >= MAX_ROUNDS:
            raise ChanchiError(
                "invalid_transition",
                f"audit {audit_id} is already at round {MAX_ROUNDS}",
                field="round",
            )
        next_no = last["round"] + 1
        round_id = conn.execute(
            "INSERT INTO audit_rounds (audit_id, round, subject_at, opened_at) VALUES (?, ?, ?, ?)",
            (audit_id, next_no, subject_at, stamp),
        ).lastrowid
        blocked = _unavailable_specs(conn, audit_id)
        by_seat = {r["seat"]: r for r in _active_seats(conn, last["id"])}
        to_fill: list[int] = []
        for seat in SEATS:
            prev = by_seat.get(seat)
            if (
                prev is not None
                and harnesses.available(prev["agent"], which)
                and prev["active"]
                and _spec(prev["agent"], prev["model"], prev["effort"]) not in blocked
            ):
                conn.execute(
                    "INSERT INTO audit_seats (round_id, seat, model_id, effort, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'assigned', ?, ?)",
                    (round_id, seat, prev["model_id"], prev["effort"], stamp, stamp),
                )
            else:
                to_fill.append(seat)
        skipped: list[dict] = []
        if to_fill:
            _, skipped = _fill(conn, round_id, to_fill, roster, audit_id=audit_id, which=which, now=stamp)
        return _finalize_round_open(conn, audit_id, next_no, round_id, skipped, stamp)


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
