# Stage 9 re-audit: Implementation Readiness (round 2)

**Target:** `docs/designs/continuous-improvement.md` Revision 2, DetailedRange lines 1098-1470
(the Technical Plan was read as context and its code claims were checked).
**Goldfish context:** `docs/designs/continuous-improvement.brief.md`
**Reviewers:** egm-implementation-readiness and egm-codebase-details (both completed after a rate-limit pause)
**Result:** not ready. 1 Blocker, 13 Majors, 15 Nits after deduplication. This is the one
re-audit the EGM cap allows; any further fixes are not re-audited.

The round-1 blockers are closed. No reviewer re-raised the shared resolver, the `--format md` clash,
the `test_no_network` import or the event foreign key. Most cited line numbers match the code.

## 🔴 Blocker

### R2-B1. Refusing any model name that contains `:` rejects real opencode models
**Raised by:** codebase-details B1, readiness M3. Confirmed by the main session.
**Scope:** design 626-630; item 12 (1268); item 13 test (1289).
**Problem:** `tests/conftest.py:53` seeds `opencode:openrouter/qwen/qwen3-coder:free`, and
`tests/test_modelspec.py:20-26` asserts that the `:free` suffix stays in the model name. Under the
rule, such an author could never record a lesson.
**Fix:** accept the spec when `(agent, model)` matches the catalog exactly. Refuse a colon only when
there is no catalog match and the last segment is within edit distance 2 of an effort name (e.g.
`hgh`). Add a test where `opencode:openrouter/qwen/qwen3-coder:free` passes with `author_model_id`
set.

## 🟡 Major

### R2-M1. `project writers` and the `identity` parent cannot be built as described
**Raised by:** CD M5, IR M1. **Scope:** item 14 (1324-1329).
argparse cannot add a parent only when `--set` is given; adding it makes the three flags required
on the read-only form; a second `--global` conflicts; `--as`/`--global` need `dest` names
(`as_role`, `global_`, as at cli.py:286).
**Fix:** `writers` declares the identity flags as optional, and the handler requires them when
`--set` is present (`invalid_value`, field `as`). Name every `dest`.

### R2-M2. `--global`/`--project` meaning on writes to an existing lesson is undefined
**Raised by:** IR M2. **Scope:** 1324-1331; 654-658.
**Fix:** `--global` is accepted only on `add`, `project writers` and the read commands. Lesson-level
writes use the lesson's origin and need no resolved project. Site writes take `--site`, and
`--site project` resolves the project from `--project` or the working directory.

### R2-M3. The step-3 checkpoint depends on step-6 code and on `tests/helpers.py`
**Raised by:** CD M4, IR M4. **Scope:** 1110, 1211-1212, 1335-1336; helpers.py:24, 31.
**Fix:** move the `cmd_change_open` edit into step 3, and add `tests/helpers.py` (Modify) so that
`Recorder.change` calls `identify(..., conn=self.conn)`.

### R2-M4. The guard on `project writers --set` has no owner and no test
**Raised by:** IR M5. **Scope:** items 7, 12, 14.
`projects.py` cannot import `lessons` (cycle), and `set_writer_roles` takes no actor.
**Fix:** `lessons.set_writers(conn, scope, actor, roles)` calls `check_writer`, then
`projects.set_writer_roles`. Roles must be non-blank and are deduplicated; an empty list is refused.
Add the tests.

### R2-M5. Most refusals have no error code
**Raised by:** IR M6. **Scope:** item 5 vs item 13.
**Fix:** one rule: every refusal not in the item-5 table is `invalid_value`, with `field` set to the
JSON key or flag. `--of N` for a missing N, and a missing lesson in general, use
`lesson_not_found`. `change`/`session` reuse `unknown_change`/`unknown_session` from
`record.get_change`/`get_session`.

### R2-M6. Signatures and return payloads of `lessons.py` and `dedup.py` are unspecified
**Raised by:** IR M7.
**Fix:** a table of command → JSON result (e.g. `add` → `{"lesson": {...}, "warnings": [...]}`).
`"scope"` is the slug, `global` or `all`. `similar` compares the full text. Rank by the higher of the
two coverages. Name the candidate dict keys.

### R2-M7. Duplicate bookkeeping and `modify` scope
**Raised by:** IR M8.
**Fix:**
- The moved count is stored in the event note as `moved=<n> to=#<N>`.
- `modify` replaces text, enums and tags, re-links `incidents` and `replaces` (delete, then
  insert), and keeps `change`, `session` and `git_head`.
- `--reason` is required for every decision; `--reason-code` is allowed on `reject` only.

### R2-M8. The Verification Plan cannot run as written
**Raised by:** CD M3, IR M9.
**Fix:**
- Time `dedup.blocking_match` over 1,000 candidate dicts in step 4.
- Stage 1 runs CUJs 1-4 and 7; stage 2 runs CUJs 5-6.
- Add a step table and a checkpoint for stage 2.
- Add parsing tests for the stage-2 commands.

### R2-M9. Impossible dedup boundary tests
**Raised by:** CD M6, IR N3. **Scope:** item 11 (1257-1258).
**Fix:**
- Full-text test: 6 shared of 20 (0.30) blocks; 4 of 14 (0.286) does not.
- Rule test: 3 of 6 (0.50) blocks; 3 of 7 (0.43) does not.
- Pin `unrelated.json` so that its shared words are not in the general rule.

### R2-M10. `record._csv` and `record._required_text` do not fit JSON values
**Raised by:** CD M7, IR N2.
**Fix:** check the type of every body key first (`invalid_value`). Normalize tags with
`record._csv(",".join(v) if isinstance(v, list) else v) or ""`. Add a test with a non-string
field.

### R2-M11. The `test_db.py` edit misses line 243
**Raised by:** CD M2, IR N1. **Fix:** line 243 becomes `[2, 3, 4, 5]`.

## 🟢 Nits

- **Reuse** (CD N8): `record.get_change`, `record.get_session`, `record.incident_dict`,
  `taxonomy.validate_choice`, `timeutil.since_to_iso`, `cli._split` and `cli._int`.
- **Voided incidents** cannot be linked (CD N9).
- **`test_both_skills_exist`** must reorder the sorted list; rename the test (CD N10).
- **`invalid_transition` field** is `state` for site refusals (CD N11).
- **Older build for the migration check:** use `git worktree add` (CD N12).
- **`identify()` with an explicit slug** returns the locator path when the working directory is
  inside that registered project (CD N13, IR N6).
- **`describe()`:** name the sub-keys (IR N4).
- **`SUGGESTED_CONFIG_LINE`:** give the full string (IR N5).
- **Fixtures** chdir into the repository and commit with `-c user.name/-c user.email`, as
  test_projects.py:22-26 does (IR N7).
- **`verify --scan`:** behavior for directories, relative paths and non-UTF-8 files; add a
  summary-inbox test (IR N8).
- **Status line** for stage 2 (IR N9).

## Resolution

**Status:** resolved in design Revision 3. The author asked to apply every fix ("si"). Each
finding above was applied as written, with these precisions:

- **R2-B1:** the refusal also needs a catalog miss, and its hint points to `chanchi models add`
  for a real model whose suffix is close to an effort (e.g. `:pro`). Tests cover
  `opencode:openrouter/qwen/qwen3-coder:free` (accepted, model id set) and an unknown model with a
  far suffix (accepted, model id NULL).
- **R2-M1/M2:** a "Scope flags" paragraph in §3; `identity` holds no `--global`.
- **R2-M3:** the `cmd_change_open` edit moved to item 7 (step 3); item 8 now covers
  `tests/helpers.py`.
- **R2-M4:** `lessons.set_writers` writes no `lesson_events` row.
- **R2-M6:** a "Results" table in §3 and the signatures in item 12.
- **R2-M7:** `--reason-code` is optional with `reject` and refused otherwise; `reopen` reads the
  moved count from the latest `moved=` event note.
- **R2-M8:** a stage-2 step table and item 28 (status line); item 27 adds parsing tests.
- **Nits:** all applied. The `invalid_transition` field for sites is in the item-5 rule.

Per the EGM cap, these fixes are not re-audited.
