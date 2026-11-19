# Stage 9: Implementation Readiness report

**Target:** `docs/designs/continuous-improvement.md`, DetailedRange lines 782-1051
**Goldfish context:** `docs/designs/continuous-improvement.brief.md`
**Reviewers:** egm-implementation-readiness and egm-codebase-details (implementation-readiness-standard), egm-style (persona only)

Mode: uninterrupted, so this is a single audit round with no resolution step.

---

## egm-implementation-readiness

**Verdict: NOT READY** (3 Blockers, 12 Majors, 6 Nits). The plan breaks the Zero-Decision Rule in several places. In three of them, following it as written breaks the build, the existing tests, or a database constraint.

### 🔴 Blocker IR-B1: `lesson export --format md|json` conflicts with the shared `--format json|text`
**Scope:** plan 874-875, 877-890; design 503-504.
Every leaf parser inherits `common`, which already defines `--format` with `choices=("json","text")` (cli.py:229-231). Adding another `--format` makes argparse fail with "conflicting option string" while building the parser, so every command breaks. `main()` always wraps the result as `{"ok": True, **payload}` and sends it through `_emit` (cli.py:388-396), and the plan does not say how Markdown reaches stdout.
**Decide:** a separate flag (`--md`) or `md` added to `FORMATS`; how `md` is emitted; what `--format text` does on `export`; the Markdown layout.

### 🔴 Blocker IR-B2: `lesson reopen-site` deletes a row that `lesson_events.site_id` still references
**Scope:** plan 1004; design 550-552, 362-366.
`lesson_events.site_id REFERENCES lesson_sites(id)` has no `ON DELETE` clause, and `PRAGMA foreign_keys = ON` (db.py:70). The `decline` that created the row also wrote an event with that `site_id`, so the `DELETE` fails.
**Decide (in migration 004 and item 23):** `ON DELETE SET NULL`; null out earlier events first; or do not delete (add a `reopened` state, or reuse the row).

### 🔴 Blocker IR-B3: `tests/test_db.py` will fail but is not in the file list
**Scope:** Stage 1 file list (787-998); verification 1038-1039.
test_db.py:238-251 appends a synthetic `(4, "004_add_probe.sql", …)`. With a real 004, the probe is skipped and `session_row["probe"]` raises. test_db.py:271-273 asserts `new_applied == [2, 3]` and `user_version == 3`.
**Fix:** add `tests/test_db.py` (Modify): renumber the probe to 5, expect `[2, 3, 4]` / `4`; optionally add the new tables to `OPERATIONAL_TABLES` (line 9).

### 🟡 Major IR-M1: The `ensure()` change is underspecified and misses the other audit commands
Plan 847-848; design 433-436, 751-753. Where does the cwd come from (`ensure` takes none, projects.py:65)? "Before" vs "only on a slug miss"? Does `--project` beat a locator? After `project rename`, `session start`, `incident add` and `show` fail with `invalid_value` (cli.py:57-58, projects.py:77-91). Add a `session start`-after-rename test. (Same root as the Stage 8 Blocker.)

### 🟡 Major IR-M2: `ChanchiError` cannot carry the required extra payload
Plan 828-830, 837-838, 979-980. `ChanchiError` (errors.py:28-61) holds only `code`, `message`, `field`, `valid_values`, `hint`. `duplicate_lesson` must carry the matched rule and shared tokens: new attribute and `to_dict()` key, or packed elsewhere? No `field` value is given for any of the six codes.

### 🟡 Major IR-M3: Item 10 (`render.py`) is a decision left to the implementer (892-898)
Decide now: "not touched", or the exact rendering rule.

### 🟡 Major IR-M4: `projects.register`/`relink`/`rename` edge cases unspecified
Plan 845; design 413-418; `projects.slug UNIQUE` (001_init.sql:17). Uncovered: folder slug owned by another registered project; `--name` with an existing unregistered folder row (adopt or new?); re-running `register` (idempotent or error?); outside git (which error?); no `origin`; whether `projects.path` updates; `relink` to a locator owned elsewhere; `rename` to an existing slug. `list_projects` and `show` reference §2, which does not specify them.

### 🟡 Major IR-M5: Read commands have no defined scope, filters or output (868-869; design 497-504)
`list` has no arguments; `similar` has no candidate set or output fields; `export`/`summary`/`list` do not say all projects or the resolved scope; `--since` column unstated.

### 🟡 Major IR-M6: `apply` semantics ambiguous (design 490-493; plan 870)
Which from-states can it update (`applied`, `retired`, `declined`, `not_applicable`)? Can a `project` lesson be applied to another project or globally? Can a `particular` lesson go global? Add a table of allowed (from-state, generality, site) combinations with refusal codes.

### 🟡 Major IR-M7: Dedup candidate rules overlap; warnings have no output key (design 518-523; plan 855)
"Approved, every site retired" is both blocking and warn-only; precedence unstated. With zero sites, `all([])` makes a never-applied approved lesson warn-only. Candidate order for "the first match" is undefined. Name the warnings key (e.g. `warnings: [{id, kind, general_rule, shared}]`).

### 🟡 Major IR-M8: Event vocabulary undefined (869-870; design 469; test 965)
Only `created` and `force_new` are named. Need an action table: command, action string, from/to source, whether `site_id` is set. Does `add --force-new` write one event or two (CUJ 1 says one `created`)? `summary`'s `force_new` rate depends on it.

### 🟡 Major IR-M9: `add` JSON validation incomplete (design 472-479; plan 868)
`change`/`session`/`incidents` on a `--global` lesson? Does `session` or `incidents` require `change`? Error for an incident from another change? `tags` string or list? Unknown keys rejected? `author_effort` when absent? Does `modify` re-run dedup and enum checks?

### 🟡 Major IR-M10: Stage 1 is one 22-file phase with no checkpoints (785-998)
Split into ordered steps, each ending with pytest: (1) migration, template, `test_db`; (2) taxonomy/errors; (3) projects; (4) dedup and stopwords; (5) lessons; (6) cli and integration tests; (7) skill, `skills_link`, README.

### 🟡 Major IR-M11: Test plan misses commands and edge cases (932-968, 1023-1029)
`repeat`; `reopen` field clearing; `retire` at one site; `replaces` guard; `project writers --set` by a non-writer and default fallback; `lesson add` outside a repo without `--global`; warn-only dedup; `git_head` capture and `None`; incidents from another change; `register` re-run, `relink`, `rename` collision; threshold boundaries (4/0.30, 3/0.50).

### 🟡 Major IR-M12: Stage-2 `verify` path resolution unspecified (1004; design 554-562)
Absolute, `~` and relative `where_` paths; "no site row for P" under `--global`; `--global` outside any project; output schema. Give rules and a JSON example.

### 🟢 Nit IR-N1: Stopword list not closed (806-813). Name the source and filter, or list every word.
### 🟢 Nit IR-N2: Item 22 is Modify, not Create (995-998); say whether Status changes on ship.
### 🟢 Nit IR-N3: `modelspec.parse` does not validate effort (modelspec.py:32-35): `claude:opus:hgh` becomes model `opus:hgh`, effort `None`. Document it, or check in `make_actor`.
### 🟢 Nit IR-N4: `reopen` of a `duplicate` leaves moved occurrences unresolved; list exactly which review fields clear, `duplicate_of` included.
### 🟢 Nit IR-N5: Paste-in lines not written out (909-913); principles and triggers only in the brief.
### 🟢 Nit IR-N6: `lesson inbox` flags differ from brief §6 line 309 (`--generality`, `--target-kind`, `--since`); inbox item output undefined; `summary` "for the resolved project" when none is required.

---

## egm-codebase-details

**Verdict: NOT READY** (4 Blockers, 6 Majors, 9 Nits).
**Claims that check out:** `record._required_text`, `modelspec.parse`, `taxonomy.describe()`, `skills_link.available_skills()`, `SUGGESTED_CONFIG_LINE`, the `--project` help text (cli.py:231), `chanchi.db.bak-v3` (db.py:174), the template drift check (test_db.py:53-67), `skills link` into `.agents/skills` and `.claude/skills`, the README sections in item 14, and hatch packaging `data/`.

### 🔴 Blocker CD-B1: `lessons.py` cannot import `subprocess`
**Scope:** 873 (`git_head` via `git rev-parse HEAD`), 1039.
tests/test_no_network.py:57-59 fails if any module other than `projects.py` imports `subprocess` (confirmed by the main session). **Fix:** put `git_head` in `projects.py` and call it from `lessons.py`.

### 🔴 Blocker CD-B2: `tests/test_db.py` breaks with a real 004 (= IR-B3)
Plus: extend `OPERATIONAL_TABLES` (test_db.py:9), and add a v3→v4 test showing existing `projects` rows survive with `registered_at` NULL.

### 🔴 Blocker CD-B3: Only `ensure()` uses locators; the other audit commands break (= IR-M1, Stage 8 Blocker 1)
Also: the new `--project` help text ("the registered project for this directory") would be false; test item 15 checks only `ensure()`. **Fix:** state new signatures for `ensure()` and `resolve_project()` (cwd, plus a flag for an explicit slug); `resolve_project()` tries locators before the slug; test `session start` and `show` after a rename and from a nested repo.

### 🔴 Blocker CD-B4: `export --format md` clashes with the shared `--format` (= IR-B1)
Also `_sniff_format` and `_emit` only know json and text (cli.py:371-385). Name the files the chosen mechanism touches.

### 🟡 Major CD-M1: Nowhere to put `duplicate_lesson` payload (= IR-M2)
Map it to `message`/`valid_values`, or add a `details` field to `ChanchiError.to_dict()` and test it in test_taxonomy.py (8-23).

### 🟡 Major CD-M2: Item 10 `render.py` left to the implementer (= IR-M3)
`render._render` already handles nested dicts and lists (render.py:32-53). Likely: drop the item.

### 🟡 Major CD-M3: Fixture files given as a glob; shared fixtures missing
`tests/fixtures/lessons/*.json` (948) must be named files. `git_repo` (conftest.py:29-38) has no commit and no remote, so `git_head` is None in every test; `Recorder` (helpers.py:19-31) resolves via `identify()`. Say whether conftest/helpers get `registered_repo`, `nested_repo` (Modify), or each test builds its own.

### 🟡 Major CD-M4: Git calls are duplicated; no shared helper
`detect()` already runs `git rev-parse --git-common-dir` (projects.py:34-47). Name one private `_git(cwd, *args) -> str | None` in projects.py for `detect`, `main_worktree`, remote lookup, `resolve_registered` and `git_head`; state the exact remote command.

### 🟡 Major CD-M5: Positional slug vs inherited `--project`
`project show [<slug>]` and `project writers [<slug>|--global]` (881-883) vs `--project` on every leaf. Which wins? `leaf()` hard-codes `parents=[common]` (cli.py:242-245); does it gain a `parents` argument?

### 🟡 Major CD-M6: Tags helper conflicts with the schema
`record._csv` (record.py:14-18) and `cli._split` (cli.py:47-50) exist; name them. `_csv` returns None for empty input but `lessons.tags` is `NOT NULL DEFAULT ''` (312). State the empty-tags rule.

### 🟢 Nit CD-N1: `make_actor` re-implements `catalog._model_row` (catalog.py:106-109). `--author human` resolves to the seeded `human:human` row (001_init.sql:84-85); item 17 should assert that.
### 🟢 Nit CD-N2: Load stopwords via `importlib.resources.files("chanchi") / "data"` (hfsignals.py:69, db.py:31).
### 🟢 Nit CD-N3: Item 20 is mostly automatic (test_skills_content.py:12, 30-45); the real change is `test_both_skills_exist` (27). "Parses with the real parser" only runs `--help`.
### 🟢 Nit CD-N4: A stage-1 skill quoting `chanchi lesson inbox` fails `test_documented_commands_exist`; say stage-2 commands stay out of the stage-1 skill.
### 🟢 Nit CD-N5: Item 21 uses a fake `skills_dir` (test_skills_link.py:9-16); use `repo_skills_dir()` or test_cli.py:163-168.
### 🟢 Nit CD-N6: Item 22 is Modify, not Create (= IS-N2, IR-N2).
### 🟢 Nit CD-N7: Item 13 does not say where the paragraph goes in the numbered list (SKILL.md:38-44).
### 🟢 Nit CD-N8: `chanchi db status` does not open the operational DB (db.py:266-282); `chanchi show` needs `--project` outside the repo. Name exact commands at 1040-1042.
### 🟢 Nit CD-N9: `check_writer` signature differs (item 8 vs Technical Plan 455); exit code is already automatic for non-`internal` codes (errors.py:49-51), so say no `exit_code` change.

**Files to add to the Stage 1 list (Modify):** tests/test_db.py; tests/test_no_network.py only if `git_head` stays out of projects.py; tests/conftest.py and/or tests/helpers.py if shared fixtures are added; render.py made unconditional or dropped. Each fixture under tests/fixtures/lessons/ as Create.

---

## egm-style

**Verdict:** No Blockers, 6 Majors, 9 Nits. The section is dry and direct. The Majors are about wording that a test writer cannot turn into a fixed outcome.

### 🟡 Major IS-1: Mixed reference frames (871)
"the state tables of the brief §4" vs "Technical Plan §N" elsewhere. Brief §4 is States; design §4 is dedup. Name the brief section in full or copy the tables in.

### 🟡 Major IS-2: Stopword source undefined (807-813)
"A standard English stopword list (… such as …)" names no source (NLTK, scikit-learn, Snowball). Dedup thresholds and fixtures (948) depend on the exact set. Name source and version, or say the shown words plus four domain words are the full list.

### 🟡 Major IS-3: Subjective change criterion for `render.py` (892-898)
"(Modify)" heading, "unless … unreadable nesting", "not touched if no change is needed". Drop, or give a testable condition.

### 🟡 Major IS-4: Error-envelope test asserts fields the codes do not define (980 vs 828-840)
Test expects `field`, `valid_values` and `hint` for every new code; only `not_a_writer` defines `valid_values`, and `invalid_transition` (839) has no hint. List fields per code; add a hint to 839 (brief §6).

### 🟡 Major IS-5: "As before" outcomes with no baseline (939-940, 1037, 1041-1042)
Name the observable (same project row id and slug, no locator rows, `registered_at` NULL). For the migration check, capture `chanchi show <ref>` JSON before migrating the copy and diff after. Name the operational DB path and one read-only command.

### 🟡 Major IS-6: "the source method's test list plus the additions" (952)
Not defined anywhere. State that 954-968 is the complete list, or name the source.

### 🟢 Nit IS-N1: Stage-2 items 23-28 (1002-1033) drop the "Type / Scope" field items 1-22 carry
### 🟢 Nit IS-N2: Item 22 (995-998) says "(Create)" for a committed file; "finalized" has no done-condition
### 🟢 Nit IS-N3: Inconsistent error-message placeholders and hint styles (831-840)
### 🟢 Nit IS-N4: Name `EXIT_VALIDATION` (2) from errors.py:9 at line 830
### 🟢 Nit IS-N5: Add citations for existing-behavior claims (802, 814, 903-904): pyproject.toml:16-17, skills_link.py:28, tests/test_db.py:53
### 🟢 Nit IS-N6: Slogans instead of outcomes (946, 954, 962): "No general rule, no record", "told with another case", "refuses itself", "coverage on empty sets" (state 0)
### 🟢 Nit IS-N7: Vague pointers (973-974, 986, 1044): "the values in this document", "the three skills", "the stage's report"
### 🟢 Nit IS-N8: Term drift: "three lines" vs a "block" (913); "per-file size" vs line count and tag count (1029); "applied to one project" vs "at least one" (1025-1026)
### 🟢 Nit IS-N9: Filler: "anyway" (813), "all green" (1038), "*Drafted with EGM*" (1051)
