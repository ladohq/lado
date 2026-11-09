## ADDED Requirements

### Requirement: Removing a model never asks

Removing a model on Model servers, by × in Your models or by its tick under a server's model,
SHALL ask nothing, an agent CLI's default too, and SHALL offer Undo where the human acted; the
removal of a default SHALL clear the default in one operation. Only removing a server SHALL ask
first, as its key cannot be brought back.

#### Scenario: × on a default
- **WHEN** the human presses × on `Локальная Qwen`, OpenCode's default
- **THEN** no question shows, the row says `Removed Локальная Qwen. OpenCode is back on its
  settings.` with Undo focused, and OpenCode's row on Agent CLIs shows `OpenCode's settings`

#### Scenario: A default set in another window
- **WHEN** this page shows no default, another window made `Локальная Qwen` OpenCode's, and the
  human presses × on it
- **THEN** the row says `Removed Локальная Qwen. OpenCode is back on its settings.` and Undo sets
  the default again

#### Scenario: A server
- **WHEN** the human presses Remove on `LM Studio дома`
- **THEN** the question shows and ends with `This cannot be undone.`

### Requirement: Undo of a model unticked

A model removed by its tick SHALL leave under that tick `Removed <name>.`, with `<CLI> is back
on its settings.` when it was a default, and Undo, the focus staying on the tick; Undo SHALL
save the model again under its name and set the default again, a refusal shown in that line.
After ten seconds only Undo SHALL go; the line SHALL stay until the human's next change on the
page. Ticking it again SHALL save the model as before, take the line away, and set no default.

#### Scenario: Unticking a default
- **WHEN** `Qwen в Kilo` is Kilo CLI's default and the human unticks Kilo CLI under `qwen3-8b`
  on `LM Studio дома`
- **THEN** no question shows, the model is removed, and under the tick the line says `Removed
  Qwen в Kilo. Kilo CLI is back on its settings.` with Undo

#### Scenario: Undo
- **WHEN** the human presses that Undo
- **THEN** `Qwen в Kilo` is saved again, the tick is on, and Kilo CLI's default is `Qwen в Kilo`

#### Scenario: Ten seconds
- **WHEN** ten seconds pass after the untick
- **THEN** the line says `Removed Qwen в Kilo.` without Undo until the human's next change

## REMOVED Requirements

### Requirement: Removing a default model asks first

**Reason**: Settings removes what can be brought back without a question and offers Undo
(LAD-243, the human's answer #4907); a default removed is brought back by Undo.
**Migration**: "Removing a model never asks" and "Undo of a model unticked" replace it; removing
a server keeps its question.
