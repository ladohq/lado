## ADDED Requirements

### Requirement: The agents of a session in a project get the project's secrets

LADO SHALL give each agent it launches in a session that is in a project the project's
secrets with its plain variables, read anew from the secrets folder at each launch, in the
project's layer: login shell → outside folder → the project's variables and secrets →
LADO's and the provider's. A session without a project SHALL get no project's secret.

#### Scenario: Two projects, one secret name
- **WHEN** project `shop` has the secret `GH_TOKEN=a` and `acme` has `GH_TOKEN=b`, and a
  session runs in each
- **THEN** in `shop` the supervisor, a worker, a flow run's worker and the supervisor of the
  session it starts with `start_session` have `GH_TOKEN=a`, and every agent of `acme` has
  `b`

#### Scenario: No project
- **WHEN** `shop` has the secret `GH_TOKEN` and a session without a project starts
- **THEN** its agents have no `GH_TOKEN` from `shop`

#### Scenario: Over the outside folder
- **WHEN** the outside folder has `GH_TOKEN` with `out` and `shop` has the secret
  `GH_TOKEN=a`
- **THEN** an agent of a session in `shop` has `a`, and an agent of a session without a
  project has `out`

### Requirement: The kits' checks see the project's secrets

A kit's MCP server whose `${NAME}` is set only as a secret of the session's project SHALL
pass the kit's check and get the value through `lado.mcp_exec` from the agent's
environment; no secret's value SHALL go into the agent's config or a process's arguments.

#### Scenario: A kit key only in the project
- **WHEN** a kit's MCP server has `env: {YOUGILE_API_KEY: ${YOUGILE_API_KEY}}`, the login
  shell and the outside folder lack it, and `shop` has it as a secret
- **THEN** a session in `shop` with that kit starts, and the server gets the project's value

#### Scenario: Without the project
- **WHEN** the same kit starts in a session without a project
- **THEN** the start is refused with `YOUGILE_API_KEY is not set`, as before

### Requirement: One reader reads the outside folder and a project's secrets folder

One core function SHALL read both the outside folder and a project's secrets folder, by
the outside folder's rules of a file it gives (a regular file, a variable name, not
reserved, at most 64 KiB of UTF-8 text without NUL, one line break at the end dropped,
names starting with `.` passed over). In a project's secrets folder a name reserved for a
project variable SHALL count as reserved.

#### Scenario: A provider's name
- **WHEN** the secrets folder of `shop` holds `CODEX_HOME`
- **THEN** it is not given and is named with `a reserved name`

### Requirement: A project's secrets folder gives no link and nothing others may read

LADO SHALL NOT give a file of a project's secrets folder that is a symbolic link or that
others may read or write (any group or other bit of its mode), nor any file of a secrets
folder that is a symbolic link or that others may read, write or enter.

#### Scenario: A file others may read
- **WHEN** `<LADO_HOME>/projects/shop/secrets/GH_TOKEN` has the mode 644
- **THEN** no agent of `shop` gets `GH_TOKEN`, and the file is named with `readable or
  writable by others: chmod 600 it`

#### Scenario: A link in the secrets folder
- **WHEN** the secrets folder of `shop` holds `GH_TOKEN`, a link to `/tmp/t`
- **THEN** no agent of `shop` gets `GH_TOKEN`, and the file is named with `a symbolic link`

### Requirement: A project's secret file not given is named with its reason

Each file of a project's secrets folder that is not given, and the folder itself when it
is not used, SHALL be named with its reason, never with its content, in the warnings of a
start and a resume of a session in the project, as `project secret <name> of <id> not
used: <reason>` (`project secrets folder of <id> not used: <reason>` for the folder), and
by `lado doctor`.

#### Scenario: Too large
- **WHEN** the secrets folder of `shop` holds `BIG` of 70 000 bytes and a session of `shop`
  starts
- **THEN** `lado start` prints `project secret BIG of shop not used: larger than 64 KiB`, and
  the agents have no `BIG`

### Requirement: A project's secrets stay out of LADO's records

LADO SHALL write no value of a project's secret anywhere but its file and the agent's
launch file (`env.json` in its config folder, mode 600, removed once read), as it does for
every variable. Errors about a secret SHALL name it, never its value.

#### Scenario: The places checked
- **WHEN** a project's secret holds a unique value
- **THEN** it appears in none of `hooks.log`, `loop.log`, `errors.jsonl`, `server.log`,
  `lado log`, `lado.db`, the API's answers (errors included), the change feed, the bug
  report, telemetry's payload, the output of `lado project show` and `lado doctor`, any
  process's arguments and the tmux server's environment

#### Scenario: A canary secret
- **WHEN** a project's secret holds a unique value set through the CLI and the API, a
  session of the project starts, a worker and a flow run's worker are spawned, a refused
  set and a refused API request are made, and `lado doctor`, `lado bug-report`, `lado log`
  and `lado project show` run
- **THEN** the value appears in none of those places, and no launch file is left once the
  agents run

### Requirement: lado doctor checks the projects' secrets folders

`lado doctor` SHALL print one check `[warn] Project secrets: <id>: <name> not used:
<reason>[; …]` for the files of projects' secrets folders that are not given (and each
folder not used), by project and file name, never a value; with none it SHALL print no
such line, and its exit code SHALL stay 0. The bug report SHALL hold no project secret's
name or value.

#### Scenario: A file others may read
- **WHEN** `shop`'s secret `GH_TOKEN` has the mode 644
- **THEN** `lado doctor` prints `[warn] Project secrets: shop: GH_TOKEN not used: readable
  or writable by others: chmod 600 it`

#### Scenario: All well
- **WHEN** every secret file of every project is usable
- **THEN** `lado doctor` prints no `Project secrets` line

## MODIFIED Requirements

### Requirement: lado doctor names the project variables that override the outside folder

While a project's variable or secret has the name of a variable the outside folder gives,
`lado doctor` SHALL print one check `[info] Project variables: <id> overrides
<NAME>[, <NAME>…] of LADO_ENV_DIR`, the projects joined by `; `, by id, never a value;
with no such name it SHALL print no such line. The bug report SHALL hold no project
variable's name or value.

#### Scenario: An override
- **WHEN** the outside folder gives `BOARD_URL` and `GH_TOKEN`, and project `shop` has
  `BOARD_URL`
- **THEN** `lado doctor` prints `[info] Project variables: shop overrides BOARD_URL of
  LADO_ENV_DIR`, and its exit code stays 0

#### Scenario: No override
- **WHEN** no project variable has a name the outside folder gives
- **THEN** `lado doctor` prints no `Project variables` line

#### Scenario: A secret overrides
- **WHEN** the outside folder gives `GH_TOKEN` and project `shop` has the secret `GH_TOKEN`
- **THEN** `lado doctor` prints `[info] Project variables: shop overrides GH_TOKEN of
  LADO_ENV_DIR`
