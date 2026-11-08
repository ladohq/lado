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
  as a panel whose computed background differs from that of a hint, and the start button
  stays on

#### Scenario: A folder that is not a repository

- **WHEN** the human types a repository with no commits yet in Where
- **THEN** its refusal shows as a panel on the refusal's ground, with its hint, its
  command and Copy inside it, and its computed background differs from both a hint's and
  a warning's

#### Scenario: A hint stays quiet

- **WHEN** a note is a hint or a success, such as `✓ Ready · branch main` or `✓ New folder`
- **THEN** it shows as 12 px text without a ground or a stripe

### Requirement: Start is off while a refusal shows under the fields

While a refusal (`field-note bad`) shows under a field of the New session or the Resume
window, the window's start button (`Start in <place>`, `Clone and start in <folder>`, Create
and start, `Set up and start in <folder>`, `Resume <name>`) SHALL be off; a note that does
not keep the session from starting, the set-up panel among them, SHALL NOT be a refusal.

#### Scenario: A folder that is not a repository keeps Start off

- **WHEN** Where names a repository with no commits yet
- **THEN** its refusal shows and the start button is off

#### Scenario: The kits list does not load

- **WHEN** `/api/kits` answers with an error while the window has kits chosen
- **THEN** its error shows as a warning in Team, not as a refusal, and the start button
  stays on when the rest of the window is ready

#### Scenario: A stopped session's provider cannot run

- **WHEN** the Resume window opens for a stopped session whose provider is not among
  `/api/providers`, or is listed as not installed
- **THEN** Team opens, the provider's refusal shows under Agent and `Resume <name>` is off;
  once the human picks an installed provider the refusal is gone and `Resume <name>` is on
