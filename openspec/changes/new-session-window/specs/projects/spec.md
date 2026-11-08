## MODIFIED Requirements

### Requirement: The project's page opens New session on its project

The button `New session…` in the head of the project's page SHALL open the New session
window with Where on this project (the Project way) and this project chosen.

#### Scenario: A new session from the page
- **WHEN** the human clicks `New session…` on `/projects/shop`
- **THEN** the New session window opens with Where on Project and `Shop` chosen

### Requirement: The server tells the New session window what a start in a project takes

`GET /api/project-launch` with the optional `project` and `repo` SHALL answer, making
nothing, `projects` (as `GET /api/projects`, sorted by title, the id without one, case
aside; none without `lado.db`), the chosen `project`, its `repos`, the chosen `repo`, and
for that repository `default_name` (`<project>-<repo>`), `name_state`, `free_name`,
`provider` (as the folder check gives it) and `last`, its latest session of this project.

#### Scenario: The window opens on Project
- **WHEN** the latest started session in a project is `shop-backend` of `shop`, and the UI
  asks `GET /api/project-launch`
- **THEN** `project` is `shop`, `repo` is `backend`, `default_name` is `shop-backend`,
  `free_name` is `shop-backend-2` when that session is stopped, and `last` is that session

### Requirement: The New session window starts a session in a project

The New session window SHALL offer a project's repository as a Recent item with its project's
badge and as **Project…** in Where's group Somewhere else. Project… SHALL show a select of the
projects (one whose folder is not found off, marked `folder not found`) and its repositories,
each with its name, branch and remote, one chosen; the start SHALL send `where: {kind:
"project", project, repo}` and open the session's page.

#### Scenario: Start in a project's repository
- **WHEN** the human picks Project…, `Shop`, then `frontend`, and clicks `Start in Shop`
- **THEN** the session `shop-frontend` starts in the project and its page opens, its head
  showing `Shop` before its title

#### Scenario: A project's repository from Recent
- **WHEN** the human picks `backend` with the badge `Project Shop` in Where's Recent
- **THEN** the start button reads `Start in Shop`, and the session starts in that repository
  of the project

### Requirement: The Project way's start names the project

For a project's repository the start button SHALL read `Start in <title>` (the id without
one), and `Start new session in <title>` beside `Resume <name>` when the repository has a
stopped session of the default name, so the human sees which project's keys the session
gets; another place's button names the place.

#### Scenario: Another project than the one last used
- **WHEN** the window opens on `Shop`, the project last used, and the human picks `ACME CRM`
  and its repository `crm`
- **THEN** the button reads `Start in ACME CRM`, and the session `acme-crm` starts in the
  project `acme`, as its head and `lado ls` show

### Requirement: The Project way takes the session's settings as Folder does

For a project's repository, Team's Name SHALL be the default name, else the free name, until
the human edits it; Team setup and Permissions SHALL come from the repository's last session,
as for a folder, and Agent from the server's suggestion. Resume SHALL be offered only for a
stopped session of the name that is of this project.

#### Scenario: A taken name
- **WHEN** a stopped `shop-frontend` of this repository exists and the window opens on it
- **THEN** Team reads `Name shop-frontend-2`, and the footer shows `Resume shop-frontend` and
  `Start new session in Shop`, also when the workspace's path goes through a link

### Requirement: Folder's refusal inside a project leads to the project

When the folder check refuses a folder with `project` set, the refusal SHALL show, above the
core's hint and command, `Start in the project <title>` when `project.repo` is set, which
turns Where to that project and repository, else `Open the project <title>`, which closes the
window and opens `/projects/<id>`. Clone into and a new empty folder inside a project SHALL
show `Open the project <title>` the same way.

#### Scenario: A project's repository in Folder
- **WHEN** the human types `<workspace>/projects/shop/frontend` in Other folder… and clicks
  `Start in the project Shop`
- **THEN** Where shows `frontend` with the badge `Project Shop`, and Team's name is
  `shop-frontend`

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

### Requirement: Start session opens New session on the repository

`Start session` on a repository's row SHALL open the New session window with Where on that
project and repository (`GET /api/project-launch?project=<id>&repo=<name>`).

#### Scenario: Started from the row
- **WHEN** the human clicks `Start session` on `backend` of `shop` and then `Start in Shop`
- **THEN** a session of project `shop` starts in `<ws>/projects/shop/backend`

## REMOVED Requirements

### Requirement: The switch of the New session window fits a phone
**Reason**: The window has no source switch any more: the ways are items of Where's list.
**Migration**: The phone's sheet and its 44 px targets (new-session-window, "The window's
frame keeps the footer in view").
