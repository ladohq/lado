## ADDED Requirements

### Requirement: On a phone a field in focus keeps the card and folds what is around it

In the phone layout, in a session's chat, while a field of the waiting card's footer has the
focus, the card SHALL not expand: the session's tabs, the Team row, the card's context and the
choices' area SHALL not be shown, and the composer SHALL be a line: on a gate's tab "Commenting
on gate #<id> above", on a question's the line of capability chat-question-card. When the field
loses the focus all of it SHALL show again.

#### Scenario: A gate's comment above the keyboard
- **WHEN** a gate waits in the session's chat on a phone 402×874, the human taps the
  gate's comment field and the keyboard leaves 440 px of the window visible
- **THEN** the card is not expanded, the session's tabs, the Team row and the context do not
  show, and the field, Approve, Reject and "Commenting on gate #1 above" lie within the
  visible 440 px

#### Scenario: An own answer
- **WHEN** a question with a free answer waits on the same phone and the human taps
  Other…
- **THEN** the field has the focus, the choices' area does not show, and the field, "Send
  answer to supervisor" and "Answering question #5 above" lie within the visible 440 px

#### Scenario: The keyboard closes
- **WHEN** the human closes the keyboard and the field loses the focus
- **THEN** the session's tabs, the context, the choices' area, the Team row and the composer
  show again, and the comment typed stays in the field

### Requirement: Outside the phone layout a field's focus changes nothing

Outside the phone layout a field's focus SHALL change nothing.

#### Scenario: A computer
- **WHEN** the human clicks a gate's comment field with a mouse in a window 390 px wide
- **THEN** the card and the composer stay as they were

### Requirement: On a phone Needs you keeps a field and its buttons above the keyboard

On Needs you in the phone layout, with a field of a card in focus, the page SHALL bring the
card's footer into the part above the on-screen keyboard. An expanded card SHALL keep its context
and the notifications' offer and the session's heading SHALL give way to it until the field
loses the focus. A button pressed SHALL keep the focus in the field.

#### Scenario: A card and an expanded card
- **WHEN** a gate's comment or an own answer has the focus on Needs you on a phone 402×874, in a
  card or an expanded one, and the keyboard leaves 440, 380 or 350 px visible
- **THEN** the field and Approve and Reject, or Send, lie whole between the top bar and the
  keyboard

#### Scenario: Approve with the field in focus
- **WHEN** the human taps Approve in the expanded card with the keyboard open
- **THEN** the gate is answered

### Requirement: On a phone a field keeps the context it needs

A field in the context of several questions SHALL keep that context, and SHALL stay in its view
when the keyboard opens; the session's tabs and the Team row SHALL not be shown while it has the
focus. An expanded card SHALL keep its context with a field in focus.

#### Scenario: Several questions
- **WHEN** a tab of three questions waits and the human taps Other… on the last, and the keyboard
  leaves 440 px visible
- **THEN** the context still shows, and the field lies within its visible part

#### Scenario: The expanded card
- **WHEN** the human expands the card to read its note and taps the comment field
- **THEN** the context stays

### Requirement: On a phone the card's field and buttons stay above the keyboard

With a field of the card in focus, the field, the buttons and the composer's line SHALL stay above
the on-screen keyboard, by the order of capability chat-question-card, requirement "A footer
taller than its room gives way in order"; the title's meta SHALL go before the title.

#### Scenario: Less room than the frame
- **WHEN** the keyboard leaves 350 px of the window visible and a gate's comment has the focus,
  under a recommendation of two lines
- **THEN** the title's meta is gone or the title too, and the field, Approve, Reject and the
  line lie within the visible 350 px

#### Scenario: Six choices
- **WHEN** the keyboard leaves 350 px of the window visible and Other… of a question of six
  choices has the focus
- **THEN** the field, Send answer and Skip question lie within the visible 350 px

#### Scenario: Six choices under a recommendation
- **WHEN** the keyboard leaves 340 px of the window visible and the field of Other… or Skip
  question has the focus, on a question of six choices under a recommendation of two lines
- **THEN** the choices' area does not show, and the recommendation, the field, Send answer and
  Skip question lie whole within the visible 340 px

### Requirement: On a phone a gate's and a question's tabs stand whole

In the phone layout two tabs of the waiting card SHALL stand whole in their row, a name cut with
an ellipsis before the row scrolls, and each SHALL keep its count.

#### Scenario: Two tabs
- **WHEN** a gate of ship/x and a question of the supervisor wait on a phone 390×844 or 360×780
- **THEN** both tabs lie within their row and show their counts, whichever is shown

### Requirement: On a phone the waiting card's targets are 44 px

In the phone layout the card's tabs, Minimize and Expand (44×44), its fields, its chips and
Approve, Reject, Send answer and Skip question SHALL be 44 px high. "↓ more" SHALL stay 24 px:
Expand does the same.

#### Scenario: Measured
- **WHEN** a question waits on a phone 390×844
- **THEN** its tab, a choice, Send answer and Skip question are each 44 px high

## MODIFIED Requirements

### Requirement: On a phone the composer stays at hand

In the phone layout the window SHALL not scroll as a page; each page's content SHALL
scroll by itself under the top bar. The app SHALL be as high as the part of the window
the human sees, its bottom never cut by the browser's bars. In a session's chat the feed
SHALL scroll by itself, and the waiting card and the composer SHALL stay whole at the
chat's bottom; the card's title and context SHALL be at most 40 % of the chat's height, its
context scrolling inside, and its footer SHALL be whole under them.

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

### Requirement: On a phone held sideways the waiting card starts minimized

In the phone layout no higher than 500 px the waiting card in a session's chat SHALL show
minimized (its tabs and one line), and a tap on a tab or its line SHALL show the card
expanded over the chat's area; Esc or the card's fold button SHALL minimize it again. The
Team row and the composer's "to" line SHALL not be shown. This SHALL not change the
minimized state the card remembers for the session.

#### Scenario: Answering a gate sideways
- **WHEN** gate #1 of ship/x waits and the human opens the chat on a phone 844×390
- **THEN** the card is minimized above the composer; a tap on its tab ship/x shows the
  gate over the chat with Approve and Reject

#### Scenario: Turning back upright
- **WHEN** the human turns the phone upright with the card minimized only because it was
  sideways
- **THEN** the card shows whole, its footer in sight

### Requirement: On a phone the app shrinks above the on-screen keyboard

When the on-screen keyboard opens on a phone, the app SHALL shrink to the part of the
window above it: the top bar SHALL stay at the screen's top, and the composer and the
waiting card's Send row SHALL stay above the keyboard. When the keyboard closes, the app
SHALL be as high as the visible part of the window again.

#### Scenario: The on-screen keyboard
- **WHEN** a question waits and the human taps the composer on a phone, and the keyboard
  covers the lower 300 px of the screen
- **THEN** the top bar stays at the screen's top, the composer and the card's Send button
  are above the keyboard

#### Scenario: The keyboard closes
- **WHEN** the human closes the keyboard
- **THEN** the app is as high as the visible part of the window again, the composer at its
  bottom

### Requirement: On a phone an expanded card hides the session's tabs and the Team row

In the phone layout an expanded waiting card in a session's chat SHALL fill the session's
page under the top bar: the feed, the composer, the session's tabs and the Team row SHALL
not be shown while it is expanded, whether its button or the phone held sideways expanded
it, and SHALL show again when it folds.

#### Scenario: Expanded by its button
- **WHEN** the human taps Expand the card in the session's chat on a phone
- **THEN** the session's tabs and the Team row are not shown

#### Scenario: Folding the expanded card
- **WHEN** the human taps Collapse the card on a phone
- **THEN** the card stands above the composer again, and the session's tabs and the Team
  row show again

## REMOVED Requirements

### Requirement: On a phone a field of the waiting card expands it

**Reason**: the field now stands in the card's footer, always in sight, so nothing has to be
expanded for it; the expanded card hid the session and stayed after the keyboard closed.

**Migration**: "On a phone a field in focus keeps the card and folds what is around it".
