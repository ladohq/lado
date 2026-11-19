## ADDED Requirements

### Requirement: The add form starts empty

`+ Add server` SHALL open a form with Address and Token; Address SHALL be empty and
focused, with the placeholder `github.com or gitlab.example.com`, whichever servers are
saved. Opened by the way out of a failure (`Add git server`), it SHALL hold that server's
address.

#### Scenario: An empty list
- **WHEN** no git server is saved and the human presses `+ Add server`
- **THEN** Address is empty and focused, shows the placeholder `github.com or
  gitlab.example.com`, and no `<Kind> answers.` line shows

#### Scenario: gitlab.com saved already
- **WHEN** `https://gitlab.com` is saved and the human presses `+ Add server`
- **THEN** Address is empty and focused

## MODIFIED Requirements

### Requirement: The add form checks the address without the token

Once the typing settles the page SHALL check the address without the token, at most 5 s a
request, saying `Checking…` meanwhile: the command's refusals of the address, the plain-http
warning `⚠ Plain http://: the token travels unencrypted.` with an ⓘ, and `<Kind> answers.`
for the kind the server's answer without a token looks like. That kind SHALL be a hint only,
and SHALL choose Token's link: the kind's token page on that server and the rights the token
needs.

#### Scenario: gitlab.com
- **WHEN** the human types `gitlab.com` in Address and no gitlab.com server is saved
- **THEN** the line says `GitLab answers.`, and Token's link is
  `https://gitlab.com/-/user_settings/personal_access_tokens` with the scopes
  `read_repository, write_repository, read_api`

#### Scenario: github.com
- **WHEN** the human types `github.com` in Address and no github.com entry is saved
- **THEN** the line says `GitHub answers.`, Token's link is
  `https://github.com/settings/tokens` with the scope `repo`, and Add server saves it

#### Scenario: Plain http
- **WHEN** the human types `http://git.lab.example`
- **THEN** `⚠ Plain http://: the token travels unencrypted.` shows first under Address, and
  Add server stays possible

## REMOVED Requirements

### Requirement: The add form starts with gitlab.com

**Reason**: github.com is an entry like gitlab.com now; the form fills in no server (#7446).
**Migration**: type the server's address; the placeholder names both kinds.
