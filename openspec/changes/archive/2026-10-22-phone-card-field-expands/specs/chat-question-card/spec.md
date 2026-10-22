## MODIFIED Requirements

### Requirement: The expanded card covers its page's area, not the window

An icon button at
the right of the card's tabs (no text; its name and tooltip "Expand the card") SHALL show the
card over its page's area, never over the whole window: in a session's chat over the
chat's whole area, the feed and the composer hidden, the session's head, tabs and team
row seen and usable (but on a phone: capability phone-layout); on Needs you over the
page's content area under its session's name line, the other sessions' cards and the
waiting agents' rows hidden.

#### Scenario: The session around an expanded card
- **WHEN** the human expands the card in session lad-46's chat
- **THEN** the feed and the composer are hidden, the card fills the chat's width and
  height, and the session's tabs (Activity, Agents, Flows, Artifacts) and the team row are
  seen and can be clicked, with no scrim

#### Scenario: Expanded on Needs you
- **WHEN** Needs you shows the cards of lad-46 and docs-site and the human expands
  lad-46's
- **THEN** lad-46's name line and its card fill the page's content area, docs-site's card
  and the agents' rows are hidden, and folding it shows them again

#### Scenario: Expanded on a phone
- **WHEN** the human expands the card in session lad-46's chat on a phone
- **THEN** the session's tabs and the team row are hidden with the feed and the composer,
  and folding the card shows them again
