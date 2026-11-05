## MODIFIED Requirements

### Requirement: Without the page everything is as before

The section and its API SHALL change no saved server, model or default by themselves. What is saved
SHALL reach sessions only as `session-model` says.

#### Scenario: Models saved through the page
- **WHEN** the human saved servers and models through the page, set no default and starts a session
  without `--model`
- **THEN** the session's agents start as their CLI chooses, with the ticked models beside its own

#### Scenario: A default set through the page
- **WHEN** the human set a CLI's default model and starts a session on that CLI
- **THEN** the session's agents start on it, with the source `default in Settings`

### Requirement: The lead of Your agent CLIs

The block's lead SHALL say `New sessions and workers of each agent CLI start on its default model.
Left on its settings, the agent CLI chooses. Your models come from the model servers below.`, and
with no configured model at all `New sessions and workers of each agent CLI start on its default
model. To add models of your own, add a model server below and tick the agent CLIs that run them.`

#### Scenario: Nothing saved
- **WHEN** no model is saved and the human opens Settings
- **THEN** the lead says how to add models and no card has a list of models

### Requirement: Picking saves at once

Picking a row SHALL close the list, save the default as `lado model default` does, keep the
focus on the field and show the value. A refusal SHALL show under the field and leave the value
as it was. `<CLI>'s settings` SHALL clear the default.

#### Scenario: A model of the list
- **WHEN** the human picks `anthropic/claude-sonnet-4-5` on Kilo CLI's card
- **THEN** `lado model default` shows it as Kilo CLI's default

#### Scenario: Back to the settings
- **WHEN** the human picks `Kilo CLI's settings`
- **THEN** Kilo CLI has no default, and its field shows `Kilo CLI's settings`
