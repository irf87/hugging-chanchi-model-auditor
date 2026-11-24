---
name: skill-chanchi-item-authoring
description: Use when creating or renaming a chanchi item (an agent, skill, eval or harness hook) in this repository. Gives the naming rule, the layout, the agent source fields, and when a rule must be a check instead of text.
---

# chanchi — item authoring

An item is agent setup a harness loads or runs. Design: `docs/designs/chanchi-agents-mvp.md`.

## Names

`<item>-chanchi-<name>`, kebab-case, where `<item>` is `agent`, `skill`, `eval` or `hook`. The
directory name and the frontmatter `name` are the same string. `tests/test_items.py` enforces
this and fails when an operational file names an item that does not exist.

## Layout

| Item | Source | Notes |
|---|---|---|
| agent | `agents/agent-chanchi-<n>/AGENT.md` | wrappers are generated; never edit `.claude/agents`, `.opencode/agents`, `.agents/agents` or `.cursor/agents` by hand |
| skill | `skills/skill-chanchi-<n>/SKILL.md`, optional `references/` | linked into projects by `chanchi skills link` |
| eval | `evals/eval-chanchi-<n>/`: `eval.toml`, `cases/<case>/` (`prompt.md`, `setup.sh`, `grade.py`), optional `rubric.md`, `triggers.md` | every new skill ships with one (`tests/test_evals.py`); after any change to an evaluated skill run `uv run python scripts/run_evals.py <skill>` and commit the ledger row |
| hook | `hooks/hook-chanchi-<n>/` | a harness hook; git hooks are not items |

## Agent source

Frontmatter: `name`, `description` (what it does and what it never does), `scope`
(`main`, `subagent`, `both`), `profile` (`read-only`, `workspace-write`, `orchestrator`),
`install` (optional: `repo` default, or `user` to also compile into installed user harness folders),
`skills: [a, b]`. One `key: value` per line, no comments. The body is the role, harness neutral.
Never put a model in it: the orchestrator picks models with `chanchi recommend`.

After editing a source, run `chanchi agents sync` (inside this repository: `uv run chanchi agents sync`),
and `chanchi agents link --user` when `install: user`, then commit the source and the wrappers.

## Eval source

Structure of `evals/eval-chanchi-<n>/` (required for new skills; grandfathered skills are listed in
`tests/test_evals.py`):

- `eval.toml`: top-level keys `name = "eval-chanchi-<n>"`, `item = "skill-chanchi-<n>"`,
  `regression = ["<case>"]` (at least one), `capability = ["<case>"]` (start with 1 regression + 1
  capability case by default; `[]` only if no capability case exists yet), `blind_allow = [...]`,
  and optional `signal = true|false` placed before `[candidate]`; `[candidate]` with `agent`,
  `harness`, `model`, `effort`; and optional `[judge]` only when `rubric.md` exists, using a
  different model family than the candidate (`chanchi.taxonomy.family_for`).
- `triggers.md`: `## Must load` and `## Must not load` bullet lists.
- `cases/<case>/`: at least one case directory holding `prompt.md` (neutral wording; blinded words
  in `tests/test_evals.py` are banned unconditionally), `setup.sh` (builds starting state; any
  blinded word in `setup.sh` or fixtures must be listed in `blind_allow`), and `grade.py` (reads
  the work directory from `sys.argv[1]` and prints one JSON line per criterion:
  `{"criterion": "<id>", "pass": true|false, "detail": "<text>"}`).

## Hook source

Harness hooks live under `hooks/hook-chanchi-<n>/` (git hooks in `.githooks/` or `.git/hooks/` are
not chanchi items). Suggested harness-agnostic layout:

- An executable hook script (e.g. `hook.sh`, `chmod +x`) that enforces the guardrail (for example,
  running the repository's check command) and exits non-zero with a failure message naming both the
  rule and the fix when it blocks.
- A brief `README.md` stating when the harness invokes it and how it signals a block.

## Rule or check?

Before adding a sentence that tells agents what they must do, ask whether a test, a ruff rule, a
CLI check or a hook can enforce it. If one can, write the check (its failure message states the
rule and the fix) and do not add the sentence. Text is for judgment; checks are for invariants.

## Size

`AGENTS.md` ≤ 150 lines, each `SKILL.md` and `AGENT.md` ≤ 300 (`tests/test_rules_budget.py`).
Move detail to `docs/` or `references/` and link to it.

## Last step

Follow the worktree and branch a brief names, and never work directly on `main` (`AGENTS.md`). For
a direct authoring request inside an already-isolated workspace with no separate brief file, author
the item directly in the current working tree using sensible repository conventions rather than
stopping. Follow your role's commit rules (executors never commit; orchestrators commit source,
wrappers, and ledger rows after checks pass).

Run `scripts/check` when present; otherwise run the verification checks documented in the
repository's `AGENTS.md` (such as its item-naming check and `chanchi agents sync --check`). Checks
must pass before handing off, and the final message must list every file created or changed.
