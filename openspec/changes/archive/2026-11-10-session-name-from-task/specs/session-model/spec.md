## MODIFIED Requirements

### Requirement: The launch window's Model field

Team SHALL have a Model field before Switch off, in New session and Resume: the model picker
of the chosen agent CLI, optional, asking for no address or key, holding that CLI's default
when the window opens (in Resume the session's model, else the default). The value left as it
came SHALL send no model, another pick its name, `<CLI>'s settings` with a default `''`.
Another agent CLI SHALL set the field to that CLI's default.

#### Scenario: A model the list lacks in the window
- **WHEN** the human picks Codex CLI, opens Team and gives `gpt-9` as an other name, or a
  saved built-in default Codex's list lost is in the field
- **THEN** the note under Model reads `gpt-9 is not in Codex CLI's list of models` with `Use
  Codex CLI's settings`, and the start button is off

#### Scenario: The folded summary
- **WHEN** the human picks `Локальная Qwen` on `LM Studio дома` and hides Team
- **THEN** Team's summary reads `Model Локальная Qwen on LM Studio дома` after its other pairs

#### Scenario: Another provider
- **WHEN** the human has picked `Локальная Qwen` for OpenCode and picks Claude Code with no default
- **THEN** the Model field reads `Claude Code's settings`, its list is Claude Code's, and the note
  reads `Локальная Qwen belongs to OpenCode, so the model is back to Claude Code's default.`

#### Scenario: The default chosen in advance
- **WHEN** OpenCode's default is `Локальная Qwen` and the human picks OpenCode
- **THEN** the field holds it, marked `default`, no note stands under it, and starting sends
  no model

#### Scenario: A server that does not answer
- **WHEN** the field holds `Локальная Qwen` and its server does not answer
- **THEN** Team is open, the note reads `LM Studio дома does not answer (<why>); qwen3-8b is on
  it. Start the server or pick another model.` with `Check again` and `Use OpenCode's settings`,
  and the footer reads `To start: fix the model`

#### Scenario: A CLI that runs on no server
- **WHEN** the field holds Codex CLI's `Локальная GPT`, on LM Studio
- **THEN** the note has the refusal and `Use Codex CLI's settings`, without `Check again`

#### Scenario: The window says agent CLI
- **WHEN** the human opens Team
- **THEN** the field before Kits reads `Agent`, and its notes say `agent CLI` or the
  CLI's title, never `provider`

#### Scenario: A key over http
- **WHEN** the chosen model's server gets its key over plain http to a public address
- **THEN** the note warns with `⚠ The key of <server> goes unencrypted (http) to an address outside
  your machine and network.`, and the start button stays on

### Requirement: The Model field looks like the window's other fields

The Model field SHALL have the height, frame, font and a chevron like Team's Agent field and
take the whole row of the open Team, so a model's name, id and server fit. Its note SHALL stand
under it as far below as the notes of the window's other fields, out of the reach of its focus
ring.

#### Scenario: The note under the focused field
- **WHEN** the Model field has the focus and a refusal under it
- **THEN** the note's top is at least 6 px below the field's bottom, as the note under
  Agent is below its field, and the focus ring does not reach it

#### Scenario: The field beside Provider
- **WHEN** the window is wider than 760 px and Team is open
- **THEN** the Model field has Agent's height, the whole row's width and a chevron at its
  right end
