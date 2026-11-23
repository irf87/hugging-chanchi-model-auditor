"""Eval ledger reader and pure git tree hash (S2 minimal; S3 adds the CLI runner)."""

from __future__ import annotations

import csv
import hashlib
import os
import stat
import subprocess
from pathlib import Path

LEDGER_COLUMNS = (
    "id",
    "date",
    "item",
    "item_sha",
    "hypothesis",
    "change",
    "arm",
    "candidate",
    "runs",
    "median_pass",
    "before",
    "after",
    "delta",
    "verdict",
    "note",
)


def _blob_digest(path: Path) -> tuple[bytes, bytes]:
    """Return (git_mode_bytes, sha1_digest_bytes) for a file or symlink."""
    if path.is_symlink():
        data = os.readlink(path).encode("utf-8")
        mode = b"120000"
    else:
        data = path.read_bytes()
        mode = b"100755" if (path.stat().st_mode & stat.S_IXUSR) else b"100644"
    header = f"blob {len(data)}\0".encode("utf-8")
    return mode, hashlib.sha1(header + data).digest()


def _tracked_files(directory: Path) -> list[Path]:
    """Files under `directory` that git tracks or has staged (the index), as absolute paths."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=directory, env=env,
                          check=True, capture_output=True, text=True).stdout.strip()
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--", str(directory.resolve())],
                         cwd=root, env=env, check=True, capture_output=True).stdout
    files = [Path(root) / name for name in out.decode("utf-8").split("\0") if name]
    return [f for f in files if f.exists() or f.is_symlink()]


def _tree_digest(directory: Path, files: list[Path]) -> bytes | None:
    """Return the raw 20-byte git tree digest of `files` below `directory`, or None if empty."""
    entries: list[tuple[bytes, bytes, str, bytes]] = []
    children: dict[str, list[Path]] = {}
    for f in files:
        rel = f.relative_to(directory)
        children.setdefault(rel.parts[0], []).append(f)
    for name, group in children.items():
        child = directory / name
        if len(group) == 1 and group[0] == child:
            mode, digest = _blob_digest(child)
            entries.append((name.encode("utf-8"), mode, name, digest))
        else:
            sub_digest = _tree_digest(child, group)
            if sub_digest is not None:
                entries.append(((name + "/").encode("utf-8"), b"40000", name, sub_digest))
    if not entries:
        return None
    entries.sort(key=lambda item: item[0])
    body = b"".join(
        mode + b" " + name.encode("utf-8") + b"\0" + digest for _, mode, name, digest in entries
    )
    header = f"tree {len(body)}\0".encode("utf-8")
    return hashlib.sha1(header + body).digest()


def tree_hash(path: Path) -> str:
    """Git's tree SHA-1 of a directory as the index lists it (tracked plus staged files, D10), hashed
    from their working-tree content; untracked and ignored files never count."""
    directory = Path(path).resolve()
    digest = _tree_digest(directory, _tracked_files(directory))
    if digest is None:
        return hashlib.sha1(b"tree 0\0").hexdigest()
    return digest.hex()


def read_ledger(path: Path) -> list[dict[str, str]]:
    """Read rows from evals/ledger.tsv as a list of dicts keyed by column name."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)
