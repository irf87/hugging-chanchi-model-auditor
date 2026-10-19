import pytest

from chanchi import catalog
from chanchi.errors import ChanchiError


def test_add_and_list_models(seeded):
    specs = [m["spec"] for m in catalog.list_models(seeded)]
    assert "claude:sonnet" in specs
    assert "human:human" in specs
    flash = next(m for m in catalog.list_models(seeded) if m["model"] == "gemini-3.8-flash-high")
    assert flash["efforts"] == ["low", "medium", "high"]
    assert flash["active"] is True
    qwen = next(m for m in catalog.list_models(seeded) if m["agent"] == "opencode")
    assert qwen["efforts"] is None


def test_add_model_validations(conn):
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="human", model="x", cost_tier=1)
    assert info.value.field == "agent"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="x", cost_tier=4)
    assert info.value.field == "cost"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="x", cost_tier=1, efforts=["turbo"])
    assert info.value.field == "efforts"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="weird:high", cost_tier=1)
    assert info.value.field == "model"
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(conn, agent="claude", model="  ", cost_tier=1)
    assert info.value.field == "model"


def test_duplicate_model(seeded):
    with pytest.raises(ChanchiError) as info:
        catalog.add_model(seeded, agent="claude", model="sonnet", cost_tier=2)
    assert info.value.code == "duplicate"


def test_set_model(seeded):
    updated = catalog.set_model(seeded, spec="claude:sonnet", cost_tier=3, active=False, notes="paused")
    assert updated["cost_tier"] == 3
    assert updated["active"] is False
    assert updated["notes"] == "paused"
    assert "claude:sonnet" not in [m["spec"] for m in catalog.list_models(seeded)]
    assert "claude:sonnet" in [m["spec"] for m in catalog.list_models(seeded, include_inactive=True)]


def test_set_model_errors(seeded):
    with pytest.raises(ChanchiError) as info:
        catalog.set_model(seeded, spec="claude:sonnet")
    assert info.value.code == "invalid_value"
    with pytest.raises(ChanchiError) as info:
        catalog.set_model(seeded, spec="claude:sonnet:high", cost_tier=1)
    assert info.value.field == "spec"
    with pytest.raises(ChanchiError) as info:
        catalog.set_model(seeded, spec="claude:nope", cost_tier=1)
    assert info.value.code == "unknown_model"


def test_resolve_model(seeded):
    row, effort = catalog.resolve_model(seeded, "agy:gemini-3.8-flash-high:high", role="executor")
    assert row["agent"] == "agy" and effort == "high"
    row, effort = catalog.resolve_model(seeded, "human", role="planner")
    assert row["agent"] == "human" and effort is None
    _, effort = catalog.resolve_model(seeded, "claude:opus:unknown", role="planner")
    assert effort == "unknown"
    _, effort = catalog.resolve_model(seeded, "opencode:openrouter/qwen/qwen3-coder:free:high", role="executor")
    assert effort == "high"  # no efforts listed: any effort accepted


def test_resolve_model_errors(seeded):
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "claude:gpt-9", role="executor")
    assert info.value.code == "unknown_model"
    assert "chanchi models add --agent claude --model gpt-9" in info.value.hint
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "human", role="executor")
    assert info.value.field == "executor"
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "agy:gemini-3.8-flash-high:max", role="executor")
    assert info.value.valid_values == ["low", "medium", "high", "unknown"]
    catalog.set_model(seeded, spec="claude:haiku", active=False)
    with pytest.raises(ChanchiError) as info:
        catalog.resolve_model(seeded, "claude:haiku", role="executor")
    assert "--active 1" in info.value.hint


def test_task_types(conn):
    codes = [t["code"] for t in catalog.list_task_types(conn)]
    assert codes[0] == "ui-component" and len(codes) == 11
    added = catalog.add_task_type(conn, code="mobile-native", description="Native iOS/Android code")
    assert added == {"code": "mobile-native", "description": "Native iOS/Android code"}
    catalog.require_task_type(conn, "mobile-native")
    with pytest.raises(ChanchiError) as info:
        catalog.add_task_type(conn, code="mobile-native", description="again")
    assert info.value.code == "duplicate"
    with pytest.raises(ChanchiError) as info:
        catalog.add_task_type(conn, code="Bad_Code", description="x")
    assert info.value.field == "code"
    with pytest.raises(ChanchiError) as info:
        catalog.add_task_type(conn, code="ok-code", description=" ")
    assert info.value.field == "description"
    with pytest.raises(ChanchiError) as info:
        catalog.require_task_type(conn, "nope")
    assert info.value.field == "task_type"
    assert "ui-component" in info.value.valid_values


def test_human_row_cannot_be_modified(seeded):
    with pytest.raises(ChanchiError) as info:
        catalog.set_model(seeded, spec="human:human", active=False)
    assert info.value.field == "spec"
