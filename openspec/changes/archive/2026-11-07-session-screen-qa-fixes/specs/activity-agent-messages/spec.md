## MODIFIED Requirements

### Requirement: The toggle for messages between agents is Yours | All, on a phone a small icon

Outside the phone layout, while the tabs fit beside it, a session's Activity tab SHALL end the tab
bar with a `role="radiogroup"` named "Messages between agents" of two radios `Yours` and `All`, 26 px high, after the word
`Messages` while the bar has room for it; the keyboard SHALL reach the chosen one by Tab and move
by the arrows. On a phone held upright the team's row SHALL end with one icon button of that name,
pressed (`aria-pressed`) while the chat shows the messages between agents.

#### Scenario: One line in a narrow column
- **WHEN** the terminal panel is open beside a chat column of 484 px and the session has
  agents supervisor, analyst and developer
- **THEN** Yours | All stands in the tab bar on the tabs' line, and the feed has no row above it

#### Scenario: Arrows
- **WHEN** the focus is on `Yours` and the human presses the right arrow
- **THEN** `All` is chosen and has the focus

#### Scenario: Only on Activity
- **WHEN** the human opens the Flows tab
- **THEN** the bar's end shows Find and no Yours | All

#### Scenario: Both themes
- **WHEN** `All` is chosen, in the light or the dark theme
- **THEN** it has the frame in `--action` and `--ink` at weight 600, not its ground alone

## ADDED Requirements

### Requirement: On a phone held sideways the toggle ends the tab row

On a phone held sideways the icon button "Messages between agents" SHALL end the tab row of the
Activity tab, as the team's row is not shown there.

#### Scenario: Sideways
- **WHEN** a running session's Activity is open on a touch screen of 844×390
- **THEN** the icon button stands at the end of the tab row, at least 36 px high, and a tap
  presses it and shows the messages between agents

#### Scenario: Sideways on a small phone
- **WHEN** Activity is open on a touch screen of 568×320
- **THEN** all four tabs and the icon button show in the row

#### Scenario: Sideways, another tab
- **WHEN** the human opens the Flows tab on a touch screen of 844×390
- **THEN** the row has no such button
