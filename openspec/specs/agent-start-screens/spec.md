# agent-start-screens Specification

## Purpose
What an agent CLI shows before its first hook: the screens of Claude Code that LADO
answers by the agent's own settings, and the session loop's safety net that shows an agent
of any provider held by a screen LADO does not know as waiting for an answer in its
terminal.

## Requirements

### Requirement: A Claude agent in bypassPermissions skips Claude Code's warning by its own settings

When a Claude agent starts with the permission mode `bypassPermissions`, LADO SHALL put
`skipDangerousModePermissionPrompt: true` in that agent's own `--settings` file, so Claude
Code's screen "WARNING: Claude Code running in Bypass Permissions mode" does not hold it;
an agent of any other mode SHALL NOT get the key, and LADO SHALL write nothing for it into
`.claude.json` or the user's settings.

#### Scenario: A session started in bypassPermissions
- **WHEN** a Claude session is started with `--permission-mode bypassPermissions` on a clean
  Claude Code config
- **THEN** the supervisor's settings file holds `skipDangerousModePermissionPrompt: true`,
  the supervisor reaches its first hook with no human, and `.claude.json` holds no key for
  the bypass mode

#### Scenario: Another mode
- **WHEN** a Claude session is started in `default`, `acceptEdits`, `auto`, `manual`,
  `dontAsk` or `plan`
- **THEN** its agents' settings files hold no `skipDangerousModePermissionPrompt`

#### Scenario: A worker of a bypass session
- **WHEN** a worker of a Claude session in `bypassPermissions` is spawned
- **THEN** its settings file holds the key too and it reaches its first hook with no human

### Requirement: A Claude agent takes its repository's MCP servers without asking

LADO SHALL put `enableAllProjectMcpServers: true` in every Claude agent's own `--settings`
file, so the servers a repository declares in its `.mcp.json` are used as for a human who
trusts the folder and Claude Code's screen "New MCP server found in this project" does not
hold the agent; LADO SHALL write nothing for it into the repository or its worktrees.

#### Scenario: A repository with a .mcp.json
- **WHEN** a Claude session starts in a repository whose `.mcp.json` declares a server
- **THEN** the supervisor reaches its first hook with no human, the server is enabled, and
  `git status` of the repository shows no new file

### Requirement: An agent with no hook after its launch waits for an answer in its terminal

The session loop SHALL put an agent of any provider that is `starting` with no hook yet,
30 s or more after its CLI's launch, into `waiting` with the reason `Waiting for an answer
in its terminal: no sign from it 30 s after its start. Open its terminal.`; its first hook
SHALL make it ready.

#### Scenario: A screen LADO does not know
- **WHEN** a Claude agent's CLI shows a screen before its first hook and nobody answers it
  for 30 s
- **THEN** the agent is `waiting` with the reason, `lado ls` prints it and Needs you shows
  it with its terminal

#### Scenario: The human answers in the terminal
- **WHEN** that agent's human answers the screen and the CLI fires its session start
- **THEN** the agent is ready and takes its queue, with no restart

#### Scenario: A slow start under the limit
- **WHEN** an agent's first hook comes 20 s after its window opened
- **THEN** it was never `waiting`

#### Scenario: After the login's wait
- **WHEN** an agent waited 5 minutes for its login and its window starts the CLI
- **THEN** it is measured from the moment its window started the CLI, not from the
  window's opening

#### Scenario: Any provider
- **WHEN** a Kilo, OpenCode or Codex agent gives no hook 30 s after its launch
- **THEN** it is `waiting` with the same reason

### Requirement: A Codex agent trusts its repository by its own config

Before a Codex agent starts, LADO SHALL write `trust_level = "trusted"` for the real path of
the session's repository's main root into the agent's own config.toml, unless the user's
Codex config has an entry Codex goes by for the agent's folder, which LADO SHALL carry as it
is (`untrusted` too); LADO SHALL write nothing into the user's Codex home. Codex's question
"Trust this folder?" SHALL then not hold the agent.

#### Scenario: A repository the user's Codex never saw
- **WHEN** a Codex session is started in a repository the user's Codex config has no entry
  for
- **THEN** the supervisor's config.toml trusts the repository's main root, the supervisor
  reaches its first hook with no human, and the user's config.toml is unchanged

#### Scenario: A worker in a worktree
- **WHEN** a Codex worker is spawned in its worktree
- **THEN** its config.toml trusts the main repository's root and it reaches its first hook
  with no human

#### Scenario: Untrusted by the user
- **WHEN** the user's Codex config marks the repository `untrusted`
- **THEN** the agent's config.toml carries `untrusted`, and the agent starts with no
  question

### Requirement: A Codex agent takes its repository's hooks without asking

When the agent's folder is trusted, LADO SHALL record in the agent's own config.toml the
hash Codex trusts each hook of the repository's own Codex config by (`.codex/hooks.json`
and the hooks of `.codex/config.toml` from the project root down), so Codex's question to
review them does not hold the agent, as a human who trusts the folder takes them; a hook
the user disabled in the user's Codex config SHALL stay disabled.

#### Scenario: A repository with hooks
- **WHEN** a Codex session starts in a repository whose `.codex/hooks.json` has a hook the
  user never reviewed
- **THEN** the supervisor reaches its first hook with no human and the repository's hook
  runs

#### Scenario: A hook the user disabled
- **WHEN** the user's Codex config has `enabled = false` for one of those hooks
- **THEN** the agent's config.toml keeps it disabled

### Requirement: A Codex agent starts without Codex's plugins

LADO SHALL write `features.plugins = false` into every Codex agent's config.toml, so Codex
does not fetch its plugins catalogue into the agent's home at the start.

#### Scenario: A new agent's home
- **WHEN** a Codex agent has started
- **THEN** its Codex home has no `.tmp/plugins`

### Requirement: A logged-in Codex agent starts with no screen in every mode

With a login and its repository trusted, a Codex agent SHALL reach its first hook with no
screen in each of LADO's permission modes for Codex (`default`, `bypassPermissions`) and
with none.

#### Scenario: Each mode
- **WHEN** a Codex session is started with `--permission-mode default`, with
  `bypassPermissions`, and with no mode, Codex logged in
- **THEN** each supervisor reaches its first hook with no human
