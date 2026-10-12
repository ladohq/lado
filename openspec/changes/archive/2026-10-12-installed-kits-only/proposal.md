Task: LAD-22

## Why

LADO looks a kit up by name in the session's repository first (`<repo>/.lado/kits`), then
among the installed kits (lado.db), then among the built-in ones. So the list of kits
depends on the folder of the session:

- The New session window cannot show a folder's kits before it is chosen, and asks the
  server again for every folder (`GET /api/kits?where=`); with this change a later task
  can load it once.
- LAD-6 (start a session from a git URL) would clone a stranger's repository and start the
  MCP servers of its `.lado/kits` without a question, while a kit installed from git shows
  what it would start and asks `Install? [y/N]` first.
- Every place that reasons about kits carries the exception "a project kit shadows the
  installed one": `lado kits --repo`, `kits.available`'s shadowing, `runtime.kit_users`
  (remove-preview), `kits check` and `kits show`.

Developing a kit is covered already: `lado kits add <folder>` installs a folder that LADO
reads in place (docs/kits.md, "Develop it from a folder").

Root cause: the kit lookup takes the session's folder as an input.

## What Changes

- Kits are looked up only among the installed kits (lado.db), then the built-in ones. A
  repository's `.lado/kits` folder is never read.
- **BREAKING (CLI)**: `lado kits --repo` is gone (argparse refuses it); `lado kits`, `kits
  show` and `kits check <name>` list and resolve the same kits whatever the current folder.
- **BREAKING (API)**: `GET /api/kits` takes no `where`; it gives the same list for every
  folder. The New session window is not changed here (another task): it still sends its
  folder as `where`, which the server now ignores, so it gets the same list each time.
- The remove-preview (`runtime.kit_users`, `lado kits remove`, the Kits page) counts every
  session whose kits name the kit; no project exception.
- No migration, hint or warning for a repository that has `.lado/kits`: the feature is
  gone. A session stored with such a kit's name fails on resume with the usual
  `kit "<name>" not found`.
- Docs: AGENTS.md, docs/kits.md, docs/design/ui.md, CLI help and CHANGELOG.md say only
  installed and built-in kits exist.
- Tests that made a project kit as a fixture install a folder kit in the test's
  `LADO_HOME` instead (unit, integration, UI, live).
- Version: minor; the CLI and the API change. It lands in 0.36.0, already a minor bump
  (unreleased).

## Scope

- The core lookup (`kits.candidates`, `find`, `available`, `resolve`), `project_kits`
  removed, `repo` parameters dropped from the lookup.
- CLI: `lado kits` without `--repo`; `kits show`, `kits check`.
- API: `/api/kits` without `where`; `launch.kit_infos`, `launch._session_kit`;
  `web/openapi.json` and `web/src/api.gen.ts` regenerated.
- `runtime.kit_users` without the project exception; `runtime.exclude_worktrees`'
  docstring (`.lado/` stays visible for the project's own files, not kits).
- Docs and tests as above.

## Out of scope

- The New session window (`web/src/Launch.tsx`, `web/src/api.ts`'s `getKits`): it keeps
  asking `/api/kits` per folder with `where`; loading the list once is another task (the
  human's decision).
- A hint or warning for a repository that still has `.lado/kits`: the task says the
  feature is simply gone; a hint would be a second code path kept for good.
- Moving the kits of a running or stopped session to installed ones: the human installs
  the folder (`lado kits add <folder>`) when they want it back.
- Shadowing between an installed kit and a built-in kit of the same name: unchanged (the
  installed one wins, `lado kits` marks the built-in one `shadowed by user`).
- `.lado/` itself (sdlc.md, tracker.yaml, worktrees, the fingerprint's exclusion of
  `.lado/`): other features use that folder.
- LAD-6 (clone from a URL): blocked on this change, built separately.

## Impact

- `src/lado/kits.py`, `cli.py`, `runtime.py`, `runs.py`, `server/launch.py`,
  `server/app.py`; `web/openapi.json`, `web/src/api.gen.ts` (generated only).
- About 27 test files (unit, integration, UI, live) move to an installed folder kit.
- AGENTS.md (Layout: kits.py, launch.py, app.py's remove-preview; Design principles:
  Explicit lookup), docs/kits.md, docs/design/ui.md, CHANGELOG.md.
