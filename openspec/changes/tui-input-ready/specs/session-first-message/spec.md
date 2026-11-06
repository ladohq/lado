## ADDED Requirements

### Requirement: An OpenCode or Kilo agent is ready when its prompt has focus

An OpenCode or Kilo agent SHALL stay `starting` until its TUI's prompt has focus, reported by a TUI
plugin LADO gives that agent alone through the CLI's own variable (`OPENCODE_TUI_CONFIG`,
`KILO_TUI_CONFIG`), never through the user's config. That report SHALL be the agent's session start;
the server plugin's init SHALL report nothing. Nothing SHALL be typed into the agent's window
before it, unless the TUI stays silent for 30 s while the server plugin lives: the agent SHALL then be
ready, its lead SHALL be told, and messages SHALL be typed in as for any idle agent.

#### Scenario: A message right after the start

- **WHEN** the human writes to a new Kilo or OpenCode session while its agent is `starting`
- **THEN** the message stays `pending` with no attempt until the prompt has focus, is typed in
  then, and is `delivered` with `attempts` 1, also on a machine under load

#### Scenario: Busy only with the message on its way

- **WHEN** that message waits for the prompt
- **THEN** the agent shows `starting`, not `busy`, until the message is typed in

#### Scenario: A CLI that shows no sign

- **WHEN** neither the TUI nor the server plugin reports for 30 s after the launch
- **THEN** the message stays `pending` and never `failed`, and the agent is `waiting` with the reason
  `Waiting for an answer in its terminal: no sign from it 30 s after its start. Open its terminal.`;
  when the prompt has focus the agent is idle and the message goes in

#### Scenario: A TUI silent while the server plugin lives

- **WHEN** the server plugin lives and the TUI has not reported 30 s after the plugin's start
- **THEN** the agent is ready, its lead gets the line `<agent>: no report from its TUI 30 s after its
  start; messages are typed in as they come, and one may be lost`, and its queue is typed in

#### Scenario: A TUI that opens after that

- **WHEN** messages typed into a silent TUI failed and the agent is `waiting`, and then the prompt has
  focus
- **THEN** the messages go back to the queue, the agent is idle, and they are `delivered`

#### Scenario: A dialog stays

- **WHEN** the agent waits for a dialog's answer and the TUI reports
- **THEN** the agent stays `waiting`

#### Scenario: Lines given on the command line

- **WHEN** a worker starts with its task's line on `--prompt` and the CLI reports the prompt
  submitted before the prompt's focus
- **THEN** the agent is `busy` with its task, and the later report changes nothing

#### Scenario: The user's config stays

- **WHEN** an agent starts
- **THEN** its TUI config is a file in its own config folder, and no file of the user's is written
