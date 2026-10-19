import pytest

from chanchi.errors import ChanchiError
from chanchi.modelspec import ModelSpec, format_spec, parse


def test_agent_model_effort():
    assert parse("claude:sonnet:medium") == ModelSpec("claude", "sonnet", "medium")


def test_effort_is_optional():
    assert parse("claude:sonnet") == ModelSpec("claude", "sonnet", None)


def test_model_containing_effort_word_without_colon():
    assert parse("agy:gemini-3.8-flash-high:high") == ModelSpec("agy", "gemini-3.8-flash-high", "high")
    assert parse("agy:gemini-3.8-flash-high") == ModelSpec("agy", "gemini-3.8-flash-high", None)


def test_colon_suffix_that_is_not_an_effort_stays_in_the_model():
    assert parse("opencode:openrouter/qwen/qwen3-coder:free") == ModelSpec(
        "opencode", "openrouter/qwen/qwen3-coder:free", None
    )
    assert parse("opencode:openrouter/qwen/qwen3-coder:free:high") == ModelSpec(
        "opencode", "openrouter/qwen/qwen3-coder:free", "high"
    )


def test_unknown_effort_is_accepted():
    assert parse("claude:opus:unknown") == ModelSpec("claude", "opus", "unknown")


def test_human_shorthand():
    assert parse("human") == ModelSpec("human", "human", None)
    assert parse("human:human") == ModelSpec("human", "human", None)


def test_whitespace_is_trimmed():
    assert parse("  claude:haiku  ") == ModelSpec("claude", "haiku", None)


def test_missing_colon_is_invalid():
    with pytest.raises(ChanchiError) as info:
        parse("sonnet", field="executor")
    assert info.value.code == "invalid_value"
    assert info.value.field == "executor"


def test_unknown_agent_lists_agents():
    with pytest.raises(ChanchiError) as info:
        parse("cursor:gpt")
    assert info.value.valid_values == ["claude", "agy", "opencode", "human"]


def test_empty_model_is_invalid():
    with pytest.raises(ChanchiError):
        parse("claude:")
    with pytest.raises(ChanchiError):
        parse("claude::high")


def test_format_spec():
    assert format_spec("claude", "sonnet", "medium") == "claude:sonnet:medium"
    assert format_spec("claude", "sonnet", None) == "claude:sonnet"
