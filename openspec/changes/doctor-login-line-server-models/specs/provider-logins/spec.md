## MODIFIED Requirements

### Requirement: lado doctor prints each CLI's login

`lado doctor` SHALL print one login line per installed CLI: `ok` with the method and where
it comes from when logged in, `warn` for a CLI whose agents need a login and have none
(saying that only its agents on the model server's models start, and where to log in for
its own models), `info` for a CLI without a login whose agents do not need one, `warn`
with why when unknown; the exit code SHALL not change for these lines.

#### Scenario: Claude Code not logged in
- **WHEN** Claude Code is installed and not logged in
- **THEN** `lado doctor` prints `[warn] Claude Code login: not logged in: only its agents
  on your model server's models start; log in in Settings → Agent CLIs for its own
  models` and exits as before

#### Scenario: Claude Code with a token of LADO's secrets
- **WHEN** LADO's secrets hold `CLAUDE_CODE_OAUTH_TOKEN`
- **THEN** `lado doctor` prints `[ok] Claude Code login: Subscription (token) · LADO's
  secret`

#### Scenario: Codex not logged in on OpenAI's models
- **WHEN** Codex CLI is installed, not logged in, and the user's Codex config names
  OpenAI's model provider (or none)
- **THEN** `lado doctor` prints `[warn] Codex CLI login: not logged in: only its agents on
  your model server's models start; log in in Settings → Agent CLIs for its own models`
