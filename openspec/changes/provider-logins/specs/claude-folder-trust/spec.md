## ADDED Requirements

### Requirement: LADO records Claude Code's first run for a logged-in agent

Before it starts a Claude agent whose environment logs Claude Code in, LADO SHALL set
`hasCompletedOnboarding` to `true` in the global config Claude Code reads when it is not
`true`, through the one careful writer, so the agent does not stop at Claude Code's
first-run screen; it SHALL tell whoever starts the agent `LADO recorded Claude Code's
first run in <config file>` and log it in the session's loop.log, once per write. It SHALL
NOT write it while Claude Code is not logged in.

#### Scenario: A fresh config with a token
- **WHEN** a Claude agent starts with `CLAUDE_CODE_OAUTH_TOKEN` and a config without
  `hasCompletedOnboarding`
- **THEN** the config has `hasCompletedOnboarding: true`, the line is told and logged, and
  the agent reaches its first hook with no human

#### Scenario: Not logged in
- **WHEN** a Claude agent waits for a login
- **THEN** `hasCompletedOnboarding` is not written until the login is there

### Requirement: LADO approves the API key it gives Claude Code

When a Claude agent's environment has `ANTHROPIC_API_KEY` whose last 20 characters are in
neither list of `customApiKeyResponses` in Claude Code's config, LADO SHALL add them to
`approved` through the one careful writer before the agent starts, and tell and log `LADO
recorded the approval of ANTHROPIC_API_KEY in <config file>`, never any part of the key. A
key in `rejected` SHALL be left as it is, and the agent SHALL wait with a reason saying so.

#### Scenario: A new key
- **WHEN** a Claude agent starts with an `ANTHROPIC_API_KEY` Claude Code has not seen
- **THEN** its last 20 characters are in `approved`, and the agent does not stop at
  "Detected a custom API key"

#### Scenario: A key the human rejected
- **WHEN** the key's last 20 characters are in `rejected`
- **THEN** the config is unchanged and the agent waits with the reason

## MODIFIED Requirements

### Requirement: A missing config is created with the trust alone

When Claude Code's config file does not exist, LADO SHALL create it holding only
`projects["<repo>"].hasTrustDialogAccepted: true`, with mode 600; the first-run keys LADO
records for a logged-in agent (`hasCompletedOnboarding`, an approved API key) SHALL then
be added by their own writes, and nothing else.

#### Scenario: A fresh home

- **WHEN** a Claude agent is started, Claude Code is not logged in, and no config file
  exists
- **THEN** the file exists afterwards as `{"projects": {"<repo>": {"hasTrustDialogAccepted":
  true}}}` with mode 600, and the agent does not wait for the trust question

#### Scenario: A fresh home with a login

- **WHEN** a Claude agent is started with `CLAUDE_CODE_OAUTH_TOKEN` and no config file
  exists
- **THEN** the file holds exactly the trust entry and `hasCompletedOnboarding: true`, with
  mode 600
