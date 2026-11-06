## MODIFIED Requirements

### Requirement: A new session or worker whose CLI needs a login and has none is refused

LADO SHALL refuse a new session whose provider needs a login (Claude Code on no model server;
Codex with a model that needs one), a resume by
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

### Requirement: An agent whose CLI needs a login waits for it and starts by itself

When an agent's CLI needs a login (Claude Code on no model server; Codex with a model that needs one) and is not logged in at launch (a session
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
