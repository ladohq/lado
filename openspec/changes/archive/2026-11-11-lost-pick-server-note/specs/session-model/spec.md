## MODIFIED Requirements

### Requirement: A pick follows its agent CLI

A pick lost to another agent CLI SHALL leave `<name> belongs to <CLI>, so the model is back to <new
CLI>'s default.`, or, when the field then takes the new CLI's one saved model of a server by
itself, `<name> belongs to <CLI>. For this session only: <new CLI> is not logged in, so it runs on
your server's model.`, until the next change of agent CLI. While the agent CLIs are read again, for
another project, the pick SHALL stay.

#### Scenario: The next change of agent CLI
- **WHEN** the line stands and the human picks a third agent CLI
- **THEN** the line is gone

#### Scenario: Another project
- **WHEN** the human has a pick and goes to Project and back to Folder
- **THEN** the pick is in the field, with no line

#### Scenario: The field takes the one server model
- **WHEN** the human has picked `kilo/large` for Kilo CLI and picks Claude Code, which is not
  logged in and has `CloudClaude` as its one saved model
- **THEN** the field holds `CloudClaude`, the one note under it reads `kilo/large belongs to Kilo
  CLI. For this session only: Claude Code is not logged in, so it runs on your server's model.`,
  and the session starts on `CloudClaude`
