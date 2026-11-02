## ADDED Requirements

### Requirement: LADO tries Codex's sandbox before it launches a Codex agent on Linux

Before it launches a Codex agent on Linux in any permission mode but `bypassPermissions`,
LADO SHALL run `codex sandbox -- true` with the agent's `CODEX_HOME` and environment, after
writing the agent's config.toml. A nonzero exit, a timeout of 10 seconds or a failure to
run it SHALL count as a sandbox that cannot start. LADO SHALL NOT run the probe on macOS or
in `bypassPermissions`.

#### Scenario: The sandbox starts
- **WHEN** a Codex agent starts in `default` on Linux and the probe exits 0
- **THEN** the agent launches with `-a on-request`, LADO's permission profile in its
  config.toml, no `--sandbox` on its argv and no warning about the sandbox

#### Scenario: Bypass mode
- **WHEN** a Codex agent starts in `bypassPermissions`
- **THEN** LADO runs no probe and launches it with `--dangerously-bypass-approvals-and-sandbox`
  as before

#### Scenario: macOS
- **WHEN** a Codex agent starts in `default` on macOS
- **THEN** LADO runs no probe and launches it as before

### Requirement: A Codex agent in LADO's container runs without a sandbox that cannot start

In LADO's container (`LADO_CONTAINER` set), when the probe says Codex's sandbox cannot
start, LADO SHALL launch the Codex agent with `--sandbox danger-full-access`, without
`default_permissions` and `permissions` in its config.toml, and with the approval policy of
its mode unchanged (`-a on-request` for `default`), and SHALL warn at the launch.

#### Scenario: A supervisor in the container
- **WHEN** a session of provider `codex` in the mode `default` starts in LADO's container,
  where `codex sandbox -- true` fails with `bwrap: No permissions to create a new
  namespace…`
- **THEN** the supervisor's argv holds `-a on-request` and `--sandbox danger-full-access`,
  its config.toml has no `default_permissions`, and `lado start` prints the warning naming
  `supervisor` and the bwrap line, which the UI shows in the session's start notice

#### Scenario: A worker in the container
- **WHEN** a Codex worker is spawned in that session
- **THEN** it launches the same way and the warning naming the worker is written to the
  session's loop.log

#### Scenario: A shell command in the container
- **WHEN** such an agent runs a shell command
- **THEN** the command runs, and Codex asks no "retry without sandbox?" question

### Requirement: The container's warning names the agent and the cause

The launch warning of a Codex agent that runs without its sandbox in LADO's container SHALL
be one line naming the agent and quoting the first line of the probe's stderr that is not
one of Codex's own `WARNING:` lines: `Codex's sandbox cannot start here (<line>): Codex agent <name> runs without it, and LADO's
container is its only boundary`.

#### Scenario: The warning's text
- **WHEN** the probe of supervisor's launch in the container fails with `bwrap: No
  permissions to create a new namespace…`
- **THEN** the launch's warnings hold `Codex's sandbox cannot start here (bwrap: No
  permissions to create a new namespace…): Codex agent supervisor runs without it, and
  LADO's container is its only boundary`

### Requirement: A Codex agent on a host keeps a sandbox that cannot start, with a warning

Outside LADO's container, when the probe says Codex's sandbox cannot start, LADO SHALL
launch the Codex agent as it would with a working sandbox, and the launch SHALL warn in one
line naming the agent and quoting the first line of the probe's stderr that is not one of
Codex's own `WARNING:` lines: `Codex's sandbox cannot start here (<line>): Codex agent <name> asks before each shell command;
docs/install.md says how to allow it, or use bypassPermissions`.

#### Scenario: A Linux host without user namespaces
- **WHEN** a Codex agent starts in `default` on a Linux host where the probe fails
- **THEN** its argv holds `-a on-request` and no `--sandbox`, its config.toml keeps LADO's
  permission profile, and the launch warns with the docs/install.md line

### Requirement: docs/install.md says what to do when Codex's sandbox cannot start

docs/install.md SHALL say that Codex agents in LADO's container run without Codex's
sandbox and why, and, for a Linux host, why Codex's sandbox may not start (unprivileged
user namespaces refused by the kernel, AppArmor or seccomp) and what the user can do:
allow them, or choose `bypassPermissions`.

#### Scenario: The docs
- **WHEN** a user reads docs/install.md's Docker part and its Linux part
- **THEN** each names Codex's sandbox: the container's fallback in the first, the host's
  warning and its remedies in the second
