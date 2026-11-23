---
name: skill-chanchi-item-adoption
description: Use when the owner asks a project to check whether there are global items to adopt, or when chanchi items inbox lists entries for the project. Compares each global item with the project's own items, proposes adopt, wrap, keep or deprecate, applies it with the owner's go-ahead, and records the audited decision.
---

# chanchi — item adoption

Global items are available, never imposed: only this project's decision changes its own items.
Follow the project's own rules (its rules file, branches, commits) for every change in it.

**Roles.** Steps 1-3 and 5a can be done by a delegated agent running unattended; it stops after
each of them and reports. Steps 4, 5b and 6 belong to the project's orchestrating role, the only
one that asks the owner, opens audits and writes chanchi records.

## 1. Read the inbox

`chanchi items inbox [--project <project slug>]` lists, for this project, every global item that needs a decision: `new` (no
decision yet), `changed` (a new version since the decision), `deprecate_pending` (a removal still
open) and `retired` (an item the project adopted or wrapped was retired; see `replaced_by`). Each
entry gives the item's folder (`path`) and `similar`: the project's own items that overlap it.
Take one entry at a time.

## 2. Compare

Read the global item in its folder and every `similar` item. Sort each rule of the project's items
into one of:

- **covered** — the global item states it (in any words);
- **particular** — only this project needs it (its paths, roles, models, runbooks, layout);
- **vendored** — text generated from an upstream source that the global item points to instead;
- **conflict** — the project's rule contradicts the global item.

## 3. Propose one decision

- **adopt** — nothing particular remains: remove the project's copies and update every reference
  to them (rules files, roles, other skills, scripts) to the global name.
- **wrap** — particular rules remain: keep them in `<kind>-chanchi-<project-slug>-<name>`, which
  starts by telling the agent to load the global item first and to follow it for everything the
  wrapper does not say; it holds only particular rules; move references to the wrapper's name and
  remove the old copies.
- **keep** — the project keeps its own item as it is; say why (for example a conflict the owner
  wants to keep).
- **deprecate** — the project's item is to be removed in a later change; name that follow-up. The
  entry stays in the inbox as `deprecate_pending` until a later adopt, wrap or keep.

A `retired` entry takes only keep (acknowledge it; no local item needed if the project adopted it)
or deprecate; its `replaced_by`, if any, is adopted or wrapped as its own entry. Vendored text and
scripts that only regenerate it are removed under adopt and wrap.

Write the proposal (decision, reason, the comparison table and every file the change touches) to
`<SYNC>/reviews/<global item>/<version>/adoption-<project slug>.md`, where `<SYNC>` is the path
`chanchi sync status` prints. Never write it inside the project.

## 4. Ask the owner

Show the owner the decision, the reason and the files it touches, with your recommendation, and
wait for a go-ahead for this project. Without it, stop here.

## 5. Apply and audit

a. Apply the approved change in a git worktree of the project, created outside the project's
   folder, on a new branch, touching only the files the proposal names, and commit it there.
   Keep and deprecate change no file: skip this step.
b. Audit it with three auditors (`skill-chanchi-audit-rounds`):
   `chanchi audit open --kind adoption --ref <project slug>:<global item> --commit <sha> --author <agent:model[:effort]> --project <project slug>`,
   where `<sha>` is the branch commit, or the project's current `HEAD` for keep and deprecate.
   The brief gives the project path, the proposal file and the diff, and asks the auditors to
   check that no covered, particular or conflicting rule was lost, that a wrapper holds only
   particular rules, and that every reference resolves.

## 6. Record

When the audit is accepted:
`chanchi items decide <global item> --decision <decision> --version <version> [--local <item>] --reason "<why>" --audit <audit id> --project <project slug>`.
Confirm with `chanchi items inbox --all --project <project slug>` that the entry is `up_to_date`
(or `deprecate_pending` after deprecate). Merging the branch follows the project's own rules and
the owner's go-ahead; after the merge, `chanchi items scan --project <project slug>` refreshes the
inventory.

If something went wrong, the orchestrating role follows `skill-chanchi-lessons`; a delegated agent
says so in its report.
