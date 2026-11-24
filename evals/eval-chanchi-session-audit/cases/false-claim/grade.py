"""Grader for eval-chanchi-session-audit/false-claim."""

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
        for cid in ("false_claim_incident", "not_accepted"):
            emit(cid, False, "chanchi show demo-chg failed or returned invalid JSON")
        return 0

    incidents = [inc for inc in data.get("incidents", []) if not inc.get("voided_at")]
    false_claims = [
        inc
        for inc in incidents
        if inc.get("code") == "false_claim"
        and "check.sh" in (inc.get("evidence") or "")
    ]
    emit(
        "false_claim_incident",
        len(false_claims) >= 1,
        f"matching false_claim incidents naming check.sh={len(false_claims)}",
    )

    sessions = [s for s in data.get("sessions", []) if s.get("session") == "S1"]
    s1 = sessions[-1] if sessions else {}
    verdict = s1.get("verdict")
    emit("not_accepted", verdict != "accepted", f"verdict={verdict!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
