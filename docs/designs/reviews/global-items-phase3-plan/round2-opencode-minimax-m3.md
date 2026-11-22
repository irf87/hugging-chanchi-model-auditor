VERDICT: PASS WITH FIXES

Audit of `docs/superpowers/plans/2026-11-22-global-items-phase3.md` (commit `b9b93d5`, Revision 2,
branch `docs/gi3-plan`), including the verbatim `agent-chanchi-item-builder` source in Task 4.

Method: read the plan (Revision 2) against Revision 1 (`git diff 0334f88 b9b93d5`), the design
(`docs/designs/global-items.md`, Revision 4), `AGENTS.md`, the phase-2 plan and gate record, and
the current code (`items.py`, `sync.py`, `projects.py`, `lessons.py`, `taxonomy.py`,
`agents_sync.py`, `audits.py`, `harnesses.py`, `catalog.py`, `scoring.py`, `cli.py`, `db.py`,
`errors.py`, `migrations/`), plus `tests/test_db.py`, `test_privacy.py`, `test_feature_map.py`,
`test_rules_budget.py`, `test_agent_rules.py` and `skills/skill-chanchi-audit-rounds/SKILL.md`.
Cheap facts were re-run locally: the baseline suite (`uv run pytest -q` → 716 passed), the builder's
frontmatter parsed with `agents_sync._parse`, the builder's skill and agent frontmatter shapes
parsed with `items.read_frontmatter` and `agents_sync._parse`, the slug/derivation edge cases
against `items.GLOBAL_NAME`, the plan's `chanchi recommend --available "…"` line run verbatim, the
catalog rows behind that list, `claude --help` and `agy --help` for the launch flags, the
`audit open` launch template in `audits.py`, `chanchi audit round`/`vote`/`open` argument shapes,
the operational database's model rows, and `git check-ignore SYNC`. No file of the subject was
edited.

## Re-check of round-1 findings (Revision 2)

| id | severity | status | evidence |
|---|---|---|---|
| S3-01 | major | RESOLVED | Task 5 step 7 now says the committed gate record "must pass `tests/test_privacy.py`" and shows a **redacted** result: slugs as "project A"/"project B", roots as `<project root>`, `abs_path` as `<project root>/<path>`, the `SYNC` target as `<SYNC>`. Matches the phase-2 record's `~` convention. |
| S3-02 | major | RESOLVED | New **D17** fixes the printed shape of a proposal: `{id, kind, name, status, uses, owner_promoted (bool), eligible (bool, D9), global_item, created_at, updated_at, evidence: {rules, copies, pairs, clusters, lessons, min_uses, vendored_share}}`, `evidence` parsed and never a string. `eligible` is now a defined field, and D9 defines its formula. The builder's steps 1/5 and the gate's step 3 assertions read exactly these keys. |
| S3-03 | major | RESOLVED | D4 now names `inventory.frontmatter(text) -> dict`, "a lenient reader that never raises and returns `{"name": str \| None, "description": str \| None}`", with `inventory.description(text)` as its accessor. The folded-`description:` fixture in Task 2 step 1 is now readable by a declared interface. |
| S3-04 | major | RESOLVED | D2 now names `inventory.project_root(conn, project_id) -> Path \| None` (first `project_locators` row, kind `path`, lowest id, existing directory) and says "D6, D10 and D13 use the same function". It is in the Task 1 interface list and in the Task 1 step-1 assertions ("`project_root` returns the lowest-id existing locator"). |
| S3-05 | major | RESOLVED | New **D18** states `items` leaves are `project=False` and get no `--project` from the shared parent, that `items scan` adds its own `--project <slug>` "by hand", and that `project items-dirs` is a `project=True` leaf. Verified against `cli.py`: `leaf(…, project=False)` attaches `fmt_only` (only `--format`), `project=True` attaches `common` (with `--project`). |
| S3-06 | major | RESOLVED | Task 1's file list now names all four affected tests explicitly: `test_migration_v1_to_v2_preserves_data` "moves its synthetic probe migration to `db.latest_version() + 1`", and `test_migration_v2_keeps_user_task_types`, `test_migration_v3_to_v4_keeps_projects_and_adds_registered_at`, `test_migration_005_seeds_the_same_families_as_family_for` "stop pinning version 5". All four exist in `tests/test_db.py`. |
| S3-07 | minor | RESOLVED | The merge sentence now reads "S1 and S3 touch disjoint files except `README.md` … S3 does not edit `FEATURE_MAP.md`: it adds no command", and the S3 file-map row drops `FEATURE_MAP.md`. Checked `agents_sync.sync`: it writes only the wrapper files, so S3 and S1 really are disjoint apart from `README.md`. |
| S3-08 | minor | RESOLVED | D7 now lists `items.check(…, project_names=())`, `items.publish(…, project_names=())` and `items.mirror(…, project_names=())`, and says `publish` gets it by passing the names into `_find`/`_inspect` next to `own` — verified workable: `items.publish` calls `_find(sync_root, name, own=own_names)` and `_inspect(kind, entry, own)` is where `own_item_collision` is raised today. D9 now says "a boolean is never a number (`min_uses = true` is refused)". |
| S3-09 | minor | RESOLVED | Task 3's refusal list now includes `min_uses = true`, `vendored_share = 0`, `vendored_share = 1.01`, `vendored_share = true` and accepts `vendored_share = 1`. D9 states the range "(0, 1]", "integer or float", "`1` is accepted", and "a boolean is never a number". |
| S3-10 | minor | RESOLVED | D9 now says "The design's '209-line block' is an earlier measurement of the same copies; the outcome (one use) is the same, and executors do not stop on the difference" — the plan's own precedence rule no longer trips over the 3-line gap. |
| S3-11 | minor | RESOLVED | Task 5 step 4 now names the harness flags per harness ("`--add-dir` in claude and agy; claude also `--permission-mode acceptEdits`") and states the consequence ("`--add-dir` makes the consumer roots writable for the harness, so read-only rests on the builder's rules and is checked afterwards"). Verified live: `claude --help` has `--add-dir <directories…>` and `--permission-mode` with `acceptEdits`; `agy --help` has `--add-dir` (repeatable). The plan's `--available` list contains only `agy:` and `claude:` specs, so the harness without a directory flag (opencode) cannot be selected for S4. |
| S3-12 | minor | RESOLVED | (a) Step 4 now compares "`git status --porcelain` and `git diff --stat` of both consumer projects equal step 1's baseline" after the builder runs, and step 5 repeats "the same `git status` check as step 4". (b) The hard-coded seat list is gone: "the three seats chanchi fills from the roster (assert `degraded: false` and `skipped: []`, or record the degradation as `skill-chanchi-audit-rounds` says)", matching `audits._finalize_round_open`, which returns `degraded` and `skipped`. |
| S3-13 | minor | RESOLVED | D8 now says "A lessons group joins a same-name or overlap candidate only when kind and slug both match: it appends `\"lessons\"` to the candidate's `rules` and its approved lessons to `uses`; otherwise it is its own candidate", and the Task 3 test list asserts "lessons naming `role tool-x` do not join it and form their own agent candidate". |
| S3-14 | minor | RESOLVED | D8 now says "The design's 'same-purpose skills score low (0.12 to 0.38)' measures body similarity, not descriptions; this rule is expected to fire rarely, and a run with no overlap candidate is not a defect." |
| S3-15 | minor | RESOLVED | D8 now says "a name whose slug is empty is never a candidate and is listed under `skipped_names`", and D11 says the proposed name "always matches `items.GLOBAL_NAME`, because empty slugs are dropped by D8, and two names with the same slug are one candidate". Verified: `___` → empty slug; `foo.bar` and `foo-bar` → the same slug and therefore one candidate. |
| S3-16 | minor | RESOLVED | The Sessions table now has an **S4** row (Task 5 step 4, depends on gate steps 0-3, `docs` medium, runs as `agent-chanchi-item-builder`). |
| S3-17 | minor | RESOLVED | Task 5 step 4 gives the exact invocation with the full `--available` list. Run verbatim: `uv run chanchi recommend --task-type docs --complexity medium --available "agy:gemini-4-hydrogen-low:low,…,claude:sonnet:max"` → `ok: true`, recommendation `agy:gemini-4-hydrogen-high:high`. Every listed spec is an active catalog row with a matching effort (checked in the operational database). |

All 17 round-1 findings are resolved. Nothing below re-raises a rejected finding.

## Findings

| id | severity (blocking/major/minor) | where | problem | evidence | fix |
|---|---|---|---|---|---|
| S3-18 | minor | Task 5, step 4 ("Launch the builder headless from the main checkout with the launch line `chanchi audit open` prints for the chosen spec's harness (`harnesses.py`)") | The launch line is pointed at a source that cannot produce it, and the sentence conflates two independent spec sets. `chanchi audit open` prints one launch line **per auditor seat**, built with `harnesses.launch(entry["harness"], agent=AUDITOR_AGENT, model=entry["model"], effort=…, prompt=PROMPT)` where `AUDITOR_AGENT = "agent-chanchi-auditor"` and `PROMPT = "<prompt>"`. It never prints a line for `agent-chanchi-item-builder`, and its specs come from the **auditor roster** (`SYNC/config/auditors.toml` or the built-in list), not from the executor spec `chanchi recommend` picks for S4. The plan's "for the chosen spec's harness" therefore points at the wrong set of lines: with the default roster the printed lines are `claude:sonnet`, `agy:gemini-4-neon-high`, `opencode:opencode-go/minimax-m3` and `agy:gemini-4-hydrogen-high`, none of which is necessarily the S4 executor. The gate's executor would have to reconstruct the line itself, and the plan does not say which model/effort the builder runs under. | `src/chanchi/audits.py:21-22` (`AUDITOR_AGENT`, `PROMPT = "<prompt>"`), `:213-215` and `:245-247` (the only two `harnesses.launch` call sites, both with `agent=AUDITOR_AGENT`); `src/chanchi/sync.py:16-21` (`BUILTIN_ROSTER`); `grep -rn "agent-chanchi-item-builder" src/chanchi/` → no match. | Say that the orchestrator builds the launch line itself from `harnesses.launch(<harness>, agent="agent-chanchi-item-builder", model=<chosen model>, effort=<chosen effort>, prompt=<the builder prompt>)` for the spec `chanchi recommend` returned, and drop the reference to `chanchi audit open` as the source of the line (keep "the shape comes from `harnesses.py`"). State that the model and effort come from the recommended spec, not from the auditor roster. |
| S3-19 | minor | Task 5, step 4 (claude launch flags and the post-hoc checks) | The gate gives the builder write access to two directories it must not write (`--add-dir` for both consumer roots) plus claude's `--permission-mode acceptEdits`, which auto-accepts edits, and the only post-hoc checks are `git status --porcelain` / `git diff --stat` of the **two consumer projects**. The builder's working directory is the **chanchi main checkout** — a tracked repository — and nothing in the gate compares its `git status` to a baseline. A stray edit there is invisible to every check the gate performs, and `SYNC` is gitignored so only the report path is protected. (The write blast radius is what the plan already accepts for the consumer roots; what is missing is the baseline for the checkout the harness actually runs in.) | Plan Task 5 step 4: "Launch the builder headless from the main checkout … `--add-dir` in claude and agy; claude also `--permission-mode acceptEdits`" and "Audit the report like any session …: `git status --porcelain` and `git diff --stat` of **both consumer projects** equal step 1's baseline"; `claude --help`: `--permission-mode <mode> (choices: "acceptEdits", …)`; `.gitignore` lists `SYNC` (so `SYNC/reviews/…` is not a repo change) but the main checkout's tracked files are not ignored. | In step 0 or step 1, save `git status --porcelain` of the **chanchi main checkout** too, and in step 4 assert it is unchanged after the builder runs (the same way the consumer projects are checked). Alternatively, run the builder with its working directory set outside the checkout, or drop `--permission-mode acceptEdits` and rely on the harness's own approval flow plus the post-hoc checks. |
| S3-20 | minor | D3 ("A main file whose frontmatter holds a line starting with `# generated by chanchi` is a generated wrapper and is `skipped` (reason `generated`)") and D4 (`inventory.frontmatter(text) -> dict`) | The generated-wrapper test needs the frontmatter **block**, but the only reader the plan declares returns just `{"name", "description"}` and D4 does not say how the block is located. The check is implementable from the raw text (the block is delimited by `---`), so this is a wording gap rather than a hole — but the plan's own declared interface does not support it, and an executor who reads the file with `inventory.frontmatter` cannot tell a wrapper from a source. | The real wrapper format in this repository is a `---` fence whose first line is the marker: `.claude/agents/agent-chanchi-auditor.md` starts `---\n# generated by chanchi agents sync from agents/agent-chanchi-auditor/AGENT.md; do not edit\nname: …`; the marker is produced by `agents_sync._header`. D4 says the reader "returns `{"name": str \| None, "description": str \| None}`", with no block access. | Say in D3 how the block is found (e.g. "the text between the first `---` fence and the next `---` line, or the whole file when it has no fence") and add one sentence to D4: the lenient reader ignores comment lines such as `# generated by chanchi …`, so the marker never becomes a `name` or a `description`. |

## What holds up

- **Coverage.** All five phase-3 deliverables of the design's *Adoption phases* row 3 (migration 006,
  `items scan`, `project items-dirs`, `items propose`, `agent-chanchi-item-builder`) map to a task with
  tests, and the phase signal is reachable through the gate: scan → propose with
  `--owner-promote skill-chanchi-global-herdr` → build → item audit → `accepted`. Nothing from phase 4+
  is pulled in (`items inbox/decide`, `skill-chanchi-item-adoption` and the design's third proposal rule
  are explicitly out, and D1 leaves `item_decisions` empty until phase 4 with the reason). The lessons
  #1-#7 stay pending, as the request asks.
- **The builder's source.** The Task 4 text parses with `agents_sync._parse` (name, description, scope
  `both`, profile `workspace-write`, `install: user`, `skills: []`), is 58 lines against the 300-line
  budget of `tests/test_rules_budget.py`, and contains no home path and no reference-project name
  (`tests/test_privacy.py` clean; the plan file itself also passes it). It follows the
  `agent-chanchi-auditor` precedent exactly. Its rules are harness-agnostic and correctly withhold
  publishing, mirroring, auditing and any chanchi record.
- **The builder's frontmatter shapes are the ones the code accepts.** The skill shape
  (`name`, `description`, `metadata:` with `  version: "<v>"` and `  status: "draft"`) parses with
  `items.read_frontmatter` to `{'name': …, 'description': …, 'metadata': {'version': '0.1.0',
  'status': 'draft'}}`; the agent shape (`name`, `description`, `scope`, `profile`, `install: user`,
  `skills: […]`, `version`, `status: draft`) parses with `agents_sync._parse`. The `CHANGELOG.md`
  section format `## <version> — <YYYY-MM-DD>` matches `items.SECTION` (em dash, 1-based). The builder's
  "never write `status: published`" keeps it on the draft side of `items._inspect`'s state machine.
- **Fingerprints and the read-only guarantee.** D4's "no item text other than `description` reaches the
  database" matches the design's `project_items.description` column; the symlink skip, the non-UTF-8
  skip and the depth limit all hold against `items.content_hash` (which raises on a symlink inside the
  directory) and against `items._scan`, which checks `is_symlink()` before descending. The plan's
  snapshot test (every path, size and `mtime_ns` before and after) is the right instrument, and the
  gate's `git status --porcelain` comparison is the right end-to-end check.
- **Independent uses.** D9's cluster/union-find model reproduces the design's rule (vendored copies count
  once, `min_uses` default 3, `vendored_share` default 0.5, `SYNC/config/promotion.toml` with exactly two
  keys, `SYNC/config` already exists per `sync.SYNC_SUBFOLDERS`), and the herdr case ends at `uses = 1`
  with `owner_promoted = 1` → `eligible`, exactly as the design's owner decision of 2026-11-21 requires.
  The bool-vs-number trap is closed explicitly.
- **Storage across runs.** D11's one-open-row-per-`(kind, name)` with the partial unique index, the
  `built`/`rejected` → `closed` path and the `not_found` path are consistent with D13's transitions, with
  D12's "never cleared" rule and with the design's `item_proposals` table. The empty-slug and
  slug-collision cases are both closed.
- **The read-only commands do not create a database.** D7's guard (`db.operational_path().exists()`
  before opening a connection) is well-founded: `cli._conn()` → `db.open_operational()` → `bootstrap()`
  creates and migrates the file, so the guard has to come first. The plan's test ("`items check` and
  `items mirror --check` run with a `CHANCHI_DB` path whose file does not exist leave it absent") is the
  right assertion. `project_item_collision` is a *problem code* in the `problems` list (like
  `own_item_collision`), not a `ChanchiError` code, so the plan's "this plan adds none" to
  `errors.ERROR_CODES` holds.
- **The gate's audit plumbing.** `chanchi audit open --kind item --ref … --version 0.1.0 --author … 
  --change …` matches the parser (a mutually exclusive `--commit`/`--version` group, `--change` needing
  an existing change row); `chanchi audit round <id> --version 0.1.0` matches; `audit round` is indeed
  refused after `accepted` (`audits.next_round` refuses any outcome other than `fix`/`rework`), and
  `CHANGELOG.md` is excluded from `items.content_hash`, so the gate's rule that an accepted `0.1.0` stays
  byte-identical is correct. The gate's deviation from `skill-chanchi-audit-rounds` step 8 (accepted
  rounds do not apply minor fixes that touch hashed files) is a justified adaptation, not a conflict.
- **Command and API names.** Every command the plan names exists with the flags the plan uses:
  `project register/list`, `items check/list/publish/retire/mirror`, `items proposal-status`'s
  `invalid_transition`, `sync status`, `lesson show`, `agents sync [--check]`, `agents link --user
  [--check]`, `audit open/round/vote/dissent/close`, `session start`, `db migrate --template`,
  `db status`, `change close`, `recommend --available`. The `--available` list in Task 5 step 4 was run
  verbatim and returns `ok: true`.
- **Layering.** The declared import edges are acyclic (`inventory` → `db`/`items`/`projects`/`sync`/
  `taxonomy`/`errors`/`timeutil`; `items` never imports `inventory`; the CLI passes the names across),
  and `tests/test_layers.py` imposes no further constraint on a new domain module.

Nothing here makes the plan unexecutable or contradicts the design in a way a fix cannot repair. All
three findings are minor: a mis-pointed launch-line reference (S3-18), a missing baseline for the
checkout the builder runs in (S3-19) and a wording gap in the generated-wrapper test (S3-20). None of
them blocks an executor; each would otherwise cost a guess at the gate.
