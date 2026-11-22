# Round 1 consolidation — global items phase 2 plan

- **Subject:** `docs/superpowers/plans/2026-11-22-global-items-phase2.md` at `77518a6` (Revision 1)
- **chanchi audit:** id 3, kind `other`, change `global-items-phase2`, round 1, not degraded
- **Outcome:** `fix` (no approvals: every vote carried major findings)

## Seats and votes

| Seat | Auditor | Family | Verdict | Blocking / major / minor | Report |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | anthropic | pass_with_fixes | 0 / 2 / 8 | [round1-claude-sonnet.md](round1-claude-sonnet.md) |
| 2 | agy:gemini-4-neon-high:high | google | pass_with_fixes | 0 / 6 / 5 | [round1-agy-gemini-4-neon.md](round1-agy-gemini-4-neon.md) |
| 3 | opencode:opencode-go/minimax-m3 | minimax | pass_with_fixes | 0 / 6 / 9 | [round1-opencode-minimax-m3.md](round1-opencode-minimax-m3.md) |

## Findings raised by more than one auditor (applied)

| Topic | Findings | Fix in Revision 2 |
|---|---|---|
| Parallel S1/S2 and the global-name placeholder | S1-06, S2-01, S3-03 | Sessions run S1 → S2 → S3; the only safe placeholder before S1 is `<item>-chanchi-global-<name>`; no explore session (every session blocks a later one) |
| How audits get the SYNC root | S1-03, S2-02, S3-10 | D6: optional `sync_root` on `open_audit`/`next_round`, passed by the CLI; existing item-kind tests updated |
| Gate closes the change on the scratch database | S1-04, S2-06, S3-01 | D15 and Task 5 step 7: unset the variables, return to the main checkout, then the agents checks and the change records |
| D1 reading of the design's `link_conflict` sentence | S1-05, S3-15 | D1 states the reading and its reason |
| `items retire` must set `status: retired` | S1-01, S2-05(2) | D9 and Task 3 |
| `published` with no `Published:` line | S1-02, S2-05(4), S3-08 | D5: `published_without_record`; retired and draft items exempt |
| Frontmatter quoting, parsing and insertion | S1-07, S2-05(1)(3), S3-13 | D3 |

## Lone findings: decisions

| Finding | Severity | Decision | Evidence |
|---|---|---|---|
| S1-08 D13 conflict scope | minor | confirmed | Design: a foreign global-named entry is never overwritten; only wanted paths conflict. D13 narrowed |
| S1-09 Gate baseline gaps | minor | confirmed | `--remove` deletes entries, not folders; compare entry names, keep the scratch DB |
| S1-10 Merge plan first; re-run recommend | minor | confirmed | Worktrees come from `main`; recommend data moves |
| S2-03 agy skill secondary on `installed("agy")` | major | **rejected** | Design: global skills get exactly the links `skills link --global` gives today, i.e. the `antigravity-cli` secondary only when that folder exists. Test fixture wording clarified |
| S2-04 Shared helper breaks all-or-nothing | major | confirmed | `link_user` writes files and the manifest in one call; D16 composable primitives |
| S2-07 `sync init` edge cases | minor | confirmed | `mkdir` on a file raises an unhandled error |
| S2-08 Register idempotency | minor | confirmed | `register` answers `already_registered` before deriving the slug |
| S2-09 Tolerant `list_items`, name regex, dotfiles | minor | confirmed | `content_hash` and the reader raise |
| S2-10 D12 test, agent-global conflict, legacy names | minor | confirmed | Task 4 tests and D14 extended |
| S2-11 Scratch HOME drops the uv cache | minor | confirmed | `uv cache dir` is under HOME; scratch HOME is now per command |
| S3-02 D14 rationale wrong | major | **rejected** | Reproduced: a dangling `~/.claude/skills/skill-chanchi-global-probe` secondary gives `_is_own == True` and `skills unlink --global` removes it |
| S3-04 `retired.json` as `unexpected_entry` | major | confirmed | D7 lists the expected entries of `ITEMS/` |
| S3-05 Gate needs the auditor agent installed | major | confirmed | Task 5 step 0 precondition |
| S3-06 Write after the cleanup baseline | major | confirmed | Step 6 is read-only now |
| S3-07 `items.check` return vs raise | minor | confirmed | D7: always returns; the CLI raises |
| S3-09 `sync.require` unresolved | minor | confirmed | D1 and Task 1 |
| S3-11 S3 verification misses `test_skills_content.py` | minor | confirmed | Added |
| S3-12 Per-topic review folder | minor | confirmed | `reviews/global-items-phase2/gate.md` |
| S3-14 Four roster models | minor | confirmed | Fixed |

## Next

Revision 2 is committed and re-checked in round 2 by the same seats.
