"""SYNC resolution and the auditor roster."""

import subprocess
from pathlib import Path

import pytest

from chanchi import sync
from chanchi.errors import ChanchiError

GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com"]


def make_repo(root: Path) -> Path:
    repo = root / "main-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def test_sync_dir_from_environment(tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir()
    assert sync.sync_dir({"CHANCHI_SYNC": str(target)}) == target


def test_sync_dir_environment_missing_directory_is_none(tmp_path):
    assert sync.sync_dir({"CHANCHI_SYNC": str(tmp_path / "nope")}) is None


def test_sync_dir_from_main_checkout_and_worktree_agree(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "SYNC").mkdir()
    worktree = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "side", str(worktree)], cwd=repo, check=True)
    from_main = sync.sync_dir({}, repo_root=repo)
    from_worktree = sync.sync_dir({}, repo_root=worktree)
    assert from_main == (repo / "SYNC").resolve()
    assert from_worktree == from_main


def test_sync_dir_missing_directory_is_none(tmp_path):
    repo = make_repo(tmp_path)
    assert sync.sync_dir({}, repo_root=repo) is None


def test_sync_dir_without_a_checkout_is_none(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert sync.sync_dir({}, repo_root=plain) is None


def test_builtin_roster_is_the_design_list():
    assert [(e["harness"], e["model"], e["effort"]) for e in sync.BUILTIN_ROSTER] == [
        ("claude", "sonnet", "medium"),
        ("agy", "gemini-4-neon-high", "high"),
        ("opencode", "opencode-go/minimax-m3", None),
        ("agy", "gemini-4-hydrogen-high", "high"),
    ]


def test_roster_falls_back_to_the_builtin_one(tmp_path):
    assert sync.roster({"CHANCHI_SYNC": str(tmp_path / "missing")}) == sync.BUILTIN_ROSTER
    (tmp_path / "config").mkdir()  # SYNC exists but has no auditors.toml
    assert sync.roster({"CHANCHI_SYNC": str(tmp_path)}) == sync.BUILTIN_ROSTER


def write_roster(tmp_path, text):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "auditors.toml").write_text(text, encoding="utf-8")
    return {"CHANCHI_SYNC": str(tmp_path)}


def test_roster_reads_auditors_toml(tmp_path):
    env = write_roster(
        tmp_path,
        '[[auditor]]\nharness = "opencode"\nmodel = "opencode-go/glm-5.3"\n\n'
        '[[auditor]]\nharness = "claude"\nmodel = "opus"\neffort = "high"\n',
    )
    assert sync.roster(env) == [
        {"harness": "opencode", "model": "opencode-go/glm-5.3", "effort": None},
        {"harness": "claude", "model": "opus", "effort": "high"},
    ]


@pytest.mark.parametrize(
    "text, needle",
    [
        ("[[auditor]\nharness =", "auditors.toml"),
        ('[[auditor]]\nharness = "claude"\n', "entry 1"),
        ('[[auditor]]\nharness = "claude"\nmodel = "ok"\n\n[[auditor]]\nmodel = "x"\n', "entry 2"),
        ('[[auditor]]\nharness = "claude"\nmodel = 7\n', "entry 1"),
        ('[[auditor]]\nharness = "claude"\nmodel = "m"\neffort = "huge"\n', "entry 1"),
        ('[[auditor]]\nharness = "claude"\nmodel = "m"\nefort = "high"\n', "entry 1"),
        ("auditor = 3\n", "auditors.toml"),
        ("# nothing\n", "auditors.toml"),
    ],
)
def test_malformed_roster_is_invalid_value(tmp_path, text, needle):
    env = write_roster(tmp_path, text)
    with pytest.raises(ChanchiError) as exc:
        sync.roster(env)
    assert exc.value.code == "invalid_value"
    assert "auditors.toml" in exc.value.message and needle in exc.value.message


def test_unknown_harness_lists_valid_values(tmp_path):
    env = write_roster(tmp_path, '[[auditor]]\nharness = "cursor"\nmodel = "m"\n')
    with pytest.raises(ChanchiError) as exc:
        sync.roster(env)
    assert exc.value.code == "invalid_value"
    assert exc.value.valid_values == ["claude", "opencode", "agy"]
    assert "entry 1" in exc.value.message
