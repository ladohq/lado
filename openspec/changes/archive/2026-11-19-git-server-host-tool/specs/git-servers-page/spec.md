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
  `https://gitlab.com/-/user_settings/personal_access_tokens` with the scope `api`

#### Scenario: github.com
- **WHEN** the human types `github.com` in Address and no github.com entry is saved
- **THEN** the line says `GitHub answers.`, Token's link is
  `https://github.com/settings/tokens` with the scope `repo`, and Add server saves it

#### Scenario: Plain http
- **WHEN** the human types `http://git.lab.example`
- **THEN** `⚠ Plain http://: the token travels unencrypted.` shows first under Address, and
  Add server stays possible
