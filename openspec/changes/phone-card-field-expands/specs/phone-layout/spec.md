## MODIFIED Requirements

### Requirement: On a phone the composer stays at hand

In the phone layout the window SHALL not scroll as a page; each page's content SHALL
scroll by itself under the top bar. The app SHALL be as high as the part of the window
the human sees, its bottom never cut by the browser's bars. In a session's chat the feed
SHALL scroll by itself, and the waiting card and the composer SHALL stay whole at the
chat's bottom; the card SHALL be at most half the chat's height, its list scrolling
inside. An expanded card SHALL fill the session's page under the top bar: the feed, the
composer, the session's tabs and the Team row SHALL not be shown while it is expanded.

#### Scenario: Writing with a gate waiting
- **WHEN** a gate waits and the human opens the session's chat on a phone 390×844
- **THEN** the composer is at the screen's bottom without scrolling, the card above it is
  at most half the chat's height, and the feed above scrolls by itself

#### Scenario: The browser's bottom bar
- **WHEN** a question waits and the human opens the session's chat in a phone's browser
  whose bottom bar covers the window's last 90 px
- **THEN** the composer's lower edge is above that bar, and the whole composer and the
  card's Send button are in sight without scrolling

#### Scenario: The expanded card
- **WHEN** the human expands the waiting card on a phone
- **THEN** the card fills the page under the top bar, the session's tabs and the Team row
  are not shown, and its Send button is in sight, above the browser's bottom bar

#### Scenario: Folding the expanded card
- **WHEN** the human taps Collapse the card on a phone
- **THEN** the card stands above the composer again, and the session's tabs and the Team
  row show again

## ADDED Requirements

### Requirement: On a phone a field of the waiting card expands it

In the phone layout, in a session's chat, a field of the waiting card (a gate's comment, a
question's own answer, a skip's comment) taking the focus SHALL expand the card; the
field SHALL keep the focus and SHALL be shown within the card's list. The card SHALL stay
expanded when the field loses the focus or the on-screen keyboard closes, until the human
folds it or nothing waits. On Needs you, and outside the phone layout, a field's focus
SHALL not expand the card.

#### Scenario: A gate's comment above the keyboard
- **WHEN** a gate waits in the session's chat on a phone 402×874, the human taps the
  gate's comment field and the keyboard leaves 400 px of the window visible
- **THEN** the card is expanded, the comment field has the focus, and the field and
  Approve and Reject lie within the visible 400 px

#### Scenario: An own answer
- **WHEN** a question with a free answer waits on the same phone and the human taps
  Other…
- **THEN** the card is expanded with the own answer's field focused, and the field and
  "Send answer to supervisor" lie within the visible 400 px

#### Scenario: The keyboard closes
- **WHEN** the card was expanded by its comment field and the keyboard closes
- **THEN** the card stays expanded, and the comment typed stays in the field

#### Scenario: A computer
- **WHEN** the human clicks a gate's comment field with a mouse in a window 390 px wide
- **THEN** the card is not expanded
