## MODIFIED Requirements

### Requirement: lado model default refuses what cannot be a CLI's default

`lado model default <cli> <model>` SHALL exit 1 and change nothing for a name that is both a
configured model and a built-in model of the CLI, a name that is only another CLI's
configured model, a CLI LADO does not know (naming those it knows), and a CLI that is not
installed.

#### Scenario: One name, two models
- **WHEN** OpenCode lists `qwen3-8b` and a configured model of OpenCode is named `qwen3-8b`
- **THEN** `lado model default opencode qwen3-8b` exits 1 with `"qwen3-8b" is both a saved
  model of OpenCode and one of its own; rename the saved one: Settings → Model servers`, and the
  default is unchanged

#### Scenario: Another CLI's model
- **WHEN** `Локальная Qwen` is OpenCode's and the human runs `lado model default claude
  "Локальная Qwen"`
- **THEN** it exits 1 with `"Локальная Qwen" is a model of OpenCode, not of Claude Code`,
  even though Claude Code gives no full list

#### Scenario: Not installed
- **WHEN** Kilo CLI is not installed and the human runs `lado model default kilo
  "Локальная Qwen"`
- **THEN** it exits 1 with `Kilo CLI is not installed`, and the default is unchanged
