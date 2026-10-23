## ADDED Requirements

### Requirement: A project keeps plain variables in lado.db

LADO SHALL keep a project's plain variables in `lado.db`, one name and one value each, a
name at most once per project; deleting the project (`lado project delete --yes`, or its
record otherwise) SHALL remove its variables with it.

#### Scenario: Deleted with the project
- **WHEN** project `shop` has `BOARD_URL`, the human runs `lado project delete shop --yes`
  and then `lado project create shop`
- **THEN** `lado project show shop` prints `  variables: none`

### Requirement: lado project set sets a plain variable

`lado project set <id> NAME VALUE` SHALL store `VALUE` as the project's variable `NAME`,
over the old value when there is one, and print `Set <NAME> in project <id>.` and then
`Agents started from now on get it; running sessions of <id> keep the old environment
until restarted: <names>`, or `Agents started from now on get it.` when no session of the
project runs (a session runs when it is not stopped).

#### Scenario: Set while a session runs
- **WHEN** session `shop-frontend` of project `shop` runs and the human runs `lado project
  set shop BOARD_URL https://a`
- **THEN** it prints `Set BOARD_URL in project shop.` and `Agents started from now on get
  it; running sessions of shop keep the old environment until restarted: shop-frontend`

#### Scenario: Set again
- **WHEN** `shop` has `BOARD_URL=https://a` and the human runs `lado project set shop
  BOARD_URL https://b`
- **THEN** `lado project show shop` lists `BOARD_URL  https://b`

### Requirement: A project variable's value is a short text

A project variable's value SHALL be at most 64 KiB of UTF-8 text without NUL, else the
command exits 1 with `lado: the value of <NAME> is <why>` and stores nothing. An empty
value SHALL be a value.

#### Scenario: Too large
- **WHEN** the human sets a value of 70 000 bytes
- **THEN** it exits 1 with `lado: the value of <NAME> is larger than 64 KiB`, and nothing
  is stored

### Requirement: lado project unset removes a plain variable

`lado project unset <id> NAME` SHALL remove the project's variable `NAME` and print
`Removed <NAME> from project <id>.` and the same line about the agents and the running
sessions as `set`. A name the project lacks SHALL exit 1 with `lado: project <id> has no
variable <NAME>; its variables: <names>` (`none` without any).

#### Scenario: Unset
- **WHEN** `shop` has `BOARD_URL` and no session of it runs, and the human runs `lado
  project unset shop BOARD_URL`
- **THEN** it prints `Removed BOARD_URL from project shop.` and `Agents started from now
  on get it.`, and `lado project show shop` prints `  variables: none`

#### Scenario: A name the project lacks
- **WHEN** `shop` has only `BOARD_URL` and the human runs `lado project unset shop MODEL_URL`
- **THEN** it exits 1 with `lado: project shop has no variable MODEL_URL; its variables:
  BOARD_URL`

### Requirement: A project variable's name is checked by one rule

LADO SHALL check a project variable's name by one rule in the core, for the CLI and the
server alike, and refuse a name that is no variable name (`[A-Za-z_][A-Za-z0-9_]*`) with
`the name <NAME> is not a variable name: Latin letters, digits and _, not starting with a
digit`, storing nothing.

#### Scenario: No variable name
- **WHEN** the human runs `lado project set shop A-B x`
- **THEN** it exits 1 with `lado: the name A-B is not a variable name: …`

### Requirement: A reserved name is no project variable

The rule SHALL refuse a reserved name with `<NAME> is reserved: LADO or the agent CLIs set
it`: each name the outside folder reserves (see `agent-variables`), any name starting
with `LADO_`, and each name LADO sets for an agent CLI (`CLAUDE_CONFIG_DIR`,
`CODEX_HOME`, the `OPENCODE_*` and `KILO_*` names of their launches).

#### Scenario: The shell's name
- **WHEN** the human runs `lado project set shop PATH /tmp`
- **THEN** it exits 1 with `lado: PATH is reserved: LADO or the agent CLIs set it`

#### Scenario: A reserved name
- **WHEN** the human runs `lado project set shop CLAUDE_CONFIG_DIR /tmp/c`
- **THEN** it exits 1 with `lado: CLAUDE_CONFIG_DIR is reserved: LADO or the agent CLIs set it`

#### Scenario: A provider's config
- **WHEN** the human runs `lado project set shop CODEX_HOME /tmp/c` or `OPENCODE_CONFIG_CONTENT {}`
- **THEN** it exits 1 naming the name as reserved

#### Scenario: LADO's own
- **WHEN** the human runs `lado project set shop LADO_HOME /tmp/h`
- **THEN** it exits 1 naming `LADO_HOME` as reserved

### Requirement: Every name a provider sets is reserved

Every name a provider sets in the environment of its agent's launch SHALL be in the
reserved list of project variables.

#### Scenario: A provider's launch
- **WHEN** any of the four providers builds an agent's launch
- **THEN** each name of its launch environment is refused as a project variable

### Requirement: A name that looks like a secret is no plain variable

The rule SHALL refuse a name with `TOKEN`, `KEY`, `SECRET` or `PASSWORD` in it, in any
case, with `<NAME> looks like a secret (<word>): a plain variable takes no name with
TOKEN, KEY, SECRET or PASSWORD; secrets come with lado project set <id> <NAME> --secret
(not built yet)`.

#### Scenario: A secret's name
- **WHEN** the human runs `lado project set shop GH_TOKEN x`
- **THEN** it exits 1 with `lado: GH_TOKEN looks like a secret (TOKEN): …` and `shop` has no
  `GH_TOKEN`

#### Scenario: Lowercase is a secret's name too
- **WHEN** the human runs `lado project set shop yougile_api_key x`
- **THEN** it exits 1 naming `KEY`

### Requirement: lado project show lists the project's variables

`lado project show <id>` SHALL print, after the repositories, `  variables:` and one line
per variable, by name: `    <NAME>  <value>`, the names padded to one width; with none,
`  variables: none`. A value SHALL be shown on one line, each line break in it shown as
`\n`.

#### Scenario: Two variables
- **WHEN** `shop` has `MODEL_URL=http://localhost:11434` and `BOARD_URL=https://a`
- **THEN** `lado project show shop` ends with `  variables:`, `    BOARD_URL  https://a` and
  `    MODEL_URL  http://localhost:11434`

### Requirement: The server sets and removes a project's variables

`PUT /api/projects/{id}/variables/{name}` with `{value}` SHALL set a variable and `DELETE
/api/projects/{id}/variables/{name}` remove one, both with the token for changes
(`guard.changes`), by the same rules as the CLI, answering `{project, running}`: the
project as `GET /api/projects/{id}` gives it after the change and the names of its
sessions that run.

#### Scenario: Set through the API
- **WHEN** the UI sends `PUT /api/projects/shop/variables/BOARD_URL` with `{"value":
  "https://a"}` while `shop-frontend` runs
- **THEN** the answer's `project.variables` has `{name: "BOARD_URL", value: "https://a"}`
  and `running` is `["shop-frontend"]`

### Requirement: The server refuses a variable as the CLI does

An unknown project SHALL be 404, an unknown variable on `DELETE` 404, and a refused name
or value 400 with the refusal's text, nothing stored.

#### Scenario: A secret's name through the API
- **WHEN** the UI sends `PUT /api/projects/shop/variables/GH_TOKEN`
- **THEN** the answer is 400 with `GH_TOKEN looks like a secret (TOKEN): …` and nothing is
  stored

#### Scenario: An unknown project
- **WHEN** the UI sends `DELETE /api/projects/nope/variables/BOARD_URL`
- **THEN** the answer is 404

## MODIFIED Requirements

### Requirement: lado project show lists the project's repositories

`lado project show <id>` SHALL print, after its `made:` line, `  repositories:` and one
line per repository, by name: `    <name>  <branch>  <remote>`, the names and branches
padded to one width, `(detached)` for no branch and `(no remote)` for no remote; with
none, `  repositories: none`. A symbolic link in the project's folder SHALL be listed
among them by name, marked `(a link to <target>: clone it into <folder> instead)`. The
project's variables follow.

#### Scenario: Two repositories
- **WHEN** the project `shop` has `frontend` (branch `main`, remote
  `https://github.com/shop/frontend`) and `backend` (branch `dev`, no remote)
- **THEN** `lado project show shop` prints `  repositories:`, `    backend   dev
  (no remote)` and `    frontend  main  https://github.com/shop/frontend`, then its
  variables

#### Scenario: A link in the project's folder
- **WHEN** `<ws>/projects/shop/docs` is a symbolic link to `/srv/docs`
- **THEN** `lado project show shop` lists `    docs      (a link to /srv/docs: clone it into
  <ws>/projects/shop instead)` between `backend` and `frontend`

#### Scenario: A project whose folder is gone
- **WHEN** the folder of `acme` is gone and the human runs `lado project show acme`
- **THEN** it prints `  folder:  <ws>/projects/acme  (folder not found)` and
  `  repositories: none`

### Requirement: Agents cannot change projects

`lado project create`, `rename`, `delete`, `set`, `unset`, `repo add` and `repo remove`
SHALL refuse, exit 1 with `lado: lado project <command> is for the human; agent "<agent>"
cannot use it` and change nothing, when `LADO_AGENT` is set (every agent of LADO has it).
`list` and `show` SHALL work for agents. LADO SHALL offer no MCP tool that makes, changes
or deletes a project, its repositories or its variables.

#### Scenario: From an agent
- **WHEN** a worker runs `lado project create shop` in its shell
- **THEN** it exits 1 with that text, and no project or folder is made

#### Scenario: Adding a repository from an agent
- **WHEN** a worker runs `lado project repo add shop --new site` in its shell
- **THEN** it exits 1 with `lado: lado project repo add is for the human; agent
  "<agent>" cannot use it`, and no folder `site` is made

#### Scenario: Setting a variable from an agent
- **WHEN** a worker runs `lado project set shop MODEL_URL http://evil` in its shell
- **THEN** it exits 1 with `lado: lado project set is for the human; agent "<agent>"
  cannot use it`, and `shop` keeps its variables as they were

### Requirement: The server gives a project with its repositories

`GET /api/projects/{id}` SHALL answer `{id, title, folder, found, repos, variables}`,
`repos` the project's repositories as `{name, path, remote, branch}`, `variables` its
variables as `{name, value}` by name, and 404 for an unknown id.

#### Scenario: A project
- **WHEN** the UI asks `GET /api/projects/shop`
- **THEN** the answer has `id: "shop"`, its title, its folder, `found: true`, its
  repositories as `lado project show` lists them and its variables
