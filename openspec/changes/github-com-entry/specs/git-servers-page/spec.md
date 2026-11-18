## ADDED Requirements

### Requirement: github.com is listed and added as any server

github.com SHALL be a row of Servers like any saved server, with the same panel, lines and
`Remove server`, and nothing of its own: no block, no "not signed in" state, no line about
the takeover or a login outside LADO. Without an entry it SHALL not be listed.

#### Scenario: Taken over
- **WHEN** the takeover saved github.com as `octo`
- **THEN** Servers lists `https://github.com` `GitHub` `signed in as octo` among the other
  servers, and the page shows no other line about it

#### Scenario: Removed
- **WHEN** the human removes github.com
- **THEN** it is no longer listed, as any removed server

## MODIFIED Requirements

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
- **WHEN** the human types `github.com` in Address and no github.com entry is saved
- **THEN** the line says `GitHub answers.`, Token's link is
  `https://github.com/settings/tokens` with the scope `repo`, and Add server saves it

#### Scenario: Plain http
- **WHEN** the human types `http://git.lab.example`
- **THEN** `⚠ Plain http://: the token travels unencrypted.` shows first under Address, and
  Add server stays possible

### Requirement: The author's Remove and Undo are off while they ask

The commit author's `Remove` and its line's `Undo` SHALL be off while their request runs,
and so SHALL the author's `Edit` and `Set author`.

#### Scenario: A slow removal
- **WHEN** the human presses `Remove` and the server has not answered yet
- **THEN** `Remove` is off and a second press sends nothing

#### Scenario: Edit while removing
- **WHEN** the human presses `Remove` and the server has not answered yet
- **THEN** `Edit` is off, and after the answer `Set author` is on
