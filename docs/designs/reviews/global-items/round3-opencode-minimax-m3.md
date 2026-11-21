VERDICT: PASS WITH FIXES

# Audit round 3 (final) — global items design, Revision 3 (auditor: opencode / minimax-m3)

Subject: `git show e40d275` on branch `docs/global-items` — `docs/designs/global-items.md`
(revision 3), `docs/designs/global-items.brief.md`,
`docs/designs/continuous-improvement.md`, and
`docs/designs/reviews/global-items/round2-consolidation.md`.

Inputs read: the round-3 brief, my round-2 report
(`docs/designs/reviews/global-items/round2-opencode-minimax-m3.md`), the round-2
consolidation, Revision 2 and Revision 3 of the design side by side, the live harness CLIs
installed on this machine (`claude`, `opencode`, `agy`), `src/chanchi/` (`skills_link.py`,
`agents_sync.py`, `projects.py`, `record.py`, `lessons.py`, `catalog.py`, `modelspec.py`,
`taxonomy.py`, `db.py`, `cli.py`, `migrations/001_init.sql`,
`migrations/004_lessons.sql`), `tests/test_items.py`, `tests/test_layers.py`,
`tests/test_privacy.py`, and the primary vendor docs for the three harnesses.

No file was edited except this report. No reference-project name and no home path appears
below; the consumer projects and the reference projects are described generically.

## Re-check of my round-2 findings

| id | severity | status | evidence |
|---|---|---|---|
| GI-01 | blocking | **RESOLVED** | Unchanged and still correct: `audits.subject_kind` + `subject_ref` with `project_id` and `change_id` both nullable (R3 L318-329), and the concepts section still says "It may link a chanchi change and a project, both optional" (L192). |
| GI-02 | blocking | **RESOLVED** | The last hole is closed: `item_proposals` now exists in migration 006 with `kind, name, evidence, uses, owner_promoted, status, global_item, created_at, updated_at` (L486-497), and the text says "Each run of `items propose` stores its candidates (`item_proposals`, migration 006) with their evidence and counted uses" (L429). Scan, proposal and decision all have a table now. |
| GI-03 | major | **RESOLVED** | Unchanged: "`global` is a reserved project slug in every path that creates or derives a slug: `projects.register` (with or without `--name`), and the slug derivation used by `change open` and `project relink`" (L103-107). Verified against the code: `projects.register` derives the slug from `main.name` or `--name` (`src/chanchi/projects.py` L323-327), and `change open` reaches `projects.ensure` through `projects.identify` (`src/chanchi/cli.py` L143 → `src/chanchi/record.py` L99). |
| GI-04 | major | **RESOLVED** | Unchanged: "rendering returns content per harness kind (`claude`, `opencode`, `agy`) and takes the header text as a parameter; a target map turns kinds into paths" (L155-160). The current `render()` still returns repo-relative keys (`src/chanchi/agents_sync.py` L135-140), so the split is still a real, named change. |
| GI-05 | major | **RESOLVED** | Unchanged and still honest: the agy user agents folder "whose exact layout under `~/.gemini/config/agents/` is verified by a live probe before phase 2 is built" (L159-160). Live check on this machine: that folder does not exist, so the probe is genuinely still pending. |
| GI-06 | major | **RESOLVED** | Unchanged: "Text similarity scores are not a criterion: same-purpose skills score low (0.12 to 0.38 in the consumer projects)" (L423-424), with the independent-use count and the configurable threshold (`SYNC/config/promotion.toml`). |
| GI-07 | major | **RESOLVED** | Unchanged: "uses the existing fields: `target_kind: skill` … and `target: \"skill herdr\"` or `target: \"skill herdr (new)\"`. No new field." (L401-402). Matches the live schema (`src/chanchi/migrations/004_lessons.sql` L34-36). |
| GI-08 | major | **RESOLVED** | Unchanged: hooks, MCP, eval items and global rules files stay non-goals (L53-54), and the `SYNC/ITEMS/` tree still holds only `agents/` and `skills/` (L95-98). |
| GI-09 | minor | **RESOLVED** | Unchanged in effect, and now with a command: "`chanchi items retire <name> [--replaced-by <name>] --reason \"<why>\"` sets `status: retired` and appends … to `retired.json`" and "`items check` fails when a name listed in `retired.json` has any status other than `retired`" (L133-139). |
| GI-10 | minor | **RESOLVED** | Unchanged: "Until phase 1 is built, the procedure is run by hand and its rounds are backfilled into the database when the commands exist." (L382-383). |
| GI-11 | minor | **RESOLVED** | Unchanged: "opencode's native `~/.config/opencode/skills/` is not needed while opencode reads `~/.agents/skills/`; adding it is one line in the harness adapter if that changes." (L152-154). Re-verified at the primary source: opencode lists `~/.agents/skills` as a global compatibility source (https://opencode.ai/docs/skills/, Discovery). |
| GI-12 | minor | **RESOLVED** | Unchanged, and the family correction is now a named command: "The owner corrects it with `chanchi models set <agent:model> --family <name>`" (L277). The flag does not exist yet (`src/chanchi/cli.py` L471-481), which is a phase-1 deliverable covered by the phase table. |
| GI-13 | minor | **RESOLVED** | Unchanged and now more precise: a `SKILL.md` carries the fields "as `metadata:` followed by the indented lines `  version: \"<x.y.z>\"` and `  status: \"<status>\"`" and "chanchi's frontmatter reader accepts exactly that shape" (L115-118). The reader does not exist yet (there is no SKILL.md parser in `src/chanchi/` today; `agents_sync._parse` only parses `AGENT.md`), so this is a named, phase-2 deliverable. |
| GI-14 | minor | **RESOLVED** | Unchanged: the mirror removes a retired item's entries, the inbox shows the retirement, `items check` refuses to republish a retired name (L136-139), and the project-side `deprecate` keeps the follow-up visible (L454-455). |
| GI-15 | minor | **RESOLVED** | Both halves are now in the plan. The reserved-slug test is item 3 (L590-591) and the headless load is now a gate, not the last item: "9. **Gate for phase 2**: one headless run per harness loads a published test global skill through the mirror … phase 2 is not done until all three pass." (L605-606). The unlink interaction was added as item 6 (L599-600). |
| GI-16 | minor | **RESOLVED** | The precedence rule is now cited at the source and in both documents: "Claude Code prefers a personal skill over a project skill but a project subagent over a personal one (code.claude.com docs, *Skills* and *Subagents*), and opencode lets a project skill override a global one (opencode docs, *Skills*, precedence)" (L40-43), and the same in the brief (L70-72). Re-verified this round at the primary sources: Claude Code skills, "Enterprise over personal, and personal over project" (https://code.claude.com/docs/en/skills.md, *Resolve skills that share a name*); Claude Code subagents, project scope priority 3 over user scope 4 (https://code.claude.com/docs/en/sub-agents.md); opencode skills, sources "registered from lower to higher precedence" with project `.opencode/skills` last (https://opencode.ai/docs/skills/, *Precedence*). |
| GI-17 | minor | **RESOLVED** | The agy row is no longer self-contradictory: "`agy --agent <a> --model <base> --effort <e> -p=\"<prompt>\" < /dev/null`, where the catalog id `<base>-<e>` (for example `gemini-4-neon-high`) is split into base and effort; a roster `effort` that differs from the id's suffix is an error" (L303). Verified live: `agy --model gemini-4-neon --effort high` → `OK`; `agy --model gemini-4-neon-high --effort xhigh` → `error: invalid model selection … --model gemini-4-neon-high conflicts with --effort=xhigh`; `agy --model gemini-4-neon-high` → `OK`. The other two templates still match the installed CLIs (`claude --help` shows `--effort <level>`; `opencode run --help` shows `--model, -m string … provider/model#variant` and no `--effort`). |
| GI-18 | minor | **RESOLVED** | Unchanged: the database path is stated as the code has it ("default `$XDG_DATA_HOME/chanchi/chanchi.db`", L68 — matches `src/chanchi/db.py` L20-24), and `AGENTS.md` still states the third naming form ("The user's global items are `<item>-chanchi-global-<name>` (`global` is a reserved slug)", `AGENTS.md` L91-94). |
| N-01 | major | **RESOLVED** | `item_proposals` is defined with `evidence` (JSON), `uses`, `owner_promoted` and `status` (L486-497), and the text ties the two together: "`items propose` records it as owner-promoted" (L427) and "Each run of `items propose` stores its candidates (`item_proposals`, migration 006)" (L429). The proposal record finally has a home. |
| N-02 | major | **RESOLVED** | One contract, stated once: the catalog id `<base>-<e>` is split into base and effort, and a roster effort that disagrees with the id suffix is an error (L303). The contradictory parenthetical is gone. Live verification above confirms the split is the form agy accepts and that the mismatch is a hard error, not an empty seat. |
| N-03 | major | **RESOLVED** | The rule is now operationalised in three places: the principle states the per-harness disagreement with sources (L39-45), the Mirror section adds "**Name collisions.** Before writing, the mirror and `items check` fail when a global item's name equals any project item recorded by `items scan` or any of chanchi's own items." (L180-181), and the verification plan adds item 7 (L601-602). The naming invariant is also structural: a global name carries the literal `-chanchi-global-` and a project name carries `-chanchi-<slug>-` with `global` reserved, so the two forms cannot collide. |
| N-04 | minor | **RESOLVED** | The separation is now a stated rule with tests in both directions: "`chanchi skills link/unlink` keep recognizing only links into this repository's `skills/` and never touch mirror entries; `items mirror --remove` never touches `skill-chanchi-*` links of chanchi's own skills. Tests cover both directions." (L170-172), plus verification item 6 (L599-600). I re-verified that the claim holds for the code as it stands: `_is_own` returns `False` for a mirror entry whose target is outside the repository's `skills/` directory (`src/chanchi/skills_link.py` L163-174), and for a relative secondary link whose relative path does not match the primary's (`src/chanchi/skills_link.py` L177-195). The test the design names is the right guard for the generalization. |
| N-05 | minor | **RESOLVED** | The match rule is now explicit: "matched on the last `/`-separated segment of the model with any `#variant` removed, so `opencode-go/minimax-m3#thinking` matches `minimax*`" (L272-277). Verified against the design's own pattern list with `fnmatch`: `opencode-go/minimax-m3` → `minimax`, `opencode-go/minimax-m3#thinking` → `minimax`, `sonnet` → `anthropic`, `gemini-4-neon-high` → `google`, `gemini-4-hydrogen-high` → `google`. The built-in roster now yields three distinct known families (anthropic, google, minimax), so a round opened with the default roster is no longer degraded by an unknown family. |
| N-06 | minor | **RESOLVED** | The audits table now mirrors the lessons pattern: `author_raw TEXT NOT NULL, -- agent:model[:effort] as declared` and `author_model_id INTEGER REFERENCES models(id), -- NULL when not in the catalog` (L324-325). This matches `src/chanchi/migrations/004_lessons.sql` L29-31 (`author_agent`, `author_model_raw` NOT NULL; `author_model_id` nullable), so an audit can be opened for a model the owner has not costed yet. |

Summary: 24 RESOLVED, 0 PARTIAL, 0 OPEN. Both round-2 blocking findings and all three
round-2 major new findings are closed.

## New findings

| id | severity | where | problem | evidence | fix |
|---|---|---|---|---|---|
| R3-01 | major | `global-items.md` L431-432 (C. Propose, the `lesson apply` command) | The command as written is rejected by the existing code. The design gives the literal command `chanchi lesson apply <id> --site global --where "SYNC item <name>@<version>"`, but `lessons.apply` requires the `--where` text to contain the literal tag `[lesson #<id>]` and raises `invalid_value` with the hint `"<path> [lesson #<id>] @ <commit>"` otherwise. The design's value carries no tag, so the phase-3 publish flow ("When a global item built from lessons is published, those lessons are applied at the global site") fails on the first command it names. | `src/chanchi/lessons.py` L863-871: `tag = f"[lesson #{lesson_id}]"`; `if tag not in where: raise _bad("where", f"where must contain {tag}", hint='"<path> [lesson #<id>] @ <commit>"')`. Reproduced with the design's literal string: `contains required tag? False`. The CLI declares `--where` as required with the same format hint (`src/chanchi/cli.py` L621-624). | Write the value with the tag and a path: `--where "SYNC/ITEMS/skills/<name>/SKILL.md [lesson #<id>] @ <version>"`. Also worth stating that the lesson must be `approved` and `agnostic` to be applied at the global site (`src/chanchi/lessons.py` L878-893), because a non-agnostic lesson is rejected for any site but its origin project. |
| R3-02 | major | `global-items.md` L44-45 (Principle 4, last clause) and L601-602 (verification plan item 7) | The design states a rule that the repository does not currently enforce, in the present tense, and then leans on it. "chanchi's own items never use `-chanchi-global-` (**`tests/test_items.py` enforces the last rule here**)" — but `tests/test_items.py` contains no such check today: the file ends at line 79, its name regex `^(agent\|skill\|eval\|hook)-chanchi-[a-z0-9]+(-[a-z0-9]+)*$` **matches** `skill-chanchi-global-foo`, and `grep -n "global" tests/test_items.py` returns nothing. The rule is real and is the design's main structural defence against the same-name clash it spends a principle explaining, but the sentence reads as a description of the present. (Verification item 7 states it correctly as a deliverable: "`tests/test_items.py` refuses an own item named `*-chanchi-global-*`.") | `tests/test_items.py` L12 `NAME = re.compile(r"^(agent\|skill\|eval\|hook)-chanchi-[a-z0-9]+(-[a-z0-9]+)*$")`; the file has 79 lines and no reference to `global`; `re.match(NAME, "skill-chanchi-global-foo")` → `True`. | Reword the principle as a rule with its test, e.g. "chanchi's own items never use `-chanchi-global-`; `tests/test_items.py` refuses one (phase-2 deliverable)". Alternatively add the check to `tests/test_items.py` in the same phase that introduces the global naming, so the present tense becomes true. |
| R3-03 | minor | `global-items.md` L177-178 (Harness detection, last sentence) | The claim about which harness reads `~/.agents/skills/` is wrong, and it contradicts both the same document and the repository's own documentation. "`~/.agents/skills/` is written when Claude Code or opencode is installed (**both read it through the chain**)" — Claude Code does not read `~/.agents/skills/`. The Claude Code skills documentation lists Enterprise, Personal (`~/.claude/skills/`), Project, Nested, Additional directory, Plugin and claude.ai account; `agents/skills` appears in none of the Claude Code documents. The same paragraph's earlier bullet (L150) states it correctly: "an absolute link in `~/.agents/skills/` (read by opencode and agy workspaces)". The repository's own `AGENTS.md` and `README.md` also state it correctly. The effect is a directory written for a harness that will never read it, plus a rule an implementer cannot trust. | `curl -s https://code.claude.com/docs/en/skills.md \| grep -c "agents/skills"` → `0`; the same grep over `sub-agents.md`, `settings.md`, `memory.md`, `cli-reference.md`, `plugins.md`, `overview.md` → `0` in every case. The Claude Code skills table lists `Personal \| ~/.claude/skills/<skill-name>/SKILL.md` and the precedence row "Enterprise over personal, and personal over project". `AGENTS.md` L23: "`.agents/skills/` (opencode, agy) and `.claude/skills/` (Claude Code)"; `README.md` L41: "`.agents/skills/skill-chanchi-*` (read by opencode and agy) and `.claude/skills/skill-chanchi-*` (read by Claude Code)". | Change the condition to the harness that actually reads it: "`~/.agents/skills/` is written when opencode or agy is installed (both read it through the chain)". The `~/.claude/skills/` secondary already covers Claude Code. If the mirror keeps writing `~/.agents/skills/` for Claude Code for symmetry, say so as an explicit no-op rather than as a reason. |
| R3-04 | minor | `global-items.md` L148-154 (Mirror, Skills bullet) and L173-179 (Harness detection) | The mirror's target map for agy covers `~/.gemini/antigravity-cli/skills/` but not the other agy skills folder the brief recorded, and the agy detection folder (`~/.gemini`) is broader than the folder agy actually reads skills from. The brief's harness facts list three agy locations — `~/.gemini/config/skills`, `~/.gemini/antigravity-cli/skills` and `~/.gemini/config/agents` — while the design's mirror writes only the middle one for skills. On this machine `~/.gemini/antigravity-cli/skills` exists and holds the project's own skills, and neither `~/.gemini/config/skills` nor `~/.gemini/config/agents` exists; `~/.gemini` also holds four unrelated directories (`antigravity`, `antigravity-backup`, `antigravity-ide`, `antigravity-cli`), so "the folder whose existence means agy is installed" is true for an Antigravity-IDE-only user who never runs the CLI. | Brief L67-68: "agy reads `~/.gemini/config/skills`, `~/.gemini/antigravity-cli/skills` and `~/.gemini/config/agents`". Design L152-153 writes only `~/.gemini/antigravity-cli/skills/`; design L175 names `~/.gemini` as the agy detection folder. Live: `ls ~/.gemini/` → `antigravity antigravity-backup antigravity-cli antigravity-ide config GEMINI.md jetski-standalone-oauth-token sandbox`; `ls ~/.gemini/config/skills` → "No such file or directory". | Either add `~/.gemini/config/skills/` to the agy target map with the same existence check the design already uses for the agents folder (which is explicitly deferred to a live probe, L159-160), or say why it is dropped. Consider detecting agy by `~/.gemini/antigravity-cli` for the skills path rather than by `~/.gemini`. This is the same "defer to a live probe" honesty the design already applies to the agents folder. |

## What must not change

Unchanged from rounds 1 and 2 and still correct:

- **The ownership model.** `SYNC/` stays in `.gitignore`, the items stay in the user's folder, the
  database stays local, nothing is pushed to a project. Verified: `git check-ignore -v SYNC` →
  `.gitignore:53:SYNC`.
- **The naming separation.** The reserved `global` slug has a named home (every slug-creating and
  slug-deriving path) and a named test.
- **The three-auditor, two-of-three, three-round rule and the degraded-round record.** The ordered
  outcome table (L219-225) is a correct implementation of it, including the lone-finding rule and
  the escalation row; Revision 3 adds the `escalation` column (`quorum` | `round_cap`) and the
  guards on `audit close` / `audit vote` / `audit unavailable` (L231-233, L338).
- **The "proposed, never pushed" principle.** Unchanged and still right; the adoption decision
  stays with each project and is audited before it is applied (L456-458).
- **The explicit wrapper instead of inheritance.** Unchanged and still right.
- **The AGENTS.md audit bullet.** Unchanged.
- **The draft-until-audited rule.** New in Revision 3 and correct: `status: draft|published|retired`,
  the mirror never exposes a draft, and `items publish` requires an accepted `item` audit at the
  item's current version (L114-124).

## Verified facts (checked against the primary source this round)

- The three headless launch forms match the installed CLIs: `claude --help` shows
  `--effort <level>`; `opencode run --help` shows `--model, -m string … provider/model#variant` and
  no `--effort`; `agy --help` shows `--effort … (low|medium|high|xhigh|max)` and `-p`.
- agy's model ids all carry an effort suffix (`agy models` → `gemini-4-neon-high`,
  `gemini-4-neon-xhigh`, `claude-opus-5-5-high`, …), and agy rejects a conflicting `--effort`.
  `taxonomy.LAUNCH_EFFORTS = ("low","medium","high","xhigh","max")` matches agy's `--effort` values.
- Claude Code skills: "Enterprise over personal, and personal over project"; Claude Code
  subagents: project scope priority 3, user scope priority 4, "Claude Code uses the one from the
  higher-priority location" (https://code.claude.com/docs/en/skills.md, .../sub-agents.md).
- opencode skills: global `~/.config/opencode/skills` plus global-compat `~/.claude/skills` and
  `~/.agents/skills`; project `.opencode/skills` registers last and therefore wins
  (https://opencode.ai/docs/skills/, *Discovery* and *Precedence*).
- opencode global agents are flat `*.md` under `~/.config/opencode/agents/`
  (https://opencode.ai/docs/agents/, *Locations*) — matching the design's user target map.
- Claude Code does not read `~/.agents/skills/`: `agents/skills` appears in none of its
  documentation pages (see R3-03).
- The design's `SYNC` resolution works here: `git rev-parse --path-format=absolute
  --git-common-dir` → `<repo>/.git`, whose parent is the main checkout.
- The mirror's skills plan matches the existing code: `skills_link.plan_targets` makes
  `<base>/.agents/skills` the primary (absolute links) and `<base>/.claude/skills` plus
  `<base>/.gemini/antigravity-cli/skills` the secondaries (relative links)
  (`src/chanchi/skills_link.py` L39-45) — exactly what the design describes for the mirror.
- `chanchi skills unlink` really does leave mirror entries alone today (see N-04's evidence).
- The `models set --family` flag does not exist yet (`src/chanchi/cli.py` L471-481) and
  `models.family` does not exist yet (`src/chanchi/migrations/001_init.sql` L3-13); both are
  phase-1 deliverables of migration 005, as the phase table states.
- The migration-number clash with the lessons design is handled on both sides: the design takes
  005 (L312-313) and the lessons design renumbers its stage 3
  (`docs/designs/continuous-improvement.md` L108, L950).
- The baseline is green: `uv run pytest` → 454 passed. `tests/test_privacy.py` passes (3 passed),
  so Revision 3 leaks neither a home path nor a reference-project name.
- The CLI groups are still `db, models, taxonomy, skills, agents, change, session, incident,
  project, lesson, scoring` — no `audit`, `sync` or `items` group exists yet, consistent with the
  phase table.

## Not verified / out of scope

- The behaviour of the other two auditors' round-2 findings and their reports; this report covers
  only my own round-1 and round-2 findings, re-checked against Revision 3.
- The agy global agents layout, which the design itself defers to a live probe (L159-160). On this
  machine that folder does not exist, so nothing could be confirmed there.
- Whether the owner intends the `SYNC` folder to be a git repository, a cloud-synced folder, or
  both; the design covers the link and the status, not the transport.
- The `install: repo|user` field's validation in `agents_sync`: the current parser silently drops
  an unknown frontmatter key (verified: an `install: user` key parses without error and without
  reaching the `AgentSource`), so the design's phase-1 work includes adding it to the parsed
  fields. The design names the field but not the parser change; this is covered by R3-02's fix
  pattern and is not counted as a separate finding.

## Recommendation

Pass with fixes. Revision 3 closes every finding I raised in rounds 1 and 2, and it closes them
with the right shape — a rule where there was an assertion, a table where there was a claim, a
command where there was a description. The four remaining findings are small and local: two
one-line corrections (R3-01's `--where` tag, R3-03's harness condition), one present-tense
correction that should become a deliverable (R3-02), and one target-map completion for agy
(R3-04). None of them touches the ownership model, the adoption model or the audit procedure, and
none of them makes the design unbuildable. This is the point at which the design can be merged
and phase 1 planned.
