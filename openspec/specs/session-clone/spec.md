# session-clone Specification

## Purpose
A LADO session from a repository's git URL: the clone of one branch into a chosen folder
(by default `~/lado/<repo>`) behind `lado start <git-url>` and the New session window's
Clone from URL, with the remote's branches, the target folder's check, progress and
cancellation, and LADO's rule that it uses only the access the machine has and never
touches a folder that exists.

## Requirements

### Requirement: A git URL is told from a folder

LADO SHALL take as a git URL, to clone, exactly a source of one of these forms:
`https://`, `http://`, `ssh://`, `git://` or `file://` followed by the rest of the
address, or the scp form `<user>@<host>:<path>`. Anything else SHALL be a folder, checked
as `lado start <folder>` checks it (`runtime.check_repo`). Every text LADO shows or logs
SHALL name a URL through `runtime.public_remote` (no password or token).

#### Scenario: An ssh address in scp form
- **WHEN** the source is `git@github.com:ladohq/lado.git`
- **THEN** it is a git URL

#### Scenario: A folder
- **WHEN** the source is `~/projects/app`, `app` or `/srv/app.git`
- **THEN** it is a folder, as before this change

#### Scenario: A token in the URL is never shown
- **WHEN** the source is `https://ghp_secret@github.com/acme/app` and the clone fails
- **THEN** the text names `https://github.com/acme/app` and holds no `ghp_secret`

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

### Requirement: The target folder is checked before any clone

Before it lists branches or clones, LADO SHALL check the target folder and give one of
these states; only `new` and `empty` SHALL let a clone start, and LADO SHALL change
nothing in a folder of another state:

| State | When | Text |
|---|---|---|
| `new` | the path does not exist | `a new folder` |
| `empty` | an empty folder | `an empty folder` |
| `same_repo` | the root of a git repository whose `origin` is the same repository | `<path> is already a clone of this repository (origin <origin>), on branch <b>` |
| `other_repo` | the root of a git repository whose `origin` is another repository | `<path> is a clone of another repository (origin <origin>): choose another folder` |
| `not_empty` | anything else in a folder | `<path> is not empty and is not a clone of <url>: choose another folder` |
| `not_folder` | a file | `<path> is a file, not a folder` |

Two addresses SHALL be the same repository when their host (lowercased) and their path
(without a leading or trailing `/`, a trailing `.git`, and for scp form the part before
`:`) are equal; the scheme, the user and the port SHALL NOT count. Two `file://` URLs or
paths SHALL compare by real path. For `other_repo`, when the URL's path has an owner
segment and `~/lado/<owner>-<repo>` (in the same parent as the given folder) is `new`,
the text SHALL end with `, e.g. <that folder>`.

#### Scenario: The same repository over another protocol
- **WHEN** the folder's origin is `git@github.com:ladohq/lado.git` and the URL is
  `https://github.com/ladohq/lado`
- **THEN** the state is `same_repo`, naming its branch

#### Scenario: Another repository with the same name
- **WHEN** the folder `~/lado/app` is a clone of `git@github.com:acme/app.git` and the URL
  is `git@github.com:ladohq/app.git`
- **THEN** the state is `other_repo`, the text names the origin `git@github.com:acme/app.git`
  and suggests `~/lado/ladohq-app`, and no clone starts

#### Scenario: A folder with other files
- **WHEN** the folder holds files and is no repository root
- **THEN** the state is `not_empty` and no clone starts

### Requirement: The remote's branches are listed without cloning

LADO SHALL list a remote's branches and its default branch with one `git ls-remote`
(heads and the `HEAD` symref), with the access rules of a clone, within
`clone.LIST_TIMEOUT` seconds (20). A remote with no branch SHALL be refused as
`the repository has no branches yet`.

#### Scenario: Branches and the default one
- **WHEN** the remote has `main` (its HEAD), `develop` and `release/1.2`
- **THEN** the list is those three and the default branch is `main`

#### Scenario: A remote that does not answer
- **WHEN** `git ls-remote` runs longer than `LIST_TIMEOUT`
- **THEN** it is stopped and refused as `<host> did not answer within 20 s`

### Requirement: LADO uses only the access the machine has

LADO's git calls of a clone or listing SHALL run with no terminal and no prompt (no
controlling terminal, stdin closed, `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS` empty, `SSH_ASKPASS_REQUIRE=never`,
`GCM_INTERACTIVE=never`, `LC_ALL=C`), in LADO's own process environment, so a missing
credential is a failure, never a wait. LADO SHALL neither ask for nor keep a password,
passphrase or token. A failure SHALL be told as `cannot read <url>: <reason> (<git's
line>)` for a listing and `cannot clone <url>: <reason> (<git's line>)` for a clone, by
kind:

| Kind | Reason | Hint (sentence: command) |
|---|---|---|
| `ssh_denied` | `<host> refused this machine's ssh key` | `Check that this machine's ssh key is added to your account on <host>:` `ssh -T <user>@<host>` |
| `host_key` | `this machine does not know <host>'s ssh host key yet` | `Connect once in a terminal and accept the host key:` `ssh -T <user>@<host>` |
| `login_needed` | `<host> asks for a login` (other hosts: `…; set up a git credential helper for it on this machine`) | github.com: `Log in with GitHub's CLI on this machine:` `gh auth login`; other hosts none |
| `not_found` | `no repository there, or this machine's account cannot read it` | github.com: `See which GitHub account this machine uses:` `gh auth status`; other hosts none |
| `unreachable` | `<host> cannot be reached` | none |
| `no_branch` | `no branch <b>` | none |
| `git_failed` | git's line alone | none |

git missing or not running SHALL be LAD-5's `no_git` / `git_broken` text and hint.
`<git's line>` SHALL be git's first error line that starts with `fatal:`, `error:` or
`ERROR:`, else its last line. `<user>` SHALL be the URL's user (`git` when it has none)
and `-p <port>` SHALL be added for a port.

#### Scenario: An ssh key the host refuses
- **WHEN** git prints `git@github.com: Permission denied (publickey).`
- **THEN** the kind is `ssh_denied` with the hint `ssh -T git@github.com`

#### Scenario: A private https repository without a login
- **WHEN** the URL is `https://github.com/acme/private` and git cannot read a username
- **THEN** the kind is `login_needed` with the hint `gh auth login`, and LADO did not wait

#### Scenario: A repository GitHub does not show
- **WHEN** git prints `ERROR: Repository not found.`
- **THEN** the kind is `not_found` with the hint `gh auth status`

### Requirement: A clone is complete or not there

LADO SHALL clone one branch (`git clone --branch <b> --progress`, all its history, no
submodules) into a temporary folder `.<name>.clone-<random>` beside the target, and
rename it to the target only when git succeeded (onto a missing or empty folder). A
cancelled or failed clone SHALL stop git's whole process group and remove the temporary
folder; the target SHALL be as it was. While it runs, the clone SHALL report git's phase,
its percent and the rest of its line (`Receiving objects`, `45`, `12.30 MiB | 2.10
MiB/s`).

#### Scenario: Cancel during the clone
- **WHEN** the clone is cancelled while git receives objects
- **THEN** git is stopped, the temporary folder is gone and the target does not exist

#### Scenario: A branch that is not there
- **WHEN** the clone asks for branch `dev` the remote does not have
- **THEN** it is refused as `no branch dev` and nothing is left

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

### Requirement: The New session window clones from a URL

The New session window SHALL have a switch **Folder | Clone from URL** in its Where field.
With Clone from URL it SHALL show a URL field, **Clone into** (the default folder, which
follows the URL until the human edits it) with the target folder's state, **Branch**
(listed by the server half a second after the URL stops changing, `fetching branches…`
meanwhile; the default branch chosen and marked `(default)`; a field that filters as the
human types when there are more than 30), and the folder's Name, Kits, Provider and Permission mode. Its
button **Clone and start** SHALL be on only when the branches are listed and the folder is
`new` or `empty`. A listing failure SHALL show under the URL with its hint and Copy. For
`same_repo` the button SHALL be **Use this clone**, with the note `LADO will use it as it
is: no clone, no pull, no branch switch`; it switches the window to Folder with that
folder and changes nothing on disk. While the clone runs the window SHALL show the phase,
the percent with a bar and the elapsed time, lock its fields, keep its ×, Esc and Cancel
from closing it, and offer **Cancel clone**. After the clone it SHALL start the session
as Start does for a folder; a refused start SHALL switch the window to Folder with the
cloned folder and show the refusal there.

#### Scenario: Branches come by themselves
- **WHEN** the human types a URL and stops
- **THEN** the Branch field lists the remote's branches with the default one chosen, and
  Clone and start turns on

#### Scenario: The window cannot be closed during a clone
- **WHEN** a clone runs and the human presses Esc or ×
- **THEN** the window stays; only Cancel clone ends the clone

#### Scenario: A name taken after the clone
- **WHEN** the clone ends and the start is refused because the name is taken
- **THEN** the window shows Folder with the cloned folder and the refusal, and the clone
  stays

### Requirement: The server runs a clone as a job its window keeps alive

The server SHALL offer `POST /api/remote-branches` (`{url}` → `RemoteInfo`), `GET
/api/clone-target?url=&path=` (`CloneTarget`, `path` defaulting to the default folder),
`POST /api/clones` (`{url, path, branch}` → `CloneJob`), `GET /api/clones/{id}`,
`DELETE /api/clones/{id}` and `POST /api/clones/{id}/cancel` (the same cancel, for a
beacon); the POSTs and the DELETE under `Guard.changes`, the GET behind the token. A
refusal SHALL be 400 `CloneRefused` (`message`, `kind`, `hint`), a second clone into the
same folder 409, an unknown job 404, never a 500. When the window's page goes away (tab
closed or reloaded) while its clone runs, the window SHALL cancel the clone at once with
`navigator.sendBeacon` to the cancel route, from the very change of the page that first
shows the clone running until the change that shows its end, and send no beacon after
that. A job no request asked about for
`clone.ABANDONED` seconds (150: longer than the minute a browser may leave between the
timers of a tab in the background) SHALL be cancelled as Cancel clone does; a finished
job SHALL be kept `clone.KEPT` seconds (60). A server that stops SHALL cancel its running
clones.

#### Scenario: A tab closed or reloaded during the clone
- **WHEN** a clone runs and its window's page goes away
- **THEN** the window's beacon cancels it at once and the temporary folder is removed

#### Scenario: A tab closed the moment the clone shows running
- **WHEN** the window's page goes away at the very change that first shows the clone
  running (Cancel clone)
- **THEN** the window's beacon cancels it, and a page that goes away at the change that
  shows the clone's end sends no beacon

#### Scenario: A window that went away
- **WHEN** a clone runs and nobody asks `GET /api/clones/{id}` for `ABANDONED` seconds
- **THEN** the server cancels it and removes the temporary folder

#### Scenario: Two clones into one folder
- **WHEN** `POST /api/clones` names a folder another running job clones into
- **THEN** it answers 409
