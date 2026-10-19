import os

import pytest

from chanchi import skills_link
from chanchi.errors import ChanchiError


@pytest.fixture
def skills_dir(tmp_path):
    root = tmp_path / "repo" / "skills"
    for name in ("chanchi-a", "chanchi-b", "other"):
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n")
    (root / "chanchi-empty").mkdir()  # no SKILL.md: ignored
    return root


@pytest.fixture
def project(tmp_path):
    base = tmp_path / "project"
    base.mkdir()
    return base


def test_available_skills(skills_dir):
    assert skills_link.available_skills(skills_dir) == ["chanchi-a", "chanchi-b"]


def test_repo_skills_dir_points_at_repository():
    assert skills_link.repo_skills_dir().name == "skills"
    assert (skills_link.repo_skills_dir().parent / "pyproject.toml").exists()


def test_link_creates_primary_and_relative_secondary(project, skills_dir):
    result = skills_link.link(project, skills_dir=skills_dir)
    primary = project / ".agents" / "skills" / "chanchi-a"
    secondary = project / ".claude" / "skills" / "chanchi-a"
    assert os.readlink(primary) == str(skills_dir.resolve() / "chanchi-a")
    assert os.readlink(secondary) == os.path.join("..", "..", ".agents", "skills", "chanchi-a")
    assert secondary.resolve() == (skills_dir / "chanchi-a").resolve()
    assert result["skills"] == ["chanchi-a", "chanchi-b"]
    assert len(result["created"]) == 4
    assert result["existing"] == []
    assert "chanchi-session-audit" in result["suggested_config_line"]
    assert not (project / ".agent").exists()
    assert not (project / ".opencode").exists()


def test_link_is_idempotent(project, skills_dir):
    skills_link.link(project, skills_dir=skills_dir)
    again = skills_link.link(project, skills_dir=skills_dir)
    assert again["created"] == []
    assert len(again["existing"]) == 4


def test_link_reports_conflicts_without_overwriting(project, skills_dir):
    blocker = project / ".claude" / "skills" / "chanchi-a"
    blocker.mkdir(parents=True)
    with pytest.raises(ChanchiError) as info:
        skills_link.link(project, skills_dir=skills_dir)
    assert info.value.code == "link_conflict"
    assert str(blocker.resolve()) in info.value.message
    assert blocker.is_dir() and not blocker.is_symlink()
    assert (project / ".claude" / "skills" / "chanchi-b").is_symlink()


def test_global_link_adds_agy_cli_dir_only_when_present(tmp_path, skills_dir):
    home = tmp_path / "home"
    home.mkdir()
    skills_link.link(home, global_=True, skills_dir=skills_dir)
    assert not (home / ".gemini").exists()
    (home / ".gemini" / "antigravity-cli").mkdir(parents=True)
    result = skills_link.link(home, global_=True, skills_dir=skills_dir)
    agy = home / ".gemini" / "antigravity-cli" / "skills" / "chanchi-a"
    assert agy.is_symlink() and agy.resolve() == (skills_dir / "chanchi-a").resolve()
    assert len(result["created"]) == 2


def test_unlink_removes_only_own_links(project, skills_dir, tmp_path):
    skills_link.link(project, skills_dir=skills_dir)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    foreign = project / ".claude" / "skills" / "chanchi-zzz"
    foreign.symlink_to(elsewhere)
    plain = project / ".agents" / "skills" / "chanchi-plain"
    plain.mkdir()
    result = skills_link.unlink(project, skills_dir=skills_dir)
    assert len(result["removed"]) == 4
    assert foreign.is_symlink()
    assert plain.is_dir()
    assert not (project / ".agents" / "skills" / "chanchi-a").exists()


def test_unlink_removes_dangling_secondary(project, skills_dir):
    skills_link.link(project, skills_dir=skills_dir)
    (project / ".agents" / "skills" / "chanchi-a").unlink()
    result = skills_link.unlink(project, skills_dir=skills_dir)
    assert str(project.resolve() / ".claude" / "skills" / "chanchi-a") in result["removed"]


def test_unlink_keeps_secondary_pointing_at_a_foreign_primary(project, skills_dir):
    foreign = project / ".agents" / "skills" / "chanchi-x"
    foreign.mkdir(parents=True)
    secondary = project / ".claude" / "skills" / "chanchi-x"
    secondary.parent.mkdir(parents=True)
    secondary.symlink_to(os.path.join("..", "..", ".agents", "skills", "chanchi-x"))
    result = skills_link.unlink(project, skills_dir=skills_dir)
    assert result["removed"] == []
    assert secondary.is_symlink()
    assert foreign.is_dir()


def test_link_reports_a_symlink_pointing_elsewhere_as_conflict(project, skills_dir, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    primary = project / ".agents" / "skills" / "chanchi-a"
    primary.parent.mkdir(parents=True)
    primary.symlink_to(elsewhere)
    with pytest.raises(ChanchiError) as info:
        skills_link.link(project, skills_dir=skills_dir)
    assert info.value.code == "link_conflict"
    assert str(primary.resolve().parent / "chanchi-a") in info.value.message or str(project.resolve() / ".agents" / "skills" / "chanchi-a") in info.value.message
    assert os.readlink(primary) == str(elsewhere)
