## ADDED Requirements

### Requirement: Tab goes through the picker's foot

Tab in an open list SHALL go on into the controls of its foot, and close it without a pick only
past the last, going on from the field; Shift+Tab SHALL go back through them.

#### Scenario: Tab through the foot
- **WHEN** the list is open and the human presses Tab
- **THEN** the focus is on the foot's first control, and past its last the list is closed and the
  focus goes on from the field

### Requirement: The search stands while a list is first read

Until a list's first read says how long it is, the picker SHALL show its search with the focus in
it; what was typed SHALL stay, and a short list with nothing typed SHALL hand the focus to the field.

#### Scenario: Typing while the list is first read
- **WHEN** the human opens a list not read yet and types at once
- **THEN** what was typed stays in the search when the list comes

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

### Requirement: The picker works from the keyboard

The field SHALL be a combobox named `Default model of <CLI>`, in the launch window `Model`: Enter,
Space, ↓ and ↑ open it on the selected row; ↑ ↓ Home End move; Enter or Space picks; Esc closes
without a pick; a click outside closes. With search the focus SHALL be in the search field, Esc
first clearing its text. Esc, a pick and a press on nothing SHALL return the focus to the field; a
press on another control SHALL go on from there.

#### Scenario: Esc in a search
- **WHEN** the human types in the picker's search and presses Esc twice
- **THEN** the first clears the text, the second closes the list, and the focus is on the field

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
