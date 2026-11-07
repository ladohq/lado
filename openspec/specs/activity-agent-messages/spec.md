# activity-agent-messages Specification

## Purpose
The choice of a session's Activity tab that adds the messages agents send each other to
the human's chat: `Yours | All` at the tab bar's end, on a phone a small icon button at the
end of the team's row, its tooltip that says what it shows, its default and its memory in
the browser (docs/design/ui.md, Activity).

## Requirements

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

### Requirement: The messages between agents are hidden by default and the choice is remembered

`Yours`, or the icon unpressed, which SHALL be the default, SHALL show the messages with the
human only; `All`, or the icon pressed, SHALL also show the messages agents send each other. The
choice SHALL be remembered in the browser, and an agent page's **All in Activity** SHALL open
the Activity tab with `All` chosen.

#### Scenario: Unpressed by default
- **WHEN** a human opens session app's Activity tab for the first time in a browser,
  with a message from supervisor to w1 in the session
- **THEN** `Yours` is chosen and the feed has no message from supervisor to w1

#### Scenario: Pressed shows the messages between agents
- **WHEN** the human chooses `All`
- **THEN** `All` is chosen, the feed shows the message from supervisor to w1 with
  "→ w1", and after a reload `All` is still chosen

#### Scenario: All in Activity
- **WHEN** `Yours` is chosen and the human clicks **All in Activity** on w1's page
- **THEN** the Activity tab opens with `All` chosen

#### Scenario: On a phone
- **WHEN** the human presses the icon "Messages between agents" on a phone
- **THEN** the button is pressed and the feed shows the message from supervisor to w1

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

### Requirement: On a phone a stopped session's toggle shows its words

In the phone layout, where a stopped session has no team beside it, the icon button "Messages between
agents" SHALL show those words beside its icon, 44 px high, and SHALL keep its name and
`aria-pressed`.

#### Scenario: A stopped session on a phone
- **WHEN** the human opens Activity of a stopped session at 390 px
- **THEN** the button shows its icon and "Messages between agents"

#### Scenario: A running session on a phone
- **WHEN** the human opens Activity of a running session at 390 px
- **THEN** the button shows only its icon

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
