## ADDED Requirements

### Requirement: A new session or worker whose CLI needs a login and has none is refused

LADO SHALL refuse a new session whose provider needs a login (Claude Code), and a new
worker by the worker's own provider, when that provider's status, read in the environment
the agent would start from (with the session's project's variables and secrets), is not
logged in; the refusal SHALL come before anything of the session or worker is stored or
made, and SHALL name the CLI and where to log in. A resume and a login LADO cannot read
SHALL NOT be refused.

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
- **WHEN** Codex, OpenCode or Kilo has no login and a new session or worker of it starts
- **THEN** it starts as before

#### Scenario: A resume is not refused
- **WHEN** Claude Code is not logged in and a stopped Claude session is resumed by `lado
  start`, by the UI's Resume or at LADO's start
- **THEN** the session resumes and its supervisor waits for the login

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

The New session window SHALL show a provider with `login_missing` as a disabled option
"`<name>` · not logged in", never choose it by itself, and, with it suggested or chosen,
show the note "`<CLI>` is not logged in: its agents cannot start. Log in first" leading to
Settings → Providers and environment and keep Start disabled; the Project way SHALL read
the list for the chosen project. The Resume window SHALL let such a resume go on with a
warning.

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
- **THEN** the amber note "Claude Code is not logged in: the supervisor waits until you log
  in. Log in…" is shown, its link leading to Settings → Providers and environment, and
  Resume is enabled

## MODIFIED Requirements

### Requirement: An agent whose CLI needs a login waits for it and starts by itself

When an agent's CLI needs a login (Claude Code) and is not logged in at launch (a resumed
agent, or a login lost after a start's check), the agent SHALL wait from its start with
the reason `<CLI> is not logged in: log in in Settings → Providers and environment, or
set <variable>; the agent starts by itself once you do`; its window SHALL check every few
seconds, file layers read anew and the login taken whole from one layer, and start
the CLI once logged in. An unknown state SHALL NOT hold it.

#### Scenario: A session started without a login
- **WHEN** Claude Code is not logged in and a stopped session with the provider `claude` is
  resumed
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
