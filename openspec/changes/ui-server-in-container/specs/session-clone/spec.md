## MODIFIED Requirements

### Requirement: The default folder of a clone

A clone's folder SHALL be, unless the human gives one, `<parent>/<repo>`: `<parent>` is
the repositories folder (`LADO_REPOS`) when one is set, else `~/lado`; `<repo>` is the
URL's last path segment without a trailing `/` or `.git`. A given folder SHALL be a full
path (`~` allowed); a relative one SHALL be refused as the window refuses it today. The
folders above it SHALL be made when missing.

#### Scenario: Default folder
- **WHEN** the URL is `https://github.com/ladohq/marketplace.git/` and no folder is given
- **THEN** the folder is `~/lado/marketplace`

#### Scenario: Default folder in the repositories folder
- **WHEN** `LADO_REPOS=/Users/me/repos` and the human clones `git@github.com:acme/app.git`
  with no folder, by `lado start` or the New session window
- **THEN** the folder is `/Users/me/repos/app`, and the window's Clone into shows it

### Requirement: lado start clones a git URL

`lado start <git-url> [<folder>] [--branch NAME]` SHALL check the folder (default
the clone's default folder, `~/lado/<repo>` or `$LADO_REPOS/<repo>`), then the session's name (default the folder's name, as for a folder),
clone the branch (the remote's default without `--branch`) with git's own progress lines
on stderr, then start the session as `lado start <folder>` does. A folder that is not
`new` or `empty` SHALL be refused with its text and nothing cloned; for `same_repo` the
next line SHALL be `lado: To start a session in it as it is: lado start <folder>`. A name
held by a session of another folder SHALL be refused before the clone. Ctrl-C during the
clone SHALL cancel it, print `lado: clone cancelled` and exit 130; a SIGTERM or SIGHUP
during the clone SHALL cancel it the same way and exit 128 plus its number. A refused
start after
the clone SHALL keep the clone and say `lado: the clone stays in <folder>`. `<folder>`
and `--branch` without a git URL SHALL be refused.

#### Scenario: Clone and start
- **WHEN** `lado start file:///srv/app.git --branch dev --no-attach` runs with no
  `~/lado/app`
- **THEN** `~/lado/app` is a clone on branch `dev` and a session `app` runs in it

#### Scenario: The clone is there already
- **WHEN** `~/lado/lado` is a clone of `https://github.com/ladohq/lado` and
  `lado start git@github.com:ladohq/lado.git` runs
- **THEN** it exits 1 printing the `same_repo` text and `lado start ~/lado/lado`, and
  changes nothing

#### Scenario: --branch with a folder
- **WHEN** `lado start ~/projects/app --branch dev` runs
- **THEN** it exits 2 saying `--branch` needs a git URL
