"""Harness adapters: headless launch lines, user folders and binary availability."""

from pathlib import Path

import pytest

from chanchi import harnesses
from chanchi.errors import ChanchiError

HOME = Path("/home-for-tests")


def test_keys():
    assert harnesses.KEYS == ("claude", "opencode", "agy")


def test_launch_claude_with_and_without_effort():
    line = harnesses.launch("claude", agent="a-1", model="sonnet", effort="medium", prompt="<prompt>")
    assert line == (
        "claude -p --agent a-1 --model sonnet --effort medium "
        '--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob" -- "<prompt>" < /dev/null'
    )
    bare = harnesses.launch("claude", agent="a-1", model="sonnet", effort=None, prompt="<prompt>")
    assert bare == (
        "claude -p --agent a-1 --model sonnet "
        '--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob" -- "<prompt>" < /dev/null'
    )
    assert "--effort" not in bare


def test_launch_opencode_keeps_variant_and_ignores_effort():
    line = harnesses.launch(
        "opencode", agent="a-1", model="opencode-go/minimax-m3#thinking", effort="high", prompt="<prompt>"
    )
    assert line == 'opencode run --agent a-1 -m opencode-go/minimax-m3#thinking --auto "<prompt>" < /dev/null'


def test_launch_agy_splits_model_and_effort():
    line = harnesses.launch("agy", agent="a-1", model="gemini-4-neon-high", effort="high", prompt="<prompt>")
    assert (
        line
        == 'agy --agent a-1 --model gemini-4-neon --effort high --dangerously-skip-permissions -p="<prompt>" < /dev/null'
    )


def test_launch_agy_refuses_missing_or_mismatched_effort():
    with pytest.raises(ChanchiError) as missing:
        harnesses.launch("agy", agent="a", model="gemini-4-neon-high", effort=None, prompt="p")
    assert missing.value.code == "invalid_value"
    with pytest.raises(ChanchiError) as mismatch:
        harnesses.launch("agy", agent="a", model="gemini-4-neon-high", effort="medium", prompt="p")
    assert mismatch.value.code == "invalid_value"


def test_split_agy_model():
    assert harnesses.split_agy_model("gemini-4-hydrogen-high", "high") == "gemini-4-hydrogen"
    for model in ("gemini-4-neon", "high", "-high"):
        with pytest.raises(ChanchiError):
            harnesses.split_agy_model(model, "high")
    with pytest.raises(ChanchiError):
        harnesses.split_agy_model("gemini-4-neon-high", None)


def test_prompt_is_escaped_inside_double_quotes():
    line = harnesses.launch("claude", agent="a", model="m", effort=None, prompt='say "hi" $HOME `x` \\')
    assert line == (
        "claude -p --agent a --model m "
        '--permission-mode acceptEdits --allowedTools "Bash Read Grep Glob" '
        '-- "say \\"hi\\" \\$HOME \\`x\\` \\\\" < /dev/null'
    )


@pytest.mark.parametrize("key", harnesses.KEYS)
@pytest.mark.parametrize("profile", ("read-only", "workspace-write", "orchestrator"))
def test_launch_carries_permission_flags_and_add_dirs(key, profile):
    model = "gemini-4-neon-high" if key == "agy" else "m"
    effort = "high" if key == "agy" else None
    dirs = ("/tmp/r1", "/tmp/r2")
    line = harnesses.launch(key, agent="a", model=model, effort=effort, prompt="p", profile=profile, add_dirs=dirs)
    msg = "a headless launch line must carry its harness's permission flags (AGENTS.md, Working Conventions)"
    if key == "claude":
        assert "--permission-mode acceptEdits" in line, msg
        assert "--dangerously-skip-permissions" not in line, msg
        expected_tools = (
            "Bash Read Grep Glob" if profile == "read-only" else "Bash Read Grep Glob Edit Write"
        )
        assert f'--allowedTools "{expected_tools}"' in line, msg
        assert line.count("--add-dir ") == 2
        assert '--add-dir "/tmp/r1"' in line and '--add-dir "/tmp/r2"' in line
    elif key == "agy":
        assert "--dangerously-skip-permissions" in line, msg
        assert line.count("--add-dir ") == 2
        assert '--add-dir "/tmp/r1"' in line and '--add-dir "/tmp/r2"' in line
    else:
        assert " --auto " in line, msg
        assert "--add-dir" not in line


def test_launch_unknown_profile_is_refused():
    with pytest.raises(ChanchiError) as exc:
        harnesses.launch("claude", agent="a", model="m", effort=None, prompt="p", profile="admin")
    assert exc.value.code == "invalid_value"
    assert exc.value.field == "profile"
    assert exc.value.valid_values == list(harnesses.PROFILES)


def test_unknown_harness_lists_valid_keys():
    with pytest.raises(ChanchiError) as exc:
        harnesses.launch("cursor", agent="a", model="m", effort=None, prompt="p")
    assert exc.value.code == "invalid_value"
    assert exc.value.valid_values == list(harnesses.KEYS)
    with pytest.raises(ChanchiError):
        harnesses.home_dir("cursor", env={}, home=HOME)
    with pytest.raises(ChanchiError):
        harnesses.available("cursor", which=lambda _: None)


def test_home_dir_per_harness():
    assert harnesses.home_dir("claude", env={}, home=HOME) == HOME / ".claude"
    assert harnesses.home_dir("agy", env={}, home=HOME) == HOME / ".gemini"
    assert harnesses.home_dir("opencode", env={}, home=HOME) == HOME / ".config" / "opencode"


def test_opencode_home_honours_environment():
    env = {"XDG_CONFIG_HOME": "/xdg"}
    assert harnesses.home_dir("opencode", env=env, home=HOME) == Path("/xdg/opencode")
    env["OPENCODE_CONFIG_DIR"] = "/oc"
    assert harnesses.home_dir("opencode", env=env, home=HOME) == Path("/oc")


def test_installed_is_whether_the_folder_exists(tmp_path):
    assert harnesses.installed("claude", env={}, home=tmp_path) is False
    (tmp_path / ".claude").mkdir()
    assert harnesses.installed("claude", env={}, home=tmp_path) is True


def test_user_agent_path(tmp_path):
    claude = harnesses.user_agent_path("claude", "agent-chanchi-auditor", env={}, home=tmp_path)
    assert claude == tmp_path / ".claude" / "agents" / "agent-chanchi-auditor.md"
    agy = harnesses.user_agent_path("agy", "agent-chanchi-auditor", env={}, home=tmp_path)
    assert agy == tmp_path / ".gemini" / "config" / "agents" / "agent-chanchi-auditor" / "agent.md"
    env = {"OPENCODE_CONFIG_DIR": str(tmp_path / "oc")}
    opencode = harnesses.user_agent_path("opencode", "agent-chanchi-auditor", env=env, home=tmp_path)
    assert opencode == tmp_path / "oc" / "agents" / "agent-chanchi-auditor.md"


def test_available_uses_the_injected_lookup():
    seen = []

    def which(name):
        seen.append(name)
        return "/bin/x" if name == "claude" else None

    assert harnesses.available("claude", which=which) is True
    assert harnesses.available("agy", which=which) is False
    assert seen == ["claude", "agy"]
