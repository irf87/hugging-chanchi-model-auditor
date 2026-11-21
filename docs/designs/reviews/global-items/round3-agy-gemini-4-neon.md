VERDICT: PASS

## Round-2 findings re-check

| id | round-2 severity / status | status | evidence (Revision 3, commit `e40d275`) |
|---|---|---|---|
| R2-1 / F6 | major / PARTIAL | RESOLVED | Ownership is now tracked by `$XDG_DATA_HOME/chanchi/mirror.json` (independent of symlink targets), covering primaries, relative secondaries, and generated agent files across `SYNC` re-pointing or unmounting, with explicit separation from `chanchi skills link/unlink` (`docs/designs/global-items.md:162–172, 595–600`). |
| R2-2 | major | RESOLVED | Migration 005 family seeding now matches on the last `/`-separated segment with any `#variant` removed (e.g., `opencode-go/minimax-m3#thinking` -> `minimax`), covering provider-prefixed opencode models (`docs/designs/global-items.md:272–277`). |
| R2-3 / F10 | major / PARTIAL | RESOLVED | Items carry `status: draft\|published\|retired`; `chanchi items retire` sets `status: retired` and appends to `retired.json`, keeping the directory for history, while `items mirror` skips non-`published` items and `items check` fails only if a retired name has any status other than `retired` (`docs/designs/global-items.md:114–124, 133–139, 145`). |
| R2-4 | major | RESOLVED | `harnesses.py` defines explicit detection folders per harness (`~/.claude`, `$OPENCODE_CONFIG_DIR`/`$XDG_CONFIG_HOME/opencode`/`~/.config/opencode`, `~/.gemini`) with an optional existence parameter on `skills_link`, and `install: repo\|user` plus `chanchi agents link --user` moved to Phase 1 alongside `agent-chanchi-auditor` (`docs/designs/global-items.md:173–179, 288, 517–523, 559`). |
| R2-5 | minor | RESOLVED | `audit round` accepts `--commit <sha> \| --version <x.y.z>` and enforces round/outcome guards, `audit close` refuses open `assigned` seats and records `escalation` (`quorum\|round_cap`), `audit_seats.harness` was dropped, and `docs/designs/continuous-improvement.md:108` now notes the migration 005 renumbering (`docs/designs/global-items.md:227–233, 338, 348`; `docs/designs/continuous-improvement.md:108`). |

## New findings in Revision 3

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| R3-1 | minor | `docs/designs/global-items.md` L150–152, L177–178 | **Primary chain target omits `agy`-only installations.** L150–152 makes `~/.gemini/antigravity-cli/skills/<n>` a relative symlink to `~/.agents/skills/<n>`, but L177 states "`~/.agents/skills/` is written when Claude Code or opencode is installed", omitting `agy`; on a machine with only `~/.gemini`, the agy relative link would dangle. | `docs/designs/global-items.md:150–152, 177–178` (`VERIFIED`). | Change L177 to write `~/.agents/skills/` whenever any installed harness chains through it (Claude Code, opencode, or agy). |
| R3-2 | minor | `docs/designs/global-items.md` L180–181, L463–484, L560–561 | **Phase-2/3 sequencing detail on `project_items` collision check.** L180–181 states `items mirror` and `items check` (Phase 2) fail on collisions with `project_items` recorded by `items scan`, which arrives in migration `006_items.sql` (Phase 3); similarly L520 notes `agents link --user` (Phase 1) shares the manifest helper introduced for `items mirror` (Phase 2). | `docs/designs/global-items.md:180–181, 463–484, 520, 559–561` (`VERIFIED`). | Note in Phase 1/2 plans that the manifest helper ships in Phase 1 (reused by Phase 2) and that Phase 2 checks collisions against chanchi's own items while Phase 3 adds the `project_items` check once migration `006` lands. |
