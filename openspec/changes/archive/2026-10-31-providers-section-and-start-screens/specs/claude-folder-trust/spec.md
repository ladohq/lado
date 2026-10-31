## REMOVED Requirements

### Requirement: Whoever starts the agent is told that LADO recorded the trust

**Reason**: The human's decision (LAD-163, item 5): LADO's own writes into Claude Code's
config are no warning; "Warnings: LADO recorded Claude Code's trust …" over a new
session's chat looked like a problem.
**Migration**: Replaced by "LADO's writes into Claude Code's config go to the session's log
only", which logs the same line in loop.log and tells no one.

## ADDED Requirements

### Requirement: LADO's writes into Claude Code's config go to the session's log only

Each line saying what LADO wrote into Claude Code's config (`Blocker.notes`) SHALL be
written to the session's loop.log once per write with the agent's name, and SHALL NOT be
told anywhere else (start warnings, stderr, a tool's result, the UI, a waiting window's
terminal); a line that LADO could not read or write the config, or that the agent will
wait, SHALL still be told.

#### Scenario: The session's start
- **WHEN** `lado start` records the trust for the supervisor
- **THEN** stderr and `Started.warnings` hold no line about it, and loop.log holds
  `supervisor: LADO recorded Claude Code's trust in <repo> in <config file>` once

#### Scenario: A worker's spawn
- **WHEN** `spawn_worker` records the trust for a worker
- **THEN** its result has no warning about it and loop.log holds the line once

#### Scenario: The UI's start
- **WHEN** a session started from the UI records the trust and the first run
- **THEN** the session's page shows no "Warnings:" box

#### Scenario: The login arrives for a waiting agent
- **WHEN** an agent's waiting window records the first run once the login is there
- **THEN** its terminal shows no line about it and loop.log holds it once

#### Scenario: A config LADO cannot read
- **WHEN** Claude Code's config is not JSON at an agent's start
- **THEN** whoever starts the agent is told `cannot tell whether Claude Code trusts <repo>:
  <file>: <error>` as before

## MODIFIED Requirements

### Requirement: A missing config is created with the trust alone

When Claude Code's config file does not exist, LADO SHALL create it holding only
`projects["<repo>"].hasTrustDialogAccepted: true`, with mode 600; the first-run keys LADO
records for a logged-in agent (`hasCompletedOnboarding`, an approved API key) SHALL then
be added by their own writes, and nothing else. The trust needs no login: an agent that
waits for its login gets it at its start, logged in loop.log.

#### Scenario: A fresh home

- **WHEN** a stopped Claude session is resumed at the container's start, Claude Code is not
  logged in, and no config file exists (a new session and a resume by hand are refused
  without the login: provider-logins)
- **THEN** the file exists afterwards as `{"projects": {"<repo>": {"hasTrustDialogAccepted":
  true}}}` with mode 600, loop.log holds the trust's line, and the agent waits for its
  login, not for the trust question

#### Scenario: The login arrives in a fresh home

- **WHEN** that agent's login is there
- **THEN** its window adds `hasCompletedOnboarding: true` to the file, logs the line in
  loop.log and starts the CLI

#### Scenario: A fresh home with a login

- **WHEN** a Claude agent is started with `CLAUDE_CODE_OAUTH_TOKEN` and no config file
  exists
- **THEN** the file holds exactly the trust entry and `hasCompletedOnboarding: true`, with
  mode 600

### Requirement: LADO records Claude Code's first run for a logged-in agent

Before it starts a Claude agent that is logged in, or whose login it cannot read (which
holds no agent), LADO SHALL set `hasCompletedOnboarding` to `true` in Claude Code's global
config when it is not, through the one careful writer, so the agent does not stop at the
first-run screen; it SHALL log `LADO recorded Claude Code's first run in <config file>` in
loop.log, once per write.

#### Scenario: A fresh config with a token
- **WHEN** a Claude agent starts with `CLAUDE_CODE_OAUTH_TOKEN` and a config without
  `hasCompletedOnboarding`
- **THEN** the config has `hasCompletedOnboarding: true`, the line is logged, and the agent
  reaches its first hook with no human

#### Scenario: A login LADO cannot read
- **WHEN** a Claude agent starts while Claude Code's status command times out, and the
  config has no `hasCompletedOnboarding`
- **THEN** the agent starts with the warning, and the config has `hasCompletedOnboarding:
  true`

### Requirement: The first run of an agent that waits for its login is recorded by its window

LADO SHALL NOT write `hasCompletedOnboarding` while Claude Code is not logged in. Whoever
starts an agent that waits for its login is told the wait; the agent's waiting window
SHALL write the first run once the login is there, log the line in loop.log, then start
the CLI.

#### Scenario: Not logged in
- **WHEN** a Claude agent waits for a login
- **THEN** `hasCompletedOnboarding` is not written until the login is there; then its
  window writes it and logs the line in loop.log, and the CLI starts

### Requirement: LADO approves the API key it gives Claude Code

When a Claude agent's environment has `ANTHROPIC_API_KEY` whose last 20 characters are in
neither list of `customApiKeyResponses` in Claude Code's config, LADO SHALL add them to
`approved` through the one careful writer before the agent starts, and log `LADO recorded
the approval of ANTHROPIC_API_KEY in <config file>` in loop.log, never any part of the
key. A key in `rejected` SHALL be left as it is, and the agent SHALL wait with a reason
saying so.

#### Scenario: A new key
- **WHEN** a Claude agent starts with an `ANTHROPIC_API_KEY` Claude Code has not seen
- **THEN** its last 20 characters are in `approved`, and the agent does not stop at
  "Detected a custom API key"

#### Scenario: A key the human rejected
- **WHEN** the key's last 20 characters are in `rejected`
- **THEN** the config is unchanged and the agent waits with the reason
