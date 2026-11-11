## ADDED Requirements

### Requirement: Model ids are in the mono face

A model's id in the picker (a built-in model's row, the id under a model's name, the id in the
field) and a model id or a server's address in Model servers SHALL show in the UI's mono face
(`--mono`); a model's name and the picker's other rows SHALL stay in the UI's face.

#### Scenario: The picker of OpenCode
- **WHEN** the human opens OpenCode's picker with `Рабочая Qwen` of `qwen3-coder-30b` saved and
  built-in models listed
- **THEN** `qwen3-coder-30b` and each built-in id are in IBM Plex Mono, and `Рабочая Qwen` and
  `OpenCode's settings` in Inter

#### Scenario: The field
- **WHEN** Kilo CLI's default is a built-in model
- **THEN** its id in the field is in IBM Plex Mono

### Requirement: The highlight stays on its row

The picker's highlighted row, the one Enter picks, SHALL stay the same row while the list stays
open and no list is read anew, whatever rows come or go above it. A highlighted row that goes
SHALL leave the highlight on the selected row, else the first, and SHALL get it back when it
comes again; a list read anew SHALL put it on the selected row.

#### Scenario: A failed read again
- **WHEN** the human moves the highlight to a built-in model, presses ↻, and LADO's server does
  not answer
- **THEN** `Read again` shows after the CLI's settings, the highlight is still on that model, and
  Enter picks it

#### Scenario: Read again fails again
- **WHEN** the human presses Enter on `Read again` and the request fails again
- **THEN** the highlight is on `Read again`

#### Scenario: A list read anew
- **WHEN** the human moved the highlight and a read of the list succeeds
- **THEN** the highlight is on the selected row
