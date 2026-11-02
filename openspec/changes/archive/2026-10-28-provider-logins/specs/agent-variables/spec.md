## MODIFIED Requirements

### Requirement: One core function lays the project's layer for every provider

One core function SHALL build every agent's environment, for every provider, with
Docker and without, each later layer over the one before: the login shell's (or the
starting process's with `LADO_AGENT_ENV=inherit`), the outside folder's, LADO's secrets
(`<LADO_HOME>/secrets/`, the agent CLIs' login variables set in the UI), the project's,
LADO's and the provider's.

#### Scenario: The order of the layers
- **WHEN** the login shell exports `BOARD_URL=shell`, the outside folder has `BOARD_URL`
  with `out`, and project `shop` has `BOARD_URL=proj`
- **THEN** an agent of a session in `shop` has `BOARD_URL=proj`, with any of the four
  providers

#### Scenario: LADO's secrets between the outside folder and the project
- **WHEN** the outside folder has `CLAUDE_CODE_OAUTH_TOKEN` with `out`, LADO's secrets have
  it with `lado`, and project `shop` has the secret with `proj`
- **THEN** an agent of a session without a project has `lado`, and an agent of a session in
  `shop` has `proj`
