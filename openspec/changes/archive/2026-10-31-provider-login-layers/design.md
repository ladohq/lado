## Context

LAD-157 (change `provider-logins`, archived 2026-10-28) gave Settings → Providers and
environment: each provider answers `login_status(env)`, `login_actions()`,
`logout_argv()`, `login_variables` and `capabilities.needs_login` (`providers/base.py`);
`lado.logins` reads them in `environment()` (`agent_env.resolve()` without a project),
names a variable's layer (`layer`), finds the waiting and running agents and the projects
with their own login, and runs the login windows. The server (`server/app.py` routes
`/api/providers/…`, `server/launch.py` `provider_logins`, models `ProviderLogins`,
`LoginInfo`, `LoginVariableInfo`) feeds `web/src/Providers.tsx` and
`web/src/LoginWindow.tsx`. An agent's environment is `runtime._base_env(project)`
(`agent_env.resolve(project_secrets.layer(project))`: login shell, outside folder, LADO's
secrets, project, each over the one before, name by name) under LADO's and the provider's
own variables (`runtime._launch_env`); a Claude agent without a login waits in
`lado.login_wait`, whose `layers` lays the file layers anew every `POLL`.

Claude Code's own order (checked in LAD-157): `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`,
`CLAUDE_CODE_OAUTH_TOKEN`, then its login file (`<config>/.credentials.json`, or the
macOS keychain), which holds a short-lived access token and a refresh token.

The human's answers: the decision of session lad-157 (`decision-provider-login-ux`) and
this run's questions #1963 (rejected the remembered choice, #1965), #1966 (rejected
generating a token, #1971), #1972 and #1976.

## Goals / Non-Goals

Goals: one state line with its layer and one button per CLI; Claude Code logs in only by a
ready token or key kept as LADO's secret; the layer that gives a login gives all of it.

Non-goals: see the proposal's Out of scope.

## Decisions

### D1. A login comes whole from one layer, in `agent_env`

`agent_env.resolve` is split, so the login shell runs once per launch as now:

- `agent_env.layers(project=None) -> Layers`: the login shell's (or the starting
  process's), the outside folder's, LADO's secrets', the project's, each a dict, in order;
- `agent_env.merge(layers, login=()) -> dict`: each over the one before, but for the names
  in `login`: the highest layer that sets any of them gives those it sets, and the names
  of `login` are taken from no lower layer;
- `resolve(project=None, login=())` stays as `merge(layers(project), login)`; `for_git`
  does not use the rule (it is no agent's login).

`login` is a list of names, so `agent_env` knows no provider (neutral core). With
`login=()` the result is today's, name by name: no caller changes unless it passes a
provider's `login_variables`.

Callers that pass `agent_cli.login_variables`:

- `runtime`: `_base_env` returns the session's `Layers`; for each agent (supervisor,
  worker, run worker) `merge(layers, agent_cli.login_variables)` before `_held_for_login`
  and `_launch_env`; a worker of another provider gets its own provider's rule. The early
  resolve for the PATH of the new session's provider uses `merge(layers)`.
- `login_wait`: its private file keeps, next to `env`, the login shell layer's values of
  the provider's login variables (`shell_login`; the file already holds every value and
  is removed when read); `layers` takes those out of `env`, reads the outside folder,
  LADO's secrets and the project anew, and merges them with the same rule.
- `logins.environment(provider=None)`: with a provider, `merge(layers(),
  provider.login_variables)`; the page's state, the login windows, `lado doctor` use it.

Options weighed: a remembered choice that leaves the competing variables out (#1963,
rejected: one more rule and more words); name by name as now (rejected: a login shell's
`ANTHROPIC_API_KEY` beats a token saved on the page, by Claude Code's order, so the page
would show a login the human did not set).

### D2. Where the login comes from: one function, the same layers

`logins.layer` names the layer that gives the login, by the same `Layers`: "LADO's
secret", "outside folder", "login shell" (or "the process that starts LADO"); a project is
never the page's (the page has no project; its projects are listed). With a login and no
variable (`LoginStatus.file`), "Claude Code's login file" comes from the provider:
`LoginStatus.file_words` ("Claude Code's login file", "the login keychain"). The words
are `Login.where`, the state line's and `lado doctor`'s (which shows the file's path when
the provider gives no words, as OpenCode's); `source()` goes with its only uses.

### D3. Claude Code's words say how the human pays

`ClaudeProvider.login_status`'s `method`: "Subscription (<Plan>)" (`subscriptionType`
capitalised; "Subscription" when absent), "Subscription (token)", "Pay per use (API
key)", "Pay per use (Console)". `lado doctor`: `[ok] Claude Code login: <method> ·
<where from>`. The recorded outputs of `tests/test_login_status.py` keep their inputs.

### D4. The provider names its question and choices

`providers/base.py` gains `LoginChoice(id, title, detail, variable)` and the attributes
`login_question: str = ""`, `login_choices: tuple[LoginChoice, ...] = ()`; `LoginStatus`
gains `choice: str` ("" for none). Claude:

- question "How do you pay for Claude?";
- `subscription`: "Subscription — Claude Pro or Max", "Run `claude setup-token` on any
  computer where Claude Code is installed and paste the token it prints.",
  `CLAUDE_CODE_OAUTH_TOKEN`;
- `usage`: "Pay per use — API billing", "Paste an API key from console.anthropic.com.",
  `ANTHROPIC_API_KEY`;
- `choice` from `authMethod`: `claude.ai`, `oauth_token` of `CLAUDE_CODE_OAUTH_TOKEN` →
  `subscription`; `api_key`, Console → `usage`. A gateway's `ANTHROPIC_AUTH_TOKEN` (also
  `oauth_token`) is no way to pay the sheet offers: "Token", no choice.

Each choice's variable must be one of `login_variables` (a unit test). OpenCode and Kilo
name none; Codex has no login action and no choice, so no button.

### D5. What goes: Claude's login commands, the file's logout

`ClaudeProvider.login_actions()` returns none; `logout_argv` and `base.Provider.logout_argv`
go, with `logins.logout`, the route `POST /api/providers/{name}/logout`, `logOut` in
`web/src/api.ts` and `ProviderLogins.can_logout`: no provider uses them any more (only
what is used). `claude auth logout` in a terminal is named in docs/install.md. OpenCode's
and Kilo's `login`/`logout` actions stay.

### D6. Save replaces LADO's login; Log out removes it

- `PUT /api/providers/{name}/variables/{variable}` writes the secret, then removes the
  provider's other login variables from LADO's secrets: one login per layer, so the
  sheet's choice is the login (otherwise a saved key would beat the token just saved).
- `DELETE /api/providers/{name}/login-secrets` (new, replaces the logout route) removes
  every login variable of the provider from LADO's secrets; the sheet's "Log out…" calls
  it after its confirmation. `DELETE …/variables/{variable}` goes with the row's Remove…:
  nothing uses it (the human's comment at the approval: remove the code of the agents'
  login that is left over).
- Both answer the row read anew, never a value; a 422 repeats no input (`SECRET_ROUTE`).

### D7. The API

`ProviderLogins` gains `question: str`, `choices: list[LoginChoiceInfo]` (`id`, `title`,
`detail`, `variable`), `from_lado: bool` (the login comes from LADO's secrets, so Log out
is offered); `LoginInfo` gains `choice: str` and `where: str` (D2's words); `can_logout`
goes, and so does what the row no longer shows (the human's comment at the approval):
`variables` (`LoginVariableInfo`, `logins.Variable`), and `LoginInfo`'s `file`,
`variable`, `layer`, `source` and `items` (`LoginItemInfo`). `make web-types` renews
`web/openapi.json` and `web/src/api.gen.ts`.

### D8. The UI: a row and one sheet

`Providers.tsx`: the row has head, the state line (`Logged in · <method> · <where>`; "Not
logged in" bold with the waiting dot; "No login"; "Unknown: …"), the waiting agents, the
projects with their own login, the note, and one button ("Log in…", primary when
`needs_login` and not logged in; "Change login…"); none when the provider has neither
choices nor actions. The secret fields, the action buttons and "Log out…" of the row go.

A new `LoginSheet.tsx` in the `login-sheet`/`login-window` frame: for a provider with
`choices`, the question, a radio per choice (the current one marked "current"), the
chosen one's `detail` and `SecretField` with Save (`putLoginVariable`), and "Log out…"
when `from_lado`, with today's `Confirm` naming the running agents. For a provider
without `choices`, it shows `LoginWindow` running its `login` action, with "Log out of
one…" in the header when logged in (reopens on `logout`). Full screen at ≤600 px. Built to
`mockup-login-ladder.html`.

### D9. LAD-161, version, tests

- LAD-161 (refuse a start without a login) may change `logins.py` and the session form in
  parallel. This change keeps `wait_reason`, `waits_for`, `read`, `agents` and extends
  `environment` with a keyword; LAD-161's check should use `environment(provider)` so it
  sees the login as the agents get it. Named in the pull request.
- A feature of the unreleased 0.44.0 (already a minor): the CHANGELOG's Added line
  "Agent CLI logins in Settings" is rewritten for the sheet and the paste; no schema
  migration.
- Tests by layer:
  - unit: `tests/test_agent_env.py` (`merge`: today's order without `login`; the highest
    layer wins whole; a project wins whole; names outside `login` untouched),
    `tests/test_login_status.py` (words, `choice`), `tests/test_providers.py` (choices'
    variables are login variables; Claude has no actions), `tests/test_logins.py`
    (`environment(provider)`, `layer` by the rule), `tests/test_login_wait.py`
    (`layers` with `shell_login`), `tests/test_runtime.py` (a worker of another provider
    keeps the variable), `tests/test_doctor.py` (the line);
  - API: `tests/test_server_providers.py` (fields; PUT removes the other; the new DELETE;
    the logout route gone; no value in any answer);
  - integration (`tests/integration/test_provider_logins.py`, `fake-login` with a second
    login variable `FAKE_AGENT_KEY`): the outside folder's `FAKE_AGENT_KEY` and LADO's
    `FAKE_AGENT_TOKEN` → the agent has the token only; a project's `FAKE_AGENT_KEY` → its
    session's agent has the key only; a token saved while an agent waits reaches it and
    the shell's key does not;
  - vitest: `web/src/Providers.test.tsx`, new `web/src/LoginSheet.test.tsx`;
  - UI e2e: `tests/ui/test_providers_section.py` at 1280 and 390 px, screenshots;
  - regression: `make lint`, `make test`, the two marked files, `make web`,
    `openspec validate --specs --strict`.

## Risks / Trade-offs

- No Claude login from a phone alone: the human needs a computer with Claude Code once a
  year to run `claude setup-token`, or an API key (#1972, 1).
- A human whose login shell exports `ANTHROPIC_API_KEY` and who also has an account
  login file: the key wins, as before; the row says "Pay per use (API key) · login shell".
- A setup-token token lives a year; LADO cannot see when it expires; the agent fails at
  its first turn with Claude Code's error.
