Task: LAD-142

## Why

Every step of the projects epic (LAD-116, S1–S7b) is in `main` and ships in 0.43.0, but
the documents still describe projects as unfinished: `ROADMAP.md` leaves the Projects item
and its steps S2–S7 unticked, `AGENTS.md` calls `docs/design/projects.md` "mostly not
built yet", `docs/design/projects.md:98-99` says "the UI's addresses are not built yet
(step S6)", and `docs/design/ui.md:1842-1844` says a session in a project is "not built
yet" and that its look is "decided with a mockup at S3" (it was: the head shows the
project from `SessionAbout.project`, ui.md, Session head). Besides these false lines,
`docs/design/projects.md` and `docs/design/ui.md` speak of the product in the epic's step
numbers ("Built in step S2", "before step S3"), which only the epic's plan explains. The
readiness check before 0.43.0rc1 (gap G1, the human's decision #1402) asks for a docs step.

The same check found that going back from 0.43.0 to 0.42.x is not described: what stays
on disk, and what blocks the next upgrade. Checking that paragraph against the code found
one more fact users must know: `lado update <older version>` backs up the current
`lado.db` and deletes every other file in `~/.lado/backups/` (`self_update.py`,
`_back_up`), the schema-31 copies included, before the older LADO refuses the schema-35
database. Fixing that is LAD-143 (the human's answer #1410); this change tells users the
way round it.

Root cause: each step updated the documents for what it built and pointed at the steps to
come; no step owned the final pass, and the readiness check was the first to read the
documents as a whole.

Options:

1. Rewrite the documents to describe the built product without step numbers, and add the
   rollback paragraph with the manual way round the backup's deletion (chosen, #1408,
   #1410). Cost: none later; the step history stays in `docs/epics/lad-116/plan.md`.
2. Fix only the four false lines and keep "Built in step Sx" as history. Cost: ~30 lines
   that need the epic's plan to read, and the task's grep check is not literally empty.
3. Fix `lado update` in this step instead of describing the way round. Cost: code in a
   docs step of size S, against the brief's threshold; it is LAD-143.

## What Changes

Texts only; no code, test, API, CLI or schema change.

- **`ROADMAP.md`, Later → Projects**: the item and every step ticked, in place (the
  section already holds a ticked item, Kit marketplace). Steps listed as built: S1, S1b,
  S2, S2b, S3, S4, S5a, S5b, S6a, S6b, S7a, S7b, each one line by the plan's step title;
  "the epic LAD-116 builds it in steps that each merge on their own" becomes past tense
  ("built it in 0.43.0").
- **`AGENTS.md`, Read more**: `docs/design/projects.md`'s line loses "(mostly not built
  yet)"; the file stays at most 200 lines.
- **`docs/design/projects.md`**: no "not built yet" and no "step S<n>":
  - the intro's "the contract the epic's steps are built against; a step that changes the
    model changes this file" becomes the model as built in 0.43.0, which a change of the
    model changes;
  - the box "What is built" becomes one sentence: everything in this file is built in
    0.43.0 except the section Not now; which step built what is in the epic's plan
    (`docs/epics/lad-116/plan.md`);
  - "Built in step Sx (…)" becomes "Built: …" or the plain description, the facts in the
    parentheses (commands, routes, modules, schema numbers) kept;
  - "before step S3" / "from before S3" becomes "before 0.43.0" / "from before 0.43.0"
    (sessions made under `projects/` by an older LADO, #808);
  - "the UI's addresses are not built yet (step S6)" becomes what is built: the UI's
    `/projects` and `/projects/<id>` (docs/design/ui.md, Projects);
  - "(step S1, the row `Workspace:` …)" and the like lose the step, keep the fact.
- **`docs/design/ui.md`**:
  - line 700: "Projects was one until step S6a" becomes "Projects was one before 0.43.0"
    (or the sentence goes);
  - lines 1547 and 1672: "step S6b of projects.md" and "step S7b" go; the task keys
    (LAD-137, LAD-139), mockups and answers stay, as elsewhere in ui.md;
  - lines 1842-1845: `repos` is a list of one item, the session's repository; the project
    a session is in is not one of them: it comes as `SessionAbout.project` (Session head,
    above); more than one item comes only with sessions over several repositories
    (projects.md, Not now).
- **`docs/install.md`, Update → Going back to an older version**: after the existing
  paragraph, a paragraph on going back from 0.43.0 to 0.42.x, every fact checked against
  the code and the readiness report (`epic/epic-projects/delivery-report`, Upgrade from
  0.42.0):
  - 0.42.x refuses a `lado.db` of schema 35 (`made by a newer LADO … knows up to 31`); it
    needs the schema-31 backup the upgrade made, `~/.lado/backups/lado.db.schema-31`;
  - `lado update 0.42.x` keeps only its own new backup in `~/.lado/backups/` and deletes
    the rest, that copy too: copy it out first. The way, as commands: `lado stop --all`,
    `lado server stop`, copy `~/.lado/backups/lado.db.schema-31` out of `backups/`,
    `lado update 0.42.x` (or the installer's own command, "Installed otherwise"), then in
    `~/.lado` remove `lado.db-wal` and `lado.db-shm` and copy the saved file to
    `lado.db`; everything LADO recorded since the upgrade is lost;
  - in Docker the way back is "Go back to the version before" with `<N>` = 31, and the
    backup is not deleted;
  - what stays: the projects, their variables and which session is in which project are
    forgotten with the database; `<workspace>/projects/` stays with every repository in
    it; each project's data folder `~/.lado/projects/<id>/`, with its secrets in
    `secrets/`, stays until removed by hand;
  - upgrading again: `lado doctor` calls `projects/` "your own folder" and `lado project
    create` refuses until it is moved away; after that, `lado project create` with an id
    whose `~/.lado/projects/<id>/` is left refuses (`… is left from a project <id>: remove
    it or choose another id`), so a secret is never taken over silently.
- **`CHANGELOG.md`**, `## 0.43.0 (unreleased)`: one item under `### Improved` on the new
  paragraph (going back from 0.43.0: what stays, and copying the backup out first).

## Scope

- `ROADMAP.md`, `AGENTS.md`, `docs/design/projects.md`, `docs/design/ui.md`,
  `docs/install.md`, `CHANGELOG.md`.
- The check: `grep -rniE "not built yet|step S[0-9]" docs ROADMAP.md AGENTS.md README.md
  --exclude-dir=epics --exclude-dir=research --exclude-dir=superpowers` finds nothing
  about projects; the one remaining hit, `docs/design/ui.md:442` ("a section not built
  yet is a placeholder", the rule of placeholders), is not about projects and stays.

## Out of scope

- `lado update` deleting the backups (LAD-143, the human's answer #1410): code, beyond a
  docs step of size S.
- `RepoInfo`'s docstring "a project will have several" (`src/lado/server/models.py`): code,
  the brief allows none; the docs say sessions over several repositories are for later.
- LAD-140 and LAD-141: their own tasks; no document here says anything false about them.
- `docs/epics/`, `docs/research/`, `docs/superpowers/`, `openspec/changes/archive/`: the
  epic's and history's files, kept as written.
- The living specs: none says projects are not built (`openspec/specs/projects/spec.md:1483`
  requires that the UI shows no "not built yet"), so there is no delta.
- The version, the RC and LAD-80: the release is the human's own task.

## Impact

- Documents only; a patch-sized change inside 0.43.0 (no minor bump of its own).
- `tests/test_agents_md.py` checks AGENTS.md's length; no other test reads these files.
- The change has no delta: it is archived with `--skip-specs`.
