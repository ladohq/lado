## ADDED Requirements

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
