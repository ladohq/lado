## MODIFIED Requirements

### Requirement: On a phone the composer stays at hand

In the phone layout the window SHALL not scroll as a page; each page's content SHALL
scroll by itself under the top bar, as on a computer's wide window. The app SHALL be as
high as the part of the window the human sees, between the browser's own bars, and its
bottom SHALL never be cut by them. In a session's chat the feed SHALL scroll by itself,
and the waiting card and the composer SHALL stay at the chat's bottom, whole; the card
SHALL be at most half the chat's height, its list scrolling inside, its Send row shown.
When the on-screen keyboard opens, the app SHALL shrink to the part above it: the top bar
SHALL stay at the screen's top, and the composer and the card's Send row SHALL stay above
the keyboard.

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
- **THEN** the card fills the chat and its Send button is in sight, above the browser's
  bottom bar

#### Scenario: The on-screen keyboard
- **WHEN** a question waits and the human taps the composer on a phone, and the keyboard
  covers the lower 300 px of the screen
- **THEN** the top bar stays at the screen's top, the composer and the card's Send button
  are above the keyboard, and the card is at most half the chat's height

#### Scenario: The keyboard closes
- **WHEN** the human closes the keyboard
- **THEN** the app is as high as the visible part of the window again, the composer at its
  bottom
