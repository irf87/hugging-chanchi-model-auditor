import re
from pathlib import Path

import pytest

from chanchi import cli, taxonomy

SKILLS = Path(__file__).resolve().parents[1] / "skills"
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TOP_LEVEL = {"recommend", "stats", "show"}
COMMAND = re.compile(r"`chanchi ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?")
SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    block = text.split("---\n", 2)[1]
    fields = {}
    for line in block.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_both_skills_exist():
    assert [p.parent.name for p in SKILL_FILES] == ["chanchi-model-selection", "chanchi-session-audit"]


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_frontmatter(path):
    fields = frontmatter(path)
    assert NAME.match(fields["name"])
    assert fields["name"] == path.parent.name
    assert 1 <= len(fields["description"]) <= 1024


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_documented_commands_exist(path, capsys):
    commands = set(COMMAND.findall(path.read_text(encoding="utf-8")))
    assert commands, f"{path} documents no chanchi command"
    for group, sub in commands:
        argv = [group, "--help"] if group in TOP_LEVEL or not sub else [group, sub, "--help"]
        assert cli.main(argv) == 0, f"{path}: `chanchi {group} {sub}` does not exist"
    capsys.readouterr()


def test_rubric_covers_every_incident_code():
    rubric = (SKILLS / "chanchi-session-audit" / "references" / "rubric.md").read_text(encoding="utf-8")
    for code in taxonomy.INCIDENT_CODES:
        assert f"`{code}`" in rubric, code
