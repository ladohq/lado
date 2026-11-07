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

### Requirement: The kit windows' warnings and a failed login are notices

The warnings "Not from the official marketplace." and "New MCP server…" of the kit windows and the
line about the running sessions of the kit removal window SHALL be warning notices. The heading of
a failed login SHALL be an error notice, and the quote of what the CLI said SHALL have no left
stripe. Orange SHALL not be the ground of any of them.

#### Scenario: A kit from outside the marketplace
- **WHEN** the install window of a kit that needs confirmation is open
- **THEN** "Not from the official marketplace." has `--warn-ground`, an icon and no border

#### Scenario: A new MCP server
- **WHEN** the update window of a kit with a new MCP server is open
- **THEN** its line has `--warn-ground`, an icon and no border

#### Scenario: A kit that a running session uses
- **WHEN** the removal window of a kit that a running session uses is open
- **THEN** the line naming that session has `--warn-ground`, an icon and no border, and Remove
  stays enabled

#### Scenario: A failed login
- **WHEN** a CLI's login fails with an answer
- **THEN** "<CLI> did not sign you in" has `--danger-ground` and an icon, and the quote's left
  border is 0
