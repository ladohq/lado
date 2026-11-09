Task: LAD-255

## Why

Found in the manual check of 0.45.0rc1 (finding 2): CHANGELOG 0.45.0 promises that Claude Code and
Codex agents run on the human's own model server with no login of their CLI. `lado start --provider
claude --model CloudClaude` does start without a login, but the New session window shows such a CLI
as `Claude Code · not logged in`, disabled, with `To start: log in to Claude Code`. In LADO's
container, where the UI is the main way to start, these agents cannot be started from the UI at all.

Cause: the window decides by `ProviderInfo.login_missing` alone (`web/src/LaunchTeam.tsx:180`).
`lado.server.launch.provider_infos` clears that flag only when the CLI's *default* model is on a
server that takes the CLI's whole process (LAD-238); a saved server model that is not the default
does not count, and the model picked in the window is not known there. The start itself
(`runtime.check_login`) already lets a start model on such a server through.

Options weighed:

- A (taken): the providers list says two things apart, whether the CLI's own login is missing
  (`login_missing`, now regardless of the default) and whether its agents can start without it on a
  saved model of a server (`starts_on_server`); the window's check of the model in the field makes
  the same login check a start makes (`runtime.check_login`), so a built-in model is refused in the
  field with the start's reason. Long-term cost: one new field, one check shared with the start;
  window and start cannot drift.
- B: only take `disabled` off in the window. A built-in model is then refused after Start, as a
  general error, and nothing tells the human beforehand. Cheap now, a second rule later.
- C: clear `login_missing` whenever any saved server model exists. The flag then lies for the
  built-in models, and the window offers starts the server refuses.

## What Changes

- `GET /api/providers`: `login_missing` is true when the CLI's agents need a login and it has none,
  whatever its default model; a new `starts_on_server` is true when its agents can still start
  without that login on a saved model of a server (the CLI takes a server's whole process and has at
  least one saved model).
- The New session and Resume windows offer such a CLI as `<title> <version> · not logged in: your
  server's models only`, take it when the place suggests it, and say under Agent `<CLI> is not
  logged in: its agents run on your server's models only. Log in for its own models.`
- The Model field: with exactly one saved server model and a value that needs the login (no
  default, or a built-in default), a new session's field takes that model by itself; with several
  it stays and is refused (`<CLI> is not logged in, so it runs on your server's models only: pick
  one.`). In its list the CLI's settings and its built-in models are marked `needs login`.
- `POST /api/session-model/check` checks the login as the start does: a built-in model of a CLI
  without its login is refused with `<CLI> is not logged in, so it cannot run <model>: pick a model
  of your server, or log in first.` and the ways out `Use <server model>` and `Log in first`.
- A resume of a session on a server's model is offered the same way (the core already resumes it).

## Scope

- `src/lado/server/launch.py` (`provider_infos`), `src/lado/server/models.py` (`ProviderInfo`,
  `SessionModelCheck`), `src/lado/server/model_entries.py` (`check_session_model`).
- `web/src/Launch.tsx`, `web/src/LaunchTeam.tsx`, `web/src/LaunchModel.tsx`,
  `web/src/ModelPicker.tsx`; `web/openapi.json`, `web/src/api.gen.ts`.
- Tests: unit (`tests/test_server_launch.py`), vitest, UI e2e (`tests/ui/test_launch.py`).
- `docs/design/ui.md` (Launch and session control).

## Out of scope

- Settings → Agent CLIs' rows and `lado doctor`: they already say "not logged in" truthfully; the
  task is the window only.
- The core's start, resume and worker checks (`runtime.check_login`): already right, unchanged.
- OpenCode and Kilo CLI: they never need a login for a server's model (`login_missing` stays false).
- A CHANGELOG line: 0.45.0 is unreleased and its line `Run agents on your own model server` already
  promises this; the fix makes it true, it adds nothing users have not been told.
- Choosing which of several server models to take by itself: the human picks; a guess among several
  may run on the wrong server.

## Impact

- API: a new field of `ProviderInfo`, a new field of `SessionModelCheck`; `login_missing` changes its
  meaning for a CLI whose default is on a server (true now, with `starts_on_server` true). No CLI or
  MCP change, no schema change. A fix for the RC: patch, inside 0.45.0.
