# launch-notes Specification

## Purpose
How the notes under the fields of the New session window look: three levels (a quiet
hint or success, an amber warning panel, a red refusal panel) set by class and drawn
from the theme's tokens, so a warning and a refusal read as such, and Start stays off
while a refusal shows.

## Requirements

### Requirement: The New session window's notes come in three levels

Each note under the fields of the New session window SHALL show at one of three levels
by its class: a hint or a success (`field-note`, `field-note ok`) as quiet 12 px text
without a ground; a warning (`field-note warn`) as a panel on `--warn-ground` with a
`--warn` stripe on its left; a refusal (`field-note bad`) as a panel on `--danger-ground`
with a `--danger` stripe and a round `!` that is not part of its text. Both panels'
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

### Requirement: The notes' panels are readable in both themes

The text of a warning's and of a refusal's panel, and the muted text inside a refusal,
SHALL have a contrast of at least 4.5:1 with the panel's ground in the light and in the
dark theme, and the panels' colours SHALL be tokens of `web/src/tokens.css` only.

#### Scenario: The tokens' contrast test

- **WHEN** the unit test of the tokens runs
- **THEN** `--ink` and `--muted` on `--warn-ground` and on `--danger-ground`, `--warn` on
  `--warn-ground` and `--danger` on `--danger-ground` reach 4.5:1 in both themes

### Requirement: Start is off while a refusal shows under the fields

While a refusal (`field-note bad`) shows under a field of the New session window, in its
New and its Resume mode, the window's start button (Start session, Clone and start,
Create and start, Resume session) SHALL be off; a note that does not keep the session
from starting SHALL NOT be a refusal.

#### Scenario: A folder that is not a repository keeps Start off

- **WHEN** Where names a folder outside any git repository
- **THEN** its refusal shows and Start session is disabled

#### Scenario: The kits list does not load

- **WHEN** `/api/kits` answers with an error while the window has kits chosen
- **THEN** its error shows as a warning, not as a refusal, and Start stays on when the
  rest of the window is ready

#### Scenario: A stopped session's provider cannot run

- **WHEN** the Resume window opens for a stopped session whose provider is not among
  `/api/providers`, or is listed as not installed
- **THEN** the provider's refusal shows under Provider and Resume session is disabled;
  once the human picks an installed provider the refusal is gone and Resume session is
  on
