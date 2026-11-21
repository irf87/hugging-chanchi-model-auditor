import os

import pytest

from chanchi import skills_link
from chanchi.errors import ChanchiError


@pytest.fixture
def skills_dir(tmp_path):
    root = tmp_path / "repo" / "skills"
    for name in ("skill-chanchi-a", "skill-chanchi-b", "other"):
        (root / name).mkdir(parents=True)
        (root / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n")
    (root / "skill-chanchi-empty").mkdir()  # no SKILL.md: ignored
    return root


@pytest.fixture
def project(tmp_path):
    base = tmp_path / "project"
    base.mkdir()
    return base


def test_available_skills(skills_dir):
    assert skills_link.available_skills(skills_dir) == ["skill-chanchi-a", "skill-chanchi-b"]


def test_repo_skills_dir_points_at_repository():
    assert skills_link.repo_skills_dir().name == "skills"
    assert (skills_link.repo_skills_dir().parent / "pyproject.toml").exists()


def test_link_creates_primary_and_relative_secondary(project, skills_dir):
    result = skills_link.link(project, skills_dir=skills_dir)
    primary = project / ".agents" / "skills" / "skill-chanchi-a"
    secondary = project / ".claude" / "skills" / "skill-chanchi-a"
    assert os.readlink(primary) == str(skills_dir.resolve() / "skill-chanchi-a")
    assert os.readlink(secondary) == os.path.join("..", "..", ".agents", "skills", "skill-chanchi-a")
    assert secondary.resolve() == (skills_dir / "skill-chanchi-a").resolve()
    assert result["skills"] == ["skill-chanchi-a", "skill-chanchi-b"]
    assert len(result["created"]) == 4
    assert result["existing"] == []
    assert "skill-chanchi-session-audit" in result["suggested_config_line"]
    assert not (project / ".agent").exists()
    assert not (project / ".opencode").exists()


def test_link_is_idempotent(project, skills_dir):
    skills_link.link(project, skills_dir=skills_dir)
    again = skills_link.link(project, skills_dir=skills_dir)
    assert again["created"] == []
    assert len(again["existing"]) == 4


def test_link_reports_conflicts_without_overwriting(project, skills_dir):
    blocker = project / ".claude" / "skills" / "skill-chanchi-a"
    blocker.mkdir(parents=True)
    with pytest.raises(ChanchiError) as info:
        skills_link.link(project, skills_dir=skills_dir)
    assert info.value.code == "link_conflict"
    assert str(blocker.resolve()) in info.value.message
    assert blocker.is_dir() and not blocker.is_symlink()
    assert (project / ".claude" / "skills" / "skill-chanchi-b").is_symlink()
    created_primary = project / ".agents" / "skills" / "skill-chanchi-a"
    assert str(created_primary) in info.value.message
    assert "created:" in info.value.message
    assert "conflicts:" in info.value.message


def test_global_link_adds_agy_cli_dir_only_when_present(tmp_path, skills_dir):
    home = tmp_path / "home"
    home.mkdir()
    skills_link.link(home, global_=True, skills_dir=skills_dir)
    assert not (home / ".gemini").exists()
    (home / ".gemini" / "antigravity-cli").mkdir(parents=True)
    result = skills_link.link(home, global_=True, skills_dir=skills_dir)
    agy = home / ".gemini" / "antigravity-cli" / "skills" / "skill-chanchi-a"
    assert agy.is_symlink() and agy.resolve() == (skills_dir / "skill-chanchi-a").resolve()
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
    assert not (project / ".agents" / "skills" / "skill-chanchi-a").exists()


def test_unlink_removes_dangling_secondary(project, skills_dir):
    skills_link.link(project, skills_dir=skills_dir)
    (project / ".agents" / "skills" / "skill-chanchi-a").unlink()
    result = skills_link.unlink(project, skills_dir=skills_dir)
    assert str(project.resolve() / ".claude" / "skills" / "skill-chanchi-a") in result["removed"]


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
    primary = project / ".agents" / "skills" / "skill-chanchi-a"
    primary.parent.mkdir(parents=True)
    primary.symlink_to(elsewhere)
    with pytest.raises(ChanchiError) as info:
        skills_link.link(project, skills_dir=skills_dir)
    assert info.value.code == "link_conflict"
    assert str(primary.resolve().parent / "skill-chanchi-a") in info.value.message or str(project.resolve() / ".agents" / "skills" / "skill-chanchi-a") in info.value.message
    assert os.readlink(primary) == str(elsewhere)


def test_link_nonexistent_path_raises_and_creates_nothing(tmp_path, skills_dir):
    missing = tmp_path / "does_not_exist"
    with pytest.raises(ChanchiError) as info:
        skills_link.link(missing, skills_dir=skills_dir)
    assert info.value.code == "invalid_value"
    assert info.value.field == "path"
    assert info.value.hint == "pass an existing project directory"
    assert not missing.exists()


def test_unlink_nonexistent_path_raises(tmp_path, skills_dir):
    missing = tmp_path / "does_not_exist"
    with pytest.raises(ChanchiError) as info:
        skills_link.unlink(missing, skills_dir=skills_dir)
    assert info.value.code == "invalid_value"
    assert info.value.field == "path"
    assert info.value.hint == "pass an existing project directory"


def legacy_layout(home, skills_dir):
    """Global links as an older chanchi left them: pointing at skills/chanchi-<n>, now gone."""
    primary = home / ".agents" / "skills"
    secondary = home / ".claude" / "skills"
    primary.mkdir(parents=True)
    secondary.mkdir(parents=True)
    for n in ("a", "b"):
        (primary / f"chanchi-{n}").symlink_to(skills_dir / f"chanchi-{n}")  # dangling
        (secondary / f"chanchi-{n}").symlink_to(os.path.join("..", "..", ".agents", "skills", f"chanchi-{n}"))
    return primary, secondary


def test_global_link_repairs_legacy_links_into_compat_links(tmp_path, skills_dir):
    home = tmp_path / "home"
    primary, secondary = legacy_layout(home, skills_dir)
    result = skills_link.link(home, global_=True, skills_dir=skills_dir)
    for directory in (primary, secondary):
        compat = directory / "chanchi-a"
        assert compat.is_symlink() and os.readlink(compat) == "skill-chanchi-a"
        assert (compat / "SKILL.md").read_text().startswith("---\nname: skill-chanchi-a")
        assert (directory / "skill-chanchi-a").resolve() == (skills_dir / "skill-chanchi-a").resolve()
    assert len(result["repaired"]) == 4


def test_global_link_no_compat_removes_compat_links(tmp_path, skills_dir):
    home = tmp_path / "home"
    legacy_layout(home, skills_dir)
    skills_link.link(home, global_=True, skills_dir=skills_dir)
    skills_link.link(home, global_=True, skills_dir=skills_dir, compat=False)
    assert not os.path.lexists(home / ".agents" / "skills" / "chanchi-a")
    assert not os.path.lexists(home / ".claude" / "skills" / "chanchi-a")


def test_project_link_creates_no_compat_links(project, skills_dir):
    skills_link.link(project, skills_dir=skills_dir)
    assert not os.path.lexists(project / ".agents" / "skills" / "chanchi-a")


def test_foreign_legacy_name_is_still_a_conflict(tmp_path, skills_dir):
    home = tmp_path / "home"
    foreign = home / ".agents" / "skills" / "chanchi-a"
    foreign.mkdir(parents=True)  # a real directory chanchi did not create
    with pytest.raises(ChanchiError) as info:
        skills_link.link(home, global_=True, skills_dir=skills_dir)
    assert info.value.code == "link_conflict"
    assert foreign.is_dir() and not foreign.is_symlink()


def test_global_link_is_idempotent_with_compat(tmp_path, skills_dir):
    home = tmp_path / "home"
    home.mkdir()
    skills_link.link(home, global_=True, skills_dir=skills_dir)
    again = skills_link.link(home, global_=True, skills_dir=skills_dir)
    assert again["created"] == [] and again["repaired"] == []


def test_chained_secondary_to_foreign_primary_is_kept(tmp_path, skills_dir):
    home = tmp_path / "home"
    foreign = home / ".agents" / "skills" / "chanchi-x"
    foreign.mkdir(parents=True)
    chained = home / ".claude" / "skills" / "chanchi-x"
    chained.parent.mkdir(parents=True)
    chained.symlink_to(os.path.join("..", "..", ".agents", "skills", "chanchi-x"))
    skills_link.link(home, global_=True, skills_dir=skills_dir)
    skills_link.unlink(home, global_=True, skills_dir=skills_dir)
    assert foreign.is_dir() and chained.is_symlink()


def test_unlink_removes_new_legacy_and_compat_links(tmp_path, skills_dir):
    home = tmp_path / "home"
    legacy_layout(home, skills_dir)
    skills_link.link(home, global_=True, skills_dir=skills_dir)
    skills_link.unlink(home, global_=True, skills_dir=skills_dir)
    for directory in (home / ".agents" / "skills", home / ".claude" / "skills"):
        assert [p.name for p in directory.iterdir()] == []
