## MODIFIED Requirements

### Requirement: Check on the panel checks the server again

`Check` SHALL check the server as `lado git-server check` does, through `POST
/api/git-servers/{host}/check`, the button off and `Checking…` under Sign-in meanwhile, and
show the result there in one line with its way out at the end; a server that works SHALL be
a status, any other outcome an alert; the closed row's second line SHALL follow the result
for this visit.

#### Scenario: The lines of the outcomes
- **WHEN** a check ends
- **THEN** its line is one of `Works: signed in as <login>, may clone and push.`, `Works:
  <Kind>, signed in as <login>.` (a server that was not checked), `Works: signed in as
  <login>; the token's rights are not checked.`, `<Kind> refused the token: it expired or was
  revoked.`, `The token lacks <scopes>.` ⓘ, `⚠ No answer in 5 seconds.` (`⚠ No answer:
  <why>.` for another reason) ⓘ [Check again], `The server's certificate is not trusted.` ⓘ
  [Check again], `It redirects to <target>: add that address instead.`, `It answers as
  <Kind>, not <saved Kind>: remove it and add it again.`, `It answers as neither GitHub nor
  GitLab.`; a `Works:` line has no `✓` before it

#### Scenario: An expired token
- **WHEN** the human presses `Check` on a GitLab server whose token the server refuses
- **THEN** `GitLab refused the token: it expired or was revoked.` shows under Sign-in with
  no button of its own, Sign-in's `Replace token` becomes its main button, and the closed row
  says `✕ check failed: token refused`

#### Scenario: An untrusted certificate
- **WHEN** the check finds the server's certificate not trusted
- **THEN** the line `The server's certificate is not trusted.` has an ⓘ `About the
  certificate` whose text says to ask the IT department to make LADO's computer trust it
  (with LADO in Docker, its container) and then check again, and a `Check again` button

#### Scenario: A server saved without a check now answers
- **WHEN** the human presses `Check` on a server that says `⚠ not checked` and it works,
  signed in as `a.sample`
- **THEN** the line says `Works: GitLab, signed in as a.sample.`, and the row says
  `signed in as a.sample` after the page is opened again

### Requirement: Replace token replaces a saved server's token

`Replace token` SHALL open under Sign-in a form with New token, `Make one on its token page
with the scopes <scopes>.`, `Save token` and `Cancel`, and send the saved address and the
token to `POST /api/git-servers`. Done, it SHALL close with `✓ Token replaced: signed in as
<login>.`, plus `⚠ Before, it was <old>.` with an ⓘ when the login changed; a refused token
SHALL show `<Kind> refused this token: copy it whole or make a new one.`, the token kept.

#### Scenario: A new token
- **WHEN** the human replaces the token of `https://gitlab.corp.example` with one the server
  accepts as `a.sample`
- **THEN** `Save token` says `Checking the token…` meanwhile, the form closes, `✓ Token
  replaced: signed in as a.sample.` shows, and the focus is on `Replace token`

#### Scenario: A token without the push right
- **WHEN** the new token lacks `write_repository`
- **THEN** the token is saved, and the result line is `⚠ The token lacks write_repository:
  agents can clone but not push.`, with Sign-in's `Replace token` as the main button

## ADDED Requirements

### Requirement: A refused or short token leaves one Replace token

A result line of a server's panel that says its token is refused or lacks a right SHALL
carry no button of its own; while it shows, Sign-in's `Replace token` SHALL be the main
button, so the panel offers one `Replace token`.

#### Scenario: A scope missing
- **WHEN** a check says `The token lacks write_repository.`
- **THEN** the panel shows exactly one button named `Replace the token of <address>`, and it
  is the main button

#### Scenario: Saved with a token without the push right
- **WHEN** Add or Replace token saves a token that lacks `write_repository`
- **THEN** the warning line has no button, and Sign-in's `Replace token` is the main button

### Requirement: The page opens a server from its address

`/settings/git-servers?check=<host>` SHALL open that saved server's panel and check it at
once; `?add=<address>` SHALL open the add form with that address, checked as typed, the focus
in Token. The page SHALL then drop the query from the address bar; a host no server is saved
for SHALL open nothing.

#### Scenario: Opened to check a server
- **WHEN** the human opens `/settings/git-servers?check=gitlab.corp.example`
- **THEN** that server's panel is open with `Checking…` under Sign-in, then its check's line,
  and the address bar shows `/settings/git-servers`

#### Scenario: Opened to add a server
- **WHEN** the human opens `/settings/git-servers?add=https%3A%2F%2Fgit.acme.example`
- **THEN** the add form shows Address `https://git.acme.example` with its kind's line, and
  the focus is in Token

### Requirement: An open info tip stays by its button when the layout changes

An open ⓘ tip SHALL stay beside its button when the page switches between the phone and the
wide layout (a phone turned, a window resized across the limit).

#### Scenario: A phone turned
- **WHEN** the Token tip is open at 390 pixels wide and the window becomes 900 pixels wide
- **THEN** the tip stands beside the Token ⓘ in its new place

### Requirement: The author's Remove and Undo are off while they ask

The commit author's `Remove` and its line's `Undo` SHALL be off while their request runs.

#### Scenario: A slow removal
- **WHEN** the human presses `Remove` and the server has not answered yet
- **THEN** `Remove` is off and a second press sends nothing
