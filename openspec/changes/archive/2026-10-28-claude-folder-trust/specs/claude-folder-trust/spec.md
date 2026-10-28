## ADDED Requirements

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

### Requirement: Whoever starts the agent is told that LADO recorded the trust

When LADO records Claude Code's trust, it SHALL tell whoever starts the agent `LADO
recorded Claude Code's trust in <repo> in <config file>` and write that line to the
session's loop.log, once per write.

#### Scenario: The session's start

- **WHEN** `lado start` records the trust for the supervisor
- **THEN** it prints the line on stderr, `Started.warnings` holds it, and loop.log holds
  it once

#### Scenario: A worker's spawn

- **WHEN** `spawn_worker` records the trust for a worker
- **THEN** its result's warnings and loop.log hold the line once

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
`projects["<repo>"].hasTrustDialogAccepted: true`, with mode 600.

#### Scenario: A fresh home

- **WHEN** a Claude agent is started and no config file exists
- **THEN** the file exists afterwards as `{"projects": {"<repo>": {"hasTrustDialogAccepted":
  true}}}` with mode 600, and the agent does not wait for the trust question

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
