"""Layer 2 checks: eval layout, blinding, skill coverage, ledger hash, and runner contract."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from chanchi.taxonomy import family_for

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_evals import LEDGER_COLUMNS, read_ledger, tree_hash  # noqa: E402

GRANDFATHERED = {
    "skill-chanchi-audit-rounds",
    "skill-chanchi-model-selection",
    "skill-chanchi-verify",
}

BLINDED_WORDS = (
    "eval",
    "test",
    "judge",
    "experiment",
    "rubric",
    "score",
    "compare",
    "benchmark",
    "candidate",
    "arena",
)
BLINDED_RE = re.compile(r"\b(?:" + "|".join(BLINDED_WORDS) + r")[a-z0-9]*", re.IGNORECASE)
D22_NAMES = ("W", "CHANCHI_DB", "CHANCHI_SYNC", "FINAL_MESSAGE_FILE", "grade.py")


def _eval_dirs(root: Path = ROOT) -> list[Path]:
    evals_root = root / "evals"
    if not evals_root.is_dir():
        return []
    return sorted(p for p in evals_root.glob("eval-chanchi-*") if p.is_dir())


def _require_non_empty_str(data: dict, key: str, where: str) -> str:
    val = data.get(key)
    assert isinstance(val, str) and val.strip(), (
        f"{where}: missing or empty string key {key!r}. Add {key!r} to eval.toml."
    )
    return val


def _require_str_list(data: dict, key: str, where: str) -> list[str]:
    val = data.get(key)
    assert isinstance(val, list) and all(isinstance(x, str) and x.strip() for x in val), (
        f"{where}: key {key!r} must be a list of strings. Set {key} = [...] in eval.toml."
    )
    return val


def check_eval_layout(eval_dir: Path, root: Path = ROOT) -> dict:
    """Validate one eval directory against D1 and D2."""
    toml_path = eval_dir / "eval.toml"
    rel = str(eval_dir.relative_to(root)) if eval_dir.is_relative_to(root) else str(eval_dir)
    assert toml_path.is_file(), f"{rel}: missing eval.toml. Create {rel}/eval.toml per D1."
    cfg = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    name = _require_non_empty_str(cfg, "name", rel)
    assert name == eval_dir.name, (
        f"{rel}/eval.toml: name {name!r} must equal directory name {eval_dir.name!r}. "
        "Fix name in eval.toml."
    )

    item = _require_non_empty_str(cfg, "item", rel)
    skill_manifest = root / "skills" / item / "SKILL.md"
    assert skill_manifest.is_file(), (
        f"{rel}/eval.toml: item {item!r} is not an existing skill in skills/. "
        "Set item to an existing skill-chanchi-<name>."
    )

    cand = cfg.get("candidate")
    assert isinstance(cand, dict), f"{rel}/eval.toml: missing [candidate] table. Add [candidate]."
    assert "signal" not in cand, (
        f"{rel}/eval.toml: 'signal' must be a top-level boolean placed before [candidate] "
        "(never nested under [candidate]). Move 'signal = true|false' above [candidate]."
    )
    if "signal" in cfg:
        assert isinstance(cfg["signal"], bool), (
            f"{rel}/eval.toml: 'signal' must be a boolean (true or false). "
            "Set 'signal = true' or 'signal = false'."
        )
    for key in ("agent", "harness", "model", "effort"):
        _require_non_empty_str(cand, key, f"{rel}/eval.toml [candidate]")

    regression = _require_str_list(cfg, "regression", f"{rel}/eval.toml")
    assert len(regression) >= 1, (
        f"{rel}/eval.toml: at least one regression case is required. Add a case to regression = [...]."
    )
    capability = _require_str_list(cfg, "capability", f"{rel}/eval.toml")
    _require_str_list(cfg, "blind_allow", f"{rel}/eval.toml")

    for case in [*regression, *capability]:
        case_dir = eval_dir / "cases" / case
        for fname in ("prompt.md", "setup.sh", "grade.py"):
            assert (case_dir / fname).is_file(), (
                f"{rel}/cases/{case}: missing {fname}. Every listed case requires prompt.md, setup.sh and grade.py."
            )

    triggers = eval_dir / "triggers.md"
    assert triggers.is_file(), f"{rel}: missing triggers.md. Create {rel}/triggers.md."
    trig_text = triggers.read_text(encoding="utf-8")
    for heading in ("## Must load", "## Must not load"):
        assert re.search(rf"^{re.escape(heading)}\s*$", trig_text, re.MULTILINE), (
            f"{rel}/triggers.md: missing heading {heading!r}. Add both '## Must load' and '## Must not load'."
        )

    has_rubric = (eval_dir / "rubric.md").is_file()
    has_judge = "judge" in cfg
    assert has_judge == has_rubric, (
        f"{rel}: [judge] in eval.toml must be present if and only if rubric.md exists "
        f"(rubric.md={has_rubric}, [judge]={has_judge}). Add or remove [judge] / rubric.md."
    )
    if has_judge:
        judge = cfg["judge"]
        assert isinstance(judge, dict), f"{rel}/eval.toml: [judge] must be a table."
        for key in ("harness", "model", "effort"):
            _require_non_empty_str(judge, key, f"{rel}/eval.toml [judge]")
        cand_family = family_for(cand["model"])
        judge_family = family_for(judge["model"])
        assert cand_family is not None, (
            f"{rel}/eval.toml: unknown candidate model family for {cand['model']!r} (fail closed). "
            "Use a model whose family taxonomy.family_for recognizes."
        )
        assert judge_family is not None, (
            f"{rel}/eval.toml: unknown judge model family for {judge['model']!r} (fail closed). "
            "Use a model whose family taxonomy.family_for recognizes."
        )
        assert cand_family != judge_family, (
            f"{rel}/eval.toml: judge family {judge_family!r} must differ from candidate family {cand_family!r}. "
            "Pick a judge model from another family."
        )

    return cfg


def check_blinding(eval_dir: Path, root: Path = ROOT) -> None:
    """Statically verify D6 blinding on prompt.md, setup.sh and case fixtures."""
    cfg = tomllib.loads((eval_dir / "eval.toml").read_text(encoding="utf-8"))
    allow = {w.lower() for w in cfg.get("blind_allow", [])}
    cases_dir = eval_dir / "cases"
    if not cases_dir.is_dir():
        return
    for case_dir in sorted(p for p in cases_dir.iterdir() if p.is_dir()):
        for file_path in sorted(p for p in case_dir.rglob("*") if p.is_file()):
            if file_path.name == "grade.py":
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            rel = file_path.relative_to(root) if file_path.is_relative_to(root) else file_path
            matches = [m.group(0) for m in BLINDED_RE.finditer(text)]
            if file_path.name == "prompt.md":
                assert not matches, (
                    f"{rel}: prompt.md must never contain blinded words (found {matches}). "
                    "Replace them with neutral domain wording."
                )
            else:
                disallowed = [w for w in matches if w.lower() not in allow]
                assert not disallowed, (
                    f"{rel}: contains blinded word(s) {disallowed} not in blind_allow. "
                    "Reword them or add them to blind_allow in eval.toml."
                )


def check_skills_have_evals(
    root: Path = ROOT, grandfathered: set[str] | None = None
) -> None:
    """D11: every skill not in GRANDFATHERED has an eval directory with at least one case."""
    exempt = GRANDFATHERED if grandfathered is None else grandfathered
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if skill_dir.name in exempt:
            continue
        expected_name = f"eval-{skill_dir.name.removeprefix('skill-')}"
        eval_dir = root / "evals" / expected_name
        cases_dir = eval_dir / "cases"
        has_case = cases_dir.is_dir() and any(p.is_dir() for p in cases_dir.iterdir())
        assert eval_dir.is_dir() and (eval_dir / "eval.toml").is_file() and has_case, (
            f"Skill {skill_dir.name} has no eval with at least one case. "
            f"Create evals/{expected_name}/ with eval.toml and at least one case."
        )


def check_ledger(root: Path = ROOT) -> None:
    """D10: every evaluated item's current tree hash has a kept or baseline row in evals/ledger.tsv."""
    ledger_path = root / "evals" / "ledger.tsv"
    assert ledger_path.is_file(), (
        "evals/ledger.tsv is missing. Create it with the D9 header row."
    )
    rows = read_ledger(ledger_path)
    for eval_dir in _eval_dirs(root):
        cfg = tomllib.loads((eval_dir / "eval.toml").read_text(encoding="utf-8"))
        item = cfg["item"]
        sha = tree_hash(root / "skills" / item)
        matched = any(
            row["item"] == item
            and row["item_sha"] == sha
            and row["arm"] == "with"
            and row["verdict"] in {"baseline", "kept"}
            for row in rows
        )
        assert matched, (
            f"{item} changed (tree {sha}) and has no kept or baseline row in evals/ledger.tsv. "
            f"Run: uv run python scripts/run_evals.py {item}, then commit the row."
        )


def check_readme_evals_contract(readme_path: Path = ROOT / "README.md") -> None:
    """D22: README.md documents the runner contract and every D22 name."""
    text = readme_path.read_text(encoding="utf-8")
    assert "## Evals" in text, "README.md is missing an '## Evals' section."
    section = text.split("## Evals", 1)[1].split("\n## ", 1)[0]
    assert "docs/designs/chanchi-agents-mvp.md" in section, (
        "README.md Evals section must point to docs/designs/chanchi-agents-mvp.md."
    )
    missing = [name for name in D22_NAMES if not re.search(rf"\b{re.escape(name)}\b", section)]
    assert not missing, (
        f"README.md Evals section is missing D22 runner contract name(s): {missing}. "
        "Document them in README.md."
    )


def test_ledger_header_exists():
    ledger = ROOT / "evals" / "ledger.tsv"
    assert ledger.is_file(), "evals/ledger.tsv must exist."
    header = ledger.read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert tuple(header) == LEDGER_COLUMNS


def test_evals_layout():
    for eval_dir in _eval_dirs(ROOT):
        check_eval_layout(eval_dir, ROOT)


def test_evals_blinding():
    for eval_dir in _eval_dirs(ROOT):
        check_blinding(eval_dir, ROOT)


def test_every_new_skill_has_eval():
    check_skills_have_evals(ROOT)


def test_ledger_matches_current_item_trees():
    check_ledger(ROOT)


def test_readme_documents_runner_contract():
    check_readme_evals_contract(ROOT / "README.md")


# --- Fixture helpers and seeded-violation tests ---


def _build_valid_fixture(root: Path, *, with_rubric: bool = True) -> Path:
    skill_dir = root / "skills" / "skill-chanchi-demo"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: skill-chanchi-demo\n---\n", encoding="utf-8")
    (skill_dir / "references" / "ref.md").write_text("ref\n", encoding="utf-8")

    eval_dir = root / "evals" / "eval-chanchi-demo"
    case_dir = eval_dir / "cases" / "case-one"
    case_dir.mkdir(parents=True)
    (case_dir / "prompt.md").write_text("Do the thing in this repository.\n", encoding="utf-8")
    (case_dir / "setup.sh").write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
    (case_dir / "grade.py").write_text("print('ok')\n", encoding="utf-8")
    (eval_dir / "triggers.md").write_text(
        "## Must load\n- Do the demo.\n## Must not load\n- Say hi.\n", encoding="utf-8"
    )
    judge_block = (
        '\n[judge]\nharness = "agy"\nmodel = "gemini-4-neon-high"\neffort = "high"\n'
        if with_rubric
        else ""
    )
    if with_rubric:
        (eval_dir / "rubric.md").write_text("# Rubric\n1. Check it.\n", encoding="utf-8")
    (eval_dir / "eval.toml").write_text(
        'name = "eval-chanchi-demo"\n'
        'item = "skill-chanchi-demo"\n'
        'regression = ["case-one"]\n'
        'capability = []\n'
        'blind_allow = ["tests"]\n'
        '\n[candidate]\n'
        'agent = "agent-chanchi-executor"\n'
        'harness = "claude"\n'
        'model = "sonnet"\n'
        'effort = "medium"\n'
        + judge_block,
        encoding="utf-8",
    )
    (root / "evals" / "ledger.tsv").write_text("\t".join(LEDGER_COLUMNS) + "\n", encoding="utf-8")
    return eval_dir


def test_tree_hash_matches_git_rev_parse(tmp_path):
    repo = tmp_path / "repo"
    skill = repo / "skills" / "skill-chanchi-demo"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (skill / "references" / "notes.md").write_text("notes\n", encoding="utf-8")
    script = skill / "references" / "helper.sh"
    script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    script.chmod(0o755)

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init"], cwd=repo, env=env, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, env=env, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, env=env, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, env=env, check=True, capture_output=True)

    expected = subprocess.run(
        ["git", "rev-parse", "HEAD:skills/skill-chanchi-demo"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tree_hash(skill) == expected
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "junk.pyc").write_bytes(b"x")
    (skill / ".DS_Store").write_bytes(b"x")
    assert tree_hash(skill) == expected, "untracked files must not change the tree hash (D10)"


def test_layout_check_passes_and_catches_violations(tmp_path):
    eval_dir = _build_valid_fixture(tmp_path)
    check_eval_layout(eval_dir, tmp_path)

    # Seed same-family judge violation
    toml_path = eval_dir / "eval.toml"
    orig = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(orig.replace("gemini-4-neon-high", "opus"), encoding="utf-8")
    with pytest.raises(AssertionError, match="judge family .* must differ"):
        check_eval_layout(eval_dir, tmp_path)

    # Seed unknown judge model family (fail closed)
    toml_path.write_text(orig.replace("gemini-4-neon-high", "mystery-model"), encoding="utf-8")
    with pytest.raises(AssertionError, match="unknown judge model family"):
        check_eval_layout(eval_dir, tmp_path)

    # Seed rubric without [judge]
    toml_path.write_text(orig.split("\n[judge]")[0] + "\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="rubric.md"):
        check_eval_layout(eval_dir, tmp_path)


def test_blinding_catches_prompt_and_unallowed_setup_words(tmp_path):
    eval_dir = _build_valid_fixture(tmp_path, with_rubric=False)
    setup = eval_dir / "cases" / "case-one" / "setup.sh"
    setup.write_text("#!/usr/bin/env bash\nmkdir -p tests\n", encoding="utf-8")
    check_blinding(eval_dir, tmp_path)  # "tests" is in blind_allow

    # Seed unallowed blinded word in setup.sh
    setup.write_text("#!/usr/bin/env bash\necho rubric\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="rubric"):
        check_blinding(eval_dir, tmp_path)
    setup.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")

    # Seed blinded word in prompt.md (never allowed, even if in blind_allow)
    prompt = eval_dir / "cases" / "case-one" / "prompt.md"
    prompt.write_text("Run the tests now.\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="prompt.md must never contain blinded words"):
        check_blinding(eval_dir, tmp_path)


def test_new_skill_without_eval_fails(tmp_path):
    _build_valid_fixture(tmp_path, with_rubric=False)
    check_skills_have_evals(tmp_path, grandfathered=set())

    (tmp_path / "skills" / "skill-chanchi-new").mkdir(parents=True)
    with pytest.raises(AssertionError, match="evals/eval-chanchi-new/"):
        check_skills_have_evals(tmp_path, grandfathered=set())


def test_ledger_check_fails_when_item_changed(tmp_path):
    _build_valid_fixture(tmp_path, with_rubric=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, env=env, check=True)
    subprocess.run(["git", "add", "skills"], cwd=tmp_path, env=env, check=True)
    sha = tree_hash(tmp_path / "skills" / "skill-chanchi-demo")
    with pytest.raises(AssertionError, match=f"skill-chanchi-demo changed \\(tree {sha}\\)"):
        check_ledger(tmp_path)

    # Add baseline row -> passes
    row = [
        "skill-chanchi-demo-1",
        "2026-11-23",
        "skill-chanchi-demo",
        sha,
        "",
        "",
        "with",
        "claude:sonnet:medium",
        "3",
        "1.00",
        "",
        "1.00",
        "",
        "baseline",
        "regression=3/3",
    ]
    ledger = tmp_path / "evals" / "ledger.tsv"
    ledger.write_text("\t".join(LEDGER_COLUMNS) + "\n" + "\t".join(row) + "\n", encoding="utf-8")
    check_ledger(tmp_path)


def test_layout_signal_key(tmp_path):
    eval_dir = _build_valid_fixture(tmp_path, with_rubric=False)
    toml_path = eval_dir / "eval.toml"
    orig = toml_path.read_text(encoding="utf-8")

    # Valid top-level signal = true and signal = false placed before [candidate]
    for val in ("true", "false"):
        toml_path.write_text(orig.replace("\n[candidate]\n", f"\nsignal = {val}\n\n[candidate]\n"), encoding="utf-8")
        cfg = check_eval_layout(eval_dir, tmp_path)
        assert cfg["signal"] is (val == "true")

    # Non-bool top-level signal = "yes" fails
    toml_path.write_text(orig.replace("\n[candidate]\n", '\nsignal = "yes"\n\n[candidate]\n'), encoding="utf-8")
    with pytest.raises(AssertionError, match="must be a boolean"):
        check_eval_layout(eval_dir, tmp_path)

    # Nested signal = true inside [candidate] fails
    toml_path.write_text(orig + "signal = true\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="top-level boolean placed before \\[candidate\\]"):
        check_eval_layout(eval_dir, tmp_path)
