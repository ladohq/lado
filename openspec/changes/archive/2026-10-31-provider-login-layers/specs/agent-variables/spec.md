## ADDED Requirements

### Requirement: An agent's login comes whole from one layer

Of the login shell's, the outside folder's, LADO's secrets' and the project's layers, the
highest that sets any of the agent's provider's login variables SHALL give all of them,
and the provider's login variables of the lower layers SHALL NOT reach the agent. A
variable that is no login variable of the agent's provider SHALL be laid name by name.

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
