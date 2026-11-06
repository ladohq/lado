## MODIFIED Requirements

### Requirement: The team is one stop of the keyboard

Outside the phone layout the team SHALL be a `role="toolbar"` named `Team`, one Tab stop, in which
the arrows, Home and End move among its agents, run links and list button. An agent SHALL be named
`<name>, <role>, <status>`, the role left out when it is the name, by the popup's words. The
button SHALL be named `All N agents`, `<M> more agents` or, with no avatar, `<M> agents`, with `,
<K> waits for you` when one hidden agent waits and `, <K> wait for you` when more do.

#### Scenario: Arrows
- **WHEN** the focus is on the team's first agent and the human presses the right arrow, then End
- **THEN** the focus moves to the next item, then to the team's last item, and one Tab leaves the
  team for Stop

#### Scenario: A name
- **WHEN** a screen reader reads `reviewer`, with role `reviewer`, while it waits
- **THEN** it says `reviewer, waits for you`

## ADDED Requirements

### Requirement: The team's list button says its name in a tooltip

The team's list button SHALL show its accessible name as the UI's tooltip, on hover and on the
keyboard's focus, but not while the list is open.

#### Scenario: The button's tooltip
- **WHEN** the human holds the pointer over the chevron of a team of 12, or over `+8` with two of
  the hidden agents waiting
- **THEN** a tooltip reads `All 12 agents`, or `8 more agents, 2 wait for you`

#### Scenario: With the list open
- **WHEN** the human opens the list and the pointer stays on the button
- **THEN** no tooltip shows

### Requirement: An agent's status reads the same wherever the UI names it

The UI SHALL name an agent's status by the popup's words (`working`, `in the background`, `idle`,
`waits for you`, `starting`, `stopped`) in the Agents tab's rows and on an agent's page, in the
update's list of what to restart, and in an accessible name of a terminal's tab or a phone's chip.

#### Scenario: A row of the Agents tab
- **WHEN** an agent has waited for 6 minutes
- **THEN** its row reads `waits for you · 6 min`

#### Scenario: An agent's page
- **WHEN** the human opens the page of an agent that has waited for 6 minutes
- **THEN** its line reads `waits for you · 6 min · spawned` with the time

#### Scenario: What to restart
- **WHEN** an update lists a session whose supervisor is busy
- **THEN** the list reads `supervisor working`
