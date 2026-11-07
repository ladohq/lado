## MODIFIED Requirements

### Requirement: The UI picks the phone layout by the screen and the pointer

The web UI SHALL use its phone layout exactly while the window is no wider than 600 px, with any
pointer, or the primary pointer is coarse (a touch screen) and the window is no higher than
500 px; the layout SHALL follow the window when it turns or resizes, without a reload. A wider
window with a fine pointer (a mouse or a trackpad) SHALL never use the phone layout, however low.
There SHALL be no setting or switch for it.

#### Scenario: A phone held upright
- **WHEN** the UI is opened on a touch screen 390 px wide and 844 px high
- **THEN** it shows the phone layout

#### Scenario: A phone held sideways
- **WHEN** the same phone turns to 844 px wide and 390 px high
- **THEN** the UI keeps the phone layout, in its sideways form, without a reload

#### Scenario: A computer's narrow window
- **WHEN** the UI is opened with a mouse in a window 390 px wide and 844 px high
- **THEN** it shows the phone layout, with Menu and the session's title in place

#### Scenario: A computer's low window
- **WHEN** the UI is opened with a mouse in a window 1280 px wide and 400 px high
- **THEN** it does not show the phone layout

#### Scenario: A touch laptop
- **WHEN** the UI is opened on a touch screen 1440 px wide and 900 px high
- **THEN** it does not show the phone layout

#### Scenario: A tablet
- **WHEN** the UI is opened on a touch screen 820 px wide and 1180 px high
- **THEN** it does not show the phone layout

### Requirement: Only a phone's chat folds around a field

On Needs you, and outside the phone layout, a field's focus SHALL change nothing.

#### Scenario: A computer
- **WHEN** the human clicks a gate's comment field with a mouse in a window 700 px wide
- **THEN** the card and the composer stay as they were

#### Scenario: Needs you on a phone
- **WHEN** the human taps a card's field on Needs you on a phone and the keyboard opens
- **THEN** nothing folds, the browser keeps the field in sight, and the page scrolls on to the
  buttons under it, which the keyboard may cover

## ADDED Requirements

### Requirement: On a phone the top bar's title and link are easy to tap

In the phone layout the session's title SHALL have a target 44 px high, the height of the top bar.
The change feed's link SHALL have a target 44 px high and 33 px wide, taken from the gaps at its
sides, so that the title loses no width. What is drawn SHALL not change.

#### Scenario: The title
- **WHEN** the human taps the top bar's height above the title's text
- **THEN** the session's details open

#### Scenario: The link
- **WHEN** the human taps 8 px beside the link's dot
- **THEN** the System panel opens
