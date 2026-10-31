## Purpose

What an agent CLI shows before its first hook: the screens of Claude Code that LADO
answers by the agent's own settings, and the session loop's safety net that shows an agent
of any provider held by a screen LADO does not know as waiting for an answer in its
terminal.

## ADDED Requirements

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
