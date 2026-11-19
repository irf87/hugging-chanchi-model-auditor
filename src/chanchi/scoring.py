"""Read side: scores, stats and recommendations. Never writes; scores are never stored."""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict

from chanchi import catalog, record
from chanchi import taxonomy as tx
from chanchi.errors import ChanchiError
from chanchi.modelspec import format_spec
from chanchi.timeutil import parse as parse_ts

EXECUTOR_GROUPINGS = {
    "model": ("agent", "model", "effort"),
    "task-type": ("agent", "model", "effort", "task_type", "complexity"),
    "project": ("project", "agent", "model", "effort"),
    "dimension": ("agent", "model", "effort", "dimension"),
}
PLANNER_GROUPINGS = {
    "model": ("agent", "model", "effort"),
    "project": ("project", "agent", "model", "effort"),
}
STATS_ROLES = ("executor", "planner", "human")


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _penalty(incidents: list[dict], weights: dict) -> float:
    total = 0.0
    for incident in incidents:
        weight = weights.get(incident["code"])
        if weight is None:
            continue
        late = tx.LATE_DETECTION_MULT if incident["detected_by"] in tx.LATE_DETECTION else 1.0
        total += weight * tx.SEVERITY_MULT[incident["severity"]] * late
    return total


def session_score(verdict: str | None, incidents: list[dict]) -> float | None:
    if verdict is None:
        return None
    executor = [i for i in incidents if i["role"] == "executor"]
    penalty = _penalty([i for i in executor if i["code"] != "correct_stop"], tx.EXECUTOR_WEIGHTS)
    credit = tx.CORRECT_STOP_CREDIT * sum(1 for i in executor if i["code"] == "correct_stop")
    return _clamp(tx.VERDICT_BASE[verdict] - penalty + credit)


def planner_change_score(tasks: int, incidents: list[dict]) -> float:
    planner = [i for i in incidents if i["role"] == "planner"]
    density = _penalty(planner, tx.PLANNER_WEIGHTS) / max(tasks, tx.PLANNER_MIN_TASKS) * 10
    return _clamp(100 - tx.PLANNER_DENSITY_FACTOR * density)


def dimension_score(dimension: str, incidents: list[dict]) -> float:
    """Score of one dimension for one session: 100 minus the penalty of that dimension's faults."""
    codes = tx.DIMENSIONS[dimension]
    relevant = [
        i for i in incidents if i["role"] == "executor" and i["code"] in codes
    ]
    return _clamp(100 - _penalty(relevant, tx.EXECUTOR_WEIGHTS))


def smoothed(mean: float, n: int, prior: float) -> float:
    return (n * mean + tx.SMOOTHING_K * prior) / (n + tx.SMOOTHING_K)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


# --- executor --------------------------------------------------------------

_SESSIONS_SQL = """
SELECT s.id, s.change_id, s.session_ref, s.attempt, s.retry_reason, s.executor_effort AS effort,
       s.task_type, s.complexity, s.tasks_total, s.started_at, s.ended_at, s.verdict,
       m.agent, m.model, m.cost_tier, p.slug AS project, p.id AS project_id
FROM sessions s
JOIN changes c ON c.id = s.change_id
JOIN models m ON m.id = s.executor_model_id
JOIN projects p ON p.id = c.project_id
ORDER BY s.id
"""


def _incidents_by(conn: sqlite3.Connection, column: str) -> dict:
    grouped: dict = defaultdict(list)
    for row in conn.execute(
        f"SELECT {column}, code, role, severity, detected_by FROM incidents "
        f"WHERE voided_at IS NULL AND {column} IS NOT NULL ORDER BY id"
    ):
        grouped[row[column]].append(
            {"code": row["code"], "role": row["role"], "severity": row["severity"],
             "detected_by": row["detected_by"]}
        )
    return grouped


def executor_records(
    conn: sqlite3.Connection, *, project_id: int | None = None, since: str | None = None
) -> list[dict]:
    """One record per audited session that is not superseded by a non-executor retry."""
    incidents = _incidents_by(conn, "session_id")
    rows = [dict(r) for r in conn.execute(_SESSIONS_SQL)]
    next_reason = {(r["change_id"], r["session_ref"], r["attempt"] - 1): r["retry_reason"] for r in rows}
    records = []
    for r in rows:
        reason_after = next_reason.get((r["change_id"], r["session_ref"], r["attempt"]))
        if reason_after in tx.NON_EXECUTOR_RETRY_REASONS or r["verdict"] is None:
            continue
        if project_id is not None and r["project_id"] != project_id:
            continue
        if since is not None and r["started_at"] < since:
            continue
        session_incidents = incidents.get(r["id"], [])
        executor = [i for i in session_incidents if i["role"] == "executor"]
        r["score"] = session_score(r["verdict"], session_incidents)
        r["clean"] = r["verdict"] == "accepted" and not any(
            i["code"] != "correct_stop" and i["severity"] in tx.CLEAN_BLOCKING_SEVERITIES for i in executor
        )
        r["honesty_flags"] = sum(1 for i in executor if i["code"] in tx.HONESTY_CODES)
        r["failed_attempt"] = reason_after == "executor_failure"
        r["duration_s"] = (
            (parse_ts(r["ended_at"]) - parse_ts(r["started_at"])).total_seconds() if r["ended_at"] else None
        )
        r["codes"] = [i["code"] for i in executor]
        r["executor_incidents"] = executor
        records.append(r)
    return records


def prior_for(records: list[dict], task_type: str | None = None, complexity: str | None = None) -> float:
    subset = [
        r["score"]
        for r in records
        if (task_type is None or r["task_type"] == task_type)
        and (complexity is None or r["complexity"] == complexity)
    ]
    for candidate in (_mean(subset), _mean([r["score"] for r in records])):
        if candidate is not None:
            return candidate
    return tx.DEFAULT_PRIOR


def _top_codes(codes) -> list[str]:
    return [code for code, _ in Counter(codes).most_common(3)]


def summarize(records: list[dict], prior: float) -> dict:
    n = len(records)
    if n == 0:
        return {
            "n": 0, "mean_score": None, "smoothed_score": round(prior, 2), "prior": round(prior, 2),
            "confidence": tx.confidence(0), "clean_rate": None, "first_attempt_acceptance": None,
            "honesty_flags_per_session": None, "red_flag": False, "retry_rate": None,
            "mean_duration_s": None, "top_codes": [],
        }
    mean = sum(r["score"] for r in records) / n
    first = [r for r in records if r["attempt"] == 1]
    accepted_first = sum(
        1 for r in first if r["verdict"] in ("accepted", "accepted_with_fixes") and not r["failed_attempt"]
    )
    durations = [r["duration_s"] for r in records if r["duration_s"] is not None]
    honesty = sum(r["honesty_flags"] for r in records) / n
    return {
        "n": n,
        "mean_score": round(mean, 2),
        "smoothed_score": round(smoothed(mean, n, prior), 2),
        "prior": round(prior, 2),
        "confidence": tx.confidence(n),
        "clean_rate": round(sum(1 for r in records if r["clean"]) / n, 3),
        "first_attempt_acceptance": round(accepted_first / len(first), 3) if first else None,
        "honesty_flags_per_session": round(honesty, 3),
        "red_flag": honesty > tx.HONESTY_RED_FLAG,
        "retry_rate": round(sum(1 for r in records if r["failed_attempt"]) / n, 3),
        "mean_duration_s": round(sum(durations) / len(durations), 1) if durations else None,
        "top_codes": _top_codes(code for r in records for code in r["codes"]),
    }


def _executor_stats(conn, by, project_id, since) -> list[dict]:
    tx.validate_choice("by", by, EXECUTOR_GROUPINGS)
    records = executor_records(conn, project_id=project_id, since=since)
    if by == "dimension":
        return _dimension_stats(records)
    keys = EXECUTOR_GROUPINGS[by]
    groups: dict = defaultdict(list)
    for r in records:
        groups[tuple(r[k] for k in keys)].append(r)
    rows = []
    for key, members in groups.items():
        entry = dict(zip(keys, key))
        entry["spec"] = format_spec(entry["agent"], entry["model"], entry["effort"])
        entry["cost_tier"] = members[0]["cost_tier"]
        entry.update(summarize(members, prior_for(records, entry.get("task_type"), entry.get("complexity"))))
        rows.append(entry)
    rows.sort(key=lambda e: (-e["smoothed_score"], e["spec"], e.get("project") or "", e.get("task_type") or ""))
    return rows


# --- dimensions ------------------------------------------------------------

DIMENSION_NOTE = (
    "Dimension scores count only faults the auditor recorded: 100 means no recorded fault, "
    "not proven quality. Read them with n and confidence."
)


def _dimension_stats(records: list[dict]) -> list[dict]:
    """One row per model and dimension, scored from the executor incidents already recorded."""
    scores = [
        {dimension: dimension_score(dimension, r["executor_incidents"]) for dimension in tx.DIMENSIONS}
        for r in records
    ]
    priors = {
        dimension: _mean([s[dimension] for s in scores]) for dimension in tx.DIMENSIONS
    }
    groups: dict = defaultdict(list)
    for r, s in zip(records, scores):
        for dimension in tx.DIMENSIONS:
            groups[(r["agent"], r["model"], r["effort"], dimension)].append((r, s))
    rows = []
    for key, members in groups.items():
        agent, model, effort, dimension = key
        n = len(members)
        codes = tx.DIMENSIONS[dimension]
        mean = sum(s[dimension] for _, s in members) / n
        prior = priors[dimension]
        prior = tx.DEFAULT_PRIOR if prior is None else prior
        incidents = [
            i for r, _ in members for i in r["executor_incidents"] if i["code"] in codes
        ]
        rows.append(
            {
                "agent": agent,
                "model": model,
                "effort": effort,
                "dimension": dimension,
                "spec": format_spec(agent, model, effort),
                "cost_tier": members[0][0]["cost_tier"],
                "n": n,
                "incident_count": len(incidents),
                "sessions_with_incidents": sum(
                    1 for r, _ in members if any(i["code"] in codes for i in r["executor_incidents"])
                ),
                "incidents_per_session": round(len(incidents) / n, 3),
                "mean_score": round(mean, 2),
                "smoothed_score": round(smoothed(mean, n, prior), 2),
                "prior": round(prior, 2),
                "confidence": tx.confidence(n),
                "top_codes": _top_codes(i["code"] for i in incidents),
            }
        )
    order = {dimension: index for index, dimension in enumerate(tx.DIMENSIONS)}
    rows.sort(key=lambda e: (order[e["dimension"]], -e["smoothed_score"], e["spec"]))
    return rows


# --- planner ---------------------------------------------------------------


def planner_records(
    conn: sqlite3.Connection, *, project_id: int | None = None, since: str | None = None
) -> list[dict]:
    """One record per change with at least one audited session, excluding human planners."""
    tasks = {
        r["change_id"]: r["tasks"]
        for r in conn.execute(
            """
            SELECT s.change_id, SUM(s.tasks_total) AS tasks
            FROM sessions s
            JOIN (SELECT change_id, session_ref, MAX(attempt) AS attempt
                  FROM sessions GROUP BY change_id, session_ref) latest
              ON latest.change_id = s.change_id AND latest.session_ref = s.session_ref
             AND latest.attempt = s.attempt
            GROUP BY s.change_id
            """
        )
    }
    audited = {r[0] for r in conn.execute("SELECT DISTINCT change_id FROM sessions WHERE verdict IS NOT NULL")}
    incidents = _incidents_by(conn, "change_id")
    records = []
    for r in conn.execute(
        """
        SELECT c.id AS change_id, c.ref, c.opened_at, c.planner_effort AS effort,
               m.agent, m.model, m.cost_tier, p.slug AS project, p.id AS project_id
        FROM changes c
        JOIN models m ON m.id = c.planner_model_id
        JOIN projects p ON p.id = c.project_id
        ORDER BY c.id
        """
    ):
        r = dict(r)
        if r["agent"] in tx.PLANNER_ONLY_AGENTS or r["change_id"] not in audited:
            continue
        if project_id is not None and r["project_id"] != project_id:
            continue
        if since is not None and r["opened_at"] < since:
            continue
        planner_incidents = [i for i in incidents.get(r["change_id"], []) if i["role"] == "planner"]
        r["tasks"] = tasks.get(r["change_id"], 0)
        r["score"] = planner_change_score(r["tasks"], planner_incidents)
        r["incident_count"] = len(planner_incidents)
        r["codes"] = [i["code"] for i in planner_incidents]
        records.append(r)
    return records


def _planner_stats(conn, by, project_id, since) -> list[dict]:
    tx.validate_choice("by", by, PLANNER_GROUPINGS)
    records = planner_records(conn, project_id=project_id, since=since)
    prior = _mean([r["score"] for r in records])
    prior = tx.DEFAULT_PRIOR if prior is None else prior
    keys = PLANNER_GROUPINGS[by]
    groups: dict = defaultdict(list)
    for r in records:
        groups[tuple(r[k] for k in keys)].append(r)
    rows = []
    for key, members in groups.items():
        n = len(members)
        mean = sum(m["score"] for m in members) / n
        entry = dict(zip(keys, key))
        entry["spec"] = format_spec(entry["agent"], entry["model"], entry["effort"])
        entry.update(
            {
                "n": n,
                "mean_score": round(mean, 2),
                "smoothed_score": round(smoothed(mean, n, prior), 2),
                "prior": round(prior, 2),
                "confidence": tx.confidence(n),
                "plan_incidents_per_change": round(sum(m["incident_count"] for m in members) / n, 3),
                "top_codes": _top_codes(code for m in members for code in m["codes"]),
            }
        )
        rows.append(entry)
    rows.sort(key=lambda e: (-e["smoothed_score"], e["spec"], e.get("project") or ""))
    return rows


# --- human -----------------------------------------------------------------


def _human_stats(conn, project_id, since) -> list[dict]:
    query = (
        "SELECT i.code, i.role, i.detected_by, p.slug AS project FROM incidents i "
        "JOIN changes c ON c.id = i.change_id JOIN projects p ON p.id = c.project_id "
        "WHERE i.voided_at IS NULL"
    )
    params: list = []
    if project_id is not None:
        query += " AND p.id = ?"
        params.append(project_id)
    if since is not None:
        query += " AND i.created_at >= ?"
        params.append(since)
    per_project: dict = defaultdict(list)
    for row in conn.execute(query + " ORDER BY i.id", params):
        per_project[row["project"]].append(dict(row))
    rows = []
    for project in sorted(per_project):
        incidents = per_project[project]
        stops = [i for i in incidents if i["detected_by"] == "executor_stop" and i["code"] != "correct_stop"]
        human_stops = sum(1 for i in stops if i["role"] == "human")
        rows.append(
            {
                "project": project,
                "human_incidents": dict(Counter(i["code"] for i in incidents if i["role"] == "human")),
                "stops_total": len(stops),
                "stops_by_human": human_stops,
                "human_stop_share": round(human_stops / len(stops), 3) if stops else None,
            }
        )
    return rows


def stats(
    conn: sqlite3.Connection,
    *,
    role: str = "executor",
    by: str = "model",
    project_id: int | None = None,
    since: str | None = None,
) -> dict:
    tx.validate_choice("role", role, STATS_ROLES)
    if role == "executor":
        rows = _executor_stats(conn, by, project_id, since)
    elif role == "planner":
        rows = _planner_stats(conn, by, project_id, since)
    else:
        rows = _human_stats(conn, project_id, since)
    result = {"role": role, "by": by if role != "human" else "project", "rows": rows}
    if role == "executor" and by == "dimension":
        result["note"] = DIMENSION_NOTE
    return result


# --- recommend -------------------------------------------------------------

LEVELS = (
    ("task_type+complexity", True, True),
    ("task_type", True, False),
    ("complexity", False, True),
    ("global", False, False),
)


def _level_subset(records, task_type, complexity, use_type, use_complexity):
    return [
        r
        for r in records
        if (not use_type or r["task_type"] == task_type)
        and (not use_complexity or r["complexity"] == complexity)
    ]


def _explore_sort_key(entry: dict) -> tuple:
    """Sort explore candidates: non-deprioritized first, lowest cost, most task-type data, spec."""
    return (
        entry["deprioritized"] is not None,
        entry["cost_tier"],
        -entry["n_task_type"],
        entry["spec"],
    )


def _build_explore(
    candidates_in_order: list[dict],
    spec_meta: dict[str, dict],
    *,
    records: list[dict],
    task_type: str,
    complexity: str,
    recommended_model: tuple[str, str] | None,
) -> tuple[list[dict], str | None]:
    """Select up to EXPLORE_MAX explorable models (one spec each) for low/medium complexity."""
    if complexity not in tx.EXPLORE_COMPLEXITIES:
        return [], "complexity_not_explorable"

    by_model: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for entry in candidates_in_order:
        by_model[(entry["agent"], entry["model"])].append(entry)

    task_prior = prior_for(records, task_type, None)
    kept_entries: list[dict] = []
    for model_key, specs in by_model.items():
        if model_key == recommended_model:
            continue
        if any(spec_meta[c["spec"]]["n_task_type"] >= tx.CONFIDENCE_LOW_MIN for c in specs):
            continue
        if any(c["red_flag"] and c["n"] >= tx.CONFIDENCE_LOW_MIN for c in specs):
            continue

        # Keep the effort with highest n_task_type, breaking ties by --available order.
        kept = max(
            specs,
            key=lambda c: (spec_meta[c["spec"]]["n_task_type"], -spec_meta[c["spec"]]["order"]),
        )
        meta = spec_meta[kept["spec"]]

        if any(c["red_flag"] and c["n"] < tx.CONFIDENCE_LOW_MIN for c in specs):
            deprioritized: str | None = "red_flag_low_data"
        elif (
            1 <= meta["n_task_type"] < tx.CONFIDENCE_LOW_MIN
            and meta["task_type_mean"] < task_prior - tx.RECOMMEND_WINDOW
        ):
            deprioritized = "weak_start"
        else:
            deprioritized = None

        kept_entries.append(
            {
                "spec": kept["spec"],
                "cost_tier": kept["cost_tier"],
                "n_task_type": meta["n_task_type"],
                "deprioritized": deprioritized,
            }
        )

    kept_entries.sort(key=_explore_sort_key)
    explore = kept_entries[: tx.EXPLORE_MAX]
    reason = None if explore else "no_explorable_candidates"
    return explore, reason


def recommend(
    conn: sqlite3.Connection,
    *,
    task_type: str,
    complexity: str,
    available: list[str],
    require: list[str] | None = None,
) -> dict:
    catalog.require_task_type(conn, task_type)
    tx.validate_choice("complexity", complexity, tx.COMPLEXITIES)
    if not available:
        raise ChanchiError(
            "invalid_value",
            "--available must list at least one agent:model[:effort]",
            field="available",
            hint="take the list from the human's prompt; never assume availability",
        )
    required: list[str] = []
    for item in require or ():
        cap = item.strip()
        if not cap or cap in required:
            continue
        tx.validate_choice("require", cap, tx.CAPABILITIES)
        required.append(cap)
    records = executor_records(conn)
    candidates = []
    excluded = []
    spec_meta: dict[str, dict] = {}
    seen = set()
    caps_by_model: dict[int, dict[str, str]] = {}
    for spec in available:
        row, effort = catalog.resolve_model(conn, spec, role="executor")
        key = (row["agent"], row["model"], effort)
        if key in seen:
            continue
        seen.add(key)
        formatted_spec = format_spec(*key)
        if required:
            caps = caps_by_model.get(row["id"])
            if caps is None:
                caps = catalog.capabilities_for(conn, row["id"])
                caps_by_model[row["id"]] = caps
            missing = [
                {"capability": cap, "value": caps.get(cap, "unknown")}
                for cap in required
                if caps.get(cap) != "yes"
            ]
            if missing:
                excluded.append({"spec": formatted_spec, "missing": missing})
                continue
        own = [r for r in records if (r["agent"], r["model"], r["effort"]) == key]
        chosen = None
        for name, use_type, use_complexity in LEVELS:
            subset = _level_subset(own, task_type, complexity, use_type, use_complexity)
            if len(subset) >= tx.CONFIDENCE_LOW_MIN:
                chosen = (name, subset, use_type, use_complexity)
                break
        if chosen is None:
            for name, use_type, use_complexity in LEVELS:
                subset = _level_subset(own, task_type, complexity, use_type, use_complexity)
                if subset:
                    chosen = (name, subset, use_type, use_complexity)
                    break
        if chosen is None:
            level, subset = None, []
            prior = prior_for(records, task_type, complexity)
        else:
            level, subset, use_type, use_complexity = chosen
            prior = prior_for(
                records, task_type if use_type else None, complexity if use_complexity else None
            )
        entry = {
            "spec": formatted_spec,
            "agent": key[0],
            "model": key[1],
            "effort": key[2],
            "cost_tier": row["cost_tier"],
            "level": level,
        }
        entry.update(summarize(subset, prior))
        task_type_records = [r for r in own if r["task_type"] == task_type]
        spec_meta[entry["spec"]] = {
            "n_task_type": len(task_type_records),
            "task_type_mean": _mean([r["score"] for r in task_type_records]),
            "order": len(candidates),
        }
        candidates.append(entry)
    eligible = [c for c in candidates if c["confidence"] in ("low", "ok") and not c["red_flag"]]
    recommendation = None
    recommended_model = None
    reason = None
    if not candidates:
        reason = "no_capable_candidates"
    elif eligible:
        best = max(c["smoothed_score"] for c in eligible)
        window = [c for c in eligible if c["smoothed_score"] >= best - tx.RECOMMEND_WINDOW]
        pick = min(window, key=lambda c: (c["cost_tier"], -c["smoothed_score"], c["spec"]))
        recommendation = {k: pick[k] for k in ("spec", "cost_tier", "smoothed_score", "confidence", "level")}
        recommended_model = (pick["agent"], pick["model"])
    elif any(c["confidence"] in ("low", "ok") for c in candidates):
        reason = "all_candidates_red_flagged"
    else:
        reason = "insufficient_data"
    candidates_in_order = list(candidates)
    candidates.sort(key=lambda c: (-c["smoothed_score"], c["spec"]))
    explore, explore_reason = _build_explore(
        candidates_in_order,
        spec_meta,
        records=records,
        task_type=task_type,
        complexity=complexity,
        recommended_model=recommended_model,
    )
    return {
        "task_type": task_type,
        "complexity": complexity,
        "recommendation": recommendation,
        "reason": reason,
        "window": tx.RECOMMEND_WINDOW,
        "candidates": candidates,
        "explore": explore,
        "explore_reason": explore_reason,
        "excluded": excluded,
    }


# --- show / explain --------------------------------------------------------


def show_change(conn: sqlite3.Connection, *, project_id: int, ref: str) -> dict:
    change = record.get_change(conn, project_id, ref)
    by_session = _incidents_by(conn, "session_id")
    sessions = []
    for row in conn.execute("SELECT id, verdict FROM sessions WHERE change_id = ? ORDER BY id", (change["id"],)):
        entry = record.session_dict(conn, row["id"])
        score = session_score(row["verdict"], by_session.get(row["id"], []))
        entry["score"] = None if score is None else round(score, 2)
        sessions.append(entry)
    incidents = [
        record.incident_dict(conn, r["id"])
        for r in conn.execute("SELECT id FROM incidents WHERE change_id = ? ORDER BY id", (change["id"],))
    ]
    active = [i for i in incidents if i["voided_at"] is None]
    planner_score = None
    if any(s["verdict"] is not None for s in sessions):
        latest: dict = {}
        for s in sessions:
            latest[s["session"]] = s["tasks_total"]
        planner_score = round(planner_change_score(sum(latest.values()), active), 2)
    distinct_sessions = {s["session"] for s in sessions}
    exploratory_sessions = {
        s["session"]
        for s in sessions
        if any(tag.strip() == "explore" for tag in s["tags"])
    }
    n_sessions = len(distinct_sessions)
    n_exploratory = len(exploratory_sessions)
    allowed = 0 if n_sessions < 2 else max(1, n_sessions // 4)
    over_budget = None if change["closed_at"] is None else (n_exploratory > allowed)
    return {
        "change": record.change_dict(conn, change["id"]),
        "sessions": sessions,
        "incidents": incidents,
        "planner_score": planner_score,
        "incident_counts_by_role": dict(Counter(i["role"] for i in active)),
        "exploration": {
            "sessions": n_sessions,
            "exploratory": n_exploratory,
            "allowed": allowed,
            "over_budget": over_budget,
        },
    }


def explain() -> dict:
    return {
        "executor_session_score": {
            "formula": "clamp(base - penalty + credit, 0, 100)",
            "base": tx.VERDICT_BASE,
            "weights": tx.EXECUTOR_WEIGHTS,
            "correct_stop_credit": tx.CORRECT_STOP_CREDIT,
        },
        "planner_change_score": {
            "formula": "clamp(100 - 5 * (penalty / max(tasks, 10) * 10), 0, 100)",
            "weights": tx.PLANNER_WEIGHTS,
            "density_factor": tx.PLANNER_DENSITY_FACTOR,
            "min_tasks": tx.PLANNER_MIN_TASKS,
        },
        "dimension_score": {
            "formula": "clamp(100 - penalty, 0, 100)",
            "dimensions": [
                {"dimension": dimension, "codes": list(codes)} for dimension, codes in tx.DIMENSIONS.items()
            ],
            "correct_stop_excluded": True,
            "note": DIMENSION_NOTE,
        },
        "severity_multipliers": tx.SEVERITY_MULT,
        "late_detection": {"detected_by": list(tx.LATE_DETECTION), "multiplier": tx.LATE_DETECTION_MULT},
        "smoothing": {
            "formula": "(n * mean + k * prior) / (n + k)",
            "k": tx.SMOOTHING_K,
            "default_prior": tx.DEFAULT_PRIOR,
        },
        "confidence": {"insufficient": "n < 3", "low": "3 <= n < 10", "ok": "n >= 10"},
        "recommendation": {
            "levels": [name for name, _, _ in LEVELS],
            "window": tx.RECOMMEND_WINDOW,
            "honesty_red_flag_above": tx.HONESTY_RED_FLAG,
        },
        "exploration": {
            "rule": (
                "At low or medium complexity, suggest up to max models where no listed effort has "
                "min_task_type_sessions or more task-type audits, no listed effort is red-flagged "
                "on 3 or more sessions, and the model is not the recommendation."
            ),
            "complexities": list(tx.EXPLORE_COMPLEXITIES),
            "max": tx.EXPLORE_MAX,
            "min_task_type_sessions": tx.CONFIDENCE_LOW_MIN,
            "sort_order": [
                "deprioritized last (red_flag_low_data or weak_start)",
                "cost_tier ascending",
                "n_task_type descending",
                "spec ascending",
            ],
        },
        "require": {
            "rule": (
                "A candidate stays only if every required capability is yes; "
                "others go to excluded with missing values no or unknown; "
                "the prior still uses all executor records."
            ),
            "capabilities": list(tx.CAPABILITIES),
            "values": list(tx.CAPABILITY_VALUES),
        },
        "retry_reasons_excluded_from_executor_metrics": list(tx.NON_EXECUTOR_RETRY_REASONS),
    }
