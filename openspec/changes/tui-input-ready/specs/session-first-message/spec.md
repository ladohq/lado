## ADDED Requirements

### Requirement: An OpenCode or Kilo agent is ready when its prompt has focus

An OpenCode or Kilo agent SHALL stay `starting` until its TUI's prompt has focus, reported by a TUI
plugin LADO gives that agent alone through the CLI's own variable (`OPENCODE_TUI_CONFIG`,
`KILO_TUI_CONFIG`), never through the user's config. That report SHALL be the agent's session start;
the server plugin's init SHALL report nothing. Nothing SHALL be typed into the agent's window
before it.

#### Scenario: A message right after the start

- **WHEN** the human writes to a new Kilo or OpenCode session while its agent is `starting`
- **THEN** the message stays `pending` with no attempt until the prompt has focus, is typed in
  then, and is `delivered` with `attempts` 1, also on a machine under load

#### Scenario: Busy only with the message on its way

- **WHEN** that message waits for the prompt
- **THEN** the agent shows `starting`, not `busy`, until the message is typed in

#### Scenario: A TUI that takes minutes

- **WHEN** the TUI is not ready for longer than every retry delay added up
- **THEN** the message stays `pending` and never `failed`; 30 s after the launch the agent is
  `waiting` with the reason `Waiting for an answer in its terminal: no sign from it 30 s after its
  start. Open its terminal.`; when the prompt has focus the agent is idle and the message goes in

#### Scenario: Lines given on the command line

- **WHEN** a worker starts with its task's line on `--prompt` and the CLI reports the prompt
  submitted before the prompt's focus
- **THEN** the agent is `busy` with its task, and the later report changes nothing

#### Scenario: The user's config stays

- **WHEN** an agent starts
- **THEN** its TUI config is a file in its own config folder, and no file of the user's is written
