## MODIFIED Requirements

### Requirement: A closed question card shows the chosen choice once

A closed question card whose reply is in the window SHALL show the choice the human picked
only in the card's list of choices, marked "✓". The reply block under the list SHALL show
the small "Y", "You · answered" and the reply's time, then only the comment that came with
the choice when there is one (Markdown with line breaks); it SHALL NOT repeat the choice.
A reply in the human's own words SHALL show those words in the reply block, and no choice
in the list SHALL be marked for it. The quiet line of the supervisor's recommendation in a
closed card (capability lead-recommendation) names the option the supervisor recommended,
not the human's choice: it is no repeat of the choice, and the choice stays marked only in
the list.

#### Scenario: A choice without a comment
- **WHEN** the human answers question #5 (choices "yes", "later") with the choice "yes"
- **THEN** its card lists "✓ yes" and "later", and its reply block holds "You · answered"
  and the time and no other text

#### Scenario: A choice with a comment
- **WHEN** the human answers question #8 with the choice "later" and the comment "after the
  tag"
- **THEN** its card lists "✓ later" once, and its reply block holds "You · answered", the
  time and "after the tag"

#### Scenario: An answer in the human's own words
- **WHEN** the human answers question #5 with the text "after the release" and no choice
- **THEN** no choice of its card is marked, and its reply block holds "You · answered", the
  time and "after the release"

#### Scenario: An answer given after other rows
- **WHEN** the human's choice "later" with the comment "after the tag" comes after other
  rows of the chat
- **THEN** the card shows it as in the scenario of a choice with a comment, and the quiet
  line "You answered question #8 ↑" where it was given still starts with "later" and the
  comment

#### Scenario: A choice the supervisor recommended too
- **WHEN** the human answers question #8 with the choice "later" and the supervisor had
  recommended "later"
- **THEN** its card lists "✓ later" once, the recommendation's quiet line reads
  "Supervisor recommended: later", and the reply block does not name the choice
