## MODIFIED Requirements

### Requirement: The New session window's notes come in three levels

Each note under the fields of the New session window SHALL show at one of three levels
by its class: a hint or a success (`field-note`, `field-note ok`) as quiet 12 px text
without a ground; a warning (`field-note warn`) as a panel on `--warn-ground`; a refusal (`field-note bad`) as
a panel on `--danger-ground` with a round `!` that is not part of its text. Neither has a
stripe on its left. Both panels'
text is 13 px in `--ink`; no note's text changes.

#### Scenario: A folder outside the workspace in the container

- **WHEN** in LADO's container the human types a repository outside the workspace in
  Where
- **THEN** under the check mark the warning `⚠ Outside the workspace (<folder>): …` shows
  as a panel whose computed background differs from that of a hint, and Start stays on

#### Scenario: A folder that is not a repository

- **WHEN** the human types a folder outside any git repository in Where
- **THEN** its refusal shows as a panel on the refusal's ground, with its hint, its
  command and Copy inside it, and its computed background differs from both a hint's and
  a warning's

#### Scenario: A hint stays quiet

- **WHEN** a note is a hint, such as "the repository's default branch" or "the only one
  installed"
- **THEN** it shows as before: 12 px muted text without a ground or a stripe
