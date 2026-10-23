## 1. Projects built

- [x] 1.1 `ROADMAP.md`, Later → Projects: tick the item and list S1, S1b, S2, S2b, S3, S4,
  S5a, S5b, S6a, S6b, S7a, S7b as ticked, one line each by `docs/epics/lad-116/plan.md`'s
  step titles; the item's text in past tense. Check: each step's line matches the plan's
  Result of that step; no `- [ ]` left under Projects.
- [x] 1.2 `AGENTS.md`, Read more: drop "(mostly not built yet)". Check:
  `uv run pytest tests/test_agents_md.py -n0` passes (at most 200 lines).
- [x] 1.3 `docs/design/projects.md`: the intro and the box "What is built" as the
  proposal says; every "step S<n>" and "not built yet" rewritten by the proposal's rules,
  the facts in parentheses kept. Check: `grep -niE "not built yet|step S[0-9]|\bS[0-9][ab]?\b"
  docs/design/projects.md` is empty; each rewritten sentence read against the code it
  names (routes in `src/lado/server/app.py`, commands in `docs/cli.md`).
- [x] 1.4 `docs/design/ui.md`: lines 700, 1547, 1672 and 1842-1845 as the proposal says.
  Check: `grep -niE "not built yet|step S[0-9]" docs/design/ui.md` finds only line 442's
  placeholder rule; the `repos` sentence agrees with `SessionAbout` in
  `src/lado/server/models.py`.
- [x] 1.5 The whole grep of the proposal's Scope finds nothing about projects. Check: its
  output pasted into the build report and the pull request (the manual check).

## 2. Going back from 0.43.0

- [x] 2.1 `docs/install.md`, Going back to an older version: the paragraph and commands of
  the proposal. Check, each fact against its source, named in the build report:
  schema 35 and the refusal's words (`src/lado/state.py`, `SCHEMA_VERSION` and the newer
  check), the migration's backup name (`state.migrate`), `lado update` deleting the other
  backups (`src/lado/self_update.py`, `_back_up`), `lado stop --all` and `lado server stop`
  (`docs/cli.md`), the refusals of `projects.check_new` (own `projects/` and the left data
  folder, `src/lado/projects.py`) and doctor's "your own folder" (`src/lado/doctor.py`),
  the data folder (`project_secrets.data_folder`), and the readiness report's Upgrade from
  0.42.0. Nothing in the paragraph without a source.
- [x] 2.2 `CHANGELOG.md`, `## 0.43.0 (unreleased)`, `### Improved`: one item by
  docs/release.md's rules (bold title, at most three lines, the user's words). Check:
  `git diff CHANGELOG.md` adds only that item.

## 3. Checks

- [x] 3.1 `make lint`, `make test` (counts in the build report), `openspec validate
  projects-docs-built --strict`, `openspec validate --specs --strict`; no code changed,
  so no integration or UI run.
- [x] 3.2 The pull request's manual check: the branch and folder, `env | grep LADO_` and
  `unset` of what it finds, the grep of 1.5 with its expected empty result about projects.
