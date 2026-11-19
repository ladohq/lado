## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: A GitHub login hint names where LADO can take a token

**Reason**: the GitHub login lives only in the github.com entry; a project's `GH_TOKEN`,
the outside folder's and `gh auth login` are no longer used.
**Migration**: the hint of an unsaved host (`lado git-server add https://github.com
--token`) or of a saved server.
