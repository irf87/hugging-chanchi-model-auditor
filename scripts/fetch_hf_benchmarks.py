"""Maintainer script to fetch public Hugging Face benchmark metadata into the committed snapshot."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import urllib.request

HUB_API_TEMPLATE = "https://huggingface.co/api/models/{repo}?expand[]=evalResults&expand[]=pipeline_tag"
REQUEST_TIMEOUT_S = 20
USER_AGENT = "chanchi-hf-fetch"


def _is_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _map_eval_row(element: object) -> dict | None:
    if not isinstance(element, dict):
        return None
    data = element.get("data")
    if not isinstance(data, dict):
        return None
    value = data.get("value")
    if not _is_number(value):
        return None
    dataset = data.get("dataset") if isinstance(data.get("dataset"), dict) else {}
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    pull_request = element.get("pullRequest")
    return {
        "dataset_id": dataset.get("id"),
        "task_id": dataset.get("task_id"),
        "value": value,
        "date": data.get("date"),
        "source_name": source.get("name"),
        "source_url": source.get("url"),
        "verified": bool(element.get("verified", False)),
        "pull_request": pull_request if pull_request is not None else None,
    }


def fetch_repo(repo: str, token: str | None, opener) -> dict:
    """Fetch and map one Hub model's evalResults and pipeline_tag; raise on any failure."""
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(HUB_API_TEMPLATE.format(repo=repo), headers=headers)
    resp = opener(req, timeout=REQUEST_TIMEOUT_S)
    ctx = resp if hasattr(resp, "__enter__") else nullcontext(resp)
    with ctx as handle:
        status = getattr(handle, "status", None)
        if status is None and hasattr(handle, "getcode"):
            status = handle.getcode()
        if status is not None and status != 200:
            raise RuntimeError(f"HTTP {status} for {repo}")
        raw = handle.read()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected JSON payload for {repo}")
    raw_results = payload.get("evalResults")
    eval_rows: list[dict] = []
    if isinstance(raw_results, list):
        for elem in raw_results:
            mapped = _map_eval_row(elem)
            if mapped is not None:
                eval_rows.append(mapped)
    return {
        "pipeline_tag": payload.get("pipeline_tag"),
        "eval_rows": eval_rows,
    }


def merge(
    previous: dict | None,
    fetched: dict[str, dict],
    model_map: dict[str, dict],
    now: str,
) -> dict:
    """Build the new snapshot dict from previous snapshot, fetched results, map and timestamp."""
    prev_models = (previous or {}).get("models", {})
    if not isinstance(prev_models, dict):
        prev_models = {}
    models: dict[str, dict] = {}
    for key, spec in model_map.items():
        result = fetched[key]
        prev = prev_models.get(key) if isinstance(prev_models.get(key), dict) else None
        if "error" in result:
            models[key] = {
                "hf_repo": spec["hf_repo"],
                "match_quality": spec["match_quality"],
                "fetched_at": prev.get("fetched_at") if prev is not None else None,
                "last_error": result["error"],
                "pipeline_tag": prev.get("pipeline_tag") if prev is not None else None,
                "eval_rows": list(prev.get("eval_rows", [])) if prev is not None else [],
            }
        else:
            models[key] = {
                "hf_repo": spec["hf_repo"],
                "match_quality": spec["match_quality"],
                "fetched_at": now,
                "last_error": None,
                "pipeline_tag": result.get("pipeline_tag"),
                "eval_rows": list(result.get("eval_rows", [])),
            }
    return {
        "schema_version": 1,
        "generated_at": now,
        "models": models,
    }


def _row_counts(rows: list[dict]) -> Counter[str]:
    return Counter(json.dumps(row, sort_keys=True) for row in rows)


def _rows_changed(prev_rows: list[dict], new_rows: list[dict]) -> int:
    prev_c = _row_counts(prev_rows)
    new_c = _row_counts(new_rows)
    added = sum((new_c - prev_c).values())
    removed = sum((prev_c - new_c).values())
    return added + removed


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Hugging Face benchmark metadata into snapshot.")
    parser.add_argument("--write", action="store_true", help="Write src/chanchi/data/hf_snapshot.json.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, root: Path | None = None, opener=None) -> int:
    repo_root = (root if root is not None else Path(__file__).resolve().parents[1]).resolve()
    if Path.cwd().resolve() != repo_root:
        sys.stderr.write(f"error: must run from repository root {repo_root}\n")
        return 2

    args = _parse_args(argv)
    map_path = repo_root / "scripts" / "hf_model_map.json"
    snapshot_path = repo_root / "src" / "chanchi" / "data" / "hf_snapshot.json"

    model_map_doc = json.loads(map_path.read_text(encoding="utf-8"))
    model_map: dict[str, dict] = model_map_doc["models"]

    previous: dict | None = None
    if snapshot_path.exists():
        previous = json.loads(snapshot_path.read_text(encoding="utf-8"))

    token = os.environ.get("HF_TOKEN") or None
    actual_opener = opener if opener is not None else urllib.request.urlopen

    fetched: dict[str, dict] = {}
    for key, spec in model_map.items():
        try:
            fetched[key] = fetch_repo(spec["hf_repo"], token, actual_opener)
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            fetched[key] = {"error": message}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_snapshot = merge(previous, fetched, model_map, now)

    prev_models = (previous or {}).get("models", {})
    summary_models: dict[str, dict] = {}
    for key, spec in model_map.items():
        prev_entry = prev_models.get(key) if isinstance(prev_models, dict) else None
        prev_rows = prev_entry.get("eval_rows", []) if isinstance(prev_entry, dict) else []
        new_rows = new_snapshot["models"][key]["eval_rows"]
        summary_models[key] = {
            "hf_repo": spec["hf_repo"],
            "rows": len(new_rows),
            "rows_changed": _rows_changed(prev_rows, new_rows),
            "error": fetched[key].get("error"),
        }

    vision_candidates = sorted(
        key for key, entry in new_snapshot["models"].items() if entry.get("pipeline_tag") == "image-text-to-text"
    )
    failed = sum(1 for res in fetched.values() if "error" in res)

    summary = {
        "models": summary_models,
        "vision_candidates": vision_candidates,
        "failed": failed,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if args.write:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(new_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
