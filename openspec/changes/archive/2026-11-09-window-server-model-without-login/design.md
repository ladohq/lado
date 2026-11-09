## Context

`lado.server.launch.provider_infos` gives `ProviderInfo.login_missing` per CLI: the login its agents
need is missing in the environment of the project's agents, unless the CLI's default model is on a
server and the CLI takes that server's whole process (`Provider.external_whole_process`: Claude Code
and Codex; not OpenCode and Kilo, which need no login there). The window (`Launch.tsx`) holds a
suggested CLI with `login_missing`, shows it disabled (`LaunchTeam.tsx`) and keeps Start off with
`log in to <CLI>`. The model in the field is checked by `POST /api/session-model/check`
(`model_entries.check_session_model`), which checks the model and its server but not the login.
The start checks the login with its start model (`runtime.check_login`): a start model on a
whole-process server needs none.

## Decisions

D1. `ProviderInfo.login_missing` means "its agents need a login for the CLI's own models and it has
none", regardless of the default; the special case for a default on a server goes. A new
`ProviderInfo.starts_on_server: bool` is true when `login_missing` and the CLI takes a server's whole
process and has at least one saved model (`state.models()` of that CLI; a saved model is always on a
server). Read once per request beside `model_settings.defaults()`, as now, not in the threads. Why:
one flag that is true only sometimes cannot tell the window both "the CLI's own models need a login"
and "it can still start"; two plain facts can, and neither is a second source of the start's rule.

D2. `check_session_model` calls `runtime.check_login(provider, env, logins.SESSION, start)` after the
model's own check, for a start with no server only (a server start skips it inside `check_login`
anyway; no login status is read then). Its `NotLoggedIn` becomes a refusal: `text` `<CLI> is not
logged in, so it cannot run <model>: pick a model of your server, or log in first.`, `short` `<CLI>
is not logged in`, `peek` `needs login`, `retry` false, and a new `SessionModelCheck.login: bool`
true. Why: the window's check is "the check a start would make"; the login is part of it, from the
same function the start calls.

D3. The window (`Launch.tsx`): a CLI is offered when installed and (`!login_missing` or
`starts_on_server`). `held`, the red note `<CLI> is not logged in: its agents cannot start. Log in
first` and `log in to <CLI>` in the footer stay for `login_missing && !starts_on_server` only. With
`starts_on_server` the note under Agent is plain (`field-note`): `<CLI> is not logged in: its agents
run on your server's models only.` with a link button `Log in` (to `/settings/agent-clis#<cli>`) and
` for its own models.`; the option reads `<title> <version> · not logged in: your server's models
only`. `canStart` follows the same rule; the Model field's refusal keeps Start off where needed.

D4. `useLaunchModel` takes the CLI's `login_missing` and `starts_on_server`. With both true:
- the value `null` (the CLI's settings, chosen or as no default) is refused in the window itself,
  no server call: `<CLI> is not logged in, so it runs on your server's models only: pick one.` with
  `Log in first`; `blocked` true, peek `needs login`;
- a new session (not a resume, no draft choice for this CLI) whose opening value needs the login
  (no default, or a built-in default) and whose CLI has exactly one saved model takes that model as
  a pick (`{kind: "pick"}`) once, with the note `For this session only: <CLI> is not logged in, so
  it runs on your server's model.`; a change of the field by the human is never undone;
- a refusal with `login` true offers `Use <name>` (the CLI's default when it is on a server, else
  the first of its saved models in Your models' order) and `Log in first`, not `Use <CLI>'s
  settings` (which would be refused too); with Resume the kept-model words stay before them.

D5. `ModelPicker` gets `needsLogin` (launch only): the `<CLI>'s settings` row and each built-in row
get the mark `needs login` (`mx-gone`, as `no longer listed`); saved models, `Other name…` and the
read-again row get none. Picking a marked row is allowed and gets D2's refusal.

D6. No new integration test: the start without a login on a server model is already covered across
processes (`tests/integration/test_claude_model_server.py`, `test_codex_model_server.py`); this
change moves no process boundary. The window's behaviour gets vitest and one UI e2e test.

D7. Version: a fix of 0.45.0's unreleased feature, for 0.45.0rc2: patch, no CHANGELOG line (the
feature's line already says it).
