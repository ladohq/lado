## MODIFIED Requirements

### Requirement: Settings shows the login of each agent CLI

Settings' section Agent CLIs and environment SHALL show, for each agent CLI LADO knows, its
name, its version, a dot and one state line, then, while its login is missing, the live
agents that wait for it, the projects that set a login variable of it and the provider's
note. Of `lado doctor`'s provider checks it SHALL show only what the user can fix (the
scenarios below), with no check's level and no other check.

#### Scenario: The section's words
- **WHEN** the human opens Settings → Agent CLIs and environment
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
  in Settings → Agent CLIs and environment, or set CLAUDE_CODE_OAUTH_TOKEN; the agent starts
  by itself once you do`, `lado ls` prints it, and Needs you shows it with "Log in…"
  leading to Settings → Agent CLIs and environment

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
  in Settings → Agent CLIs and environment, or set OPENAI_API_KEY; the agent starts by
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
  Agent CLIs and environment…` and exits as before

#### Scenario: Claude Code with a token of LADO's secrets
- **WHEN** LADO's secrets hold `CLAUDE_CODE_OAUTH_TOKEN`
- **THEN** `lado doctor` prints `[ok] Claude Code login: Subscription (token) · LADO's
  secret`

### Requirement: Each CLI's row has at most one login button

Each CLI's row in Agent CLIs and environment SHALL have at most one button: "Log in…"
without a login (the primary button when its agents need one), "Change login…" with one,
none for a CLI with no way to log in from the page; the secret fields and the actions are
in the sheet it opens.

#### Scenario: Logged in
- **WHEN** Claude Code is logged in by a token of LADO's secrets
- **THEN** its row has the one button "Change login…" and no field

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
  started: log in in LADO's UI (Settings → Agent CLIs and environment, `lado ui`), or set
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
  started: ask the human to log in in Settings → Agent CLIs and environment, or start the
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
  started: log in in LADO's UI (Settings → Agent CLIs and environment, `lado ui`), or set
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
  resumed: log in in LADO's UI (Settings → Agent CLIs and environment, `lado ui`), or set
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

### Requirement: The New session window offers only CLIs that can start

The New session window and the Resume window SHALL show a provider with `login_missing` as
a disabled option "`<name>` · not logged in", never choose it by itself, and, with it
suggested or chosen, show the note "`<CLI>` is not logged in: its agents cannot start. Log
in first" leading to Settings → Agent CLIs and environment and keep Start (Resume)
disabled; the Project way and the Resume window SHALL read the list for the session's
project.

#### Scenario: The folder's last session was Claude
- **WHEN** Claude Code is not logged in and the New session window opens on a folder whose
  last session ran `claude`
- **THEN** Agent CLI shows "choose…", the option "claude · not logged in" is disabled, the
  red note with "Log in first" is shown, and Start is disabled

#### Scenario: Log in first
- **WHEN** the human follows "Log in first"
- **THEN** the window closes and Settings → Agent CLIs and environment opens

#### Scenario: The project's own login
- **WHEN** the Project way has project `shop`, whose secrets log Claude Code in
- **THEN** "claude · Claude Code <version>" can be chosen and Start is enabled

#### Scenario: Resume without a login
- **WHEN** the Resume window opens for a stopped Claude session and Claude Code is not
  logged in
- **THEN** the option "claude · not logged in" is disabled, the red note "Claude Code is
  not logged in: its agents cannot start. Log in first" is shown, its link leading to
  Settings → Agent CLIs and environment, and Resume is disabled until another CLI with a
  login is chosen
