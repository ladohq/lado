# claude-folder-trust Specification

## Purpose
LADO records Claude Code's folder trust in the session's repository itself, through one
careful writer of Claude Code's config, and keeps the trust question as the fallback.

## Requirements

### Requirement: LADO records Claude Code's trust in the session's repository

Before it starts a Claude agent (a session's start, its resume, a worker's spawn), when
Claude Code would not trust the agent's folder, LADO SHALL set `hasTrustDialogAccepted` to
`true` in the `projects` entry of the real path of the repository's main root in the
global config Claude Code reads its trust from, and change nothing else; the agent SHALL
then not wait for the human.

#### Scenario: A repository Claude Code has not seen

- **WHEN** a session is started with the provider `claude` in a repository the config
  does not trust
- **THEN** the config's `projects["<repo's real path>"].hasTrustDialogAccepted` is `true`
  and the supervisor is not `waiting` with the trust question

#### Scenario: A worker in a worktree

- **WHEN** a Claude worker is spawned in its worktree of an untrusted repository
- **THEN** the entry written is the main repository's root, not the worktree's path

#### Scenario: Already trusted

- **WHEN** the config already trusts the repository (its entry, or a folder Claude Code
  goes by)
- **THEN** the file is not written (its contents and modification time are unchanged) and
  no line is told or logged

#### Scenario: An entry Claude Code made earlier

- **WHEN** the repository's entry exists with `hasTrustDialogAccepted: false` and other
  keys
- **THEN** the flag becomes `true` and the entry's other keys keep their values

#### Scenario: The agent's own config folder

- **WHEN** the agent's environment sets `CLAUDE_CONFIG_DIR`
- **THEN** the trust is written to `$CLAUDE_CONFIG_DIR/.claude.json`, and the home's
  `.claude.json` is not touched

#### Scenario: An older config file

- **WHEN** `<config home>/.config.json` exists
- **THEN** the trust is written there, the file Claude Code reads first

### Requirement: Claude Code's config is changed by one careful writer

Every change LADO makes to Claude Code's global config SHALL go through one function that
re-reads the file right before the write, keeps every key it does not change, writes
nothing when the change changes nothing, writes the new contents to a temporary file in the
same folder and replaces the old file with it in one step, keeps the old file's mode, and
writes through a symlinked config to its target.

#### Scenario: The rest of the config is kept

- **WHEN** LADO records the trust in a config holding other top-level keys (a login,
  `mcpServers`) and other projects' entries
- **THEN** after the write every one of them is there with the same value

#### Scenario: Mode and symlink

- **WHEN** the config is a symlink to a file of mode 600
- **THEN** after the write the config is still that symlink, and its target holds the
  entry and still has mode 600

#### Scenario: No temporary file is left

- **WHEN** the write succeeds or fails
- **THEN** no temporary file of LADO's is left in the config's folder

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

### Requirement: A config LADO cannot understand is left as it is

LADO SHALL NOT write a Claude Code config that it cannot read, that is not JSON, whose top
level or `projects` is not a JSON object, or whose repository entry is not a JSON object;
it SHALL leave the file byte for byte as it was and say why.

#### Scenario: Not JSON

- **WHEN** the config is not valid JSON
- **THEN** the file is unchanged, and whoever starts the agent is warned `cannot tell
  whether Claude Code trusts <repo>: <file>: <error>`, as before this change

#### Scenario: The repository's entry is not an object

- **WHEN** `projects["<repo>"]` is a string or `null`
- **THEN** the file is unchanged and the agent waits with the fallback reason, which names
  the file and why

### Requirement: The trust question stays the fallback when LADO cannot record it

When LADO cannot record the trust (the config refused, the folder not writable, any
`OSError`), the agent SHALL wait in Needs you from its start with the reason
`Claude Code asks whether to trust <repo>: LADO could not record the trust (<why>); in its
terminal choose "Yes, I trust this folder" (Enter alone answers "No, exit" and closes the
agent)`.

#### Scenario: A config folder LADO cannot write

- **WHEN** the config's folder is read-only and the config does not trust the repository
- **THEN** the agent is `waiting`, its status reason is the fallback reason with the
  error, and nothing in the folder changed

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
