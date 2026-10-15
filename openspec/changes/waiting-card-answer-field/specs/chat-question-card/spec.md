## ADDED Requirements

### Requirement: The card's text fields grow with their text and stay in view

The waiting card's text fields, an own answer (Other…), the comment of a Skip and a gate's
comment for the next step, SHALL open 3 lines high, SHALL grow with their text up to
8 lines and then scroll inside, and SHALL have no resize handle; each SHALL be as wide as
its question. While the human types in one of them, its lower edge with the caret SHALL
stay in view within the card: when the field grows past the card's visible list, the list
SHALL scroll by as much. A gate's comment field SHALL grow the same way wherever the
gate's panel shows.

#### Scenario: A short own answer
- **WHEN** the human picks Other… and types one short line
- **THEN** the field is 3 lines high

#### Scenario: A long own answer
- **WHEN** the human types an answer of 12 lines in the field of Other…
- **THEN** the field is 8 lines high, scrolls inside, and its lower edge with the caret
  is within the card's list and within the window

#### Scenario: The expanded card
- **WHEN** the card is expanded and the human types an answer of 12 lines
- **THEN** the field is 8 lines high and its lower edge is above the Send row and within
  the window

#### Scenario: A gate's comment
- **WHEN** the human types a comment of 12 lines on a gate's tab
- **THEN** the field is 8 lines high, scrolls inside, and its lower edge is above the Send
  row and within the window
