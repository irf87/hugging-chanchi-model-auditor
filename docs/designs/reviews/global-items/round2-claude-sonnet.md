VERDICT: PASS WITH FIXES

Counts of what remains open after Revision 2 (carried plus new): blocking 0, major 2, minor 8.
No finding of mine is rejected by Revision 2; 17 of my 20 are RESOLVED or PARTIAL with only a small remainder.

Method: `git show a7a1a20`, the consolidation, the full Revision 2 text, and checks against
`src/chanchi/` (`skills_link.py`, `agents_sync.py`, `projects.py`, `errors.py`). Privacy: no
reference-project name and no home path written here.

## Re-check of my round-1 findings

| id | status | evidence |
|---|---|---|
| M1 mirror vs principle 2; draft state | PARTIAL | Principle 2 is restated truthfully ("available ... visible in every project; never replaces a project's item"), but there is still no draft or released state: C says the builder writes into `SYNC/ITEMS/` and "accepted, ... `items mirror` exposes it", yet a symlinked skill is live the moment it is written, and nothing ties the mirror to an accepted audit hash. |
| M2 SYNC location | RESOLVED | "Locating `SYNC`": `CHANCHI_SYNC`, else the parent of `git rev-parse --git-common-dir` of chanchi's source, so every worktree resolves to the main checkout; `missing_prerequisite` exists in `errors.py`. |
| M3 subject text restarts the cap | RESOLVED | `audits(subject_kind, subject_ref)` plus `audit_rounds(audit_id, round)` with `UNIQUE (audit_id, round)` and `subject_at`; a fix commit cannot restart the count. |
| M4 outcome table | PARTIAL | Ordered table with the lone-finding rule and "fewer than two voted -> escalated" resolves (a) and (b). Still open: no rule that `pass` implies blocking 0 (c), and `accepted` still needs two clean `pass`, so `pass_with_fixes`-heavy rounds (all three of round 1) keep producing `fix`; the Risks line "most subjects close in one or two rounds" is still unevidenced. |
| M5 auditor agent and launch templates | RESOLVED | `agent-chanchi-auditor` defined; templates carry `--effort`, `#variant` and `< /dev/null`. (A phase-ordering problem this created is N2.) |
| M6 families fail open | PARTIAL | Seeding by name pattern and fail-closed degrade are specified and unknown never counts as distinct. Gaps are in N3. |
| M7 independent uses and herdr | PARTIAL | Vendored copies count once, similarity dropped, herdr owner-promoted, `promotion.toml` named. Not added: the global item over vendored text keeps only the shared rules and points to the upstream generator, recording its version; the keys of `promotion.toml` are not specified. |
| M8 mirror vs `skills_link` | PARTIAL | The mirror now reuses `skills_link` with the same primary and secondaries and agy only when its CLI folder exists. The ownership rule written for it does not fit those links: see N1. |
| m1 migrations and lessons | PARTIAL | 005 vs the lessons stage is noted in both documents; 006 is specified; the `item` field is dropped in favor of `target`. Not stated: how a lesson is closed once an item is built from it (apply at the global site), and that lessons #1-#3 stay pending as test data. |
| m2 `render` refactor and agy layout | RESOLVED | Per-kind rendering, header parameter and a target map are specified; the agy user layout is a live probe before phase 2 (I verified a flat `~/.gemini/config/agents/<n>.md` is listed by `agy agents`, so the probe will pass). |
| m3 `audience: global` overload | OPEN | Still `audience: repo\|global`; reserved word reused for chanchi-owned agents, and the ownership rule for them is undefined (N2). |
| m4 adapter overstated | RESOLVED | The list of what a new harness needs (adapter row, renderer, taxonomy key, catalog families, tests) replaces "a row". |
| m5 hash and version parsing | PARTIAL | Exclusions, symlink error and POSIX paths are specified. Framing is addressed in N4; reading nested `metadata.version` with a flat-only parser is still not stated. |
| m6 AGENTS.md | RESOLVED | "accepted when at least two of three pass"; the global naming and reserved slug are in the Items section. |
| m7 citations | RESOLVED | Rule of three attributed to the article's author, debate cap marked as measured on reasoning tasks, brief wording corrected on reload and rounds. |
| m8 report independence; author family | RESOLVED | Private scratch paths until every seat has voted; `audits.author_*` recorded, family not excluded and said so. |
| m9 dangling mirror links, reload claim | RESOLVED | Ownership by link text including dangling entries, `sync status` reports reachability, reload claim narrowed (subject to N1 for secondaries). |
| m10 adopt leaves references | RESOLVED | `adopt` and `wrap` update every reference in roles, rules and other skills. |
| m11 similarity | RESOLVED | Similarity is explicitly not a criterion. |
| m12 phase-1 signal, change row, plumbing | PARTIAL | Backfill is stated and `change_id` is now optional. Not stated: FEATURE_MAP entries, `test_layers` fit, README and verify-skill updates per phase; reserving `global` in this repository's own item names (`tests/test_items.py` still allows `skill-chanchi-global-x` in `skills/`); `skill-chanchi-item-authoring` update. |

## New findings

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| N1 | major | Mirror, Skills and Ownership bullets | Contradiction inside the fix. Skills are linked "exactly like chanchi's own": one absolute link in `~/.agents/skills/` and relative links to it in `~/.claude/skills/` and the agy CLI folder. But ownership is defined as "a symlink whose link text starts with the resolved `SYNC/ITEMS/` path", which only the primary satisfies; the relative secondaries (link text like `../../.agents/...`) are classed as foreign, so a second `items mirror` run reports a conflict and `--remove` leaves them behind (the phase-2 signal "leaves nothing behind" fails). Separately `skills_link._is_own` treats any dangling `skill-chanchi-*` secondary as chanchi's own, and `skill-chanchi-global-*` matches that prefix, so `chanchi skills unlink` of chanchi's own skills can delete mirror secondaries. | `src/chanchi/skills_link.py` `_ensure` (secondaries are relative to the primary), `_is_own` (prefix `skill-chanchi-` plus dangling-secondary rule). | Own a `*-chanchi-global-*` entry if its link text starts with the resolved `SYNC/ITEMS/` path, or equals the relative link to an owned primary. Make the generalized `skills_link` take the prefix as an exact owner class, and exclude `skill-chanchi-global-` from the repository-skills prefix handling (and test both directions). |
| N2 | minor | `agent-chanchi-auditor` (phase 1) vs E and the phase table | The auditor agent is `audience: global` and phase 1 ships it, but `audience` and `agents link --global` are delivered in phase 5, and `agents_sync` does not know the key today. The ownership rule for user-home agents "same as the mirror" is keyed on names containing `-chanchi-global-`, which `agent-chanchi-auditor` and `agent-chanchi-item-builder` do not contain, so there is no marker for chanchi's own global agents. | Phase table rows 1 and 5; `agents_sync._parse` (fixed keys). | Ship `audience` and a minimal `agents link --global` in phase 1, or make the auditor a repo agent until phase 5; give chanchi-owned user-home agents their own header text and ownership rule, and consider renaming the field (`audience: repo\|user-home`) to stop overloading `global`. |
| N3 | minor | Roster, families and fallback | Fresh-catalog and pattern gaps. (a) "Available means ... in the catalog" and "an entry not in the catalog is an error" disagree for the built-in defaults on a new database (the template catalog holds only `human`): `audit open` errors for every default. (b) Families are seeded only for models already in the catalog at migration time; a model added later with `models add` is NULL (fail closed) unless `add` applies the same patterns or takes `--family`. (c) Patterns like `minimax*` must match the part after the provider slash, because the roster model is `opencode-go/minimax-m3`. | `uv run chanchi models list` on a scratch database (only `human:human`); roster example; `catalog.add_model`. | State one behavior for (a) (skip with a note, or fail with the `models add` hint listing all missing), apply the seed function in `models add`, and define pattern matching on the last path segment. |
| N4 | minor | Versions and hashes, Content hash | "the path, a NUL byte, the file's bytes, a NUL byte" has no length, so two different file sets can concatenate to the same stream when contents contain NUL bytes; the vercel-labs algorithm the design cites uses the decimal byte length. | vercel-labs/skills README, "Lock File Content Hash" (step 5: path, NUL, length, NUL, content). | Add the length field (or adopt the algorithm and test vectors verbatim) and say how nested `metadata.version` is read without a YAML dependency. |
| N5 | minor | Procedure step 7 and the outcome table | `audit round` is not guarded: nothing says it is refused unless the last outcome is `fix` or `rework`, or when round 3 is reached; `escalated` by "fewer than two voted" is not distinguished from a round-3 escalation in what the human receives. | Step 7 text; table rows 1 and 5. | State the guard and the error code, and let `audit show` print the escalation reason. |

## What must not change

- Principle 2's new wording, the ordered outcome table with the lone-finding rule, `audits` with stable subject
  keys and per-audit round numbers, the seat model with same-seat refill, fail-closed families.
- The `SYNC` resolution through the git common directory with `CHANCHI_SYNC` first, and the ownership
  principle of recognizing dangling mirror entries (only its link-text test needs the N1 fix).
- Private scratch paths for reports until every seat has voted, and the AGENTS.md wording.

AUDIT DONE
