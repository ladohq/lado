## RENAMED Requirements

- FROM: `### Requirement: The configured models are kept in lado.db and used by no session yet`
- TO: `### Requirement: The configured models are kept in lado.db and used by sessions`

## MODIFIED Requirements

### Requirement: The configured models are kept in lado.db and used by sessions

The configured models SHALL be kept in `lado.db` (from schema 38), each with an id that
never changes (from schema 39), its name, CLI, model and its server's id; a model SHALL NOT
exist without a saved server. With none saved and no default set, `lado start`, the launch window
and every agent SHALL behave as before. A saved model SHALL reach an agent of its CLI as
`session-model` says, and a default as the start model of a session that chose none.

#### Scenario: A session with models saved
- **WHEN** models and servers are saved, no default is set and the human runs `lado start <repo>`
  without `--model`
- **THEN** the session's agents start on their CLI's choice, as without them, and no server is asked

#### Scenario: A session with a default set
- **WHEN** OpenCode's default model is set and the human starts a session on OpenCode
- **THEN** the session's agents start on that model
