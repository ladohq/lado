## ADDED Requirements

### Requirement: A Codex agent runs on its model whatever its repository's Codex config names

When a Codex agent's config carries a model, LADO's choice or else the one carried from the user's
Codex config, LADO SHALL also give it on Codex's command line as `-m <model>`, so the agent runs on
that model whatever `model` the repository's `.codex/config.toml` names.

#### Scenario: The session's model over the repository's
- **WHEN** `lado start --provider codex --model gpt-5.6-luna` starts a session in a repository
  whose `.codex/config.toml` has `model = "gpt-5.6-terra"`
- **THEN** Codex is started with `-m gpt-5.6-luna`, the supervisor's model is `gpt-5.6-luna` with
  the source `session`, and its first hook naming `gpt-5.6-luna` leaves it so

#### Scenario: The user's carried model over the repository's
- **WHEN** a Codex agent with no model from LADO is spawned in that repository and the user's
  `~/.codex/config.toml` has `model = "gpt-5.6-sol"`
- **THEN** Codex is started with `-m gpt-5.6-sol` and the agent's model is `gpt-5.6-sol` with the
  source `cli-config`

#### Scenario: A worker on a model server
- **WHEN** a Codex worker is spawned on a model server's model `qwen3-8b` in that repository
- **THEN** Codex is started with `-m qwen3-8b`

#### Scenario: No model anywhere
- **WHEN** a Codex agent has no model from LADO, none from the user's Codex config and none in the
  repository's
- **THEN** Codex is started with no `-m`

### Requirement: A Codex agent on its repository's model shows it from the start

When a Codex agent's config carries no model and its folder is trusted, LADO SHALL record at the
launch the `model` of the nearest `.codex/config.toml` from the agent's folder up to its project
root that names one, with the source `cli` and the detail `the repository's .codex/config.toml`.

#### Scenario: The repository's model
- **WHEN** a Codex agent with no model from LADO or from the user's Codex config is spawned in a
  repository whose `.codex/config.toml` has `model = "gpt-5.6-terra"`
- **THEN** its page reads Model `gpt-5.6-terra · CLI default, the repository's .codex/config.toml`
  before its first hook

#### Scenario: A folder's own config is nearer
- **WHEN** the agent runs in the repository's folder `sub`, whose `.codex/config.toml` has
  `model = "gpt-5.6-terra-sub"`
- **THEN** its model is `gpt-5.6-terra-sub`

#### Scenario: A worker in its worktree
- **WHEN** a Codex worker is spawned in its worktree, whose `.codex/config.toml` has
  `model = "gpt-5.6-terra"`
- **THEN** its model is `gpt-5.6-terra` with the detail `the repository's .codex/config.toml`

#### Scenario: An untrusted repository
- **WHEN** the user's Codex config marks the repository `untrusted`
- **THEN** the agent's model has no name and the source `cli` until its CLI names the model
