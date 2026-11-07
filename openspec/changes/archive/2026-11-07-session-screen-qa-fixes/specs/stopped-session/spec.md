## MODIFIED Requirements

### Requirement: A stopped session shows no team

A stopped session SHALL show no team in the head. On a phone its Activity SHALL show neither the
word Team nor chips. Held upright, the toggle "Messages between agents" SHALL stay, with its words,
44 px high and its pressed state; held sideways, it SHALL be the icon button at the end of the tab
row.

#### Scenario: Above a phone
- **WHEN** the human opens a stopped session at 1440 px
- **THEN** the head has no group named Team

#### Scenario: A phone
- **WHEN** the human opens Activity of a stopped session at 390 px
- **THEN** no word Team shows and the toggle reads "Messages between agents"

#### Scenario: An empty feed sideways
- **WHEN** a stopped session's feed says "No messages with you. Messages between agents are hidden."
  on a touch screen of 844×390 and the human taps the icon button
- **THEN** the button is pressed and the feed shows what All shows
