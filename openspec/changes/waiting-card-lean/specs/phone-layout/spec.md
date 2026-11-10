## ADDED Requirements

### Requirement: On a phone the recommendation's splitter is easy to take

In the phone layout the recommendation's splitter of the chat's card SHALL take a touch 24 px
high, drawn as on a computer, and SHALL not scroll the page while it is dragged. It SHALL not show
while a field of the card has the focus.

#### Scenario: Dragged by a finger
- **WHEN** a gate with a long recommendation waits on a phone 390×844 and the human drags 8 px
  above the splitter's line upward
- **THEN** the recommendation's text grows and the feed does not scroll

## MODIFIED Requirements

### Requirement: On a phone the composer stays at hand

In the phone layout the window SHALL not scroll as a page; each page's content SHALL
scroll by itself under the top bar. The app SHALL be as high as the part of the window
the human sees, its bottom never cut by the browser's bars. In a session's chat the feed
SHALL scroll by itself, and the waiting card and the composer SHALL stay whole at the
chat's bottom; the card SHALL be at most half the chat's height, its head and footer whole and
only its report giving way.

#### Scenario: Writing with a gate waiting
- **WHEN** a gate waits and the human opens the session's chat on a phone 390×844
- **THEN** the composer is at the screen's bottom without scrolling, the card above it has
  its footer whole, and the feed above scrolls by itself

#### Scenario: The browser's bottom bar
- **WHEN** a question waits and the human opens the session's chat in a phone's browser
  whose bottom bar covers the window's last 90 px
- **THEN** the composer's lower edge is above that bar, and the whole composer and the
  card's Send button are in sight without scrolling

#### Scenario: The expanded card
- **WHEN** the human expands the waiting card on a phone
- **THEN** the card fills the page under the top bar, the session's tabs and the Team row
  are not shown, and its Send button is in sight, above the browser's bottom bar

### Requirement: On a phone a field in focus keeps the card and folds what is around it

In the phone layout, in a session's chat, while a field of the waiting card's footer has the
focus, the card SHALL not expand: the session's tabs, the Team row, the card's report, the
recommendation's splitter and the choices' area SHALL not be shown, and the composer SHALL be a
line: on a gate's tab "Commenting on gate #<id> above", on a question's the line of capability
chat-question-card. When the field loses the focus all of it SHALL show again.

#### Scenario: A gate's comment above the keyboard
- **WHEN** a gate waits in the session's chat on a phone 402×874, the human taps the
  gate's comment field and the keyboard leaves 440 px of the window visible
- **THEN** the card is not expanded, the session's tabs, the Team row and the report do not
  show, and the field, Approve, Reject and "Commenting on gate #1 above" lie within the
  visible 440 px

#### Scenario: An own answer
- **WHEN** a question with a free answer waits on the same phone and the human taps
  Other…
- **THEN** the field has the focus, the choices' area does not show, and the field, "Send
  answer to supervisor" and "Answering question #5 above" lie within the visible 440 px

#### Scenario: The keyboard closes
- **WHEN** the human closes the keyboard and the field loses the focus
- **THEN** the session's tabs, the report, the choices' area, the Team row and the composer
  show again, and the comment typed stays in the field

### Requirement: On a phone the card's field and buttons stay above the keyboard

With a field of the card in focus, the field, the buttons and the composer's line SHALL stay above
the on-screen keyboard, by the order of capability chat-question-card, requirement "A footer
taller than its room gives way in order"; the head SHALL go before the recommendation.

#### Scenario: Less room than the frame
- **WHEN** the keyboard leaves 350 px of the window visible and a gate's comment has the focus,
  under a recommendation of two lines
- **THEN** the head is gone or cut, and the field, Approve, Reject and the line lie within the
  visible 350 px

#### Scenario: Six choices
- **WHEN** the keyboard leaves 350 px of the window visible and Other… of a question of six
  choices has the focus
- **THEN** the field and Send answer lie within the visible 350 px

#### Scenario: Six choices under a recommendation
- **WHEN** the keyboard leaves 340 px of the window visible and the field of Other… or Skip
  has the focus, on a question of six choices under a recommendation of two lines
- **THEN** the choices' area does not show, and the recommendation, the field and Send answer
  lie whole within the visible 340 px

### Requirement: On a phone the waiting card's targets are 44 px

In the phone layout the card's tabs, Minimize and Expand (44×44), its fields, its chips, its
choices, Other… and Skip, and Approve, Reject and Send answer SHALL be 44 px high, and the answer's
buttons SHALL share the footer's width.

#### Scenario: Measured
- **WHEN** a question waits on a phone 390×844
- **THEN** its tab, a choice, Skip and Send answer are each 44 px high
