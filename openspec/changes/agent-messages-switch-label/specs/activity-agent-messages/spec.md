## ADDED Requirements

### Requirement: The switch for messages between agents says what it shows

A session's Activity tab SHALL end the team's row with a switch labelled "Messages
between agents". Off, which SHALL be the default, the chat SHALL show the messages with
the human only; on, it SHALL also show the messages agents send each other. The choice
SHALL be remembered in the browser, and an agent page's **All in Activity** SHALL open
the Activity tab with the switch on. The switch SHALL have the UI's own tooltip, shown on
hover and on the keyboard's focus: "Also show the messages agents send each other. Off:
only your conversation with the agents."

#### Scenario: Off by default
- **WHEN** a human opens session app's Activity tab for the first time in a browser,
  with a message from supervisor to w1 in the session
- **THEN** the checkbox "Messages between agents" is unchecked and the feed has no
  message from supervisor to w1

#### Scenario: On shows the messages between agents
- **WHEN** the human checks "Messages between agents"
- **THEN** the feed shows the message from supervisor to w1 with "→ w1", and after a
  reload the checkbox is still checked

#### Scenario: The tooltip explains it
- **WHEN** the human holds the pointer over the switch, or moves the keyboard's focus to
  its checkbox
- **THEN** a tooltip reads "Also show the messages agents send each other. Off: only
  your conversation with the agents." and goes when the pointer leaves, the focus goes,
  or on Esc

#### Scenario: All in Activity
- **WHEN** the switch is off and the human clicks **All in Activity** on w1's page
- **THEN** the Activity tab opens with "Messages between agents" checked
