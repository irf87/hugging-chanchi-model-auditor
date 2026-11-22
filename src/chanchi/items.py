"""Global items in SYNC/ITEMS: frontmatter, content hash, check, list, publish and retire.

Design: docs/designs/global-items.md, "Versions and hashes". This module is a domain module:
it never imports `audits` (it reads the audit tables with SQL) and never renders output.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from chanchi import agents_sync, taxonomy
from chanchi.errors import ChanchiError

GLOBAL_NAME = re.compile(r"^(agent|skill)-chanchi-global-[a-z0-9]+(-[a-z0-9]+)*$")
MANIFEST = {"agent": "AGENT.md", "skill": "SKILL.md"}
KIND_FOLDER = {kind: folder for folder, kind in taxonomy.ITEM_KINDS.items()}
CHANGELOG = "CHANGELOG.md"
RETIRED = "retired.json"
SECTION = re.compile(r"^## (\d+\.\d+\.\d+) — (\d{4}-\d{2}-\d{2})\s*$")
PUBLISHED_LINE = re.compile(
    r"^Published: (\d{4}-\d{2}-\d{2}) · audit (\d+) · audited ([0-9a-f]{64}) · sha256 ([0-9a-f]{64})\s*$"
)
BLOCK_SCALAR = re.compile(r"^[>|][+-]?\d*$")
# Problems that stop `retire` because the item's version or status cannot be trusted.
STRUCTURAL = ("bad_name", "wrong_folder", "name_mismatch", "bad_frontmatter", "bad_version", "bad_status")


@dataclass(frozen=True)
class Item:
    name: str
    kind: str
    path: Path
    version: str | None = None
    status: str | None = None
    hash: str | None = None
    published_hash: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "version": self.version,
            "status": self.status,
            "hash": self.hash,
            "published_hash": self.published_hash,
        }


def _bad_frontmatter(detail: str) -> ChanchiError:
    return ChanchiError(
        "invalid_value",
        f"frontmatter: {detail}",
        field="frontmatter",
        hint="a --- block of `key: value` lines; SKILL.md may hold a `metadata:` block of two-space-indented "
        "`key: value` lines; no other nesting and no folded or multi-line values",
    )


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


# --- frontmatter ----------------------------------------------------------------


def _frontmatter_end(lines: list[str]) -> int:
    if not lines or lines[0].rstrip("\r") != "---":
        raise _bad_frontmatter("the file must start with a --- line")
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r") == "---":
            return index
    raise _bad_frontmatter("the --- block is never closed")


def read_frontmatter(text: str) -> dict:
    """Flat `key: value` lines plus an optional `metadata:` block as a dict; anything else is an error."""
    lines = text.split("\n")
    end = _frontmatter_end(lines)
    out: dict = {}
    block: dict | None = None
    for raw in lines[1:end]:
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        key, sep, value = line.strip().partition(":")
        key, value = key.strip(), value.strip()
        if line[0] in " \t":
            if block is None or not line.startswith("  ") or line[2:3] in (" ", "\t"):
                raise _bad_frontmatter(f"unexpected indentation or nesting in {line.strip()!r}")
            if not sep or not key or not value or BLOCK_SCALAR.match(value):
                raise _bad_frontmatter(f"metadata lines are `key: value` on one line, got {line.strip()!r}")
            if key in block:
                raise _bad_frontmatter(f"duplicate metadata key {key!r}")
            block[key] = agents_sync.unquote(value)
            continue
        block = None
        if not sep or not key or key.startswith("-"):
            raise _bad_frontmatter(f"bad line {line!r}")
        if key in out:
            raise _bad_frontmatter(f"duplicate key {key!r}")
        if key == "metadata":
            if value:
                raise _bad_frontmatter("metadata must be a block of indented lines")
            out[key] = block = {}
            continue
        if BLOCK_SCALAR.match(value):
            raise _bad_frontmatter(f"{key} must be on one line (no folded or multi-line value)")
        out[key] = agents_sync.unquote(value)
    return out


def _quote_of(value: str) -> str:
    value = value.strip()
    return value[0] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else ""


def _cr(line: str) -> str:
    return "\r" if line.endswith("\r") else ""


def _is_indented(line: str) -> bool:
    return line[:1] in (" ", "\t")


def _key(line: str) -> str:
    return line.partition(":")[0].strip()


def set_status(text: str, kind: str, status: str) -> str:
    """Rewrite only the `status` value, keeping its form; insert the line after `version` when missing."""
    taxonomy.validate_choice("status", status, taxonomy.ITEM_STATUSES)
    lines = text.split("\n")
    end = _frontmatter_end(lines)
    if kind == "agent":
        found = version = None
        for index in range(1, end):
            if _is_indented(lines[index]):
                continue
            if _key(lines[index]) == "status":
                found = index
            elif _key(lines[index]) == "version":
                version = index
        if found is not None:
            q = _quote_of(lines[found].partition(":")[2])
            lines[found] = f"status: {q}{status}{q}{_cr(lines[found])}"
        else:
            at = version + 1 if version is not None else end
            lines.insert(at, f"status: {status}{_cr(lines[at - 1])}")
        return "\n".join(lines)
    meta = next((i for i in range(1, end) if not _is_indented(lines[i]) and _key(lines[i]) == "metadata"), None)
    if meta is None:
        lines[end:end] = ["metadata:", f'  status: "{status}"']
        return "\n".join(lines)
    found = version = None
    last = meta
    for index in range(meta + 1, end):
        if not lines[index].strip():
            continue
        if not _is_indented(lines[index]):
            break
        last = index
        if _key(lines[index]) == "status":
            found = index
        elif _key(lines[index]) == "version":
            version = index
    if found is not None:
        indent = lines[found][: len(lines[found]) - len(lines[found].lstrip())]
        q = _quote_of(lines[found].partition(":")[2])
        lines[found] = f"{indent}status: {q}{status}{q}{_cr(lines[found])}"
    else:
        at = (version if version is not None else last) + 1
        lines.insert(at, f'  status: "{status}"{_cr(lines[at - 1])}')
    return "\n".join(lines)


# --- content hash -----------------------------------------------------------------


def _is_conflict(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(".icloud") or "conflicted copy" in lower or "(conflict" in lower


def _scan(root: Path) -> tuple[list[tuple[str, Path]], list[str], list[str]]:
    """(hashed files sorted by relative POSIX path, conflict copies, symlinks) of one item directory."""
    files: list[tuple[str, Path]] = []
    conflicts: list[str] = []
    symlinks: list[str] = []
    if root.is_symlink():
        return files, conflicts, ["."]

    def walk(directory: Path, prefix: str) -> None:
        with os.scandir(directory) as entries:
            children = sorted(entries, key=lambda e: e.name)
        for child in children:
            rel = prefix + child.name
            if child.is_symlink():
                symlinks.append(rel)
            elif _is_conflict(child.name):
                conflicts.append(rel)
            elif child.name.startswith("."):
                continue
            elif child.is_dir(follow_symlinks=False):
                walk(Path(child.path), rel + "/")
            elif child.is_file(follow_symlinks=False) and rel != CHANGELOG:
                files.append((rel, Path(child.path)))

    walk(root, "")
    return sorted(files), conflicts, symlinks


def _hash_files(files: Iterable[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    for rel, path in files:
        data = path.read_bytes()
        digest.update(rel.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0" + data)
    return digest.hexdigest()


def _symlink_error(item_dir: Path, symlinks: list[str]) -> ChanchiError:
    return ChanchiError(
        "invalid_value",
        f"{item_dir.name}: symbolic links are not allowed inside an item: {symlinks}",
        field="path",
        hint="replace each link with a regular file or remove it",
    )


def content_hash(item_dir: Path) -> str:
    """SHA-256 over every hashed file's framed path and bytes (design, Versions and hashes)."""
    item_dir = Path(item_dir)
    files, _, symlinks = _scan(item_dir)
    if symlinks:
        raise _symlink_error(item_dir, symlinks)
    return _hash_files(files)


# --- changelog --------------------------------------------------------------------


def _section_bounds(lines: list[str], version: str) -> tuple[int, int] | None:
    for start, line in enumerate(lines):
        match = SECTION.match(line)
        if match and match.group(1) == version:
            end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
            return start, end
    return None


def _changelog_state(item_dir: Path, version: str) -> tuple[bool, str | None]:
    """(the current version has a section, the published hash recorded in it)."""
    path = item_dir / CHANGELOG
    try:
        lines = _read(path).split("\n")
    except (OSError, UnicodeDecodeError):
        return False, None
    bounds = _section_bounds(lines, version)
    if bounds is None:
        return False, None
    published = None
    for line in lines[bounds[0] + 1 : bounds[1]]:
        match = PUBLISHED_LINE.match(line)
        if match:
            published = match.group(4)
    return True, published


# --- retired.json -----------------------------------------------------------------


def _retired_entries(sync_root: Path) -> tuple[list[dict] | None, str | None]:
    """(entries, None), or (None, why the file is unusable). A missing file is an empty list."""
    path = Path(sync_root) / "ITEMS" / RETIRED
    if not os.path.lexists(path):
        return [], None
    try:
        data = json.loads(_read(path))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"cannot read {RETIRED}: {exc}"
    if not isinstance(data, list):
        return None, f"{RETIRED} must be a JSON array"
    for index, entry in enumerate(data):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"]:
            return None, f"{RETIRED} entry {index} must be an object with a string name"
    return data, None


# --- inspection ----------------------------------------------------------------------


def own_names() -> list[str]:
    """Names of chanchi's own agents and skills, from the checkout that holds its source (else empty)."""
    root = Path(__file__).resolve().parents[2]
    if not (root / "src" / "chanchi" / "items.py").is_file():
        return []
    names: list[str] = []
    for folder in taxonomy.ITEM_KINDS:
        base = root / folder
        if base.is_dir():
            names += sorted(p.name for p in base.iterdir() if p.is_dir())
    return names


def _inspect(kind: str, entry: Path, own: set[str]) -> tuple[Item, list[dict]]:
    name = entry.name
    problems: list[dict] = []

    def add(code: str, detail: str) -> None:
        problems.append({"item": name, "code": code, "detail": detail})

    bare = Item(name, kind, entry)
    if _is_conflict(name):
        add("conflict_copy", f"{name} is a cloud conflict copy or placeholder")
        return bare, problems
    match = GLOBAL_NAME.match(name)
    if match is None:
        add("bad_name", f"{name} is not <kind>-chanchi-global-<name> (kebab-case)")
        return bare, problems
    if match.group(1) != kind:
        add("wrong_folder", f"{name} is a {match.group(1)} but sits under ITEMS/{KIND_FOLDER[kind]}/")
        return bare, problems
    if name in own:
        add("own_item_collision", f"{name} is also one of chanchi's own items")

    files, conflicts, symlinks = _scan(entry)
    for rel in conflicts:
        add("conflict_copy", f"{rel} is a cloud conflict copy or placeholder")
    for rel in symlinks:
        add("symlink", f"{rel} is a symbolic link; replace it with a regular file")
    digest = None if symlinks else _hash_files(files)

    manifest = entry / MANIFEST[kind]
    version = status = None
    frontmatter: dict | None = None
    try:
        frontmatter = read_frontmatter(_read(manifest))
    except (OSError, UnicodeDecodeError) as exc:
        add("bad_frontmatter", f"cannot read {MANIFEST[kind]}: {exc}")
    except ChanchiError as exc:
        add("bad_frontmatter", f"{MANIFEST[kind]}: {exc.message}")
    structural = False
    if frontmatter is not None:
        if frontmatter.get("name") != name:
            add("name_mismatch", f"frontmatter name {frontmatter.get('name')!r} must equal {name!r}")
            structural = True
        source = frontmatter.get("metadata", {}) if kind == "skill" else frontmatter
        raw_version, raw_status = source.get("version"), source.get("status")
        if raw_version is not None and taxonomy.ITEM_VERSION.match(raw_version):
            version = raw_version
        else:
            add("bad_version", f"version must be <major>.<minor>.<patch>, got {raw_version!r}")
            structural = True
        if raw_status in taxonomy.ITEM_STATUSES:
            status = raw_status
        else:
            add("bad_status", f"status must be one of {list(taxonomy.ITEM_STATUSES)}, got {raw_status!r}")
            structural = True
        if kind == "skill" and not frontmatter.get("description"):
            add("bad_frontmatter", "SKILL.md needs a single-line description")
        if kind == "agent" and not structural:
            try:
                agents_sync._parse(manifest)
            except ChanchiError as exc:
                add("bad_frontmatter", exc.message)

    published_hash = None
    if version is not None:
        has_section, published_hash = _changelog_state(entry, version)
        if not has_section:
            add("missing_changelog", f"{CHANGELOG} has no `## {version} — <YYYY-MM-DD>` section")
    if status == "published" and digest is not None:
        if published_hash is None:
            add("published_without_record", f"status is published but {CHANGELOG} has no Published: line for {version}")
        elif digest != published_hash:
            add("edited_after_publish", "the item changed after it was published; open a new round or a new version")
    item = Item(name, kind, entry, version, status, digest, published_hash)
    return item, problems


def _entries(sync_root: Path, own: set[str]) -> tuple[list[Item], list[dict]]:
    items_root = Path(sync_root) / "ITEMS"
    found: list[Item] = []
    problems: list[dict] = []
    if not items_root.is_dir():
        return found, problems
    for entry in sorted(items_root.iterdir(), key=lambda p: p.name):
        name = entry.name
        if _is_conflict(name):
            problems.append({"item": name, "code": "conflict_copy",
                             "detail": f"{name} is a cloud conflict copy or placeholder"})
        elif name.startswith("."):
            continue
        elif name in taxonomy.ITEM_KINDS and not entry.is_dir():
            problems.append({"item": name, "code": "unexpected_entry", "detail": f"ITEMS/{name} must be a directory"})
        elif name == RETIRED and not entry.is_file():
            problems.append({"item": name, "code": "unexpected_entry", "detail": f"{RETIRED} must be a file"})
        elif name not in taxonomy.ITEM_KINDS and name != RETIRED:
            problems.append({"item": name, "code": "unexpected_entry",
                             "detail": f"ITEMS/ holds only agents/, skills/ and {RETIRED}"})
    for folder, kind in taxonomy.ITEM_KINDS.items():
        base = items_root / folder
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir(), key=lambda p: p.name):
            if entry.name.startswith(".") and not _is_conflict(entry.name):
                continue
            if not entry.is_dir() and not _is_conflict(entry.name):
                problems.append({"item": entry.name, "code": "unexpected_entry",
                                 "detail": f"ITEMS/{folder}/ holds only item directories"})
                continue
            item, item_problems = _inspect(kind, entry, own)
            found.append(item)
            problems += item_problems
    return found, problems


def load(sync_root: Path) -> list[Item]:
    """Every item directory under SYNC/ITEMS; a field that cannot be read is None."""
    return _entries(sync_root, set())[0]


def check(sync_root: Path, *, own_names: Iterable[str]) -> dict:
    """Validate SYNC/ITEMS. Never raises for item problems: returns {items, problems}."""
    found, problems = _entries(sync_root, set(own_names))
    retired, error = _retired_entries(sync_root)
    if error is not None:
        problems.append({"item": RETIRED, "code": "bad_retired_json", "detail": error})
    else:
        by_name = {item.name: item for item in found}
        for entry in retired:
            item = by_name.get(entry["name"])
            if item is not None and item.status != "retired":
                problems.append({
                    "item": item.name, "code": "retired_not_retired",
                    "detail": f"listed in {RETIRED} but its status is {item.status!r}; a retired name stays retired",
                })
    return {"items": found, "problems": problems}


def list_items(sync_root: Path) -> list[dict]:
    """name, kind, version, status, hash, published_hash and retired for every item; never fails on a problem."""
    retired, error = _retired_entries(sync_root)
    names = _names(retired) if error is None else None
    rows = []
    for item in load(sync_root):
        row = item.to_dict()
        row["retired"] = None if names is None else item.name in names
        rows.append(row)
    return rows


# --- one item -----------------------------------------------------------------------------


def _find(sync_root: Path, name: str, field: str = "name", own: Iterable[str] = ()) -> tuple[Item, list[dict]]:
    match = GLOBAL_NAME.match(name) if isinstance(name, str) else None
    if match is None:
        raise ChanchiError(
            "invalid_value", f"{name!r} is not a global item name", field=field,
            hint="global items are <agent|skill>-chanchi-global-<name>; run `chanchi items list`",
        )
    kind = match.group(1)
    entry = Path(sync_root) / "ITEMS" / KIND_FOLDER[kind] / name
    if not entry.is_dir():
        raise ChanchiError(
            "invalid_value", f"no global item {name!r} in SYNC/ITEMS/{KIND_FOLDER[kind]}/", field=field,
            hint="run `chanchi items list`",
        )
    return _inspect(kind, entry, set(own))


def subject_at(sync_root: Path | None, name: str, version: str) -> str:
    """`<version>@<content hash>`: what an `item` audit round records for the item as it is now."""
    if sync_root is None:
        raise ChanchiError(
            "missing_prerequisite", "SYNC is not initialized", field="sync", hint="chanchi sync init"
        )
    item, _ = _find(sync_root, name, field="ref")
    if item.version != version:
        raise ChanchiError(
            "invalid_value",
            f"{name} is at version {item.version}, not {version}",
            field="version",
            hint="pass the item's current version: `chanchi items list`",
        )
    return f"{version}@{item.hash or content_hash(item.path)}"


def _today(today: str | None) -> str:
    return today or datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _names(entries: list[dict] | None) -> set[str]:
    return {entry["name"] for entry in entries or []}


def _insert_published_line(text: str, version: str, line: str) -> str:
    lines = text.split("\n")
    bounds = _section_bounds(lines, version)
    if bounds is None:
        raise ChanchiError(
            "invalid_value", f"{CHANGELOG} has no section for {version}", field="changelog",
            hint=f"add `## {version} — <YYYY-MM-DD>`",
        )
    start, end = bounds
    section = lines[start:end]
    while len(section) > 1 and not section[-1].strip():
        section.pop()
    section += ["", line, ""]
    return "\n".join(lines[:start] + section + lines[end:])


def publish(
    conn: sqlite3.Connection,
    sync_root: Path,
    name: str,
    *,
    audit_id: int,
    own_names: Iterable[str],
    today: str | None = None,
) -> dict:
    """Set `status: published` when an accepted `item` audit covers the item's draft version and hash."""
    item, problems = _find(sync_root, name, own=own_names)
    retired, retired_error = _retired_entries(sync_root)
    if item.status == "retired" or name in _names(retired):
        raise ChanchiError(
            "invalid_transition", f"{name} is retired and is never published again", field="name",
            hint="write a new item with another name",
        )
    if item.status == "published":
        raise ChanchiError(
            "invalid_transition", f"{name} {item.version} is already published", field="name",
            hint="write the next version as `draft`, add its changelog section and audit it",
        )
    if retired_error is not None:
        problems = problems + [{"item": RETIRED, "code": "bad_retired_json", "detail": retired_error}]
    if problems:
        raise ChanchiError(
            "invalid_value",
            f"{name} fails `chanchi items check`: {sorted({p['code'] for p in problems})}",
            field="name",
            hint="run `chanchi items check` and fix every problem",
            details={"problems": problems},
        )
    audit = conn.execute("SELECT * FROM audits WHERE id = ?", (audit_id,)).fetchone()
    if audit is None:
        raise ChanchiError(
            "unknown_audit", f"audit {audit_id} does not exist", field="audit",
            hint="run `chanchi audit list --kind item` to see the audits",
        )
    if audit["subject_kind"] != "item" or audit["subject_ref"] != name:
        raise ChanchiError(
            "invalid_value",
            f"audit {audit_id} is a {audit['subject_kind']} audit of {audit['subject_ref']!r}, not an item audit of {name}",
            field="audit",
            hint=f"chanchi audit open --kind item --ref {name} --author <spec> --version {item.version}",
        )
    last = conn.execute(
        "SELECT * FROM audit_rounds WHERE audit_id = ? ORDER BY round DESC LIMIT 1", (audit_id,)
    ).fetchone()
    expected = f"{item.version}@{item.hash}"
    if last is None or last["outcome"] != "accepted" or last["subject_at"] != expected:
        seen = "no round" if last is None else f"round {last['round']} {last['outcome'] or 'open'} at {last['subject_at']}"
        raise ChanchiError(
            "invalid_transition",
            f"audit {audit_id} does not accept {name} as it is now ({seen}; the item is at {expected})",
            field="audit",
            hint="open a new round (`chanchi audit round`) or a new version and audit it",
        )

    manifest = item.path / MANIFEST[item.kind]
    changelog = item.path / CHANGELOG
    old_manifest, old_changelog = _read(manifest), _read(changelog)
    new_manifest = set_status(old_manifest, item.kind, "published")
    _write(manifest, new_manifest)
    try:
        published_hash = content_hash(item.path)
        line = f"Published: {_today(today)} · audit {audit_id} · audited {item.hash} · sha256 {published_hash}"
        _write(changelog, _insert_published_line(old_changelog, item.version, line))
    except Exception:
        _write(manifest, old_manifest)
        _write(changelog, old_changelog)
        raise
    return {
        "name": name,
        "version": item.version,
        "status": "published",
        "audit_id": audit_id,
        "audited_hash": item.hash,
        "hash": published_hash,
    }


def _append_retired(existing: str | None, entry: dict) -> str:
    body = json.dumps(entry, indent=2, ensure_ascii=False)
    block = "\n".join(f"  {line}" for line in body.splitlines())
    if existing is None:
        return f"[\n{block}\n]\n"
    stripped = existing.rstrip()
    head = stripped[:-1].rstrip()
    if head.endswith("["):
        return f"{head}\n{block}\n]\n"
    return f"{head},\n{block}\n]\n"


def retire(
    sync_root: Path,
    name: str,
    *,
    reason: str,
    replaced_by: str | None = None,
    today: str | None = None,
) -> dict:
    """Set `status: retired` and append the entry to `retired.json`; the directory stays for history."""
    reason = (reason or "").strip()
    if not reason:
        raise ChanchiError("invalid_value", "reason must not be empty", field="reason")
    item, problems = _find(sync_root, name)
    retired, retired_error = _retired_entries(sync_root)
    if retired_error is not None:
        problems = problems + [{"item": RETIRED, "code": "bad_retired_json", "detail": retired_error}]
    if item.status == "retired" or name in _names(retired):
        raise ChanchiError(
            "invalid_transition", f"{name} is already retired", field="name",
            hint="a retired item is never retired twice or published again",
        )
    blocking = [p for p in problems if p["code"] in STRUCTURAL or p["code"] == "bad_retired_json"]
    if blocking:
        raise ChanchiError(
            "invalid_value",
            f"{name} cannot be retired until `chanchi items check` passes for: "
            f"{sorted({p['code'] for p in blocking})}",
            field="name",
            hint="run `chanchi items check` and fix those problems",
            details={"problems": blocking},
        )
    if replaced_by is not None:
        if replaced_by == name:
            raise ChanchiError("invalid_value", "an item cannot replace itself", field="replaced_by")
        other, _ = _find(sync_root, replaced_by, field="replaced_by")
        if other.kind != item.kind:
            raise ChanchiError(
                "invalid_value", f"{replaced_by} is a {other.kind}, not a {item.kind}", field="replaced_by"
            )
        if other.status == "retired" or replaced_by in _names(retired):
            raise ChanchiError("invalid_value", f"{replaced_by} is retired", field="replaced_by")
    entry = {"name": name, "version": item.version, "replaced_by": replaced_by, "date": _today(today),
             "reason": reason}
    retired_path = Path(sync_root) / "ITEMS" / RETIRED
    old_retired = _read(retired_path) if retired_path.is_file() else None
    manifest = item.path / MANIFEST[item.kind]
    _write(retired_path, _append_retired(old_retired, entry))
    try:
        _write(manifest, set_status(_read(manifest), item.kind, "retired"))
    except Exception:
        if old_retired is None:
            retired_path.unlink()
        else:
            _write(retired_path, old_retired)
        raise
    return {"name": name, "version": item.version, "status": "retired", "replaced_by": replaced_by,
            "reason": reason, "date": entry["date"]}
