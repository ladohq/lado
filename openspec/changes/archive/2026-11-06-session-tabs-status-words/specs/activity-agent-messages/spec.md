## MODIFIED Requirements

### Requirement: The toggle for messages between agents is Yours | All, on a phone a small icon

Outside the phone layout, while the tabs fit beside it, a session's Activity tab SHALL end the tab
bar with a `role="radiogroup"` named "Messages between agents" of two radios `Yours` and `All`, 26 px high, after the word
`Messages` while the bar has room for it; the keyboard SHALL reach the chosen one by Tab and move
by the arrows. In the phone layout the team's row SHALL end with one icon button of that name,
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

### Requirement: The toggle's tooltip says what each choice shows

Each radio SHALL have the UI's own tooltip, shown on hover and on the keyboard's focus: `Yours`
"Only your conversation with the agents", `All` "Also what agents write to each other". The icon
SHALL keep its tooltip that names its state and what a click does: unpressed "Messages between
agents: hidden" and "Click to also show what agents write to each other."; pressed "Messages between
agents: shown" and "Click to show only your conversation with the agents."

#### Scenario: The tooltip says the state
- **WHEN** the human holds the pointer over `All`, or moves the keyboard's focus to it
- **THEN** a tooltip reads "Also what agents write to each other", and goes when the
  pointer leaves, the focus goes, or on Esc

## ADDED Requirements

### Requirement: A narrow tab bar shows the icon instead of the radios

Outside the phone layout, when the tabs without counts do not fit beside the radios, the tab bar
SHALL show the phone's icon button in their place, with its name, state and tooltip. The icon and
the radios SHALL show the same choice, and the focus SHALL pass from one form to the other.

#### Scenario: The icon in a narrow column
- **WHEN** the chat is 420 px wide and the human presses the icon, and the window then widens
- **THEN** the icon is pressed and the feed shows the messages between agents, and at the wider
  width `All` is the chosen radio

#### Scenario: The focus when the form changes
- **WHEN** the focus is on `Yours` and the chat narrows until the icon stands for the radios
- **THEN** the focus is on the icon
