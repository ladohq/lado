## RENAMED Requirements

- FROM: `### Requirement: The card keeps the chat in view and expands to the window`
- TO: `### Requirement: The card keeps the chat in view and expands within its page`

## MODIFIED Requirements

### Requirement: The card keeps the chat in view and expands within its page

The card SHALL be at most half the chat's height; its list of questions SHALL scroll inside
it while its tabs and its Send row stay in view. An icon button at the right of its tabs
(no text; its name and tooltip "Expand the card") SHALL show the card over its page's
area, never over the whole window: in a session's chat over the chat's whole area, the
feed and the composer hidden, the session's head, tabs and team row seen and usable; on
Needs you over the page's content area under its session's name line, the other
sessions' cards and the waiting agents' rows hidden. Nothing around it SHALL be dimmed.
There an icon button ("Collapse the card") or Esc SHALL bring it back, and it SHALL come
back by itself when nothing waits any more. While an artifact panel is open, Esc SHALL
close the panel only and leave the card expanded.

#### Scenario: Long questions
- **WHEN** the supervisor's tab holds three questions whose text is longer than half the
  chat
- **THEN** the card's list scrolls inside and "Send 3 answers to supervisor" stays in view

#### Scenario: Expanded and back
- **WHEN** the human clicks the expand icon, then presses Esc
- **THEN** the card covers the chat's area, then stands above the composer again

#### Scenario: The session around an expanded card
- **WHEN** the human expands the card in session lad-46's chat
- **THEN** the feed and the composer are hidden, the card fills the chat's width and
  height, and the session's tabs (Activity, Agents, Flows, Artifacts) and the team row are
  seen and can be clicked, with no scrim

#### Scenario: An artifact from an expanded card
- **WHEN** the human clicks the chip `lad-46-plan` in the expanded card, presses Esc, then
  Esc again
- **THEN** the artifact panel shows on the right over the card, the first Esc closes it
  with the focus back on the chip and the card still expanded with its picks, and the
  second Esc folds the card with the focus on the expand button

#### Scenario: Expanded on Needs you
- **WHEN** Needs you shows the cards of lad-46 and docs-site and the human expands
  lad-46's
- **THEN** lad-46's name line and its card fill the page's content area, docs-site's card
  and the agents' rows are hidden, and folding it shows them again
