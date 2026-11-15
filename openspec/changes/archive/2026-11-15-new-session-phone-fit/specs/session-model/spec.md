## MODIFIED Requirements

### Requirement: The Model field looks like the window's other fields

The Model field SHALL have the height, frame, font and a chevron like Team's Agent field and
take the whole row of the open Team, so a model's name, id and server fit. A picked model's
name SHALL stay whole at every width: the id and then the server's mark give way first, the
server's down to its icon; only a name longer than the whole field is cut. Its note SHALL stand under it as far below as the notes of the window's other fields, out
of the reach of its focus ring.

#### Scenario: The note under the focused field
- **WHEN** the Model field has the focus and a refusal under it
- **THEN** the note's top is at least 6 px below the field's bottom, as the note under
  Agent is below its field, and the focus ring does not reach it

#### Scenario: The field beside Provider
- **WHEN** the window is wider than 760 px and Team is open
- **THEN** the Model field has Agent's height, the whole row's width and a chevron at its
  right end

#### Scenario: A short name on a phone
- **WHEN** the window is 390 px wide and the field holds OpenCode's default `Локальная Qwen` on
  `LM Studio дома`
- **THEN** the field shows `Локальная Qwen` whole, then `default`, and the server's mark cut
  first, down to its icon

### Requirement: A refused model in the window

A model in the field SHALL be checked as the start checks it, the start button staying on while
the check runs. A refusal SHALL open Team, turn the start button off with `To start: fix the
model`, and stand under the field with `Use <CLI>'s settings`, and `Check again` where a new
try can help. A start refused after a good check SHALL do the same and put the focus on Model,
with no second notice of the refusal elsewhere in the window.

#### Scenario: Refused at Start
- **WHEN** the server answered the check and stops answering before the human presses the
  start button
- **THEN** Team is open, the refusal `LM Studio дома does not answer…` stands under Model,
  the focus is on Model, the field and the refusal are scrolled into the window's body, the
  start button is off, and no `Not started` line stands above the buttons

#### Scenario: Check again
- **WHEN** the human presses `Check again`
- **THEN** until the answer the refusal and its buttons stay, the button reads `Checking…`, off with
  the focus on it, and the start button stays off

## ADDED Requirements

### Requirement: The Model field's server mark shows a refusal

In the launch window's Model field, the server's mark of a model refused because its server does
not answer SHALL carry the refusal's round `!`, not `⚠`; the rows of the field's list SHALL keep
`⚠`.

#### Scenario: The mark of a silent server
- **WHEN** the field holds `Локальная Qwen` and `LM Studio дома` does not answer
- **THEN** the server's mark in the field carries the round `!` of the refusal under it, and
  the server's row in the open list keeps `⚠`
