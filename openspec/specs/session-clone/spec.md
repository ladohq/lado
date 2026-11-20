# session-clone Specification

## Purpose
A LADO session from a repository's git URL: the clone of one branch into a chosen folder
(by default `<workspace>/<repo>`) behind `lado start <git-url>` and the New session window's
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

### Requirement: The target folder is checked before any clone

Before it lists branches or clones, LADO SHALL check the target folder and give one of
these states; only `new` and `empty` SHALL let a clone start, and LADO SHALL change
nothing in a folder of another state:

| State | When | Text |
|---|---|---|
| `new` | the path does not exist | `a new folder` |
| `empty` | an empty folder | `an empty folder` |
| `not_empty` | anything else in a folder | `<path> is not empty and is not a clone of <url>: choose another folder` |

#### Scenario: A folder with other files
- **WHEN** the folder holds files and is no repository root
- **THEN** the state is `not_empty` and no clone starts

### Requirement: A file is no target of a clone

The target folder's check SHALL also give this state, which lets no clone start:

| State | When | Text |
|---|---|---|
| `not_folder` | a file | `<path> is a file, not a folder` |

#### Scenario: A file as the target
- **WHEN** the target path is a file
- **THEN** the state is `not_folder` with `<path> is a file, not a folder`, and no clone
  starts

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

### Requirement: Two addresses are the same repository by host and path

Two addresses SHALL be the same repository when their host (lowercased) and their path
(without a leading or trailing `/`, a trailing `.git`, and for scp form the part before
`:`) are equal; the scheme, the user and the port SHALL NOT count. Two `file://` URLs or
paths SHALL compare by real path.

#### Scenario: The same repository over another protocol
- **WHEN** the folder's origin is `git@github.com:ladohq/lado.git` and the URL is
  `https://github.com/ladohq/lado`
- **THEN** the state is `same_repo`, naming its branch

### Requirement: A clone of another repository suggests a free folder

For `other_repo`, when the URL's path has an owner segment and `<parent>/<owner>-<repo>`
(`<parent>` the given folder's parent) is `new`, the text SHALL end with `, e.g. <that
folder>`.

#### Scenario: The suggested folder is taken too
- **WHEN** the folder `~/workspace/app` is a clone of `git@github.com:acme/app.git`, the
  URL is `git@github.com:ladohq/app.git`, and `~/workspace/ladohq-app` exists
- **THEN** the state is `other_repo` and its text suggests no folder

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
`GCM_INTERACTIVE=never`, `LC_ALL=C`), in the environment of LADO's own git calls
(capability `agent-variables`), so a missing credential is a failure, never a wait. LADO
SHALL neither ask for nor keep a password, passphrase or token.

#### Scenario: A private https repository without a login
- **WHEN** the URL is `https://github.com/acme/private`, github.com has no entry, and git
  cannot read a username
- **THEN** the kind is `login_needed` with the hint `lado git-server add
  https://github.com --token`, and LADO did not wait

### Requirement: A failed clone or listing is told by its kind with git's line

A failure SHALL be told as `cannot read <url>: <reason> (<git's
line>)` for a listing and `cannot clone <url>: <reason> (<git's line>)` for a clone, by
kind. git missing or not running SHALL be LAD-5's `no_git` / `git_broken` text and hint.
`<git's line>` SHALL be git's first error line that starts with `fatal:`, `error:` or
`ERROR:`, else its last line. In a hint, `<user>` SHALL be the URL's user (`git` when it
has none) and `-p <port>` SHALL be added for a port.

#### Scenario: git's line among others
- **WHEN** a listing fails and git printed a progress line, then a `fatal:` line, then a
  `hint:` line
- **THEN** the failure's text ends with the `fatal:` line in parentheses

### Requirement: An ssh failure says how to check the key or the host key

Outside LADO's container the ssh kinds of failure SHALL be:

| Kind | Reason | Hint (sentence: command) |
|---|---|---|
| `ssh_denied` | `<host> refused this machine's ssh key` | `Check that this machine's ssh key is added to your account on <host>:` `ssh -T <user>@<host>` |
| `host_key` | `this machine does not know <host>'s ssh host key yet` | `Connect once in a terminal and accept the host key:` `ssh -T <user>@<host>` |

#### Scenario: An ssh key the host refuses
- **WHEN** git prints `git@github.com: Permission denied (publickey).`
- **THEN** the kind is `ssh_denied` with the hint `ssh -T git@github.com`

### Requirement: A login or access failure points at the machine's login

The login and access kinds SHALL be `login_needed` (`<host> asks for a login`),
`access_denied` (`<host> refused access`) and `not_found` (`no repository there, or this
machine's account cannot read it`), with no hint, but where a git server's text of this
capability applies, github.com's included.

#### Scenario: A repository GitHub does not show
- **WHEN** git prints `ERROR: Repository not found.` for github.com with no entry
- **THEN** the kind is `not_found` with no hint

#### Scenario: GitHub refuses access
- **WHEN** a listing of `https://github.com/acme/app` fails with git's `The requested URL
  returned error: 403` and github.com has no entry
- **THEN** the kind is `access_denied`, the reason `github.com refused access`, with the
  hint `Add it as a git server with a token:` `lado git-server add https://github.com --token`

### Requirement: Other failures of a clone carry no hint

The other kinds of failure SHALL be:

| Kind | Reason | Hint (sentence: command) |
|---|---|---|
| `unreachable` | `<host> cannot be reached` | none |
| `no_branch` | `no branch <b>` | none |
| `git_failed` | git's line alone | none |

#### Scenario: A host that cannot be reached
- **WHEN** a listing of `https://git.acme.org/app` fails because the host cannot be reached
- **THEN** the text is `cannot read https://git.acme.org/app: git.acme.org cannot be
  reached (<git's line>)`, with no hint

### Requirement: A clone is complete or not there

LADO SHALL clone one branch (`git clone --branch <b> --progress`, all its history, no
submodules) into a temporary folder `.<name>.clone-<random>` beside the target, and
rename it to the target only when git succeeded (onto a missing or empty folder). A
cancelled or failed clone SHALL stop git's whole process group and remove the temporary
folder; the target SHALL be as it was.

#### Scenario: Cancel during the clone
- **WHEN** the clone is cancelled while git receives objects
- **THEN** git is stopped, the temporary folder is gone and the target does not exist

#### Scenario: A branch that is not there
- **WHEN** the clone asks for branch `dev` the remote does not have
- **THEN** it is refused as `no branch dev` and nothing is left

### Requirement: A running clone reports git's progress

While it runs, the clone SHALL report git's phase,
its percent and the rest of its line (`Receiving objects`, `45`, `12.30 MiB | 2.10
MiB/s`).

#### Scenario: Receiving objects
- **WHEN** git reports that it receives objects at 45%, 12.30 MiB so far at 2.10 MiB/s
- **THEN** the clone reports `Receiving objects`, `45` and `12.30 MiB | 2.10 MiB/s`

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

### Requirement: lado start refuses a target or a name before the clone

A folder that is not
`new` or `empty` SHALL be refused by `lado start <git-url>` with its text and nothing cloned; for `same_repo` the
next line SHALL be `lado: To start a session in it as it is: lado start <folder>`. A name
held by a session of another folder, and whatever else the new session's start would refuse
(capability session-scratch: "A new session is checked whole before its folder is made"),
SHALL be refused before the clone.

#### Scenario: The clone is there already
- **WHEN** `LADO_REPOS` is unset, `~/workspace/lado` is a clone of
  `https://github.com/ladohq/lado` and `lado start git@github.com:ladohq/lado.git` runs
- **THEN** it exits 1 printing the `same_repo` text and `lado start ~/workspace/lado`, and
  changes nothing

#### Scenario: A kit's refusal before the clone
- **WHEN** `lado start https://github.com/ladohq/lado --kit sdlc` runs and no kit gives the skill `tracker`
- **THEN** it exits 1 with the kit's refusal, and nothing is cloned

### Requirement: lado start ends its clone cleanly on a signal or a refused start

Ctrl-C during the
clone of `lado start` SHALL cancel it, print `lado: clone cancelled` and exit 130; a SIGTERM or SIGHUP
during the clone SHALL cancel it the same way and exit 128 plus its number. A refused
start after
the clone SHALL keep the clone and say `lado: the clone stays in <folder>`.

#### Scenario: Ctrl-C during the clone
- **WHEN** the human presses Ctrl-C while `lado start <git-url>` clones
- **THEN** it prints `lado: clone cancelled`, exits 130, and the target is as it was

### Requirement: The New session window clones from a URL

The New session window SHALL offer a clone as **Clone from URL…** in Where's group Somewhere
else (capability new-session-window). Its button **Clone and start in <folder>** SHALL be on
only when the branches are listed and the folder is `new` or `empty`. A listing failure SHALL
show under Repository URL with its hint and Copy, or with its git server's way out.

#### Scenario: A listing that fails
- **WHEN** the listing of the URL fails as `ssh_denied`
- **THEN** its text and the hint `ssh -T git@github.com` show under Repository URL with
  Copy, and Clone and start is off

### Requirement: Clone from URL shows the URL, the folder, the branch and the session's settings

With Clone from URL the window SHALL show **Repository URL** (`✓ Found` once listed), **Branch**
(listed by the server half a second after the URL stops changing, `fetching branches…`
meanwhile; the default branch chosen and marked `(default)`; a filtering field above 30
branches), **Clone into** (the default folder until edited, with its state: `✓ New folder`,
`✓ Empty folder` or the refusal), then Task and Team as for a folder.

#### Scenario: Branches come by themselves
- **WHEN** the human types a URL and stops
- **THEN** the Branch field lists the remote's branches with the default one chosen, and
  Clone and start turns on

### Requirement: Use this clone takes a clone that is there as it is

For `same_repo` the button SHALL be **Use this clone**, with the note `LADO will use it as it
is: no clone, no pull, no branch switch`; it turns Where to that folder and changes nothing
on disk.

#### Scenario: A clone that is there
- **WHEN** Clone into is a clone of the same repository and the human presses Use this
  clone
- **THEN** Where shows that folder, and nothing on disk changed

### Requirement: The window shows a running clone and cannot be closed by mistake

While the clone runs the window SHALL show the phase,
the percent with a bar and the elapsed time, lock its fields, keep its ×, Esc and Cancel
from closing it, and offer **Cancel clone**.

#### Scenario: The window cannot be closed during a clone
- **WHEN** a clone runs and the human presses Esc or ×
- **THEN** the window stays; only Cancel clone ends the clone

### Requirement: After the clone the window starts the session

After the clone the window SHALL start the session as it does for a folder; a refused start
SHALL turn Where to the cloned folder and show the refusal there.

#### Scenario: A name taken after the clone
- **WHEN** the clone ends and the start is refused because the name is taken
- **THEN** Where shows the cloned folder with the refusal, and the clone stays

### Requirement: The server runs a clone as a job its window keeps alive

The server SHALL offer `POST /api/remote-branches` (`{url}` → `RemoteInfo`), `GET
/api/clone-target?url=&path=` (`CloneTarget`, `path` defaulting to the default folder),
`POST /api/clones` (`{url, path, branch}` → `CloneJob`), `GET /api/clones/{id}`,
`DELETE /api/clones/{id}` and `POST /api/clones/{id}/cancel` (the same cancel, for a
beacon); the POSTs and the DELETE under `Guard.changes`, the GET behind the token.

#### Scenario: A clone asked by the window
- **WHEN** the window posts `{url, path, branch}` to `POST /api/clones`
- **THEN** it gets a `CloneJob`, and `GET /api/clones/{id}` gives that job

### Requirement: The clone routes refuse with a 4xx, never a 500

A refusal of the clone routes SHALL be 400 `CloneRefused` (`message`, `kind`, `hint`), a
second clone into the same folder 409, an unknown job 404, never a 500.

#### Scenario: Two clones into one folder
- **WHEN** `POST /api/clones` names a folder another running job clones into
- **THEN** it answers 409

### Requirement: A page that goes away cancels its clone with a beacon

When the window's page goes away (tab
closed or reloaded) while its clone runs, the window SHALL cancel the clone at once with
`navigator.sendBeacon` to the cancel route, from the very change of the page that first
shows the clone running until the change that shows its end, and send no beacon after
that.

#### Scenario: A tab closed or reloaded during the clone
- **WHEN** a clone runs and its window's page goes away
- **THEN** the window's beacon cancels it at once and the temporary folder is removed

#### Scenario: A tab closed the moment the clone shows running
- **WHEN** the window's page goes away at the very change that first shows the clone
  running (Cancel clone)
- **THEN** the window's beacon cancels it, and a page that goes away at the change that
  shows the clone's end sends no beacon

### Requirement: The server cancels an abandoned clone and keeps a finished one a while

A clone job no request asked about for
`clone.ABANDONED` seconds (150: longer than the minute a browser may leave between the
timers of a tab in the background) SHALL be cancelled as Cancel clone does; a finished
job SHALL be kept `clone.KEPT` seconds (60). A server that stops SHALL cancel its running
clones.

#### Scenario: A window that went away
- **WHEN** a clone runs and nobody asks `GET /api/clones/{id}` for `ABANDONED` seconds
- **THEN** the server cancels it and removes the temporary folder

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

### Requirement: A folder inside LADO's projects/ is no target of a clone

The target folder's check SHALL also give this state, which lets no clone start, checked
before the others:

| State | When | Text |
|---|---|---|
| `in_project` | the folder, by its real path, is inside LADO's `<workspace>/projects` (capability `projects`) | the refusal of a new session there, with its hint |

#### Scenario: A clone into a project's folder
- **WHEN** the target is `<ws>/projects/shop/web`, `shop` is a project and `web` does not
  exist
- **THEN** the state is `in_project`, the text names the project, the hint offers `lado
  project repo add shop <git-url>`, and no clone starts

#### Scenario: A clone into a project's repository
- **WHEN** the target is `<ws>/projects/shop/frontend`, a repository of `shop`
- **THEN** the state is `in_project` and the hint offers `lado start --project shop --repo
  frontend`

### Requirement: A kit's or marketplace's git failure is told by the clone's kinds

A git failure of LADO's network calls for kits, skill packs and marketplaces (a remote's
tags, a pinned clone, a marketplace's clone and update) SHALL be told by the kinds and
texts of a clone's failure, on one line: `<LADO's head>: <reason> (<git's line>)`, then
`. ` and the hint's sentence and command when the kind has one; a failure of no known kind
SHALL keep `<LADO's head>: <git's line>`. These calls SHALL run with the same no-prompt
variables as a clone, and never in a project's layer.

#### Scenario: A private kit without a token
- **WHEN** `lado kits add https://github.com/ladohq/kit-epic.git` runs, github.com has no
  entry, and git cannot read a username
- **THEN** it fails with `cannot read the tags of https://github.com/ladohq/kit-epic.git:
  github.com asks for a login (fatal: could not read Username for 'https://github.com':
  terminal prompts disabled). Add it as a git server with a token: lado git-server add
  https://github.com --token`

#### Scenario: A failure of no known kind
- **WHEN** a kit's pinned clone fails with git's `fatal: bad object` line
- **THEN** the text ends with `: fatal: bad object` and carries no hint

### Requirement: A saved git server's access failure names the server

When the git server saved for the URL's host (the one whose token git takes) is refused
(`login_needed`, `access_denied`, `not_found`), the reason SHALL name the host with its
port and the server, and the hint SHALL give, each on its own line, `Check the git
server:` `lado git-server check <address>` and `If its token expired or was revoked,
replace it:` `lado git-server add <address> --token`.

#### Scenario: A revoked token
- **WHEN** the token of the saved `https://gitlab.corp.example` was revoked and a listing of
  `https://gitlab.corp.example/team/app.git` fails with `Authentication failed`
- **THEN** the text is `cannot read https://gitlab.corp.example/team/app.git:
  gitlab.corp.example refused the token of the git server https://gitlab.corp.example
  (<git's line>)` with the hint `lado git-server check https://gitlab.corp.example`

#### Scenario: A repository the token may not read
- **WHEN** git answers `not found` for a saved server's host
- **THEN** the reason is `no repository there, or the token of the git server <address>
  cannot read it` with the same hint

#### Scenario: An ssh address of a saved server
- **WHEN** `git@gitlab.corp.example:team/app.git` fails with `Authentication failed` and
  `https://gitlab.corp.example` is saved
- **THEN** the hint is `lado git-server check https://gitlab.corp.example`

#### Scenario: A server with a port
- **WHEN** the token of the saved `https://git.test:8443` is refused
- **THEN** the reason starts `git.test:8443 refused the token`, and the hint's two commands
  are on two lines

#### Scenario: github.com saved
- **WHEN** github.com's entry token was revoked and a clone from github.com fails
- **THEN** the hint is `lado git-server check https://github.com` and the replace line

### Requirement: An unsaved host that asks for a login offers to add it

An http(s) URL whose host is no saved server's, refused as `login_needed` or
`access_denied`, SHALL keep its reason and get the hint `Add it as a git server with a
token:` `lado git-server add <scheme>://<host>[:<port>] --token`, github.com's included.
`not_found`, ssh failures and the kinds that are no access failure
SHALL carry no git server hint.

#### Scenario: A login asked for by an unsaved host
- **WHEN** a listing of `https://git.acme.example/team/app.git` fails because git cannot read
  a username, and no server is saved for `git.acme.example`
- **THEN** the reason is `git.acme.example asks for a login` with the hint `lado git-server
  add https://git.acme.example --token`

#### Scenario: An unreachable unsaved host
- **WHEN** the same listing fails because the host cannot be resolved
- **THEN** the text is `… git.acme.example cannot be reached (<git's line>)` with no hint

#### Scenario: A host saved under another scheme
- **WHEN** `https://gitlab.corp.example` is saved and `http://gitlab.corp.example/team/app`
  asks for a login
- **THEN** the failure carries no git server hint, as git takes no saved token for it

#### Scenario: github.com without an entry in the UI
- **WHEN** the New session window's clone of `https://github.com/acme/private` asks for a
  login and github.com has no entry
- **THEN** its note's button opens Settings → Git servers with the Add form's Address
  `https://github.com`

### Requirement: The window's note of a git server opens Settings

Where the UI shows a clone's or listing's failure (the New session window, a project's Add
repository), a git server hint SHALL show its sentence and a button that opens Settings →
Git servers in a new tab: `Check <host> ↗` for a saved server, `Add git server ↗` for an
unsaved host; no command to copy. The window and its fields SHALL stay as they were.

#### Scenario: A saved server's note
- **WHEN** the listing of a saved server's URL fails with a refused token
- **THEN** under Repository URL shows `Check this git server; if its token expired or was
  revoked, replace it there.` and `Check gitlab.corp.example ↗`, which opens
  `/settings/git-servers?check=gitlab.corp.example` in a new tab

#### Scenario: An unsaved host's note
- **WHEN** the listing of `https://git.acme.example/team/app.git` fails asking for a login
- **THEN** the note says `Add git.acme.example as a git server with a token: LADO and its
  agents then sign in to it.` and `Add git server ↗` opens
  `/settings/git-servers?add=https%3A%2F%2Fgit.acme.example` in a new tab

### Requirement: In LADO's container an ssh failure points at the git servers

In LADO's container both ssh kinds of an ssh address of the user `git` on port 22
(`git@<host>:`, `ssh://git@<host>[:22]/`) of a host with no saved git server SHALL say `LADO's container has no ssh key for <host>`, with the hint `Add it
as a git server with a token:` `lado git-server add https://<host> --token` and the UI's
way out `Add git server`: `Add <host> as a git server with a token: its git@ addresses
then go over https too.`

#### Scenario: github.com not saved
- **WHEN** in the container the clone of `git@github.com:acme/app.git` fails with
  `Permission denied (publickey)` or `Host key verification failed` and no github.com entry
  is saved
- **THEN** the reason is `LADO's container has no ssh key for github.com`, the hint is
  `lado git-server add https://github.com --token`, and Clone from URL shows `Add git
  server ↗` opening Settings → Git servers with `https://github.com` in Address

#### Scenario: Outside the container
- **WHEN** the same github.com failure happens outside LADO's container
- **THEN** the kind's reason and hint are those of the ssh kinds' table

### Requirement: In LADO's container another ssh address asks for https

In LADO's container both ssh kinds of any other ssh address (another user or none, a port
other than 22, a host with a saved git server, or saved servers LADO cannot read: lado.db
at another schema) SHALL say `LADO's container has no ssh: clone by the
repository's https address`, with no hint and no way out.

#### Scenario: Another ssh port
- **WHEN** in the container the clone of `ssh://git@git.example:2222/team/app.git` fails
  with `Permission denied (publickey)`
- **THEN** the reason is `LADO's container has no ssh: clone by the repository's https
  address`, with no hint and no way out

### Requirement: An untrusted certificate of a git server points to its check

git's refusal of a server's certificate (OpenSSL's and GnuTLS's words, a certificate of
another host too) SHALL be the kind `cert_untrusted`, `the certificate of <host> is not
trusted`. For a saved server's URL its hint SHALL be `Check the git server and trust its
certificate:` `lado git-server check <address>`, and its UI way out `Check <host> ↗`; for an
unsaved http(s) host, the hint to add it.

#### Scenario: A saved company server
- **WHEN** `https://gitlab.corp.example` is saved without a certificate and a clone of
  `https://gitlab.corp.example/team/app.git` fails with `SSL certificate problem: unable to
  get local issuer certificate`
- **THEN** the text is `cannot clone https://gitlab.corp.example/team/app.git: the
  certificate of gitlab.corp.example is not trusted (<git's line>)` with the hint `lado
  git-server check https://gitlab.corp.example`

#### Scenario: The window's note
- **WHEN** the same failure shows in the New session window
- **THEN** the note says `Check the git server and trust its certificate there.` and
  `Check gitlab.corp.example ↗` opens `/settings/git-servers?check=gitlab.corp.example`

#### Scenario: An unsaved host
- **WHEN** a clone of `https://git.lab.example/app.git`, no saved server's, fails the same way
- **THEN** the hint is `Add it as a git server with a token:` `lado git-server add
  https://git.lab.example --token`
