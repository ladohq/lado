## ADDED Requirements

### Requirement: A ring around an item of the card shows whole

The waiting card SHALL show the ring drawn around one of its items whole, on all four
sides: the focus ring of a gate's comment for the next step, of an own answer and of a
Skip's comment, and the ring of a question the human came to from the feed. Neither the
card's scrolling list nor the panel around it SHALL cut a ring at rest, while the human
types, or after the list scrolled a field into view. The questions, the fields and the
Send row SHALL stay where they were before this rule.

#### Scenario: A gate's comment with the focus
- **WHEN** the human clicks into the comment field on a gate's tab
- **THEN** the field's focus ring is whole on the left, the top, the right and the bottom,
  within the card's list

#### Scenario: A long gate's comment
- **WHEN** the human types a comment of 12 lines on a gate's tab
- **THEN** the field, 8 lines high and scrolled into view, has its focus ring whole on all
  four sides

#### Scenario: An own answer with the focus
- **WHEN** the human picks Other… on a question and its field gets the focus
- **THEN** the field's focus ring is whole on all four sides

#### Scenario: The first question marked
- **WHEN** the human comes to the card's first question from its line in the feed
- **THEN** the question's ring is whole on all four sides, its top too

#### Scenario: A narrow window
- **WHEN** the window is 600 px wide and the comment field on a gate's tab has the focus
- **THEN** the field's focus ring is whole on all four sides

#### Scenario: Nothing moves
- **WHEN** a gate's tab is shown
- **THEN** its question and its comment field start as far from the panel's left edge as
  before, and the Send row stands where it stood
