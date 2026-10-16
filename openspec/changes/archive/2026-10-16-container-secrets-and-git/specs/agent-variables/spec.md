## ADDED Requirements

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
- With `LADO_ENV_DIR` unset or empty, or with no folder at its path, an agent's
  environment SHALL be what it is without this requirement.

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
`variable file <name> in <folder> not used: <reason>`, and by `lado doctor`. A folder that
LADO_ENV_DIR names but that is not a folder or cannot be listed SHALL be named the same
way, and the launch SHALL go on with the login shell's environment.

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

### Requirement: A name LADO sets keeps LADO's value

When a file of the outside folder has a name that LADO or the agent's provider sets for
that launch (`LADO_*` is refused by name; the provider's own variables, such as Claude
Code's or OpenCode's config variables), the launch SHALL keep LADO's or the provider's
value and SHALL say so in its warnings (a start's or resume's, `spawn_worker`'s result),
`variable file <name> in <folder> not used: LADO sets <name> for <provider>`, once per
launch.

#### Scenario: A provider's variable
- **WHEN** the folder holds a file named after a variable the agent's provider sets for
  its launch
- **THEN** the agent has the provider's value, and the start's warnings name the file

### Requirement: lado doctor checks the outside folder

While `LADO_ENV_DIR` is set and not empty, `lado doctor` SHALL print one check `Variables
from outside`:
- `[ok  ]` with the folder and the names it gives (never a value), or `none` for an empty
  folder;
- `[info]` for a path with no folder;
- `[warn]` naming each file that is not applied and why, a path that is not absolute, or
  a folder that cannot be listed.

The bug report (`doctor.report`) SHALL hold at most the number of variables, never a name
or a value.

#### Scenario: Two variables and a bad file
- **WHEN** the folder holds `GH_TOKEN`, `YOUGILE_API_KEY` and `a-b`
- **THEN** `lado doctor` prints `[warn] Variables from outside: <folder>: GH_TOKEN,
  YOUGILE_API_KEY; a-b not used: not a variable name`, and its exit code stays 0

### Requirement: The outside folder's values stay out of LADO's records

LADO SHALL write no value of the outside folder anywhere but the agent's launch file
(`env.json` in its config folder, mode 600, removed once read), as it does for every
variable today. That excludes `hooks.log`, `loop.log`, `errors.jsonl`, `server.log`,
`lado log`, `lado.db`, the API, the change feed, the bug report and telemetry. Errors
about a file SHALL name the file, never its content.

#### Scenario: A canary value
- **WHEN** the folder holds `CANARY` with a unique value, a session starts, a worker is
  spawned, a file of the folder is refused, and `lado doctor` and `lado bug-report` run
- **THEN** the value appears in none of LADO_HOME's logs, `lado.db`, `lado log`, the
  doctor's and the bug report's output, or the API's answers
