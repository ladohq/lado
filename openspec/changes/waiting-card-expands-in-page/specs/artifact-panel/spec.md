## ADDED Requirements

### Requirement: A chip on Needs you opens the artifact panel over Needs you

A chip on Needs you SHALL open the artifact panel over the Needs you page, as a step of
the browser's history, without leaving the page: its cards, their picks and an expanded
card SHALL stay as they were. ×, Esc, a click on the scrim and Back SHALL close it, the
focus going back to the chip. The address SHALL name the record and its session, so a
reload shows the same panel over Needs you.

#### Scenario: A chip in a card on Needs you
- **WHEN** the human has picked "Делай сам в ветке" in lad-46's card on Needs you and
  clicks its chip `lad-46-plan`
- **THEN** the panel shows `lad-46-plan` over Needs you, and after × the page shows the
  card with that choice still picked and the focus on the chip

#### Scenario: Back
- **WHEN** the panel is open over Needs you and the human goes Back
- **THEN** the panel closes and Needs you stays

#### Scenario: From an expanded card
- **WHEN** lad-46's card is expanded on Needs you and the human clicks its chip
- **THEN** the panel shows over the expanded card, and the card stays expanded after the
  panel closes
