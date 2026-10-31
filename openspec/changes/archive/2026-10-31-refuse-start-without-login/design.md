## Context

LAD-157 (change `provider-logins`) made each provider answer whether its CLI is logged in
(`Provider.login_status(env)`, `yes`/`no`/`unknown`) and whether its agents need a login
(`Capabilities.needs_login`, only Claude Code). `runtime._held_for_login`, called from
`_before_window` at every launch (`start_session`, new or resumed, and `spawn_worker`),
reads the status in the agent's launch environment and, for `no`, blocks the agent with
`logins.wait_reason` and starts its window as `lado.login_wait` instead of the CLI. By then
the session is stored (`state.add_session` / `state.resume_session`) or the worker's
worktree, branch and record are made.

The environment an agent starts from is `runtime._base_env(project)`: login shell, outside
folder, LADO's secrets and the project's layer (`agent_env.resolve`), under LADO's and the
provider's own variables (`_launch_env`). Claude Code's `Launch.env` is empty and LADO's
own variables (`providers.agent_env`) hold no login, so `_base_env(project)` gives the same
login status as the launch environment.

The New session window (`web/src/Launch.tsx`) lists providers from `GET /api/providers`
(`server.launch.provider_infos`: installed, version) and takes the folder's suggestion
(`ProviderSuggestion`, the folder's last session's or the only one installed).

The human's answers: questions #1961 and #1969 (all recommendations taken: the window's
look of `mockup-start-without-login.html`; the project's secrets count; a resume is never
refused and warned in the Resume window; the refusal texts; an unreadable login refuses
nothing; sessions mix CLIs and each agent is checked by its own provider).

## Goals / Non-Goals

Goals: no new session or worker of a CLI that needs a login and has none; the refusal said
where it is asked (CLI, UI, MCP) with where to log in; the window shows it before Start.

Non-goals: see the proposal's Out of scope.

## Decisions

### D1. One check in `lado.logins`, the refusal raised by `lado.runtime`

`logins.refusal(provider, env, what) -> str | None`: None unless
`provider.capabilities.needs_login` and `provider.login_status(env).state == NO`; else the
text for `what` (`SESSION` or `WORKER`):

- session: `<title> is not logged in, so the session was not started: log in in LADO's UI
  (Settings → Providers and environment, `lado ui`), or set <first login variable> as
  LADO's secret or a project secret`
- worker: `<title> is not logged in, so the worker was not started: ask the human to log
  in in Settings → Providers and environment, or start the worker with another provider`

The texts live in `lado.logins` next to `wait_reason`, so one module owns the words of the
login. `runtime.check_login(agent_cli, project, what)` builds `_base_env(project)` and
raises `NotLoggedIn(LadoError)`; every caller that already turns a `LadoError` into its
answer (CLI exit 1, HTTP 400, MCP error) needs nothing new. Why not a new provider method:
the rule is the core's, the provider only answers `login_status`.

### D2. Where the check runs

- `start_session`: when `old` is None (a new session), right after `_check_commands`,
  with the `base_env` it already built, before `state.add_session`. A resume (`old` set)
  is never checked: the decision keeps the wait for it, and a resume at LADO's start
  (`resume_at_start`) must not fail for a login lost meanwhile. The approved
  `start_session` MCP tool goes through `start_session(resume=False)` and gets it for free.
- `spawn_worker`: right after `_check_commands`, with its `base_env`, by the worker's own
  provider (`provider or sess.provider`), before `exclude_worktrees` and `git worktree
  add`. `runs.spawn_worker` calls `runtime.spawn_worker` after `_restore_worktree`, which
  only restores the run's existing worktree, so nothing new is left.
- `lado start <git-url>` and `lado start --new` (`cli._start_clone`, `_start_new`), and the
  server's `POST /api/sessions` with `where.kind == "scratch"`: before the clone or
  `scratch.make`, when the provider is known: given, or the only one installed on the
  agents' PATH (`runtime.suggested_provider(None, …)`, the rule a folder with no sessions
  gets). Otherwise `start_session` decides after the folder exists, as now.

### D3. The launch-time wait stays as it is

`_held_for_login` and `lado.login_wait` are unchanged: they serve a resume and the short
race between the check and the launch (a logout in between). The status is then read twice
for a new Claude agent (about 0.1 s each, `claude auth status --json`); accepted over
threading a result through `_before_window`, which would couple the check to the launch.

### D4. Unknown never refuses

`refusal` refuses only `NO`. `UNKNOWN` goes on, and `_held_for_login` warns as now ("cannot
tell whether … is logged in: …; the agent starts all the same"). A broken status command
must not lock the human out.

### D5. `ProviderInfo.login_missing` and `GET /api/providers?project=`

`server.launch.provider_infos(project=None)` reads, for each installed provider with
`needs_login`, `login_status` in `runtime._base_env(project)` (in the existing thread pool),
and sets `login_missing = state == NO`; other providers and an unreadable status are false.
`project` unknown: 404 (`projects.NoSuchProject`). An environment that cannot be built
(`AgentEnvError`, the login shell fails) gives `login_missing` false for all: the start
then refuses with that error itself. `make web-types` regenerates `web/openapi.json` and
`web/src/api.gen.ts`.

### D6. The window decides from `login_missing`

`Launch.tsx` asks `getProviders(project)` with the Project way's chosen project (again on
each change of it), and without one for the folder, clone and scratch ways. An option with
`login_missing` is disabled and labelled `<name> · not logged in`; the folder's suggestion
of such a provider is not applied (Provider stays "choose…") but its note is shown;
`ProviderNote` shows the red note with the link "Log in first" (closes the window,
`navigate(PROVIDERS_PATH)`); `ready`, `cloneReady`, `scratchReady` and `projectReady` need
`!login_missing`. In the Resume window (`resuming`) the same state gives the amber
`field-note warn` with "Log in…" and does not block. The server's suggestion
(`ProviderSuggestion`) does not change: `lado start` without `--provider` in a folder whose
last session was Claude refuses with the reason, and `--provider` picks another.

### D7. `lado doctor`'s line

`[warn] Claude Code login: not logged in: new sessions and workers of it are refused, a
resumed agent waits (Settings → Providers and environment)`. Only the words change; the
spec's scenario elides them.

### D8. LAD-160

If LAD-160 ("the method chosen on the page wins") merges first, it changes what an agent's
environment holds; this check reads `_base_env(project)`, the environment the agent gets,
so it follows without a second rule. A merge conflict in `lado/logins.py` is resolved by
keeping both: LAD-160's page logic and this change's `refusal`.

## Risks / Trade-offs

- [The providers list runs `claude auth status` each time the window opens] → about
  0.1 s, in the pool that already runs `--version`; time limit `LOGIN_TIMEOUT` as on the
  Settings page.
- [A project's layer read without the session] → the same `_base_env` the launch uses, so
  the window and the start agree.
- [The integration test of LAD-157 that starts a session without a login] → it now resumes
  a stopped session, the path the wait still serves.

## Test layers

- `logins.refusal` texts and `NO`/`UNKNOWN`/no-`needs_login`: unit, `tests/test_logins.py`.
- `start_session` / `spawn_worker` refusal leaves nothing; resume not refused; project
  layer; mixed providers; unknown: unit with fake tmux, `tests/test_runtime.py`,
  `tests/test_runtime_projects.py`, `tests/test_runtime_start_approved.py`.
- CLI clone/new pre-check: unit, `tests/test_cli.py`.
- `POST /api/sessions` 400, scratch not made, `GET /api/providers` `login_missing` and
  `?project=`: API, `tests/test_server_launch.py`.
- The window: vitest `web/src/Launch.test.tsx`; UI e2e `tests/ui/test_launch.py` (the
  greyed option, the note's link, the Resume note) with the fake provider `fake-login`.
- Crossing processes (`lado start` → lado.db, tmux; `lado mcp` → `spawn_worker`):
  integration with the fake agent, `tests/integration/test_provider_logins.py`.
