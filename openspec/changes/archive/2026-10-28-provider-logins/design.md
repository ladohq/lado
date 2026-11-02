## Context

What LADO knows of an agent CLI today is its version (`doctor.provider_status`, shown in
the System panel and New session) and, for Claude Code, its folder trust, read and
recorded before the launch (`ClaudeProvider.first_hook_blocker`, a `base.Blocker` with a
`reason` that makes the agent wait from its start, `state.block`, until its first hook).
An agent's environment is built by `agent_env.resolve` (login shell, outside folder,
project) under LADO's and the provider's own variables (`runtime._launch_env`) and reaches
its tmux window through the file `env.json`, which `agent_env.main` reads, removes, then
execs the CLI. The UI's terminal (`lado.terminal`, `server/terminals.py`, xterm.js in
`web/src/Terminals.tsx`) streams one agent's window through a viewer session.

The human's answers: question #1891 (all eight recommendations taken: one pull request;
LADO records Claude Code's first-run keys; a waiting agent starts by itself; the login
window is the CLI's own command in a terminal with phone helpers; LADO's secrets folder
for the login variables; Codex shown with its note, no button; Log out confirms naming
the running agents; `lado doctor` prints the login and no `lado login` command).

## Goals / Non-Goals

Goals: the login state of the four CLIs, read by their own commands, in the UI and
`lado doctor`; logging in and out from the UI, a phone too; Claude Code's token and API
key as values the UI writes and never reads back; a Claude agent without a login that
waits with the reason and starts by itself; no first-run screen in front of a logged-in
Claude agent.

Non-goals: see the proposal's Out of scope.

## Decisions

### D1. The provider interface answers four questions about logins

`providers/base.py` gains, with neutral types:

- `login_status(env) -> LoginStatus`: `state` (`yes`, `no`, `unknown`), `method` (words for
  the human: "Claude subscription (Max)", "token", "API key", "Anthropic Console",
  "2 credentials"), `file` (the CLI's own login file when it names one), `variable` (the
  variable that logs it in, when one does), `items` (OpenCode's and Kilo's credentials and
  environment keys: provider name and kind), `problem` (why `unknown`). It runs the CLI's
  own command with `env` and a time limit (`LOGIN_TIMEOUT`, 10 s); a failure, a timeout or
  output it cannot read is `unknown` with why, never `no`. Default: `unknown` "LADO cannot
  read this CLI's login".
- `login_actions`: the commands of the login window, each `(id, label, argv)`: Claude
  `login` (`claude auth login --claudeai`, "Log in with your Claude account…"),
  `login-console` (`--console`), OpenCode and Kilo `login` (`<cli> auth login`, "Add a
  login…") and `logout` (`<cli> auth logout`, "Log out of one…"); Codex none.
- `logout_argv`: a logout that asks nothing, run without a window: Claude `claude auth
  logout`; None for the others (theirs is in `login_actions`).
- `login_variables`: the variables that log the CLI in and that the UI may set as LADO's
  secrets: Claude `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`; the others none.
- `capabilities.needs_login`: an agent of this CLI cannot work without a login, so LADO
  holds it until there is one: Claude only. `login_note`: a line the page shows under the
  state (Codex: its agents do not get the login, GitHub #113).

Each provider parses its own CLI's output in `providers/`: Claude the JSON of `claude auth
status --json` (`authMethod`, `subscriptionType`, `apiKeySource`; its file is
`<config dir>/.credentials.json`, or the login keychain on macOS); Codex the first line of
`codex login status`, the part before ` - ` (never what follows, which may be a masked
key), with the user's own `CODEX_HOME`; OpenCode and Kilo (`opencode_family.py`, shared)
the lines of `auth list` with ANSI codes removed: `Credentials <path>`, `● <Provider>
<kind>`, and the `Environment` section's `● <Provider> <VARIABLE>`. Nothing above
`providers/` knows any of these outputs. Why the commands and not the files: the human
named them in the task, and they give the CLI's own view (Claude's environment variables
over its file).

### D2. The login state is read in the environment LADO's agents get, without a project

`lado.logins` (new core module) reads each installed provider's `login_status` with
`_launch_env`'s layers for a session without a project: `agent_env.resolve()` with LADO's
secrets (D4), then LADO's and the provider's own variables for a launch (a provider's
`launch.env` that holds login-relevant variables, e.g. Kilo's config, is not needed for
the status; only `providers.agent_env`-style fixed variables apply). The variable that
logs a CLI in is attributed to its layer by the core (login shell, outside folder, LADO's
secret), the same rule as `lado doctor`'s override line. Projects whose variables or
secrets set one of a provider's `login_variables` are listed by id (names only), so the
page is honest about sessions in them.

### D3. An agent of a CLI that needs a login waits in its window and starts by itself

In `runtime`, before the window of an agent whose provider has `needs_login` starts (a
session's start and resume, `spawn_worker`, a run's worker), LADO reads `login_status`
with the agent's launch environment. When the state is `no`:

- the agent waits from its start (`state.block`) with the reason built by the core from
  the provider: `<title> is not logged in: log in in Settings → Providers and environment,
  or set <first login variable>; the agent starts by itself once you do`; the line is told
  whoever starts it and logged in loop.log, as the trust note is;
- the window's command is `lado login-wait` (a hidden command of `lado.login_wait`, run
  through `providers.lado_command`, so the fake providers of the tests are known to it as
  to the hooks) instead of `lado.agent_env`: it reads and
  removes `env.json` as `agent_env.main` does, prints what it waits for, and every
  `LOGIN_POLL` (3 s) lays the file layers read anew (outside folder, LADO's secrets, the
  session's project) over the environment it holds, never over LADO's and the provider's
  own variables, and asks `login_status` again; at `yes` it runs the provider's
  `first_hook_blocker` (D6) with that environment and execs the CLI. What needs no login
  (Claude Code's trust) is recorded at the launch already and told whoever starts the
  agent; the window's lines go to its terminal and loop.log. A login shell's change
  needs a new agent (said in docs/design/agents.md).
- `unknown` never holds an agent: the launch goes on, with the problem as a warning (AC-10).

The core keeps the reason text in one function, `logins.wait_reason(provider)`, which the
server also uses to tell that an agent waits for a login (D9). The integration test drives
it with the fake provider (D12).

### D4. LADO's secrets: a folder in LADO_HOME, read by the outside folder's reader

`<LADO_HOME>/secrets/` holds one file per variable (folder 700, files 600), written
atomically and removed link-safely by the functions of `project_secrets` made general over
the folder (one writer, one remover, one reader `agent_env.read_folder(own=…)` with its
checks: no link, no loose mode, a name, size, UTF-8). `agent_env.resolve` lays it
after the outside folder and before the project; `for_git` does not (an agent CLI's login
means nothing to git). Only a name in
some provider's `login_variables` may be written (API refuses others, 400); a file of
another name put there by hand is still read and named by `lado doctor` (as the outside
folder's files are). `lado doctor`'s override line names a LADO secret that overrides the
outside folder (`[info] LADO secrets: CLAUDE_CODE_OAUTH_TOKEN overrides LADO_ENV_DIR`).
The canary test of project secrets is extended to a LADO secret.

### D5. The login window: a tmux session of its own on LADO's server

`lado.logins.open_window(provider, action)` starts a tmux session `lado-login-<provider>`
on LADO's private server, labelled with a user option `@lado-login` (and LADO_HOME, as the
viewers are), whose only window runs the action's argv through `agent_env.command` with the
environment of D2; one per provider: opening it again while it runs returns the running
one. `lado stop --all`, the UI server's start and its stop end the login windows by their
label, never by name; `lado ls` and the runtime ignore them (they are no LADO session).
`lado.terminal` gets a second target kind, a login window, attached directly in CONTROL
(no viewer: nobody else owns it). When its command ends the session ends; the socket
closes with a code "for good" and the UI reads the status again.

API (under `guard.changes` for changes, in OpenAPI): `GET /api/providers/logins` (the page's data,
D9), `POST /api/providers/{name}/login {action}` (opens the window, 400 for an action the
provider lacks), `DELETE /api/providers/{name}/login` (closes it),
`WS /api/providers/{name}/login/terminal` (the terminal protocol of `server/terminals.py`,
control only), `POST /api/providers/{name}/logout` (runs `logout_argv`, 400 when None),
`PUT`/`DELETE /api/providers/{name}/variables/{variable}` (`{value}`, never returned; a 422
answers without the input, as `SECRET_ROUTE`).

### D6. Claude Code's first-run keys through `edit_config`

`ClaudeProvider.first_hook_blocker` keeps recording the trust and, when the agent's
environment does not leave Claude Code without a login (its `login_status` is not `no`:
an unknown login holds no agent, which would stand on the theme screen):

- sets `hasCompletedOnboarding: true` when it is not `true`;
- when `ANTHROPIC_API_KEY` is set, adds its last 20 characters to
  `customApiKeyResponses.approved` when they are in neither `approved` nor `rejected`; a
  key in `rejected` is left as the human answered, and the agent waits with a reason that
  says so (Claude Code would ask again).

Each write is one `edit_config` call and one `Blocker.note` (`LADO recorded Claude Code's
first run in <file>`, `LADO recorded the approval of ANTHROPIC_API_KEY in <file>`), never
the key itself. A config LADO cannot understand stays as it is with the warning of
LAD-106. A missing config is created with the keys LADO records (the trust, then these).
AGENTS.md's exception names the three keys. The key's characters are the same ones Claude
Code itself stores in that file; they go nowhere else.

### D7. The page: one section of Settings, read on open and after each action

`web/src/Providers.tsx` (new) replaces the placeholder in `Settings.tsx`, with the anchor
`providers-and-environment` so a link scrolls to it. One row per provider, as the mockup
`mockup-providers.html`: the title and version (or how to install it), a dot and the
state, the source line, the waiting agents as links to their terminals, the projects with
their own login, the note, the actions (the window's actions, Log out, and the login
variables' secret fields with Save and Remove, the `SecretField` of the project page made
shared). Under the rows `lado doctor`'s provider checks (D10) and "Check again". The page
reads `GET /api/providers/logins` when it opens, after a window closes, after a Save,
Remove or Log out, and on "Check again"; not from the change feed (the CLIs' files change
outside LADO), the waiting agents with it.

### D8. The login window in the UI: a sheet with the terminal and phone helpers

A dialog (a full-screen sheet on a phone, as the agent's terminal is) with the title
`Log in: <CLI>`, Close (ends the window), the xterm terminal of `Terminals.tsx` made
reusable over a socket URL, `@xterm/addon-web-links` (new dependency, xterm's own) so a
link, also one wrapped over lines, opens in a new tab, and under it the "Text to send" field
with "Send ⏎" (sends the text then `\r` as one input frame) and the keys ↑ ↓ Enter Esc. The
field is a plain text field (a code is no secret worth a font), cleared after send.

### D9. What the server gives the page and the agents' rows

`GET /api/providers/logins` → `ProvidersPage`: `providers`, a `ProviderLogins` each, with
the System panel's `ProviderInfo` as `cli`, and `checks` (D10). `GET /api/providers` stays
the System panel's and New session's list, which runs no CLI's status command (the build
moved the page to its own path for that). A row has `login` (D1's status), `actions` (id, label), `can_logout`, `variables` (each login
variable: `set` in LADO's secrets or not, and the layer that gives it now), `note`,
`waiting` (session, agent: the live agents whose block reason is `logins.wait_reason` of
this provider), `projects` (ids), `running` (session, agent: live agents of this provider,
for Log out's confirmation). `AgentInfo` gains `login_wait` (the provider's name when the
agent waits for its login, else null), so Needs you shows "Log in…" without parsing text.
`make web-types`.

### D10. `lado doctor`: a login line per installed CLI; the page shows the provider checks

`check_logins` adds `[ok] <title> login: <method>` / `[warn] Claude Code login: not
logged in: its agents wait for a login (Settings → Providers and environment)` /
`[info] <title> login: none` for a CLI that does not need one / `[warn] … unknown: <why>`;
the exit code stays as it was (a warning). `GET /api/providers/logins` carries the checks the page
shows: the providers' version checks, the graphical session (Mac), the agents' environment
and the login lines, from the same functions as `lado doctor` (no second list).

### D11. Log out and Remove ask first

Log out of Claude Code and Remove of a login variable open a confirmation that names the
running agents of that provider ("supervisor of my-app, developer of my-app will stop
being able to answer"); OpenCode's and Kilo's logout ask inside their own command.

### D12. Tests at the lowest layer that catches each bug

Unit: each provider's parser on recorded outputs (Claude's JSON for each `authMethod`,
Codex's lines, OpenCode's and Kilo's text with ANSI), `unknown` on a failure, a timeout and
odd output; the layer order with LADO's secrets; `edit_config`'s new keys; the wait reason;
`check_logins`. API (`tests/test_server_providers.py`): the list, open/close a window with
a fake provider's argv, logout, set/remove a variable (refusals: a name not in
`login_variables`, a value in no answer, 422 without input). Integration (fake agent,
`tests/integration/test_provider_logins.py`): the fake provider gets `needs_login` and a
`login_status` that reads a marker file; a session's supervisor without the marker waits
with the reason (`lado ls` prints it, `AgentInfo.login_wait` set), then the marker appears
and the agent reaches its first hook by itself; a value put in LADO's secrets reaches a
waiting agent; a status that times out does not hold the agent; a login window's command
runs with the agents' environment and ends by itself. Canary: a LADO secret's value
nowhere (extending `test_project_secrets_canary.py`'s list). UI e2e (`tests/ui/`): the
section with the fake provider's states, the window with a fake login command that prints
a link and reads a line ("Text to send" logs in, the window closes, the state changes),
Needs you's "Log in…" leading to the section, at a phone's width. Smoke (real CLIs, CI):
each CLI's status parses in a fresh home (no login; Claude with a made-up token; OpenCode
and Kilo with a written `auth.json` and a key variable), and a Claude agent in a fresh
config with a token passes the first run with no human (D6).

### D13. The docs

docs/design/ui.md (Providers and environment: the section, the window, the API; Needs
you's "Log in…"), docs/design/agents.md (the login wait before the first hook, LADO's
secrets layer, the first-run keys), docs/design/modules.md (`logins.py`, `login_wait`,
the providers' methods), docs/cli.md (`lado doctor`'s login lines, `lado ls`'s reason),
docs/install.md (Docker: log in from the UI first; the shell ways stay), the compose and
Dockerfile headers (the UI's way named), AGENTS.md (the exception's keys; `logins.py` on
the map), CHANGELOG.md (`## 0.44.0 (unreleased)`, Added, one item).

### D14. Version

A feature with new API endpoints: the minor, 0.44.0, already the unreleased version. No
schema change: LADO's secrets are files, the wait reason is a BLOCKED event as before.

## Risks / Trade-offs

- Claude Code's status JSON and first-run keys are not a public contract: pinned by the
  smoke test with the real CLI at the tested version, as the trust is.
- OpenCode's and Kilo's `auth list` is text: its parser is pinned by recorded outputs and
  the smoke test; an output it cannot read is `unknown`, never a wrong "no".
- `claude auth status` on macOS reads the keychain; from a server outside the graphical
  session it may say "not logged in" while the human's terminal is logged in. The agent
  would fail the same way there; the existing keychain warning names the cause.
- A token is not checked: a wrong token shows "Logged in · token" and the agents fail at
  their first turn with Claude Code's own error.
