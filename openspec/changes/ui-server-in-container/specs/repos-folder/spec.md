## ADDED Requirements

### Requirement: LADO_REPOS names the folder of the human's repositories

LADO SHALL take the environment variable `LADO_REPOS` as the folder of the human's
repositories when it is an absolute path after `~` is expanded, and SHALL take it as unset
when it is unset, empty or not absolute. One function (`clone.repos_folder`) SHALL answer
it for the clone's default folder, the UI server and `lado doctor`. It SHALL work alike in
and out of a container.

#### Scenario: A home-relative value
- **WHEN** `LADO_REPOS=~/code`
- **THEN** the repositories folder is the home folder's `code`

#### Scenario: A relative value
- **WHEN** `LADO_REPOS=code`
- **THEN** LADO has no repositories folder, and `lado doctor` warns `LADO_REPOS is not an
  absolute path: code; LADO ignores it`

### Requirement: lado doctor names the repositories folder

When `LADO_REPOS` is set and not empty, `lado doctor` SHALL print a check
`Repositories folder`: `ok` with `<path> (LADO_REPOS)` for a folder, `info` with `<path>
(LADO_REPOS), not made yet: the first clone makes it` for a missing path, `warn` for a
value that is not absolute or a path that is not a folder (`LADO_REPOS is not a folder:
<path>`). When it is unset or empty, `lado doctor` SHALL print no such line.

#### Scenario: The image's folder
- **WHEN** `lado doctor` runs with `LADO_REPOS=/Users/me/repos`, a folder
- **THEN** it prints `[ok  ] Repositories folder: /Users/me/repos (LADO_REPOS)`

#### Scenario: Unset
- **WHEN** `lado doctor` runs without `LADO_REPOS`
- **THEN** it prints no Repositories folder line

### Requirement: The New session window starts Where in the repositories folder

The server SHALL answer `GET /api/repos-folder` with `{path}`, the repositories folder or
null. With a folder, the New session window's **Where** field, while empty, SHALL suggest
that folder's subfolders when it has the focus, and picking one SHALL put its full path
(`<folder>/<name>`) in the field; its placeholder SHALL be `<folder>/…`; under it a row
`Repositories folder:` SHALL show the folder as a button that puts `<folder>/` into the
field, before the recent folders and hidden in Resume, as they are. The field SHALL stay
empty when the window opens, with no folder check until the human types or picks. **Clone
into**'s placeholder SHALL be `<folder>/<repo>`. Without a folder the window SHALL be as
before.

#### Scenario: A first session in the container
- **WHEN** `LADO_REPOS=/Users/me/repos` holds `app`, `api` and `site`, and the human opens
  New session and clicks into Where
- **THEN** the list shows `api/`, `app/`, `site/`, and picking `app/` puts
  `/Users/me/repos/app` into Where, which is checked as any folder

#### Scenario: The button
- **WHEN** the human clicks `/Users/me/repos` in the Repositories folder row
- **THEN** Where reads `/Users/me/repos/` and lists its subfolders

#### Scenario: Without the variable
- **WHEN** the server runs without `LADO_REPOS`
- **THEN** `GET /api/repos-folder` gives `{"path": null}`, and the window has the
  placeholder `~/projects/app`, no Repositories folder row, and suggests nothing for an
  empty field
