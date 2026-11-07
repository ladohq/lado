## ADDED Requirements

### Requirement: The kit windows' warnings and a failed login are notices

The warnings "Not from the official marketplace." and "New MCP server…" of the kit windows SHALL be
warning notices. The heading of a failed login SHALL be an error notice, and the quote of what the
CLI said SHALL have no left stripe. Orange SHALL not be the ground of any of them.

#### Scenario: A kit from outside the marketplace
- **WHEN** the install window of a kit that needs confirmation is open
- **THEN** "Not from the official marketplace." has `--warn-ground`, an icon and no border

#### Scenario: A new MCP server
- **WHEN** the update window of a kit with a new MCP server is open
- **THEN** its line has `--warn-ground`, an icon and no border

#### Scenario: A failed login
- **WHEN** a CLI's login fails with an answer
- **THEN** "<CLI> did not sign you in" has `--danger-ground` and an icon, and the quote's left
  border is 0
