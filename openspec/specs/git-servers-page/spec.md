# git-servers-page Specification

## Purpose
Settings → Git servers: the human's GitLab and GitHub Enterprise servers seen, added and
removed from the web UI with the rules of `lado git-server`, and the server API it uses,
which takes a token only in a request's body and never gives it back.

## Requirements

### Requirement: The page lists the saved git servers as the command does

Settings → Git servers SHALL list every saved git server, asking none of them, with the same
facts as `lado git-server list`: its address, its kind, the login seen when it was added or
`⚠ not checked` for one saved without a check, and `⚠ its token file is missing` when it is.
The section's lead SHALL say that running agents get a change after their restart.

#### Scenario: Two servers
- **WHEN** `https://gitlab.com` (GitLab, `alex`) and `https://git.corp.example` (GitHub, saved
  without a check) are saved and the human opens Settings → Git servers
- **THEN** the page shows both rows, `signed in as alex` and `⚠ not checked`, and each address,
  kind and login is the one `lado git-server list` prints

#### Scenario: None saved
- **WHEN** no git server is saved
- **THEN** the page shows no row and `+ Add server`, and opening it makes no lado.db

### Requirement: The add form starts with gitlab.com

`+ Add server` SHALL open a form with Address and Token; Address SHALL hold
`https://gitlab.com`, selected so that typing replaces it, while no server of gitlab.com is
saved, and be empty otherwise.

#### Scenario: gitlab.com saved already
- **WHEN** `https://gitlab.com` is saved and the human presses `+ Add server`
- **THEN** Address is empty and focused

### Requirement: The add form checks the address without the token

Once the typing settles the page SHALL check the address without the token, at most 5 s a
request, saying `checking <address> …` meanwhile: the command's refusals of the address, the
plain-http warning, a note that Add replaces the token of an address already saved, and the
kind the server's answer without a token looks like. That kind SHALL be a hint only, and SHALL
choose Token's link: the kind's token page on that server and the rights the token needs.

#### Scenario: gitlab.com
- **WHEN** no gitlab.com server is saved and the human presses `+ Add server`
- **THEN** Address holds `https://gitlab.com`, the hint says it looks like GitLab, and Token's
  link is `https://gitlab.com/-/user_settings/personal_access_tokens` with the scopes
  `read_repository, write_repository, read_api`

#### Scenario: github.com
- **WHEN** the human types `github.com` in Address
- **THEN** the refusal under Address says github.com is reached through gh's login, and Add
  server is off

#### Scenario: Plain http
- **WHEN** the human types `http://git.lab.example`
- **THEN** the warning that the token goes to git.lab.example over plain http://, unencrypted,
  shows under Address, and Add server stays possible

### Requirement: Add server saves as lado git-server add does

Add server SHALL send the address, the token and the kind chosen, if any; LADO SHALL check and
save the server with `lado git-server add`'s rules, each request at most 5 s, the button
saying `checking the server…` meanwhile. The saved server SHALL take the form's place with
`Saved git server <address>: <kind>, signed in as <login>.` (or `Replaced …`) and the line that
agents started from now on reach it.

#### Scenario: A server of the human's own
- **WHEN** the human adds `git.corp.example`, which answers as GitHub, with a token it accepts
- **THEN** the row `https://git.corp.example`, GitHub, `signed in as <login>` shows, and
  `lado git-server list` prints the same server

### Requirement: A refusal shows under its field in the page's words

A refusal of Add SHALL show under the field it concerns (Address, Token or Kind; one of none
under the buttons) in the command's words with no command in them; the form SHALL keep the
address and the kind and empty the token, unless the token itself was refused.

#### Scenario: A wrong token
- **WHEN** the server refuses the token
- **THEN** `GitLab at <address> refuses the token` shows under Token with where to make one and
  its scopes, and nothing is saved

### Requirement: The kind is chosen by hand only for a server that cannot be told

The form SHALL show a choice of the kind (GitHub, GitLab), none chosen, only when the address
check finds that the server does not answer or answers as neither kind or as both; Add SHALL
then be `Add without a check`, off until a kind is chosen, and save the server as `--kind`
does, its row saying `⚠ not checked`. A server that sends elsewhere SHALL be refused with no
choice.

#### Scenario: A server that does not answer
- **WHEN** the human types an address whose server does not answer in 5 s
- **THEN** the warning says it does not answer, the choice of the kind shows, and after
  choosing GitLab and a token, `Add without a check` saves it as not checked

#### Scenario: A server that sends elsewhere
- **WHEN** the address answers with a redirect
- **THEN** the refusal says where it sends and to give the server's own address, and no
  choice of the kind shows

### Requirement: Remove asks first

A server's 🗑 SHALL ask under its row, `Remove <address>?`, that its token is deleted too and
that this cannot be undone, with Remove server and Cancel (the focus on Cancel); Remove server
SHALL remove the server as `lado git-server remove` does and leave `Removed <address>.` in its
place.

#### Scenario: Removing a server
- **WHEN** the human removes `https://git.corp.example` and confirms
- **THEN** its row says `Removed https://git.corp.example.`, `lado git-server list` no longer
  shows it, and its token folder is gone

### Requirement: The token never leaves the request that carries it

The token SHALL reach LADO's server only in the body of `POST /api/git-servers`; no answer of
the git servers' API, no refusal (a 422 included), no log of LADO's server, no file of
`LADO_HOME` but the server's token file, and no part of the page once Add is done SHALL hold
it. The token field SHALL be the project page's secret field, emptied once Add is done or
refused for anything but the token, on Cancel and when the form closes.

#### Scenario: A token through the page
- **WHEN** the human adds a server with a canary token through the page
- **THEN** the canary is in no API answer, not in the page's DOM after the save, not in
  LADO's server log, and in no file of `LADO_HOME` but the token file
