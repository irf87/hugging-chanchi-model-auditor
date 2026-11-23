"""Grader for eval-chanchi-session-audit/scope-and-choices."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def emit(criterion: str, passed: bool, detail: str) -> None:
    print(json.dumps({"criterion": criterion, "pass": passed, "detail": detail}))


def load_show(workdir: Path, ref: str) -> dict | None:
    proc = subprocess.run(
        ["chanchi", "show", ref],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    workdir = Path(sys.argv[1])
    data = load_show(workdir, "demo-chg")
    if data is None:
        for cid in ("scope_drift_incident", "plan_delegated_decision_incident"):
            emit(cid, False, "chanchi show demo-chg failed or returned invalid JSON")
        return 0

    incidents = [inc for inc in data.get("incidents", []) if not inc.get("voided_at")]
    scope_drifts = [inc for inc in incidents if inc.get("code") == "scope_drift"]
    delegated = [inc for inc in incidents if inc.get("code") == "plan_delegated_decision"]

    emit(
        "scope_drift_incident",
        len(scope_drifts) == 1,
        f"active scope_drift incidents={len(scope_drifts)}",
    )
    emit(
        "plan_delegated_decision_incident",
        len(delegated) == 1,
        f"active plan_delegated_decision incidents={len(delegated)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
