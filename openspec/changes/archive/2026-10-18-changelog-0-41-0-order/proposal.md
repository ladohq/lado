Task: LAD-101

## Why

The section `## 0.41.0 (unreleased)` of CHANGELOG.md becomes the notes of the GitHub
releases of 0.41.0rc1 and 0.41.0 (`scripts/release_notes.py`), which users read. It
breaks the order docs/release.md (CHANGELOG.md) sets: user items, then `Upgrade:` items,
then `API:` / `MCP:` items last.

- It has no `Upgrade:` item, though 0.41.0 migrates lado.db to schema 31 and, in Docker,
  opening LADO on a phone needs 0.41.0's `compose.yaml`.
- The facts for integrators sit inside three user items: Start from scratch (LAD-98),
  opening LADO on another device (LAD-94) and answering with files (LAD-86).

Root cause: each pull request added its own item and wrote its API and upgrade facts into
it; nothing checks the section's order, and no one gathered the section before the RC.

Options:

1. Rewrite the section by hand, once, before the RC (chosen). Cost: none later; the same
   slip can recur in the next release, caught by the release's own read of the notes.
2. Also add a check to `scripts/release_check.py` that an `(unreleased)` section's items
   go user, `Upgrade:`, `API:`/`MCP:`. Cost: code and tests to keep, a heuristic that
   cannot tell an inline `API:` sentence from a user's word "API"; the task allows no code.
3. Leave the section and fix the GitHub release's notes by hand after the tag. Cost: the
   notes and CHANGELOG.md drift apart (one source of truth broken), and PyPI's RC already
   points users at them.

## What Changes

Only CHANGELOG.md's section `## 0.41.0 (unreleased)`; the nine user items keep their
order and their facts.

- The Start from scratch item ends at "`lado doctor` has a new check, `git author`.": its
  sentence `API: …` moves to its own item.
- The item on opening LADO on a phone or another computer loses `(POST
  /api/access/new-token)` after "without a restart", and its Docker sentence becomes "In
  Docker set `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=<this computer's name>` in
  `.env`." (the `compose.yaml` part moves to the Docker upgrade item).
- The item on answering with files ends at "previews and chips.": its sentences "The
  API's …" and "lado.db goes to schema 31 (`gates.answer_note`)." move to the items below.
- After the nine user items, in this order, wrapped at 90 columns with two-space
  continuation lines as the file's other items:

  ```markdown
  - Upgrade: schema 31, restart running sessions after the update (lado update does it).
  - Upgrade: Docker: take 0.41.0's `compose.yaml`, as every update does (docs/install.md,
    Update the container). Only it publishes the port on `LADO_LISTEN` and passes
    `LADO_LISTEN` and `LADO_PUBLIC_HOST` to the container: under 0.40.0's no other device
    reaches LADO and the UI shows no link for a phone.
  - API: `GET /api/scratch-target` (`ScratchTarget`), `where` of kind `scratch` and `title`
    for `POST /api/sessions`, `FolderInfo.scratch`.
  - API: `GET /api/access` (`AccessInfo`), `POST /api/access/new-token`.
  - API: `POST /api/sessions/{name}/answers` and
    `POST /api/sessions/{name}/gates/{gate}/answer` take `artifacts`; `GateInfo` gains
    `answer_attachments`.
  ```

Facts checked against `v0.40.0..origin/main` (a93d366):

- `docker/compose.yaml` changed only for `LADO_LISTEN` and `LADO_PUBLIC_HOST`; mise,
  `make`, `gcc`/`g++` and `~/.local` for `npm install -g` / `uv tool install` are in the
  image (`docker/Dockerfile`, `docker/profile.sh`, `docker/mise.toml`) and need no new
  `compose.yaml`.
- New routes: `GET /api/access`, `POST /api/access/new-token`, `GET /api/scratch-target`;
  new models `AccessInfo`, `ScratchTarget`, `ScratchProblem` (a field of `ScratchTarget`);
  `FolderInfo.scratch`, `Launch.title`, `Where.kind` `scratch`, the answers' `artifacts`,
  `GateInfo.answer_attachments`. `GET /api/access` was not in the section at all.
- `src/lado/mcp_server.py` is unchanged: no `MCP:` item.
- Every user-visible task since v0.40.0 has its item: LAD-92, LAD-98, LAD-94, LAD-93, the
  container's `npm install -g`, LAD-97, LAD-86, LAD-95, LAD-87. PRs #90, #91 and #100
  changed release and plan documents only, nothing users see.

## Scope

- CHANGELOG.md, the section `## 0.41.0 (unreleased)` only.

## Out of scope

- The version, the date and the RC (`uv version 0.41.0rc1`, the tag): the release is its
  own work the human starts (docs/release.md), and the integrator never bumps or dates.
- Past sections: docs/release.md says they stay as written.
- A check of the section's order in `scripts/release_check.py` (option 2): the task is
  documents only; its heuristic would cost more than one read of the notes per release.
- dependabot's TypeScript 6.0 (PR #41), LAD-94's review leftovers (F5, E4) and the flaky
  tests LAD-96, LAD-99: the human left them out of this task (artifact
  `release-0.41.0-prep`, section 2).
- The tracker's LAD-10 and LAD-100: section 3 of that plan, not this change.

## Impact

- CHANGELOG.md only. No code, API, CLI, MCP or schema change; no version bump.
- No test reads the real CHANGELOG.md (the tests of `scripts/release_notes.py`,
  `release_check.py` and `rc_check.py` use their own texts); the check is
  `python3 scripts/release_notes.py v0.41.0rc1`, the notes the Release workflow will
  publish, read as a user reads them.
