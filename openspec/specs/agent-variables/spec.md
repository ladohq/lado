# agent-variables Specification

## Purpose
Variables an agent gets from outside its login shell: the folder `LADO_ENV_DIR` names
(LADO's image: `/run/secrets`), one regular file per variable, laid over the login
shell's environment at each launch and passed on to the agents an agent launches, with
each file LADO does not use named with why and no value anywhere in LADO's records.

## Requirements

### Requirement: Agents get the variables of the outside folder

When the process that launches an agent has `LADO_ENV_DIR` set to an absolute path,
LADO SHALL, for each agent it launches (a session's start, a resume, `spawn_worker`, a
run's worker), read that folder anew and lay its variables over the environment that
`agent_env.resolve` gives (the login shell's, or the starting process's with
`LADO_AGENT_ENV=inherit`).

#### Scenario: A new file reaches the next agent
- **WHEN** a session runs and the human adds a file `NEW_KEY` to the folder, then a worker
  is spawned
- **THEN** the worker has `NEW_KEY` and the agents started before do not

### Requirement: Each file of the outside folder is one variable

Each regular file directly in the folder SHALL be one variable: its name is the variable's
name and its content the value, with one trailing `\n` (or `\r\n`) dropped.

#### Scenario: A variable from the folder
- **WHEN** `LADO_ENV_DIR` names a folder holding a file `YOUGILE_API_KEY` with the content
  `k-123\n`, and a session starts
- **THEN** its supervisor's process has `YOUGILE_API_KEY=k-123`

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

### Requirement: Without an outside folder an agent's environment is as before

With `LADO_ENV_DIR` unset or empty, with no folder at its path, or with the null device
at its path (the character device `/dev/null` is, which compose's default binds there),
an agent's environment SHALL be what it is without the outside folder, and no line SHALL
name the folder.

#### Scenario: No folder
- **WHEN** `LADO_ENV_DIR` is unset
- **THEN** an agent's environment is the login shell's with, in a session in a project,
  the project's variables, then LADO's and its provider's variables, as before

#### Scenario: The null device
- **WHEN** `LADO_ENV_DIR` names `/dev/null` (or a path where the null device is mounted)
  and a session starts
- **THEN** the agents' environment is the login shell's with, in a session in a project,
  the project's variables, then LADO's and its provider's variables, and the start's
  warnings have no line about the folder

### Requirement: A file the outside folder cannot give is named, never applied

LADO SHALL NOT apply a file of the `LADO_ENV_DIR` folder in any of these cases:
- it is not a regular file, or lies in a subfolder;
- its name starts with `.`;
- its name is not a variable name (`[A-Za-z_][A-Za-z0-9_]*`);
- its name is reserved: `HOME`, `USER`, `LOGNAME`, `SHELL`, `PATH`, `PWD`, `OLDPWD`,
  `SHLVL`, `_`, `TERM`, `TERM_PROGRAM`, `TERM_PROGRAM_VERSION`, `TMUX`, `TMUX_PANE`, or
  any name starting with `LADO_`.

#### Scenario: Not a variable name
- **WHEN** the folder holds `gh-token.txt` and `.hidden`
- **THEN** neither is applied, `lado doctor` warns about `gh-token.txt` with `not a variable
  name`, and `.hidden` is passed over without a warning

### Requirement: A file of the outside folder that is not a short text is not applied

LADO SHALL NOT apply a file of the `LADO_ENV_DIR` folder in any of these cases either:
- it cannot be read;
- it is larger than 64 KiB;
- its content is not UTF-8 text or holds a NUL character.

#### Scenario: Too large or not text
- **WHEN** the folder holds `BIG` of 70 000 bytes and `BIN` with a NUL byte
- **THEN** neither is applied, and each is named with its reason

### Requirement: A file not applied is named with its reason

Each file of the outside folder that is not applied SHALL be named with its reason, never with its content, in the warnings of
a session's start and resume (`lado start` on stderr, the UI's `Started.warnings`), as
`variable file <name> in <folder> not used: <reason>`, and by `lado doctor`.

#### Scenario: A reserved name
- **WHEN** the folder holds a file `PATH`
- **THEN** agents keep the login shell's `PATH`, and `lado start` prints `variable file PATH
  in <folder> not used: a reserved name`

### Requirement: A LADO_ENV_DIR that is no folder is named and the launch goes on

A path that
LADO_ENV_DIR names that is neither a folder nor the null device (a regular file, another
device), or a folder that cannot be listed, SHALL be named the same way, inside a
container or out, and the launch SHALL go on with the login shell's environment.

#### Scenario: A regular file instead of a folder
- **WHEN** `LADO_ENV_DIR` names a regular file and a session starts
- **THEN** `lado start` prints `variable folder <path> (LADO_ENV_DIR) not used: not a
  folder`, and `lado doctor` warns with the same words

### Requirement: A name LADO sets keeps LADO's value

When a file of the outside folder, or a variable of the session's project, has a name that
LADO or the agent's provider sets for that launch (such as a provider's config variable),
the launch SHALL keep LADO's or the provider's value and SHALL name the file or the
variable once in that launch's warnings (a start's, a resume's or `spawn_worker`'s).

#### Scenario: A provider's variable
- **WHEN** the folder holds a file named after a variable the agent's provider sets for
  its launch
- **THEN** the agent has the provider's value, and the start's warnings say `variable file
  <name> in <folder> not used: LADO sets <name> for <provider>`

#### Scenario: A project's variable stored under a name now reserved
- **WHEN** project `shop` holds in `lado.db` a variable named after a variable the agent's
  provider sets for its launch, and a session of `shop` starts
- **THEN** the agent has the provider's value, and the start's warnings say `project
  variable <name> of shop not used: LADO sets <name> for <provider>`

### Requirement: lado doctor checks the outside folder

While `LADO_ENV_DIR` is set and not empty, `lado doctor` SHALL print one check `Variables
from outside`:
- `[ok  ]` with the folder and the names it gives (never a value), or `none` for an empty
  folder;
- `[warn]` naming each file that is not applied and why, a path that is not absolute, a
  path that is neither a folder nor the null device, or a folder that cannot be listed.

#### Scenario: Two variables and a bad file
- **WHEN** the folder holds `GH_TOKEN`, `YOUGILE_API_KEY` and `a-b`
- **THEN** `lado doctor` prints `[warn] Variables from outside: <folder>: GH_TOKEN,
  YOUGILE_API_KEY; a-b not used: not a variable name`, and its exit code stays 0

### Requirement: lado doctor informs of an outside folder that is not there

The check `Variables from outside` of `lado doctor` SHALL be:
- `[info]` for a path with no folder or with the null device: outside a container
  `<folder>: no folder`; in a container (`LADO_CONTAINER`) `<folder>: none` with the hint
  `to give the agents variables: LADO_SECRETS=./secrets in compose's .env and mkdir -m 700
  secrets (docker run: -v <folder>:/run/secrets:ro); docs/install.md#the-agents-variables`.

#### Scenario: No secrets in a container
- **WHEN** `LADO_CONTAINER=1` and `LADO_ENV_DIR` names the null device, or a path with
  nothing at it
- **THEN** `lado doctor` prints `[info] Variables from outside: <folder>: none` with the
  hint naming `LADO_SECRETS=./secrets`, and its exit code stays 0

#### Scenario: The null device outside a container
- **WHEN** `LADO_CONTAINER` is unset and `LADO_ENV_DIR` names `/dev/null`
- **THEN** `lado doctor` prints `[info] Variables from outside: /dev/null: no folder` with
  no hint

### Requirement: The bug report counts the outside variables, never names them

The bug report (`doctor.report`) SHALL hold at most the number of variables, never a name
or a value.

#### Scenario: Two variables in the bug report
- **WHEN** the folder holds `GH_TOKEN` and `YOUGILE_API_KEY` and the human runs
  `lado bug-report`
- **THEN** the report names neither `GH_TOKEN` nor `YOUGILE_API_KEY` nor their values

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
starting process's with `LADO_AGENT_ENV=inherit`), the outside folder's, LADO's secrets
(`<LADO_HOME>/secrets/`, the agent CLIs' login variables set in the UI), the project's,
LADO's and the provider's.

#### Scenario: The order of the layers
- **WHEN** the login shell exports `BOARD_URL=shell`, the outside folder has `BOARD_URL`
  with `out`, and project `shop` has `BOARD_URL=proj`
- **THEN** an agent of a session in `shop` has `BOARD_URL=proj`, with any of the four
  providers

#### Scenario: LADO's secrets between the outside folder and the project
- **WHEN** the outside folder has `CLAUDE_CODE_OAUTH_TOKEN` with `out`, LADO's secrets have
  it with `lado`, and project `shop` has the secret with `proj`
- **THEN** an agent of a session without a project has `lado`, and an agent of a session in
  `shop` has `proj`

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

### Requirement: LADO's own git calls get the outside folder's variables

LADO's network git calls (a kit's or skill pack's tags and pinned clone, a marketplace's
clone and update, the listing of a URL's branches and its clone, from the CLI and from the
UI server) SHALL run with the outside folder's variables over LADO's process environment,
read anew at each call by the outside folder's reader, with the same files not used. They
SHALL NOT take the login shell's environment. LADO's local git calls are unchanged.

#### Scenario: The server's clone gets the outside folder's GH_TOKEN
- **WHEN** LADO's image runs with `GH_TOKEN` only in `/run/secrets`, and the New session
  window lists the branches of `https://github.com/acme/private` and clones it
- **THEN** git's credential helper of github.com gets that token for the listing and the
  clone, and neither asks for a login

#### Scenario: A kit added through the server
- **WHEN** the same server adds the kit `https://github.com/ladohq/kit-epic.git` from the
  Kits page
- **THEN** its tags are read and its clone is made with the folder's `GH_TOKEN`

#### Scenario: A file added after the server started
- **WHEN** the server runs, and the human then adds `GH_TOKEN` to the outside folder
- **THEN** the next listing, clone or kit add uses it, with no restart

### Requirement: A clone into a project gets the project's variables and secrets

A listing or clone of a URL into a project (`lado project repo add`, the project page's
Add repository and its branch list) SHALL run with the project's plain variables and
secrets, read anew at the call, over the outside folder's variables, in the agents'
order: LADO's process environment → the outside folder → the project's. A listing or
clone without a project SHALL get no project's variable.

#### Scenario: A project's own token
- **WHEN** project `shop` has the secret `GH_TOKEN=a`, the outside folder has `GH_TOKEN`
  with `out`, and the human adds `https://github.com/acme/private` on `shop`'s page
- **THEN** the branch list and the clone use `a`

#### Scenario: Another project's token is not used
- **WHEN** project `acme` has the secret `GH_TOKEN`, and a clone without a project runs
  from New session → Clone
- **THEN** git gets no `GH_TOKEN` from `acme`

### Requirement: The server lists a remote's branches for a project

The server's branch listing (`POST /api/remote-branches`) SHALL take an optional
`project` and list in that project's layer; the project page's Add repository SHALL send
its project, and New session → Clone none. An unknown project SHALL be refused as the
project routes refuse it.

#### Scenario: The project page asks with its project
- **WHEN** the human types a URL in Add repository on `shop`'s page
- **THEN** the window posts `{url, project: "shop"}` to `/api/remote-branches`

#### Scenario: An unknown project
- **WHEN** `/api/remote-branches` is posted with `project: "nope"` and no such project
- **THEN** the answer is the project routes' refusal of an unknown project, and git did
  not run

### Requirement: One core function builds the environment of LADO's own git calls

One core function SHALL build the environment of every network git call of LADO, and the
project's layer (its plain variables with its secrets over them) SHALL be built by one
function that both the agents' environment and LADO's git calls use.

#### Scenario: The order of the layers
- **WHEN** LADO's process has `BOARD_URL=proc`, the outside folder has `BOARD_URL` with
  `out`, and project `shop` has `BOARD_URL=proj`
- **THEN** a git call of a clone into `shop` has `BOARD_URL=proj`, one without a project
  has `out`, and LADO's `no prompt` variables are over all of them

### Requirement: An agent's login comes whole from one layer

Of the login shell's, the outside folder's, LADO's secrets' and the project's layers, the
highest that sets any of the agent's provider's login variables SHALL give all of them,
and the provider's login variables of the lower layers SHALL NOT reach the agent. A
variable that is no login variable of the agent's provider SHALL be laid name by name.

#### Scenario: A login comes whole from the highest layer that sets one
- **WHEN** the login shell exports `ANTHROPIC_API_KEY`, the outside folder has
  `CLAUDE_CODE_OAUTH_TOKEN` with `out`, and project `shop` has `ANTHROPIC_API_KEY` with
  `proj`
- **THEN** a Claude agent of a session without a project has `CLAUDE_CODE_OAUTH_TOKEN=out`
  and no `ANTHROPIC_API_KEY`, and one of a session in `shop` has `ANTHROPIC_API_KEY=proj`
  and no `CLAUDE_CODE_OAUTH_TOKEN`

#### Scenario: Other providers keep the variables
- **WHEN** LADO's secrets have `CLAUDE_CODE_OAUTH_TOKEN` and the login shell exports
  `ANTHROPIC_API_KEY`
- **THEN** an OpenCode agent has `ANTHROPIC_API_KEY`, which is no login variable of its
  provider
