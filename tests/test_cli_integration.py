import json
import os
import subprocess
import sys


def chanchi(cwd, env, *args):
    result = subprocess.run(
        [sys.executable, "-m", "chanchi", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False
    )
    return result.returncode, result.stdout, result.stderr


def test_end_to_end_through_a_subprocess(tmp_path):
    repo = tmp_path / "demo-app"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    env = {**os.environ, "CHANCHI_DB": str(tmp_path / "data" / "chanchi.db")}

    steps = [
        ("models", "add", "--agent", "claude", "--model", "opus", "--cost", "3"),
        ("models", "add", "--agent", "claude", "--model", "haiku", "--cost", "1"),
        ("change", "open", "c1", "--kind", "openspec", "--planner", "claude:opus:high"),
        ("session", "start", "c1", "S1", "--executor", "claude:haiku:low", "--task-type", "docs",
         "--complexity", "low", "--tasks", "2"),
        ("session", "report", "c1", "S1", "--status", "COMPLETE"),
        ("session", "audit", "c1", "S1", "--verdict", "accepted"),
        ("change", "close", "c1"),
    ]
    for step in steps:
        code, out, err = chanchi(repo, env, *step)
        assert code == 0, (step, err)
        assert json.loads(out)["ok"] is True

    code, out, _ = chanchi(repo, env, "show", "c1")
    assert code == 0
    assert json.loads(out)["sessions"][0]["score"] == 100

    code, out, err = chanchi(repo, env, "session", "start", "c1", "S2", "--executor", "claude:haiku",
                             "--task-type", "docs", "--complexity", "tiny", "--tasks", "1")
    assert code == 2 and out == ""
    assert json.loads(err)["error"]["code"] == "invalid_value"

    outside = tmp_path / "outside"
    outside.mkdir()
    code, _, err = chanchi(outside, env, "show", "c1")
    assert code == 2
    assert json.loads(err)["error"]["code"] == "project_not_detected"
    code, out, _ = chanchi(outside, env, "show", "c1", "--project", "demo-app")
    assert code == 0 and json.loads(out)["change"]["ref"] == "c1"
