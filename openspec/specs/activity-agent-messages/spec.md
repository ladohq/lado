# activity-agent-messages Specification

## Purpose
The toggle of a session's Activity tab that adds the messages agents send each other to
the human's chat: a small icon button at the end of the team's row, its tooltip that
says what it shows, its default and its memory in the browser (docs/design/ui.md,
Activity).

## Requirements

### Requirement: The toggle for messages between agents is a small icon that says what it shows

A session's Activity tab SHALL end the team's row with one icon button named "Messages
between agents", pressed (`aria-pressed`) while the chat shows the messages between
agents. The button SHALL be small enough that, in a chat column of 484 px, three agents'
chips and the button stand on one line.

#### Scenario: One line in a narrow column
- **WHEN** the terminal panel is open beside a chat column of 484 px and the session has
  agents supervisor, analyst and developer
- **THEN** the three chips and the button stand on the team's first line

### Requirement: The messages between agents are hidden by default and the choice is remembered

Unpressed, which SHALL be the default, the chat SHALL show the messages with the
human only; pressed, it SHALL also show the messages agents send each other. The choice
SHALL be remembered in the browser, and an agent page's **All in Activity** SHALL open
the Activity tab with the button pressed.

#### Scenario: Unpressed by default
- **WHEN** a human opens session app's Activity tab for the first time in a browser,
  with a message from supervisor to w1 in the session
- **THEN** the button "Messages between agents" is not pressed and the feed has no
  message from supervisor to w1

#### Scenario: Pressed shows the messages between agents
- **WHEN** the human clicks "Messages between agents"
- **THEN** the button is pressed, the feed shows the message from supervisor to w1 with
  "→ w1", and after a reload the button is still pressed

#### Scenario: All in Activity
- **WHEN** the button is not pressed and the human clicks **All in Activity** on w1's
  page
- **THEN** the Activity tab opens with "Messages between agents" pressed

### Requirement: The toggle's tooltip names its state and what a click does

The button SHALL have the UI's own tooltip,
shown on hover and on the keyboard's focus, that names its state and what a click does:
unpressed "Messages between agents: hidden" and "Click to also show what agents write to
each other."; pressed "Messages between agents: shown" and "Click to show only your
conversation with the agents."

#### Scenario: The tooltip says the state
- **WHEN** the button is not pressed and the human holds the pointer over it, or moves
  the keyboard's focus to it
- **THEN** a tooltip reads "Messages between agents: hidden" and "Click to also show
  what agents write to each other.", and goes when the pointer leaves, the focus goes,
  or on Esc
