## Context

The kit lookup is `kits.candidates(repo)`: `_in_folder(<repo>/.lado/kits, "project")`,
then `installed_kits()` (lado.db), then `builtin_kits()`. `find(name, repo)`,
`available(repo)` and `resolve(repo, ...)` take the repository only to pass it there.
Callers: `runtime.start_session` and `spawn_worker` (`kits.resolve(sess.repo, ...)`),
`runs.py` (`kits.resolve(sess.repo, ...)`), `cli.cmd_kits` / `cmd_kits_show` /
`cmd_kits_check` (`--repo`, `_repo_or_none`), `server/launch.kit_infos(where)` (`GET
/api/kits?where=`) and `launch._session_kit(name, repo)` (`GET …/about`).
`runtime.kit_users` skips a session whose repository has `.lado/kits/<kit>`. The web UI
asks `getKits(root)` again for every folder (`Launch.tsx`, `useAsked`).

Root cause: the lookup takes the session's folder as an input, so every consumer of the
kit list carries a folder and a shadowing exception.

## Options

1. **Remove project kits** (chosen; the task's decision). The lookup has no folder: one
   list per `LADO_HOME`. Long-term cost: none added; four parameters, one CLI option,
   one query parameter and one exception go. A kit developer runs `lado kits add
   <folder>` once.
2. **Keep them, ask before starting a project kit's MCP servers** (as an install asks).
   Fixes LAD-6's risk but not the Launch window (the list still depends on the folder),
   and adds a confirmation path in the core, the CLI and the UI that every later feature
   (projects, LAD-7) must carry. High long-term cost.
3. **Keep them behind an opt-in** (a setting or `--project-kits`). Two lookups to test
   and document for good, against "Only what is used": no kit in use relies on them (this
   repository has no `.lado/kits`).

Held against ROADMAP.md: stage 7's desktop app and the coming projects (LAD-6, LAD-7)
want a kit list that is the machine's, not the folder's. Design principles: *Explicit
lookup* gets simpler (two places, both shown by `lado kits`); *One source of truth*: the
installed kits are one table; *No silent drops*: a session that named a project kit fails
loudly on resume with `kit not found`; *Neutral core*: no provider is involved.

## Decisions

- **D1. The lookup takes no folder.** `kits.project_kits` is deleted. `candidates(with_installed=True)`,
  `find(name)`, `available(with_installed=True)` and `resolve(kits, without=(),
  expected=REQUIRE)` lose their `repo` parameter; every caller is updated. `find`'s error
  names the installed kits in lado.db and the built-in folder, then `migration_hint()`
  and `legacy_hint()` as today.
- **D2. Shadowing stays only between installed and built-in.** `available` still pairs
  each kit with the place of the kit that shadows it, so `lado kits` keeps `(shadowed by
  user)` for a built-in kit an installed one of the same name hides; `launch.kit_infos`
  still skips shadowed ones.
- **D3. `Found.where` is `user` or `built-in`.** The comment and the module docstring
  drop `project`. `_in_folder` stays for the built-in folder; its broken-link branch and
  `Found._check`'s broken-link check only served project kits (the built-in folder ships
  in the package, installed kits are rows with a folder, not links): both are removed.
- **D4. CLI.** `kits_cmd`'s `--repo` argument and `_repo_or_none` are deleted.
  `cmd_kits_check` on a folder loads it as today (`load_release`) and resolves it with
  `kits.resolve([kit], expected=ASSUME)`; by name it uses `kits.find(args.kit)`.
- **D5. API.** `GET /api/kits` takes only `has_db`; `launch.kit_infos(has_db)`.
  FastAPI ignores an unknown query parameter, so the current page, which still sends
  `where=` (D6), gets 200 and the same list. `make web-types` regenerates `web/openapi.json` and `web/src/api.gen.ts`.
  `launch._session_kit(name)` drops its `repo`.
- **D6. The web UI is not touched** (the human's decision: the New session window is
  another task). `web/src/api.ts`'s `getKits(where)` and `Launch.tsx` stay as they are:
  the window still asks `/api/kits?where=<folder>` per folder and gets the same list each
  time (D5). Only the generated `web/openapi.json` and `web/src/api.gen.ts` change; `make
  web` must stay green with them (`getKits` builds its URL by hand, so it compiles).
- **D7. `runtime.kit_users`** counts every session whose `kits` contains the name.
- **D8. `runtime.exclude_worktrees`' docstring**: the rest of `.lado/` stays visible so
  the project's own files there (e.g. `sdlc.md`) can be committed; no mention of kits.
  Behaviour unchanged.
- **D9. Tests install a folder kit.** One helper, `install_kit(folder) -> str` in
  `tests/agent_helpers.py` (shared by unit, integration, UI and live tests; it imports
  only `lado.state`), writes `state.add_kit(state.InstalledKit(<name from kit.yaml>,
  folder=str(folder)))` into the test's `LADO_HOME` and returns the name. Kit folders move
  out of the repository to `tmp_path / "kits" / <name>` (a kit's own files, e.g. the live
  test's `mcp-token`, then never show in the repository's `git status`). Integration,
  UI and live sessions run with the test's `LADO_HOME`, so their processes see the row.
  `tests/test_kits.py`'s `project` fixture becomes a `kits_dir` of folders installed by
  the helper. Tests of project-kit behaviour (shadowing by a project kit, `kits --repo`,
  `where=`, the kit_users exception) are replaced by the spec's scenarios.
- **D10. Unrelated `.lado/` paths in tests stay meaningful.** `tests/test_fingerprint.py`
  and `tests/test_runtime.py`'s `git status` check use `.lado/kits/...` only as "a file
  under `.lado/`": they switch to `.lado/sdlc.md`, so no test suggests project kits exist.
- **D11. Docs.** AGENTS.md: `kits.py` lookup line, `launch.py`'s `/api/kits`, the
  remove-preview line in the server section, Design principles "Explicit lookup".
  docs/kits.md: the section "Project kits" and the `--repo` hint in Troubleshooting go.
  docs/design/ui.md: Launch's Kits line says the list is the installed and built-in kits
  (the server ignores the folder the window sends), and the Kits page's "not a project's
  kits (… Launch shows them for its folder)" clause goes. CHANGELOG.md under 0.36.0: project
  kits are no longer read, install a folder with `lado kits add <folder>`; `lado kits
  --repo` and `/api/kits?where=` are gone.
- **D12. Version.** Minor (CLI and API change); 0.36.0 is already the unreleased minor.

## Risks

- A user with a project kit loses it silently until the next start or resume, which then
  fails loudly with `kit not found`; accepted by the task. CHANGELOG says how to get it back.
- Integration and UI tests start sessions in other processes: the helper must write the
  row before the session starts, in the same `LADO_HOME`. Checked by the integration tests
  that run each kit.
