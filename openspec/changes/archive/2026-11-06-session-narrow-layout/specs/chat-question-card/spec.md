## MODIFIED Requirements

### Requirement: The card keeps the chat in view and expands within its page

The card SHALL be as high as its content. Its title and context together SHALL be at most
40 % of the chat's height unless the human set another height; its footer SHALL not count in
that limit and SHALL not be cut by it. Its context SHALL scroll inside it while its tabs and its
footer stay in view.

#### Scenario: Long questions
- **WHEN** the supervisor's tab holds three questions whose text is longer than half the
  chat
- **THEN** the card's context scrolls inside and "Send 3 answers to supervisor" stays in view

#### Scenario: A short gate
- **WHEN** a gate with a note of two lines waits in a chat 700 px high
- **THEN** the card is as high as its content, with no empty room in it

#### Scenario: A long note in a narrow window
- **WHEN** a gate with a note of 60 lines waits in a chat 800 px high in a window 800 px wide
- **THEN** its title and context are at most 320 px high, and its comment field and Approve
  follow right under them

### Requirement: The expanded card covers the chat's area, not the window

An icon button at
the right of the card's tabs in a session's chat (no text; its name and tooltip "Expand the
card") SHALL show the card over the chat's whole area, never over the whole window: the feed and
the composer hidden, the session's head, tabs and team row seen and usable (but on a phone:
capability phone-layout; in a window of 601 to 900 px: the requirement "At 601 to 900 px the
expanded card fills the window under the top bar").

#### Scenario: The session around an expanded card
- **WHEN** the human expands the card in session lad-46's chat
- **THEN** the feed and the composer are hidden, the card fills the chat's width and
  height, and the session's tabs (Activity, Agents, Flows, Artifacts) and the team row are
  seen and can be clicked, with no scrim

#### Scenario: Expanded on a phone
- **WHEN** the human expands the card in session lad-46's chat on a phone
- **THEN** the session's tabs and the team row are hidden with the feed and the composer,
  and folding the card shows them again

## REMOVED Requirements

### Requirement: A window that scrolls keeps the footer in sight

**Reason**: A session's page no longer scrolls at 601 to 900 px (capability session-layout), so
nothing sticks; the human sees the same through "At 601 to 900 px the footer and the composer
stay in sight".

### Requirement: In a window that scrolls the expanded card holds the page

**Reason**: The page no longer scrolls at 601 to 900 px, so there is nothing to hold; the human
sees the same through "At 601 to 900 px the expanded card fills the window under the top bar".

## ADDED Requirements

### Requirement: At 601 to 900 px the footer and the composer stay in sight

In a window 601 to 900 px wide outside the phone layout, the chat's card SHALL stand above the
composer at the chat's lower edge, its parts giving way in their order, and its footer and the
composer SHALL lie within the window however long the note and however far the feed is scrolled.
A window too low for both SHALL keep the card's buttons before the composer.

#### Scenario: A low window
- **WHEN** a gate with a long note waits in a window 768×700
- **THEN** the recommendation, the field, Approve, Reject and the composer lie within the window

#### Scenario: A card that grew
- **WHEN** the human opens the recommendation and types 4 lines in a window 768×700 or 768×500,
  or a question of six choices waits there with its own answer open
- **THEN** the context gives way, and the field and the buttons lie within the window

#### Scenario: The sessions' list opens or closes
- **WHEN** the human opens the sessions' list over the chat in a window 768×700, or closes it
- **THEN** the card and its footer stay where they are

### Requirement: At 601 to 900 px the expanded card fills the window under the top bar

In a window 601 to 900 px wide outside the phone layout, the expanded card SHALL be the window's
height under the top bar, the session strip, the tabs and the team row hidden with the feed and the
composer, also after the window narrows or turns, until it folds.

#### Scenario: Expanded
- **WHEN** the human expands a card in a window 768×700 or 768×1024 and turns the wheel
- **THEN** the card stands under the top bar, its footer lies within the window and nothing moves

#### Scenario: The window narrows
- **WHEN** the card is expanded in a window 1440×900 and the window narrows to 768×700
- **THEN** the card stands under the top bar and its footer lies within the window
