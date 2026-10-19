"""Parse and format model specs: agent:model[:effort]."""

from __future__ import annotations

from dataclasses import dataclass

from chanchi import taxonomy
from chanchi.errors import ChanchiError

SPEC_HINT = "use agent:model[:effort], e.g. claude:sonnet:medium"


@dataclass(frozen=True)
class ModelSpec:
    agent: str
    model: str
    effort: str | None


def parse(spec: str, *, field: str = "spec") -> ModelSpec:
    """The agent is before the first ':'; the last ':'-segment is an effort only if it is a valid one."""
    text = spec.strip()
    if text == "human":
        return ModelSpec("human", "human", None)
    if ":" not in text:
        raise ChanchiError(
            "invalid_value", f"{text!r} is not a model spec", field=field, hint=SPEC_HINT
        )
    agent, rest = text.split(":", 1)
    taxonomy.validate_choice(field, agent, taxonomy.ALL_AGENTS)
    effort = None
    if ":" in rest:
        head, last = rest.rsplit(":", 1)
        if last in taxonomy.EFFORTS:
            rest, effort = head, last
    if not rest:
        raise ChanchiError(
            "invalid_value", f"{text!r} has an empty model name", field=field, hint=SPEC_HINT
        )
    return ModelSpec(agent, rest, effort)


def format_spec(agent: str, model: str, effort: str | None) -> str:
    return f"{agent}:{model}" + (f":{effort}" if effort else "")
