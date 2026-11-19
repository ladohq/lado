## MODIFIED Requirements

### Requirement: The outside folder's value wins over the login shell's

A value of the folder SHALL win over the same name from the login shell, a project's
variable SHALL win over the folder's (see "The project's value wins over the outside
folder's"), and LADO's own variables and the agent's provider's SHALL win over both (see
"A name LADO sets keeps LADO's value"). GitHub's variables come from no layer (capability
`git-servers`).

#### Scenario: Over the login shell
- **WHEN** the login shell exports `YOUGILE_API_KEY=old` and the folder has
  `YOUGILE_API_KEY` with `new`
- **THEN** an agent launched after that has `YOUGILE_API_KEY=new`

#### Scenario: GitHub's token from no layer
- **WHEN** the login shell exports `GH_TOKEN=old` and the folder has `GH_TOKEN` with `new`
- **THEN** an agent has neither value of `GH_TOKEN`

### Requirement: lado doctor checks the outside folder

While `LADO_ENV_DIR` is set and not empty, `lado doctor` SHALL print one check `Variables
from outside`:
- `[ok  ]` with the folder and the names it gives (never a value), or `none` for an empty
  folder;
- `[warn]` naming each file that is not applied and why, a path that is not absolute, a
  path that is neither a folder nor the null device, or a folder that cannot be listed.

#### Scenario: Two variables and a bad file
- **WHEN** the folder holds `BOARD_URL`, `YOUGILE_API_KEY` and `a-b`
- **THEN** `lado doctor` prints `[warn] Variables from outside: <folder>: BOARD_URL,
  YOUGILE_API_KEY; a-b not used: not a variable name`, and its exit code stays 0

### Requirement: lado doctor names the project variables that override the outside folder

While a project's variable or secret has the name of a variable the outside folder gives,
`lado doctor` SHALL print one check `[info] Project variables: <id> overrides
<NAME>[, <NAME>…] of LADO_ENV_DIR`, the projects joined by `; `, by id, never a value;
with no such name it SHALL print no such line. The bug report SHALL hold no project
variable's name or value.

#### Scenario: An override
- **WHEN** the outside folder gives `BOARD_URL` and `YOUGILE_API_KEY`, and project `shop`
  has `BOARD_URL`
- **THEN** `lado doctor` prints `[info] Project variables: shop overrides BOARD_URL of
  LADO_ENV_DIR`, and its exit code stays 0

#### Scenario: No override
- **WHEN** no project variable has a name the outside folder gives
- **THEN** `lado doctor` prints no `Project variables` line

#### Scenario: A secret overrides
- **WHEN** the outside folder gives `YOUGILE_API_KEY` and project `shop` has the secret
  `YOUGILE_API_KEY`
- **THEN** `lado doctor` prints `[info] Project variables: shop overrides YOUGILE_API_KEY of
  LADO_ENV_DIR`

### Requirement: The agents of a session in a project get the project's secrets

LADO SHALL give each agent it launches in a session that is in a project the project's
secrets with its plain variables, read anew from the secrets folder at each launch, in the
project's layer: login shell → outside folder → the project's variables and secrets →
LADO's and the provider's. A session without a project SHALL get no project's secret.

#### Scenario: Two projects, one secret name
- **WHEN** project `shop` has the secret `YOUGILE_API_KEY=a` and `acme` has
  `YOUGILE_API_KEY=b`, and a session runs in each
- **THEN** in `shop` the supervisor, a worker, a flow run's worker and the supervisor of the
  session it starts with `start_session` have `YOUGILE_API_KEY=a`, and every agent of
  `acme` has `b`

#### Scenario: No project
- **WHEN** `shop` has the secret `YOUGILE_API_KEY` and a session without a project starts
- **THEN** its agents have no `YOUGILE_API_KEY` from `shop`

#### Scenario: Over the outside folder
- **WHEN** the outside folder has `YOUGILE_API_KEY` with `out` and `shop` has the secret
  `YOUGILE_API_KEY=a`
- **THEN** an agent of a session in `shop` has `a`, and an agent of a session without a
  project has `out`

#### Scenario: A project's GH_TOKEN
- **WHEN** `shop` has the secret `GH_TOKEN`
- **THEN** no agent of `shop` has it

### Requirement: LADO's own git calls get the outside folder's variables

LADO's network git calls (a kit's or skill pack's tags and pinned clone, a marketplace's
clone and update, the listing of a URL's branches and its clone, from the CLI and from the
UI server) SHALL run with the outside folder's variables over LADO's process environment,
read anew at each call by the outside folder's reader, with the same files not used. They
SHALL NOT take the login shell's environment. LADO's local git calls are unchanged.

#### Scenario: The server's clone gets the outside folder's GH_TOKEN
- **WHEN** LADO's image runs with `GIT_SSH_COMMAND` only in `/run/secrets`, and the New
  session window lists the branches of `git@git.example:acme/private.git` and clones it
- **THEN** git runs that command for the listing and the clone

#### Scenario: A kit added through the server
- **WHEN** the same server adds the kit `git@git.example:acme/kit.git` from the Kits page
- **THEN** its tags are read and its clone is made with the folder's `GIT_SSH_COMMAND`

#### Scenario: A file added after the server started
- **WHEN** the server runs, and the human then adds `GIT_SSH_COMMAND` to the outside folder
- **THEN** the next listing, clone or kit add uses it, with no restart

### Requirement: A clone into a project gets the project's variables and secrets

A listing or clone of a URL into a project (`lado project repo add`, the project page's
Add repository and its branch list) SHALL run with the project's plain variables and
secrets, read anew at the call, over the outside folder's variables, in the agents'
order: LADO's process environment → the outside folder → the project's. A listing or
clone without a project SHALL get no project's variable.

#### Scenario: A project's own token
- **WHEN** project `shop` has the variable `GIT_SSH_COMMAND=a`, the outside folder has
  `GIT_SSH_COMMAND` with `out`, and the human adds `git@git.example:acme/private.git` on
  `shop`'s page
- **THEN** the branch list and the clone use `a`

#### Scenario: Another project's token is not used
- **WHEN** project `acme` has the variable `GIT_SSH_COMMAND`, and a clone without a project
  runs from New session → Clone
- **THEN** git gets no `GIT_SSH_COMMAND` from `acme`
