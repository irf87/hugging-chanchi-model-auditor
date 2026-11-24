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
| eval | `evals/eval-chanchi-<item>/` | phase 2: from then on every new skill ships with at least one eval case |
| hook | `hooks/hook-chanchi-<n>/` | a harness hook; git hooks are not items |

## Agent source

Frontmatter: `name`, `description` (what it does and what it never does), `scope`
(`main`, `subagent`, `both`), `profile` (`read-only`, `workspace-write`, `orchestrator`),
`install` (optional: `repo` default, or `user` to also compile into installed user harness folders),
`skills: [a, b]`. One `key: value` per line, no comments. The body is the role, harness neutral.
Never put a model in it: the orchestrator picks models with `chanchi recommend`.

After editing a source, run `chanchi agents sync` (inside this repository: `uv run chanchi agents sync`),
and `chanchi agents link --user` when `install: user`, then commit the source and the wrappers.

## Rule or check?

Before adding a sentence that tells agents what they must do, ask whether a test, a ruff rule, a
CLI check or a hook can enforce it. If one can, write the check (its failure message states the
rule and the fix) and do not add the sentence. Text is for judgment; checks are for invariants.

## Size

`AGENTS.md` ≤ 150 lines, each `SKILL.md` and `AGENT.md` ≤ 300 (`tests/test_rules_budget.py`).
Move detail to `docs/` or `references/` and link to it.

## Last step

Run `scripts/check`. It must pass before the change is handed off.
