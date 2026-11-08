## MODIFIED Requirements

### Requirement: The New session window starts Where in the workspace

The server SHALL answer `GET /api/repos-folder` with `{path, made}`. Other folder…'s path
field SHALL have the placeholder `<path>/…`, Clone into `<path>/<repo>`, and New empty
folder's info button name `<path>`. With `made`, the empty path field SHALL suggest that
folder's subfolders on focus, a pick putting `<folder>/<name>` in it; without `made` it
SHALL suggest nothing.

#### Scenario: A first session in the container
- **WHEN** `LADO_REPOS=/Users/me/repos` holds `app`, `api` and `site`, and the human picks
  Other folder… and clicks into its empty path field
- **THEN** the list shows `api/`, `app/`, `site/`, and picking `app/` puts
  `/Users/me/repos/app` into the field, which is checked as any folder

#### Scenario: Without the variable
- **WHEN** the server runs without `LADO_REPOS`, the home folder is `/Users/ann` and
  `/Users/ann/workspace` does not exist
- **THEN** `GET /api/repos-folder` gives `{"path": "/Users/ann/workspace", "made": false}`,
  and the path field has the placeholder `/Users/ann/workspace/…` and suggests nothing
  while empty

#### Scenario: The default workspace made
- **WHEN** `/Users/ann/workspace` holds `app` and the human clicks into the empty path field
- **THEN** the list shows `app/`

#### Scenario: The focus before the server's answer
- **WHEN** `LADO_REPOS=/Users/me/repos` holds `app` and `api`, and the human clicks into
  the empty path field before `GET /api/repos-folder` has answered
- **THEN** the list shows `api/` and `app/` as soon as the answer comes, while the field
  keeps the focus; a field left before the answer shows no list

### Requirement: Where hints and recent folders leave out LADO's projects/

The subfolders the server gives for the workspace SHALL leave out `projects` when it is
LADO's (capability `projects`), a folder inside LADO's `projects/` SHALL have none, and the
recent places SHALL leave out the folders inside it, but a project's repository whose
session ran in that project, listed as a project item (capability new-session-window).

#### Scenario: The workspace with projects
- **WHEN** `/Users/ann/workspace` holds `app` and `projects`, which holds the folder of the
  project `shop`, and the human clicks into an empty path field
- **THEN** the list shows `app/` only

#### Scenario: The human's own projects folder
- **WHEN** `/Users/ann/workspace/projects` holds only the human's `notes` and LADO has no
  project
- **THEN** the list shows `projects/` as any folder

#### Scenario: A project's session in the recent places
- **WHEN** the latest session ran in the repository `backend` of the project `shop`
- **THEN** `/api/folders/recent` lists it with `project: {id: "shop", title, repo:
  "backend"}`, and Where's Recent shows `backend` with the badge `Project <title>`

### Requirement: In a container LADO warns about a session folder outside the workspace

In a container (`LADO_CONTAINER`), LADO SHALL warn about a session folder whose real path
is not the workspace's (`projects.workspace`) real path or below it. The warning is
`Outside the workspace (<folder>): this folder is only in the container, your computer
does not see it or the agents' work in it`. Outside a container there SHALL be no warning.

#### Scenario: A folder on the home volume
- **WHEN** in a container with `LADO_REPOS=/Users/ann/projects` the human types
  `/home/lado/app`, a git repository, into Where
- **THEN** the window shows `✓ Ready · branch main`, then `⚠ Outside the
  workspace (/Users/ann/projects): this folder is only in the container, your
  computer does not see it or the agents' work in it`, and the start button is on

#### Scenario: A folder in the workspace
- **WHEN** in that container the human types `/Users/ann/projects/app`
- **THEN** no warning shows

#### Scenario: The workspace through a link
- **WHEN** the folder is a symbolic link whose real path is below the workspace
- **THEN** no warning shows

#### Scenario: Outside a container
- **WHEN** LADO runs without `LADO_CONTAINER` and with `LADO_REPOS=/Users/ann/projects`,
  and the human types `/tmp/app`
- **THEN** no warning shows

## REMOVED Requirements

### Requirement: The Workspace row puts the folder into Where
**Reason**: The window has no Workspace row any more: Where opens on the last place, and the
workspace is the path field's placeholder and the list of its empty field.
**Migration**: Other folder…'s path field lists the workspace's subfolders while empty
(requirement "The New session window starts Where in the workspace").
