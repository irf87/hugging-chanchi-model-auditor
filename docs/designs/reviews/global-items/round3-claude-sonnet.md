VERDICT: PASS WITH FIXES

Counts of what remains open after Revision 3 (carried plus new): blocking 0, major 0, minor 6.
Both of my round-2 majors (M1 draft state, N1 mirror ownership) are RESOLVED. Nothing remaining blocks
merging the design; the minors are wording or phase-plan items that the phase 1 and 2 plans can absorb.

Method: `git show HEAD` and `git diff a7a1a20 HEAD` for `docs/designs/global-items.md` and the
consolidation `round2-consolidation.md`, checked against `src/chanchi/` (`skills_link.py`, `db.py`,
`catalog.py`) and the opencode skills documentation. No other auditor's report read. No
reference-project name or home path written here.

## Re-check of my round-2 open findings

| id | status | evidence |
|---|---|---|
| M1 draft state, unaudited items mirrored | RESOLVED (small remainder in R3-1) | `status: draft\|published\|retired`; the builder writes drafts, the mirror "exposes only `published` items", and `items publish <name> --audit <id>` requires an accepted `item` audit at the current version. |
| M4 remainder: `pass` vs counts; strict `pass`; "one or two rounds" claim | OPEN (minor) | The revision diff does not touch the vote validation or the Risks line; `pass` with `--blocking > 0` is still accepted and the audit-cost estimate is still unevidenced. |
| M6/N3 family inference gaps | PARTIAL | Matching on the last `/` segment with `#variant` removed and "missing roster entries are unavailable with a hint" are fixed; `models add` still has no stated way to set the family for models added after migration 005 (they stay unknown and fail closed). |
| M7 remainder: vendored-text guidance, `promotion.toml` keys | OPEN (minor) | Neither is in the diff; independent-use counting itself is resolved. |
| N1 ownership vs relative links | RESOLVED | Ownership moved to a manifest (`mirror.json`) of every created entry (primaries, secondaries, generated agents), independent of link text; separation from `skills unlink` is stated and tested both ways (verification 6). |
| m1 lesson closure | RESOLVED | "applied at the global site" via `lesson apply <id> --site global --where "SYNC item <name>@<version>"` on publish. |
| m3 / N2 `audience: global` overload and phase order | RESOLVED | Renamed `install: repo\|user`, `agents link --user` and `agent-chanchi-auditor` ship in phase 1, same manifest ownership; the phase table row 5 no longer carries them. |
| m5 / N4 hash framing, nested metadata | RESOLVED | UTF-8 path, NUL, length, NUL, bytes; reader shape "a `metadata:` line followed by two-space-indented `key: value` lines". |
| N5 `audit round` guard, escalation reason | RESOLVED | Refused unless last outcome is `fix` or `rework` and round below 3; `escalation` column `quorum\|round_cap`; `close` refused with assigned seats. |
| m12 plumbing | RESOLVED | "Fitting the existing code": `harnesses.py` as a leaf in `tests/test_layers.py`, FEATURE_MAP, skills-content test, README, verify helpers; own items may not use `-chanchi-global-` (verification 7). |

## New findings

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| R3-1 | minor | Versions and hashes, `items publish`; phase 2 signal | The audit binds to a version, not to content. After an accepted audit, edits at the same version still publish, and after publishing a skill's symlink stays live under hand edits, yet the phase-2 signal says "`--check` catches a hand edit": `--check` has no accepted hash to compare against for skills (it only detects stale generated agent files). The status line is inside the hashed `SKILL.md`/`AGENT.md`, so draft and published hash differently. | `audit_rounds.subject_at` is "commit sha or item version"; content hash excludes only `CHANGELOG.md` and dotfiles. | For kind `item`, store `<version>@<content hash excluding the status field>` in `subject_at`; `publish` compares it with the current hash; `items check` warns when a published item's hash differs from the accepted one; restate the phase-2 signal accordingly. |
| R3-2 | minor | Mirror, Name collisions; verification item 7 | The check "equals any project item recorded by `items scan`" needs the scan tables of migration 006 (phase 3), but the mirror and `items check` ship in phase 2 and verification item 7 is in the phase 1-2 plan. Failing a mirror on stale scan data also couples it to the scan. | Phase table rows 2 and 3; migration 006 section. | Make the scan-based collision check a phase 3 addition (chanchi-item check only in phase 2); keep the mirror independent of the scan. |
| R3-3 | minor | Mirror, Ownership by manifest | The manifest is at `$XDG_DATA_HOME/chanchi/mirror.json`, but chanchi's scratch convention is `CHANCHI_DB`, which `db.py` uses to override only the database path; tests that set a temporary `HOME` but not `XDG_DATA_HOME` would write the operational manifest. A lost or deleted manifest also turns every existing entry into a "conflict" with no stated recovery. | `src/chanchi/db.py` lines near 20-23 (`CHANCHI_DB` override, then `XDG_DATA_HOME`); AGENTS.md rule to use a scratch `CHANCHI_DB`. | Place the manifest next to the resolved database file (or give it its own env override that tests set), and add `items mirror --adopt` (re-adopt entries whose link text or header matches) as the recovery path. |
| R3-4 | minor | Mirror, Separation from chanchi's own skills | "`chanchi skills link/unlink` keep recognizing only links into this repository's `skills/`" is not what the code does today: `_is_own` also accepts any dangling `skill-chanchi-*` relative secondary, which includes dangling `skill-chanchi-global-*` mirror secondaries. Verification 6 as worded (leaves every mirror entry) will not cover the dangling case. | `src/chanchi/skills_link.py` `_is_own` (dangling-secondary branch, prefix `skill-chanchi-`). | State that the dangling-secondary rule excludes names containing `-chanchi-global-`, and add the dangling case to verification 6. |

## What must not change

- The draft/published/retired status flow, `items publish` gated on an accepted `item` audit, and the
  mirror exposing only published items.
- Manifest-based ownership of mirror and `agents link --user` entries, independent of link targets.
- The ordered outcome table with the lone-finding rule, per-audit round numbers, seats with same-seat
  refill, `escalation` reasons, and the guards on `audit round`, `close`, `vote`.
- Fail-closed families with last-segment, variant-free matching; `install: repo|user` shipping in phase 1.
- The headless per-harness load as the phase-2 gate, and the privacy posture (`SYNC` ignored, nothing
  private committed).

AUDIT DONE
