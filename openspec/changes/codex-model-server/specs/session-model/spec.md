## REMOVED Requirements

### Requirement: A CLI that runs on no server is refused

**Reason**: Every agent CLI runs on a model server now.
**Migration**: Replaced by "A server a CLI cannot use is refused".

## ADDED Requirements

### Requirement: A server a CLI cannot use is refused

A start model on a server of a type its CLI cannot use SHALL be refused before any request, naming why and the CLIs that the server suits; a spawned worker SHALL be refused the same way.

#### Scenario: Claude Code on a gateway
- **WHEN** Claude Code's default is `Шлюз Opus` on `Шлюз`, which proves the Anthropic Messages API,
  and the human starts a Claude session
- **THEN** no refusal names Claude Code, `Шлюз` is asked, and the session starts on it

#### Scenario: Codex on a gateway
- **WHEN** Codex's default is `Шлюз GPT` on `Шлюз`, which proves the Responses API, and the human starts a Codex session
- **THEN** no refusal names Codex CLI, `Шлюз` is asked, and the session starts on it

#### Scenario: Codex on LM Studio
- **WHEN** Codex's default is `Локальная GPT` on `LM Studio дома`, saved before this rule, and the human starts a Codex session
- **THEN** it refuses with `Локальная GPT is on the model server LM Studio дома; LM Studio дома does not suit Codex CLI: its Responses API loses Codex CLI's MCP tools, so the agent could not talk to LADO; Kilo CLI and OpenCode do`, adding the default's way out, and `LM Studio дома` is not asked

#### Scenario: A worker of that CLI
- **WHEN** the supervisor of an OpenCode session spawns a worker with the provider `codex` on that model
- **THEN** `spawn_worker` fails with the same line
