"""The eval runner (scripts/run_evals.py), driven with a fake harness executable and a fake credential source.

No test launches a real harness or reads the keychain: `claude` and `agy` are scripts written here, placed at
the front of PATH, and the credential source is the CHANCHI_EVALS_CREDENTIALS_DIR folder written by the test.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_evals as R  # noqa: E402
from run_evals import LEDGER_COLUMNS, read_ledger  # noqa: E402

ITEM = "skill-chanchi-demo"
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

FAKE_HARNESS = r'''#!__PYTHON__
import json, os, subprocess, sys
from pathlib import Path

here = Path(__file__).resolve().parent
cfg = json.loads((here / "config.json").read_text())
name = Path(sys.argv[0]).name
argv = sys.argv[1:]


def val(flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


agent = val("--agent")
role = "trigger" if agent is None else ("judge" if agent == "agent-chanchi-judge" else "candidate")
calls = here / "calls.jsonl"
previous = [json.loads(x) for x in calls.read_text().splitlines()] if calls.exists() else []
index = sum(1 for c in previous if c["role"] == role)
spec = cfg.get(role, {})
if isinstance(spec, list):
    spec = spec[min(index, len(spec) - 1)]
cwd = Path.cwd()
home = Path(os.environ.get("HOME", ""))
cred = home / (".claude/.credentials.json" if name == "claude" else ".gemini/antigravity-cli/antigravity-oauth-token")


def read(rel):
    p = cwd / rel
    return p.read_text() if p.is_file() else None


wrapper = read(".claude/agents/worker.md") or read(".agents/agents/worker/agent.md") \
    or read(".claude/agents/agent-chanchi-judge.md") or read(".agents/agents/agent-chanchi-judge/agent.md")
skills = sorted(str(p.relative_to(cwd)) for base in (".claude/skills", ".agents/skills") if (cwd / base).is_dir()
                for p in (cwd / base).rglob("*") if p.is_file())
git = None
if (cwd / ".git").exists():
    git = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout
record = {
    "name": name, "role": role, "argv": argv, "cwd": str(cwd), "env": dict(os.environ), "wrapper": wrapper,
    "skills": skills, "git_status": git, "stdin_tty": sys.stdin.isatty(),
    "cred_exists": cred.is_file(), "cred_mode": oct(cred.stat().st_mode & 0o777) if cred.is_file() else None,
    "cred_text": cred.read_text() if cred.is_file() else None, "home": str(home),
    "criteria": read("criteria.md"), "output": read("output.md"), "transcript": read("transcript.jsonl"),
    "judge_dir_files": sorted(p.name for p in cwd.iterdir()) if role == "judge" else None,
}
with calls.open("a") as handle:
    handle.write(json.dumps(record) + "\n")

for rel, text in spec.get("files", {}).items():
    target = cwd / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
if spec.get("run"):
    subprocess.run(spec["run"], shell=True, cwd=cwd, check=False)

final = spec.get("final", "done")
exit_code = spec.get("exit", 0)
item = spec.get("skill") or next((Path(s).parts[2] for s in skills), "skill-chanchi-demo")
out = []
if name == "claude":
    out.append({"type": "system", "subtype": "init", "skills": ["design", *sorted({Path(s).parts[2] for s in skills})],
                "agents": ["worker"]})
    if spec.get("load_skill"):
        out.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tu1", "name": "Skill",
                                                                   "input": {"skill": item}}]}})
        out.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tu1",
                                                              "content": "Launching skill: " + item}]}})
        out.append({"type": "user", "isSynthetic": True, "message": {"content": [{"type": "text",
                                                                                    "text": "SKILL TEXT BODY"}]}})
    out.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tu2", "name": "Bash",
                                                               "input": {"command": "echo hi"}}]}})
    out.append({"type": "assistant", "message": {"content": [{"type": "text", "text": final}]}})
    if not spec.get("no_result"):
        out.append({"type": "result", "subtype": "success", "is_error": exit_code != 0, "result": final})
else:
    out.append({"event": "init", "init": {"model": val("--model"), "agent": agent}})
    if spec.get("load_skill"):
        for state in ("ACTIVE", "DONE"):
            out.append({"event": "step_update", "step_update": {"step_index": 2, "state": state, "step_type": "tool",
                                                                 "tool_name": "read_file", "tool_info": {
                "name": "read_file", "parameters": {"Path": f"{cwd}/.agents/skills/{item}/SKILL.md"}}}})
    out.append({"event": "step_update", "step_update": {"step_index": 3, "state": "DONE", "step_type": "tool",
                                                         "tool_name": "run_command", "tool_info": {
        "name": "run_command", "parameters": {"CommandLine": "echo hi"}}}})
    if not spec.get("no_result"):
        out.append({"event": "result", "result": {"status": "ERROR" if exit_code else "SUCCESS", "response": final}})
for event in out:
    print(json.dumps(event))
sys.exit(exit_code)
'''

JUDGE_PASS = '```json\n{"criteria": [{"n": 1, "verdict": "PASS", "critique": "ok"}, ' \
             '{"n": 2, "verdict": "PASS", "critique": "ok"}]}\n```'


def verdicts(v1: str, v2: str) -> str:
    return ('```json\n{"criteria": [{"n": 1, "verdict": "%s", "critique": "x"}, '
            '{"n": 2, "verdict": "%s", "critique": "y"}]}\n```' % (v1, v2))


GRADE = '''import json, os, sys
from pathlib import Path

work = Path(sys.argv[1])
final = Path(os.environ["FINAL_MESSAGE_FILE"]).read_text()
sync = Path(os.environ["CHANCHI_SYNC"])
(sync / "grade-seen").write_text(json.dumps({"sync": str(sync), "db": os.environ["CHANCHI_DB"], "final": final}))
print(json.dumps({"criterion": "ran", "pass": (work / "out.txt").exists(), "detail": "out.txt present"}))
'''

SETUP = '''set -e
mkdir -p "$CHANCHI_SYNC" "$(dirname "$CHANCHI_DB")"
echo "$CHANCHI_SYNC|$CHANCHI_DB" > "$CHANCHI_SYNC/setup-seen"
git init -q
echo base > base.txt
mkdir tests
echo t > tests/t.txt
git add -A
git commit -qm init
'''


class World:
    def __init__(self, tmp_path: Path, monkeypatch):
        self.tmp = tmp_path
        self.repo = tmp_path / "repo"
        self.bin = tmp_path / "fakebin"
        self.creds = tmp_path / "creds"
        self.evals_dir = tmp_path / "artifacts"
        self.monkeypatch = monkeypatch
        self.bin.mkdir()
        self.creds.mkdir()
        (self.creds / "claude").write_text('{"claudeAiOauth": "fake"}')
        (self.creds / "agy").write_text('{"token": "fake"}')
        for name in ("claude", "agy"):
            path = self.bin / name
            path.write_text(FAKE_HARNESS.replace("__PYTHON__", sys.executable))
            path.chmod(0o755)
        monkeypatch.setenv("PATH", f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv("CHANCHI_EVALS_CREDENTIALS_DIR", str(self.creds))
        monkeypatch.setenv("CHANCHI_EVALS_DIR", str(self.evals_dir))
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
        self.build_repo()
        self.config({})

    # -- repository fixture --
    def build_repo(self):
        repo = self.repo
        skill = repo / "skills" / ITEM
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: skill-chanchi-demo\n---\nDo the demo.\n")
        (skill / "references" / "x.md").write_text("x\n")
        for agent in ("agent-chanchi-executor", "agent-chanchi-judge"):
            shutil.copytree(ROOT / "agents" / agent, repo / "agents" / agent)
        ev = repo / "evals" / "eval-chanchi-demo"
        for case in ("reg-a", "cap-a"):
            case_dir = ev / "cases" / case
            case_dir.mkdir(parents=True)
            (case_dir / "prompt.md").write_text(f"Handle the {case} request.\n")
            (case_dir / "setup.sh").write_text(SETUP)
            (case_dir / "grade.py").write_text(GRADE)
        (ev / "rubric.md").write_text(
            "# Rubric: skill-chanchi-demo\nFor each criterion answer PASS or FAIL.\n"
            "1. The cause names why.\n   It continues here.\n2. The rule is general.\n\nClosing note.\n"
        )
        (ev / "triggers.md").write_text(
            "## Must load\n- Do the demo now.\n## Must not load\n- Say hello.\n"
        )
        (ev / "eval.toml").write_text(
            'name = "eval-chanchi-demo"\nitem = "skill-chanchi-demo"\nregression = ["reg-a"]\n'
            'capability = ["cap-a"]\nblind_allow = ["tests"]\n\n'
            '[candidate]\nagent = "agent-chanchi-executor"\nharness = "claude"\nmodel = "sonnet"\neffort = "medium"\n\n'
            '[judge]\nharness = "agy"\nmodel = "gemini-4-neon-high"\neffort = "high"\n'
        )
        (repo / "evals" / "ledger.tsv").write_text("\t".join(LEDGER_COLUMNS) + "\n")
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "a@b.c")
        git(repo, "config", "user.name", "T")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")

    def config(self, cfg: dict):
        (self.bin / "config.json").write_text(json.dumps(cfg))
        calls = self.bin / "calls.jsonl"
        if calls.exists():
            calls.unlink()

    def calls(self, role: str | None = None) -> list[dict]:
        path = self.bin / "calls.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
        return [r for r in rows if role is None or r["role"] == role]

    def run(self, capsys, *args: str, item: str | None = ITEM) -> tuple[int, str, str]:
        argv = ([item] if item else []) + ["--repo", str(self.repo), *args]
        code = R.main(argv)
        out, err = capsys.readouterr()
        return code, out, err

    def ledger(self) -> list[dict[str, str]]:
        return read_ledger(self.repo / "evals" / "ledger.tsv")

    def stage_skill_change(self, text: str):
        (self.repo / "skills" / ITEM / "SKILL.md").write_text(f"---\nname: skill-chanchi-demo\n---\n{text}\n")
        git(self.repo, "add", "skills")

    def runs_dir(self) -> Path:
        return self.evals_dir / ITEM


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=CLEAN_ENV, check=True, capture_output=True,
                          text=True).stdout


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def last_json(out: str) -> dict:
    return json.loads(out.strip().splitlines()[-1])


def full_config(**over) -> dict:
    """Candidate order of a full `--arm both --runs 3` baseline: with/reg-a x3, with/cap-a x3, without/cap-a x3."""
    cfg = {
        "candidate": [{"files": {"out.txt": "x"}, "final": "cand final"}] * 9,
        "judge": [{"final": JUDGE_PASS}],
        "trigger": [{"load_skill": True}, {"load_skill": True}],
    }
    cfg.update(over)
    return cfg


# ---------------------------------------------------------------- planning, refusal, dry run


def test_dry_run_prints_the_plan_and_runs_nothing(world, capsys):
    world.config(full_config())
    code, out, _ = world.run(capsys, "--dry-run", "--no-ledger")
    assert code == 0
    plan = last_json(out)
    # Rev 5 defaults: --arm auto (with + without on first baseline) and --runs 1; reg-a is never judged
    assert plan["arm"] == "auto" and plan["resolved_arms"] == ["with", "without"]
    assert plan["runs"] == 1 and plan["ledger"] == "none"
    assert (plan["candidate"], plan["judge"], plan["trigger"], plan["total"], plan["max_total"]) == (3, 2, 2, 7, 7)
    assert world.calls() == []

    # Without --no-ledger, full=True so max_total accounts for adaptive repeat up to 3 runs in `with`
    code, out, _ = world.run(capsys, "--dry-run")
    assert code == 0
    plan = last_json(out)
    assert plan["ledger"] == "write"
    assert (plan["total"], plan["max_total"]) == (7, 13)


def test_arm_with_has_no_without_runs_and_no_triggers(world, capsys):
    code, out, _ = world.run(capsys, "--dry-run", "--arm", "with")
    plan = last_json(out)
    assert plan["resolved_arms"] == ["with"]
    assert (plan["candidate"], plan["judge"], plan["trigger"], plan["total"], plan["max_total"]) == (2, 1, 0, 3, 9)
    code, out, _ = world.run(capsys, "--dry-run", "--arm", "without", "--cases", "reg-a,cap-a")
    plan = last_json(out)
    assert plan["resolved_arms"] == ["without"]
    assert (plan["candidate"], plan["judge"], plan["trigger"], plan["total"], plan["max_total"]) == (1, 1, 0, 2, 2)


def test_more_than_30_runs_need_yes(world, capsys):
    world.config(full_config())
    code, out, err = world.run(capsys, "--arm", "both", "--runs", "6", "--no-ledger")
    assert code == 2 and "--yes" in err and "30" in err
    plan = last_json(out)
    assert plan["candidate"] == 18 and plan["judge"] == 12 and plan["total"] == 32 and plan["max_total"] == 32
    assert world.calls() == []
    # 5 runs of one case in one arm: 5 candidate + 5 judge runs, under the limit, no --yes needed
    code, _, err = world.run(capsys, "--runs", "5", "--no-ledger", "--cases", "cap-a", "--arm", "with")
    assert code == 0, err
    assert len(world.calls("candidate")) == 5


def test_max_total_over_30_refused_without_yes_even_when_initial_total_under_30(world, capsys):
    ev = world.repo / "evals" / "eval-chanchi-demo"
    for extra in ("reg-b", "reg-c", "reg-d", "reg-e", "cap-b", "cap-c"):
        shutil.copytree(ev / "cases" / ("reg-a" if extra.startswith("reg-") else "cap-a"), ev / "cases" / extra)
    toml = ev / "eval.toml"
    toml.write_text(
        toml.read_text()
        .replace('regression = ["reg-a"]', 'regression = ["reg-a", "reg-b", "reg-c", "reg-d", "reg-e"]')
        .replace('capability = ["cap-a"]', 'capability = ["cap-a", "cap-b", "cap-c"]')
    )
    git(world.repo, "add", "-A")
    # 5 reg + 3 cap: --arm with --runs 1 -> initial candidate=8, judge=3, total=11 <= 30,
    # but adaptive repeat max_total = 8*3 + 3*3 = 33 > 30!
    code, out, err = world.run(capsys, "--arm", "with", "--runs", "1")
    assert code == 2 and "--yes" in err and "30" in err
    plan = last_json(out)
    assert plan["total"] == 11 and plan["max_total"] == 33
    assert world.calls() == []


# ---------------------------------------------------------------- one run: wiring


def test_arm_wiring_wrapper_and_skill_only_in_the_with_arm(world, capsys):
    world.config(full_config())
    code, _, err = world.run(capsys, "--arm", "both", "--runs", "3", "--no-ledger", "--yes")
    assert code == 0, err
    cands = world.calls("candidate")
    assert len(cands) == 9
    with_runs, without_runs = cands[:6], cands[6:]
    for call in with_runs:
        assert f".claude/skills/{ITEM}/SKILL.md" in call["skills"]
        assert f".claude/skills/{ITEM}/references/x.md" in call["skills"]
        assert re.search(rf"^skills:\n  - {ITEM}$", call["wrapper"], re.MULTILINE)
    for call in without_runs:
        assert call["skills"] == []
        assert "skills:" not in call["wrapper"]
    for call in cands:
        wrapper = call["wrapper"]
        assert re.search(r"^name: worker$", wrapper, re.MULTILINE)
        assert "agent-chanchi" not in wrapper.split("---\n", 2)[1]  # neutral name; scope both: no initialPrompt
        assert "initialPrompt" not in wrapper
        body = (ROOT / "agents" / "agent-chanchi-executor" / "AGENT.md").read_text().split("\n---\n", 1)[1].strip()
        assert body in wrapper  # the role is the wrapper's body (scope both), whichever arm
        argv = call["argv"]
        assert argv[:5] == ["-p", "--agent", "worker", "--model", "sonnet"]
        assert argv[argv.index("--effort") + 1] == "medium"
        assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
        assert argv[argv.index("--allowedTools") + 1] == "Bash Read Grep Glob Edit Write Skill"
        assert "--dangerously-skip-permissions" not in argv
        assert argv[argv.index("--output-format") + 1] == "stream-json" and "--verbose" in argv
        assert argv[-2] == "--" and argv[-1] == "Handle the reg-a request." or "Handle the" in argv[-1]
        assert call["stdin_tty"] is False


def test_agy_candidate_launch_and_skill_location(world, capsys):
    toml = (world.repo / "evals" / "eval-chanchi-demo" / "eval.toml")
    toml.write_text(toml.read_text().replace(
        '[candidate]\nagent = "agent-chanchi-executor"\nharness = "claude"\nmodel = "sonnet"\neffort = "medium"',
        '[candidate]\nagent = "agent-chanchi-executor"\nharness = "agy"\nmodel = "gemini-4-hydrogen-medium"\n'
        'effort = "medium"').replace('harness = "agy"\nmodel = "gemini-4-neon-high"',
                                     'harness = "claude"\nmodel = "opus"').replace('effort = "high"', 'effort = "high"'))
    git(world.repo, "add", "-A")
    world.config(full_config(judge=[{"final": JUDGE_PASS}]))
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "cap-a", "--runs", "1")
    assert code == 0, err
    call = world.calls("candidate")[0]
    argv = call["argv"]
    assert call["name"] == "agy"
    assert argv[argv.index("--agent") + 1] == "worker"
    assert argv[argv.index("--model") + 1] == "gemini-4-hydrogen"
    assert argv[argv.index("--effort") + 1] == "medium"
    assert "--dangerously-skip-permissions" in argv and "--add-dir" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[-1].startswith("-p=")
    assert f".agents/skills/{ITEM}/SKILL.md" in call["skills"]
    assert "preloadSkills:" in call["wrapper"] and "mainAgent: true" in call["wrapper"]


def test_environment_credentials_and_scratch_paths(world, capsys):
    world.config(full_config())
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "reg-a", "--runs", "1")
    assert code == 0, err
    call = world.calls("candidate")[0]
    env = call["env"]
    assert set(env) <= {"PATH", "HOME", "TERM", "CHANCHI_DB", "CHANCHI_SYNC", "PWD", "SHLVL", "_", "LC_CTYPE",
                        "__CF_USER_TEXT_ENCODING"}
    assert env["TERM"] == "dumb"
    assert "CLAUDECODE" not in env and not any(k.startswith("CLAUDE_CODE") for k in env)
    cwd = Path(call["cwd"]).resolve()
    assert re.fullmatch(r"work-[0-9a-f]{8}", cwd.name)
    assert Path(env["CHANCHI_DB"]).resolve() == cwd / ".state" / "chanchi.db"
    assert re.fullmatch(r"sync-[0-9a-f]{8}", Path(env["CHANCHI_SYNC"]).name)
    assert Path(env["CHANCHI_SYNC"]).resolve().parent == cwd.parent
    first = env["PATH"].split(os.pathsep)[0]
    assert first != str(world.bin)  # the shim folder comes first, the fake harness folder later
    assert str(world.bin) in env["PATH"].split(os.pathsep)
    assert "--add-dir" in call["argv"] and call["argv"][call["argv"].index("--add-dir") + 1] == env["CHANCHI_SYNC"]
    # temporary HOME holds the credential (mode 600), is not the real one, and is gone afterwards
    assert call["cred_exists"] and call["cred_mode"] == "0o600"
    assert json.loads(call["cred_text"]) == {"claudeAiOauth": "fake"}
    assert call["home"] != str(Path.home()) and not Path(call["home"]).exists()
    assert not cwd.exists()  # the scratch folders are removed; artifacts live under CHANCHI_EVALS_DIR


def test_shim_resolves_chanchi_on_the_candidate_path(world, capsys):
    world.config(full_config(candidate=[{"files": {"out.txt": "x"}, "run": "command -v chanchi > shim-path.txt && "
                                         "cat \"$(command -v chanchi)\" > shim-text.txt"}]))
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "reg-a", "--runs", "1")
    assert code == 0, err
    run = next(p for p in world.runs_dir().iterdir() if p.is_dir())
    assert Path((run / "work" / "shim-path.txt").read_text().strip()).name == "chanchi"
    text = (run / "work" / "shim-text.txt").read_text()
    assert f"run --project {world.repo} chanchi" in text
    meta = json.loads((run / "meta.json").read_text())
    assert meta["shim"] == f"uv run --project {world.repo} chanchi"


def test_scratch_sync_reaches_setup_candidate_and_grader(world, capsys):
    world.config(full_config())
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "reg-a", "--runs", "1")
    assert code == 0, err
    call = world.calls("candidate")[0]
    run = next(p for p in world.runs_dir().iterdir() if p.is_dir())
    seen = (run / "sync" / "setup-seen").read_text().strip()
    assert seen == f"{call['env']['CHANCHI_SYNC']}|{call['env']['CHANCHI_DB']}"
    graded = json.loads((run / "sync" / "grade-seen").read_text())
    assert graded["sync"] == call["env"]["CHANCHI_SYNC"] and graded["db"] == call["env"]["CHANCHI_DB"]
    assert graded["final"] == "cand final"
    assert (run / "final_message.txt").read_text() == "cand final"


def test_work_directory_is_git_clean_after_injection_in_both_arms(world, capsys):
    world.config(full_config())
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--cases", "cap-a", "--runs", "1")
    assert code == 0, err
    cands = world.calls("candidate")
    assert len(cands) == 2
    assert [c["git_status"] for c in cands] == ["", ""]
    # the injected paths really exist in the work directory before the candidate starts
    assert cands[0]["wrapper"] is not None and cands[0]["skills"]
    assert cands[1]["wrapper"] is not None and cands[1]["skills"] == []


def test_blinded_names_in_the_work_directory_are_refused(world, capsys):
    setup = world.repo / "evals" / "eval-chanchi-demo" / "cases" / "reg-a" / "setup.sh"
    setup.write_text(SETUP + "echo x > benchmark-notes.txt\n")
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "reg-a", "--runs", "1")
    assert code == 2 and "benchmark-notes.txt" in err and "blind" in err.lower()
    assert world.calls() == []
    # a word listed in blind_allow (and the skill or wrapper folders) pass: `tests/` exists in the default setup
    setup.write_text(SETUP)
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "reg-a", "--runs", "1")
    assert code == 0, err


def test_credential_missing_refuses_naming_the_keychain_item(world, capsys):
    (world.creds / "claude").unlink()
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "reg-a", "--runs", "1")
    assert code == 2 and "Claude Code-credentials" in err
    assert world.calls() == []
    (world.creds / "agy").unlink()
    with pytest.raises(R.RunnerError, match="antigravity"):
        R.read_credential("agy")


def test_agy_credential_prefix_is_decoded(world):
    import base64

    raw = b'{"token": {"access_token": "t"}}'
    (world.creds / "agy").write_bytes(b"go-keyring-base64:" + base64.b64encode(raw))
    assert R.read_credential("agy") == raw


def test_harness_must_be_found_on_path(world, capsys, monkeypatch):
    shutil.rmtree(world.bin)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    world.bin.mkdir()
    code, _, err = world.run(capsys, "--no-ledger", "--yes", "--arm", "with", "--cases", "reg-a", "--runs", "1")
    assert code == 2 and "claude" in err and "PATH" in err


def test_a_failed_harness_run_stops_the_measurement(world, capsys):
    world.config(full_config(candidate=[{"exit": 1, "final": "boom"}]))
    code, _, err = world.run(capsys, "--yes", "--arm", "with")
    assert code == 2 and "failed" in err
    assert len(world.calls("candidate")) == 1
    assert len(world.ledger()) == 0


# ---------------------------------------------------------------- grading, judge, scores, ledger


def baseline_config(with_cap=(True, True, False), without_ok=False, judge=None, triggers=None):
    cands = [{"files": {"out.txt": "x"}}] * 3  # reg-a x3 pass
    cands += [{"files": {"out.txt": "x"}} if ok else {"final": "nothing"} for ok in with_cap]
    cands += [{"files": {"out.txt": "x"}} if without_ok else {"final": "nothing"}] * 3
    return {
        "candidate": cands,
        "judge": judge or [{"final": JUDGE_PASS}],
        "trigger": triggers or [{"load_skill": True}, {"load_skill": True}],
    }


def test_baseline_rows_median_regression_note_ids_and_triggers(world, capsys):
    world.config(baseline_config())
    code, out, err = world.run(capsys, "--arm", "both", "--runs", "3", "--yes")
    assert code == 0, err
    rows = world.ledger()
    assert [r["id"] for r in rows] == [f"{ITEM}-1", f"{ITEM}-2", f"{ITEM}-3"]
    by_arm = {r["arm"]: r for r in rows}
    sha = R.tree_hash(world.repo / "skills" / ITEM)
    cfg = R.load_eval(world.repo, ITEM)
    c_sha = R.cases_sha(world.repo, cfg)
    t_sha = R.triggers_sha(world.repo, cfg)
    for row in rows:
        assert row["item"] == ITEM and row["item_sha"] == sha and row["verdict"] == "baseline"
        assert row["candidate"] == "claude:sonnet:medium"
        assert row["hypothesis"] == "" and row["change"] == "" and row["before"] == "" and row["delta"] == ""
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", row["date"])
    # with: reg-a x3 (1.00) + cap-a x3 (code pass,pass,fail -> scores 1, 1, 1/3 -> median 1.00); 6 candidate runs
    assert by_arm["with"]["median_pass"] == "1.00" and by_arm["with"]["after"] == "1.00"
    assert by_arm["with"]["runs"] == "6"
    w_toks = R.note_tokens(by_arm["with"]["note"])
    assert w_toks == {"regression": "3/3", "cases_sha": c_sha, "cases": "reg-a:1.00,cap-a:1.00"}
    # without / cap-a: every code check fails -> gated score 0/3 = 0.00 (judge not invoked)
    assert by_arm["without"]["median_pass"] == "0.00" and by_arm["without"]["runs"] == "3"
    wo_toks = R.note_tokens(by_arm["without"]["note"])
    assert wo_toks == {"cases_sha": c_sha, "cases": "cap-a:0.00"}
    # triggers: must-load loads, must-not-load loads too -> 1 of 2
    assert by_arm["triggers"]["median_pass"] == "0.50" and by_arm["triggers"]["runs"] == "2"
    assert R.note_tokens(by_arm["triggers"]["note"]) == {"triggers": "1/2", "triggers_sha": t_sha}
    assert last_json(out)["ledger_ids"] == [r["id"] for r in rows]
    # a second baseline appends rows 4-6 (n counts the item's rows)
    world.config(baseline_config())
    assert world.run(capsys, "--arm", "both", "--runs", "3", "--yes")[0] == 0
    assert [r["id"] for r in world.ledger()][3:] == [f"{ITEM}-4", f"{ITEM}-5", f"{ITEM}-6"]


def test_trigger_runs_have_no_agent_and_the_skill_installed(world, capsys):
    world.config(baseline_config())
    assert world.run(capsys, "--yes")[0] == 0
    triggers = world.calls("trigger")
    assert len(triggers) == 2
    for call in triggers:
        argv = call["argv"]
        assert "--agent" not in argv and call["wrapper"] is None
        assert f".claude/skills/{ITEM}/SKILL.md" in call["skills"]
        assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
        assert argv[argv.index("--allowedTools") + 1] == "Bash Read Grep Glob Edit Write Skill"
    assert triggers[0]["argv"][-1] == "Do the demo now."
    assert triggers[1]["argv"][-1] == "Say hello."


def test_hill_climb_rows_kept_and_reverted(world, capsys):
    world.config(baseline_config(with_cap=(True, False, False)))  # cap-a scores 1, 0, 0 -> median 0.00
    assert world.run(capsys, "--arm", "both", "--runs", "3", "--yes")[0] == 0
    base = {r["arm"]: r for r in world.ledger()}
    assert base["with"]["median_pass"] == "0.00"
    cfg = R.load_eval(world.repo, ITEM)
    c_sha = R.cases_sha(world.repo, cfg)

    # an edit not staged is refused, and nothing runs
    (world.repo / "skills" / ITEM / "SKILL.md").write_text("changed but not staged\n")
    world.config({"candidate": [{"files": {"out.txt": "x"}}], "judge": [{"final": JUDGE_PASS}]})
    code, _, err = world.run(capsys, "--yes", "--arm", "with", "--hypothesis", "h1")
    assert code == 2 and "git add skills/" + ITEM in err
    assert world.calls() == [] and len(world.ledger()) == 3

    world.stage_skill_change("better")
    assert world.run(capsys, "--yes", "--arm", "with", "--runs", "3", "--hypothesis", "h1", "--change", "feat/x")[0] == 0
    row = world.ledger()[-1]
    assert row["id"] == f"{ITEM}-4" and row["arm"] == "with" and row["verdict"] == "kept"
    assert (row["hypothesis"], row["change"]) == ("h1", "feat/x")
    assert (row["before"], row["after"], row["delta"], row["median_pass"]) == ("0.00", "1.00", "1.00", "1.00")
    assert row["item_sha"] == R.tree_hash(world.repo / "skills" / ITEM) and row["item_sha"] != base["with"]["item_sha"]
    assert R.note_tokens(row["note"]) == {"regression": "3/3", "cases_sha": c_sha, "cases": "reg-a:1.00,cap-a:1.00"}
    assert row["runs"] == "6" and len(world.ledger()) == 4

    # same median, same regression passes: reverted
    world.stage_skill_change("different")
    assert world.run(capsys, "--yes", "--arm", "with", "--runs", "3", "--hypothesis", "h2")[0] == 0
    row = world.ledger()[-1]
    assert row["verdict"] == "reverted" and (row["before"], row["after"], row["delta"]) == ("1.00", "1.00", "0.00")

    # regression runs passed dropped although the median stays 1.00 is reverted too
    world.stage_skill_change("worse")
    world.config({"candidate": [{"final": "nothing"}] * 3 + [{"files": {"out.txt": "x"}}] * 3,
                  "judge": [{"final": JUDGE_PASS}]})
    assert world.run(capsys, "--yes", "--arm", "with", "--runs", "3", "--hypothesis", "h3")[0] == 0
    row = world.ledger()[-1]
    assert row["verdict"] == "reverted"
    assert R.note_tokens(row["note"])["regression"] == "0/3"


def test_hypothesis_needs_the_with_arm_and_a_baseline(world, capsys):
    code, _, err = world.run(capsys, "--dry-run", "--hypothesis", "h", "--arm", "both")
    assert code == 2 and "--arm with" in err
    code, _, err = world.run(capsys, "--dry-run", "--hypothesis", "h", "--arm", "without")
    assert code == 2 and "--arm with" in err
    code, _, err = world.run(capsys, "--yes", "--arm", "with", "--hypothesis", "h")
    assert code == 2 and "baseline" in err and world.calls() == []
    # Also refuses when a `with` baseline exists but `without` baseline is missing
    world.config(baseline_config())
    assert world.run(capsys, "--yes", "--arm", "with")[0] == 0
    world.config({})
    world.stage_skill_change("edit")
    code, _, err = world.run(capsys, "--yes", "--hypothesis", "h")
    assert code == 2 and "without" in err and world.calls() == []


def test_partial_runs_and_no_ledger_write_no_row(world, capsys):
    world.config(baseline_config())
    assert world.run(capsys, "--yes", "--no-ledger")[0] == 0
    assert world.ledger() == []
    assert world.run(capsys, "--yes", "--cases", "reg-a", "--arm", "with")[0] == 0
    assert world.ledger() == []
    world.config(baseline_config())
    assert world.run(capsys, "--yes", "--runs", "2", "--arm", "with")[0] == 0
    assert len(world.ledger()) == 1
    assert world.run(capsys, "--yes", "--arm", "with")[0] == 0
    assert len(world.ledger()) == 2


def test_unstaged_changes_refuse_a_ledger_row_but_not_no_ledger(world, capsys):
    (world.repo / "skills" / ITEM / "references" / "x.md").write_text("edited\n")
    code, _, err = world.run(capsys, "--yes", "--arm", "with")
    assert code == 2 and f"git add skills/{ITEM}" in err and world.calls() == []
    (world.repo / "skills" / ITEM / "new.md").write_text("untracked\n")
    git(world.repo, "checkout", "--", "skills")
    code, _, err = world.run(capsys, "--yes", "--arm", "with")
    assert code == 2 and "untracked" in err
    assert world.run(capsys, "--yes", "--arm", "with", "--no-ledger", "--cases", "reg-a")[0] == 0
    git(world.repo, "add", "skills")
    assert world.run(capsys, "--yes", "--arm", "with")[0] == 0  # staged additions are fine
    assert len(world.ledger()) == 1


def test_judge_answer_is_retried_once_then_counted_failed(world, capsys):
    cfg = baseline_config()
    cfg["judge"] = [{"final": "I think it is fine."}, {"final": JUDGE_PASS}, {"final": "garbage"}, {"final": "garbage"},
                    {"final": JUDGE_PASS}]
    world.config(cfg)
    assert world.run(capsys, "--yes", "--arm", "with", "--cases", "cap-a", "--runs", "3", "--no-ledger")[0] == 0
    judge_calls = world.calls("judge")
    assert len(judge_calls) == 5  # run 1: 2 judge calls (retry); run 2: 2 (both unparsable); run 3: 1
    results = sorted(p / "result.json" for p in world.runs_dir().iterdir() if p.is_dir())
    data = [json.loads(p.read_text()) for p in results]
    by_n = {d["n"]: d for d in data}
    assert by_n[1]["judge_error"] is None and by_n[1]["score"] == 1.0
    assert by_n[2]["judge_error"] and [c["verdict"] for c in by_n[2]["judge"]] == ["FAIL", "FAIL"]
    assert by_n[2]["score"] == pytest.approx(1 / 3) and by_n[2]["passed"] is False
    assert by_n[3]["score"] == 1.0 and by_n[3]["passed"] is True


def test_judge_verdicts_na_excluded_and_every_criterion_required(world):
    ok = R.parse_judge_answer(
        'text\n```json\n{"criteria": [{"n": 1, "verdict": "PASS", "critique": "a"}, '
        '{"n": 2, "verdict": "n/a", "critique": "b"}]}\n```\nbye', 2)
    assert [c["verdict"] for c in ok] == ["PASS", "N/A"]
    assert R.parse_judge_answer('```json\n{"criteria": [{"n": 1, "verdict": "PASS", "critique": "a"}]}\n```', 2) is None
    assert R.parse_judge_answer('```json\n{"criteria": [{"n": 1, "verdict": "MAYBE", "critique": "a"}, '
                                '{"n": 2, "verdict": "PASS", "critique": "a"}]}\n```', 2) is None
    assert R.parse_judge_answer("no block", 1) is None
    # the last fenced block wins
    two = '```json\n{"criteria": []}\n```\n```json\n{"criteria": [{"n": 1, "verdict": "FAIL", "critique": "z"}]}\n```'
    assert R.parse_judge_answer(two, 1)[0]["verdict"] == "FAIL"
    assert R.score_run([{"criterion": "a", "pass": True}], ok) == 1.0
    assert R.score_run([{"criterion": "a", "pass": False}], ok) == 0.5
    assert R.score_run([], [{"n": 1, "verdict": "N/A", "critique": ""}]) == 0.0


def test_judge_gets_criteria_output_and_a_stripped_transcript(world, capsys):
    cfg = baseline_config()
    cfg["candidate"] = [{"files": {"out.txt": "x"}, "load_skill": True, "final": "the answer"}] * 3
    world.config(cfg)
    code, _, err = world.run(capsys, "--yes", "--arm", "with", "--cases", "cap-a", "--runs", "1", "--no-ledger")
    assert code == 0, err
    judge = world.calls("judge")[0]
    assert judge["name"] == "agy"
    argv = judge["argv"]
    assert argv[argv.index("--agent") + 1] == "agent-chanchi-judge"
    assert argv[argv.index("--model") + 1] == "gemini-4-neon" and argv[argv.index("--effort") + 1] == "high"
    assert "--dangerously-skip-permissions" in argv and argv[-1].startswith("-p=")
    assert re.fullmatch(r"judge-[0-9a-f]{8}", Path(judge["cwd"]).name)
    assert judge["cred_exists"] and json.loads(judge["cred_text"]) == {"token": "fake"}
    assert not Path(judge["home"]).exists()
    assert set(judge["judge_dir_files"]) == {".agents", "criteria.md", "output.md", "transcript.jsonl"}
    assert judge["skills"] == []
    assert "agent-chanchi-judge" in judge["wrapper"] and "rubric" not in judge["criteria"].lower()
    assert judge["criteria"].splitlines()[-3:] == ["1. The cause names why.", "   It continues here.",
                                                   "2. The rule is general."]
    assert "Closing note" not in judge["criteria"] and "For each criterion" not in judge["criteria"]
    assert "the answer" in judge["output"]
    transcript = judge["transcript"]
    assert "Skill" not in transcript and "SKILL TEXT BODY" not in transcript and "Launching skill" not in transcript
    assert ITEM not in transcript  # also removed from the init event's skills list
    assert "echo hi" in transcript  # the other tool calls stay
    raw = (next(p for p in world.runs_dir().iterdir() if p.is_dir()) / "transcript.jsonl").read_text()
    assert "SKILL TEXT BODY" in raw  # the saved candidate transcript is complete


def test_strip_load_events_claude_and_agy_unit():
    item = "skill-x"
    claude = [
        {"type": "system", "subtype": "init", "skills": ["a", item, "b"]},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "loading"},
            {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": item}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
        {"type": "user", "isSynthetic": True, "message": {"content": [{"type": "text", "text": "skill body"}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": f"/w/.claude/skills/{item}/SKILL.md"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "content": "body"}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t3", "name": "Skill", "input": {"skill": "other"}}]}},
        {"type": "result", "result": "end"},
    ]
    stripped = R.strip_load_events("claude", claude, item)
    text = json.dumps(stripped)
    assert "skill body" not in text and '"t1"' not in text and '"t2"' not in text and "SKILL.md" not in text
    assert '"loading"' in text  # a text block next to the removed tool_use stays
    assert '"t3"' in text and stripped[0]["skills"] == ["a", "b"] and stripped[-1]["type"] == "result"
    agy = [
        {"event": "init", "init": {}},
        {"event": "step_update", "step_update": {"step_index": 2, "state": "ACTIVE", "step_type": "tool",
                                                 "tool_name": "read_file",
                                                 "tool_info": {"parameters": {"Path": f"/w/.agents/skills/{item}/SKILL.md"}}}},
        {"event": "step_update", "step_update": {"step_index": 2, "state": "DONE", "step_type": "tool",
                                                 "tool_name": "read_file", "tool_info": {"output": "5 lines"}}},
        {"event": "step_update", "step_update": {"step_index": 3, "state": "DONE", "step_type": "tool",
                                                 "tool_name": "read_file",
                                                 "tool_info": {"parameters": {"Path": "/w/notes.md"}}}},
        {"event": "result", "result": {"response": "end"}},
    ]
    stripped = R.strip_load_events("agy", agy, item)
    assert [e.get("step_update", {}).get("step_index") for e in stripped] == [None, 3, None]
    assert R.load_event_found("agy", agy, item) and not R.load_event_found("agy", stripped, item)
    assert R.load_event_found("claude", claude, item) and not R.load_event_found("claude", [claude[-1]], item)
    only_read = [claude[4]]
    assert R.load_event_found("claude", only_read, item)


# ---------------------------------------------------------------- calibration and rejudge


def calibration_world(world, capsys, judge_verdicts, *, runs=3):
    """A full `--arm both` baseline whose judge answers follow `judge_verdicts` (capability runs only)."""
    cfg = baseline_config(with_cap=(True, True, True), without_ok=True)
    if runs != 3:
        cfg["candidate"] = [{"files": {"out.txt": "x"}}] * (runs * 3)
    cfg["judge"] = [{"final": verdicts(a, b)} for a, b in judge_verdicts]
    world.config(cfg)
    assert world.run(capsys, "--arm", "both", "--runs", str(runs), "--yes")[0] == 0


def fill_sheet(sheet: Path, labels: dict[int, str]):
    text = sheet.read_text()
    for n, label in labels.items():
        text = re.sub(rf"(## Sample {n}\b.*?\nlabel:)[^\n]*(\ncritique:)[^\n]*",
                      lambda m: f"{m.group(1)} {label}{m.group(2)} owner says {label.lower()}", text, count=1,
                      flags=re.DOTALL)
    sheet.write_text(text)


def test_calibration_sheet_hides_arm_and_verdict_and_excludes_all_na(world, capsys):
    # 4 runs per capability case x 2 arms = 8 capability runs (reg-a is never judged)
    pairs = [("PASS", "PASS"), ("FAIL", "PASS"), ("N/A", "N/A"), ("PASS", "PASS"),
             ("FAIL", "FAIL"), ("PASS", "N/A"), ("PASS", "PASS"), ("FAIL", "PASS")]
    cfg = {
        "candidate": [{"files": {"out.txt": "x"}}] * 12,
        "judge": [{"final": verdicts(a, b)} for a, b in pairs],
        "trigger": [{"load_skill": True}, {"load_skill": True}],
    }
    world.config(cfg)
    assert world.run(capsys, "--arm", "both", "--runs", "4", "--yes")[0] == 0
    code, out, err = world.run(capsys, "--calibration-sheet", "--samples", "7")
    assert code == 0, err
    sheet = world.runs_dir() / "calibration-sheet.md"
    text = sheet.read_text()
    summary = last_json(out)
    assert summary["samples"] == 7 and summary["sheet"] == str(sheet)
    assert text.count("## Sample ") == 7 and text.count("\nlabel:") == 7 and text.count("\ncritique:") == 7
    for hidden in ("with-skill", "without", "regression", "capability", "verdict", "reg-a", "cap-a", "judge", ITEM):
        assert hidden not in text.lower(), hidden
    assert "1. The cause names why.\n   It continues here." in text and "> done" in text and "out.txt" in text
    assert "echo hi" in text  # excerpt of the transcript's tool calls
    mapping = json.loads((world.runs_dir() / "calibration-map.json").read_text())
    assert len(mapping) == 7


def test_calibrate_writes_agreement_and_calibration_tsv(world, capsys):
    pairs = [("PASS", "PASS")] * 6
    calibration_world(world, capsys, pairs)
    assert world.run(capsys, "--calibration-sheet")[0] == 0
    sheet = world.runs_dir() / "calibration-sheet.md"
    # 6/6 all-PASS fails on missing owner-label contrast (D14)
    fill_sheet(sheet, {n: "PASS" for n in range(1, 7)})
    code, out, err = world.run(capsys, "--calibrate", str(sheet))
    assert code == 0, err
    summary = last_json(out)
    assert summary == {
        "agree": 6, "total": 6, "has_contrast": False, "calibrated": False,
        "reason": "uncalibrated: no contrast", "file": str(world.repo / "evals" / "eval-chanchi-demo" / "calibration.tsv"),
    }
    tsv = (world.repo / "evals" / "eval-chanchi-demo" / "calibration.tsv").read_text().splitlines()
    assert tsv[0] == "sample\towner_label\tjudge_label\tagree\towner_critique"
    assert len(tsv) == 7 and tsv[1].split("\t")[1:4] == ["PASS", "PASS", "true"]


def test_calibrate_with_ten_samples_and_disagreement(world, capsys):
    # 2 capability cases x 3 runs x 2 arms = 12 capability runs: judge 11 PASS, 1 FAIL
    ev = world.repo / "evals" / "eval-chanchi-demo"
    toml = ev / "eval.toml"
    toml.write_text(toml.read_text().replace('capability = ["cap-a"]', 'capability = ["cap-a", "cap-b"]'))
    shutil.copytree(ev / "cases" / "cap-a", ev / "cases" / "cap-b")
    git(world.repo, "add", "-A")
    cfg = {
        "candidate": [{"files": {"out.txt": "x"}}] * 15,
        "judge": [{"final": verdicts("PASS", "PASS")}] * 11 + [{"final": verdicts("FAIL", "PASS")}],
        "trigger": [{"load_skill": True}, {"load_skill": True}],
    }
    world.config(cfg)
    assert world.run(capsys, "--arm", "both", "--runs", "3", "--yes")[0] == 0
    code, out, err = world.run(capsys, "--calibration-sheet", "--samples", "10")
    assert code == 0, err
    assert last_json(out)["samples"] == 10 and last_json(out)["judge_fail"] == 1
    sheet = world.runs_dir() / "calibration-sheet.md"
    mapping = json.loads((world.runs_dir() / "calibration-map.json").read_text())
    failing = next(n for n, rid in mapping.items()
                   if json.loads((world.runs_dir() / rid / "result.json").read_text())["judge"][0]["verdict"] == "FAIL")
    # 9 PASS + 1 FAIL for owner (contrast present; one disagreement with judge's FAIL -> 9/10 agree)
    labels = {n: "PASS" for n in range(1, 11)}
    other = 1 if int(failing) != 1 else 2
    labels[other] = "FAIL"
    fill_sheet(sheet, labels)
    code, out, err = world.run(capsys, "--calibrate", str(sheet))
    assert code == 0, err
    # failing sample: owner PASS vs judge FAIL (disagree); other sample: owner FAIL vs judge PASS (disagree) -> 8/10!
    assert last_json(out)["agree"] == 8 and last_json(out)["calibrated"] is False
    # Now owner agrees with the judge FAIL on `failing`, and disagrees only on `other` -> 9/10 agree + contrast
    labels[int(failing)] = "FAIL"
    fill_sheet(sheet, labels)
    code, out, err = world.run(capsys, "--calibrate", str(sheet))
    assert code == 0, err
    assert last_json(out) == {**last_json(out), "agree": 9, "total": 10, "has_contrast": True, "calibrated": True,
                               "reason": None}
    rows = (world.repo / "evals" / "eval-chanchi-demo" / "calibration.tsv").read_text().splitlines()[1:]
    assert [r.split("\t")[3] for r in rows].count("false") == 1
    assert next(r for r in rows if r.startswith(f"{failing}\t")).split("\t")[2] == "FAIL"
    # an unlabeled sample is refused
    sheet.write_text(sheet.read_text().replace("label: PASS", "label:", 1))
    code, _, err = world.run(capsys, "--calibrate", str(sheet))
    assert code == 2 and "without a PASS or FAIL label" in err


def test_rejudge_updates_runs_and_uncommitted_rows_then_calibrate_again(world, capsys):
    calibration_world(world, capsys, [("FAIL", "PASS")] * 6)
    before = {r["arm"]: r for r in world.ledger()}
    assert before["with"]["median_pass"] == "0.67" and before["without"]["median_pass"] == "0.67"
    assert world.run(capsys, "--calibration-sheet")[0] == 0
    sheet = world.runs_dir() / "calibration-sheet.md"
    labels = {n: ("FAIL" if n == 1 else "PASS") for n in range(1, 7)}
    fill_sheet(sheet, labels)
    assert world.run(capsys, "--calibrate", str(sheet))[0] == 0
    tsv_path = world.repo / "evals" / "eval-chanchi-demo" / "calibration.tsv"
    assert tsv_path.read_text().count("\ttrue\t") == 1  # only sample 1 agreed

    # the judge now says PASS everywhere (the rubric was reworded): re-judge 6 capability runs only
    world.config({"judge": [{"final": verdicts("PASS", "PASS")}]})
    code, out, err = world.run(capsys, "--rejudge", "--dry-run")
    assert code == 0 and last_json(out) == {**last_json(out), "candidate": 0, "judge": 6, "trigger": 0, "total": 6}
    assert world.calls() == []
    code, out, err = world.run(capsys, "--rejudge")
    assert code == 0, err
    assert len(world.calls("judge")) == 6 and world.calls("candidate") == []
    after = {r["arm"]: r for r in world.ledger()}
    assert after["with"]["median_pass"] == "1.00" and after["with"]["after"] == "1.00"
    assert R.note_tokens(after["with"]["note"])["regression"] == "3/3"
    assert after["without"]["median_pass"] == "1.00"
    assert after["triggers"] == before["triggers"] and after["with"]["id"] == before["with"]["id"]
    assert len(world.ledger()) == 3

    code, out, err = world.run(capsys, "--calibrate", str(sheet))
    assert code == 0, err
    assert last_json(out)["agree"] == 5 and last_json(out)["calibrated"] is True
    assert tsv_path.read_text().count("\ttrue\t") == 5


def test_rejudge_refuses_rows_already_committed(world, capsys):
    calibration_world(world, capsys, [("PASS", "PASS")] * 6)
    git(world.repo, "add", "-A")
    git(world.repo, "commit", "-qm", "rows")
    code, _, err = world.run(capsys, "--rejudge", "--yes")
    assert code == 2 and "committed" in err
    assert len(world.calls("judge")) == 6  # only the baseline's own judge runs; nothing new


def test_rejudge_over_30_needs_yes(world, capsys):
    calibration_world(world, capsys, [("PASS", "PASS")] * 6)
    path = next(world.runs_dir().glob("measurement-*.json"))
    data = json.loads(path.read_text())
    sample_rid = next(rid for rid in data["runs"] if "cap-a" in rid)
    sample_dir = world.runs_dir() / sample_rid
    extra = []
    for i in range(31):
        new_rid = f"extra-cap-{i}"
        shutil.copytree(sample_dir, world.runs_dir() / new_rid)
        extra.append(new_rid)
    data["runs"] = extra
    path.write_text(json.dumps(data))
    code, out, err = world.run(capsys, "--rejudge")
    assert code == 2 and "--yes" in err and last_json(out)["judge"] == 31


# ---------------------------------------------------------------- current rows and the signal


def ledger_row(**kw):
    base = dict.fromkeys(LEDGER_COLUMNS, "")
    base.update(kw)
    return base


def test_current_with_row_rule():
    rows = [
        ledger_row(id="a-1", item="a", item_sha="s1", arm="with", verdict="baseline", median_pass="0.50",
                   candidate="claude:sonnet:medium", note="cases_sha=cs1"),
        ledger_row(id="a-2", item="a", item_sha="s1", arm="without", verdict="baseline", median_pass="0.30",
                   candidate="claude:sonnet:medium", note="cases_sha=cs1"),
        ledger_row(id="a-3", item="a", item_sha="s2", arm="with", verdict="reverted", median_pass="0.40",
                   candidate="claude:sonnet:medium", note="cases_sha=cs1"),
        ledger_row(id="a-4", item="a", item_sha="s3", arm="with", verdict="kept", median_pass="0.80",
                   candidate="claude:sonnet:medium", note="cases_sha=cs1"),
        ledger_row(id="b-1", item="b", item_sha="s2", arm="with", verdict="baseline", median_pass="0.10",
                   candidate="claude:sonnet:medium", note="cases_sha=cs1"),
        ledger_row(id="a-5", item="a", item_sha="s3", arm="triggers", verdict="baseline", median_pass="1.00",
                   candidate="claude:sonnet:medium", note="triggers_sha=ts1"),
    ]
    assert R.current_with_row(rows, "a", "s3")["id"] == "a-4"
    assert R.current_with_row(rows, "a", "s1")["id"] == "a-1"
    assert R.current_with_row(rows, "a", "s2") is None  # reverted rows are never current
    assert R.baseline_without_row(rows, "a")["id"] == "a-2"
    assert R.current_with_row(rows, "a", "s3", candidate="claude:sonnet:medium", cases_sha="cs1")["id"] == "a-4"
    assert R.current_with_row(rows, "a", "s3", candidate="agy:other:low", cases_sha="cs1") is None
    assert R.current_with_row(rows, "a", "s3", candidate="claude:sonnet:medium", cases_sha="cs2") is None
    assert R.baseline_without_row(rows, "a", candidate="claude:sonnet:medium", cases_sha="cs2") is None
    assert R.matching_triggers_row(rows, "a", candidate="claude:sonnet:medium", triggers_sha="ts1")["id"] == "a-5"
    assert R.matching_triggers_row(rows, "a", candidate="claude:sonnet:medium", triggers_sha="ts2") is None


def lesson(tag="zork", **over):
    text = " ".join(f"{tag}{w}" for w in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot"))
    data = {"what_happened": text, "evidence": f"evidence {tag}", "cause": f"cause {tag}",
            "prevention": f"prevention {tag}", "proposal": text, "general_rule": text, "target": "role executor",
            "target_kind": "role", "generality": "agnostic", "severity": "high"}
    data.update(over)
    return data


def chanchi(cwd, env, *args, stdin=None):
    result = subprocess.run([sys.executable, "-m", "chanchi", *args], cwd=cwd, env=env, capture_output=True,
                            text=True, check=False, input=None if stdin is None else json.dumps(stdin))
    assert result.returncode == 0, (args, result.stderr)
    return json.loads(result.stdout)


def test_signal_report_with_a_project_and_a_global_lesson(world, capsys, tmp_path, monkeypatch):
    db = tmp_path / "ops" / "chanchi.db"
    monkeypatch.setenv("CHANCHI_DB", str(db))
    env = {**os.environ, "CHANCHI_DB": str(db)}
    project = tmp_path / "demo-app"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i"],
                   cwd=project, check=True)
    chanchi(project, env, "project", "register")
    who = ("--as", "planner", "--author", "claude:opus:high", "--conversation", "c1")
    p1 = chanchi(project, env, "lesson", "add", *who, "--json", "-", stdin=lesson("p1"))["lesson"]
    chanchi(project, env, "lesson", "repeat", str(p1["id"]), *who, "--evidence", "again")
    tool_lesson = chanchi(project, env, "lesson", "add", *who, "--json", "-",
                          stdin=lesson("p2", target_kind="tool", target="tool chanchi check"))["lesson"]
    chanchi(project, env, "lesson", "repeat", str(tool_lesson["id"]), *who, "--evidence", "again")
    single = chanchi(project, env, "lesson", "add", *who, "--json", "-", stdin=lesson("p3"))["lesson"]
    owner = ("--as", "owner", "--author", "human", "--conversation", "c2")
    g1 = chanchi(tmp_path, env, "lesson", "add", "--global", *owner, "--json", "-",
                 stdin=lesson("g1", target_kind="skill", target="skill skill-chanchi-x"))["lesson"]
    chanchi(tmp_path, env, "lesson", "repeat", str(g1["id"]), *owner, "--evidence", "again")

    # an eval with a rubric: calibrated 5/6 with contrast, regression 1/1, with 1.00 beats without 0.00
    sha = R.tree_hash(world.repo / "skills" / ITEM)
    cfg = R.load_eval(world.repo, ITEM)
    c_sha = R.cases_sha(world.repo, cfg)
    rows = [
        ledger_row(id=f"{ITEM}-1", item=ITEM, item_sha=sha, arm="with", verdict="baseline", median_pass="1.00",
                   after="1.00", note=f"regression=1/1;cases_sha={c_sha};cases=reg-a:1.00,cap-a:1.00",
                   candidate=cfg.candidate_spec, runs="2"),
        ledger_row(id=f"{ITEM}-2", item=ITEM, item_sha=sha, arm="without", verdict="baseline", median_pass="0.00",
                   after="0.00", note=f"cases_sha={c_sha};cases=cap-a:0.00", candidate=cfg.candidate_spec, runs="1"),
    ]
    ledger = world.repo / "evals" / "ledger.tsv"
    ledger.write_text("\t".join(LEDGER_COLUMNS) + "\n" + "".join(
        "\t".join(r[c] for c in LEDGER_COLUMNS) + "\n" for r in rows))
    cal = ["sample\towner_label\tjudge_label\tagree\towner_critique"]
    cal += [f"{n}\tPASS\tPASS\ttrue\tok" for n in range(1, 5)] + ["5\tFAIL\tFAIL\ttrue\tbad", "6\tPASS\tFAIL\tfalse\tno"]
    (world.repo / "evals" / "eval-chanchi-demo" / "calibration.tsv").write_text("\n".join(cal) + "\n")
    git(world.repo, "add", "-A")

    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    report = json.loads(out)
    item = report["items"][ITEM]
    assert item["judge"] == "agy:gemini-4-neon-high:high"
    assert item["calibrated"] == {"agree": 5, "total": 6, "has_contrast": True, "met": True, "reason": None}
    assert item["regression"] == {"passed": 1, "runs": 1, "met": True}
    assert item["capability"] == {"with": 1.0, "without": 0.0, "met": True}
    assert item["in_signal"] is True
    flagged = {entry["id"] for entry in report["lessons"]["flagged"]}
    assert flagged == {p1["id"], g1["id"]}  # 2+ occurrences, prose target kinds; the tool lesson and p3 are not
    assert single["id"] not in flagged and tool_lesson["id"] not in flagged
    assert report["lessons"]["met"] is False and report["met"] is False

    # a global lesson that proposes a check or a single occurrence is not flagged
    chanchi(project, env, "lesson", "review", str(p1["id"]), "--as", "planner", "--author", "claude:opus:high",
            "--conversation", "c9", "--decision", "postpone", "--reason", "later")
    code, out, err = world.run(capsys, "--signal", item=None)
    assert {e["id"] for e in json.loads(out)["lessons"]["flagged"]} == {g1["id"]}


def test_signal_reports_none_judge_and_unmet_conditions(world, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CHANCHI_DB", str(tmp_path / "ops2" / "chanchi.db"))
    ev = world.repo / "evals" / "eval-chanchi-demo"
    toml = (ev / "eval.toml").read_text().split("\n[judge]")[0]
    (ev / "eval.toml").write_text(toml + "\n")
    (ev / "rubric.md").unlink()
    git(world.repo, "add", "-A")
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    report = json.loads(out)
    item = report["items"][ITEM]
    assert item["judge"] == "none" and item["in_signal"] is False
    assert item["regression"]["met"] is False and item["capability"]["met"] is False
    assert report["lessons"] == {"met": True, "flagged": []}
    assert report["met"] is False
    assert report["reason"] == "no signal evals"


def test_unknown_item_and_mode_errors(world, capsys):
    code, _, err = world.run(capsys, "--dry-run", item="skill-chanchi-nope")
    assert code == 2 and "skill-chanchi-nope" in err
    code, _, err = world.run(capsys, "--rejudge", "--signal", item=None)
    assert code == 2
    code, _, err = world.run(capsys, "--dry-run", item=None)
    assert code == 2 and "item" in err


def test_redact_item_hides_the_skill_name_in_judge_and_owner_copies():
    events = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
               "input": {"command": "cat .claude/skills/skill-chanchi-x/references/r.md"}}]}}]
    out, text = R.redact_item(events, "Per skill-chanchi-x I accepted it.", "skill-chanchi-x")
    assert "skill-chanchi-x" not in json.dumps(out) and "skill-chanchi-x" not in text
    assert R.REDACTED in text


# ---------------------------------------------------------------- Rev 5 protocol tests (S7)


def test_arm_auto_reuses_cached_without_and_skips_unchanged_triggers(world, capsys):
    # First baseline under --arm auto: runs with (reg-a, cap-a), without (cap-a), triggers (2)
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}, {"final": "nothing"}],
        "judge": [{"final": JUDGE_PASS}],
        "trigger": [{"load_skill": True}, {"load_skill": False}],
    })
    code, out, err = world.run(capsys)
    assert code == 0, err
    assert len(world.calls("candidate")) == 3 and len(world.calls("trigger")) == 2
    assert [r["arm"] for r in world.ledger()] == ["with", "without", "triggers"]

    # Second run after body-only edit under --arm auto: reuses cached without and skips triggers
    world.stage_skill_change("improved body only")
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}],
        "judge": [{"final": JUDGE_PASS}],
    })
    code, out, err = world.run(capsys)
    assert code == 0, err
    assert len(world.calls("candidate")) == 2 and world.calls("trigger") == []
    assert [r["arm"] for r in world.ledger()] == ["with", "without", "triggers", "with"]


def test_explicit_arms_and_triggers_flags(world, capsys):
    # Explicit --arm with and --arm without skip triggers by default
    code, out, _ = world.run(capsys, "--dry-run", "--arm", "with")
    assert code == 0 and last_json(out)["trigger"] == 0
    code, out, _ = world.run(capsys, "--dry-run", "--arm", "without")
    assert code == 0 and last_json(out)["trigger"] == 0
    # Explicit --triggers forces triggers even on --arm with
    code, out, _ = world.run(capsys, "--dry-run", "--arm", "with", "--triggers")
    assert code == 0 and last_json(out)["trigger"] == 2
    # Explicit --no-triggers suppresses triggers even on --arm both or --arm auto
    code, out, _ = world.run(capsys, "--dry-run", "--arm", "both", "--no-triggers")
    assert code == 0 and last_json(out)["trigger"] == 0
    code, out, _ = world.run(capsys, "--dry-run", "--arm", "auto", "--no-triggers")
    assert code == 0 and last_json(out)["trigger"] == 0
    # Mutual exclusion: --triggers --no-triggers exits non-zero from argparse
    with pytest.raises(SystemExit):
        R.main([ITEM, "--repo", str(world.repo), "--dry-run", "--triggers", "--no-triggers"])


def test_cases_sha_and_triggers_sha_invalidation_and_ignores(world, capsys):
    cfg = R.load_eval(world.repo, ITEM)
    base_c = R.cases_sha(world.repo, cfg)
    base_t = R.triggers_sha(world.repo, cfg)

    # Ignoring __pycache__, *.pyc, .DS_Store inside capability case dir
    cap_dir = cfg.dir / "cases" / "cap-a"
    (cap_dir / "__pycache__").mkdir()
    (cap_dir / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"pyc")
    (cap_dir / "extra.pyc").write_bytes(b"pyc")
    (cap_dir / ".DS_Store").write_bytes(b"ds")
    assert R.cases_sha(world.repo, cfg) == base_c

    # Regression edit and skill body edit do NOT change cases_sha
    (cfg.dir / "cases" / "reg-a" / "prompt.md").write_text("Changed regression prompt.\n")
    (world.repo / "skills" / ITEM / "SKILL.md").write_text("---\nname: skill-chanchi-demo\n---\nChanged body.\n")
    assert R.cases_sha(world.repo, cfg) == base_c
    assert R.triggers_sha(world.repo, cfg) == base_t

    # Editing AGENT.md, rubric.md, or capability file DOES invalidate cases_sha
    agent_md = world.repo / "agents" / "agent-chanchi-executor" / "AGENT.md"
    orig_agent = agent_md.read_text()
    agent_md.write_text(orig_agent + "\nExtra line.\n")
    assert R.cases_sha(world.repo, cfg) != base_c
    agent_md.write_text(orig_agent)
    assert R.cases_sha(world.repo, cfg) == base_c

    (cfg.dir / "rubric.md").write_text("# Rubric\n1. Changed.\n")
    assert R.cases_sha(world.repo, cfg) != base_c

    # Editing SKILL.md frontmatter description or triggers.md invalidates triggers_sha
    (world.repo / "skills" / ITEM / "SKILL.md").write_text(
        "---\nname: skill-chanchi-demo\ndescription: New description.\n---\nBody.\n"
    )
    t_after_desc = R.triggers_sha(world.repo, cfg)
    assert t_after_desc != base_t
    (cfg.dir / "triggers.md").write_text("## Must load\n- Different prompt.\n## Must not load\n- Say hello.\n")
    assert R.triggers_sha(world.repo, cfg) != t_after_desc


def test_adaptive_repeat_unchanged_vs_changed_regression_and_flaky(world, capsys):
    # Baseline: reg-a passes (1.00), cap-a fails code (0.00); without cap-a fails (0.00)
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}, {"final": "nothing"}, {"final": "nothing"}],
        "judge": [{"final": JUDGE_PASS}],
        "trigger": [{"load_skill": True}, {"load_skill": False}],
    })
    assert world.run(capsys)[0] == 0
    assert len(world.calls("candidate")) == 3

    # Unchanged skill: reg-a passes, cap-a still 0.00 -> stays at 1 run per case (2 cand runs)
    world.stage_skill_change("v2")
    world.config({"candidate": [{"files": {"out.txt": "x"}}, {"final": "nothing"}]})
    assert world.run(capsys, "--hypothesis", "no change")[0] == 0
    assert len(world.calls("candidate")) == 2
    assert world.ledger()[-1]["verdict"] == "reverted"

    # cap-a improves on run 1 (1.00 != 0.00): reg-a stays at 1 run, cap-a tops up to 3 runs (--runs 1)
    world.stage_skill_change("v3")
    world.config({
        "candidate": [
            {"files": {"out.txt": "x"}},  # reg-a #1 (unchanged -> 1 run)
            {"files": {"out.txt": "x"}},  # cap-a #1 (1.00 != 0.00 -> top up #2, #3)
            {"files": {"out.txt": "x"}},  # cap-a #2
            {"files": {"out.txt": "x"}},  # cap-a #3
        ],
        "judge": [{"final": JUDGE_PASS}],
    })
    assert world.run(capsys, "--hypothesis", "lift")[0] == 0
    assert len(world.calls("candidate")) == 4
    row = world.ledger()[-1]
    assert row["verdict"] == "kept" and row["runs"] == "4"
    assert R.note_tokens(row["note"])["regression"] == "1/1"

    # With --runs 2 when reg-a fails run 1 & 2, tops up to 3 runs
    world.stage_skill_change("v4")
    world.config({
        "candidate": [
            {"final": "bad"}, {"files": {"out.txt": "x"}}, {"final": "bad"},  # reg-a #1, #2 -> top up #3 -> 1/3
            {"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}},          # cap-a #1, #2 (unchanged 1.00 -> stays 2)
        ],
        "judge": [{"final": JUDGE_PASS}],
    })
    assert world.run(capsys, "--runs", "2", "--hypothesis", "reg fail")[0] == 0
    assert len(world.calls("candidate")) == 5
    row = world.ledger()[-1]
    assert row["verdict"] == "reverted" and R.note_tokens(row["note"])["regression"] == "1/3"


def test_adaptive_repeat_flaky_prior_regression_and_rate_comparison(world, capsys):
    # Baseline has flaky 2/3 regression pass rate; cap-a 0.00; without 0.00
    world.config({
        "candidate": [
            {"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}, {"final": "bad"},  # reg-a x3 -> 2/3
            {"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}},
            {"final": "nothing"}, {"final": "nothing"}, {"final": "nothing"},
        ],
        "judge": [{"final": JUDGE_PASS}],
        "trigger": [{"load_skill": True}, {"load_skill": False}],
    })
    assert world.run(capsys, "--arm", "both", "--runs", "3", "--yes")[0] == 0
    assert R.note_tokens(world.ledger()[0]["note"])["regression"] == "2/3"

    # Next --hypothesis with --runs 1: even though reg-a passes run 1, prior regression < 100% triggers top-up to 3!
    # All 3 pass -> 3/3 > 2/3 -> kept (even though capability stayed 1.00)!
    world.stage_skill_change("fix flaky")
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}] * 4,
        "judge": [{"final": JUDGE_PASS}],
    })
    assert world.run(capsys, "--hypothesis", "fix reg")[0] == 0
    assert len(world.calls("candidate")) == 4  # reg-a x3 + cap-a x1
    row = world.ledger()[-1]
    assert row["verdict"] == "kept" and R.note_tokens(row["note"])["regression"] == "3/3"

    # Now prior regression is 3/3 (rate 1.0). Next --hypothesis has reg-a pass in 1 run (1/1, rate 1.0)
    # and capability unchanged -> 1/1 vs 3/3 is NOT a regression drop, just unchanged (rate 1.0 == 1.0)!
    # Test rate-based kept when capability improves from 0.67 to 1.00 while reg is 1/1 vs prior 3/3:
    # Seed a kept row with cap-a=0.67, reg=3/3
    cfg = R.load_eval(world.repo, ITEM)
    c_sha = R.cases_sha(world.repo, cfg)
    sha = R.tree_hash(world.repo / "skills" / ITEM)
    rows = world.ledger()
    rows.append(ledger_row(
        id=f"{ITEM}-5", date="2026-11-24", item=ITEM, item_sha=sha, arm="with", candidate=cfg.candidate_spec,
        runs="6", median_pass="0.67", before="1.00", after="0.67", delta="-0.33", verdict="kept",
        note=f"regression=3/3;cases_sha={c_sha};cases=reg-a:1.00,cap-a:0.67",
    ))
    R.write_ledger(world.repo / "evals" / "ledger.tsv", rows)
    world.stage_skill_change("cap lift")
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}] * 4,  # reg-a x1 (1/1) + cap-a x3 (1.00)
        "judge": [{"final": JUDGE_PASS}],
    })
    assert world.run(capsys, "--hypothesis", "cap lift")[0] == 0
    last = world.ledger()[-1]
    assert last["verdict"] == "kept" and R.note_tokens(last["note"])["regression"] == "1/1"


def test_timeout_default_and_forwarded_to_context(world, capsys, monkeypatch):
    assert R.Context(repo=world.repo, artifacts=world.evals_dir).timeout == 300
    assert R.build_parser().parse_args([ITEM]).timeout == 300
    seen = []
    orig_launch = R.launch

    def spy_launch(argv, cwd, env, timeout):
        seen.append(timeout)
        return orig_launch(argv, cwd, env, timeout)

    monkeypatch.setattr(R, "launch", spy_launch)
    world.config({"candidate": [{"files": {"out.txt": "x"}}], "judge": [{"final": JUDGE_PASS}]})
    assert world.run(capsys, "--arm", "with", "--cases", "cap-a", "--no-ledger", "--timeout", "42")[0] == 0
    assert seen == [42, 42]  # candidate and judge both received 42
    code, _, err = world.run(capsys, "--timeout", "0")
    assert code == 2 and "--timeout" in err


def test_per_case_median_aggregation_weights_cases_equally():
    results = [
        {"arm": "with", "case": "reg-a", "kind": "regression", "score": 1.0, "passed": True},
        {"arm": "with", "case": "cap-a", "kind": "capability", "score": 0.0, "passed": False},
        {"arm": "with", "case": "cap-a", "kind": "capability", "score": 0.0, "passed": False},
        {"arm": "with", "case": "cap-a", "kind": "capability", "score": 0.0, "passed": False},
        {"arm": "with", "case": "cap-b", "kind": "capability", "score": 1.0, "passed": True},
    ]
    s = R.arm_summary(results, "with")
    # cap-a median is 0.0 (3 runs), cap-b median is 1.0 (1 run) -> median([0.0, 1.0]) = 0.50 (NOT 0.00!)
    assert s["median"] == 0.5
    assert s["runs"] == 5
    assert s["cases"] == {"reg-a": 1.0, "cap-a": 0.0, "cap-b": 1.0}


def test_gated_judge_and_strict_score_monotonicity(world, capsys):
    # Regression never calls judge; code-failed capability skips judge; strict monotonicity vs all-FAIL & unparsable
    # Give cap-a a 2-criterion grade.py (c1, c2) and 2-criterion rubric.md
    ev = world.repo / "evals" / "eval-chanchi-demo"
    (ev / "cases" / "cap-a" / "grade.py").write_text(
        'import json, sys\nfrom pathlib import Path\nw = Path(sys.argv[1])\n'
        'print(json.dumps({"criterion": "c1", "pass": (w / "a.txt").exists(), "detail": "a"}))\n'
        'print(json.dumps({"criterion": "c2", "pass": (w / "b.txt").exists(), "detail": "b"}))\n'
    )
    git(world.repo, "add", "-A")
    world.config({
        "candidate": [
            {"files": {"out.txt": "x"}},                  # reg-a: pass -> no judge
            {"files": {"a.txt": "x"}},                    # cap-a: 1/2 code pass -> gated score 1/(2+2)=0.25, no judge
            {"files": {"a.txt": "x", "b.txt": "x"}},      # cap-a: 2/2 code pass, judge all-FAIL -> 2/(2+2)=0.50
            {"files": {"a.txt": "x", "b.txt": "x"}},      # cap-a: 2/2 code pass, judge unparsable -> 2/(2+2)=0.50
        ],
        "judge": [
            {"final": verdicts("FAIL", "FAIL")},
            {"final": "bad1"}, {"final": "bad2"},
        ],
    })
    assert world.run(capsys, "--arm", "with", "--cases", "reg-a", "--no-ledger")[0] == 0
    assert world.calls("judge") == []

    world.config({
        "candidate": [
            {"files": {"a.txt": "x"}},                    # 1/2 code pass -> skipped judge, score 0.25
            {"files": {"a.txt": "x", "b.txt": "x"}},      # 2/2 code pass, judge all-FAIL -> 0.50
            {"files": {"a.txt": "x", "b.txt": "x"}},      # 2/2 code pass, judge unparsable -> 0.50
        ],
        "judge": [
            {"final": verdicts("FAIL", "FAIL")},
            {"final": "bad1"}, {"final": "bad2"},
        ],
    })
    assert world.run(capsys, "--arm", "with", "--cases", "cap-a", "--runs", "3", "--no-ledger")[0] == 0
    # Run 1 skipped judge (0 calls), run 2 took 1 judge call, run 3 took 2 judge calls (retry) -> 3 total
    assert len(world.calls("judge")) == 3
    results = sorted(
        (json.loads((p / "result.json").read_text()) for p in world.runs_dir().iterdir() if p.is_dir() and "cap-a" in p.name),
        key=lambda r: r["n"],
    )
    assert results[0]["judge"] is None and results[0]["judge_skipped"] == "code_failed"
    assert results[0]["score"] == 0.25 and results[0]["passed"] is False
    assert results[1]["judge_skipped"] is None and results[1]["score"] == 0.5
    assert results[2]["judge_error"] and results[2]["score"] == 0.5
    assert results[0]["score"] < results[1]["score"] and results[0]["score"] < results[2]["score"]


def test_calibration_sheet_collect_and_no_collect_refusal(world, capsys):
    # 1-run baseline gives 2 eligible capability runs (with/cap-a PASS, without/cap-a FAIL); --calibration-sheet without --collect fails
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}],
        "judge": [{"final": JUDGE_PASS}, {"final": verdicts("FAIL", "PASS")}],
        "trigger": [{"load_skill": True}, {"load_skill": False}],
    })
    assert world.run(capsys)[0] == 0
    ledger_before = world.ledger()
    code, _, err = world.run(capsys, "--calibration-sheet")
    assert code == 2 and "--collect" in err

    # --collect runs only the missing 4 capability runs (alternating without/with, judging even code-failed runs)
    world.config({
        "candidate": [{"final": "nothing"}, {"files": {"out.txt": "x"}}] * 2,
        "judge": [{"final": verdicts("FAIL", "FAIL")}, {"final": verdicts("PASS", "PASS")}] * 2,
    })
    code, out, err = world.run(capsys, "--calibration-sheet", "--collect", "--dry-run")
    assert code == 0 and last_json(out)["candidate"] == 4 and last_json(out)["judge"] == 4
    assert world.calls() == []

    code, out, err = world.run(capsys, "--calibration-sheet", "--collect")
    assert code == 0, err
    summary = last_json(out)
    assert summary["samples"] == 6 and summary["judge_pass"] >= 2 and summary["judge_fail"] >= 2
    assert len(world.calls("candidate")) == 4 and len(world.calls("judge")) == 4
    # Baseline ledger rows untouched
    assert world.ledger() == ledger_before
    # Collected runs saved under calibration-runs/
    cal_dirs = [p for p in (world.runs_dir() / "calibration-runs").iterdir() if p.is_dir()]
    assert len(cal_dirs) == 4
    mapping = json.loads((world.runs_dir() / "calibration-map.json").read_text())
    assert sum(1 for v in mapping.values() if v.startswith("calibration-runs/")) == 4

    # 5/6 with contrast passes calibration; 4/6 fails calibration
    sheet = world.runs_dir() / "calibration-sheet.md"
    labels = {}
    for n, ref in mapping.items():
        r = json.loads((world.runs_dir() / ref / "result.json").read_text())
        labels[int(n)] = R.judge_label(r)
    first_key = next(iter(labels))
    labels[first_key] = "FAIL" if labels[first_key] == "PASS" else "PASS"
    fill_sheet(sheet, labels)
    code, out, err = world.run(capsys, "--calibrate", str(sheet))
    assert code == 0 and last_json(out)["agree"] == 5 and last_json(out)["calibrated"] is True

    second_key = [k for k in labels if k != first_key][0]
    labels[second_key] = "FAIL" if labels[second_key] == "PASS" else "PASS"
    fill_sheet(sheet, labels)
    code, out, err = world.run(capsys, "--calibrate", str(sheet))
    assert code == 0 and last_json(out)["agree"] == 4 and last_json(out)["calibrated"] is False
    assert last_json(out)["reason"] == "uncalibrated: low agreement"


def test_rejudge_preserves_code_failed_gated_scores_and_refreshes_cases_sha(world, capsys):
    # Baseline (runs=1): reg-a passes, with/cap-a passes code & judge FAIL, without/cap-a fails code (gated 0.00)
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}, {"final": "nothing"}],
        "judge": [{"final": verdicts("FAIL", "PASS")}],
        "trigger": [{"load_skill": True}, {"load_skill": False}],
    })
    assert world.run(capsys)[0] == 0
    old_c_sha = R.cases_sha(world.repo, R.load_eval(world.repo, ITEM))
    # Collect 5 more calibration runs (some code-failed)
    world.config({
        "candidate": [{"final": "nothing"}, {"files": {"out.txt": "x"}}] * 3,
        "judge": [{"final": verdicts("FAIL", "FAIL")}, {"final": verdicts("PASS", "PASS")}] * 3,
    })
    assert world.run(capsys, "--calibration-sheet", "--collect")[0] == 0

    # Escalate judge in eval.toml (changes cases_sha!)
    ev = world.repo / "evals" / "eval-chanchi-demo"
    toml = ev / "eval.toml"
    toml.write_text(toml.read_text().replace("gemini-4-neon-high", "gemini-4-hydrogen-high"))
    new_c_sha = R.cases_sha(world.repo, R.load_eval(world.repo, ITEM))
    assert new_c_sha != old_c_sha

    # --rejudge re-judges set(cal_refs) | {code-passed baseline cap runs} = 6 (with/cap-a is in both, deduplicated;
    # reg-a and code-failed without/cap-a are NOT re-judged!)
    world.config({"judge": [{"final": verdicts("PASS", "PASS")}]})
    code, out, err = world.run(capsys, "--rejudge")
    assert code == 0, err
    res = last_json(out)
    assert res["rejudged"] == 6 and res["cases_sha"] == new_c_sha
    assert len(world.calls("judge")) == 6

    rows = {r["arm"]: r for r in world.ledger()}
    assert R.note_tokens(rows["with"]["note"])["cases_sha"] == new_c_sha
    assert R.note_tokens(rows["without"]["note"])["cases_sha"] == new_c_sha
    # without/cap-a failed code, so its baseline score remains 0.00 (calibration-runs never mixed in!)
    assert rows["without"]["median_pass"] == "0.00"
    assert rows["with"]["median_pass"] == "1.00"


def test_hypothesis_writes_triggers_row_on_description_change(world, capsys):
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}, {"files": {"out.txt": "x"}}, {"final": "nothing"}],
        "judge": [{"final": verdicts("FAIL", "PASS")}],
        "trigger": [{"load_skill": True}, {"load_skill": False}],
    })
    assert world.run(capsys)[0] == 0
    # Change frontmatter description and stage
    (world.repo / "skills" / ITEM / "SKILL.md").write_text(
        "---\nname: skill-chanchi-demo\ndescription: Updated trigger description.\n---\nNew body.\n"
    )
    git(world.repo, "add", "skills")
    new_t_sha = R.triggers_sha(world.repo, R.load_eval(world.repo, ITEM))
    world.config({
        "candidate": [{"files": {"out.txt": "x"}}] * 4,
        "judge": [{"final": JUDGE_PASS}],
        "trigger": [{"load_skill": True}, {"load_skill": False}],
    })
    code, out, err = world.run(capsys, "--hypothesis", "update description")
    assert code == 0, err
    assert len(world.calls("trigger")) == 2
    rows = world.ledger()
    assert rows[-2]["arm"] == "with" and rows[-2]["verdict"] == "kept"
    trig = rows[-1]
    assert trig["arm"] == "triggers" and trig["verdict"] == "baseline"
    assert trig["before"] == "" and trig["delta"] == ""
    assert trig["hypothesis"] == "update description"
    assert R.note_tokens(trig["note"]) == {"triggers": "2/2", "triggers_sha": new_t_sha}


def test_signal_rejects_mismatched_candidate_or_cases_sha_or_no_contrast(world, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CHANCHI_DB", str(tmp_path / "ops3" / "chanchi.db"))
    sha = R.tree_hash(world.repo / "skills" / ITEM)
    cfg = R.load_eval(world.repo, ITEM)
    c_sha = R.cases_sha(world.repo, cfg)
    rows = [
        ledger_row(id=f"{ITEM}-1", item=ITEM, item_sha=sha, arm="with", verdict="baseline", median_pass="1.00",
                   after="1.00", note="regression=1/1;cases_sha=wrongsha0000;cases=reg-a:1.00,cap-a:1.00",
                   candidate=cfg.candidate_spec, runs="2"),
        ledger_row(id=f"{ITEM}-2", item=ITEM, item_sha=sha, arm="without", verdict="baseline", median_pass="0.00",
                   after="0.00", note=f"cases_sha={c_sha};cases=cap-a:0.00", candidate="other:model:low", runs="1"),
    ]
    ledger = world.repo / "evals" / "ledger.tsv"
    ledger.write_text("\t".join(LEDGER_COLUMNS) + "\n" + "".join(
        "\t".join(r[c] for c in LEDGER_COLUMNS) + "\n" for r in rows))
    cal = ["sample\towner_label\tjudge_label\tagree\towner_critique"] + [
        f"{n}\tPASS\tPASS\ttrue\tok" for n in range(1, 7)
    ]
    (world.repo / "evals" / "eval-chanchi-demo" / "calibration.tsv").write_text("\n".join(cal) + "\n")
    git(world.repo, "add", "-A")

    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    item = json.loads(out)["items"][ITEM]
    assert item["calibrated"]["met"] is False and item["calibrated"]["reason"] == "uncalibrated: no contrast"
    assert item["regression"]["met"] is False
    assert item["capability"]["met"] is False
    assert json.loads(out)["met"] is False


def _make_code_only(eval_dir: Path, *, signal_line: str = "") -> None:
    toml = (eval_dir / "eval.toml").read_text().split("\n[judge]")[0]
    if signal_line:
        toml = toml.replace("\n[candidate]\n", f"\n{signal_line}\n\n[candidate]\n")
    (eval_dir / "eval.toml").write_text(toml + "\n")
    rubric = eval_dir / "rubric.md"
    if rubric.is_file():
        rubric.unlink()


def _write_ledger(repo: Path, rows: list[dict[str, str]]) -> None:
    (repo / "evals" / "ledger.tsv").write_text(
        "\t".join(LEDGER_COLUMNS) + "\n" + "".join("\t".join(r[c] for c in LEDGER_COLUMNS) + "\n" for r in rows)
    )


def test_signal_true_code_only_eval(world, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CHANCHI_DB", str(tmp_path / "ops_s9_1" / "chanchi.db"))
    ev = world.repo / "evals" / "eval-chanchi-demo"
    _make_code_only(ev, signal_line="signal = true")
    cfg = R.load_eval(world.repo, ITEM)
    sha = R.tree_hash(world.repo / "skills" / ITEM)
    c_sha = R.cases_sha(world.repo, cfg)

    # Passing regression (1/1) and capability (with > without) -> met True, reason None
    _write_ledger(world.repo, [
        ledger_row(id=f"{ITEM}-1", item=ITEM, item_sha=sha, arm="with", verdict="baseline", median_pass="1.00",
                   after="1.00", note=f"regression=1/1;cases_sha={c_sha};cases=cap-a:1.00",
                   candidate=cfg.candidate_spec, runs="2"),
        ledger_row(id=f"{ITEM}-2", item=ITEM, item_sha=sha, arm="without", verdict="baseline", median_pass="0.00",
                   after="0.00", note=f"cases_sha={c_sha};cases=cap-a:0.00",
                   candidate=cfg.candidate_spec, runs="1"),
    ])
    git(world.repo, "add", "-A")
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    report = json.loads(out)
    item = report["items"][ITEM]
    assert item["judge"] == "none" and item["calibrated"] is None and item["in_signal"] is True
    assert report["met"] is True and report["reason"] is None

    # Failing regression -> met False
    _write_ledger(world.repo, [
        ledger_row(id=f"{ITEM}-1", item=ITEM, item_sha=sha, arm="with", verdict="baseline", median_pass="1.00",
                   after="1.00", note=f"regression=0/1;cases_sha={c_sha};cases=cap-a:1.00",
                   candidate=cfg.candidate_spec, runs="2"),
        ledger_row(id=f"{ITEM}-2", item=ITEM, item_sha=sha, arm="without", verdict="baseline", median_pass="0.00",
                   after="0.00", note=f"cases_sha={c_sha};cases=cap-a:0.00",
                   candidate=cfg.candidate_spec, runs="1"),
    ])
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    assert json.loads(out)["met"] is False

    # Capability with <= without -> met False
    _write_ledger(world.repo, [
        ledger_row(id=f"{ITEM}-1", item=ITEM, item_sha=sha, arm="with", verdict="baseline", median_pass="0.50",
                   after="0.50", note=f"regression=1/1;cases_sha={c_sha};cases=cap-a:0.50",
                   candidate=cfg.candidate_spec, runs="2"),
        ledger_row(id=f"{ITEM}-2", item=ITEM, item_sha=sha, arm="without", verdict="baseline", median_pass="0.50",
                   after="0.50", note=f"cases_sha={c_sha};cases=cap-a:0.50",
                   candidate=cfg.candidate_spec, runs="1"),
    ])
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    assert json.loads(out)["met"] is False


def test_signal_true_judged_eval_still_requires_calibration(world, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CHANCHI_DB", str(tmp_path / "ops_s9_2" / "chanchi.db"))
    ev = world.repo / "evals" / "eval-chanchi-demo"
    toml = (ev / "eval.toml").read_text()
    (ev / "eval.toml").write_text(toml.replace("\n[candidate]\n", "\nsignal = true\n\n[candidate]\n"))
    cfg = R.load_eval(world.repo, ITEM)
    sha = R.tree_hash(world.repo / "skills" / ITEM)
    c_sha = R.cases_sha(world.repo, cfg)
    _write_ledger(world.repo, [
        ledger_row(id=f"{ITEM}-1", item=ITEM, item_sha=sha, arm="with", verdict="baseline", median_pass="1.00",
                   after="1.00", note=f"regression=1/1;cases_sha={c_sha};cases=cap-a:1.00",
                   candidate=cfg.candidate_spec, runs="2"),
        ledger_row(id=f"{ITEM}-2", item=ITEM, item_sha=sha, arm="without", verdict="baseline", median_pass="0.00",
                   after="0.00", note=f"cases_sha={c_sha};cases=cap-a:0.00",
                   candidate=cfg.candidate_spec, runs="1"),
    ])
    git(world.repo, "add", "-A")

    # Missing calibration.tsv -> met False
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    report = json.loads(out)
    assert report["items"][ITEM]["calibrated"]["met"] is False
    assert report["met"] is False

    # Too few samples (< 6) -> met False
    cal = ["sample\towner_label\tjudge_label\tagree\towner_critique",
           "1\tPASS\tPASS\ttrue\tok",
           "2\tFAIL\tFAIL\ttrue\tok"]
    (ev / "calibration.tsv").write_text("\n".join(cal) + "\n")
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    report = json.loads(out)
    assert report["items"][ITEM]["calibrated"]["met"] is False
    assert report["met"] is False


def test_signal_false_excludes_eval_from_scoped(world, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("CHANCHI_DB", str(tmp_path / "ops_s9_3" / "chanchi.db"))
    ev = world.repo / "evals" / "eval-chanchi-demo"
    toml = (ev / "eval.toml").read_text()
    (ev / "eval.toml").write_text(toml.replace("\n[candidate]\n", "\nsignal = false\n\n[candidate]\n"))
    git(world.repo, "add", "-A")

    # Only signal = false eval exists -> met False, reason "no signal evals"
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    report = json.loads(out)
    assert report["items"][ITEM]["in_signal"] is False
    assert report["met"] is False and report["reason"] == "no signal evals"

    # Add a passing signal = true code-only eval alongside the failing/uncalibrated signal = false eval -> met True
    other_item = "skill-chanchi-other"
    (world.repo / "skills" / other_item).mkdir(parents=True)
    (world.repo / "skills" / other_item / "SKILL.md").write_text("---\nname: skill-chanchi-other\n---\n# Other\n")
    ev2 = world.repo / "evals" / "eval-chanchi-other"
    (ev2 / "cases" / "reg-a").mkdir(parents=True)
    (ev2 / "cases" / "cap-a").mkdir(parents=True)
    for c in ("reg-a", "cap-a"):
        (ev2 / "cases" / c / "prompt.md").write_text("p\n")
        (ev2 / "cases" / c / "setup.sh").write_text("#!/bin/sh\n")
        (ev2 / "cases" / c / "grade.py").write_text("print('{}')\n")
    (ev2 / "triggers.md").write_text("## Must load\n- a\n\n## Must not load\n- b\n")
    (ev2 / "eval.toml").write_text(
        'name = "eval-chanchi-other"\n'
        'item = "skill-chanchi-other"\n'
        'regression = ["reg-a"]\n'
        'capability = ["cap-a"]\n'
        'blind_allow = []\n'
        'signal = true\n\n'
        '[candidate]\n'
        'agent = "agent-chanchi-executor"\n'
        'harness = "claude"\n'
        'model = "sonnet"\n'
        'effort = "medium"\n'
    )
    git(world.repo, "add", "-A")
    cfg2 = R.load_eval(world.repo, other_item)
    sha2 = R.tree_hash(world.repo / "skills" / other_item)
    c_sha2 = R.cases_sha(world.repo, cfg2)
    _write_ledger(world.repo, [
        ledger_row(id=f"{other_item}-1", item=other_item, item_sha=sha2, arm="with", verdict="baseline",
                   median_pass="1.00", after="1.00", note=f"regression=1/1;cases_sha={c_sha2};cases=cap-a:1.00",
                   candidate=cfg2.candidate_spec, runs="2"),
        ledger_row(id=f"{other_item}-2", item=other_item, item_sha=sha2, arm="without", verdict="baseline",
                   median_pass="0.00", after="0.00", note=f"cases_sha={c_sha2};cases=cap-a:0.00",
                   candidate=cfg2.candidate_spec, runs="1"),
    ])
    code, out, err = world.run(capsys, "--signal", item=None)
    assert code == 0, err
    report = json.loads(out)
    assert report["items"][ITEM]["in_signal"] is False
    assert report["items"][other_item]["in_signal"] is True
    assert report["met"] is True and report["reason"] is None


def test_signal_omitted_defaults_to_bool_judge(world):
    # With rubric.md + [judge], signal defaults to True
    cfg_judged = R.load_eval(world.repo, ITEM)
    assert cfg_judged.judge is not None and cfg_judged.signal is True

    # Code-only (no rubric.md), signal defaults to False
    ev = world.repo / "evals" / "eval-chanchi-demo"
    _make_code_only(ev)
    cfg_code = R.load_eval(world.repo, ITEM)
    assert cfg_code.judge is None and cfg_code.signal is False


def test_load_eval_rejects_non_bool_signal(world):
    ev = world.repo / "evals" / "eval-chanchi-demo"
    toml = (ev / "eval.toml").read_text()
    (ev / "eval.toml").write_text(toml.replace("\n[candidate]\n", '\nsignal = "true"\n\n[candidate]\n'))
    with pytest.raises(R.RunnerError, match="must be a boolean"):
        R.load_eval(world.repo, ITEM)


def test_ledger_ids_unique_after_gaps_or_renumbering(world, capsys):
    cfg = R.load_eval(world.repo, ITEM)
    sha = R.tree_hash(world.repo / "skills" / ITEM)
    c_sha = R.cases_sha(world.repo, cfg)
    world.config(full_config())

    # Preserved <item>-3 (gap where -1, -2 were discarded) -> next baseline rows are -4, -5, -6
    _write_ledger(world.repo, [
        ledger_row(id=f"{ITEM}-3", item=ITEM, item_sha="oldsha", arm="with", verdict="baseline", median_pass="0.50",
                   after="0.50", note=f"regression=1/1;cases_sha={c_sha};cases=cap-a:0.50",
                   candidate=cfg.candidate_spec, runs="2"),
    ])
    code, _, err = world.run(capsys)
    assert code == 0, err
    ids = [r["id"] for r in world.ledger()]
    assert ids == [f"{ITEM}-3", f"{ITEM}-4", f"{ITEM}-5", f"{ITEM}-6"]
    assert len(ids) == len(set(ids))

    # Renumbered <item>-1 -> next baseline rows are -2, -3, -4
    world.config(full_config())
    _write_ledger(world.repo, [
        ledger_row(id=f"{ITEM}-1", item=ITEM, item_sha=sha, arm="with", verdict="baseline", median_pass="0.50",
                   after="0.50", note=f"regression=1/1;cases_sha={c_sha};cases=cap-a:0.50",
                   candidate=cfg.candidate_spec, runs="2"),
    ])
    code, _, err = world.run(capsys, "--arm", "both")
    assert code == 0, err
    ids = [r["id"] for r in world.ledger()]
    assert ids == [f"{ITEM}-1", f"{ITEM}-2", f"{ITEM}-3", f"{ITEM}-4"]
    assert len(ids) == len(set(ids))
