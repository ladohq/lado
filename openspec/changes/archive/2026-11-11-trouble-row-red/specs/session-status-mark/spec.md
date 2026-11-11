## ADDED Requirements

### Requirement: A row in trouble says its trouble in the danger colour

A row of the session list whose session is `tmux_gone` or `loop_down` SHALL show its status in
words (`tmux session is gone`, `session loop not running`) in `--danger`, with a full
`--danger` dot before them, the dot of that trouble in the session's head, in the light and
the dark theme.

#### Scenario: The tmux session is gone
- **WHEN** the human opens the session list with a session whose tmux session is gone
- **THEN** its row says `tmux session is gone` in `--danger` after a full `--danger` dot, not
  in `--muted` after a ring

#### Scenario: Loop down while a gate waits
- **WHEN** a session's loop does not run and a gate waits in it
- **THEN** its row is under **Needs you**, its line says what waits, and under it
  `session loop not running` in `--danger` after a full `--danger` dot
