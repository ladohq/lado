# provider-logins Specification

## Purpose
The agent CLIs' logins: LADO reads whether each CLI is logged in by the CLI's own status
command, shows it in Settings → Providers and environment and `lado doctor`, logs Claude
Code, OpenCode and Kilo in from the UI (a phone too), keeps their login variables as LADO's
secrets, and holds an agent whose CLI needs a login until there is one.

## Requirements

### Requirement: LADO reads each CLI's login with the CLI's own command

LADO SHALL read whether an agent CLI is logged in, and how, only by the CLI's own status
command run in the environment LADO's agents get without a project (`claude auth status
--json`, `codex login status`, `opencode auth list`, `kilo auth list`), within a time
limit, and SHALL NOT read the screen of any agent. A command that fails, times out or
prints what LADO cannot read SHALL give the state `unknown` with why, never "not logged
in".

#### Scenario: Claude Code with a subscription
- **WHEN** `claude auth status --json` prints `loggedIn: true`, `authMethod: "claude.ai"`
  and `subscriptionType: "max"`
- **THEN** the state is logged in, the method "Claude subscription (Max)", and the source
  Claude Code's login file in its config folder

#### Scenario: Claude Code with a token from LADO's secrets
- **WHEN** LADO's secrets hold `CLAUDE_CODE_OAUTH_TOKEN` and the status prints
  `authMethod: "oauth_token"`
- **THEN** the state is logged in, the method "token", and the source the variable
  `CLAUDE_CODE_OAUTH_TOKEN` from LADO's secrets

#### Scenario: Claude Code not logged in
- **WHEN** the status prints `loggedIn: false` and exits 1
- **THEN** the state is not logged in

#### Scenario: OpenCode with credentials and a key variable
- **WHEN** `opencode auth list` lists the credentials `Anthropic api` and `OpenRouter
  oauth` and, under Environment, `OpenAI OPENAI_API_KEY`
- **THEN** the state is logged in with those three, each with its kind, and the source
  names the credentials file and the variable

#### Scenario: The command times out
- **WHEN** a CLI's status command does not end within the limit
- **THEN** it is killed, and the state is unknown with "timed out"

### Requirement: Settings shows the login of each agent CLI

Settings' section Providers and environment SHALL show, for each agent CLI LADO knows,
its version, its login state and method, where the login comes from (the CLI's file, or a
variable and its layer), the live agents that wait for its login, the projects that set
one of its login variables (by id), the provider's note and `lado doctor`'s provider
checks, read when the section opens, after each of its actions and on "Check again".

#### Scenario: A new user in Docker
- **WHEN** Claude Code is installed and not logged in, and a session's supervisor waits for
  its login
- **THEN** Claude Code's row shows "Not logged in", names that supervisor with a link, and
  offers the login actions and the token and key fields

#### Scenario: A project with its own token
- **WHEN** project `shop` has the secret `CLAUDE_CODE_OAUTH_TOKEN`
- **THEN** Claude Code's row names `shop` among the projects with a login of their own,
  without the value

### Requirement: Codex's row says that its agents do not get the login

Codex's row SHALL show its version and its login state for the user's own Codex home, and
SHALL say that Codex agents do not get that login yet (each has a Codex home of its own)
and work only with a model that needs no login; it SHALL offer no login action.

#### Scenario: Codex logged in
- **WHEN** `codex login status` prints `Logged in using ChatGPT`
- **THEN** the row shows that login and the note, and no login button

### Requirement: The login window runs the CLI's own login command

A login action SHALL open a terminal on the page that runs the CLI's own login or logout
command (`claude auth login`, `opencode auth login`, `kilo auth login` and their
logouts) in the environment of the agents without a project, at most one per CLI; when
the command ends the window SHALL close and the page SHALL read the state again, and
Close SHALL end the command.

#### Scenario: Claude Code's login from a phone
- **WHEN** the human opens "Log in with your Claude account…" on a phone, opens the
  printed link, signs in and sends the code with "Text to send"
- **THEN** the command ends, the window closes, and the row shows "Logged in"

#### Scenario: Opened twice
- **WHEN** Claude Code's login window is open and the action is chosen again
- **THEN** the same window is shown and no second command starts

#### Scenario: The windows end with LADO
- **WHEN** a login window runs and the UI server stops, or `lado stop --all` runs
- **THEN** its tmux session is gone, found by its label, and `lado ls` never listed it

### Requirement: The login window works from a phone

The login window SHALL make each link in its terminal clickable, also one wrapped over
lines, and SHALL offer a "Text to send" field that sends its text followed by Enter and
the keys ↑ ↓ Enter Esc, at a phone's width too.

#### Scenario: The code sent from the field
- **WHEN** the login command waits for a code and the human types it in "Text to send" and
  chooses Send
- **THEN** the command receives the code and Enter as one input

### Requirement: Logging out of Claude Code asks first

Log out of Claude Code SHALL ask for a confirmation that names the running Claude agents
before it runs `claude auth logout`, and SHALL then show the state read anew.

#### Scenario: Log out with running agents
- **WHEN** two Claude agents run and the human chooses Log out
- **THEN** the confirmation names both, and only after Yes the login is removed and the
  row shows the state the CLI then gives

### Requirement: A CLI's login variables can be set as LADO's secrets

The page SHALL offer a secret field for each variable a provider names as its login
(Claude Code: `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`); Save SHALL write it to
`<LADO_HOME>/secrets/<NAME>` (folder 700, file 600, atomically), Remove SHALL delete it
after a confirmation that names the running agents of that CLI. No answer of LADO SHALL
contain the value, and the server SHALL refuse a name no provider names as its login.

#### Scenario: A token saved
- **WHEN** the human saves `CLAUDE_CODE_OAUTH_TOKEN` on the page
- **THEN** `<LADO_HOME>/secrets/CLAUDE_CODE_OAUTH_TOKEN` holds it with mode 600, the row
  shows "set", and the value is in no API answer, change feed, log, lado.db or bug report

#### Scenario: Another name
- **WHEN** a request sets `GH_TOKEN` as a LADO secret
- **THEN** the server answers 400 and writes nothing

### Requirement: An agent whose CLI needs a login waits for it and starts by itself

When an agent's provider needs a login (Claude Code) and its launch environment is not
logged in, the agent SHALL wait from its start with the reason `<CLI> is not logged in:
log in in Settings → Providers and environment, or set <variable>; the agent starts by
itself once you do`; its window SHALL check again every few seconds, with the file layers
read anew, and start the CLI once logged in. An unknown state SHALL NOT hold it.

#### Scenario: A session started without a login
- **WHEN** Claude Code is not logged in and a session starts with the provider `claude`
- **THEN** the supervisor is `waiting` with the reason, `lado ls` prints it, and Needs you
  shows it with "Log in…" leading to Settings → Providers and environment

#### Scenario: The login arrives
- **WHEN** the supervisor waits for the login and the human logs Claude Code in on the page
- **THEN** within a few seconds the window starts Claude Code, and the supervisor reaches
  its first hook with no restart

#### Scenario: A token arrives
- **WHEN** an agent waits for the login and the human saves `CLAUDE_CODE_OAUTH_TOKEN` on the
  page
- **THEN** the waiting window takes it and starts the CLI, which has the token

#### Scenario: Other CLIs are not held
- **WHEN** Codex, OpenCode or Kilo has no login and an agent of it starts
- **THEN** it starts as before, with no wait for a login

#### Scenario: The status cannot be read
- **WHEN** the status command times out at a launch
- **THEN** the agent starts as before and whoever starts it is warned with why

### Requirement: lado doctor prints each CLI's login

`lado doctor` SHALL print one login line per installed CLI: `ok` with the method when
logged in, `warn` for a CLI whose agents need a login and have none (with where to log
in), `info` for a CLI without a login whose agents do not need one, `warn` with why when
unknown; the exit code SHALL not change for these lines.

#### Scenario: Claude Code not logged in
- **WHEN** Claude Code is installed and not logged in
- **THEN** `lado doctor` prints `[warn] Claude Code login: not logged in: …Settings →
  Providers and environment…` and exits as before
