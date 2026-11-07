## MODIFIED Requirements

### Requirement: The launch window's Model field

The launch window's Advanced SHALL have a Model field before Switch off, in New session and Resume:
the model picker of the chosen agent CLI, optional, asking for no address or key, holding that CLI's
default when the window opens (in Resume the session's model, else the default). The value left as
it came SHALL send no model, another pick its name, `<CLI>'s settings` with a default `''`. Another
agent CLI SHALL set the field to that CLI's default.

#### Scenario: A model the list lacks in the window
- **WHEN** the human picks Codex, opens Advanced and gives `gpt-9` as an other name, or a saved
  built-in default Codex's list lost is in the field
- **THEN** the note under Model reads `gpt-9 is not in Codex CLI's list of models` with `Use
  Codex CLI's settings`, and Start session is off

#### Scenario: The folded summary
- **WHEN** the human picks `Локальная Qwen` on `LM Studio дома` and folds Advanced
- **THEN** its summary reads `Advanced: model Локальная Qwen on LM Studio дома`

#### Scenario: Another provider
- **WHEN** the human has picked `Локальная Qwen` for OpenCode and picks Claude Code with no default
- **THEN** the Model field reads `Claude Code's settings`, its list is Claude Code's, and the note
  reads `Локальная Qwen belongs to OpenCode, so the model is back to Claude Code's default.`

#### Scenario: The default chosen in advance
- **WHEN** OpenCode's default is `Локальная Qwen` and the human picks OpenCode
- **THEN** the field holds it, marked `default`, the note reads `OpenCode's default model, from
  Settings → Models.`, and starting sends no model

#### Scenario: A server that does not answer
- **WHEN** the field holds `Локальная Qwen` and its server does not answer
- **THEN** Advanced is open, the note reads `LM Studio дома does not answer (<why>); qwen3-8b is on
  it. Start the server or pick another model.` with `Check again` and `Use OpenCode's settings`,
  and Start session is off

#### Scenario: A server the CLI cannot use
- **WHEN** the field holds Codex CLI's `Локальная GPT`, on LM Studio
- **THEN** the note has the refusal and `Use Codex CLI's settings`, without `Check again`

#### Scenario: The window says agent CLI
- **WHEN** the human opens the window
- **THEN** the field above Permission mode reads `Agent CLI`, and its notes say `agent CLI`, never
  `provider`

#### Scenario: A key over http
- **WHEN** the chosen model's server gets its key over plain http to a public address
- **THEN** the note warns with `⚠ The key of <server> goes unencrypted (http) to an address outside
  your machine and network.`, and Start session stays on

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
