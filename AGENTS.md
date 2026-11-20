# chanchi — Agent Instructions

Harness-agnostic instructions for any AI coding agent working on this repository
(Claude Code, agy/Antigravity, opencode, Codex, Cursor, …). This file is the single
source of truth for project rules.

## Harness Entry Points

Every harness must receive this file automatically at session start, never by
trusting the model to "read AGENTS.md". Add a harness-specific file only when the
harness cannot load `AGENTS.md` by itself, and keep it a thin wrapper that never
restates or overrides these rules (`tests/test_agent_rules.py` guards this).

| Harness | How it loads `AGENTS.md` | Verified |
|---|---|---|
| agy CLI / Antigravity app | Natively (also reads `GEMINI.md` if present and merges both) | agy 1.5.13 canary test; app 2.33.0 session self-report, 2026-11-20 |
| Claude Code | Does not read `AGENTS.md`; `CLAUDE.md` imports it with `@AGENTS.md` | claude canary test, 2026-11-20 |
| opencode | Natively; never reads `CLAUDE.md`, even when `AGENTS.md` is missing | opencode 2.2.6 canary test, 2026-11-20 |
| Codex | Natively | documented |

Do not add a `GEMINI.md`: Antigravity already loads `AGENTS.md`, so it would only
add a second, drifting source. Skills are exposed per harness by
`chanchi skills link`: `.agents/skills/` (opencode, agy) and `.claude/skills/`
(Claude Code).

## Purpose

chanchi is part of an agentic trust system: through continuous improvement, the
elements of a harness — rules, skills, workflows, hooks and agents — improve
themselves so that human intervention keeps shrinking. The human steers each
project with the decisions that matter; agents handle the rest. Agentic
micromanagement does not work with people and does not work with agentic LLMs
either, so every design choice here should move work away from the human, not
toward them.

What the code does, how to install it and how to develop it: `README.md`.
Design: `docs/superpowers/specs/`.

## Core Rules

### 1. The human is the bottleneck

- Propose and solve. Reach a working solution with the minimum human
  intervention: decide from the request, the code, the docs and sensible
  defaults, and state the decision you took instead of asking for it.
- Before asking anything, check whether it truly needs a human. Only ask for
  decisions that are genuinely the human's: product direction, priorities,
  irreversible or outward-facing actions, and trade-offs no evidence can settle.
- When asked "which do you recommend?", answer with a recommendation.

### 2. At most 3 questions at a time

- Never put more than 3 questions or decisions in front of the human at once;
  more than that cannot be understood and answered well.
- If more than 3 remain after filtering (rule 1), ask them in blocks of 3,
  most consequential first, and fold each answer in before the next block.
- Each question must stand on its own, give a recommended option, and say what
  changes depending on the answer.

### 3. Language

- Talk to the human in the language they prefer (currently Spanish).
- Everything else is in English: code, comments, docs, specs, skills, rules,
  commit messages, branch names, reports, chanchi records, and every
  conversation or brief exchanged with other harnesses, agents or subagents.

### 4. Harness agnostic

- This project, like the projects that use it, must work with any harness.
  Every harness that edits this repository must stay compatible with the others.
- Put shared knowledge in agnostic places: this file, `skills/` (the source of
  truth for chanchi skills, exposed to harnesses through `chanchi skills link`),
  `README.md` and `docs/`.
- Harness-specific files stay thin wrappers. Never make a feature depend on one
  harness unless an agnostic fallback exists, and never verify a harness's
  capability from memory — check it locally first.

## Working Conventions

- Branch per change (never work on `main` directly), Conventional Commits in
  English; the orchestrating session merges to `main` after verifying the work.
- The orchestrator plans and audits; executors implement and hand off. Record
  sessions, incidents and verdicts with the `chanchi-session-audit` skill; pick
  executors with `chanchi-model-selection`.
- When delegating to another harness, use unique agent names, isolate work in a
  git worktree, and point `CHANCHI_DB` at a scratch database so tests never touch
  the operational one.
- Never commit `external-references/` (local symlinks to reference projects).
- Tests: `uv run pytest`. A database migration commits the SQL file and the
  regenerated `src/chanchi/data/template.db` together (see `README.md`).
