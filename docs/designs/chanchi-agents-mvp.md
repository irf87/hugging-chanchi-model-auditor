# chanchi Agents and the Agentic Trust MVP

- **Author:** Iván R
- **Status:** Phase 1 implemented (2026-11-21, change `chanchi-agents-phase1`) and closed
  (2026-11-23): its exit signal holds on the consecutive changes `global-items-phase1`,
  `global-items-phase2` and `global-items-phase3`: every `agent-chanchi-executor` session is
  `accepted` with `gate:first-green` (one attempt superseded by a `retry_reason: env` retry does not
  count), and 10 of those 11 sessions also carry `verify:feature-map` (`chanchi show`; evidence
  in [phase1-exit.md](reviews/chanchi-agents-mvp/phase1-exit.md)). Phase 2 (layer 2, skills
  tested by evals) implemented (2026-11-24, change `chanchi-agents-phase2`) and closed
  (2026-11-24): `uv run python scripts/run_evals.py --signal` returns `met: true` across all three
  signal skills (`skill-chanchi-session-audit`, `skill-chanchi-lessons`,
  `skill-chanchi-item-authoring`), with `skill-chanchi-item-adoption` tracked outside the phase
  signal (`signal = false`) and Condition 4 (lessons) met (`flagged: []`; evidence in
  [phase2-exit.md](reviews/chanchi-agents-mvp/phase2-exit.md)). Phase 3 (safe parallelism) next.
- **Date:** 2026-11-21
- **Revision:** 5 (2026-11-24, accepted in chanchi audit 19 round 1 — 3/3 approvals across
  `anthropic`, `google`, `tencent`; phase-2 closeout reconciliation of remaining plan adaptations
  D3, D4, D6, D10, D11, D16, D19, D20, D21 and Phase 2 exit status; see
  [phase2-exit.md](reviews/chanchi-agents-mvp/phase2-exit.md). Revision 4 was accepted in chanchi
  audit 17 round 2 — 3/3 approvals across `anthropic`, `google`, `tencent`; see
  [chanchi-agents-mvp-code-only-phase2](reviews/chanchi-agents-mvp-code-only-phase2/): owner
  decision Option B — Layer 2 evals are code-graded by default (`grade.py` + `triggers.md`); LLM
  judging (`rubric.md` + `[judge]` + `agent-chanchi-judge`) and judge calibration stay shipped as
  an optional opt-in when deterministic graders cannot verify a qualitative criterion, removing
  mandatory human labeling from phase 2. Revision 3 was accepted in
  chanchi audit 16 round 2 — 3/3 approvals across `anthropic`, `google`, `tencent`; see
  [chanchi-agents-mvp-eval-cost-cut](reviews/chanchi-agents-mvp-eval-cost-cut/): amended Layer 2 eval
  protocol, calibration threshold, cost controls, and phase-2 exit signal. Revision 2 followed two
  independent audits of Revision 1, both `PASS WITH FIXES` and both agreeing with option A:
  [Claude Sonnet](reviews/chanchi-agents-mvp/audit-claude-sonnet.md) and
  [agy Gemini 4 Neon](reviews/chanchi-agents-mvp/audit-agy-gemini-4-neon.md))
- **Brief:** [chanchi-agents-mvp.brief.md](chanchi-agents-mvp.brief.md). This document is complete
  without it.

---

## Overview

chanchi is part of an agentic trust system: harness elements improve themselves so the human
intervenes less and less. This design gives chanchi:

1. **A naming rule for every item** chanchi creates, and the reserved form for items it will later
   help other projects create.
2. **Its own agents**, written once and run by any harness (Claude Code, opencode, agy; Codex
   later).
3. **A minimal version of the three-layer workflow** described by Lauren Tan (Cursor):
   autonomous verification, skills tested by evals, and hard guardrails. Each layer is adapted
   to a Python standard-library CLI and kept as small as the evidence allows.
4. **A three-phase adoption plan** where each step forward needs a signal measured in chanchi's
   own data, not an impression.

How chanchi helps other projects build their own items is out of scope (see
[Other projects](#chanchi-and-other-projects)). What is already known about that interaction is
written down here and summarized in `AGENTS.md`.

### Principles

1. **The shortest path for the agent is the correct one.** A rule that must hold goes into a
   check that fails with a remediation hint, not into more prose.
2. **Deterministic first.** A test, an exit code or a database row decides whenever it can. An
   LLM judge decides only what code cannot check.
3. **One source per fact.** An agent's role is written once; harness files are generated from it
   and a test fails when they drift.
4. **Adapt, do not adopt.** Every borrowed idea names its source and what changed
   ([Adopt / Adapt / Avoid](#adopt--adapt--avoid)).
5. **Fewest agents that work.** Multi-agent runs cost far more tokens than a single agent, and
   coding has fewer parallel tasks than research (Anthropic, *How we built our multi-agent
   research system*). Each agent below exists because the current workflow already uses that role.

### Non-goals

- Items for other projects, a global install of chanchi's agents, and the migration of the two
  consumer projects (TODO, later phase).
- A browser, mobile or UI driver: chanchi is a CLI.
- Cloud evaluation infrastructure: evals run locally through the harness CLIs.
- Recording eval results as model ratings in chanchi (possible later; the ledger keeps the data).

---

## Items and naming

An **item** is a piece of agent setup that a harness loads or runs: an **agent**, a **skill**, an
**eval** or a harness **hook**. Code, tests and scripts follow Python and pytest conventions and
are not items.

| Owner | Form | Example |
|---|---|---|
| chanchi itself | `<item>-chanchi-<name>` | `agent-chanchi-executor`, `skill-chanchi-verify` |
| another project (later phase) | `<item>-chanchi-<project-slug>-<name>` | `skill-chanchi-acme-invoice-format` |

- `<item>` is one of `agent`, `skill`, `eval`, `hook`. A `hook` is a harness hook (for example a
  Claude Code `PreToolUse` script), kept in `hooks/hook-chanchi-<name>/`; none exists in this
  phase. Git hooks have names fixed by git and are not items. `<name>` and `<project-slug>` are kebab-case
  (`[a-z0-9]+(-[a-z0-9]+)*`).
- `<project-slug>` is the slug the project registered with `chanchi project register`. A project
  item lives only in that project's repository, so a check there can tell the slug apart from the
  name by matching the registered slug.
- The directory name and the frontmatter `name` are the same string.

### Renaming the existing skills

The owner decided (2026-11-21) to apply the rule to the existing skills with no exception:

| Old | New |
|---|---|
| `chanchi-model-selection` | `skill-chanchi-model-selection` |
| `chanchi-session-audit` | `skill-chanchi-session-audit` |
| `chanchi-lessons` | `skill-chanchi-lessons` |

- `skills_link.SKILL_PREFIX` becomes `skill-chanchi-`. `SUGGESTED_CONFIG_LINE`, `README.md`, the
  skills' cross-references and `tests/test_skills_content.py` follow.
- **Transition.** Two consumer projects load the skills through path globs
  (`~/.agents/skills/chanchi-*/SKILL.md`, and in one role `~/.claude/skills/chanchi-*`), and
  today's global links point at directories the rename removes. `skills_link` changes as follows:
  - **Repair:** a symlink in a target directory that points into this repository's
    `skills/chanchi-*` (a legacy link, dangling after the rename) is replaced instead of being
    reported as a conflict. Any other existing file or link is still never overwritten.
  - **Compatibility links:** `link --global` creates `chanchi-<n>` → `skill-chanchi-<n>` in
    `~/.agents/skills/` and `~/.claude/skills/`, the two directories the consumers name.
    `link <project>` creates none.
  - **Unlink:** `unlink` recognizes both the new links and the legacy or compatibility links as
    its own.
  - Consumer rule text that says "use the `chanchi-lessons` skill" keeps working, because the
    compatibility directory carries the old name. Consumers change their text and globs in TODO 1,
    after which `link --global --no-compat` removes the compatibility links.
  - Cost during the transition: a harness scanning those two directories may list each skill
    twice.

---

## Agents

### One source, generated wrappers (option A)

Each harness reads agents from its own place, with its own frontmatter and its own meaning for
the body. Verified on the installed binaries (2026-11-21):

| Harness | Project path | Body | Role switches |
|---|---|---|---|
| Claude Code 2.1.330 | `.claude/agents/<n>.md` | a non-empty body replaces the default system prompt; `initialPrompt` is the first user turn of a main session and is ignored for subagents | `tools`, `disallowedTools`, `skills` (preload, subagents only) |
| opencode 2.2.6 | `.opencode/agents/<n>.md` (a nested `<n>/agent.md` becomes id `<n>/agent`) | becomes `system` | `mode: primary\|subagent\|all`, `permission` |
| agy 1.5.14 | `.agents/agents/<n>/agent.md` (only in a trusted folder) | prepended to agy's prompt | `tools` (exact names; omitted means read-only), `subagent`, `skills` |

One Markdown file cannot serve all three, so symlinks are impossible. Hand-written wrappers have
already drifted in both consumer projects. Two independent assessments (the orchestrator and an
agy `gemini-4-neon-high` session that was not told which option was preferred) chose the same
design:

- **Source:** `agents/agent-chanchi-<n>/AGENT.md`, harness-neutral frontmatter plus the role body.
- **`chanchi agents sync`** compiles every source into the three wrappers and writes them;
  **`chanchi agents sync --check`** writes nothing and fails, listing each stale file, when a
  committed wrapper differs from what it would write. The wrappers are committed so a fresh
  clone or worktree runs the agents with no bootstrap.
- The role body is **inlined**, never "read this other file": a wrapper that asks the model to read
  another file costs a turn and fails when the model skips it.

`agents link` (symlinking the compiled wrappers into other repositories or `~`) belongs to the
later phase; this phase only runs agents inside this repository.

### Source format

```markdown
---
name: agent-chanchi-executor
description: Implements one brief in an isolated git worktree and hands off a report. Never commits, merges or writes chanchi records.
scope: both            # main | subagent | both
profile: workspace-write  # read-only | workspace-write | orchestrator
skills: [skill-chanchi-verify]
---

# Executor

<role body, harness neutral>
```

| Field | Meaning | How each harness gets it |
|---|---|---|
| `name`, `description` | identity, routing | copied; opencode takes the id from the file name |
| `scope` | how the agent is launched | Claude: `main` puts the body in `initialPrompt` and leaves the body empty, so Claude keeps its default system prompt; `subagent` and `both` put it in the body. opencode: `mode` primary, subagent or all. agy: `mainAgent: true` for `main` and `both`, `mainAgent: false` for `subagent`; `subagent: true` for `subagent` and `both`. |
| `profile` | what the agent may change | one table in the generator maps it: Claude `disallowedTools`, opencode `permission`, agy exact `tools:` list. `read-only` denies file edits (shell stays available and is restricted by the role text); `workspace-write` and `orchestrator` allow edits. |
| `skills` | skills the agent needs | Native preload only where it is verified live: Claude `skills:` for subagents. agy has both `skills:` and `preloadSkills:` in its frontmatter schema; the implementation verifies which one preloads and pins it. Everywhere else (Claude main sessions, opencode, agy if neither key preloads) the generator writes one line into the body or `initialPrompt`: "Before starting, load these skills: …". |

**How each agent is launched.** On Claude Code, the orchestrator delegates to executors and
researchers as subagents (the `Agent` tool), so their Claude wrappers use the body. Headless
`claude -p --agent` runs of those agents are not part of the workflow; if one is needed, it loses
Claude's default prompt, and that is the only case. On agy and opencode the executor and
researcher run as main sessions in a herdr pane (`agy --agent`, `opencode run --agent`), where
the body is prepended or becomes `system`, so nothing is lost.

No model is written into any wrapper. The orchestrator chooses agent, model and effort per session
with `chanchi recommend` and passes them on the command line (`claude --model`, `opencode run -m`,
`agy --model --effort`). The generated wrappers carry `# generated by chanchi agents sync from
agents/<n>/AGENT.md; do not edit` inside the frontmatter, so the body stays empty where it must.

The tool names for agy's `tools:` list are read from the installed binary when the generator is
built and pinned in its mapping table. After a CLI upgrade, the smoke check in the verification
skill lists the agents with `agy agents` (trusted folder) and `opencode debug agents`. For Claude
Code, which has no command that lists agent definitions (`claude agents` lists running
sessions), the check is one headless run, `claude -p --agent agent-chanchi-researcher "<fixed
question>"`; a pytest check also validates the frontmatter of every generated Claude wrapper.

### The agents of this phase

| Agent | Scope | Profile | Skills | Job |
|---|---|---|---|---|
| `agent-chanchi-orchestrator` | main | orchestrator | model-selection, session-audit, lessons, item-authoring | Plans, writes briefs, picks executors with `chanchi recommend`, audits reports, records sessions and lessons (writer role), merges only after the gate is green and an independent audit passed. |
| `agent-chanchi-executor` | both | workspace-write | verify | Implements one brief in an isolated worktree with a scratch `CHANCHI_DB`; verifies with the feature map; writes a report with each verification command and its last output line; never commits, merges or writes chanchi records. |
| `agent-chanchi-researcher` | both | read-only | none | Reads code, sibling projects, installed binaries and the web; marks every claim VERIFIED (with the command or URL and quote) or UNVERIFIED; writes one report. |

They follow Anthropic's **orchestrator-workers** pattern (*Building effective agents*): a central
model splits the work, delegates bounded tasks and integrates the results. Workers keep their
output in files (worktrees, reports) instead of relaying it through chat.

`agent-chanchi-judge` (`scope: both`, `profile: read-only`, `install: repo`, `skills: []`,
launched on another model family than the candidate) shipped in phase 2 for optional qualitative
evals, completing the **evaluator-optimizer** pattern. Auditors and reviewers stay prompts of
`researcher` or dedicated agents (`agent-chanchi-auditor`, added in global-items) when justified.

### Item-authoring skill

`skill-chanchi-item-authoring` is the guide for creating any chanchi item: the naming rule, the
directory layout, the `AGENT.md` fields, when a rule should be a check instead of text, the
requirement that a new skill gets an eval case before phase 2, and the last step (run
`scripts/check`). Its hard parts are enforced by the gate, so the skill stays short.

---

## Layer 1: autonomous verification

### Feature map

`FEATURE_MAP.md` at the root, one H2 per CLI command group, with the four fields of the feature
files in `poteto/verification-skill-example`, adapted to a CLI, plus the evidence field:

```markdown
## lesson

### Sub-features
- `lesson add`, `lesson similar`, `lesson repeat`, `lesson review`, `lesson apply`,
  `lesson retire`, `lesson reopen`, `lesson export`, `lesson summary`, `lesson show`

### How to get to it
export CHANCHI_DB="$(mktemp -d)/chanchi.db"
cd <a git repository>; chanchi project register --name scratch

### Driving it
chanchi lesson add --as planner --author claude:opus:high --conversation c1 --json - < tests/fixtures/lessons/base.json

### Evidence
JSON `ok: true`, `lesson.status == "pending"`; `chanchi lesson summary` counts 1 pending.
Covered by: tests/test_lessons.py, tests/test_cli_integration.py

### Gotchas
- `--global` requires `generality: agnostic`.
```

A test parses the map and fails when a CLI subcommand has no entry or an entry names a test file
that does not exist. The map is therefore kept current by the gate, not by memory.

### Verification skill

`skill-chanchi-verify` uses the sections of pstack's `create-verification-skill`:

- **Launch:** `uv run chanchi ...` with `CHANCHI_DB` in a fresh temporary directory, never the
  operational database.
- **Doctor:** `chanchi db status` shows the scratch path; `uv run pytest -q` is green before the
  change.
- **Drive:** the feature-map entries the change touches, run as written.
- **Evidence:** the command and the last output line, and the database state the command must
  leave (rows, status), not only the exit code.
- **Cleanup:** remove the scratch directory after the evidence is in the report; never delete
  evidence.
- **Helpers:** the harness smoke checks after a CLI upgrade.

The skill is proven once end to end by an executor on a real change before phase 1 closes.

---

## Layer 2: skills tested by evals

The protocol combines pstack's `eval.md` and `hillclimb.md` with Anthropic's guidance for agent
evals and the Agent Skills evaluation guide. Evals are code-graded by default (`grade.py`); when an
eval opts into a qualitative `rubric.md`, graders run in this order: code first, judge second.

### Layout

```
evals/
  ledger.tsv
  eval-chanchi-session-audit/
    eval.toml                   # candidate agent, harness and model; optional signal flag and [judge]
    cases/<case>/prompt.md      # what the candidate reads: neutral words only
    cases/<case>/setup.sh       # builds the starting state in the work directory
    cases/<case>/grade.py       # code graders: read the end state, print one pass/fail per criterion
    rubric.md                   # optional: judge-only criteria, 3 to 6, pass/fail with a written critique
    triggers.md                 # prompts that must and must not load the skill
scripts/run_evals.py
```

Optional `rubric.md` (present only when `[judge]` is set in `eval.toml`; never copied into a work
directory):

```markdown
# Rubric: skill-chanchi-lessons
For each criterion answer PASS or FAIL, then one or two sentences of critique quoting the output.
1. The cause names why the failure happened, not what was observed.
2. The general rule holds for any case of this kind, not only this one.
3. The target names one place where the fix belongs.
```

`triggers.md`:

```markdown
## Must load
- At the end of this conversation, note what went wrong with the executor's report format.
## Must not load
- Fix the failing test in tests/test_db.py.
```

`eval.toml` names the candidate (for example for `skill-chanchi-session-audit`:
`agent-chanchi-orchestrator` on `agy` / `claude-sonnet-5-5-low`, effort `low`, family `anthropic`)
and an optional `signal = true|false` flag marking whether the item is part of the phase exit signal.
By default, Layer 2 evals are code-graded only (`grade.py` + `triggers.md`, no `rubric.md` or
`[judge]`). When an eval opts into a qualitative `rubric.md`, `eval.toml` also names `[judge]`
(for example `agy` / `gemini-4-hydrogen-high`, effort `high`, family `google`), always of another
model family than the candidate. The runner remains harness-agnostic (`claude` and `agy` supported).

### One run

1. **Isolate.** Copy the case into a new directory `W` = `<tmp>/work-<8 hex>` under the system temp dir
   with a neutral name. `prompt.md` never contains a blinded word (`eval`, `test`, `judge`,
   `experiment`, `rubric`, `score`, `compare`, `benchmark`, `candidate` or `arena`, as a word or
   word prefix, any case; pstack `eval.md`); `setup.sh` and case fixtures may hold a blinded word
   only when explicitly listed in `blind_allow` in `eval.toml` (for domain necessities such as
   `tests/` or `pytest`). The evaluated skill and candidate wrapper are exempt as the subject.
   `CHANCHI_DB` points inside the work directory (`W/.state/chanchi.db`) and `CHANCHI_SYNC` points
   to a sibling scratch folder (`<tmp>/sync-<8 hex>`) so neither the operational database nor the
   user's `SYNC` is touched.
2. **Two arms, with cached `without`.** Run the candidate headless (`claude -p --agent worker`,
   `agy --agent worker -p="<prompt>"`; the runner currently supports `claude` and `agy`) **with the
   skill** and **without it**, so the result measures the skill's lift, not the model. Regression
   cases run only in the with-skill arm. The `without`-skill arm runs once per frozen capability
   harness (`cases_sha`: first 12 hex of SHA-256 over canonical JSON of candidate spec, judge spec
   or `null`, `agents/<agent>/AGENT.md`, sorted capability case files excluding
   `__pycache__`/`.pyc`/`.DS_Store`, and `rubric.md` if present) and is reused across subsequent
   skill changes until that frozen harness changes. Instead of copying the committed wrapper, the
   runner renders the candidate wrapper with `agents_sync.render` from a copy of its source renamed
   to the neutral name `worker` (so `chanchi agents sync` in a work directory never treats it as an
   orphan), with `scope: both` (so on Claude the role is the system prompt) and `skills:` set to
   `[<item>]` in the with-skill arm and `[]` in the without-skill arm, and copies only the
   evaluated skill directory into the with-skill arm (`.claude/skills/` for Claude, `.agents/skills/`
   for agy). When `W/.git` exists, the runner adds `.state/`, the injected wrapper, and the
   injected skill folder to `W/.git/info/exclude` before the candidate starts so `W` starts
   git-clean in both arms. Before launching, the runner sets `HOME` to a temporary directory that
   holds only that harness's credential files (hiding global skill directories such as
   `~/.claude/skills/` and `~/.agents/skills/`), or stops with an error when it cannot isolate it.
   A baseline arm contaminated by a global copy would measure nothing. Headless runs pass each
   harness's non-interactive permissions: Claude uses `--permission-mode acceptEdits --allowedTools
   "Bash Read Grep Glob Edit Write Skill"` (`"Bash Read Grep Glob"` for the read-only judge),
   `--add-dir` for the scratch `SYNC`, and `--` before the prompt; agy uses
   `--dangerously-skip-permissions` and `--add-dir` for the scratch `SYNC`.
   Transcripts are captured from each CLI's structured output: `claude -p --verbose
   --output-format stream-json` (Claude requires `--verbose` with it) and `agy --output-format
   stream-json -p="<prompt>"`.
3. **Repeat adaptively.** **One run per case by default.** A `with`-arm case is repeated up to
   3 runs (keeping the per-case pass rate for regression cases and the per-case score median for
   capability cases) only when its run-1 result differs from the previous matching `baseline`/`kept`
   `with` ledger row (`candidate` + `cases_sha`) for that case, when a regression case fails run 1,
   or when the previous `with` row had `< 100%` regression pass rate (preventing a flaky `2/3`
   regression from passing on a single lucky run). Routine edits that do not change a case stop
   after 1 run; any claimed improvement or regression is automatically confirmed across 3 runs
   before `kept` or `reverted`.
4. **Code graders.** `grade.py` checks the end state, such as the scratch chanchi database (sessions,
   incidents with evidence, verdict), files and exit codes. Regression cases are code-graded only.
5. **Gated judge (optional).** Evals without `rubric.md` skip this step and use code-grader scores
   directly (the default, avoiding both LLM-judge cost and manual calibration). For capability cases
   of an eval that opts into `rubric.md` and `[judge]`, `agent-chanchi-judge` from another model
   family than the candidate runs **only when every code grader passes** (a run that already failed
   code needs no judge). When it runs, the score is
   `(passed_code + passed_rubric_applicable) / (len(code) + total_rubric_applicable)` (`N/A`
   excluded). When the judge is skipped due to a code failure, the run's score is
   `passed_code / (len(code) + len(rubric_criteria))`, guaranteeing that a code-failed run always
   scores strictly lower than any code-passed run (including when all rubric criteria fail or an
   unparsable judge answer fails all rubric criteria after retry, giving
   `C / (C + R) > (C - 1) / (C + R)`). When it runs, the judge reads `rubric.md`, the candidate's
   output and its stripped, redacted transcript, and returns pass, fail or `N/A` per criterion with
   a critique. When comparing two outputs pairwise, it judges both orders and counts only agreement
   (position bias, Zheng et al. 2023).
6. **Triggers on description change.** Each prompt in `triggers.md` is run with the skill installed
   and no agent; the transcript shows whether the skill's `SKILL.md` was read or the skill tool was
   called. Triggers run on the first baseline and whenever the skill's frontmatter `description`,
   `triggers.md`, or candidate (`{harness, model, effort}`) changes (`triggers_sha`); edits to the
   skill body that leave `description` unchanged skip triggers.
7. **Ledger.** One row per executed arm in `evals/ledger.tsv`: `id, date, item, item_sha,
   hypothesis, change, arm, candidate, runs, median_pass, before, after, delta, verdict, note`,
   where `verdict` is `baseline`, `kept` or `reverted` and `item_sha` is the git tree hash of the
   item's directory. `note` stores semicolon-separated tokens without altering the 15-column schema:
   `regression=<passed>/<runs>;cases_sha=<12-hex>;cases=<case>:<val>,...` on `with` rows (regression
   pass rates and capability medians), `cases_sha=<12-hex>;cases=<case>:<val>,...` on `without`
   rows (capability cases only), and `triggers=<passed>/<total>;triggers_sha=<12-hex>` on
   `triggers` rows. Comparisons between `with` and `without` (and adaptive repeat / hill-climb
   `before`) match on `(candidate, cases_sha)` so rows from different frozen harnesses are never
   compared.

### Judge calibration (optional, only when an eval uses a judge)

Code-graded evals require no calibration step: removing mandatory human labeling of synthetic eval
outputs keeps routine skill evaluation autonomous (moving work away from the human). Only when an
eval opts into `rubric.md` and `[judge]` must its judge be calibrated before its verdicts count: the
owner labels **at least 6 outputs** pass or fail once, with a one-line critique, containing
**contrast** (at least one owner `PASS` and at least one owner `FAIL`, preferring ≥ 2 of each when
the pool allows; an all-identical sheet is uncalibrated), and the judge must agree with at most one
disagreement (`total >= 6` and `agree >= total - 1`: ≥ 5 of 6 for small skills, ≥ 9 of 10 for
10-sample sheets; Hamel Husain, *Using LLM-as-a-Judge*). After calibration, the loop needs no human.

Because a 1-run-per-case baseline of 1–2 capability cases yields fewer than 6 judged outputs,
calibration uses a one-time collection step (`--calibration-sheet --collect`) that reuses saved
artifacts first and runs only the missing capability runs (alternating `without` and `with`,
judging code-failed calibration runs solely for calibration so PASS and FAIL examples exist, never
mutating baseline ledger scores). If agreement falls short (`agree < total - 1`), the rubric may
be reworded once (or the judge model escalated before commit) and `--rejudge` re-judges the
calibration samples plus code-passed baseline capability runs, recomputes the uncommitted baseline
`with`/`without` rows from all runs of the latest baseline (preserving gated scores on code-failed
baseline runs), and refreshes `cases_sha` and `cases=` in those rows. If a sheet instead fails on
missing owner-label contrast (`"uncalibrated: no contrast"`), re-judging cannot change owner
labels: collect contrasting samples (or propose a harder capability case) and label a new sheet.

### Improving a skill

Every new skill starts with **1 regression case and 1 capability case**; add more cases only when
a real failure exposes a gap. The hill-climb loop is one change, one measurement, keep or revert.
The entire harness (regression cases, capability cases, graders, rubric) is frozen before the loop
starts; editing a regression case requires a fresh baseline. A change is kept only when
regression cases do not regress (100% of executed regression runs pass once healthy: `1/1` when
unchanged, `3/3` when confirmed) and either the capability median or the regression pass rate
improves. Regression cases (the ones that must always pass) are kept apart from capability cases
(allowed to start low).

### First items under eval

All three phase-2 signal skills run **code-graded only** (`grade.py` + `triggers.md`, no `rubric.md`
or `[judge]`; owner decision 2026-11-24). `agent-chanchi-judge` and the runner's judge/calibration
workflow remain shipped for future skills that genuinely need qualitative judging:

1. `skill-chanchi-session-audit`: it writes audit data, and its end state (reports, incidents with
   evidence, verdict) is fully checkable in the scratch database.
2. `skill-chanchi-lessons`: database fields (non-blank cause/general rule/target, valid enums,
   writer role) and check-first replacement routing (`tool`/`hook`/`permission` + `duplicate`) are
   code-graded in the scratch database.
3. `skill-chanchi-item-authoring`: names, layout, eval structure, and hook isolation are
   code-graded by `grade.py` and the repository naming check.

A fourth backlog skill added before phase 2 (`skill-chanchi-item-adoption`) also ships with a
code-graded eval (`signal = false` in `eval.toml`): it is covered by the ledger gate and its own
regression check, while staying outside the phase-2 exit signal.

### Cost controls

Evals never run in the gate. They run when an evaluated item changes, through
`scripts/run_evals.py <item>`. With code-graded evals by default, 1 regression + 1 capability case,
1 run by default, cached `without`, and description-gated triggers, a routine skill change costs
**2 headless runs** (4 runs when adaptive confirmation repeats a changed case), and a first baseline
costs **7 runs** (3 candidate + 4 triggers; 0 judge runs, 0 calibration runs). Evals that opt into
a `rubric.md` + `[judge]` add 1–2 gated judge runs per measurement (up to 3–4 with adaptive
confirmation) plus a one-time calibration collection (~8–12 runs). The runner prints the
planned counts (initial and adaptive worst-case `max_total`) and refuses `max_total > 30` without
`--yes`. Because neither `claude` nor `agy` CLI exposes a `--max-turns` flag (verified locally
2026-11-23; `agy` exposes `--print-timeout`, while a uniform Python subprocess timeout preserves
harness parity), the runner caps runaway turns with a default per-run timeout of `300s`
(configurable via `--timeout`). The same caps apply when chanchi helps another project evaluate
its own items (TODO 4).

The gate only reads the ledger: from phase 2 it fails when an evaluated item's current `item_sha`
has no `kept` or `baseline` row, with the hint to run the command above. `tree_hash(path)` computes
git's recursive tree SHA-1 over git-tracked and staged files in the item directory (blobs
`100644`/`100755`, subtrees `40000`, ignoring untracked files), and the runner's CLI refuses to
write a ledger row while the item directory has unstaged or untracked changes. There is no
exemption for text-only edits: a skill's text is its behavior, so any change to an evaluated item's
directory needs a new ledger row. `tests/test_evals.py` also enforces that every new skill in
`skills/` has an eval directory with at least one case (exempting only the pre-phase-2
`GRANDFATHERED` set: `skill-chanchi-audit-rounds`, `skill-chanchi-model-selection`,
`skill-chanchi-verify`).

---

## Layer 3: hard guardrails

### The gate

`scripts/check` is the single entry point: `uv run ruff check` and `uv run pytest -q` (ruff is
added to the `dev` dependency group with its rule selection in `pyproject.toml`). It prints a
warning when `git config core.hooksPath` is not `.githooks` or `git config merge.ff` is not
`false`.

- **Local, blocking:** `.githooks/pre-merge-commit` and `.githooks/pre-push` run
  `scripts/check`. Git skips `pre-merge-commit` on a fast-forward, so merges into `main` use
  `--no-ff` (written in `AGENTS.md` and the orchestrator role, and made the default per clone by
  `git config merge.ff false`). Per-clone setup: `git config core.hooksPath .githooks` and
  `git config merge.ff false` (documented in `README.md` and checked by the warning).
- **CI mirror:** `.github/workflows/check.yml` runs `scripts/check` on every push, which catches a
  `--no-verify`.

Every failing check prints the rule it enforces and the command that fixes it. The error is the
documentation the agent reads at the moment it needs it (OpenAI, *Harness engineering*).

### Checks

Existing checks stay (template database at the latest migration, schema matches migrations,
commands named in skills exist, no network module, thin `CLAUDE.md`). New ones:

| # | Check | Catches |
|---|---|---|
| 1 | **Item names and references.** Every directory in `agents/`, `skills/`, `evals/`, `hooks/` matches `<item>-chanchi-<name>` with the right `<item>`, its frontmatter `name` equals the directory, and every `agent-chanchi-*` / `skill-chanchi-*` / `eval-chanchi-*` / `hook-chanchi-*` named in an operational file (`AGENTS.md`, `CLAUDE.md`, `README.md`, `FEATURE_MAP.md`, `agents/`, `skills/`, `evals/` — skipping `evals/*/cases/**` and `evals/*/triggers.md`, whose prompts may name fictional or planned items, while keeping `eval.toml` and `rubric.md` checked) exists. `docs/` is excluded: designs name planned and example items. | wrong names, renames that leave dead references |
| 2 | **Wrappers in sync** (`chanchi agents sync --check`). | hand edits to generated files, a source changed without regenerating |
| 3 | **Feature map coverage.** Every CLI subcommand has an entry; every `Covered by` file exists. | features an agent cannot find |
| 4 | **Runtime stays stdlib.** `pyproject.toml` `dependencies` is empty and `src/chanchi` imports only the standard library and itself (extends the no-network test). | a dependency added by reflex |
| 5 | **Import layers** (an AST test, no new dependency). Leaf modules (`errors`, `timeutil`, `dedup`, `hfsignals`) import no other chanchi module except `errors`; no module except `__main__` imports `cli`; only `cli` imports `render`. | layering erosion |
| 6 | **Ruff against frequent agent shortcuts:** unused imports and names (`F`), bare and blind excepts (`E722`, `BLE001`), `try`-`except`-`pass` (`S110`), commented-out code (`ERA001`), `print` outside `cli.py`, `render.py`, `scripts/`, `evals/*` and `tests/*` (`T20`), mutable defaults (`B006`). Ruff is a dev dependency only. | silent failures, dead code, debug output |
| 7 | **Rules budget.** `AGENTS.md` stays at or under 150 lines and each `SKILL.md` / `AGENT.md` at or under 300; a longer file must move detail into `docs/` or `references/`. | rules files that grow until they are ignored |

### Repeated corrections become checks

The path already exists: a failure becomes a chanchi lesson (`skill-chanchi-lessons`). A lesson
whose `occurrences` reaches 2 is reviewed with one question first: can a check enforce it? If yes
and its `target_kind` is not already `tool`, `hook` or `permission`, the reviewer does not approve
it (because `chanchi lesson review` cannot change another conversation's `target_kind`): instead,
the reviewer records a replacement lesson with that `target_kind` and `replaces` listing the
original (adding `--force-new` if reported as a duplicate), then reviews the original as
`duplicate --of <new id>`. The prose rule is never added. The review section of
`skill-chanchi-lessons` carries this procedure.

---

## Architecture

```
AGENTS.md                      rules map for every harness (≤150 lines)
FEATURE_MAP.md                 layer 1
agents/agent-chanchi-*/AGENT.md     agent sources
.claude/agents/agent-chanchi-*.md   generated, committed
.opencode/agents/agent-chanchi-*.md generated, committed
.agents/agents/agent-chanchi-*/agent.md  generated, committed
skills/skill-chanchi-*/SKILL.md     skills (renamed)
evals/eval-chanchi-*/, evals/ledger.tsv   layer 2 (phase 2)
src/chanchi/agents_sync.py     generator and profile mapping table
scripts/check                  the gate
scripts/run_evals.py           eval runner (phase 2)
.githooks/pre-merge-commit, .githooks/pre-push
.github/workflows/check.yml    CI mirror
tests/test_items.py, test_agents_sync.py, test_feature_map.py, test_layers.py, test_rules_budget.py
```

| Where | What runs |
|---|---|
| Repository | sources, generated wrappers, feature map, evals, gate |
| Local, every merge and push | `scripts/check` through git hooks |
| Local, on demand | `scripts/run_evals.py` (spends tokens), `chanchi agents sync` |
| CI | `scripts/check` on push (same script, no tokens) |

---

## Adopt / Adapt / Avoid

Sources were opened and quoted by a research session on 2026-11-21.

| Decision | Item | Source | Reason |
|---|---|---|---|
| Adopt | Candidate blinding word list, isolated directories, hidden rubric of 3-6 criteria held back from candidates | pstack `skills/poteto-mode/playbooks/eval.md` | Direct fit; costs nothing |
| Adopt | One change, one measurement, keep or revert; frozen harness; ledger columns | pstack `playbooks/hillclimb.md` | Direct fit |
| Adopt | Launch, Doctor, Drive, Evidence, Cleanup, Helpers; evidence survives cleanup; prove once end to end | pstack `skills/create-verification-skill/SKILL.md` | Direct fit |
| Adapt | Feature file fields (Sub-features, How to get to it, Driving it, Gotchas) | `poteto/verification-skill-example` | Written for a web UI with a driver script; for a CLI, "driving" is the command line and we add Evidence and Covered by |
| Adapt | Cross-family judge | pstack `eval.md`; Gu et al. 2024 survey | Zheng et al. 2023 could not confirm self-preference; Wataoka et al. show judges also favor low-perplexity text from other models. We keep cross-family, add both-order judging, code graders first, and calibration against owner labels |
| Adapt | Pass/fail with a written critique; calibration against expert labels | Hamel Husain, *Using LLM-as-a-Judge* | Calibration reduced to one 6–10-label pass per rubric (`total >= 6`, `agree >= total - 1`) |
| Adapt | With-skill vs without-skill arms; trigger checks | Agent Skills evaluation guide (agentskills.io) | 1+1 cases to start, 1 run by default (adaptive up to 3 on change), cached `without` per frozen harness, triggers only when `description` changes |
| Adapt | Code graders before model graders; regression vs capability sets | Anthropic, *Demystifying evals for AI agents* | Our end state lives in SQLite, so most criteria are code-checkable |
| Adapt | Mechanical enforcement with remediation in the error; `AGENTS.md` as a short map | OpenAI, *Harness engineering*; Böckeler, Martin Fowler site | Our budget is 150 lines, not 100: the file also carries the harness entry-point table |
| Adapt | Orchestrator-workers, evaluator-optimizer | Anthropic, *Building effective agents* | Three agents now, the judge in phase 2 |
| Avoid | Adding prose rules for repeated corrections | OpenAI; pstack `poteto-mode` ("Encode Lessons in Structure") | Large instruction files rot and crowd context |
| Avoid | Many agents by default | Anthropic, multi-agent research system | Token cost; coding parallelizes less than research |
| Avoid | Hand-written per-harness wrappers | two consumer projects (drifted) | Missing roles in some harnesses |
| Avoid | Cursor-only features (`pstack-models.mdc`, `Task` arguments, `/loop`, `agent-transcripts/`), JS linters, browser and mobile MCP drivers | research digest | Not portable or not relevant to a Python CLI |
| Avoid | Trusting the third-party research report | verification on 2026-11-21 | Six of its claims were false (playbook counts, frontmatter fields, attributions, release numbers) |

---

## Adoption plan

Each signal is read from chanchi (`chanchi show`, `chanchi stats`, `chanchi lesson summary`) or
from git, never from an impression. The orchestrator, the only chanchi writer, records what the
signals need:

- `chanchi session start ... --tags agent-chanchi-<agent>` names the agent the session ran as.
- `chanchi session audit ... --notes` carries fixed tokens when they apply: `gate:first-green`
  (the gate passed on its first run after the audit, with no fix by the owner) and
  `verify:feature-map` (the executor verified through the feature map with no instruction beyond
  the brief).

`skill-chanchi-session-audit` documents the tag and the tokens.

### Phase 1: local, supervised

Items: naming rule and checks 1, 4-7; ruff as a dev dependency; skill rename with the repair,
compatibility and unlink changes; `chanchi agents sync` and check 2; the three agents;
`skill-chanchi-item-authoring`; `FEATURE_MAP.md`, `skill-chanchi-verify` and check 3;
`scripts/check`, the git hooks (blocking from the start: the deterministic checks are cheap and
green) and the CI mirror (it costs no tokens and catches `--no-verify` from the first day);
`AGENTS.md` section on items and other projects. The owner reviews each merge.

**Signal to move on:** three consecutive changes whose executor sessions carry the tag
`agent-chanchi-executor`, each audited with verdict `accepted` and the note `gate:first-green`,
and at least one with the note `verify:feature-map`.

### Phase 2: automatic verification and guardrails

Items: `agent-chanchi-judge` (shipped for optional qualitative evals); code-graded evals for the
three skills, `scripts/run_evals.py`, the ledger and its gate check; the "can a check enforce it?"
question in lesson review.

**Signal to move on:** for every signal skill (`signal = true` in `eval.toml`):
1. if the eval opts into `rubric.md` + `[judge]`, its judge is calibrated (`total >= 6`,
   `agree >= total - 1`, and label contrast: at least one owner `PASS` and one owner `FAIL`);
   code-graded evals require no judge calibration (phase 2's three signal skills run code-graded
   only, owner decision 2026-11-24);
2. its regression cases pass 100% of executed runs (`1/1` when unchanged, `3/3` when confirmed);
3. its capability median with the skill beats the cached arm without it (matching `candidate` and
   `cases_sha`);
4. no pending lesson with 2 or more occurrences proposes a prose rule where a check is possible.

### Phase 3: safe parallelism

Items: several executors at once, each in its own worktree with its own scratch database; the
orchestrator merges one at a time, each behind the gate; `chanchi recommend` with the exploration
budget chooses the executors.

**Signal that it holds:** five changes delivered with parallel sessions and no gate failure on
`main` after a merge, and no incident of a session touching another session's worktree.

---

## chanchi and other projects

### The contract today

1. **Distribution.** `chanchi skills link <project>` symlinks chanchi's skills into the project's
   `.agents/skills/` and `.claude/skills/`; `--global` does it in `~` (and agy's global skills
   directory). It prints one line for the project's rules or `openspec/config.yaml`. Today both
   consumers use the global links only.
2. **Identity.** Commands derive the project from git; `chanchi project register` stores the slug
   and the writer roles only in chanchi's database. Apart from the skill links, chanchi writes
   nothing into the project's repository.
3. **One writer.** Only the orchestrating role (planner) writes to chanchi: it selects models,
   records sessions, incidents and verdicts, and records lessons. Executors, auditors and reviewers
   report; they never write chanchi records.
4. **One database for every project** (`~/.local/share/chanchi/chanchi.db`); executors and tests
   use a scratch `CHANCHI_DB`.

### TODO (later phase)

1. Migrate the consumer projects: skill paths to `skill-chanchi-*`, link `skill-chanchi-lessons`,
   register the projects, add the writer and reporter lines; then remove the compatibility links.
2. `chanchi agents sync` on a consumer's own `agents/` sources, with the project-slug naming and
   the same `--check` for their gate.
3. `chanchi agents link` to install chanchi's own agents (for example the item builder) into a
   consumer or `~`.
4. An item-builder agent and skill that help a project create its own
   `<item>-chanchi-<slug>-<name>` items, including their feature map and evals.
5. Decide how a project's lessons, evals and ledger relate to chanchi's database (stage 2 of the
   lessons design already covers lesson inboxes).
6. Decide where the global items chanchi builds for a user (not exclusive to chanchi) live. They
   belong to the user, like the database, so they are never committed to this repository: they go
   to the user's home or to a path in `.gitignore` (owner's rule, 2026-11-21).

---

## Risks

| Risk | Mitigation |
|---|---|
| A harness upgrade renames tools or paths | Mapping table in one module; smoke check in `skill-chanchi-verify`; the generator test pins the expected output |
| agy ignores workspace agents in an untrusted folder | Worktree launches answer the trust prompt first (already in the delegation procedure); the smoke check lists agents |
| A Claude `both` agent run as a main session loses the default prompt | Documented; `scope: main` exists for agents that run as main sessions |
| Duplicate skill listings during the rename transition | Compatibility links only in `~/.agents/skills` and `~/.claude/skills`, removed by TODO 1 |
| Ruff flags existing code | Fix findings in the same change; per-file ignores only with a reason comment |
| Eval cost | Evals run only when an evaluated item changes; code-graded by default (optional judge gated on passing code when a rubric is present), 1+1 cases to start, 1 run/case default (adaptive up to 3 on change), cached `without`, triggers only on `description` change, 300s default timeout; the gate reads the ledger |
| Single-run baseline variance & optional 6-sample calibration noise | Default 1 run/case can let a noisy baseline flip `with > without`, and optional 6-sample calibration (when an eval opts into a judge) has lower statistical power than 10 samples; mitigated by label-contrast requirement (≥ 1 owner PASS and ≥ 1 owner FAIL), adaptive 3-run confirmation on any changed/failing case, and re-measuring near-ties with `--runs 3 --arm both` |
| Code-only evals do not automatically grade free-text prose quality | Mitigated by checking all structured end states (SQLite rows, evidence fields, git files, checks) via `grade.py`, auditing free-text outputs in real operational sessions, and keeping optional `rubric.md` + `agent-chanchi-judge` ready when a future skill genuinely needs qualitative judging |

## Verification plan

1. `scripts/check` is green on the branch, and red on purpose for one seeded violation per new
   check (each with its remediation message).
2. `chanchi agents sync` on a clean tree changes nothing; editing a wrapper by hand makes
   `--check` fail.
3. `opencode debug agents` and `agy agents` (trusted folder) list the three agents; for Claude Code
   the generated wrappers pass the frontmatter test.
4. One headless smoke run per harness of `agent-chanchi-researcher` answering a fixed question
   about the repository; on Claude Code this is also the proof that the wrapper loads.
5. Skill preload is checked live once per harness and launch mode (Claude main and subagent, agy
   `skills:` versus `preloadSkills:`, opencode), and the generator's table records the result.
6. In a temporary `HOME` holding today's legacy links, `chanchi skills link --global` repairs
   them, creates the compatibility links, and the consumer globs `~/.agents/skills/chanchi-*`
   and `~/.claude/skills/chanchi-*` resolve; `unlink` removes all of them. One consumer harness
   loads a skill through a compatibility link.
7. Phase 1's exit signal is read from `chanchi show` for the three changes.
8. Phase 2's exit signal is read from `uv run python scripts/run_evals.py --signal`
   ([phase2-exit.md](reviews/chanchi-agents-mvp/phase2-exit.md)).
