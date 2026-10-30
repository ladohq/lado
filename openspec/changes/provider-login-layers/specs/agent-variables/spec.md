## MODIFIED Requirements

### Requirement: One core function lays the project's layer for every provider

One core function SHALL build every agent's environment, for every provider, with
Docker and without, each later layer over the one before: the login shell's (or the
starting process's with `LADO_AGENT_ENV=inherit`), the outside folder's, LADO's secrets
(`<LADO_HOME>/secrets/`, the agent CLIs' login variables set in the UI), the project's,
LADO's and the provider's. A login SHALL come whole from one layer: of the first four,
the highest that sets any of the agent's provider's login variables gives all of them,
and the provider's login variables of the lower layers SHALL NOT reach the agent.

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

#### Scenario: A login comes whole from the highest layer that sets one
- **WHEN** the login shell exports `ANTHROPIC_API_KEY`, the outside folder has
  `CLAUDE_CODE_OAUTH_TOKEN` with `out`, and project `shop` has `ANTHROPIC_API_KEY` with
  `proj`
- **THEN** a Claude agent of a session without a project has `CLAUDE_CODE_OAUTH_TOKEN=out`
  and no `ANTHROPIC_API_KEY`, and one of a session in `shop` has `ANTHROPIC_API_KEY=proj`
  and no `CLAUDE_CODE_OAUTH_TOKEN`

#### Scenario: Other providers keep the variables
- **WHEN** LADO's secrets have `CLAUDE_CODE_OAUTH_TOKEN` and the login shell exports
  `ANTHROPIC_API_KEY`
- **THEN** an OpenCode agent has `ANTHROPIC_API_KEY`, which is no login variable of its
  provider
