"""Grader for eval-chanchi-session-audit/clean-complete."""

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
        for cid in ("s1_complete", "s1_accepted", "no_incident"):
            emit(cid, False, "chanchi show demo-chg failed or returned invalid JSON")
        return 0

    sessions = [s for s in data.get("sessions", []) if s.get("session") == "S1"]
    s1 = sessions[-1] if sessions else {}
    reported = s1.get("reported_status")
    emit("s1_complete", reported == "COMPLETE", f"reported_status={reported!r}")

    verdict = s1.get("verdict")
    emit("s1_accepted", verdict == "accepted", f"verdict={verdict!r}")

    incidents = [inc for inc in data.get("incidents", []) if not inc.get("voided_at")]
    emit("no_incident", len(incidents) == 0, f"active incidents={len(incidents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
