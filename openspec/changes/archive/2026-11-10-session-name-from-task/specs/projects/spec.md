## ADDED Requirements

### Requirement: A project's default session name does not repeat the project

The default name of a session in the repository `<name>` of the project `<id>` SHALL be, of
their slugs, the repository's when it equals the project's or starts with `<id>-`, the
project's when it ends with `-<name>`, else `<id>-<name>`; the New session window and `lado
start --project` SHALL take it from the core's one function. Sessions that exist SHALL keep
their names.

#### Scenario: The same name twice
- **WHEN** the project `lado` has the repository `lado`
- **THEN** the default name is `lado`, not `lado-lado`

#### Scenario: A repository named after its project
- **WHEN** the project `lado` has the repository `lado-site`, or the project `acme-web` the
  repository `web`
- **THEN** the default name is `lado-site`, or `acme-web`

#### Scenario: Different names
- **WHEN** the project `acme` has the repository `api`
- **THEN** the default name is `acme-api`

## MODIFIED Requirements

### Requirement: lado start --project --repo starts a session in a project's repository

`lado start --project <id> --repo <name>` SHALL start a session in the repository `<name>`
of the project `<id>`, refer to the project in its record, and print `Started session
"<session>" in <folder> (project <id>)`. Without `--name` the session SHALL be named the
project's default session name. Its other options SHALL work as for a folder. A session of that
name in the same project SHALL be resumed.

#### Scenario: A first session in a project
- **WHEN** the project `shop` has the repository `frontend` and the human runs
  `lado start --project shop --repo frontend --no-attach`
- **THEN** the session `shop-frontend` runs in `<ws>/projects/shop/frontend`, its record
  has the project `shop`, and the output has `Started session "shop-frontend" in
  <ws>/projects/shop/frontend (project shop)`

#### Scenario: Started again
- **WHEN** `shop-frontend` is stopped and the human runs the same command
- **THEN** it is resumed, with its history and project

#### Scenario: A repository named as its project
- **WHEN** the project `lado` has the repository `lado` and the human runs `lado start
  --project lado --repo lado --no-attach`
- **THEN** the session `lado` runs in `<ws>/projects/lado/lado`; a stopped `lado-lado` of
  before stays stopped

### Requirement: The server starts a session in a project's repository

`POST /api/sessions` with `where: {kind: "project", project: <id>, repo: <name>}` and the
change token SHALL start a new session as `lado start --project <id> --repo <name>` does,
by the same core function (`runtime.start_session` with `project` and `repo_name`, no
path), never a resume: its folder the repository, its default name the project's default
session name, its project `<id>`.

#### Scenario: A start in a project
- **WHEN** the UI posts `where: {kind: "project", project: "shop", repo: "frontend"}`
- **THEN** the session `shop-frontend` starts in `<workspace>/projects/shop/frontend` with
  project `shop`, and the answer is `Started` with `session.project: "shop"`

### Requirement: The server tells the New session window what a start in a project takes

`GET /api/project-launch` with the optional `project` and `repo` SHALL answer, making
nothing, `projects` (as `GET /api/projects`, sorted by title, the id without one, case
aside; none without `lado.db`), the chosen `project`, its `repos`, the chosen `repo`, and
for that repository `default_name` (the project's default session name), `name_state`,
`free_name`, `provider` (as the folder check gives it) and `last`, its latest session of this
project.

#### Scenario: The window opens on Project
- **WHEN** the latest started session in a project is `shop-backend` of `shop`, and the UI
  asks `GET /api/project-launch`
- **THEN** `project` is `shop`, `repo` is `backend`, `default_name` is `shop-backend`,
  `free_name` is `shop-backend-2` when that session is stopped, and `last` is that session

#### Scenario: A repository named as its project
- **WHEN** the UI asks `GET /api/project-launch?project=lado&repo=lado`
- **THEN** `default_name` is `lado`

### Requirement: The New session window starts a session in a project

The New session window SHALL offer a project's repository as a Recent item with `in project
<title>` after its name and as **Project…** in Where's group Somewhere else. Project… SHALL show
a select of the projects (one whose folder is not found off, marked `folder not found`) and its
repositories, each with its name, branch and remote, one chosen; the start SHALL send `where:
{kind: "project", project, repo}` and open the session's page.

#### Scenario: Start in a project's repository
- **WHEN** the human picks Project…, `Shop`, then `frontend`, and clicks `Start in Shop`
- **THEN** the session `shop-frontend` starts in the project and its page opens, its head
  showing `Shop` before its title

#### Scenario: A project's repository from Recent
- **WHEN** the human picks `backend` with `in project Shop` in Where's Recent
- **THEN** the start button reads `Start in Shop`, and the session starts in that repository
  of the project

### Requirement: The Project way takes the session's settings as Folder does

For a project's repository, Name SHALL be named as for any place, the project's default session
name or its free name standing for the place; Kits and Permissions SHALL come from the
repository's last session, as for a folder, and Agent from the server's suggestion. The line
`Session <name> stopped here` SHALL name only a stopped session of the name that is of this
project.

#### Scenario: A taken name
- **WHEN** a stopped `shop-frontend` of this repository exists, Task is empty and the window
  opens on it
- **THEN** Name reads `shop-frontend-2`, and the footer shows one button, `Start new
  session in Shop`, and no `Resume shop-frontend`, also when the workspace's path goes through a
  link

### Requirement: Folder's refusal inside a project leads to the project

When the folder check refuses a folder with `project` set, the refusal SHALL show, above the
core's hint and command, `Start in the project <title>` when `project.repo` is set, which
turns Where to that project and repository, else `Open the project <title>`, which closes the
window and opens `/projects/<id>`. Clone into and a new empty folder inside a project SHALL
show `Open the project <title>` the same way.

#### Scenario: A project's repository in Folder
- **WHEN** the human types `<workspace>/projects/shop/frontend` in Other folder… and clicks
  `Start in the project Shop`
- **THEN** Where shows `frontend` with `in project Shop`, and Name reads `shop-frontend` while
  Task is empty

#### Scenario: A folder of a project that is no repository
- **WHEN** the human types `<workspace>/projects/shop/notes`, a folder without git
- **THEN** the refusal offers `Open the project Shop`, which opens `/projects/shop`

#### Scenario: Clone into a new folder of a project
- **WHEN** the human chooses Clone from URL and types `<workspace>/projects/shop/admin` in
  Clone into
- **THEN** the refusal names the project, offers `Open the project Shop` above the hint
  `lado project repo add shop <git-url>`, and the button closes the window and opens
  `/projects/shop`

#### Scenario: Create in a new folder of a project
- **WHEN** the human chooses New empty folder… with the target `<workspace>/projects/shop`
- **THEN** the refusal offers `Open the project Shop`
