## MODIFIED Requirements

### Requirement: A login or access failure points at the machine's login

The login and access kinds SHALL be `login_needed` (`<host> asks for a login`; github.com:
where LADO can take a token), `access_denied` (`<host> refused access`; github.com: `gh auth
status`) and `not_found` (`no repository there, or this machine's account cannot read it`;
github.com: `gh auth status`), other hosts with no hint, but where a git server's text of
this capability applies.

#### Scenario: A repository GitHub does not show
- **WHEN** git prints `ERROR: Repository not found.`
- **THEN** the kind is `not_found` with the hint `gh auth status`

#### Scenario: GitHub refuses access
- **WHEN** a listing of `https://github.com/acme/app` fails with git's `The requested URL
  returned error: 403`
- **THEN** the kind is `access_denied`, the reason `github.com refused access`, with the
  hint `See which GitHub account this machine uses:` `gh auth status`

### Requirement: The New session window clones from a URL

The New session window SHALL offer a clone as **Clone from URL…** in Where's group Somewhere
else (capability new-session-window). Its button **Clone and start in <folder>** SHALL be on
only when the branches are listed and the folder is `new` or `empty`. A listing failure SHALL
show under Repository URL with its hint and Copy, or with its git server's way out.

#### Scenario: A listing that fails
- **WHEN** the listing of the URL fails as `ssh_denied`
- **THEN** its text and the hint `ssh -T git@github.com` show under Repository URL with
  Copy, and Clone and start is off

## ADDED Requirements

### Requirement: A saved git server's access failure names the server

When the git server saved for the URL's host (the one whose token git takes) is refused
(`login_needed`, `access_denied`, `not_found`), the reason SHALL name the server, and the
hint SHALL be `Check the git server; if its token expired or was revoked, replace it
(lado git-server add <address> --token):` `lado git-server check <address>`.

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

### Requirement: An unsaved host that asks for a login offers to add it

An http(s) URL whose host is neither github.com nor any saved server's, refused as
`login_needed` or `access_denied`, SHALL keep its reason and get the hint `Add it as a git
server with a token:` `lado git-server add <scheme>://<host>[:<port>] --token`.
`not_found`, ssh failures and the kinds that are no access failure SHALL carry no git server
hint.

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
