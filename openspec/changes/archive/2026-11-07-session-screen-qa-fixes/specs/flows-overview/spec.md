## MODIFIED Requirements

### Requirement: A run's card and row show its task

A run's card in Active and row in History SHALL show the first line of its task under its name, in
13 px `--muted`, on one line cut with "…", a waiting run's too. A run with a blank task SHALL show no
such line.

#### Scenario: A long task
- **WHEN** a run's task starts with a line longer than the row
- **THEN** that line shows under the name, cut with "…", and the task's later lines do not show

#### Scenario: A blank task
- **WHEN** a run's task is blank
- **THEN** its row shows the name and its state line only

#### Scenario: A waiting run
- **WHEN** a run waits for the human
- **THEN** its task's line is `--muted` and the line under it is `--human`

## ADDED Requirements

### Requirement: A run's tooltip shows the task its row hides

When a run's card or row hides part of its task, by a cut line or by later lines, hovering it or
giving it the keyboard's focus SHALL show the task in a tooltip with its line breaks, at most 12
lines and 600 characters. A longer task SHALL end with "…" and the line "The rest is on the run's
page". A task shown whole SHALL have no such tooltip.

#### Scenario: A cut line
- **WHEN** the pointer rests on a row whose task's line is cut
- **THEN** the tooltip shows the whole line

#### Scenario: Several lines by the keyboard
- **WHEN** the keyboard's focus reaches a row whose task has three short lines
- **THEN** the tooltip shows the three lines

#### Scenario: A very long task
- **WHEN** the pointer rests on a row whose task has 40 lines
- **THEN** the tooltip shows the first 12 lines, "…" and "The rest is on the run's page"

#### Scenario: Nothing hidden
- **WHEN** the pointer rests on a row whose one-line task fits
- **THEN** no tooltip shows

#### Scenario: A tap
- **WHEN** the human taps a run's row on a touch screen
- **THEN** the run opens and no tooltip shows
