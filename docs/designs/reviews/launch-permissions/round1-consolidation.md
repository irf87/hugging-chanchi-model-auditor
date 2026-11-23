# launch-permissions — audit round 1 consolidation

- Subject: branch `fix/launch-permissions` at `7261f8d` (headless launch lines carry each harness's
  permission flags); chanchi audit 13, kind `other`, round 1, **degraded** (anthropic, google,
  google; gpt-oss replaced by the owner's instruction).
- Outcome: `accepted`. All findings minor; fixed in the follow-up commit.

| Seat | Auditor | Verdict | B | M | m |
|---|---|---|---|---|---|
| 1 | claude:sonnet:medium | pass_with_fixes | 0 | 0 | 4 |
| 2 | agy:gemini-4-neon-high:high | pass_with_fixes | 0 | 0 | 5 |
| 3 | agy:gemini-4-hydrogen-high:high | pass | 0 | 0 | 3 |

Seat 1 ran with the new claude launch flags and re-ran the tests itself: the fix's first live use.

## Minor fixes applied

| Finding | Seats | Fix |
|---|---|---|
| Stale launch lines in `docs/designs/global-items.md`, `README.md`, `skill-chanchi-verify` | S1-F1, S2-F4, S3-F1 | Updated to the new lines or pointed to `AGENTS.md` and `chanchi audit open` |
| `AGENTS.md` paragraph ambiguous (could read as allowing the skip flag on `claude -p`), mixed dates, singular "flag" | S1-F2, S2-F2 | Rewritten: headless claude never uses the skip flag; both owner dates named; "These flags" |
| Audit-rounds step 3 repeats itself and ignores opencode's missing `--add-dir` | S1-F3, S2-F3, S3-F2 | One sentence, "(where present)", an unreplaced placeholder is an error |
| Profile parametrized by a literal tuple | S2-F5b, S3-F3 | `harnesses.PROFILES` |
| `add_dirs` splits a bare string per character; `_dq` docstring | S2-F1 (lone, confirmed) | Refused with `invalid_value` (`field: add_dirs`), tested; docstrings |
| `audit unavailable` launch line untested | S2-F5a (lone, confirmed) | Asserted in `tests/test_audits.py` |
| Read-only claude seat writing its report not confirmed live | S1-F4 (lone, rejected) | Seats 1 of audits 11, 12 and 13 wrote their reports with these flags |
