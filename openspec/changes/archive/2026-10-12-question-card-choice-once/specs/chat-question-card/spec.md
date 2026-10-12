## Purpose

An agent's question to the human (`ask_human`) as the web UI's session chat shows it once
it is closed: its choices and the human's reply in one card (docs/design/ui.md, A
question; Answer in the question card).

## ADDED Requirements

### Requirement: A closed question card shows the chosen choice once

A closed question card whose reply is in the window SHALL show the choice the human picked
only in the card's list of choices, marked "✓". The reply block under the list SHALL show
the small "Y", "You · answered" and the reply's time, then only the comment that came with
the choice when there is one (Markdown with line breaks); it SHALL NOT repeat the choice.
A reply in the human's own words SHALL show those words in the reply block, and no choice
in the list SHALL be marked for it.

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
