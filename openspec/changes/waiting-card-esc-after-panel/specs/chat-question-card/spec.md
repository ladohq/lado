## MODIFIED Requirements

### Requirement: The expanded card comes back as it was

Nothing around the expanded card
SHALL be dimmed. There an icon button ("Collapse the card") or Esc SHALL bring it back,
as it was before (minimized when it was), and it SHALL come back by itself when nothing
waits any more. While an artifact panel is open, Esc SHALL close the panel only and leave
the card expanded. Once the panel is gone from the page, the next Esc SHALL fold the card,
however soon it follows.

#### Scenario: Expanded and back
- **WHEN** the human clicks the expand icon, then presses Esc
- **THEN** the card covers the chat's area, then stands above the composer again

#### Scenario: Expanded from minimized
- **WHEN** the card is minimized and the human clicks the expand icon, then presses Esc
- **THEN** the whole card covers the chat's area, then stands minimized above the composer

#### Scenario: An artifact from an expanded card
- **WHEN** the human clicks the chip `lad-46-plan` in the expanded card, presses Esc, then
  Esc again
- **THEN** the artifact panel shows on the right over the card, the first Esc closes it
  with the focus back on the chip and the card still expanded with its picks, and the
  second Esc folds the card with the focus on the expand button

#### Scenario: A quick second Esc
- **WHEN** the human closes the artifact panel over the expanded card with Esc and presses
  Esc again the moment the panel is gone
- **THEN** the second Esc folds the card
