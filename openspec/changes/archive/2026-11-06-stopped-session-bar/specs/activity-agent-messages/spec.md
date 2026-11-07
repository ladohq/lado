## ADDED Requirements

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
