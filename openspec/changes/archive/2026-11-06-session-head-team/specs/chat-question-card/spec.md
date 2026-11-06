## MODIFIED Requirements

### Requirement: The expanded card covers the chat's area, not the window

An icon button at
the right of the card's tabs in a session's chat (no text; its name and tooltip "Expand the
card") SHALL show the card over the chat's whole area, never over the whole window: the feed and
the composer hidden, the session's head, with the team, and its tabs seen and usable (but on a phone:
capability phone-layout; in a window of 601 to 900 px: the requirement "At 601 to 900 px the
expanded card fills the window under the top bar").

#### Scenario: The session around an expanded card
- **WHEN** the human expands the card in session lad-46's chat
- **THEN** the feed and the composer are hidden, the card fills the chat's width and
  height, and the session's tabs (Activity, Agents, Flows, Artifacts) and the team in the head
  are seen and can be clicked, with no scrim

#### Scenario: Expanded on a phone
- **WHEN** the human expands the card in session lad-46's chat on a phone
- **THEN** the session's tabs and the team row are hidden with the feed and the composer,
  and folding the card shows them again

### Requirement: At 601 to 900 px the expanded card fills the window under the top bar

In a window 601 to 900 px wide outside the phone layout, the expanded card SHALL be the window's
height under the top bar, the session strip and the tabs hidden with the feed and the
composer, also after the window narrows or turns, until it folds.

#### Scenario: Expanded
- **WHEN** the human expands a card in a window 768×700 or 768×1024 and turns the wheel
- **THEN** the card stands under the top bar, its footer lies within the window and nothing moves

#### Scenario: The window narrows
- **WHEN** the card is expanded in a window 1440×900 and the window narrows to 768×700
- **THEN** the card stands under the top bar and its footer lies within the window
