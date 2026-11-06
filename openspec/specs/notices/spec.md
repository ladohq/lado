# notices Specification

## Purpose
How the web UI's error and warning notices look: a ground and an icon, never a coloured stripe on
the left.

## Requirements

### Requirement: A notice has a ground and an icon, not a stripe

An error notice SHALL show on `--danger-ground` with an alert icon and `--danger` text, and a warning
on `--warn-ground` with an alert icon and `--warn` text, in both themes, and SHALL have no coloured
left stripe. The session list's selected row SHALL keep its stripe; quotes, a gate's note, the
recommendation and the waiting card's tab are not notices.

#### Scenario: An error
- **WHEN** a page shows `<p class="problem">`
- **THEN** its computed background is `--danger-ground`, its left border is as wide as its other
  borders, and its icon shows before the text

#### Scenario: A warning
- **WHEN** the Share window shows its warning
- **THEN** its computed background is `--warn-ground` and it has no left stripe

#### Scenario: The selected session
- **WHEN** a session is selected in the list
- **THEN** its row keeps its stripe

#### Scenario: The dark theme
- **WHEN** the theme is dark
- **THEN** a notice's text and its ground have a contrast of at least 4.5:1
