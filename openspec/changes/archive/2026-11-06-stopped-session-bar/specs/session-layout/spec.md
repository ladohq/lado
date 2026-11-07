## MODIFIED Requirements

### Requirement: Above 900 px the chat keeps 420 px

In a window wider than 900 px that is not the phone layout, the session's column SHALL be at
least 420 px wide. Short of room, terminals the human did not open SHALL fold to their strip;
terminals the human opened SHALL stay and the session list SHALL fold to its strip instead. The
rail SHALL never fold by itself. A stopped session's terminals count as opened only when the human
opened them there.

#### Scenario: Terminals nobody opened
- **WHEN** nothing is stored and the window is 1024 px wide
- **THEN** the list is open, the terminals are in their strip and the chat is 672 px wide

#### Scenario: Terminals the human opened
- **WHEN** the human opens the terminals in a window 1024 px wide
- **THEN** the terminals stay open, the list folds to its strip of 48 px and the chat is at
  least 420 px wide

#### Scenario: Every width
- **WHEN** the window is 901, 1024, 1101, 1280 or 1440 px wide, with the terminals opened by the
  human or not
- **THEN** the chat is at least 420 px wide

#### Scenario: A stopped session
- **WHEN** the terminals are stored open and a stopped session shows at 1024 px
- **THEN** they are in their strip and the list is open
