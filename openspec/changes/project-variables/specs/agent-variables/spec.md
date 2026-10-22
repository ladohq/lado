## ADDED Requirements

### Requirement: The agents of a session in a project get the project's variables

LADO SHALL, for each agent it launches in a session that is in a project (its
supervisor at a start and a resume, `spawn_worker`, a flow run's worker, and the
supervisor of a session `start_session` starts from it), read the project's variables
from `lado.db` anew and give them to the agent.

#### Scenario: Two projects, one name
- **WHEN** project `shop` has `BOARD_URL=https://a` and `acme` has `BOARD_URL=https://b`,
  and a session runs in each
- **THEN** in `shop` the supervisor, a worker, a flow run's worker and the supervisor of
  the session it starts with `start_session` have `BOARD_URL=https://a`, and every agent
  of `acme` has `https://b`

#### Scenario: A resume reads the variables anew
- **WHEN** session `shop-frontend` is stopped, the human sets `MODEL_URL` in `shop`, and
  the session is resumed
- **THEN** its supervisor has `MODEL_URL`

### Requirement: One core function lays the project's layer for every provider

One core function SHALL build every agent's environment, for every provider, with
Docker and without, each later layer over the one before: the login shell's (or the
starting process's with `LADO_AGENT_ENV=inherit`), the outside folder's, the project's,
LADO's and the provider's.

#### Scenario: The order of the layers
- **WHEN** the login shell exports `BOARD_URL=shell`, the outside folder has `BOARD_URL`
  with `out`, and project `shop` has `BOARD_URL=proj`
- **THEN** an agent of a session in `shop` has `BOARD_URL=proj`, with any of the four
  providers

### Requirement: A session without a project gets no project's variables

A session without a project SHALL get no variable of any project.

#### Scenario: No project
- **WHEN** project `shop` has `BOARD_URL` and a session without a project starts
- **THEN** its agents have no `BOARD_URL` from it

### Requirement: The project's value wins over the outside folder's

A project's variable SHALL win over the same name from the login shell and from the
outside folder.

#### Scenario: Over the outside folder
- **WHEN** the outside folder has `BOARD_URL` with `https://out` and project `shop` has
  `BOARD_URL=https://a`
- **THEN** an agent of a session in `shop` has `https://a`, and an agent of a session
  without a project has `https://out`

### Requirement: A changed project variable reaches the agents started after it

A project variable set or removed SHALL reach each agent launched after the change, and
SHALL NOT change the environment of an agent that runs.

#### Scenario: Unset
- **WHEN** a session of `shop` runs with `BOARD_URL=https://a` in its supervisor, the human
  runs `lado project unset shop BOARD_URL`, then a worker is spawned
- **THEN** the worker has no `BOARD_URL` from the project, and the supervisor still has
  `https://a`

### Requirement: lado doctor names the project variables that override the outside folder

While a project's variable has the name of a variable the outside folder gives, `lado
doctor` SHALL print one check `[info] Project variables: <id> overrides <NAME>[, <NAME>…]
of LADO_ENV_DIR`, the projects joined by `; `, by id, never a value; with no such name it
SHALL print no such line. The bug report SHALL hold no project variable's name or value.

#### Scenario: An override
- **WHEN** the outside folder gives `BOARD_URL` and `GH_TOKEN`, and project `shop` has
  `BOARD_URL`
- **THEN** `lado doctor` prints `[info] Project variables: shop overrides BOARD_URL of
  LADO_ENV_DIR`, and its exit code stays 0

#### Scenario: No override
- **WHEN** no project variable has a name the outside folder gives
- **THEN** `lado doctor` prints no `Project variables` line

## MODIFIED Requirements

### Requirement: The outside folder's value wins over the login shell's

A value of the folder SHALL win over the same name from the login shell, a project's
variable SHALL win over the folder's (see "The project's value wins over the outside
folder's"), and LADO's own variables and the agent's provider's SHALL win over both (see
"A name LADO sets keeps LADO's value").

#### Scenario: Over the login shell
- **WHEN** the login shell exports `GH_TOKEN=old` and the folder has `GH_TOKEN` with `new`
- **THEN** an agent launched after that has `GH_TOKEN=new`

### Requirement: The kits' checks see the outside folder's variables

The kits' checks of an agent's environment (an MCP server's `${NAME}`, `expects`) SHALL
see the folder's variables and the variables of the session's project as the agent gets
them, and a kit's MCP server SHALL get the value through `lado.mcp_exec` from the
agent's environment.

#### Scenario: A kit's MCP server needs the variable
- **WHEN** a kit's MCP server has `env: {API_KEY: ${YOUGILE_API_KEY}}`, the login shell
  has no `YOUGILE_API_KEY`, and the folder has it
- **THEN** the session starts, where without the file it is refused with the kit's error
  naming `YOUGILE_API_KEY`

#### Scenario: A kit's key set only in the project
- **WHEN** a kit's MCP server has `env: {URL: ${BOARD_URL}}`, neither the login shell nor
  the folder has `BOARD_URL`, and project `shop` has `BOARD_URL=https://a`
- **THEN** a session in `shop` starts and the server's process has `URL=https://a`, and a
  session without a project is refused with the kit's error naming `BOARD_URL`

### Requirement: A name LADO sets keeps LADO's value

When a file of the outside folder, or a variable of the session's project, has a name that
LADO or the agent's provider sets for that launch (`LADO_*` is refused by name; the
provider's own variables, such as Claude Code's or OpenCode's config variables), the
launch SHALL keep LADO's or the provider's value and SHALL say so in its warnings (a
start's or resume's, `spawn_worker`'s result), `variable file <name> in <folder> not
used: LADO sets <name> for <provider>` for a file and `project variable <name> of <id>
not used: LADO sets <name> for <provider>` for a project's variable, once per launch.

#### Scenario: A provider's variable
- **WHEN** the folder holds a file named after a variable the agent's provider sets for
  its launch
- **THEN** the agent has the provider's value, and the start's warnings name the file

#### Scenario: A project's variable stored under a name now reserved
- **WHEN** project `shop` holds in `lado.db` a variable named after a variable the agent's
  provider sets for its launch, and a session of `shop` starts
- **THEN** the agent has the provider's value, and the start's warnings say `project
  variable <name> of shop not used: LADO sets <name> for <provider>`
