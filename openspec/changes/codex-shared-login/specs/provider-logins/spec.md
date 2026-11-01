## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Codex's row says that its agents do not get the login

**Reason**: Codex agents now share the user's login (GitHub #113, LAD-166).
**Migration**: "Codex's sheet asks how the human pays" and "Every Codex agent shares the
user's Codex login".
