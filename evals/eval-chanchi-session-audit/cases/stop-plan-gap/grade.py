"""Grader for eval-chanchi-session-audit/stop-plan-gap."""

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
        for cid in ("s1_stopped", "plan_gap_blocking", "correct_stop_s1", "not_accepted"):
            emit(cid, False, "chanchi show demo-chg failed or returned invalid JSON")
        return 0

    sessions = [s for s in data.get("sessions", []) if s.get("session") == "S1"]
    s1 = sessions[-1] if sessions else {}
    reported = s1.get("reported_status")
    emit("s1_stopped", reported == "STOPPED", f"reported_status={reported!r}")

    incidents = [inc for inc in data.get("incidents", []) if not inc.get("voided_at")]
    plan_gaps = [
        inc
        for inc in incidents
        if inc.get("code") == "plan_gap"
        and inc.get("severity") == "blocking"
        and bool((inc.get("evidence") or "").strip())
    ]
    emit(
        "plan_gap_blocking",
        len(plan_gaps) == 1,
        f"matching blocking plan_gap incidents={len(plan_gaps)}",
    )

    correct_stops = [
        inc
        for inc in incidents
        if inc.get("code") == "correct_stop"
        and inc.get("session") == "S1"
        and bool((inc.get("evidence") or "").strip())
    ]
    emit(
        "correct_stop_s1",
        len(correct_stops) == 1,
        f"matching S1 correct_stop incidents={len(correct_stops)}",
    )

    verdict = s1.get("verdict")
    emit("not_accepted", verdict != "accepted", f"verdict={verdict!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
