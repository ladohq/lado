## MODIFIED Requirements

### Requirement: LADO reads each CLI's login with the CLI's own command

LADO SHALL read whether an agent CLI is logged in, and how, only by the CLI's own status
command run in the environment LADO's agents of that CLI get without a project
(`claude auth status --json`, `codex login status`, `opencode auth list`, `kilo auth
list`), within a time limit, and SHALL NOT read the screen of any agent. A command that
fails, times out or prints what LADO cannot read SHALL give the state `unknown` with why,
never "not logged in".

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

#### Scenario: The command times out
- **WHEN** a CLI's status command does not end within the limit
- **THEN** it is killed, and the state is unknown with "timed out"

### Requirement: Settings shows the login of each agent CLI

Settings' section Providers and environment SHALL show, for each agent CLI LADO knows, its
name, its version, a dot and one state line ("Logged in · <method> · <where from>",
"Not logged in", "No login" or "Unknown: <why>"), then the live agents that wait for its
login, the projects that set a login variable of it and the provider's note.
It SHALL be read when it opens, after each of its actions and on "Check again", with
`lado doctor`'s provider checks under the rows.

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

### Requirement: The login window runs the CLI's own login command

For a CLI whose login is the CLI's own command (OpenCode, Kilo), the row's button SHALL
open a terminal on the page that runs it (`opencode auth login`, `kilo auth login`), with
"Log out of one…" (their `auth logout`) while logged in, in the environment of the agents
without a project, at most one per CLI; when the command ends the window SHALL close and
the page SHALL read the state again, and Close SHALL end the command. LADO SHALL run no
login command of Claude Code.

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
- **THEN** its row shows its state and note and no button

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

When an agent's provider needs a login (Claude Code) and its launch environment is not
logged in, the agent SHALL wait from its start with the reason `<CLI> is not logged in:
log in in Settings → Providers and environment, or set <variable>; the agent starts by
itself once you do`; its window SHALL check again every few seconds, with the file layers
read anew and a login taken whole from one layer, and start the CLI once logged in. An
unknown state SHALL NOT hold it.

#### Scenario: A session started without a login
- **WHEN** Claude Code is not logged in and a session starts with the provider `claude`
- **THEN** the supervisor is `waiting` with the reason, `lado ls` prints it, and Needs you
  shows it with "Log in…" leading to Settings → Providers and environment

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
- **WHEN** Codex, OpenCode or Kilo has no login and an agent of it starts
- **THEN** it starts as before, with no wait for a login

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

## ADDED Requirements

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
