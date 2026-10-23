## MODIFIED Requirements

### Requirement: The project's page shows the project and what is not built yet

The project's page SHALL show the title (the id without one), the id, the line `<N>
repositories · <N> sessions running · folder <folder>` (`folder not found` after it when
it is missing), and the line `New session in this project… Not built yet: the
repositories on this page (adding, removing), renaming and deleting the project. Plan:
Projects, step S7. Meanwhile: lado project show <id>, lado project repo add <id>
<git-url>.` with its first words a button and the plan a link.

#### Scenario: The head of the page
- **WHEN** the human opens `/projects/shop`
- **THEN** the page shows `Shop`, `shop`, `2 repositories · 2 sessions running · folder
  <workspace>/projects/shop` and the not-built line naming `lado project show shop`

## ADDED Requirements

### Requirement: The project's page opens New session on its project

The button `New session in this project…` of the project's page SHALL open the New session
window in Project with this project chosen.

#### Scenario: A new session from the page
- **WHEN** the human clicks `New session in this project…` on `/projects/shop`
- **THEN** the New session window opens in Project with `Shop` chosen

### Requirement: The server starts a session in a project's repository

`POST /api/sessions` with `where: {kind: "project", project: <id>, repo: <name>}` and the
change token SHALL start a new session as `lado start --project <id> --repo <name>` does,
by the same core function (`runtime.start_session` with `project` and `repo_name`, no
path), never a resume: its folder the repository, its default name `<id>-<name>`, its
project `<id>`.

#### Scenario: A start in a project
- **WHEN** the UI posts `where: {kind: "project", project: "shop", repo: "frontend"}`
- **THEN** the session `shop-frontend` starts in `<workspace>/projects/shop/frontend` with
  project `shop`, and the answer is `Started` with `session.project: "shop"`

### Requirement: The server refuses a start in a project as the core does

A start of kind `project` SHALL answer 404 with the core's text for an unknown project or
repository, 409 `Taken` for a name a session has, as for a folder, and 400 with the core's
text for any other refusal of the core. `where` of kind `project` with a `path` or without
`project` or `repo`, and of kind `folder` or `scratch` with `project` or `repo`, SHALL be
400. Nothing SHALL start on a refusal.

#### Scenario: An unknown repository
- **WHEN** the UI posts `where: {kind: "project", project: "shop", repo: "docs"}` and
  `shop` has `frontend` and `backend`
- **THEN** the answer is 404 with `project shop has no repository docs; its repositories:
  backend, frontend`, and nothing starts

#### Scenario: A taken name
- **WHEN** a stopped session `shop-frontend` exists and the UI posts the same start
- **THEN** the answer is 409 `Taken` with its status and folder

#### Scenario: A path with a project
- **WHEN** the UI posts `where: {kind: "project", project: "shop", repo: "frontend",
  path: "/tmp/x"}`
- **THEN** the answer is 400, and nothing starts

### Requirement: The server tells the New session window what a start in a project takes

`GET /api/project-launch` with the optional `project` and `repo` SHALL answer, making
nothing, `projects` (as `GET /api/projects` gives them, sorted by title, the id without
one, case aside; none without `lado.db`), the chosen `project`, its `repos`, the chosen
`repo`, and for that repository `default_name` (`<project>-<repo>` as the core makes it),
`name_state`, `provider` (as the folder check gives it) and `last`, the repository's latest
started session of this project or null.

#### Scenario: The window opens on Project
- **WHEN** the latest started session in a project is `shop-backend` of `shop`, and the UI
  asks `GET /api/project-launch`
- **THEN** `project` is `shop`, `repo` is `backend`, `default_name` is `shop-backend` and
  `last` is that session

### Requirement: The Project way chooses the project and repository last used

`GET /api/project-launch` SHALL choose as `project` the id asked when it is a project, else
that of the latest started session in a project whose folder is found, else the first of
`projects` whose folder is found, else the first, null without projects; and as `repo` the name asked when it is one of the
project's repositories, else that of the project's latest started session when it is still
one, else the first, null when there are none.

#### Scenario: Another project chosen
- **WHEN** the UI asks `GET /api/project-launch?project=acme` and `acme` has no session but
  the repository `crm`
- **THEN** `project` is `acme`, `repo` is `crm`, `name_state` is `free` and `last` is null

#### Scenario: An empty project
- **WHEN** the UI asks for a project with no repository
- **THEN** `repos` is empty and `repo`, `default_name` and `last` are null

### Requirement: A name held outside the project is taken elsewhere

`name_state` of `GET /api/project-launch` SHALL be the folder check's, but a session of the
default name that is in another project or in none SHALL count as `taken_elsewhere`.

#### Scenario: A name of another project
- **WHEN** a session `shop-frontend` exists that is not in `shop`
- **THEN** `name_state` for `shop` and `frontend` is `taken_elsewhere`

### Requirement: The folder check names the project a folder is in

`GET /api/folders` for a path inside a project's folder (by its real path, while
`projects/` is LADO's) SHALL carry `project: {id, title, repo}`, `repo` the project's
repository the path is in or null; for any other path, a foreign folder of `projects/`
included, `project` SHALL be null. The refusal's text and hint SHALL stay the core's.

#### Scenario: A project's repository
- **WHEN** the UI checks `<workspace>/projects/shop/frontend/src`
- **THEN** `ok` is false, `problem_kind` is `in_project` and `project` is `{id: "shop",
  title: "Shop", repo: "frontend"}`

#### Scenario: The project's folder itself
- **WHEN** the UI checks `<workspace>/projects/shop`
- **THEN** `project` is `{id: "shop", title: "Shop", repo: null}`

### Requirement: The New session window starts a session in a project

The New session window SHALL have the source **Project** last in its switch. Project SHALL
show a select of the projects (one whose folder is not found off, marked `folder not
found`), the chosen project's line `<N> repositories · <N> sessions running · folder
<folder>`, and its repositories, each with its name, branch and remote, one chosen. **Start
session** SHALL start with `where: {kind: "project", project, repo}` and open the session's
page. The window's first source SHALL stay as before.

#### Scenario: Start in a project's repository
- **WHEN** the human picks Project, `Shop`, then `frontend`, and clicks Start session
- **THEN** the session `shop-frontend` starts in the project and its page opens, its head
  showing `project Shop`

### Requirement: The Project way only chooses a repository, from a list always shown

Project's list of repositories SHALL show even with one item. The window SHALL only choose
one of the project's repositories: it SHALL NOT add, clone or make one.

#### Scenario: The list with one repository
- **WHEN** the chosen project has the one repository `crm`
- **THEN** the list shows `crm`, chosen

### Requirement: The Project way takes the session's settings as Folder does

In Project, Name SHALL be the default name until the human edits it, with the folder
check's notes for a taken name; Kits and Permission mode SHALL come from the repository's
last session, as Folder takes them from a folder's, and Provider from the server's
suggestion. A refused start SHALL show the core's text, with `Resume it` or `Open it` as
for a folder.

#### Scenario: A taken name
- **WHEN** a stopped `shop-frontend` of this repository exists and the human clicks Start
  session
- **THEN** the window shows `session "shop-frontend" exists already (stopped, in
  <workspace>/projects/shop/frontend); resume it, or give the new session another name`
  and `Resume it`

### Requirement: The Project way sends the human to the project when nothing can be chosen

In Project, a project with no repository SHALL show in the list's place `No repositories
yet. Add one on the project's page:` with a link `Open <title>` to `/projects/<id>`, and
Start session SHALL be off. With no project the field SHALL show `No projects yet. A project
keeps its repositories and the variables its sessions get.` with a link `Make one in
Projects` to `/projects`. Each link SHALL close the window.

#### Scenario: An empty project
- **WHEN** the human picks the project `ACME CRM` without repositories
- **THEN** the field shows the line with `Open ACME CRM`, and Start session is off

#### Scenario: No project
- **WHEN** LADO has no project and the human picks Project
- **THEN** the field shows `No projects yet…` with `Make one in Projects`

### Requirement: Folder's refusal inside a project leads to the project

When Folder's check refuses a folder with `project` set, the refusal SHALL show, above the
core's hint and its command, the button `Start in the project <title>` when `project.repo`
is set, which switches the window to Project with that project and repository chosen, else
the button `Open the project <title>`, which closes the window and opens `/projects/<id>`.
The refusals of Clone into and Create in SHALL stay as they are.

#### Scenario: A project's repository in Folder
- **WHEN** the human types `<workspace>/projects/shop/frontend` in Folder and clicks `Start
  in the project Shop`
- **THEN** the window shows Project with `Shop` and `frontend` chosen and the name
  `shop-frontend`

#### Scenario: A folder of a project that is no repository
- **WHEN** the human types `<workspace>/projects/shop/notes`, a folder without git
- **THEN** the refusal offers `Open the project Shop`, which opens `/projects/shop`

### Requirement: The switch of the New session window fits a phone

On a screen of at most 760 px the switch of the New session window SHALL show its four
buttons as a grid of two columns within the window, none cut off.

#### Scenario: A phone
- **WHEN** the human opens New session on a 390 px screen
- **THEN** From scratch and Folder are on the first row, Clone from URL and Project on the
  second, all inside the window
