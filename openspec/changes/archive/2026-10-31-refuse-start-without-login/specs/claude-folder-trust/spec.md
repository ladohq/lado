## MODIFIED Requirements

### Requirement: A missing config is created with the trust alone

When Claude Code's config file does not exist, LADO SHALL create it holding only
`projects["<repo>"].hasTrustDialogAccepted: true`, with mode 600; the first-run keys LADO
records for a logged-in agent (`hasCompletedOnboarding`, an approved API key) SHALL then
be added by their own writes, and nothing else. The trust needs no login: an agent that
waits for its login gets it at its start, told whoever starts it.

#### Scenario: A fresh home

- **WHEN** a stopped Claude session is resumed, Claude Code is not logged in, and no config
  file exists (a new session is refused without the login: provider-logins)
- **THEN** the file exists afterwards as `{"projects": {"<repo>": {"hasTrustDialogAccepted":
  true}}}` with mode 600, whoever started the agent is told the trust's line, and the
  agent waits for its login, not for the trust question

#### Scenario: The login arrives in a fresh home

- **WHEN** that agent's login is there
- **THEN** its window adds `hasCompletedOnboarding: true` to the file, logs the line in
  loop.log and starts the CLI

#### Scenario: A fresh home with a login

- **WHEN** a Claude agent is started with `CLAUDE_CODE_OAUTH_TOKEN` and no config file
  exists
- **THEN** the file holds exactly the trust entry and `hasCompletedOnboarding: true`, with
  mode 600
