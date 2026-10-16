## MODIFIED Requirements

### Requirement: Agents get the variables of the outside folder

When the process that launches an agent has `LADO_ENV_DIR` set to an absolute path,
LADO SHALL, for each agent it launches (a session's start, a resume, `spawn_worker`, a
run's worker), read that folder anew and lay its variables over the environment that
`agent_env.resolve` gives (the login shell's, or the starting process's with
`LADO_AGENT_ENV=inherit`).
- Each regular file directly in the folder is one variable: its name is the variable's
  name and its content the value, with one trailing `\n` (or `\r\n`) dropped.
- A value of the folder SHALL win over the same name from the login shell, and LADO's
  own variables and the agent's provider's SHALL win over the folder's (see "A name LADO
  sets keeps LADO's value").
- The kits' checks of an agent's environment (an MCP server's `${NAME}`, `expects`) SHALL
  see the folder's variables as the agent gets them.
- With `LADO_ENV_DIR` unset or empty, with no folder at its path, or with the null device
  at its path (the character device `/dev/null` is, which compose's default binds there),
  an agent's environment SHALL be what it is without this requirement, and no line SHALL
  name the folder.

#### Scenario: A variable from the folder
- **WHEN** `LADO_ENV_DIR` names a folder holding a file `YOUGILE_API_KEY` with the content
  `k-123\n`, and a session starts
- **THEN** its supervisor's process has `YOUGILE_API_KEY=k-123`

#### Scenario: Over the login shell
- **WHEN** the login shell exports `GH_TOKEN=old` and the folder has `GH_TOKEN` with `new`
- **THEN** an agent launched after that has `GH_TOKEN=new`

#### Scenario: A new file reaches the next agent
- **WHEN** a session runs and the human adds a file `NEW_KEY` to the folder, then a worker
  is spawned
- **THEN** the worker has `NEW_KEY` and the agents started before do not

#### Scenario: A kit's MCP server needs the variable
- **WHEN** a kit's MCP server has `env: {API_KEY: ${YOUGILE_API_KEY}}`, the login shell
  has no `YOUGILE_API_KEY`, and the folder has it
- **THEN** the session starts, where without the file it is refused with the kit's error
  naming `YOUGILE_API_KEY`

#### Scenario: No folder
- **WHEN** `LADO_ENV_DIR` is unset
- **THEN** an agent's environment is the login shell's with LADO's and its provider's
  variables, as before

#### Scenario: The null device
- **WHEN** `LADO_ENV_DIR` names `/dev/null` (or a path where the null device is mounted)
  and a session starts
- **THEN** the agents' environment is the login shell's with LADO's and its provider's
  variables, and the start's warnings have no line about the folder

### Requirement: A file the outside folder cannot give is named, never applied

LADO SHALL NOT apply a file of the `LADO_ENV_DIR` folder in any of these cases:
- it is not a regular file, or lies in a subfolder;
- its name starts with `.`;
- its name is not a variable name (`[A-Za-z_][A-Za-z0-9_]*`);
- its name is reserved: `HOME`, `USER`, `LOGNAME`, `SHELL`, `PATH`, `PWD`, `OLDPWD`,
  `SHLVL`, `_`, `TERM`, `TERM_PROGRAM`, `TERM_PROGRAM_VERSION`, `TMUX`, `TMUX_PANE`, or
  any name starting with `LADO_`;
- it cannot be read;
- it is larger than 64 KiB;
- its content is not UTF-8 text or holds a NUL character.

Each such file SHALL be named with its reason, never with its content, in the warnings of
a session's start and resume (`lado start` on stderr, the UI's `Started.warnings`), as
`variable file <name> in <folder> not used: <reason>`, and by `lado doctor`. A path that
LADO_ENV_DIR names that is neither a folder nor the null device (a regular file, another
device), or a folder that cannot be listed, SHALL be named the same way, inside a
container or out, and the launch SHALL go on with the login shell's environment.

#### Scenario: A reserved name
- **WHEN** the folder holds a file `PATH`
- **THEN** agents keep the login shell's `PATH`, and `lado start` prints `variable file PATH
  in <folder> not used: a reserved name`

#### Scenario: Not a variable name
- **WHEN** the folder holds `gh-token.txt` and `.hidden`
- **THEN** neither is applied, `lado doctor` warns about `gh-token.txt` with `not a variable
  name`, and `.hidden` is passed over without a warning

#### Scenario: Too large or not text
- **WHEN** the folder holds `BIG` of 70 000 bytes and `BIN` with a NUL byte
- **THEN** neither is applied, and each is named with its reason

#### Scenario: A regular file instead of a folder
- **WHEN** `LADO_ENV_DIR` names a regular file and a session starts
- **THEN** `lado start` prints `variable folder <path> (LADO_ENV_DIR) not used: not a
  folder`, and `lado doctor` warns with the same words

### Requirement: lado doctor checks the outside folder

While `LADO_ENV_DIR` is set and not empty, `lado doctor` SHALL print one check `Variables
from outside`:
- `[ok  ]` with the folder and the names it gives (never a value), or `none` for an empty
  folder;
- `[info]` for a path with no folder or with the null device: outside a container
  `<folder>: no folder`; in a container (`LADO_CONTAINER`) `<folder>: none` with the hint
  `to give the agents variables: LADO_SECRETS=./secrets in compose's .env and mkdir -m 700
  secrets (docker run: -v <folder>:/run/secrets:ro); docs/install.md#the-agents-variables`;
- `[warn]` naming each file that is not applied and why, a path that is not absolute, a
  path that is neither a folder nor the null device, or a folder that cannot be listed.

The bug report (`doctor.report`) SHALL hold at most the number of variables, never a name
or a value.

#### Scenario: Two variables and a bad file
- **WHEN** the folder holds `GH_TOKEN`, `YOUGILE_API_KEY` and `a-b`
- **THEN** `lado doctor` prints `[warn] Variables from outside: <folder>: GH_TOKEN,
  YOUGILE_API_KEY; a-b not used: not a variable name`, and its exit code stays 0

#### Scenario: No secrets in a container
- **WHEN** `LADO_CONTAINER=1` and `LADO_ENV_DIR` names the null device, or a path with
  nothing at it
- **THEN** `lado doctor` prints `[info] Variables from outside: <folder>: none` with the
  hint naming `LADO_SECRETS=./secrets`, and its exit code stays 0

#### Scenario: The null device outside a container
- **WHEN** `LADO_CONTAINER` is unset and `LADO_ENV_DIR` names `/dev/null`
- **THEN** `lado doctor` prints `[info] Variables from outside: /dev/null: no folder` with
  no hint
