"""The gate must not leak git's hook environment into the test suite."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_check_clears_git_hook_environment():
    text = (ROOT / "scripts" / "check").read_text(encoding="utf-8")
    assert "unset $(git rev-parse --local-env-vars)" in text, (
        "scripts/check must clear GIT_DIR, GIT_INDEX_FILE and the other variables git exports to "
        "hooks; tests that create repositories would otherwise write into this one"
    )


def test_local_env_vars_cover_the_hook_variables():
    names = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"], capture_output=True, text=True, check=True, cwd=ROOT,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    ).stdout.split()
    assert {"GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"} <= set(names)
