# git-servers-page Specification

## Purpose
Settings → Git servers: the human's GitLab and GitHub Enterprise servers seen, added and
removed from the web UI with the rules of `lado git-server`, and the server API it uses,
which takes a token only in a request's body and never gives it back.

## Requirements

### Requirement: The page lists the saved git servers as the command does

Settings → Git servers SHALL list every saved git server, asking none of them, with the same
facts as `lado git-server list`: its address, its kind, the login seen when it was added or
last checked, `⚠ not checked` for one saved without a check, and `⚠ token missing` when its
token file is. The ⓘ beside the heading `Servers` SHALL say that running agents get a change
after their restart.

#### Scenario: Two servers
- **WHEN** `https://gitlab.com` (GitLab, `alex`) and `https://git.corp.example` (GitHub, saved
  without a check) are saved and the human opens Settings → Git servers
- **THEN** the page shows both rows, `signed in as alex` and `⚠ not checked`, and each address,
  kind and login is the one `lado git-server list` prints

#### Scenario: None saved
- **WHEN** no git server is saved
- **THEN** the page shows `No git servers yet.` and `+ Add server`, and opening it makes no
  lado.db

### Requirement: The add form starts with gitlab.com

`+ Add server` SHALL open a form with Address and Token; Address SHALL hold
`https://gitlab.com`, selected so that typing replaces it, while no server of gitlab.com is
saved, and be empty otherwise.

#### Scenario: gitlab.com saved already
- **WHEN** `https://gitlab.com` is saved and the human presses `+ Add server`
- **THEN** Address is empty and focused

### Requirement: The add form checks the address without the token

Once the typing settles the page SHALL check the address without the token, at most 5 s a
request, saying `Checking…` meanwhile: the command's refusals of the address, the plain-http
warning `⚠ Plain http://: the token travels unencrypted.` with an ⓘ, and `<Kind> answers.`
for the kind the server's answer without a token looks like. That kind SHALL be a hint only,
and SHALL choose Token's link: the kind's token page on that server and the rights the token
needs.

#### Scenario: gitlab.com
- **WHEN** no gitlab.com server is saved and the human presses `+ Add server`
- **THEN** Address holds `https://gitlab.com`, the line says `GitLab answers.`, and Token's
  link is `https://gitlab.com/-/user_settings/personal_access_tokens` with the scopes
  `read_repository, write_repository, read_api`

#### Scenario: github.com
- **WHEN** the human types `github.com` in Address
- **THEN** `github.com uses the GitHub CLI's login: it is not added here.` shows under
  Address, and Add server is off

#### Scenario: Plain http
- **WHEN** the human types `http://git.lab.example`
- **THEN** `⚠ Plain http://: the token travels unencrypted.` shows first under Address, and
  Add server stays possible

### Requirement: Add server saves as lado git-server add does

Add server SHALL send the address, the token and the kind chosen, if any; LADO SHALL check and
save the server with `lado git-server add`'s rules, each request at most 5 s, the button
saying `Checking the token…` meanwhile. The form SHALL close and the new server's row stand
open in its place, the focus on its head, its panel starting with `✓ Saved: <Kind>, signed in
as <login>.` (`✓ Saved without a check as <Kind>.` for one saved without a check).

#### Scenario: A server of the human's own
- **WHEN** the human adds `git.corp.example`, which answers as GitHub, with a token it accepts
- **THEN** the row `https://git.corp.example`, GitHub, `Signed in as <login>` shows open, and
  `lado git-server list` prints the same server

### Requirement: A refusal shows under its field in the page's words

A refusal of Add SHALL show under the field it concerns (Address, Token or Kind; one of none
under the buttons) in the page's words with no command in them; a refused token as `<Kind>
refused this token: copy it whole or make a new one.`; the form SHALL keep the address and
the kind and empty the token, unless the token itself was refused.

#### Scenario: A wrong token
- **WHEN** the server refuses the token
- **THEN** `GitLab refused this token: copy it whole or make a new one.` shows under Token with
  the token page link and its scopes, and nothing is saved

### Requirement: The kind is chosen by hand only for a server that cannot be told

The form SHALL show a choice of the kind (GitHub, GitLab), none chosen, only when the address
check finds that the server does not answer or answers as neither kind or as both, saying
`⚠ No answer in 5 seconds. Choose its kind to save it without a check.` for one that does not
answer; Add SHALL then be `Add without a check`, off until a kind is chosen, and save the
server as `--kind` does, its row saying `⚠ not checked`. A server that sends elsewhere SHALL
be refused with no choice.

#### Scenario: A server that does not answer
- **WHEN** the human types an address whose server does not answer in 5 s
- **THEN** the warning says it does not answer, the choice of the kind shows, and after
  choosing GitLab and a token, `Add without a check` saves it as not checked

#### Scenario: A server that sends elsewhere
- **WHEN** the address answers with a redirect
- **THEN** the refusal says where it sends and to give the server's own address, and no
  choice of the kind shows

### Requirement: Remove asks first

`Remove server` at the foot of a server's panel SHALL ask in its place, `Remove <address>?`,
`Its token and commit author go too. This cannot be undone.`, with Remove server and Cancel
(the focus on Cancel); Remove server SHALL remove the server as `lado git-server remove` does
and leave `Removed <address>.` in its place, the focus on `+ Add server`.

#### Scenario: Removing a server
- **WHEN** the human removes `https://git.corp.example` and confirms
- **THEN** its row says `Removed https://git.corp.example.`, `lado git-server list` no longer
  shows it, and its token folder is gone

### Requirement: The token never leaves the request that carries it

The token SHALL reach LADO's server only in the body of `POST /api/git-servers` (Add and
Replace token alike); no answer of the git servers' API, a check's included, no refusal (a
422 included), no log of LADO's server, no file of `LADO_HOME` but the server's token file,
and no part of the page once the save is done SHALL hold it. The token field SHALL be the
project page's secret field, emptied once the save is done or refused for anything but the
token, on Cancel and when the form closes.

#### Scenario: A token through the page
- **WHEN** the human adds a server with a canary token through the page
- **THEN** the canary is in no API answer, not in the page's DOM after the save, not in
  LADO's server log, and in no file of `LADO_HOME` but the token file

#### Scenario: A token replaced and checked
- **WHEN** the human replaces a server's token with a canary and then presses `Check`
- **THEN** the canary is in no API answer, not in the page's DOM, and not in LADO's server
  log

### Requirement: A server's commit author is set and removed on its row

The Commit author row of a server's panel SHALL open with `Set author` or `Edit` a form under
it with Name and Email (the saved author, else empty), Save author and Cancel, which set the
author as `lado git-server author` does, its refusals under Name or Email; done, it SHALL say
`✓ Author saved.`, the focus on `Edit`. `Remove` SHALL clear the author at once. A closed row
with an author SHALL show `commits as <name> <<email>>`.

#### Scenario: Setting an author
- **WHEN** the human presses `Set author` on `https://gitlab.corp.example`, types `Ivan Petrov`
  and `ivan.petrov@corp.example` and presses Save author
- **THEN** the form closes, `✓ Author saved.` shows, the row's value is `Ivan Petrov
  <ivan.petrov@corp.example>`, and `lado git-server list` prints the same author

#### Scenario: A wrong email
- **WHEN** the human types `ivan.petrov` in Email and
  presses Save author
- **THEN** `not an email address: name@host` shows under Email and nothing is saved

#### Scenario: Removing it
- **WHEN** the human presses `Remove` on the commit author of a server with one
- **THEN** the value is `Your own git author`, and `lado git-server list` prints `-` for its
  author

### Requirement: A server's row opens to its panel

A server's row SHALL be one button, named by the address, that opens and closes its panel:
the address whole, the kind and `plain http` for an http address; then the first of `✕ check
failed: <reason>` (after a failed Check of this visit), `⚠ check: no answer`, `⚠ token
missing`, `⚠ not checked`, `signed in as <login>`; then `commits as <name> <<email>>` when an
author is set. An open row SHALL hide those last two lines, its panel saying the same.

#### Scenario: A closed row
- **WHEN** `https://gitlab.corp.example` (GitLab, `a.sample`, author `Sample Name
  <sample.name@corp.example.com>`) is saved
- **THEN** its closed row shows the address, `GitLab`, `signed in as a.sample` and `commits as
  Sample Name <sample.name@corp.example.com>`

### Requirement: A server's panel has Sign-in, Commit author and Remove server

An open panel SHALL show Sign-in (`Signed in as <login>`, `⚠ Not checked` or `⚠ Token
missing`, with `Check` and `Replace token`, or `Replace token` alone as the main button when
the token is missing), Commit author (`<name> <<email>>` with `Edit` and `Remove`, or `Your
own git author` with `Set author`) and a foot with `Remove server`. Each button's accessible
name SHALL carry the address (`Check <address>`, `Replace the token of <address>`).

#### Scenario: An open server
- **WHEN** the human presses the row of `https://gitlab.corp.example` (GitLab, `a.sample`,
  author `Sample Name <sample.name@corp.example.com>`)
- **THEN** its panel shows `Signed in as a.sample` with `Check` and `Replace token`, `Sample
  Name <sample.name@corp.example.com>` with `Edit` and `Remove`, and `Remove server`

#### Scenario: A missing token
- **WHEN** the server's token file is missing
- **THEN** the closed row says `⚠ token missing`, and the open panel's Sign-in offers
  `Replace token` alone, as its main button

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
  revoked.` [Replace token], `The token lacks <scopes>.` ⓘ [Replace token], `⚠ No answer in 5
  seconds.` (`⚠ No answer: <why>.` for another reason) ⓘ [Check again], `The server's
  certificate is not trusted.` ⓘ [Check again], `It redirects to <target>: add that address
  instead.`, `It answers as <Kind>, not <saved Kind>: remove it and add it again., `It answers as neither GitHub
  nor GitLab.`

#### Scenario: An expired token
- **WHEN** the human presses `Check` on a GitLab server whose token the server refuses
- **THEN** `GitLab refused the token: it expired or was revoked.` shows under Sign-in with
  `Replace token`, and the closed row says `✕ check failed: token refused`

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
  agents can clone but not push.` with `Replace token`

### Requirement: Replace token saves without a check under the saved kind

When the server does not answer while a new token is checked, the Replace token form SHALL
save nothing yet and say `⚠ No answer in 5 seconds: save it without a check, as <Kind>.` with
`Save without a check`, which SHALL save the token under the server's saved kind as `--kind`
does, the server then `⚠ not checked`.

#### Scenario: The server does not answer
- **WHEN** the server does not answer while the token is checked
- **THEN** nothing is saved yet, the form offers `Save without a check`, and pressing it
  saves the token, the row then saying `⚠ not checked`

### Requirement: Explanations stand behind ⓘ buttons

The page SHALL keep why and what happens later behind ⓘ buttons (the shared info tip),
never the only way to act; each ⓘ SHALL stand beside its heading or label, not inside it, be
named `About <what it explains>` (`About Servers`, `About the missing scope`, `About the
certificate`), keep its phone hit area off the field below, and the Token tip SHALL leave the
token page link visible.

#### Scenario: The Servers tip
- **WHEN** the human presses the ⓘ beside `Servers`
- **THEN** a tip says agents clone and push with the token given and that running agents get
  a change after they restart, and the focus stays on the ⓘ

#### Scenario: The Token tip on a phone
- **WHEN** the page is 390 pixels wide and the human opens the ⓘ of Token
- **THEN** the token page link stays visible and can be pressed, and pressing the ⓘ never
  focuses the field

### Requirement: The page shows one result at a time and moves the focus by rule

The page SHALL show at most one result line (a save, a check, a removal, an author line with
`Undo`); any next action on the page SHALL remove the previous one; opening or closing a
panel SHALL not count as an action. The focus SHALL go: a form opened → its first field;
Cancel or Esc → the button that opened it; a save → that button (a new server → its row);
an author removed → `Undo`, after Undo → `Edit`; a server removed → `+ Add server`; Replace
its token from Add → the New token field.

#### Scenario: A check after a save
- **WHEN** `✓ Token replaced: …` shows and the human presses `Check` on another server
- **THEN** only that check's result shows on the page

### Requirement: The page has one form open at a time

At most one form SHALL be open on the page: opening the add form SHALL close a panel's
form, and opening a panel's form SHALL close the add form; open panels SHALL stay open.

#### Scenario: One form at a time
- **WHEN** the add form is open and the human presses `Replace token` in an open panel
- **THEN** the add form closes and the Replace token form opens; the panel stays open

### Requirement: Add leads an address already saved to its server

For an address already saved the add form SHALL say `Already saved.` with `Replace its
token`, Add server off; `Replace its token` SHALL close the form and open that server's
Replace token.

#### Scenario: An address already saved
- **WHEN** `https://gitlab.corp.example` is saved and the human types `gitlab.corp.example`
- **THEN** `Already saved.` shows with `Replace its token`, Add server is off, and `Replace
  its token` closes the form and opens that server's Replace token, the focus in New token

### Requirement: A saved token without a right agents need is shown with a warning

When Add saves a token that lacks a right agents need, the new server's panel SHALL start with
`⚠ The token lacks <scopes>: agents can clone but not push.` (`…neither clone nor push.`
without the read right) and `Replace token`, as Replace token's result does.

#### Scenario: A token without the push right
- **WHEN** the human adds a GitLab server with a token whose scopes are `read_repository,
  read_api`
- **THEN** the server is saved and its panel starts with `⚠ The token lacks
  write_repository: agents can clone but not push.` and `Replace token`

### Requirement: Add offers the kind when the server stops answering

When the server answered the address check but gives no answer at Add, Add's refusal SHALL
carry `choose_kind`, and the form SHALL say `⚠ It stopped answering when you pressed Add.`
with `Try again` and the choice of the kind, the token kept.

#### Scenario: A server that stops answering at Add
- **WHEN** the server answered the address check and does not answer when the human presses
  Add server
- **THEN** `⚠ It stopped answering when you pressed Add.` shows with `Try again` and the
  choice of the kind, and the token stays in its field

### Requirement: Removing a commit author can be undone

`Remove` on a commit author SHALL say `✓ Author removed.` with `Undo`, the focus on Undo;
`Undo` SHALL set the same name and email again through the author's API and say `✓ Author
saved.`, the focus on `Edit`; Undo SHALL go with the next action on the page.

#### Scenario: Undo
- **WHEN** the human presses `Undo` after removing the author
- **THEN** the author is set again, `✓ Author saved.` shows, and the focus is on `Edit`
