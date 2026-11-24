"""Eval runner: runs an evaluated skill's cases with and without it, grades them, and keeps the ledger.

Design: docs/designs/chanchi-agents-mvp.md (Layer 2); decisions D1-D23 of
docs/superpowers/plans/2026-11-23-chanchi-agents-phase2.md; runner contract: README.md, section Evals.
Standard library only; imports chanchi for the agent renderer, frontmatter parser, and the agy model split.

    run_evals.py <item> [--arm auto|with|without|both] [--cases a,b] [--runs 1]
                        [--triggers|--no-triggers] [--timeout 300] [--yes] [--dry-run] [--no-ledger]
                        [--hypothesis TEXT] [--change REF]
    run_evals.py <item> --calibration-sheet [--samples 6] [--collect] | --calibrate SHEET | --rejudge
    run_evals.py --signal

Never run in the gate; the orchestrator runs it against real harnesses (the budget is counted there).
"""

from __future__ import annotations

import argparse
import base64
import csv
import dataclasses
import functools
import getpass
import hashlib
import json
import os
import re
import shlex
import shutil
import sqlite3
import stat
import statistics
import subprocess
import sys
import tempfile
import tomllib
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from chanchi import agents_sync, errors, harnesses, items

LEDGER_COLUMNS = (
    "id",
    "date",
    "item",
    "item_sha",
    "hypothesis",
    "change",
    "arm",
    "candidate",
    "runs",
    "median_pass",
    "before",
    "after",
    "delta",
    "verdict",
    "note",
)


def _blob_digest(path: Path) -> tuple[bytes, bytes]:
    """Return (git_mode_bytes, sha1_digest_bytes) for a file or symlink."""
    if path.is_symlink():
        data = os.readlink(path).encode("utf-8")
        mode = b"120000"
    else:
        data = path.read_bytes()
        mode = b"100755" if (path.stat().st_mode & stat.S_IXUSR) else b"100644"
    header = f"blob {len(data)}\0".encode("utf-8")
    return mode, hashlib.sha1(header + data).digest()


def _tracked_files(directory: Path) -> list[Path]:
    """Files under `directory` that git tracks or has staged (the index), as absolute paths."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=directory, env=env,
                          check=True, capture_output=True, text=True).stdout.strip()
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--", str(directory.resolve())],
                         cwd=root, env=env, check=True, capture_output=True).stdout
    files = [Path(root) / name for name in out.decode("utf-8").split("\0") if name]
    return [f for f in files if f.exists() or f.is_symlink()]


def _tree_digest(directory: Path, files: list[Path]) -> bytes | None:
    """Return the raw 20-byte git tree digest of `files` below `directory`, or None if empty."""
    entries: list[tuple[bytes, bytes, str, bytes]] = []
    children: dict[str, list[Path]] = {}
    for f in files:
        rel = f.relative_to(directory)
        children.setdefault(rel.parts[0], []).append(f)
    for name, group in children.items():
        child = directory / name
        if len(group) == 1 and group[0] == child:
            mode, digest = _blob_digest(child)
            entries.append((name.encode("utf-8"), mode, name, digest))
        else:
            sub_digest = _tree_digest(child, group)
            if sub_digest is not None:
                entries.append(((name + "/").encode("utf-8"), b"40000", name, sub_digest))
    if not entries:
        return None
    entries.sort(key=lambda item: item[0])
    body = b"".join(
        mode + b" " + name.encode("utf-8") + b"\0" + digest for _, mode, name, digest in entries
    )
    header = f"tree {len(body)}\0".encode("utf-8")
    return hashlib.sha1(header + body).digest()


def tree_hash(path: Path) -> str:
    """Git's tree SHA-1 of a directory as the index lists it (tracked plus staged files, D10), hashed
    from their working-tree content; untracked and ignored files never count."""
    directory = Path(path).resolve()
    digest = _tree_digest(directory, _tracked_files(directory))
    if digest is None:
        return hashlib.sha1(b"tree 0\0").hexdigest()
    return digest.hex()


def read_ledger(path: Path) -> list[dict[str, str]]:
    """Read rows from evals/ledger.tsv as a list of dicts keyed by column name."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


# ===================================================================================================
# S3: the runner
# ===================================================================================================

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_RUNS_WITHOUT_YES = 30
NEUTRAL_AGENT = "worker"
JUDGE_AGENT = "agent-chanchi-judge"
CLAUDE_TOOLS = "Bash Read Grep Glob Edit Write Skill"
CLAUDE_JUDGE_TOOLS = "Bash Read Grep Glob"
BLINDED_WORDS = ("eval", "test", "judge", "experiment", "rubric", "score", "compare", "benchmark", "candidate",
                 "arena")
BLINDED_RE = re.compile(r"\b(?:" + "|".join(BLINDED_WORDS) + r")[a-z0-9]*", re.IGNORECASE)
LESSON_CHECK_KINDS = ("tool", "hook", "permission")
KEYCHAIN_ITEMS = {
    "claude": 'the macOS keychain item "Claude Code-credentials" (generic password, account $USER)',
    "agy": 'the macOS keychain item with service "gemini" and account "antigravity" '
           "(or the file ~/.gemini/antigravity-cli/antigravity-oauth-token)",
}
CREDENTIAL_TARGETS = {
    "claude": Path(".claude") / ".credentials.json",
    "agy": Path(".gemini") / "antigravity-cli" / "antigravity-oauth-token",
}
PRELOAD_NOTES = {
    "claude": "claude: no preload, discovery",
    "agy": "agy: preloadSkills in the with-skill arm (leaves no load event)",
}


class RunnerError(Exception):
    """A refusal or failure the operator must read; main() prints it and exits 2."""


# --------------------------------------------------------------------------------------- eval layout


@dataclasses.dataclass
class EvalConfig:
    dir: Path
    name: str
    item: str
    candidate: dict
    judge: dict | None
    regression: list[str]
    capability: list[str]
    blind_allow: list[str]
    signal: bool = False

    @property
    def cases(self) -> list[str]:
        return [*self.regression, *self.capability]

    def kind(self, case: str) -> str:
        return "regression" if case in self.regression else "capability"

    @property
    def candidate_spec(self) -> str:
        c = self.candidate
        return f"{c['harness']}:{c['model']}:{c['effort']}"


def load_eval(repo: Path, item: str) -> EvalConfig:
    evals_root = repo / "evals"
    for toml_path in sorted(evals_root.glob("eval-*/eval.toml")):
        cfg = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        if item in (cfg.get("item"), cfg.get("name")):
            judge = cfg.get("judge") if (toml_path.parent / "rubric.md").is_file() else None
            if "signal" in cfg:
                if not isinstance(cfg["signal"], bool):
                    raise RunnerError(f"{toml_path}: 'signal' must be a boolean (true or false)")
                signal = cfg["signal"]
            else:
                signal = judge is not None
            return EvalConfig(toml_path.parent, cfg["name"], cfg["item"], cfg["candidate"], judge,
                              list(cfg.get("regression", [])), list(cfg.get("capability", [])),
                              list(cfg.get("blind_allow", [])), signal=signal)
    raise RunnerError(f"no eval for item {item!r} under {evals_root}. Create evals/eval-chanchi-<name>/ "
                      "(skill-chanchi-item-authoring).")


def all_evals(repo: Path) -> list[EvalConfig]:
    out = []
    for toml_path in sorted((repo / "evals").glob("eval-*/eval.toml")):
        cfg = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        out.append(load_eval(repo, cfg["name"]))
    return out


def parse_rubric_criteria(text: str) -> list[str]:
    """The rubric's numbered criteria (with their indented continuation lines), nothing else."""
    criteria: list[list[str]] = []
    open_item = False
    for line in text.splitlines():
        if re.match(r"^\d+\.\s", line):
            criteria.append([line.rstrip()])
            open_item = True
        elif open_item and line.startswith((" ", "\t")) and line.strip():
            criteria[-1].append(line.rstrip())
        elif line.strip():
            open_item = False
    return ["\n".join(lines) for lines in criteria]


def parse_trigger_prompts(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"load": [], "skip": []}
    current = None
    for line in text.splitlines():
        heading = line.strip().lower()
        if heading == "## must load":
            current = "load"
        elif heading == "## must not load":
            current = "skip"
        elif line.startswith("## "):
            current = None
        elif current and line.startswith("- "):
            out[current].append(line[2:].strip())
    return out


def _canonical_sha(payload: object) -> str:
    """First 12 hex characters of SHA-256 over canonical JSON (D9)."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def cases_sha(repo: Path, cfg: EvalConfig) -> str:
    """Frozen capability harness hash (D9): candidate, judge, agent source, sorted capability files, and rubric."""
    agent_path = repo / "agents" / cfg.candidate["agent"] / "AGENT.md"
    if not agent_path.is_file():
        raise RunnerError(f"candidate agent {cfg.candidate['agent']!r} has no source under agents/")
    capability = sorted(cfg.capability)
    capability_files: list[list[str]] = []
    for case in capability:
        case_dir = cfg.dir / "cases" / case
        if not case_dir.is_dir():
            continue
        for path in sorted(case_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(cfg.dir)
            if "__pycache__" in rel.parts or path.name.endswith(".pyc") or path.name == ".DS_Store":
                continue
            capability_files.append([rel.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()])
    capability_files.sort(key=lambda pair: pair[0])
    rubric_path = cfg.dir / "rubric.md"
    rubric_sha256 = hashlib.sha256(rubric_path.read_bytes()).hexdigest() if rubric_path.is_file() else None
    return _canonical_sha({
        "candidate": cfg.candidate,
        "judge": cfg.judge,
        "agent_sha256": hashlib.sha256(agent_path.read_bytes()).hexdigest(),
        "capability": capability,
        "capability_files": capability_files,
        "rubric_sha256": rubric_sha256,
    })


def triggers_sha(repo: Path, cfg: EvalConfig) -> str:
    """Frozen trigger hash (D9): candidate spec, SKILL.md frontmatter description, and triggers.md."""
    skill_path = repo / "skills" / cfg.item / "SKILL.md"
    try:
        fm = items.read_frontmatter(skill_path.read_text(encoding="utf-8")) if skill_path.is_file() else {}
    except errors.ChanchiError as exc:
        raise RunnerError(f"skills/{cfg.item}/SKILL.md: {exc}") from exc
    description = str(fm.get("description") or "")
    triggers_path = cfg.dir / "triggers.md"
    return _canonical_sha({
        "candidate": {
            "harness": cfg.candidate["harness"],
            "model": cfg.candidate["model"],
            "effort": cfg.candidate["effort"],
        },
        "description": description,
        "triggers_sha256": hashlib.sha256(triggers_path.read_bytes()).hexdigest(),
    })


# --------------------------------------------------------------------------------------- planning


def plan_runs(cfg: EvalConfig, arm: str, cases: list[str] | None, runs: int, *, resolved_arms: list[str],
              triggers: int, full: bool) -> dict:
    """D5: capability cases in both arms, regression only in `with`; gated judge only on capability runs."""
    chosen = cfg.cases if cases is None else cases
    unknown = [c for c in chosen if c not in cfg.cases]
    if unknown:
        raise RunnerError(f"unknown case(s) {unknown}; the eval has {cfg.cases}")
    with_cases = [c for c in chosen if "with" in resolved_arms]
    without_cases = [c for c in chosen if "without" in resolved_arms and cfg.kind(c) == "capability"]
    with_cap_cases = [c for c in with_cases if cfg.kind(c) == "capability"]
    candidate = (len(with_cases) + len(without_cases)) * runs
    judge = ((len(with_cap_cases) + len(without_cases)) * runs) if cfg.judge else 0
    total = candidate + judge + triggers
    if full and "with" in resolved_arms and runs < 3:
        extra_cand = len(with_cases) * (3 - runs)
        extra_judge = (len(with_cap_cases) * (3 - runs)) if cfg.judge else 0
        max_total = total + extra_cand + extra_judge
    else:
        max_total = total
    return {"item": cfg.item, "arm": arm, "resolved_arms": resolved_arms, "cases": chosen, "runs": runs,
            "candidate": candidate, "judge": judge, "trigger": triggers, "total": total, "max_total": max_total,
            "ledger": "write" if full else "none"}


# --------------------------------------------------------------------------------------- credentials


def _keychain(service: str, account: str) -> bytes | None:
    if sys.platform != "darwin" or shutil.which("security") is None:
        return None
    result = subprocess.run(["security", "find-generic-password", "-s", service, "-a", account, "-w"],
                            capture_output=True, check=False)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def default_credential_source(harness: str) -> bytes | None:
    """The credential of a harness: CHANCHI_EVALS_CREDENTIALS_DIR/<harness> when set (tests; the keychain is
    never read then), else the macOS keychain item or the credential file the harness itself falls back to."""
    override = os.environ.get("CHANCHI_EVALS_CREDENTIALS_DIR")
    if override:
        path = Path(override) / harness
        return path.read_bytes() if path.is_file() else None
    if harness == "claude":
        value = _keychain("Claude Code-credentials", os.environ.get("USER") or getpass.getuser())
        if value is not None:
            return value
        path = Path.home() / ".claude" / ".credentials.json"
        return path.read_bytes() if path.is_file() else None
    if harness == "agy":
        path = Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
        if path.is_file():
            return path.read_bytes()
        return _keychain("gemini", "antigravity")
    return None


def read_credential(harness: str, source: Callable[[str], bytes | None] | None = None) -> bytes:
    """The credential bytes to put in a temporary HOME; `source` is injectable so tests never touch the keychain."""
    if harness not in CREDENTIAL_TARGETS:
        raise RunnerError(f"harness {harness!r} is not supported by the runner (claude and agy are)")
    raw = (source or default_credential_source)(harness)
    if not raw:
        raise RunnerError(f"cannot run {harness} under a temporary HOME: no credential found in "
                          f"{KEYCHAIN_ITEMS[harness]}. Sign in to {harness} first.")
    if harness == "agy" and raw.startswith(b"go-keyring-base64:"):
        raw = base64.b64decode(raw[len(b"go-keyring-base64:"):])
    return raw


def build_home(harness: str, home: Path, source: Callable[[str], bytes | None] | None = None) -> None:
    """A temporary HOME holding only the harness credential (mode 600): the global skill folders are not in it."""
    data = read_credential(harness, source)
    target = home / CREDENTIAL_TARGETS[harness]
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    target.chmod(0o600)


# --------------------------------------------------------------------------------------- harness launch


def split_model(harness: str, model: str, effort: str | None) -> str:
    return harnesses.split_agy_model(model, effort) if harness == "agy" else model


def build_argv(harness: str, *, agent: str | None, model: str, effort: str, prompt: str, tools: str,
               add_dirs: Sequence[str] = ()) -> list[str]:
    """The headless launch line as an argument list (S1-verified forms; stdin is /dev/null at launch)."""
    if harness == "claude":
        argv = ["claude", "-p"]
        if agent:
            argv += ["--agent", agent]
        argv += ["--model", model, "--effort", effort, "--permission-mode", "acceptEdits", "--allowedTools", tools]
        for directory in add_dirs:
            argv += ["--add-dir", str(directory)]
        return [*argv, "--output-format", "stream-json", "--verbose", "--", prompt]
    if harness == "agy":
        argv = ["agy"]
        if agent:
            argv += ["--agent", agent]
        argv += ["--model", split_model("agy", model, effort), "--effort", effort, "--dangerously-skip-permissions"]
        for directory in add_dirs:
            argv += ["--add-dir", str(directory)]
        return [*argv, "--output-format", "stream-json", f"-p={prompt}"]
    raise RunnerError(f"harness {harness!r} is not supported by the runner (claude and agy are)")


@dataclasses.dataclass
class HarnessResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def launch(argv: list[str], cwd: Path, env: dict[str, str], timeout: int) -> HarnessResult:
    binary = shutil.which(argv[0], path=env["PATH"])
    if binary is None:
        raise RunnerError(f"harness {argv[0]!r} not found on PATH")
    try:
        done = subprocess.run([binary, *argv[1:]], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return HarnessResult(-1, out, err, timed_out=True)
    return HarnessResult(done.returncode, done.stdout, done.stderr)


# --------------------------------------------------------------------------------------- stream-json


def parse_events(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def final_message(harness: str, events: list[dict]) -> tuple[str, str | None]:
    """(text, error): claude's last `result` event, agy's last `result` event's `result.response` (S1)."""
    if harness == "claude":
        results = [e for e in events if e.get("type") == "result"]
        if not results:
            return "", "no result event in the stream"
        last = results[-1]
        text = last.get("result") if isinstance(last.get("result"), str) else ""
        return text, ("the harness reported an error" if last.get("is_error") else None)
    results = [e for e in events if e.get("event") == "result"]
    if not results:
        return "", "no result event in the stream"
    body = results[-1].get("result") or {}
    text = body.get("response") if isinstance(body.get("response"), str) else ""
    if body.get("status") == "ERROR":
        return text, f"the harness reported an error: {body.get('error', '')}".rstrip(": ")
    return text, None


def _skill_read_path(path: object, item: str) -> bool:
    return isinstance(path, str) and path.endswith(f"/{item}/SKILL.md")


def _claude_load_blocks(event: dict, item: str) -> list[dict]:
    """The `tool_use` blocks of an assistant event that load the item (Skill tool or a read of its SKILL.md)."""
    if event.get("type") != "assistant":
        return []
    hits = []
    for block in (event.get("message") or {}).get("content") or []:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        data = block.get("input") or {}
        if (block.get("name") == "Skill" and data.get("skill") == item) or (
                block.get("name") == "Read" and _skill_read_path(data.get("file_path"), item)):
            hits.append(block)
    return hits


def _agy_load_step(event: dict, item: str) -> int | None:
    step = event.get("step_update") if event.get("event") == "step_update" else None
    if not isinstance(step, dict):
        return None
    params = ((step.get("tool_info") or {}).get("parameters")) or {}
    if step.get("step_type") == "tool" and step.get("tool_name") == "read_file" and _skill_read_path(
            params.get("Path"), item):
        return step.get("step_index")
    return None


def load_event_found(harness: str, events: list[dict], item: str) -> bool:
    if harness == "claude":
        return any(_claude_load_blocks(e, item) for e in events)
    return any(_agy_load_step(e, item) is not None for e in events)


def strip_load_events(harness: str, events: list[dict], item: str) -> list[dict]:
    """The transcript copy the judge reads (D14): the skill-load events (S1) removed so the arm stays hidden.
    claude: the load `tool_use` (the rest of its event stays), its `tool_result`, and the synthetic `user`
    event with the skill text that follows it; the skill name is also taken out of the init event's `skills`."""
    if harness == "agy":
        indexes = {i for i in (_agy_load_step(e, item) for e in events) if i is not None}
        return [e for e in events
                if not (e.get("event") == "step_update" and (e.get("step_update") or {}).get("step_index") in indexes)]
    removed: set[str] = set()
    out: list[dict] = []
    drop_synthetic = False
    for event in events:
        hits = _claude_load_blocks(event, item)
        if hits:
            removed.update(b.get("id") for b in hits)
            drop_synthetic = True
            blocks = [b for b in event["message"]["content"] if b not in hits]
            if blocks:
                out.append({**event, "message": {**event["message"], "content": blocks}})
            continue
        if event.get("type") == "user":
            content = (event.get("message") or {}).get("content")
            blocks = content if isinstance(content, list) else []
            if any(isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in removed
                   for b in blocks):
                continue
            if drop_synthetic and event.get("isSynthetic"):
                drop_synthetic = False
                continue
        if event.get("type") == "system" and event.get("subtype") == "init" and isinstance(event.get("skills"), list):
            event = {**event, "skills": [s for s in event["skills"] if s != item]}
        out.append(event)
    return out


REDACTED = "[skill]"


def redact_item(events: list[dict], text: str, item: str) -> tuple[list[dict], str]:
    """Replace every mention of the evaluated skill's name (and so its folder path) with a neutral token in the
    judge's and the owner's copies, in both arms: a candidate that reads a skill file with a shell command, or names
    the skill in its answer, would otherwise reveal the arm (D14). The saved candidate transcript stays complete."""
    return ([json.loads(json.dumps(e).replace(item, REDACTED)) for e in events], text.replace(item, REDACTED))


def tool_call_lines(harness: str, events: list[dict], limit: int = 60) -> list[str]:
    """One line per tool call, for the calibration sheet's excerpt."""
    lines: list[str] = []
    seen: set = set()
    for event in events:
        if harness == "claude" and event.get("type") == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    lines.append(f"{block.get('name')}: {json.dumps(block.get('input'), ensure_ascii=False)[:200]}")
        elif harness == "agy" and event.get("event") == "step_update":
            step = event["step_update"]
            if step.get("step_type") == "tool" and step.get("step_index") not in seen:
                seen.add(step.get("step_index"))
                params = (step.get("tool_info") or {}).get("parameters")
                lines.append(f"{step.get('tool_name')}: {json.dumps(params, ensure_ascii=False)[:200]}")
    return lines[:limit]


# --------------------------------------------------------------------------------------- grading and scores


def parse_grade_output(stdout: str) -> list[dict]:
    rows = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "criterion" in value and "pass" in value:
            rows.append({"criterion": str(value["criterion"]), "pass": bool(value["pass"]),
                         "detail": str(value.get("detail", ""))})
    return rows


JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.DOTALL)
VERDICTS = ("PASS", "FAIL", "N/A")


def parse_judge_answer(text: str, count: int) -> list[dict] | None:
    """The last fenced json block's criteria, or None when it is missing, malformed or misses a criterion."""
    blocks = JSON_BLOCK.findall(text or "")
    if not blocks:
        return None
    try:
        data = json.loads(blocks[-1])
        entries = data["criteria"]
        parsed = {}
        for entry in entries:
            n = int(entry["n"])
            verdict = str(entry["verdict"]).strip().upper()
            if verdict not in VERDICTS:
                return None
            parsed[n] = {"n": n, "verdict": verdict, "critique": str(entry.get("critique", ""))}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if set(parsed) != set(range(1, count + 1)):
        return None
    return [parsed[n] for n in sorted(parsed)]


def score_run(code: list[dict], judge: list[dict] | None) -> float:
    """Passed criteria over applicable ones (code and judge; N/A excluded); 0.0 when none applies."""
    applicable = [bool(c["pass"]) for c in code]
    applicable += [v["verdict"] == "PASS" for v in (judge or []) if v["verdict"] != "N/A"]
    return sum(applicable) / len(applicable) if applicable else 0.0


def run_passed(code: list[dict], judge: list[dict] | None) -> bool:
    flags = [bool(c["pass"]) for c in code]
    flags += [v["verdict"] == "PASS" for v in (judge or []) if v["verdict"] != "N/A"]
    return bool(flags) and all(flags)


def gated_code_failed_score(code: list[dict], rubric_count: int) -> float:
    """D7: score when a code criterion fails on a capability run; strictly less than any code-passed run."""
    denom = len(code) + rubric_count
    return (sum(1 for c in code if c["pass"]) / denom) if denom else 0.0


def judge_label(result: dict) -> str | None:
    """The judge's rubric-only verdict (code criteria excluded); None when every criterion was N/A or failed."""
    judge = result.get("judge")
    if not judge or result.get("judge_error"):
        return None
    applicable = [v for v in judge if v["verdict"] != "N/A"]
    if not applicable:
        return None
    return "PASS" if all(v["verdict"] == "PASS" for v in applicable) else "FAIL"


# --------------------------------------------------------------------------------------- run context


@dataclasses.dataclass
class Context:
    repo: Path
    artifacts: Path
    timeout: int = 300
    credential_source: Callable[[str], bytes | None] | None = None
    log: Callable[[str], None] = lambda message: print(message, file=sys.stderr)


def artifacts_root() -> Path:
    base = os.environ.get("CHANCHI_EVALS_DIR")
    return Path(base) if base else Path.home() / ".local" / "share" / "chanchi" / "evals"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@functools.lru_cache(maxsize=1)
def uv_cache_dir() -> str | None:
    if os.environ.get("UV_CACHE_DIR"):
        return os.environ["UV_CACHE_DIR"]
    uv = shutil.which("uv")
    if uv is None:
        return None
    done = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True, check=False)
    return done.stdout.strip() or None if done.returncode == 0 else None


def write_shim(folder: Path, repo: Path) -> str:
    """The `chanchi` shim on the candidate's PATH: `uv run --project <repo> chanchi` (D22)."""
    folder.mkdir(parents=True)
    uv = shutil.which("uv") or "uv"
    cache = uv_cache_dir()
    lines = ["#!/bin/sh"]
    if cache:
        lines.append(f"export UV_CACHE_DIR={shlex.quote(cache)}")
    lines.append(f"exec {shlex.quote(uv)} run --project {shlex.quote(str(repo))} chanchi \"$@\"")
    shim = folder / "chanchi"
    shim.write_text("\n".join(lines) + "\n", encoding="utf-8")
    shim.chmod(0o755)
    return f"uv run --project {repo} chanchi"


def base_env(home: Path, shim_dir: Path | None, db: Path | None, sync: Path | None) -> dict[str, str]:
    """A clean environment (S1): PATH, HOME, TERM and the D22 variables; nothing from CLAUDE_CODE*."""
    path = os.environ.get("PATH", "/usr/bin:/bin")
    env = {"PATH": f"{shim_dir}{os.pathsep}{path}" if shim_dir else path, "HOME": str(home), "TERM": "dumb"}
    if db is not None:
        env["CHANCHI_DB"] = str(db)
    if sync is not None:
        env["CHANCHI_SYNC"] = str(sync)
    return env


def check_blinded_paths(work: Path, skip: Sequence[Path], allow: Sequence[str]) -> None:
    """D6, at run time: no file name under `work` carries a blinded word unless the eval allows it. The injected
    wrapper and skill (the subject), `.git` and `.state` are exempt."""
    allowed = {w.lower() for w in allow}
    skip_paths = [p.resolve() for p in skip]
    for path in sorted(work.rglob("*")):
        resolved = path.resolve()
        rel = path.relative_to(work)
        if rel.parts[0] in (".git", ".state") or any(resolved == s or s in resolved.parents for s in skip_paths):
            continue
        bad = [m.group(0) for m in BLINDED_RE.finditer(rel.name) if m.group(0).lower() not in allowed]
        if bad:
            raise RunnerError(f"blinded word {bad} in the work directory path {rel}. The candidate must not see "
                              "it: reword the case's setup.sh or list the word in blind_allow in eval.toml.")


def exclude_paths(work: Path, paths: Sequence[str]) -> None:
    info = work / ".git" / "info"
    if not (work / ".git").is_dir():
        return
    info.mkdir(parents=True, exist_ok=True)
    exclude = info / "exclude"
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    extra = "".join(f"/{p}\n" for p in paths)
    exclude.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n") + extra, encoding="utf-8")


def candidate_wrapper(repo: Path, cfg: EvalConfig, with_skill: bool) -> tuple[str, str]:
    """D3: the candidate's wrapper rendered under the neutral name `worker`, scope both, `skills:` set per arm."""
    harness = cfg.candidate["harness"]
    sources = {s.name: s for s in agents_sync.load_sources(repo / "agents")}
    name = cfg.candidate["agent"]
    if name not in sources:
        raise RunnerError(f"candidate agent {name!r} has no source under agents/")
    source = dataclasses.replace(sources[name], name=NEUTRAL_AGENT, scope="both",
                                 skills=[cfg.item] if with_skill else [])
    rendered = agents_sync.render(source)
    rel = agents_sync.REPO_TARGETS[harness](NEUTRAL_AGENT)
    return rel, rendered[rel]


def skill_dir_for(harness: str) -> str:
    return ".claude/skills" if harness == "claude" else ".agents/skills"


def inject(work: Path, repo: Path, cfg: EvalConfig, *, with_skill: bool, wrapper: bool) -> list[str]:
    """Write the wrapper and (with-skill arm) the skill into `work`; return the injected top-level paths."""
    injected = []
    harness = cfg.candidate["harness"]
    if wrapper:
        rel, text = candidate_wrapper(repo, cfg, with_skill)
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        injected.append(rel)
    if with_skill:
        rel = f"{skill_dir_for(harness)}/{cfg.item}"
        shutil.copytree(repo / "skills" / cfg.item, work / rel, symlinks=True)
        injected.append(rel)
    return injected


def run_script(command: list[str], cwd: Path, env: dict[str, str], what: str) -> subprocess.CompletedProcess:
    done = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          check=False)
    if done.returncode != 0:
        raise RunnerError(f"{what} failed (exit {done.returncode}): {(done.stderr or done.stdout).strip()[-800:]}")
    return done


GIT_IDENTITY = {"GIT_AUTHOR_NAME": "case", "GIT_AUTHOR_EMAIL": "case@example.invalid",
                "GIT_COMMITTER_NAME": "case", "GIT_COMMITTER_EMAIL": "case@example.invalid"}


def end_state(work: Path, hidden: Sequence[str] = ()) -> str:
    """Files, changes and the scratch database as the grader and the judge see them (never the injected paths)."""
    lines: list[str] = []
    skip = tuple(hidden) + (".state",)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if (work / ".git").is_dir():
        status = subprocess.run(["git", "status", "--porcelain"], cwd=work, env=env, capture_output=True,
                                text=True, check=False).stdout
        listing = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=work,
                                 env=env, capture_output=True, text=True, check=False).stdout.splitlines()
        changed = [ln[3:].strip().strip('"') for ln in status.splitlines() if ln.strip()]
        lines += ["git status --porcelain:", status.rstrip() or "(clean)", "", "Files:"] + [f"- {p}" for p in listing]
    else:
        listing = sorted(str(p.relative_to(work)) for p in work.rglob("*")
                         if p.is_file() and not str(p.relative_to(work)).startswith(skip))
        changed = listing
        lines += ["Files:"] + [f"- {p}" for p in listing]
    shown = 0
    for rel in changed:
        path = work / rel
        if path.is_file() and not rel.startswith(skip) and shown < 20:
            try:
                body = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            lines += ["", f"File {rel}:", body[:4000].rstrip()]
            shown += 1
    db = work / ".state" / "chanchi.db"
    if db.is_file():
        lines += ["", "Scratch database:"]
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "AND name NOT LIKE '%migration%' ORDER BY name")]
                for table in tables:
                    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
                    rows = conn.execute(f'SELECT * FROM "{table}" LIMIT 50').fetchall()
                    if rows:
                        lines.append(f"{table}:")
                        lines += ["  " + json.dumps(dict(zip(cols, (str(v)[:300] for v in row))), ensure_ascii=False)
                                  for row in rows]
        except sqlite3.Error as exc:
            lines.append(f"(unreadable: {exc})")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------------------- judge


def run_judge(ctx: Context, cfg: EvalConfig, criteria: list[str], output_md: str, transcript: list[dict],
              base: Path) -> tuple[list[dict], str | None]:
    """One run's judge verdicts. An unparsable answer (or a failed harness run) is retried once; a second
    failure counts every criterion as FAIL and returns the reason (D7)."""
    judge = cfg.judge
    assert judge is not None
    harness = judge["harness"]
    sources = {s.name: s for s in agents_sync.load_sources(ctx.repo / "agents")}
    if JUDGE_AGENT not in sources:
        raise RunnerError(f"judge agent {JUDGE_AGENT!r} has no source under agents/")
    rel = agents_sync.REPO_TARGETS[harness](JUDGE_AGENT)
    wrapper_text = agents_sync.render(sources[JUDGE_AGENT])[rel]
    prompt = "Read criteria.md, output.md and transcript.jsonl in this directory and give your verdict."
    reason = "no answer"
    for attempt in (1, 2):
        tag = uuid.uuid4().hex[:8]
        work = base / f"judge-{tag}"
        home = base / f"home-{tag}"
        work.mkdir(parents=True)
        (work / "criteria.md").write_text("# Criteria\n\n" + "\n".join(criteria) + "\n", encoding="utf-8")
        (work / "output.md").write_text(output_md, encoding="utf-8")
        (work / "transcript.jsonl").write_text("".join(json.dumps(e) + "\n" for e in transcript), encoding="utf-8")
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(wrapper_text, encoding="utf-8")
        try:
            build_home(harness, home, ctx.credential_source)
            argv = build_argv(harness, agent=JUDGE_AGENT, model=judge["model"], effort=judge["effort"],
                              prompt=prompt, tools=CLAUDE_JUDGE_TOOLS)
            result = launch(argv, work, base_env(home, None, None, None), ctx.timeout)
        finally:
            shutil.rmtree(home, ignore_errors=True)
        events = parse_events(result.stdout)
        text, error = final_message(harness, events)
        if result.timed_out:
            error = "the judge timed out"
        elif result.exit_code != 0 and not error:
            error = f"the judge exited {result.exit_code}"
        parsed = None if error else parse_judge_answer(text, len(criteria))
        if parsed is not None:
            return parsed, None
        reason = error or "the judge answer had no valid json block covering every criterion"
        ctx.log(f"judge attempt {attempt} unusable: {reason}")
    failed = [{"n": i, "verdict": "FAIL", "critique": f"judge unusable: {reason}"} for i in range(1, len(criteria) + 1)]
    return failed, reason


# --------------------------------------------------------------------------------------- one run


def new_run_id(arm: str, case: str, n: int) -> str:
    return f"{utc_now():%Y%m%dT%H%M%S%f}-{arm}-{case}-{n}-{uuid.uuid4().hex[:6]}"


def save_tree(source: Path, dest: Path) -> None:
    if source.exists():
        shutil.copytree(source, dest, symlinks=True, ignore_dangling_symlinks=True, dirs_exist_ok=True)


def execute_case_run(ctx: Context, cfg: EvalConfig, *, arm: str, case: str, n: int, measurement: str,
                     item_sha: str, c_sha: str = "", force_judge: bool = False,
                     artifacts_subdir: str | None = None) -> dict:
    """One candidate run of a case: setup, candidate, grader, gated judge. Returns the saved result record."""
    harness = cfg.candidate["harness"]
    with_skill = arm == "with"
    case_dir = cfg.dir / "cases" / case
    run_id = new_run_id(arm, case, n)
    item_root = ctx.artifacts / cfg.item
    run_dir = (item_root / artifacts_subdir / run_id) if artifacts_subdir else (item_root / run_id)
    run_dir.mkdir(parents=True)
    base = Path(tempfile.mkdtemp(prefix="run-"))
    tag = uuid.uuid4().hex[:8]
    work, sync, home = base / f"work-{tag}", base / f"sync-{tag}", base / f"home-{tag}"
    final_file = base / f"final-{tag}.txt"
    try:
        work.mkdir()
        sync.mkdir()
        (work / ".state").mkdir()
        shim = write_shim(base / f"bin-{tag}", ctx.repo)
        env = base_env(home, base / f"bin-{tag}", work / ".state" / "chanchi.db", sync)
        home.mkdir()
        run_script(["bash", str(case_dir / "setup.sh")], work, {**env, **GIT_IDENTITY}, f"setup.sh of case {case}")
        injected = inject(work, ctx.repo, cfg, with_skill=with_skill, wrapper=True)
        exclude_paths(work, [".state/", *injected])
        check_blinded_paths(work, [work / p for p in injected], cfg.blind_allow)

        prompt = (case_dir / "prompt.md").read_text(encoding="utf-8").strip()
        argv = build_argv(harness, agent=NEUTRAL_AGENT, model=cfg.candidate["model"],
                          effort=cfg.candidate["effort"], prompt=prompt, tools=CLAUDE_TOOLS, add_dirs=[str(sync)])
        build_home(harness, home, ctx.credential_source)
        try:
            result = launch(argv, work, env, ctx.timeout)
        finally:
            shutil.rmtree(home, ignore_errors=True)
        (run_dir / "transcript.jsonl").write_text(result.stdout, encoding="utf-8")
        (run_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        events = parse_events(result.stdout)
        text, error = final_message(harness, events)
        if result.timed_out:
            error = f"timed out after {ctx.timeout}s"
        elif result.exit_code != 0 and not error:
            error = f"exit code {result.exit_code}"
        final_file.write_text(text, encoding="utf-8")
        (run_dir / "final_message.txt").write_text(text, encoding="utf-8")
        if error:
            raise RunnerError(f"candidate run failed ({error}); artifacts: {run_dir}")

        grade = run_script([sys.executable, "-I", str(case_dir / "grade.py"), str(work)], work,
                           {**env, "FINAL_MESSAGE_FILE": str(final_file)}, f"grade.py of case {case}")
        code = parse_grade_output(grade.stdout)
        if not code:
            raise RunnerError(f"grade.py of case {case} printed no criterion line; artifacts: {run_dir}")
        state = end_state(work, injected)
        (run_dir / "end_state.md").write_text(state, encoding="utf-8")
        stripped, shown_text = redact_item(strip_load_events(harness, events, cfg.item),
                                           f"# Final message\n\n{text}\n\n# End state\n\n{state}", cfg.item)
        output_md = shown_text
        (run_dir / "output.md").write_text(output_md, encoding="utf-8")
        (run_dir / "judge-transcript.jsonl").write_text("".join(json.dumps(e) + "\n" for e in stripped),
                                                        encoding="utf-8")
        judge_list, judge_error, judge_skipped = None, None, None
        kind = cfg.kind(case)
        if kind == "capability" and cfg.judge:
            criteria = parse_rubric_criteria((cfg.dir / "rubric.md").read_text(encoding="utf-8"))
            if all(c["pass"] for c in code) or force_judge:
                judge_list, judge_error = run_judge(ctx, cfg, criteria, output_md, stripped, base)
                score = score_run(code, judge_list)
                passed = run_passed(code, judge_list)
            else:
                judge_skipped = "code_failed"
                score = gated_code_failed_score(code, len(criteria))
                passed = False
        else:
            score = score_run(code, None)
            passed = run_passed(code, None)
        record = {
            "run_id": run_id, "measurement": measurement, "arm": arm, "case": case, "kind": kind, "n": n,
            "item_sha": item_sha, "cases_sha": c_sha, "code": code, "judge": judge_list, "judge_error": judge_error,
            "judge_skipped": judge_skipped, "score": score, "passed": passed,
            "note": PRELOAD_NOTES[harness] if with_skill else "", "tool_calls": tool_call_lines(harness, stripped),
        }
        (run_dir / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        (run_dir / "meta.json").write_text(json.dumps({
            "run_id": run_id, "arm": arm, "case": case, "n": n, "shim": shim, "argv": argv[:-1] + ["<prompt>"],
            "harness": harness, "skill_preload": PRELOAD_NOTES[harness] if with_skill else None}, indent=2),
            encoding="utf-8")
        return record
    finally:
        shutil.rmtree(home, ignore_errors=True)
        save_tree(work, run_dir / "work")
        save_tree(sync, run_dir / "sync")
        shutil.rmtree(base, ignore_errors=True)


def execute_trigger_run(ctx: Context, cfg: EvalConfig, *, prompt: str, expect_load: bool, index: int,
                        measurement: str) -> dict:
    """One trigger prompt: the skill installed, no agent, the same permission flags (D4, D5)."""
    harness = cfg.candidate["harness"]
    run_id = new_run_id("triggers", f"trigger{index}", 1)
    run_dir = ctx.artifacts / cfg.item / run_id
    run_dir.mkdir(parents=True)
    base = Path(tempfile.mkdtemp(prefix="run-"))
    tag = uuid.uuid4().hex[:8]
    work, home = base / f"work-{tag}", base / f"home-{tag}"
    try:
        work.mkdir()
        home.mkdir()
        inject(work, ctx.repo, cfg, with_skill=True, wrapper=False)
        env = base_env(home, None, None, None)
        argv = build_argv(harness, agent=None, model=cfg.candidate["model"], effort=cfg.candidate["effort"],
                          prompt=prompt, tools=CLAUDE_TOOLS)
        build_home(harness, home, ctx.credential_source)
        try:
            result = launch(argv, work, env, ctx.timeout)
        finally:
            shutil.rmtree(home, ignore_errors=True)
        (run_dir / "transcript.jsonl").write_text(result.stdout, encoding="utf-8")
        events = parse_events(result.stdout)
        _, error = final_message(harness, events)
        if result.timed_out or (result.exit_code != 0 and error):
            raise RunnerError(f"trigger run failed ({error or 'timeout'}); artifacts: {run_dir}")
        loaded = load_event_found(harness, events, cfg.item)
        record = {"run_id": run_id, "measurement": measurement, "arm": "triggers", "prompt": prompt,
                  "expect_load": expect_load, "loaded": loaded, "passed": loaded == expect_load}
        (run_dir / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record
    finally:
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(base, ignore_errors=True)


# --------------------------------------------------------------------------------------- ledger


def fmt(value: float) -> str:
    return f"{round(value + 0.0, 2) + 0.0:.2f}"


def arm_summary(results: list[dict], arm: str) -> dict:
    """D9: per-case medians across capability cases (fallback to all arm cases if none), plus regression counts."""
    mine = [r for r in results if r["arm"] == arm]
    by_case: dict[str, list[dict]] = {}
    for r in mine:
        by_case.setdefault(r["case"], []).append(r)
    cases: dict[str, float] = {}
    cap_medians: list[float] = []
    all_medians: list[float] = []
    for case, cruns in by_case.items():
        if cruns[0]["kind"] == "regression":
            cases[case] = sum(1 for r in cruns if r["passed"]) / len(cruns)
            all_medians.append(statistics.median(r["score"] for r in cruns))
        else:
            med = statistics.median(r["score"] for r in cruns)
            cases[case] = med
            cap_medians.append(med)
            all_medians.append(med)
    pool = cap_medians or all_medians
    regression = [r for r in mine if r["kind"] == "regression"]
    return {
        "median": round(statistics.median(pool), 2) if pool else 0.0,
        "reg_passed": sum(1 for r in regression if r["passed"]),
        "reg_runs": len(regression),
        "runs": len(mine),
        "cases": cases,
    }


def write_ledger(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_rows(path: Path, new_rows: list[dict[str, str]]) -> None:
    write_ledger(path, [*read_ledger(path), *new_rows])


def clean_cell(value: object) -> str:
    return re.sub(r"[\t\r\n]+", " ", str(value)).strip()


def note_tokens(note: str) -> dict[str, str]:
    """Parse semicolon-separated `key=value` tokens from a ledger row's `note` field."""
    out: dict[str, str] = {}
    for part in (note or "").split(";"):
        part = part.strip()
        if "=" in part:
            key, _, val = part.partition("=")
            key = key.strip()
            if key:
                out[key] = val.strip()
    return out


def parse_case_values(token: str) -> dict[str, str]:
    """Parse comma-separated `case:value` pairs from a `cases=` note token."""
    out: dict[str, str] = {}
    for entry in (token or "").split(","):
        entry = entry.strip()
        if ":" in entry:
            case, _, val = entry.partition(":")
            case = case.strip()
            if case:
                out[case] = val.strip()
    return out


def format_with_note(cfg: EvalConfig, summary: dict, c_sha: str) -> str:
    cases_str = ",".join(f"{c}:{fmt(summary['cases'][c])}" for c in cfg.cases if c in summary["cases"])
    return f"regression={summary['reg_passed']}/{summary['reg_runs']};cases_sha={c_sha};cases={cases_str}"


def format_without_note(cfg: EvalConfig, summary: dict, c_sha: str) -> str:
    cases_str = ",".join(f"{c}:{fmt(summary['cases'][c])}" for c in cfg.capability if c in summary["cases"])
    return f"cases_sha={c_sha};cases={cases_str}"


def _matches_harness(row: dict[str, str], *, candidate: str | None = None,
                     cases_sha_val: str | None = None) -> bool:
    if candidate is not None and row.get("candidate") != candidate:
        return False
    if cases_sha_val is not None and note_tokens(row.get("note", "")).get("cases_sha") != cases_sha_val:
        return False
    return True


def current_with_row(rows: list[dict[str, str]], item: str, sha: str, *, candidate: str | None = None,
                     cases_sha: str | None = None) -> dict[str, str] | None:
    """D9: newest baseline or kept `with` row matching item, item_sha, and optional (candidate, cases_sha)."""
    match = [r for r in rows if r["item"] == item and r["arm"] == "with" and r["item_sha"] == sha
             and r["verdict"] in ("baseline", "kept")
             and _matches_harness(r, candidate=candidate, cases_sha_val=cases_sha)]
    return match[-1] if match else None


def baseline_without_row(rows: list[dict[str, str]], item: str, *, candidate: str | None = None,
                         cases_sha: str | None = None) -> dict[str, str] | None:
    match = [r for r in rows if r["item"] == item and r["arm"] == "without" and r["verdict"] == "baseline"
             and _matches_harness(r, candidate=candidate, cases_sha_val=cases_sha)]
    return match[-1] if match else None


def previous_with_row(rows: list[dict[str, str]], item: str, *, candidate: str | None = None,
                      cases_sha: str | None = None) -> dict[str, str] | None:
    match = [r for r in rows if r["item"] == item and r["arm"] == "with" and r["verdict"] in ("baseline", "kept")
             and _matches_harness(r, candidate=candidate, cases_sha_val=cases_sha)]
    return match[-1] if match else None


def matching_triggers_row(rows: list[dict[str, str]], item: str, *, candidate: str,
                          triggers_sha: str) -> dict[str, str] | None:
    match = [r for r in rows if r["item"] == item and r["arm"] == "triggers" and r.get("candidate") == candidate
             and note_tokens(row_note := r.get("note", "")).get("triggers_sha") == triggers_sha
             and row_note is not None]
    return match[-1] if match else None


def regression_counts(note: str) -> tuple[int, int] | None:
    match = re.search(r"regression=(\d+)/(\d+)", note or "")
    return (int(match.group(1)), int(match.group(2))) if match else None


def max_ledger_suffix(rows: list[dict[str, str]], item: str) -> int:
    """Highest numeric `<item>-<N>` suffix among existing ledger rows for `item`."""
    prefix = f"{item}-"
    suffixes = [
        int(row_id[len(prefix):])
        for r in rows
        if r.get("item") == item and (row_id := r.get("id", "")).startswith(prefix) and row_id[len(prefix):].isdigit()
    ]
    return max(suffixes, default=0)


def make_row(item: str, n: int, sha: str, arm: str, candidate: str, runs: int, median: float, *, verdict: str,
             note: str = "", hypothesis: str = "", change: str = "", before: str = "", delta: str = "") -> dict[str, str]:
    return {"id": f"{item}-{n}", "date": f"{utc_now():%Y-%m-%d}", "item": item, "item_sha": sha,
            "hypothesis": clean_cell(hypothesis), "change": clean_cell(change), "arm": arm, "candidate": candidate,
            "runs": str(runs), "median_pass": fmt(median), "before": before, "after": fmt(median), "delta": delta,
            "verdict": verdict, "note": note}


def item_dir_status(repo: Path, item: str) -> list[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    out = subprocess.run(["git", "status", "--porcelain", "--", f"skills/{item}"], cwd=repo, env=env,
                         capture_output=True, text=True, check=False).stdout
    return [ln for ln in out.splitlines() if ln.startswith("??") or (len(ln) > 1 and ln[1] != " ")]


def committed_ledger_ids(repo: Path) -> set[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    done = subprocess.run(["git", "show", "HEAD:evals/ledger.tsv"], cwd=repo, env=env, capture_output=True,
                          text=True, check=False)
    if done.returncode != 0:
        return set()
    return {line.split("\t", 1)[0] for line in done.stdout.splitlines()[1:] if line}


# --------------------------------------------------------------------------------------- measurement


def measurement_files(artifacts: Path, item: str) -> list[Path]:
    return sorted((artifacts / item).glob("measurement-*.json")) if (artifacts / item).is_dir() else []


def latest_baseline(artifacts: Path, item: str) -> dict:
    for path in reversed(measurement_files(artifacts, item)):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("kind") == "baseline" and data.get("rows"):
            data["_path"] = str(path)
            return data
    raise RunnerError(f"no baseline measurement for {item} under {artifacts / item}. Run: "
                      f"uv run python scripts/run_evals.py {item}")


def load_results(artifacts: Path, item: str, run_ids: list[str]) -> list[dict]:
    return [json.loads((artifacts / item / rid / "result.json").read_text(encoding="utf-8")) for rid in run_ids]


def ensure_ready(ctx: Context, cfg: EvalConfig, *, need_candidate: bool, need_judge: bool) -> None:
    """Fail before spending a run: the harness binaries are on PATH and a credential exists for each."""
    needed = []
    if need_candidate:
        needed.append(cfg.candidate["harness"])
    if need_judge and cfg.judge:
        needed.append(cfg.judge["harness"])
    for harness in dict.fromkeys(needed):
        if shutil.which(harness, path=os.environ.get("PATH", "")) is None:
            raise RunnerError(f"harness {harness!r} not found on PATH")
        read_credential(harness, ctx.credential_source)


def _should_repeat_case(cfg: EvalConfig, case: str, case_runs: list[dict],
                        prev_with: dict[str, str] | None) -> bool:
    """D5: adaptive repeat triggers confirming runs up to 3 on failure, prior flakiness, or value change."""
    kind = cfg.kind(case)
    if kind == "regression" and not all(r["passed"] for r in case_runs):
        return True
    if prev_with is None:
        return False
    prev_toks = note_tokens(prev_with.get("note", ""))
    prev_cases = parse_case_values(prev_toks.get("cases", ""))
    if kind == "regression":
        prev_reg = regression_counts(prev_with.get("note", ""))
        if prev_reg is not None and prev_reg[1] > 0 and prev_reg[0] < prev_reg[1]:
            return True
        if case in prev_cases and float(prev_cases[case]) < 1.0:
            return True
        init_val = sum(1 for r in case_runs if r["passed"]) / len(case_runs)
    else:
        init_val = statistics.median(r["score"] for r in case_runs)
    return case in prev_cases and fmt(init_val) != prev_cases[case]


def cmd_run(ctx: Context, args: argparse.Namespace) -> int:
    cfg = load_eval(ctx.repo, args.item)
    cases = args.cases.split(",") if args.cases else None
    if args.hypothesis and args.arm not in ("auto", "with"):
        raise RunnerError("--hypothesis measures a skill change and needs --arm auto or --arm with (D17)")
    full = (cases is None) and (not args.no_ledger) and (args.runs >= 1)
    if args.hypothesis and not full:
        raise RunnerError("a hill-climb measurement is a full measurement: drop --cases and --no-ledger")

    if full and not args.dry_run:
        dirty = item_dir_status(ctx.repo, cfg.item)
        if dirty:
            raise RunnerError(f"skills/{cfg.item} has unstaged or untracked changes ({dirty[0].strip()}); stage them "
                              f"first: git add skills/{cfg.item} (the ledger row names the staged tree, D10)")

    ledger_path = ctx.repo / "evals" / "ledger.tsv"
    ledger_rows = read_ledger(ledger_path) if ledger_path.is_file() else []
    c_sha = cases_sha(ctx.repo, cfg)
    candidate = cfg.candidate_spec
    chosen = cfg.cases if cases is None else cases

    if args.arm == "both":
        resolved_arms = ["with", "without"]
    elif args.arm in ("with", "without"):
        resolved_arms = [args.arm]
    else:
        has_cap = any(cfg.kind(c) == "capability" for c in chosen)
        cached_without = baseline_without_row(ledger_rows, cfg.item, candidate=candidate, cases_sha=c_sha)
        resolved_arms = ["with"] if (args.hypothesis or cached_without is not None or not has_cap) else ["with", "without"]

    trigger_prompts = parse_trigger_prompts((cfg.dir / "triggers.md").read_text(encoding="utf-8"))
    n_triggers = len(trigger_prompts["load"]) + len(trigger_prompts["skip"])
    t_sha = ""
    if args.triggers:
        run_triggers = n_triggers > 0
    elif args.no_triggers:
        run_triggers = False
    elif args.arm in ("with", "without"):
        run_triggers = False
    elif args.arm == "both":
        run_triggers = n_triggers > 0
    else:
        t_sha = triggers_sha(ctx.repo, cfg)
        run_triggers = (matching_triggers_row(ledger_rows, cfg.item, candidate=candidate, triggers_sha=t_sha) is None
                        and n_triggers > 0)
    if run_triggers and not t_sha:
        t_sha = triggers_sha(ctx.repo, cfg)

    plan = plan_runs(cfg, args.arm, cases, args.runs, resolved_arms=resolved_arms,
                     triggers=n_triggers if run_triggers else 0, full=full)
    print(json.dumps(plan))
    if args.dry_run:
        return 0
    if plan["max_total"] > MAX_RUNS_WITHOUT_YES and not args.yes:
        raise RunnerError(f"refusing {plan['max_total']} max runs (more than {MAX_RUNS_WITHOUT_YES}) without --yes")

    previous = None
    if full:
        previous = previous_with_row(ledger_rows, cfg.item, candidate=candidate, cases_sha=c_sha)
        if args.hypothesis:
            if previous is None:
                raise RunnerError(f"no baseline `with` row for {cfg.item} matching ({candidate}, cases_sha={c_sha}): "
                                  f"run the baseline measurement first (uv run python scripts/run_evals.py {cfg.item})")
            if baseline_without_row(ledger_rows, cfg.item, candidate=candidate, cases_sha=c_sha) is None:
                raise RunnerError(f"no baseline `without` row for {cfg.item} matching ({candidate}, cases_sha={c_sha}): "
                                  f"run the baseline measurement first (uv run python scripts/run_evals.py {cfg.item})")

    need_judge = bool(cfg.judge and any(cfg.kind(c) == "capability" for c in plan["cases"]))
    ensure_ready(ctx, cfg, need_candidate=True, need_judge=need_judge)

    item_sha = tree_hash(ctx.repo / "skills" / cfg.item) if full else ""
    measurement = f"{utc_now():%Y%m%dT%H%M%S%f}-{uuid.uuid4().hex[:6]}"
    results: list[dict] = []
    done = 0
    for arm in resolved_arms:
        for case in plan["cases"]:
            if arm == "without" and cfg.kind(case) != "capability":
                continue
            case_runs: list[dict] = []
            for n in range(1, args.runs + 1):
                done += 1
                ctx.log(f"[{done}/{plan['candidate']}] {arm} {case} #{n}")
                rec = execute_case_run(ctx, cfg, arm=arm, case=case, n=n, measurement=measurement,
                                       item_sha=item_sha, c_sha=c_sha)
                case_runs.append(rec)
                results.append(rec)
            if full and arm == "with" and args.runs < 3 and _should_repeat_case(cfg, case, case_runs, previous):
                for n in range(args.runs + 1, 4):
                    done += 1
                    ctx.log(f"[{done} adaptive] {arm} {case} #{n}")
                    rec = execute_case_run(ctx, cfg, arm=arm, case=case, n=n, measurement=measurement,
                                           item_sha=item_sha, c_sha=c_sha)
                    case_runs.append(rec)
                    results.append(rec)

    trigger_results: list[dict] = []
    if run_triggers:
        index = 0
        for expect, key in ((True, "load"), (False, "skip")):
            for prompt in trigger_prompts[key]:
                index += 1
                ctx.log(f"[trigger {index}/{n_triggers}] {prompt[:60]}")
                trigger_results.append(execute_trigger_run(ctx, cfg, prompt=prompt, expect_load=expect, index=index,
                                                           measurement=measurement))

    summary: dict = {"item": cfg.item, "measurement": measurement, "cases_sha": c_sha, "arms": {},
                     "ledger": False, "ledger_ids": []}
    for arm in resolved_arms:
        s = arm_summary(results, arm)
        summary["arms"][arm] = {"median_pass": s["median"], "regression": f"{s['reg_passed']}/{s['reg_runs']}"}
    if trigger_results:
        passed = sum(1 for r in trigger_results if r["passed"])
        summary["arms"]["triggers"] = {"median_pass": round(passed / len(trigger_results), 2),
                                       "passed": f"{passed}/{len(trigger_results)}"}
    rows_by_arm: dict[str, str] = {}
    record: dict = {"measurement": measurement, "item": cfg.item, "item_sha": item_sha, "cases_sha": c_sha,
                    "kind": "adhoc", "runs": [r["run_id"] for r in results],
                    "trigger_runs": [r["run_id"] for r in trigger_results], "rows": {}, "ledger_ids": []}
    if full:
        rows = read_ledger(ledger_path)
        counter = max_ledger_suffix(rows, cfg.item)
        new_rows: list[dict[str, str]] = []
        if args.hypothesis:
            assert previous is not None
            s = arm_summary(results, "with")
            before = float(previous["median_pass"])
            prev_counts = regression_counts(previous["note"]) or (0, 0)
            prev_reg_rate = (prev_counts[0] / prev_counts[1]) if prev_counts[1] > 0 else 0.0
            reg_rate = (s["reg_passed"] / s["reg_runs"]) if s["reg_runs"] > 0 else 0.0
            reg_ok = s["reg_runs"] > 0 and reg_rate >= prev_reg_rate
            improved = s["median"] > before or reg_rate > prev_reg_rate
            verdict = "kept" if reg_ok and improved else "reverted"
            counter += 1
            new_rows.append(make_row(cfg.item, counter, item_sha, "with", candidate, s["runs"], s["median"],
                                     verdict=verdict, hypothesis=args.hypothesis, change=args.change or "",
                                     before=fmt(before), delta=fmt(s["median"] - before),
                                     note=format_with_note(cfg, s, c_sha)))
            rows_by_arm["with"] = new_rows[-1]["id"]
            if trigger_results:
                passed = sum(1 for r in trigger_results if r["passed"])
                counter += 1
                new_rows.append(make_row(cfg.item, counter, item_sha, "triggers", candidate, len(trigger_results),
                                         passed / len(trigger_results), verdict="baseline",
                                         hypothesis=args.hypothesis, change=args.change or "", before="", delta="",
                                         note=f"triggers={passed}/{len(trigger_results)};triggers_sha={t_sha}"))
                rows_by_arm["triggers"] = new_rows[-1]["id"]
            record["kind"] = "hill-climb"
            summary["verdict"] = verdict
        else:
            for arm in resolved_arms:
                s = arm_summary(results, arm)
                counter += 1
                note = format_with_note(cfg, s, c_sha) if arm == "with" else format_without_note(cfg, s, c_sha)
                new_rows.append(make_row(cfg.item, counter, item_sha, arm, candidate, s["runs"], s["median"],
                                         verdict="baseline", note=note))
                rows_by_arm[arm] = new_rows[-1]["id"]
            if trigger_results:
                passed = sum(1 for r in trigger_results if r["passed"])
                counter += 1
                new_rows.append(make_row(cfg.item, counter, item_sha, "triggers", candidate, len(trigger_results),
                                         passed / len(trigger_results), verdict="baseline",
                                         note=f"triggers={passed}/{len(trigger_results)};triggers_sha={t_sha}"))
                rows_by_arm["triggers"] = new_rows[-1]["id"]
            record["kind"] = "baseline"
        append_rows(ledger_path, new_rows)
        record["rows"] = rows_by_arm
        record["ledger_ids"] = [r["id"] for r in new_rows]
        summary["ledger"] = True
        summary["ledger_ids"] = record["ledger_ids"]
    (ctx.artifacts / cfg.item).mkdir(parents=True, exist_ok=True)
    (ctx.artifacts / cfg.item / f"measurement-{measurement}.json").write_text(json.dumps(record, indent=2),
                                                                              encoding="utf-8")
    summary["artifacts"] = str(ctx.artifacts / cfg.item)
    print(json.dumps(summary))
    return 0


# --------------------------------------------------------------------------------------- calibration


def _calibration_reason(total: int, agree: int, has_contrast: bool) -> str | None:
    if not has_contrast:
        return "uncalibrated: no contrast"
    if total < 6:
        return "uncalibrated: too few samples"
    if agree < total - 1:
        return "uncalibrated: low agreement"
    return None


def cmd_calibration_sheet(ctx: Context, args: argparse.Namespace) -> int:
    cfg = load_eval(ctx.repo, args.item)
    if not cfg.judge:
        raise RunnerError(f"{cfg.item} has no rubric.md, so there is nothing to calibrate")
    if args.samples < 6:
        raise RunnerError("--samples must be at least 6")
    if not cfg.capability:
        raise RunnerError(f"{cfg.item} has no capability cases to calibrate")
    c_sha = cases_sha(ctx.repo, cfg)

    pool_entries: list[tuple[str, dict]] = []
    has_baseline = False
    for path in reversed(measurement_files(ctx.artifacts, cfg.item)):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("kind") == "baseline" and data.get("rows"):
            has_baseline = True
            for rid in data["runs"]:
                r_path = ctx.artifacts / cfg.item / rid / "result.json"
                if r_path.is_file():
                    pool_entries.append((rid, json.loads(r_path.read_text(encoding="utf-8"))))
            break
    cal_dir = ctx.artifacts / cfg.item / "calibration-runs"
    if cal_dir.is_dir():
        for r_path in sorted(cal_dir.glob("*/result.json")):
            rel = f"calibration-runs/{r_path.parent.name}"
            pool_entries.append((rel, json.loads(r_path.read_text(encoding="utf-8"))))
    if not has_baseline and not pool_entries and not args.collect:
        latest_baseline(ctx.artifacts, cfg.item)

    def is_eligible(result: dict) -> bool:
        return (result.get("kind") == "capability" and judge_label(result) is not None
                and result.get("cases_sha") == c_sha)

    eligible: list[tuple[str, dict]] = [(rel, r) for rel, r in pool_entries if is_eligible(r)]
    missing = max(0, args.samples - len(eligible))

    if args.collect:
        max_total = 2 * (missing + (2 if missing else 0))
        plan = {"item": cfg.item, "candidate": missing, "judge": missing, "trigger": 0, "total": 2 * missing,
                "max_total": max_total, "existing": len(eligible), "samples": args.samples}
        print(json.dumps(plan))
        if args.dry_run:
            return 0
        if plan["max_total"] > MAX_RUNS_WITHOUT_YES and not args.yes:
            raise RunnerError(f"refusing {plan['max_total']} max runs (more than {MAX_RUNS_WITHOUT_YES}) without --yes")
        if missing > 0:
            ensure_ready(ctx, cfg, need_candidate=True, need_judge=True)
            item_sha = tree_hash(ctx.repo / "skills" / cfg.item)
            step = 0
            for i in range(missing):
                arm = "without" if step % 2 == 0 else "with"
                case = cfg.capability[(step // 2) % len(cfg.capability)]
                step += 1
                ctx.log(f"[collect {i + 1}/{missing}] {arm} {case}")
                rec = execute_case_run(ctx, cfg, arm=arm, case=case, n=step, measurement="calibration",
                                       item_sha=item_sha, c_sha=c_sha, force_judge=True,
                                       artifacts_subdir="calibration-runs")
                if is_eligible(rec):
                    eligible.append((f"calibration-runs/{rec['run_id']}", rec))
            fallback = 0
            while len(eligible) < args.samples and fallback < 2:
                arm = "without" if step % 2 == 0 else "with"
                case = cfg.capability[(step // 2) % len(cfg.capability)]
                step += 1
                fallback += 1
                ctx.log(f"[collect fallback {fallback}/2] {arm} {case}")
                rec = execute_case_run(ctx, cfg, arm=arm, case=case, n=step, measurement="calibration",
                                       item_sha=item_sha, c_sha=c_sha, force_judge=True,
                                       artifacts_subdir="calibration-runs")
                if is_eligible(rec):
                    eligible.append((f"calibration-runs/{rec['run_id']}", rec))
            if len(eligible) < args.samples:
                raise RunnerError(f"only {len(eligible)} non-N/A calibration sample(s) collected (need {args.samples})")
    else:
        if args.dry_run:
            print(json.dumps({"item": cfg.item, "existing": len(eligible), "missing": missing, "samples": args.samples}))
            return 0
        if missing > 0:
            raise RunnerError(f"only {len(eligible)} eligible calibration sample(s) for {cfg.item} "
                              f"(need {args.samples}); pass --collect to run {missing} more")

    passes = sorted((entry for entry in eligible if judge_label(entry[1]) == "PASS"), key=lambda e: e[1]["run_id"])
    fails = sorted((entry for entry in eligible if judge_label(entry[1]) == "FAIL"), key=lambda e: e[1]["run_id"])
    chosen: list[tuple[str, dict]] = []
    while len(chosen) < args.samples and (passes or fails):
        for pool in (passes, fails):
            if pool and len(chosen) < args.samples:
                chosen.append(pool.pop(0))
    chosen.sort(key=lambda entry: hashlib.sha1(entry[1]["run_id"].encode()).hexdigest())
    criteria = parse_rubric_criteria((cfg.dir / "rubric.md").read_text(encoding="utf-8"))

    def quote(text: str) -> str:
        return "\n".join(f"> {line}" if line else ">" for line in text.splitlines()) or ">"

    parts = [f"# Calibration sheet: {REDACTED}\n",
             "Label each sample PASS (every applicable criterion holds) or FAIL, using the numbered criteria only. "
             "Fill `label:` and `critique:` at the end of each sample.\n"]
    mapping = {}
    for number, (rel_path, result) in enumerate(chosen, start=1):
        run_dir = ctx.artifacts / cfg.item / rel_path
        mapping[str(number)] = rel_path
        final = (run_dir / "final_message.txt").read_text(encoding="utf-8")
        state = (run_dir / "end_state.md").read_text(encoding="utf-8")
        parts.append(f"\n## Sample {number}\n\nCriteria:\n\n" + "\n".join(criteria) + "\n\nFinal message:\n\n"
                     + quote(final) + "\n\nEnd state:\n\n" + quote(state) + "\n\nTool calls:\n\n"
                     + quote("\n".join(result.get("tool_calls", [])[:40])) + "\n\nlabel:\ncritique:\n")
    sheet = ctx.artifacts / cfg.item / "calibration-sheet.md"
    sheet.write_text("".join(parts).replace(cfg.item, REDACTED), encoding="utf-8")
    (ctx.artifacts / cfg.item / "calibration-map.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(json.dumps({"sheet": str(sheet), "samples": len(chosen),
                      "judge_pass": sum(1 for _, r in chosen if judge_label(r) == "PASS"),
                      "judge_fail": sum(1 for _, r in chosen if judge_label(r) == "FAIL")}))
    return 0


def parse_sheet(text: str) -> dict[int, tuple[str | None, str]]:
    out: dict[int, tuple[str | None, str]] = {}
    pieces = re.split(r"(?m)^## Sample (\d+)\s*$", text)
    for number, body in zip(pieces[1::2], pieces[2::2]):
        label_at = body.rfind("\nlabel:")
        crit_at = body.rfind("\ncritique:")
        label = None
        critique = ""
        if label_at != -1 and crit_at > label_at:
            raw = body[label_at + len("\nlabel:"):crit_at].strip().upper()
            label = raw if raw in ("PASS", "FAIL") else None
            critique = re.sub(r"\s+", " ", body[crit_at + len("\ncritique:"):]).strip()
        out[int(number)] = (label, critique)
    return out


def cmd_calibrate(ctx: Context, args: argparse.Namespace) -> int:
    cfg = load_eval(ctx.repo, args.item)
    sheet = Path(args.calibrate)
    if not sheet.is_file():
        raise RunnerError(f"calibration sheet {sheet} not found")
    mapping = json.loads((ctx.artifacts / cfg.item / "calibration-map.json").read_text(encoding="utf-8"))
    labels = parse_sheet(sheet.read_text(encoding="utf-8"))
    missing = [n for n in mapping if labels.get(int(n), (None, ""))[0] is None]
    if missing:
        raise RunnerError(f"samples without a PASS or FAIL label: {', '.join(missing)}")
    rows = ["sample\towner_label\tjudge_label\tagree\towner_critique"]
    agree = 0
    owner_labels: set[str] = set()
    for number in sorted(mapping, key=int):
        result = json.loads((ctx.artifacts / cfg.item / mapping[number] / "result.json").read_text(encoding="utf-8"))
        owner, critique = labels[int(number)]
        assert owner is not None
        owner_labels.add(owner)
        judged = judge_label(result) or "FAIL"
        ok = owner == judged
        agree += ok
        rows.append("\t".join([number, owner, judged, "true" if ok else "false", clean_cell(critique)]))
    (cfg.dir / "calibration.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    total = len(mapping)
    has_contrast = ("PASS" in owner_labels and "FAIL" in owner_labels)
    calibrated = (total >= 6) and (agree >= total - 1) and has_contrast
    reason = None if calibrated else _calibration_reason(total, agree, has_contrast)
    print(json.dumps({"agree": agree, "total": total, "has_contrast": has_contrast, "calibrated": calibrated,
                      "reason": reason, "file": str(cfg.dir / "calibration.tsv")}))
    return 0


def cmd_rejudge(ctx: Context, args: argparse.Namespace) -> int:
    cfg = load_eval(ctx.repo, args.item)
    if not cfg.judge:
        raise RunnerError(f"{cfg.item} has no rubric.md, so there is nothing to re-judge")
    measurement = latest_baseline(ctx.artifacts, cfg.item)
    measurement_path = Path(measurement.pop("_path"))
    committed = committed_ledger_ids(ctx.repo)
    already = [i for i in measurement["ledger_ids"] if i in committed]
    new_c_sha = cases_sha(ctx.repo, cfg)
    criteria = parse_rubric_criteria((cfg.dir / "rubric.md").read_text(encoding="utf-8"))
    map_path = ctx.artifacts / cfg.item / "calibration-map.json"
    cal_refs = list(json.loads(map_path.read_text(encoding="utf-8")).values()) if map_path.is_file() else []

    baseline_cap_passed: list[str] = []
    for rid in measurement["runs"]:
        res = json.loads((ctx.artifacts / cfg.item / rid / "result.json").read_text(encoding="utf-8"))
        if res.get("kind") == "capability" and all(c["pass"] for c in res["code"]):
            baseline_cap_passed.append(rid)
    to_rejudge = list(dict.fromkeys([*cal_refs, *baseline_cap_passed]))

    plan = {"item": cfg.item, "candidate": 0, "judge": len(to_rejudge), "trigger": 0,
            "total": len(to_rejudge), "measurement": measurement["measurement"]}
    print(json.dumps(plan))
    if args.dry_run:
        return 0
    if already:
        raise RunnerError(f"ledger row(s) {already} are already committed; a committed baseline is never re-judged")
    if plan["total"] > MAX_RUNS_WITHOUT_YES and not args.yes:
        raise RunnerError(f"refusing {plan['total']} runs (more than {MAX_RUNS_WITHOUT_YES}) without --yes")
    ensure_ready(ctx, cfg, need_candidate=False, need_judge=True)

    rejudged_set = set(to_rejudge)
    for number, ref in enumerate(to_rejudge, start=1):
        run_dir = ctx.artifacts / cfg.item / ref
        result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        ctx.log(f"[{number}/{len(to_rejudge)}] re-judge {ref}")
        transcript = [json.loads(x) for x in (run_dir / "judge-transcript.jsonl").read_text(
            encoding="utf-8").splitlines() if x]
        base = Path(tempfile.mkdtemp(prefix="run-"))
        try:
            judged, error = run_judge(ctx, cfg, criteria, (run_dir / "output.md").read_text(encoding="utf-8"),
                                      transcript, base)
        finally:
            shutil.rmtree(base, ignore_errors=True)
        result.update({
            "judge": judged,
            "judge_error": error,
            "judge_skipped": None,
            "score": score_run(result["code"], judged),
            "passed": run_passed(result["code"], judged),
            "cases_sha": new_c_sha,
        })
        (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    baseline_results: list[dict] = []
    for rid in measurement["runs"]:
        run_dir = ctx.artifacts / cfg.item / rid
        result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        if rid not in rejudged_set:
            if result.get("kind") == "capability":
                result.update({
                    "judge": None,
                    "judge_error": None,
                    "judge_skipped": "code_failed",
                    "score": gated_code_failed_score(result["code"], len(criteria)),
                    "passed": False,
                    "cases_sha": new_c_sha,
                })
            else:
                result["cases_sha"] = new_c_sha
            (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        baseline_results.append(result)

    ledger_path = ctx.repo / "evals" / "ledger.tsv"
    rows = read_ledger(ledger_path)
    for arm, row_id in measurement["rows"].items():
        if arm == "triggers":
            continue
        s = arm_summary(baseline_results, arm)
        for row in rows:
            if row["id"] == row_id:
                row["median_pass"] = fmt(s["median"])
                row["after"] = fmt(s["median"])
                row["runs"] = str(s["runs"])
                row["note"] = format_with_note(cfg, s, new_c_sha) if arm == "with" else format_without_note(
                    cfg, s, new_c_sha)
    write_ledger(ledger_path, rows)
    measurement["cases_sha"] = new_c_sha
    measurement_path.write_text(json.dumps(measurement, indent=2), encoding="utf-8")
    print(json.dumps({"rejudged": len(to_rejudge), "ledger_ids": measurement["ledger_ids"], "cases_sha": new_c_sha}))
    return 0


# --------------------------------------------------------------------------------------- signal


def lesson_export(repo: Path) -> list[dict]:
    done = subprocess.run([sys.executable, "-m", "chanchi", "lesson", "export", "--all", "--status", "pending",
                           "--limit", "1000"], cwd=repo, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise RunnerError(f"chanchi lesson export failed: {(done.stderr or done.stdout).strip()[-400:]}")
    return json.loads(done.stdout)["lessons"]


def cmd_signal(ctx: Context, args: argparse.Namespace) -> int:
    rows = read_ledger(ctx.repo / "evals" / "ledger.tsv")
    items_out: dict[str, dict] = {}
    for cfg in all_evals(ctx.repo):
        sha = tree_hash(ctx.repo / "skills" / cfg.item)
        c_sha = cases_sha(ctx.repo, cfg)
        cand = cfg.candidate_spec
        current = current_with_row(rows, cfg.item, sha, candidate=cand, cases_sha=c_sha)
        without = baseline_without_row(rows, cfg.item, candidate=cand, cases_sha=c_sha)
        entry: dict = {"in_signal": cfg.signal,
                       "judge": "none" if not cfg.judge else
                       f"{cfg.judge['harness']}:{cfg.judge['model']}:{cfg.judge['effort']}"}
        if cfg.judge:
            cal_path = cfg.dir / "calibration.tsv"
            cal_rows = ([ln for ln in cal_path.read_text(encoding="utf-8").splitlines()[1:] if ln.strip()]
                        if cal_path.is_file() else [])
            agree = sum(1 for line in cal_rows if line.split("\t")[3:4] == ["true"])
            owner_labels = {line.split("\t")[1] for line in cal_rows if len(line.split("\t")) >= 2}
            has_contrast = ("PASS" in owner_labels and "FAIL" in owner_labels)
            total = len(cal_rows)
            cal_met = total >= 6 and agree >= total - 1 and has_contrast
            reason = None if cal_met else _calibration_reason(total, agree, has_contrast)
            entry["calibrated"] = {"agree": agree, "total": total, "has_contrast": has_contrast,
                                   "met": cal_met, "reason": reason}
        else:
            entry["calibrated"] = None
        counts = regression_counts(current["note"]) if current else None
        entry["regression"] = {"passed": counts[0] if counts else None, "runs": counts[1] if counts else None,
                               "met": bool(counts and counts[1] >= 1 and counts[0] == counts[1])}
        w = float(current["median_pass"]) if current else None
        wo = float(without["median_pass"]) if without else None
        entry["capability"] = {"with": w, "without": wo, "met": w is not None and wo is not None and w > wo}
        items_out[cfg.item] = entry
    flagged = [{k: lesson.get(k) for k in ("id", "occurrences", "target_kind", "target", "origin")}
               for lesson in lesson_export(ctx.repo)
               if int(lesson.get("occurrences", 1)) >= 2 and lesson.get("target_kind") not in LESSON_CHECK_KINDS]
    lessons = {"met": not flagged, "flagged": flagged}
    scoped = [e for e in items_out.values() if e["in_signal"]]
    met = bool(scoped) and lessons["met"] and all(
        (True if e["calibrated"] is None else e["calibrated"]["met"])
        and e["regression"]["met"] and e["capability"]["met"]
        for e in scoped
    )
    print(json.dumps({"items": items_out, "lessons": lessons, "met": met,
                      "reason": None if scoped else "no signal evals"}))
    return 0


# --------------------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_evals.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("item", nargs="?", help="the evaluated skill, e.g. skill-chanchi-lessons")
    parser.add_argument("--arm", choices=("auto", "with", "without", "both"), default="auto")
    parser.add_argument("--cases", help="comma list of cases (a partial measurement writes no ledger row)")
    parser.add_argument("--runs", type=int, default=1)
    trig_group = parser.add_mutually_exclusive_group()
    trig_group.add_argument("--triggers", action="store_true", help="force trigger runs")
    trig_group.add_argument("--no-triggers", action="store_true", help="skip trigger runs")
    parser.add_argument("--yes", action="store_true", help=f"allow more than {MAX_RUNS_WITHOUT_YES} runs")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    parser.add_argument("--no-ledger", action="store_true", help="never write a ledger row")
    parser.add_argument("--hypothesis", help="hill-climb: the one change being measured (needs --arm auto|with)")
    parser.add_argument("--change", help="hill-climb: the ref of the change (a branch or commit)")
    parser.add_argument("--calibration-sheet", action="store_true", help="write the owner's labeling sheet")
    parser.add_argument("--samples", type=int, default=6, help="number of calibration samples (default 6)")
    parser.add_argument("--collect", action="store_true", help="run missing capability runs for calibration")
    parser.add_argument("--calibrate", metavar="SHEET", help="compare the owner's labels with the judge")
    parser.add_argument("--rejudge", action="store_true", help="re-judge the latest baseline's saved outputs")
    parser.add_argument("--signal", action="store_true", help="print the phase-2 signal as JSON")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="repository root (default: this repository)")
    parser.add_argument("--timeout", type=int, default=300, help="seconds per harness run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    modes = [m for m, on in (("--calibration-sheet", args.calibration_sheet), ("--calibrate", bool(args.calibrate)),
                             ("--rejudge", args.rejudge), ("--signal", args.signal)) if on]
    try:
        if len(modes) > 1:
            raise RunnerError(f"choose one mode, got {', '.join(modes)}")
        if args.signal:
            if args.item:
                raise RunnerError("--signal takes no item")
        elif not args.item:
            raise RunnerError("an item is required (for example skill-chanchi-lessons)")
        if args.runs < 1:
            raise RunnerError("--runs must be at least 1")
        if args.timeout < 1:
            raise RunnerError("--timeout must be at least 1")
        ctx = Context(repo=Path(args.repo).resolve(), artifacts=artifacts_root(), timeout=args.timeout)
        if args.signal:
            return cmd_signal(ctx, args)
        if args.calibration_sheet:
            return cmd_calibration_sheet(ctx, args)
        if args.calibrate:
            return cmd_calibrate(ctx, args)
        if args.rejudge:
            return cmd_rejudge(ctx, args)
        return cmd_run(ctx, args)
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
