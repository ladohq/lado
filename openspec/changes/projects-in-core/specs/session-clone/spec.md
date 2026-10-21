## RENAMED Requirements

- FROM: `### Requirement: The default folder of a clone, in the workspace when there is one`
- TO: `### Requirement: The default folder of a clone is in the workspace`

## MODIFIED Requirements

### Requirement: lado start clones a git URL

`lado start <git-url> [<folder>] [--branch NAME]` SHALL check the folder (default
the clone's default folder, `<workspace>/<repo>`), then the session's name (default the folder's name, as for a folder),
clone the branch (the remote's default without `--branch`) with git's own progress lines
on stderr, then start the session as `lado start <folder>` does. `<folder>`
and `--branch` without a git URL SHALL be refused.

#### Scenario: Clone and start
- **WHEN** `lado start file:///srv/app.git --branch dev --no-attach` runs without
  `LADO_REPOS` and with no `~/workspace/app`
- **THEN** `~/workspace/app` is a clone on branch `dev` and a session `app` runs in it

#### Scenario: --branch with a folder
- **WHEN** `lado start ~/workspace/app --branch dev` runs
- **THEN** it exits 2 saying `--branch` needs a git URL

### Requirement: The default folder of a clone is in the workspace

A clone's folder SHALL be, unless the human gives one, `<workspace>/<repo>`
(`projects.workspace`; `<repo>` is the URL's last path segment without a trailing `/` or
`.git`). A given folder SHALL be a full path (`~` allowed); a relative one SHALL be refused
as the window refuses it. The folders above it, the workspace among them, SHALL be made
when missing. Sessions in `~/lado/<repo>`, the default before 0.43.0, SHALL keep working.

#### Scenario: Default folder
- **WHEN** `LADO_REPOS` is unset, the URL is `https://github.com/ladohq/marketplace.git/`
  and no folder is given
- **THEN** the folder is `~/workspace/marketplace`, and `~/workspace` is made if missing

#### Scenario: Default folder in the workspace
- **WHEN** `LADO_REPOS=/Users/me/repos` and the human clones `git@github.com:acme/app.git`
  with no folder, by `lado start` or the New session window
- **THEN** the folder is `/Users/me/repos/app`, and the window's Clone into shows it

#### Scenario: An older session's folder
- **WHEN** a session made before this change runs in `~/lado/app` and the human resumes it
- **THEN** it resumes in `~/lado/app`

### Requirement: The target check tells a clone by its origin

The target folder's check SHALL also give these states, each of which lets no clone start:

| State | When | Text |
|---|---|---|
| `same_repo` | the root of a git repository whose `origin` is the same repository | `<path> is already a clone of this repository (origin <origin>), on branch <b>` |
| `other_repo` | the root of a git repository whose `origin` is another repository | `<path> is a clone of another repository (origin <origin>): choose another folder` |

#### Scenario: Another repository with the same name
- **WHEN** the folder `~/workspace/app` is a clone of `git@github.com:acme/app.git` and
  the URL is `git@github.com:ladohq/app.git`
- **THEN** the state is `other_repo`, the text names the origin `git@github.com:acme/app.git`
  and suggests `~/workspace/ladohq-app`, and no clone starts

### Requirement: A clone of another repository suggests a free folder

For `other_repo`, when the URL's path has an owner segment and `<parent>/<owner>-<repo>`
(`<parent>` the given folder's parent) is `new`, the text SHALL end with `, e.g. <that
folder>`.

#### Scenario: The suggested folder is taken too
- **WHEN** the folder `~/workspace/app` is a clone of `git@github.com:acme/app.git`, the
  URL is `git@github.com:ladohq/app.git`, and `~/workspace/ladohq-app` exists
- **THEN** the state is `other_repo` and its text suggests no folder

### Requirement: lado start refuses a target or a name before the clone

A folder that is not
`new` or `empty` SHALL be refused by `lado start <git-url>` with its text and nothing cloned; for `same_repo` the
next line SHALL be `lado: To start a session in it as it is: lado start <folder>`. A name
held by a session of another folder SHALL be refused before the clone.

#### Scenario: The clone is there already
- **WHEN** `LADO_REPOS` is unset, `~/workspace/lado` is a clone of
  `https://github.com/ladohq/lado` and `lado start git@github.com:ladohq/lado.git` runs
- **THEN** it exits 1 printing the `same_repo` text and `lado start ~/workspace/lado`, and
  changes nothing
