# provider-logins Specification

## Purpose
The agent CLIs' logins: LADO reads whether each CLI is logged in by the CLI's own status
command, shows it in Settings → Providers and environment and `lado doctor`, logs Claude
Code, OpenCode and Kilo in from the UI (a phone too), keeps their login variables as LADO's
secrets, and holds an agent whose CLI needs a login until there is one.

## Requirements

### Requirement: LADO reads each CLI's login with the CLI's own command

LADO SHALL read whether an agent CLI is logged in, and how, only by the CLI's own status
command, run within a time limit in the environment LADO's agents of that CLI get without
a project, except a login variable the CLI does not report itself (Codex's
`OPENAI_API_KEY`), and SHALL NOT read any agent's screen. A command that fails, times out
or prints what LADO cannot read SHALL give the state `unknown` with why, never "not logged
in".

#### Scenario: The status commands
- **WHEN** LADO reads the logins of Claude Code, Codex, OpenCode and Kilo
- **THEN** it runs `claude auth status --json`, `codex login status -c
  cli_auth_credentials_store="file"`, `opencode auth list` and `kilo auth list`

#### Scenario: Claude Code with a subscription
- **WHEN** `claude auth status --json` prints `loggedIn: true`, `authMethod: "claude.ai"`
  and `subscriptionType: "max"`
- **THEN** the state is logged in, the method "Subscription (Max)", and the source
  Claude Code's login file in its config folder

#### Scenario: Claude Code with a token from LADO's secrets
- **WHEN** LADO's secrets hold `CLAUDE_CODE_OAUTH_TOKEN` and the status prints
  `authMethod: "oauth_token"`
- **THEN** the state is logged in, the method "Subscription (token)", and the source the
  variable `CLAUDE_CODE_OAUTH_TOKEN` from LADO's secrets

#### Scenario: Claude Code not logged in
- **WHEN** the status prints `loggedIn: false` and exits 1
- **THEN** the state is not logged in

#### Scenario: OpenCode with credentials and a key variable
- **WHEN** `opencode auth list` lists the credentials `Anthropic api` and `OpenRouter
  oauth` and, under Environment, `OpenAI OPENAI_API_KEY`
- **THEN** the state is logged in with those three, each with its kind, and the source
  names the credentials file and the variable

#### Scenario: Codex with a ChatGPT login
- **WHEN** `codex login status`, run with `-c cli_auth_credentials_store="file"`, prints
  `Logged in using ChatGPT`
- **THEN** the state is logged in, the method "ChatGPT plan", and the source Codex's login
  file

#### Scenario: Codex with an API key variable
- **WHEN** the agents' environment has `OPENAI_API_KEY` from LADO's secrets and no
  `CODEX_ACCESS_TOKEN`
- **THEN** the state is logged in, the method "Pay per use (API key)", and the source the
  variable `OPENAI_API_KEY` from LADO's secrets, whatever Codex's own file holds

#### Scenario: Codex with an access token
- **WHEN** the agents' environment has `CODEX_ACCESS_TOKEN` from the outside folder and
  `codex login status` prints that it is logged in with it
- **THEN** the state is logged in, the method "ChatGPT access token", and the source the
  variable `CODEX_ACCESS_TOKEN` from the outside folder

#### Scenario: The command times out
- **WHEN** a CLI's status command does not end within the limit
- **THEN** it is killed, and the state is unknown with "timed out"

### Requirement: Settings shows the login of each agent CLI

Settings' section Providers and environment SHALL show, for each agent CLI LADO knows, its
name, its version, a dot and one state line, then, while its login is missing, the live
agents that wait for it, the projects that set a login variable of it and the provider's
note. Of `lado doctor`'s provider checks it SHALL show only what the user can fix (the
scenarios below), with no check's level and no other check.

#### Scenario: The section's words
- **WHEN** the human opens Settings → Providers and environment
- **THEN** under its title is "Sign-ins your agents use. Changes apply to agents started
  afterwards.", and each state line is "Logged in · <method> · <where from>", "Not logged
  in", "No login" or "Couldn't check the sign-in" with why

#### Scenario: A new user in Docker
- **WHEN** Claude Code is installed and not logged in, and a session's supervisor waits for
  its login
- **THEN** Claude Code's row shows "Not logged in", names that supervisor with a link, and
  has the primary button "Log in…" and no other button or field

#### Scenario: A token in the outside folder
- **WHEN** the outside folder has `CLAUDE_CODE_OAUTH_TOKEN` and no other layer sets a
  login variable of Claude Code
- **THEN** the row shows "Logged in · Subscription (token) · outside folder" and the one
  button "Change login…"

#### Scenario: The account login in Claude Code's file
- **WHEN** Claude Code is logged in with its account in its own file and no layer sets a
  login variable
- **THEN** the row shows "Logged in · Subscription (Max) · Claude Code's login file"

#### Scenario: A project with its own token
- **WHEN** project `shop` has the secret `CLAUDE_CODE_OAUTH_TOKEN`
- **THEN** Claude Code's row names `shop` among the projects with a login of their own,
  without the value

#### Scenario: Everything is fine
- **WHEN** every CLI is installed at its tested version and the agents' environment
  resolves
- **THEN** the section shows the rows only: no "lado doctor about the providers", no
  `[ok]`, `[info]` or `[warn]`, no line about the environment and no "Check again"

#### Scenario: A CLI not installed
- **WHEN** Codex CLI is not installed
- **THEN** its row shows its name greyed, "not installed" and its install hint, and no
  state line or button

#### Scenario: No CLI installed
- **WHEN** none of the agent CLIs is installed
- **THEN** one line over the list says that no agent CLI is installed and a session needs
  one

#### Scenario: An untested version
- **WHEN** Kilo CLI 7.9.1 is installed and LADO is tested with 7.8.x
- **THEN** Kilo's row shows "7.9.1" and, small next to it, "LADO is tested with 7.8.x"

#### Scenario: A sign-in that cannot be checked
- **WHEN** Claude Code's status command times out
- **THEN** its row shows "Couldn't check the sign-in" and, under it, why

#### Scenario: The agents' environment cannot be resolved
- **WHEN** the login shell does not answer in time
- **THEN** a line under the rows says that the agents' environment could not be read from
  the login shell, why, and that `lado doctor` shows more

#### Scenario: Saved while an agent waits
- **WHEN** an agent waits for Claude Code's login and the human saves a token in the sheet
- **THEN** the row shows "Logged in · …" and no line that an agent waits for this login,
  at no moment

### Requirement: The login window runs the CLI's own login command

For a CLI that logs in by its own command (OpenCode, Kilo: the row's button; Codex: its
sheet's choice "ChatGPT plan"), the page SHALL open a terminal that runs it, in the
environment of the agents without a project, at most one per CLI, with "Log out of one…"
while logged in where the CLI asks which; when the command ends the window SHALL close and
the page SHALL read the state again, and Close SHALL end the command. LADO SHALL run no
login command of Claude Code.

#### Scenario: The login commands
- **WHEN** the login window opens for OpenCode, Kilo or Codex's "ChatGPT plan"
- **THEN** it runs `opencode auth login`, `kilo auth login` or `codex login --device-auth
  -c cli_auth_credentials_store="file"`, and "Log out of one…" runs `opencode auth logout`
  or `kilo auth logout`

#### Scenario: OpenCode's login from a phone
- **WHEN** the human chooses OpenCode's "Log in…" on a phone, picks a model provider with
  ↓ and Enter and sends its key with "Text to send"
- **THEN** the command ends, the window closes, and the row shows "Logged in"

#### Scenario: Claude Code's login from a phone
- **WHEN** the human chooses Claude Code's "Log in…" on a phone
- **THEN** the sheet asks "How do you pay for Claude?" with a field for a token or a key,
  and no login command of Claude Code runs

#### Scenario: Opened twice
- **WHEN** OpenCode's login window is open and its button is chosen again
- **THEN** the same window is shown and no second command starts

#### Scenario: The windows end with LADO
- **WHEN** a login window runs and the UI server stops, or `lado stop --all` runs
- **THEN** its tmux session is gone, found by its label, and `lado ls` never listed it

#### Scenario: Codex has no button
- **WHEN** Codex is installed
- **THEN** its row has no button that runs a Codex command at once: its one button opens
  Codex's sheet, where "Get a sign-in code" runs the login command

#### Scenario: Codex's sign-in code
- **WHEN** the human chooses "Get a sign-in code" in Codex's sheet
- **THEN** the login window shows Codex's link and one-time code, and once the human has
  entered the code the command ends, the window closes, and the row shows "Logged in ·
  ChatGPT plan · Codex's login file"

### Requirement: The login window works from a phone

The login window SHALL make each link in its terminal clickable, also one wrapped over
lines, and SHALL offer a "Text to send" field that sends its text followed by Enter and
the keys ↑ ↓ Enter Esc, at a phone's width too.

#### Scenario: The code sent from the field
- **WHEN** the login command waits for a code and the human types it in "Text to send" and
  chooses Send
- **THEN** the command receives the code and Enter as one input

### Requirement: Logging out of Claude Code asks first

Claude Code's sheet SHALL offer "Log out…" only while its login comes from LADO's
secrets; it SHALL ask for a confirmation that names the running Claude agents, then remove
Claude Code's login variables from LADO's secrets and show the state read anew. A login
from the CLI's own file, the login shell, the outside folder or a project SHALL offer no
Log out.

#### Scenario: Log out with running agents
- **WHEN** the token is LADO's secret, two Claude agents run and the human chooses Log out
- **THEN** the confirmation names both, and only after Yes the token is removed and the
  row shows the state the CLI then gives

#### Scenario: A token of the outside folder
- **WHEN** the login comes from the outside folder
- **THEN** the sheet offers no Log out

### Requirement: A CLI's login variables can be set as LADO's secrets

The sheet's Save SHALL write a login variable's value to `<LADO_HOME>/secrets/<NAME>`
(folder 700, file 600, atomically) and remove the provider's other login variables from
LADO's secrets. No answer of LADO SHALL contain the value, and the server SHALL refuse a
name no provider names as its login.

#### Scenario: A token saved
- **WHEN** the human saves a token under Subscription
- **THEN** `<LADO_HOME>/secrets/CLAUDE_CODE_OAUTH_TOKEN` holds it with mode 600, the row
  shows "Logged in · Subscription (token) · LADO's secret", and the value is in no API
  answer, change feed, log, lado.db or bug report

#### Scenario: From a key to a token
- **WHEN** `ANTHROPIC_API_KEY` is LADO's secret and the human saves a token
- **THEN** LADO's secrets hold the token and no `ANTHROPIC_API_KEY`

#### Scenario: Another name
- **WHEN** a request sets `GH_TOKEN` as a LADO secret
- **THEN** the server answers 400 and writes nothing

### Requirement: An agent whose CLI needs a login waits for it and starts by itself

When an agent's CLI needs a login (Claude Code; Codex with a model that needs one) and is not logged in at launch (a session
LADO resumes by itself, or a login lost after a start's check), the agent SHALL wait from
its start with a reason that says where to log in; its window SHALL check every few
seconds, file layers read anew and the login taken whole from one layer, and start the CLI
once logged in. An unknown state SHALL NOT hold it.

#### Scenario: A session started without a login
- **WHEN** Claude Code is not logged in and a stopped session with the provider `claude` is
  resumed at the container's start or by `lado update`
- **THEN** the supervisor is `waiting` with the reason `Claude Code is not logged in: log in
  in Settings → Providers and environment, or set CLAUDE_CODE_OAUTH_TOKEN; the agent starts
  by itself once you do`, `lado ls` prints it, and Needs you shows it with "Log in…"
  leading to Settings → Providers and environment

#### Scenario: The login arrives
- **WHEN** the supervisor waits for the login and the human logs Claude Code in outside
  LADO's page (its own login file)
- **THEN** within a few seconds the window starts Claude Code, and the supervisor reaches
  its first hook with no restart

#### Scenario: A token arrives
- **WHEN** an agent waits for the login and the human saves `CLAUDE_CODE_OAUTH_TOKEN` on the
  page
- **THEN** the waiting window takes it and starts the CLI, which has the token

#### Scenario: Other CLIs are not held
- **WHEN** OpenCode or Kilo has no login, or Codex has none and its model needs none, and
  an agent of it starts
- **THEN** it starts as before, with no wait for a login

#### Scenario: A Codex session resumed without a login
- **WHEN** Codex is not logged in, its model is OpenAI's, and a stopped Codex session is
  resumed at the container's start
- **THEN** the supervisor is `waiting` with the reason `Codex CLI is not logged in: log in
  in Settings → Providers and environment, or set OPENAI_API_KEY; the agent starts by
  itself once you do`, and it starts once the human logs in with a sign-in code

#### Scenario: The status cannot be read
- **WHEN** the status command times out at a launch
- **THEN** the agent starts as before and whoever starts it is warned with why

### Requirement: lado doctor prints each CLI's login

`lado doctor` SHALL print one login line per installed CLI: `ok` with the method and where
it comes from when logged in, `warn` for a CLI whose agents need a login and have none
(with where to log in), `info` for a CLI without a login whose agents do not need one,
`warn` with why when unknown; the exit code SHALL not change for these lines.

#### Scenario: Claude Code not logged in
- **WHEN** Claude Code is installed and not logged in
- **THEN** `lado doctor` prints `[warn] Claude Code login: not logged in: …Settings →
  Providers and environment…` and exits as before

#### Scenario: Claude Code with a token of LADO's secrets
- **WHEN** LADO's secrets hold `CLAUDE_CODE_OAUTH_TOKEN`
- **THEN** `lado doctor` prints `[ok] Claude Code login: Subscription (token) · LADO's
  secret`

### Requirement: Claude Code's login method says how the human pays

Claude Code's method SHALL be named by how the human pays: "Subscription (<Plan>)" for
its account login, "Subscription (token)", "Pay per use (API key)", "Pay per use
(Console)".

#### Scenario: Claude Code with an API key
- **WHEN** the status prints `authMethod: "api_key"` and `apiKeySource:
  "ANTHROPIC_API_KEY"`
- **THEN** the state is logged in and the method "Pay per use (API key)"

### Requirement: Each CLI's row has at most one login button

Each CLI's row in Providers and environment SHALL have at most one button: "Log in…"
without a login (the primary button when its agents need one), "Change login…" with one,
none for a CLI with no way to log in from the page; the secret fields and the actions are
in the sheet it opens.

#### Scenario: Logged in
- **WHEN** Claude Code is logged in by a token of LADO's secrets
- **THEN** its row has the one button "Change login…" and no field

### Requirement: Claude Code's sheet asks how the human pays

Claude Code's sheet SHALL ask "How do you pay for Claude?" with the provider's choices,
the current one marked: "Subscription — Claude Pro or Max" (a token made with `claude
setup-token`, `CLAUDE_CODE_OAUTH_TOKEN`) and "Pay per use — API billing" (an API key,
`ANTHROPIC_API_KEY`), each with a secret field.

#### Scenario: The current choice
- **WHEN** `CLAUDE_CODE_OAUTH_TOKEN` is LADO's secret and the human chooses "Change login…"
- **THEN** the sheet asks "How do you pay for Claude?" with "Subscription — Claude Pro or
  Max" chosen and marked current, and a secret field for the token

### Requirement: A new session or worker whose CLI needs a login and has none is refused

LADO SHALL refuse a new session whose provider needs a login (Claude Code; Codex with a
model that needs one), a resume by
hand by the provider of the supervisor it starts, and a new worker by its own provider,
when that provider's status, read in the environment the agent would start from, is not
logged in; before anything of it is stored or made, naming the CLI and where to log in. A
resume LADO makes by itself and a login LADO cannot read SHALL NOT be refused.

#### Scenario: lado start without a login
- **WHEN** Claude Code is not logged in and `lado start <repo> --provider claude` starts a
  new session
- **THEN** it exits non-zero with `Claude Code is not logged in, so the session was not
  started: log in in LADO's UI (Settings → Providers and environment, `lado ui`), or set
  CLAUDE_CODE_OAUTH_TOKEN as LADO's secret or a project secret`, and lado.db, tmux and the
  agents' config folders hold nothing of that session

#### Scenario: A clone is not made for a session that cannot start
- **WHEN** Claude Code is not logged in and `lado start <git-url> --provider claude` runs
- **THEN** it refuses with the same reason before cloning, and the target folder does not
  exist

#### Scenario: The UI's start
- **WHEN** Claude Code is not logged in and `POST /api/sessions` asks for a new session with
  the provider `claude`
- **THEN** the server answers 400 with the reason and no session is stored

#### Scenario: A session approved from another session
- **WHEN** a supervisor calls `start_session` after the human's approval and the new
  session's provider, Claude Code, is not logged in
- **THEN** the tool fails with the reason and no session is stored

#### Scenario: A worker without a login
- **WHEN** a supervisor calls `spawn_worker` with the provider `claude` (with or without a
  run) and Claude Code is not logged in
- **THEN** the tool fails with `Claude Code is not logged in, so the worker was not
  started: ask the human to log in in Settings → Providers and environment, or start the
  worker with another provider`; no worktree, branch, agent or window is left, and a run's
  step still waits for its worker

#### Scenario: A project with its own login
- **WHEN** LADO has no Claude Code login and project `shop` has the secret
  `CLAUDE_CODE_OAUTH_TOKEN`
- **THEN** a new Claude session of `shop` starts, and so does its Claude worker

#### Scenario: A mixed session
- **WHEN** Claude Code is not logged in and a session's provider is `kilo`
- **THEN** the session starts, its Kilo workers start, and its worker with the provider
  `claude` is refused with the reason

#### Scenario: Other CLIs start without a login
- **WHEN** OpenCode or Kilo has no login, or Codex has none and its model needs none, and a
  new session or worker of it starts
- **THEN** it starts as before

#### Scenario: Codex without a login on OpenAI's model
- **WHEN** Codex is not logged in, the user's Codex config names no model provider (OpenAI's
  by default), and `lado start <repo> --provider codex` starts a new session
- **THEN** it exits non-zero with `Codex CLI is not logged in, so the session was not
  started: log in in LADO's UI (Settings → Providers and environment, `lado ui`), or set
  OPENAI_API_KEY as LADO's secret or a project secret`, and nothing of the session is
  stored or made

#### Scenario: A resume is not refused
- **WHEN** Claude Code is not logged in and a stopped Claude session is resumed at the
  container's start, or by `lado update` (its `lado start --wait-for-login`)
- **THEN** the session resumes and its supervisor waits for the login

#### Scenario: A resume by hand without a login
- **WHEN** Claude Code is not logged in and the human resumes a stopped Claude session with
  `lado start <repo> --name <session>`
- **THEN** it exits non-zero with `Claude Code is not logged in, so the session was not
  resumed: log in in LADO's UI (Settings → Providers and environment, `lado ui`), or set
  CLAUDE_CODE_OAUTH_TOKEN as LADO's secret or a project secret`, the session stays stopped
  and no window is made

#### Scenario: The UI's resume without a login
- **WHEN** Claude Code is not logged in and `POST /api/sessions/{name}/resume` resumes a
  stopped session with the provider `claude`
- **THEN** the server answers 400 with the same reason and the session stays stopped

#### Scenario: A resume by hand with another CLI
- **WHEN** Claude Code is not logged in and the human resumes a stopped Claude session with
  the provider `kilo`
- **THEN** the session resumes with a Kilo supervisor

#### Scenario: A login that cannot be read
- **WHEN** Claude Code's status command times out at a new session's start
- **THEN** the session starts and whoever starts it is warned with why

### Requirement: The providers list says which CLI lacks the login it needs

`GET /api/providers` SHALL give, for each provider, `login_missing`: true when its agents
need a login and its status, read in the environment of the agents without a project, or
with the project `project=<id>` names, is not logged in; false otherwise, also when the
status cannot be read. An unknown project SHALL be 404.

#### Scenario: Claude Code without a login
- **WHEN** Claude Code is installed and not logged in, and the UI asks `GET /api/providers`
- **THEN** Claude Code's entry has `login_missing: true`, and Kilo's `false` whatever its
  login

#### Scenario: Asked for a project with its own login
- **WHEN** project `shop` has the secret `CLAUDE_CODE_OAUTH_TOKEN` and LADO has no Claude
  Code login, and the UI asks `GET /api/providers?project=shop`
- **THEN** Claude Code's entry has `login_missing: false`

### Requirement: The New session window offers only CLIs that can start

The New session window and the Resume window SHALL show a provider with `login_missing` as
a disabled option "`<name>` · not logged in", never choose it by itself, and, with it
suggested or chosen, show the note "`<CLI>` is not logged in: its agents cannot start. Log
in first" leading to Settings → Providers and environment and keep Start (Resume)
disabled; the Project way and the Resume window SHALL read the list for the session's
project.

#### Scenario: The folder's last session was Claude
- **WHEN** Claude Code is not logged in and the New session window opens on a folder whose
  last session ran `claude`
- **THEN** Provider shows "choose…", the option "claude · not logged in" is disabled, the
  red note with "Log in first" is shown, and Start is disabled

#### Scenario: Log in first
- **WHEN** the human follows "Log in first"
- **THEN** the window closes and Settings → Providers and environment opens

#### Scenario: The project's own login
- **WHEN** the Project way has project `shop`, whose secrets log Claude Code in
- **THEN** "claude · Claude Code <version>" can be chosen and Start is enabled

#### Scenario: Resume without a login
- **WHEN** the Resume window opens for a stopped Claude session and Claude Code is not
  logged in
- **THEN** the option "claude · not logged in" is disabled, the red note "Claude Code is
  not logged in: its agents cannot start. Log in first" is shown, its link leading to
  Settings → Providers and environment, and Resume is disabled until another CLI with a
  login is chosen

### Requirement: Settings answers at once from the last check of the CLIs

The server SHALL keep the last result of reading the CLIs for its lifetime, answer the
section with it at once, and refresh it by one background check at a time, all CLIs at
once, each row kept as soon as it is read; the section SHALL start a check when it opens,
on ↻ by its heading and after a login, a logout or a login window's end, and change its
rows in place while ↻ turns.

#### Scenario: A second visit
- **WHEN** the section was read before and the human opens Settings again
- **THEN** the rows show at once with ↻ turning, and change in place when the check ends,
  with no "Reading the CLIs…"

#### Scenario: The first visit
- **WHEN** the server has no result yet and the section opens
- **THEN** each row shows its name and "checking…" until its CLI is read, and its state as
  soon as it is, the others still checking

#### Scenario: ↻ while a check runs
- **WHEN** a check runs and the human presses ↻
- **THEN** no second check starts and the section shows the running one's rows

#### Scenario: After Save
- **WHEN** the human saves a token in Claude Code's sheet
- **THEN** the row shows the answer of the save at once, and a check starts, whose rows
  replace it when it ends

#### Scenario: The API
- **WHEN** the UI asks `POST /api/providers/check` and then `GET /api/providers/logins`
- **THEN** the POST starts a check unless one runs (then one more runs once after it, so
  what changed meanwhile is read), and the GET answers at once with the rows kept,
  `checking: true` while a check runs, and `ready: false` on each row not read yet

#### Scenario: A check that fails
- **WHEN** reading a CLI raises
- **THEN** its row says why and the check ends; the other rows are read as usual

### Requirement: Every Codex agent shares the user's Codex login

Before a Codex agent's first hook, LADO SHALL make `auth.json` of the agent's Codex home a
symbolic link to the user's Codex login file (`$CODEX_HOME/auth.json` of the agent's
environment, else `~/.codex/auth.json`), also while that file does not exist, and SHALL
write `cli_auth_credentials_store = "file"` into the agent's config.toml; it SHALL write
nothing into the user's Codex home. A file LADO cannot link SHALL be a warning to whoever
starts the agent.

#### Scenario: Logged in once, every agent works
- **WHEN** the user has logged Codex in with ChatGPT in a terminal and starts a Codex
  session with a worker
- **THEN** each agent's `auth.json` is a link to the user's `auth.json`, and neither shows
  Codex's sign-in screen

#### Scenario: A refresh in one agent
- **WHEN** an agent's Codex refreshes the login's tokens
- **THEN** its `auth.json` is still a link, the user's file holds the new tokens, and the
  other agents and the user's own Codex go on working with them

#### Scenario: A login after the start
- **WHEN** a Codex agent waits for its login and the user logs in with a sign-in code
- **THEN** the agent's link, made before the file existed, now reaches the login, and the
  agent starts

### Requirement: A login variable gives Codex agents their login

Codex's login variables SHALL be `OPENAI_API_KEY` and `CODEX_ACCESS_TOKEN` (Codex reads
the token itself), taken whole from one layer as any CLI's. With `OPENAI_API_KEY` and no
`CODEX_ACCESS_TOKEN` in an agent's environment, LADO SHALL write the agent's `auth.json` as
a file of its own, mode 600, holding that key as Codex's own key login does, in place of the
link; a variable SHALL win over Codex's login file.

#### Scenario: A key in the secrets folder
- **WHEN** the container's secrets folder holds `OPENAI_API_KEY` and Codex has no login file
- **THEN** Codex's row shows "Logged in · Pay per use (API key) · outside folder", a Codex
  session starts, and its agents' `auth.json` is a file with mode 600 holding that key

#### Scenario: An access token
- **WHEN** LADO's secrets hold `CODEX_ACCESS_TOKEN`
- **THEN** Codex's row shows "Logged in · ChatGPT access token · LADO's secret" and each
  Codex agent gets the variable

#### Scenario: The key is no longer set
- **WHEN** an agent started with a key file and the key is removed from LADO's secrets
- **THEN** an agent started afterwards gets the link to the user's file again

### Requirement: Codex's model decides whether its agents need a login

Codex's agents SHALL need a login when the model provider of the user's Codex config, as
carried to the agents (`model_provider`, or the chosen profile's), is OpenAI's (`openai`,
also when none is named) or a provider with `requires_openai_auth = true`; with any other
provider they SHALL need none. Every reader of whether a CLI needs a login (the refusal,
the wait, the providers list, Settings, `lado doctor`) SHALL ask it of the environment it
reads the login in.

#### Scenario: A local model
- **WHEN** the user's Codex config has `model_provider = "ollama"` and Codex has no login
- **THEN** Codex's row shows "No login", `GET /api/providers` gives `login_missing: false`
  for Codex, and a Codex session starts

#### Scenario: OpenAI's model by default
- **WHEN** the user's Codex config names no model provider and Codex has no login
- **THEN** Codex's row shows "Not logged in" with the primary button "Log in…", and
  `login_missing` is true

### Requirement: Codex's sheet asks how the human pays

Codex's sheet SHALL ask "How do you pay for Codex?" with the current choice marked:
"ChatGPT plan — Plus, Pro, Business or Enterprise" with the button "Get a sign-in code",
which opens the login window (see "The login window runs the CLI's own login command");
"ChatGPT Business or Enterprise — access token" with a secret field for
`CODEX_ACCESS_TOKEN`; "Pay per use — OpenAI API key" with a secret field for
`OPENAI_API_KEY`. Codex's row SHALL NOT say that its agents do not get the login.

#### Scenario: The sheet
- **WHEN** Codex is not logged in and the human chooses "Log in…" on Codex's row
- **THEN** the sheet asks "How do you pay for Codex?" with the three choices, "ChatGPT
  plan" chosen, and its button "Get a sign-in code"

#### Scenario: A key saved
- **WHEN** the human chooses "Pay per use — OpenAI API key", pastes a key and chooses Save
- **THEN** `<LADO_HOME>/secrets/OPENAI_API_KEY` holds it with mode 600, LADO's secrets hold
  no `CODEX_ACCESS_TOKEN`, and the row shows "Logged in · Pay per use (API key) · LADO's
  secret"

#### Scenario: From a phone
- **WHEN** the human opens Codex's sheet on a phone and chooses "Get a sign-in code"
- **THEN** the login window fills the screen, its link can be tapped, and the code can be
  read in full

### Requirement: A Codex login kept in the keyring is named

When the user's Codex keeps its login only in the system keyring
(`cli_auth_credentials_store` `keyring` or `auto`), which an agent's Codex home cannot
reach, Codex's row SHALL show "Not logged in", a note that says so, and "Log in…"; a login
from the sheet SHALL go to Codex's login file.

#### Scenario: A Mac with the keyring
- **WHEN** the user's config has `cli_auth_credentials_store = "keyring"` and the user's
  Codex is logged in there
- **THEN** Codex's row shows "Not logged in", the note "Your Codex keeps its login in the
  system keyring, which Codex agents cannot read. Log in here: the login goes to Codex's
  login file, and your own Codex keeps using the keyring." and "Log in…", and a new Codex
  session on OpenAI's model is refused

### Requirement: Logging out of Codex asks first

Codex's sheet SHALL offer "Log out…" while Codex is logged in, and SHALL ask for a
confirmation that names the running Codex agents. For a login from LADO's secrets it SHALL
remove Codex's login variables from them; for Codex's login file it SHALL run `codex
logout` in the login window and say in the confirmation that the user's own Codex is
logged out too. A login from the login shell, the outside folder or a project SHALL offer
no Log out.

#### Scenario: Log out of the shared file
- **WHEN** Codex is logged in with ChatGPT in its file, two Codex agents run, and the human
  chooses Log out
- **THEN** the confirmation names both and says that the user's own Codex is logged out
  too; after Yes `codex logout` runs and the row shows "Not logged in"

#### Scenario: A key of the secrets folder
- **WHEN** Codex's login is `OPENAI_API_KEY` of the outside folder
- **THEN** the sheet offers no Log out
