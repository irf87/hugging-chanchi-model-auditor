"""Harness adapters: headless launch lines, user-level folders and binary availability.

A leaf module (imports only chanchi.errors). chanchi never runs a harness: it only prints the launch
line and checks whether the binary is on PATH. Design: docs/designs/global-items.md, "Harness adapters".
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from chanchi.errors import ChanchiError

KEYS = ("claude", "opencode", "agy")

_BINARY = {"claude": "claude", "opencode": "opencode", "agy": "agy"}
_PLAIN = re.compile(r"^[A-Za-z0-9@%+=:,./#_-]+$")
_DQ_ESCAPED = re.compile(r'([\\"$`])')


def _key(key: str) -> str:
    if key not in KEYS:
        raise ChanchiError(
            "invalid_value",
            f"unknown harness {key!r}",
            field="harness",
            valid_values=KEYS,
        )
    return key


def _arg(value: str) -> str:
    """A shell word: left as is when it is plain, quoted otherwise (a mid-word `#` is not a comment)."""
    return value if _PLAIN.match(value) else shlex.quote(value)


def _dq(prompt: str) -> str:
    """The prompt as one double-quoted shell word."""
    return '"' + _DQ_ESCAPED.sub(r"\\\1", prompt) + '"'


def split_agy_model(model: str, effort: str | None) -> str:
    """The base of an agy catalog id `<base>-<effort>`; the effort must match the id's suffix."""
    if effort is None:
        raise ChanchiError(
            "invalid_value",
            f"agy needs an effort to launch {model!r}",
            field="effort",
            hint="set effort in the roster entry to the id's suffix, for example high",
        )
    suffix = f"-{effort}"
    if not model.endswith(suffix) or len(model) == len(suffix):
        raise ChanchiError(
            "invalid_value",
            f"agy model {model!r} does not end in -{effort}",
            field="effort",
            hint="the roster effort must equal the effort suffix of the agy catalog id",
        )
    return model[: -len(suffix)]


def launch(key: str, *, agent: str, model: str, effort: str | None, prompt: str) -> str:
    """The headless launch line of a harness. The caller runs it; chanchi never does."""
    _key(key)
    if key == "claude":
        flag = f" --effort {_arg(effort)}" if effort else ""
        return f"claude -p --agent {_arg(agent)} --model {_arg(model)}{flag} {_dq(prompt)} < /dev/null"
    if key == "opencode":
        return f"opencode run --agent {_arg(agent)} -m {_arg(model)} {_dq(prompt)} < /dev/null"
    base = split_agy_model(model, effort)
    return f'agy --agent {_arg(agent)} --model {_arg(base)} --effort {_arg(effort)} -p={_dq(prompt)} < /dev/null'


def home_dir(key: str, *, env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """The user-level folder of a harness."""
    _key(key)
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    if key == "claude":
        return home / ".claude"
    if key == "agy":
        return home / ".gemini"
    if env.get("OPENCODE_CONFIG_DIR"):
        return Path(env["OPENCODE_CONFIG_DIR"])
    if env.get("XDG_CONFIG_HOME"):
        return Path(env["XDG_CONFIG_HOME"]) / "opencode"
    return home / ".config" / "opencode"


def installed(key: str, *, env: Mapping[str, str] | None = None, home: Path | None = None) -> bool:
    """Whether the harness's user-level folder exists."""
    return home_dir(key, env=env, home=home).is_dir()


def user_agent_path(
    key: str, name: str, *, env: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """Where a user-level agent is written. agy: ~/.gemini/config/agents (decision D1 of the phase-1 plan)."""
    base = home_dir(key, env=env, home=home)
    if key == "claude":
        return base / "agents" / f"{name}.md"
    if key == "opencode":
        return base / "agents" / f"{name}.md"
    return base / "config" / "agents" / name / "agent.md"


def available(key: str, which: Callable[[str], str | None] = shutil.which) -> bool:
    """Whether the harness binary is on PATH."""
    return which(_BINARY[_key(key)]) is not None
