"""Offline derivation of Hugging Face benchmark ordering signals from the committed snapshot."""

from __future__ import annotations

import importlib.resources
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HF_MIN_REPORTERS = 5

HF_BENCHMARKS: dict[str, dict] = {
    "datacurve/deep-swe": {
        "signal": "swe",
        "task_ids": ("deep_swe",),
        "unit": "percent",
        "range": (0, 100),
    },
    "ScaleAI/SWE-bench_Pro": {
        "signal": "swe",
        "task_ids": ("SWE_Bench_Pro",),
        "unit": "percent",
        "range": (0, 100),
    },
    "SWE-bench/SWE-bench_Verified": {
        "signal": "swe",
        "task_ids": (),
        "unit": "percent",
        "range": (0, 100),
    },
    "SWE-bench/SWE-bench_Multilingual": {
        "signal": "swe",
        "task_ids": (),
        "unit": "percent",
        "range": (0, 100),
    },
    "harborframework/terminal-bench-2.1": {
        "signal": "terminal",
        "task_ids": ("terminalbench_2_1",),
        "unit": "percent",
        "range": (0, 100),
    },
    "hkust-nlp/Toolathlon": {
        "signal": "tool-use",
        "task_ids": ("toolathlon_verified",),
        "unit": "percent",
        "range": (0, 100),
    },
    "claw-eval/Claw-Eval": {
        "signal": "tool-use",
        "task_ids": ("general",),
        "unit": "percent",
        "range": (0, 100),
    },
}

TASK_SIGNALS: dict[str, str] = {
    "bugfix": "swe",
    "refactor": "swe",
    "business-logic": "swe",
    "api-endpoint": "swe",
    "infra-config-ci": "terminal",
    "integration": "tool-use",
}

SNAPSHOT_PATH = importlib.resources.files("chanchi") / "data" / "hf_snapshot.json"

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PEER_MATCH_QUALITIES = ("exact", "family")


def load_snapshot(path=None) -> tuple[dict | None, str]:
    """Load and validate the Hugging Face snapshot without raising on missing or corrupt files."""
    target = SNAPSHOT_PATH if path is None else path
    try:
        if isinstance(target, str):
            raw = Path(target).read_text(encoding="utf-8")
        else:
            raw = target.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "missing"
    if not isinstance(data, dict):
        return None, "schema_mismatch"
    version = data.get("schema_version")
    if type(version) is not int or version != 1:
        return None, "schema_mismatch"
    return data, "snapshot"


def _parse_date(raw: object) -> str | None:
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    prefix = raw[:10]
    if not _DATE_PREFIX_RE.match(prefix):
        return None
    try:
        datetime.strptime(prefix, "%Y-%m-%d")
    except ValueError:
        return None
    return prefix


def _valid_value(value: object, spec: dict) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    low, high = spec["range"]
    if value < low or value > high:
        return False
    if spec["unit"] == "percent" and 0 < value <= 1:
        return False
    return True


def _repo_canonical_rows(eval_rows: object) -> dict[tuple[str, str], dict]:
    """Return latest-date mean and pull_request flag per valid (dataset_id, task_id)."""
    if not isinstance(eval_rows, list):
        return {}
    grouped: dict[tuple[str, str], list[tuple[str, float, bool]]] = defaultdict(list)
    for row in eval_rows:
        if not isinstance(row, dict):
            continue
        dataset_id = row.get("dataset_id")
        task_id = row.get("task_id")
        spec = HF_BENCHMARKS.get(dataset_id)
        if spec is None or task_id not in spec["task_ids"]:
            continue
        value = row.get("value")
        if not _valid_value(value, spec):
            continue
        date = _parse_date(row.get("date"))
        if date is None:
            continue
        grouped[(dataset_id, task_id)].append((date, float(value), row.get("pull_request") is not None))

    canonical: dict[tuple[str, str], dict] = {}
    for key, entries in grouped.items():
        latest_date = max(d for d, _, _ in entries)
        latest = [item for item in entries if item[0] == latest_date]
        canonical[key] = {
            "value": sum(v for _, v, _ in latest) / len(latest),
            "date": latest_date,
            "pull_request": any(pr for _, _, pr in latest),
        }
    return canonical


def canonical_values(snapshot: dict | None) -> dict[tuple[str, str, str], float]:
    """Compute canonical latest-date mean per peer (hf_repo, dataset_id, task_id)."""
    if not isinstance(snapshot, dict):
        return {}
    models = snapshot.get("models")
    if not isinstance(models, dict):
        return {}
    values: dict[tuple[str, str, str], float] = {}
    seen_repos: set[str] = set()
    for entry in models.values():
        if not isinstance(entry, dict):
            continue
        if entry.get("match_quality") not in _PEER_MATCH_QUALITIES:
            continue
        hf_repo = entry.get("hf_repo")
        if not isinstance(hf_repo, str) or hf_repo in seen_repos:
            continue
        seen_repos.add(hf_repo)
        for (dataset_id, task_id), row in _repo_canonical_rows(entry.get("eval_rows")).items():
            values[(hf_repo, dataset_id, task_id)] = row["value"]
    return values


def percentiles(values: dict[tuple[str, str, str], float]) -> dict[tuple[str, str, str], dict]:
    """Compute within-benchmark percentiles and peer counts for benchmarks with >= HF_MIN_REPORTERS."""
    by_benchmark: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for (hf_repo, dataset_id, task_id), value in values.items():
        by_benchmark[(dataset_id, task_id)].append((hf_repo, value))

    result: dict[tuple[str, str, str], dict] = {}
    for (dataset_id, task_id), peers in by_benchmark.items():
        n = len(peers)
        if n < HF_MIN_REPORTERS:
            continue
        for hf_repo, value in peers:
            below = sum(1 for _, other in peers if other < value)
            equal = sum(1 for _, other in peers if other == value)
            pct = (below + 0.5 * (equal - 1)) / (n - 1)
            result[(hf_repo, dataset_id, task_id)] = {"percentile": pct, "peers": n}
    return result


def _signal_for(
    snapshot: dict | None,
    agent: str,
    model: str,
    task_type: str,
    *,
    pct_table: dict[tuple[str, str, str], dict] | None = None,
) -> tuple[dict | None, float | None]:
    if not isinstance(snapshot, dict):
        return None, None
    signal_name = TASK_SIGNALS.get(task_type)
    if signal_name is None:
        return None, None
    models = snapshot.get("models")
    if not isinstance(models, dict):
        return None, None
    entry = models.get(f"{agent}:{model}")
    if not isinstance(entry, dict):
        return None, None

    hf_repo = entry.get("hf_repo")
    match_quality = entry.get("match_quality")
    table = pct_table if pct_table is not None else percentiles(canonical_values(snapshot))

    counted = sorted(
        {(ds, tid) for (_, ds, tid) in table if HF_BENCHMARKS.get(ds, {}).get("signal") == signal_name}
    )
    repo_rows = _repo_canonical_rows(entry.get("eval_rows"))
    benchmarks: list[dict] = []
    pct_values: list[float] = []
    for dataset_id, task_id in counted:
        row = repo_rows.get((dataset_id, task_id))
        if row is None:
            continue
        if match_quality == "proxy":
            peers_count = None
        else:
            pct_entry = table.get((hf_repo, dataset_id, task_id))
            if pct_entry is None:
                continue
            peers_count = pct_entry["peers"]
            pct_values.append(pct_entry["percentile"])
        benchmarks.append(
            {
                "dataset_id": dataset_id,
                "task_id": task_id,
                "value": round(row["value"], 2),
                "date": row["date"],
                "pull_request": row["pull_request"],
                "peers": peers_count,
            }
        )

    raw_value: float | None = None
    if match_quality != "proxy" and pct_values:
        raw_value = sum(pct_values) / len(pct_values)

    external = {
        "signal": signal_name,
        "value": round(raw_value, 4) if raw_value is not None else None,
        "hf_repo": hf_repo,
        "match_quality": match_quality,
        "fetched_at": entry.get("fetched_at"),
        "verified": False,
        "benchmarks": benchmarks,
    }
    return external, raw_value


def signal_for(snapshot: dict | None, agent: str, model: str, task_type: str) -> dict | None:
    """Return the allowlisted external_signals object for a mapped model and task_type, or None."""
    external, _ = _signal_for(snapshot, agent, model, task_type)
    return external
