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
