# repos-folder Specification

## Purpose
Where LADO starts looking for the human's repositories: `LADO_REPOS` names their folder (in
the container image or on the human's own machine), the New session window starts Where in
it, a clone goes there by default, and `lado doctor` says which folder it is or why its
value is ignored.

## Requirements

### Requirement: LADO_REPOS names the folder of the human's repositories

LADO SHALL take the environment variable `LADO_REPOS` as the folder of the human's
repositories when it is an absolute path after `~` is expanded, and SHALL take it as unset
when it is unset, empty or not absolute. One function (`clone.repos_folder`) SHALL answer
it for the clone's default folder, the UI server and `lado doctor`. It SHALL work alike in
and out of a container.

#### Scenario: A home-relative value
- **WHEN** `LADO_REPOS=~/code`
- **THEN** the workspace is the home folder's `code`

#### Scenario: A relative value
- **WHEN** `LADO_REPOS=code`
- **THEN** LADO has no workspace, and `lado doctor` warns `LADO_REPOS is not an
  absolute path: code; LADO ignores it`

### Requirement: lado doctor names the workspace

When `LADO_REPOS` is set and not empty, `lado doctor` SHALL print a check
`Workspace`: `ok` with `<path> (LADO_REPOS)` for a folder LADO may write in,
`info` with `<path> (LADO_REPOS), not made yet: the first clone makes it` for a missing
path. When it is unset or empty, `lado doctor` SHALL print no
such line.

#### Scenario: The image's folder
- **WHEN** `lado doctor` runs with `LADO_REPOS=/Users/me/repos`, a folder
- **THEN** it prints `[ok  ] Workspace: /Users/me/repos (LADO_REPOS)`

#### Scenario: Unset
- **WHEN** `lado doctor` runs without `LADO_REPOS`
- **THEN** it prints no Workspace line

### Requirement: lado doctor warns about a workspace LADO cannot use

The check `Workspace` SHALL be `warn` for a value that is not absolute, a path that is not a folder (`LADO_REPOS is
not a folder: <path>`), one LADO may not look at (`cannot look at LADO_REPOS <path>:
<reason>`) or a folder LADO may not write in (`LADO may not write in LADO_REPOS <path>:
<reason>`).

#### Scenario: A file instead of a folder
- **WHEN** `lado doctor` runs with `LADO_REPOS=/Users/me/notes`, a regular file
- **THEN** it prints `[warn] Workspace: LADO_REPOS is not a folder:
  /Users/me/notes`

### Requirement: Whether LADO may write in the workspace is found by trying

Whether LADO may write in the workspace SHALL be found by making a new hidden file in the
folder and removing it at once, never by its owner and mode bits alone, which a bind mount
of Docker Desktop shows wrong.

#### Scenario: A folder LADO may not write in
- **WHEN** `lado doctor` runs with `LADO_REPOS` a folder where LADO cannot make a file
- **THEN** it prints `[warn] Workspace: LADO may not write in LADO_REPOS
  <path>: <reason>`, and the folder holds no file the check made

### Requirement: The New session window starts Where in the workspace

The server SHALL answer `GET /api/repos-folder` with `{path}`, the workspace or
null. With a folder, the New session window's **Where** field, while empty, SHALL suggest
that folder's subfolders when it has the focus, and picking one SHALL put its full path
(`<folder>/<name>`) in the field; its placeholder SHALL be `<folder>/…`. **Clone
into**'s placeholder SHALL be `<folder>/<repo>`. Without a folder the window SHALL be as
before.

#### Scenario: A first session in the container
- **WHEN** `LADO_REPOS=/Users/me/repos` holds `app`, `api` and `site`, and the human opens
  New session and clicks into Where
- **THEN** the list shows `api/`, `app/`, `site/`, and picking `app/` puts
  `/Users/me/repos/app` into Where, which is checked as any folder

#### Scenario: Without the variable
- **WHEN** the server runs without `LADO_REPOS`
- **THEN** `GET /api/repos-folder` gives `{"path": null}`, and the window has the
  placeholder `~/projects/app`, no Workspace row, and suggests nothing for an
  empty field

### Requirement: The Workspace row puts the folder into Where

With a folder, under the **Where** field a row
`Workspace:` SHALL show the folder as a button that puts `<folder>/` into the
field and gives the field the focus, before the recent folders and hidden in Resume, as
they are. The field SHALL stay empty when the window opens, with no folder check until the
human types or picks; the workspace itself (with or without its last `/`) is not
checked either, as it is no session's folder.

#### Scenario: The button
- **WHEN** the human clicks `/Users/me/repos` in the Workspace row
- **THEN** Where reads `/Users/me/repos/`, has the focus and lists its subfolders, with no
  folder check under it; leaving the field closes the list

### Requirement: One function gives the warning about a folder outside LADO_REPOS

One function
(`runtime.outside_repos`) SHALL give that warning, or None:
- for the UI's folder check, as `FolderInfo.warning`, shown under **Where** after the
  check mark;
- for the clone's target, as `CloneTarget.warning`, shown under **Clone into**;
- for a start and a resume, among its warnings: `lado start` on stderr, `Started.warnings`
  in the UI, the result of the supervisor's `start_session`.
It SHALL never refuse a folder: the check mark and Start stay as they are.

#### Scenario: A start outside it
- **WHEN** in that container `lado start /home/lado/app` starts a session
- **THEN** stderr has the warning, and the session runs

### Requirement: In a container LADO warns about a session folder outside the workspace

In a container (`LADO_CONTAINER`), with a workspace (`LADO_REPOS`), LADO SHALL
warn about a session folder whose real path is not the workspace's real path or
below it. The warning is `Outside the workspace (<folder>): this folder is only
in the container, your computer does not see it or the agents' work in it`. Outside a
container, or without a workspace, there SHALL be no warning.

#### Scenario: A folder on the home volume
- **WHEN** in a container with `LADO_REPOS=/Users/ann/projects` the human types
  `/home/lado/app`, a git repository, into Where
- **THEN** the window shows `✓ git repository · branch main`, then `⚠ Outside the
  workspace (/Users/ann/projects): this folder is only in the container, your
  computer does not see it or the agents' work in it`, and Start is available

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
