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


# --- promotion.toml -------------------------------------------------------------------


def write_promotion(tmp_path, text):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "promotion.toml").write_text(text, encoding="utf-8")
    return {"CHANCHI_SYNC": str(tmp_path)}


def test_promotion_defaults_without_sync_and_without_the_file(tmp_path):
    defaults = {"min_uses": 3, "vendored_share": 0.5}
    assert sync.promotion({"CHANCHI_SYNC": str(tmp_path / "missing")}) == defaults
    (tmp_path / "config").mkdir()  # SYNC exists but has no promotion.toml
    assert sync.promotion({"CHANCHI_SYNC": str(tmp_path)}) == defaults


def test_promotion_reads_both_keys_and_either_alone(tmp_path):
    env = write_promotion(tmp_path, "min_uses = 2\nvendored_share = 0.75\n")
    assert sync.promotion(env) == {"min_uses": 2, "vendored_share": 0.75}
    env = write_promotion(tmp_path, "min_uses = 5\n")
    assert sync.promotion(env) == {"min_uses": 5, "vendored_share": 0.5}
    env = write_promotion(tmp_path, "# only a comment\nvendored_share = 0.6\n")
    assert sync.promotion(env) == {"min_uses": 3, "vendored_share": 0.6}


def test_promotion_accepts_a_vendored_share_of_exactly_one(tmp_path):
    env = write_promotion(tmp_path, "vendored_share = 1\n")
    assert sync.promotion(env)["vendored_share"] == 1
    env = write_promotion(tmp_path, "vendored_share = 1.0\n")
    assert sync.promotion(env)["vendored_share"] == 1


@pytest.mark.parametrize(
    "text",
    [
        "other = 1\n",
        "min_uses = 3\nextra = true\n",
        "min_uses = 0\n",
        "min_uses = -1\n",
        "min_uses = true\n",
        "min_uses = 2.0\n",
        'min_uses = "3"\n',
        "vendored_share = 0\n",
        "vendored_share = 0.0\n",
        "vendored_share = 1.01\n",
        "vendored_share = -0.5\n",
        "vendored_share = true\n",
        'vendored_share = "0.5"\n',
        "vendored_share = nan\n",
        "min_uses = [1]\n",
        "[section]\nmin_uses = 3\n",
        "min_uses = \n",
    ],
)
def test_promotion_refuses_bad_files(tmp_path, text):
    env = write_promotion(tmp_path, text)
    with pytest.raises(ChanchiError) as exc:
        sync.promotion(env)
    assert exc.value.code == "invalid_value"
    assert exc.value.field == "promotion"
    assert "promotion.toml" in exc.value.message


def test_promotion_refuses_a_file_that_is_not_utf8(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "promotion.toml").write_bytes(b"min_uses = \xff\n")
    with pytest.raises(ChanchiError) as exc:
        sync.promotion({"CHANCHI_SYNC": str(tmp_path)})
    assert exc.value.code == "invalid_value" and exc.value.field == "promotion"


def test_sync_init_creates_folders_and_is_idempotent(tmp_path):
    target = tmp_path / "SYNC"
    env = {"CHANCHI_SYNC": str(target)}
    first = sync.init(env)
    assert first == {
        "path": str(target),
        "created": ["config", "ITEMS/agents", "ITEMS/skills"],
        "link": None,
    }
    for sub in ("config", "ITEMS/agents", "ITEMS/skills"):
        assert (target / sub).is_dir()

    second = sync.init(env)
    assert second == {"path": str(target), "created": [], "link": None}


def test_sync_init_with_link_creates_symlink_and_recommendation(tmp_path):
    repo = make_repo(tmp_path)
    cloud = tmp_path / "cloud" / "chanchi-sync"
    result = sync.init({}, repo_root=repo, link=cloud)
    expected_sync = repo.resolve() / "SYNC"
    assert result["path"] == str(expected_sync)
    assert result["created"] == ["config", "ITEMS/agents", "ITEMS/skills"]
    assert result["link"] == str(cloud)
    for needle in ("Google Drive", "iCloud Drive", "Dropbox", "private git"):
        assert needle in result["recommendation"]
    assert expected_sync.is_symlink()
    assert expected_sync.readlink() == cloud
    for sub in ("config", "ITEMS/agents", "ITEMS/skills"):
        assert (cloud / sub).is_dir()
    # sync_path keeps the unresolved SYNC path
    assert sync.sync_path({}, repo_root=repo) == expected_sync
    assert sync.require({}, repo_root=repo) == expected_sync


def test_sync_init_link_refuses_existing_entry_and_non_directory_target(tmp_path):
    # Existing directory at SYNC
    existing_dir = tmp_path / "existing-dir"
    existing_dir.mkdir()
    (existing_dir / "keep.txt").write_text("keep")
    cloud = tmp_path / "cloud"
    with pytest.raises(ChanchiError) as exc:
        sync.init({"CHANCHI_SYNC": str(existing_dir)}, link=cloud)
    assert exc.value.code == "link_conflict"
    assert exc.value.hint == "chanchi sync status"
    assert (existing_dir / "keep.txt").read_text() == "keep"
    assert not cloud.exists()

    # Existing regular file at SYNC
    existing_file = tmp_path / "existing-file"
    existing_file.write_text("hello")
    with pytest.raises(ChanchiError) as exc:
        sync.init({"CHANCHI_SYNC": str(existing_file)}, link=cloud)
    assert exc.value.code == "link_conflict"
    assert existing_file.read_text() == "hello"

    # Existing dangling symlink at SYNC
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "gone")
    with pytest.raises(ChanchiError) as exc:
        sync.init({"CHANCHI_SYNC": str(dangling)}, link=cloud)
    assert exc.value.code == "link_conflict"
    assert dangling.is_symlink() and dangling.readlink() == tmp_path / "gone"

    # --link pointing to an existing file -> invalid_value
    file_target = tmp_path / "file-target"
    file_target.write_text("nope")
    fresh = tmp_path / "fresh-sync"
    with pytest.raises(ChanchiError) as exc:
        sync.init({"CHANCHI_SYNC": str(fresh)}, link=file_target)
    assert exc.value.code == "invalid_value"
    assert exc.value.field == "link"
    assert not fresh.exists()


def test_sync_init_plain_errors_on_file_dangling_link_and_missing_root(tmp_path):
    existing_file = tmp_path / "file-sync"
    existing_file.write_text("data")
    with pytest.raises(ChanchiError) as exc:
        sync.init({"CHANCHI_SYNC": str(existing_file)})
    assert exc.value.code == "link_conflict"

    dangling = tmp_path / "dangling-sync"
    dangling.symlink_to(tmp_path / "missing-target")
    with pytest.raises(ChanchiError) as exc:
        sync.init({"CHANCHI_SYNC": str(dangling)})
    assert exc.value.code == "missing_prerequisite"
    assert exc.value.hint == "chanchi sync status"

    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ChanchiError) as exc:
        sync.init({}, repo_root=plain)
    assert exc.value.code == "missing_prerequisite"
    assert "CHANCHI_SYNC" in exc.value.hint


def test_sync_status_reports_missing_linked_and_dangling_without_creating(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert sync.status({}, repo_root=plain) == {
        "path": None,
        "exists": False,
        "is_link": False,
        "target": None,
        "reachable": False,
        "config": False,
        "items": False,
    }

    sync_link = tmp_path / "SYNC"
    cloud = tmp_path / "cloud"
    env = {"CHANCHI_SYNC": str(sync_link)}
    assert sync.status(env) == {
        "path": str(sync_link),
        "exists": False,
        "is_link": False,
        "target": None,
        "reachable": False,
        "config": False,
        "items": False,
    }
    assert not sync_link.exists()

    sync.init(env, link=cloud)
    assert sync.status(env) == {
        "path": str(sync_link),
        "exists": True,
        "is_link": True,
        "target": str(cloud),
        "reachable": True,
        "config": True,
        "items": True,
    }

    # Remove the link target: status reports reachable=False and does not recreate it
    import shutil
    shutil.rmtree(cloud)
    assert sync.status(env) == {
        "path": str(sync_link),
        "exists": True,
        "is_link": True,
        "target": str(cloud),
        "reachable": False,
        "config": False,
        "items": False,
    }
    assert not cloud.exists()


def test_sync_init_from_worktree_creates_in_main_checkout(tmp_path):
    repo = make_repo(tmp_path)
    worktree = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "side", str(worktree)], cwd=repo, check=True)
    result = sync.init({}, repo_root=worktree)
    expected = repo.resolve() / "SYNC"
    assert result["path"] == str(expected)
    assert (expected / "config").is_dir()
    assert (expected / "ITEMS" / "agents").is_dir()
    assert (expected / "ITEMS" / "skills").is_dir()
    assert not (worktree / "SYNC").exists()


def test_sync_require_raises_when_missing_or_dangling(tmp_path):
    env = {"CHANCHI_SYNC": str(tmp_path / "missing")}
    with pytest.raises(ChanchiError) as exc:
        sync.require(env)
    assert exc.value.code == "missing_prerequisite"
    assert exc.value.hint == "chanchi sync init"

    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "gone")
    with pytest.raises(ChanchiError) as exc:
        sync.require({"CHANCHI_SYNC": str(dangling)})
    assert exc.value.code == "missing_prerequisite"
    assert exc.value.hint == "chanchi sync init"


def test_sync_is_gitignored_in_this_repository():
    import os

    root = Path(__file__).resolve().parents[1]
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    proc = subprocess.run(
        ["git", "check-ignore", "-q", "SYNC"], cwd=root, env=clean_env, check=False
    )
    assert proc.returncode == 0
