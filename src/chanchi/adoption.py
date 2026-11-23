"""Global item adoption: project inbox and audited adoption decisions.

Design: docs/designs/global-items.md, "D. Adopt" and "Data model (migration 006)".
This is a domain module: it reads audit tables with SQL, never imports `audits`,
never reads project files, and never renders output.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from chanchi import db, inventory, items, taxonomy
from chanchi.errors import ChanchiError
from chanchi.timeutil import utc_now

WRAPPER_LOCAL_SUFFIX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@contextmanager
def _write(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One write transaction; joins the caller's transaction when one is already open."""
    if conn.in_transaction:
        yield conn
    else:
        with db.transaction(conn):
            yield conn


def _retired_map(sync_root: Path) -> dict[str, dict]:
    """Last retired.json entry per item name, or raise `invalid_value` if malformed."""
    entries, error = items.retired_entries(sync_root)
    if error is not None:
        raise ChanchiError("invalid_value", error, field="items", hint="chanchi items check")
    by_name: dict[str, dict] = {}
    for entry in entries or ():
        by_name[entry["name"]] = entry
    return by_name


def _unreadable(item: items.Item) -> bool:
    return item.version is None or item.status is None or item.hash is None


def _entry_state(*, is_retired: bool, item_version: str, decision_row: Mapping | None) -> str | None:
    """Inbox state of one global item for this project, or None when unlisted."""
    if is_retired:
        if decision_row is None:
            return None
        choice = decision_row["decision"]
        if choice in ("adopt", "wrap"):
            return "retired"
        if choice == "deprecate":
            return "deprecate_pending"
        return "up_to_date"
    if decision_row is None:
        return "new"
    if decision_row["decision"] == "deprecate":
        return "deprecate_pending"
    if decision_row["version"] != item_version:
        return "changed"
    return "up_to_date"


def _decision_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "decision": row["decision"],
        "version": row["version"],
        "hash": row["hash"],
        "local_item": row["local_item"],
        "reason": row["reason"],
        "audit_id": row["audit_id"],
        "decided_at": row["decided_at"],
    }


def _short_name(global_item: str) -> str:
    return global_item.split("-chanchi-global-", 1)[1]


def _proposal_paths(conn: sqlite3.Connection, slug: str) -> dict[str, set[str]]:
    """Paths and aliases recorded for `slug` in built proposals, keyed by `global_item`."""
    found: dict[str, set[str]] = {}
    rows = conn.execute(
        "SELECT global_item, evidence FROM item_proposals WHERE global_item IS NOT NULL"
    ).fetchall()
    for row in rows:
        evidence = json.loads(row["evidence"])
        paths = found.setdefault(row["global_item"], set())
        for copy in evidence.get("copies", ()):
            if copy.get("project") != slug:
                continue
            if copy.get("path"):
                paths.add(copy["path"])
            for alias in copy.get("aliases", ()):
                paths.add(alias)
    return found


def _similar_items(
    item: items.Item,
    project_rows: list[sqlite3.Row],
    root: Path | None,
    proposal_paths: set[str],
) -> list[dict]:
    """Current `project_items` of the same kind matching name slug or proposal evidence."""
    short = _short_name(item.name)
    matches: list[dict] = []
    for row in project_rows:
        if row["kind"] != item.kind:
            continue
        if inventory.slug_of(row["name"]) == short or row["path"] in proposal_paths:
            matches.append({
                "kind": row["kind"],
                "name": row["name"],
                "path": row["path"],
                "abs_path": None if root is None else str(root / row["path"]),
                "lines": row["lines"],
                "sha256": row["sha256"],
            })
    return matches


def inbox(conn: sqlite3.Connection, sync_root: Path, *, project_id: int, slug: str, all_: bool = False) -> dict:
    """List global items needing an adoption decision for one registered project."""
    retired_map = _retired_map(sync_root)
    loaded = sorted(items.load(sync_root), key=lambda i: i.name)

    decisions: dict[str, sqlite3.Row] = {}
    for row in conn.execute(
        "SELECT * FROM item_decisions WHERE project_id = ? ORDER BY id", (project_id,)
    ):
        decisions[row["global_item"]] = row

    project_rows = conn.execute(
        "SELECT * FROM project_items WHERE project_id = ? ORDER BY path", (project_id,)
    ).fetchall()
    root = inventory.project_root(conn, project_id)
    prop_paths = _proposal_paths(conn, slug)

    entries: list[dict] = []
    problems: list[dict] = []
    for item in loaded:
        if _unreadable(item):
            problems.append({"item": item.name, "hint": "chanchi items check"})
            continue
        is_retired = item.status == "retired" or item.name in retired_map
        if not is_retired and item.status != "published":
            continue
        dec = decisions.get(item.name)
        state = _entry_state(is_retired=is_retired, item_version=item.version, decision_row=dec)
        if state is None:
            continue
        if not all_ and state == "up_to_date":
            continue
        version_changed = dec is not None and dec["version"] != item.version
        replaced_by = retired_map[item.name].get("replaced_by") if is_retired and item.name in retired_map else None
        entries.append({
            "item": item.name,
            "kind": item.kind,
            "version": item.version,
            "hash": item.hash,
            "status": item.status,
            "state": state,
            "version_changed": version_changed,
            "replaced_by": replaced_by,
            "path": str(item.path),
            "decision": _decision_dict(dec),
            "similar": _similar_items(item, project_rows, root, prop_paths.get(item.name, set())),
        })
    return {"project": slug, "entries": entries, "problems": problems}


def _validate_local(*, decision: str, kind: str, slug: str, is_retired: bool, local: str | None) -> str | None:
    if local is not None:
        local = local.strip()
        if not local:
            raise ChanchiError("invalid_value", "local item must not be empty", field="local")
    if decision == "wrap":
        prefix = f"{kind}-chanchi-{inventory.slug_of(slug)}-"
        if local is None:
            raise ChanchiError(
                "invalid_value",
                "--local is required for wrap",
                field="local",
                hint=f"name the wrapper {prefix}<name>",
            )
        if not local.startswith(prefix) or WRAPPER_LOCAL_SUFFIX.match(local[len(prefix) :]) is None:
            raise ChanchiError(
                "invalid_value",
                f"wrapper name {local!r} must match {prefix}<name> (kebab-case)",
                field="local",
                hint=f"use prefix {prefix}<name>",
            )
    elif decision in ("keep", "deprecate") and not is_retired and local is None:
        raise ChanchiError(
            "invalid_value",
            f"--local is required for {decision} on a published item",
            field="local",
            hint="pass the project item that is kept or to be removed",
        )
    return local


def _validate_audit(conn: sqlite3.Connection, *, audit_id: int, project_id: int, slug: str, item: str) -> None:
    audit = conn.execute("SELECT * FROM audits WHERE id = ?", (audit_id,)).fetchone()
    if audit is None:
        raise ChanchiError(
            "unknown_audit",
            f"audit {audit_id} does not exist",
            field="audit",
            hint="run `chanchi audit list --kind adoption` to see the audits",
        )
    expected_ref = f"{slug}:{item}"
    if audit["subject_kind"] != "adoption" or audit["subject_ref"] != expected_ref or audit["project_id"] != project_id:
        raise ChanchiError(
            "invalid_value",
            f"audit {audit_id} is not an adoption audit of {expected_ref!r} for project {slug!r}",
            field="audit",
            hint=f"chanchi audit open --kind adoption --ref {expected_ref} --project {slug} --author <spec> --commit <sha>",
        )
    last = conn.execute(
        "SELECT * FROM audit_rounds WHERE audit_id = ? ORDER BY round DESC LIMIT 1", (audit_id,)
    ).fetchone()
    if last is None or last["outcome"] != "accepted":
        raise ChanchiError(
            "invalid_transition",
            f"audit {audit_id} is not accepted",
            field="audit",
            hint="finish the audit rounds",
        )
    used = conn.execute("SELECT id FROM item_decisions WHERE audit_id = ?", (audit_id,)).fetchone()
    if used is not None:
        raise ChanchiError(
            "invalid_value",
            f"audit {audit_id} is already used by decision {used['id']}",
            field="audit",
            hint="open a new adoption audit for this decision",
        )


def decide(
    conn: sqlite3.Connection,
    sync_root: Path,
    *,
    project_id: int,
    slug: str,
    item: str,
    decision: str,
    version: str,
    reason: str,
    audit_id: int,
    local: str | None = None,
    now: str | None = None,
) -> dict:
    """Record an audited adoption decision for one global item in one registered project."""
    match = items.GLOBAL_NAME.match(item) if isinstance(item, str) else None
    loaded = (
        next((entry for entry in items.load(sync_root) if entry.name == item and entry.kind == match.group(1)), None)
        if match is not None
        else None
    )
    if loaded is None:
        raise ChanchiError(
            "invalid_value",
            f"unknown global item {item!r}",
            field="item",
            hint="run `chanchi items list`",
        )
    if _unreadable(loaded):
        raise ChanchiError(
            "invalid_value",
            f"{item} cannot be read fully",
            field="item",
            hint="chanchi items check",
        )
    retired_map = _retired_map(sync_root)
    is_retired = loaded.status == "retired" or item in retired_map
    if not is_retired and loaded.status == "draft":
        raise ChanchiError(
            "invalid_transition",
            f"{item} is a draft and cannot be decided yet",
            field="item",
            hint="publish the item with `chanchi items publish` first",
        )
    taxonomy.validate_choice("decision", decision, taxonomy.ADOPTION_DECISIONS)
    if version != loaded.version:
        raise ChanchiError(
            "invalid_value",
            f"{item} is at version {loaded.version}, not {version}",
            field="version",
            hint="pass the item's current version: `chanchi items list`",
        )
    if is_retired and decision not in ("keep", "deprecate"):
        replaced_by = retired_map[item].get("replaced_by") if item in retired_map else None
        hint = (
            f"adopt or wrap its replaced_by {replaced_by!r} as its own entry"
            if replaced_by
            else "adopt or wrap its replaced_by as its own entry"
        )
        raise ChanchiError(
            "invalid_transition",
            f"{item} is retired and takes only keep or deprecate, not {decision}",
            field="decision",
            valid_values=("keep", "deprecate"),
            hint=hint,
        )
    reason = (reason or "").strip()
    if not reason:
        raise ChanchiError("invalid_value", "reason must not be empty", field="reason")

    clean_local = _validate_local(
        decision=decision, kind=loaded.kind, slug=slug, is_retired=is_retired, local=local
    )
    _validate_audit(conn, audit_id=audit_id, project_id=project_id, slug=slug, item=item)

    stamp = now or utc_now()
    with _write(conn):
        cursor = conn.execute(
            "INSERT INTO item_decisions "
            "(project_id, global_item, version, hash, decision, local_item, reason, audit_id, decided_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, item, version, loaded.hash, decision, clean_local, reason, audit_id, stamp),
        )
        decision_id = cursor.lastrowid
    state = _entry_state(
        is_retired=is_retired,
        item_version=loaded.version,
        decision_row={"decision": decision, "version": version},
    )
    return {
        "id": decision_id,
        "project": slug,
        "item": item,
        "version": version,
        "hash": loaded.hash,
        "decision": decision,
        "local_item": clean_local,
        "reason": reason,
        "audit_id": audit_id,
        "decided_at": stamp,
        "state": state,
    }
