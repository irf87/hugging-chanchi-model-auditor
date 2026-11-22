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

chanchi is the instrument maker, not the composer: it ships the instruments (the CLI, the agents,
the skills that build items) and helps users build their own. What users make with them is
theirs: their databases and records, their lessons, the projects they take as references, and the
global items built for them that are not exclusive to chanchi. None of it is committed here; it
stays in the user's home or in ignored paths (`.gitignore`). This repository is public.

What the code does, how to install it and how to develop it: `README.md`.
Designs: `docs/designs/<topic>.brief.md` (the request) and `docs/designs/<topic>.md` (the
design), with their reviews in `docs/designs/reviews/<topic>/`. The first design and plans live in
`docs/superpowers/`.

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
  `README.md` and `docs/`. A rule that guides agents is written there, never only
  in one harness's private memory.
- Harness-specific files stay thin wrappers. Never make a feature depend on one
  harness unless an agnostic fallback exists, and never verify a harness's
  capability from memory — check it locally first.

## Items and Other Projects

- An item is agent setup a harness loads or runs: `agent`, `skill`, `eval`, `hook`. chanchi's
  own items are named `<item>-chanchi-<name>`. Items chanchi helps another project create are
  `<item>-chanchi-<project-slug>-<name>` and live only in that project. The user's global items
  are `<item>-chanchi-global-<name>` (`global` is a reserved slug) and live in the user's `SYNC/`,
  never in this repository. Designs: `docs/designs/chanchi-agents-mvp.md`,
  `docs/designs/global-items.md`.
- How other projects use chanchi today: they get skills through `chanchi skills link`, are
  identified from git and `chanchi project register` (chanchi writes nothing into their
  repository except skill links), and only their orchestrating role writes chanchi records, into
  one shared database. Helping them build their own items is a later phase (TODO list in the
  design).

## Working Conventions

- Branch per change (never work on `main` directly), Conventional Commits in
  English; the orchestrating session merges to `main` with `git merge --no-ff` after
  verifying the work.
- The orchestrator plans and audits; executors implement and hand off. Record
  sessions, incidents and verdicts with the `skill-chanchi-session-audit` skill; pick
  executors with `skill-chanchi-model-selection`.
- The author does not judge its own work. Everything the orchestrator writes (designs, briefs,
  rules, skills, agents, lessons) is audited before merge by agents from other conversations,
  which check it against the request and the evidence: three auditors per round, each of a
  different model family when available (otherwise the next one in the user's roster, and the
  round is recorded as degraded), accepted when at least two of three approve (a pass, or a pass with only minor fixes), at most three
  rounds, then the human decides with the disagreement report. Procedure:
  `skill-chanchi-audit-rounds` and `docs/designs/global-items.md`.
- When delegating to another harness, use unique agent names, isolate work in a
  git worktree, and point `CHANCHI_DB` at a scratch database so tests never touch
  the operational one.
- External research (repositories, posts, papers) is adapted, never adopted wholesale: rarely
  does anything cover our goal completely. Verify each claim at its primary source before relying
  on it, and give every design that uses external sources an "Adopt / Adapt / Avoid" section that
  names the source of each item and the reason, so we keep what works and do not repeat what
  failed elsewhere.
- Never commit `external-references/` (local symlinks to reference projects), and never name a
  reference project or write a home path (`/Users/<user>/`, `/home/<user>/`) in a committed file:
  describe it generically ("a consumer project"). `tests/test_privacy.py` enforces both.
- Tests: `uv run pytest`. A database migration commits the SQL file and the
  regenerated `src/chanchi/data/template.db` together (see `README.md`).
