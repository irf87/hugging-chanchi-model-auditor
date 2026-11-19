# Stage 6: Comprehension Test report

**Target:** `docs/designs/continuous-improvement.md`. FeatureRange 1-781; DetailedRange 782-1051.
**Reviewer:** egm-comprehension (completed). Read the document alone, with no context files and no standard.

## Paraphrase: FeatureRange (lines 1-781)

**What this proposes**
chanchi records audited agent sessions, incidents and model ratings. This design adds "lessons" to it. A lesson is a structured record of a process failure: what happened, evidence, cause, a general rule, and one target place (a role, skill, rules file, hook and so on, at global or project level) where the fix belongs.

Only "writer roles" can record, review and apply lessons. The default writer role is `planner`, set per project or globally. The `human` agent can always do it. A lesson must be reviewed from a different conversation than the one that recorded it. Approval is tracked on the lesson. Each place where the lesson is applied, declined or retired is tracked separately in `lesson_sites`. A person or agent edits the files by hand, tags them `[lesson #N]` and records where.

For this, projects become explicitly registered in the SQLite DB. A command resolves to a project by the longest registered path prefix, then by normalized remote.

The rest of the design covers:
- word-overlap dedup, which blocks near-duplicates;
- an export ordered by generality, then severity, then occurrences;
- one skill, `chanchi-lessons`;
- in stage 2, a per-project inbox of approved agnostic lessons already applied somewhere, plus a read-only `verify` that checks the files against the DB;
- stages 3 and 4, harness hooks that only get a contract here and are blocked on Q1-Q5.

**How the existing system works, per this document**
chanchi is a local CLI with one SQLite DB per machine. It has tables `models`, `changes`, `sessions` and `incidents`, and numbered migrations (001, 003) with automatic `.bak-vN` backups and forward-only versioning. Audits identify a project by a slug taken from the git toplevel folder name, through `detect()`, `identify()` and `ensure()`. Projects are not registered today.

`taxonomy.py` holds the enum sets and `taxonomy.ALL_AGENTS` (`claude`, `agy`, `opencode`, `human`). `modelspec.parse` validates `agent:model[:effort]`. `chanchi recommend` rates models from incidents. `chanchi skills link` symlinks `chanchi-*` skills into projects and home. `cli.py` handlers delegate to `record.py`.

Every section could be paraphrased, so there is no paraphrase-level Blocker.

## Paraphrase: DetailedRange (lines 782-1051)

**What this proposes**
Stage 1 is one branch with these changes:
- migration 004 and a regenerated template DB;
- an English stopword file;
- the new taxonomy sets and six new error codes;
- `projects.py` extensions for registration, resolution and writer roles, plus a locator lookup step in `ensure()`;
- the new pure module `dedup.py`, which holds the thresholds;
- the new module `lessons.py`, which holds the transitions and events;
- the CLI groups `project` and `lesson`, with a shared identity parent parser;
- the skill, a paragraph in the session-audit skill, the README and tests.

Stage 2 is a later branch. It adds inbox, decline, reopen-site and verify to the code, CLI, skill, README and tests. Verification is pytest, a migration run on a copy of the real DB, a manual run of CUJs 1-7, and a skills link check.

**How the existing system works, per this document**
The template DB is committed and drift-tested in `tests/test_db.py`. hatch packages `src/chanchi/data`. `record._required_text` and `db.transaction` already exist. `available_skills()` picks up any `chanchi-*` folder automatically. There is a `--project` flag whose default is the "git toplevel name". `tests/test_no_network.py` enforces that the package imports no network module.

## Findings

### 🟡 Major C-1: The state machine lives in the brief, not here
**Scope:** line 871 ("the state tables of the brief §4"); also 6, 774.
§3 gives per-command preconditions but no full transition table. Open questions: can `approved` go back to `pending` or become `duplicate`? What happens to sites on reopen? Can `retired` be applied again? Inline the table, or state that §3 is complete.

### 🟡 Major C-2: "The five principles" and "the five triggers" are never listed
**Scope:** 569, 682 ("principle 4"), 692.
Alternative H is rejected on "principle 4", which the reader cannot look up. The skill content (item 12, 906-913) is specified as "the five principles; ... the five triggers", so the main deliverable is undefined in this document.

### 🟡 Major C-3: "The source method" is never named or linked
**Scope:** 72-75, 80, 648, 673, 719, 952.
Item 17 ports tests "from the source method's test list plus the additions"; that list is absent. Alternatives D, G and M are justified as departures from it. Link the source, or say item 17's bullets are the complete list.

### 🟡 Major C-4: "Agent" has two meanings, and how `human` is declared is unstated
**Scope:** 99-100, 135, 228-229, 449-450, 455, 668.
"Agent" means both an AI actor and a harness value (`ALL_AGENTS`, `--author agent:model`). The authorization rule "or the `human` agent" depends on the second sense. Not stated: what model a human gives in `--author human:<model>`, whether `--as` is still required, and what stops an AI agent from passing `--author human:...` to bypass the writer check.

### 🟡 Major C-5: Generality and severity values are undefined
**Scope:** 101-102, 394-395, 572.
`agnostic`, `project` and `particular` drive ordering, review scope (463-467), dedup and the inbox, but are never defined; "particular" is never explained. Severity levels have no criteria (572 points to a skill table not in this doc). Also unexplained: a global-origin lesson (NULL origin, line 290) with generality `project`, whose review scope "its origin project" does not exist.

### 🟡 Major C-6: Assumes the reader knows the existing audit model
**Scope:** 167, 173, 433-435, 474-476, 589.
"change", "change ref", "session ref", "latest attempt", and what `ensure()`, `identify()`, `detect()` and `resolve_project()` each do. Add one or two sentences describing the current flow (change → sessions/attempts → incidents; projects created by slug today).

### 🟢 Nit C-7: "Reporter roles", "maintenance conversation", `planner`/`executor` need one-line definitions
Lines 79, 139, 178-180, 574, 579.

### 🟢 Nit C-8: Format of the `target` field is unspecified
Lines 172-173, 231, 301. Does it repeat the kind prefix? Free path or name? How do validation, dedup and verify use it?

### 🟢 Nit C-9: `project list/show/writers` first appear in the plan
Item 6 (846) and item 9 (881-883); not specified in §2.

### 🟢 Nit C-10: Do lesson commands accept `--project`?
Resolution step 2 (427) relies on it; item 9 (885-890) lists `--global` in the parent parser but not `--project`.

### 🟢 Nit C-11: Undefined proper nouns
agy (45), the herdr script (152), zoom-out v1 (632), the seven Goldfish reports and EGM (774, 1051), `recommend`'s exploration list and Hugging Face ordering (715), the launcher that sets `CHANCHI_ROLE` (598).

### 🟢 Nit C-12: Backup and operational vs template DB are assumed knowledge
Lines 615-616, 1040. Point to the README section "Databases and migrations".

## Summary
No Blockers. Both ranges paraphrase cleanly. The main gaps are load-bearing content held outside the document (C-1, C-2, C-3) and undefined core vocabulary (C-4, C-5, C-6).
