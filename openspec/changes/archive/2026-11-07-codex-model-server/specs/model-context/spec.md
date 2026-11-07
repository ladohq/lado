## ADDED Requirements

### Requirement: A known context goes to a Codex agent

For a model with a known context, a Codex agent's config SHALL hold `model_context_window` with that context and `model_auto_compact_token_limit` with the context less the output room, and its list entry the context. A model with no known context SHALL have neither key and a null context in its entry. Codex has no setting for its output, so nothing SHALL cap it.

#### Scenario: A context of 65536
- **WHEN** a Codex agent starts on a model whose context is 65536 and no output is reported
- **THEN** its config holds `model_context_window = 65536` and `model_auto_compact_token_limit = 57344`

#### Scenario: No known context
- **WHEN** a Codex agent starts on a model of a public server that reports no context
- **THEN** its config has neither key, and the start warns as on the other CLIs

#### Scenario: The real CLI compacts
- **WHEN** real Codex on a fake server has its token use pass that limit
- **THEN** its next turn is preceded by a compaction request to the same server
