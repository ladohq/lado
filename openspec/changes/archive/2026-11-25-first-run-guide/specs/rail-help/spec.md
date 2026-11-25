## MODIFIED Requirements

### Requirement: The rail has one Help item with a menu

The rail SHALL have, above Settings, on every page, an item **Help** with a question-mark icon
that opens a menu: `Documentation ↗` (`https://github.com/ladohq/lado#readme`) and `GitHub ↗`
(`https://github.com/ladohq/lado`) in a new tab, then `Getting started` (the first-run
guide) and `Report a bug` (`/report`). The menu SHALL open beside the rail, its first item
focused; arrow keys SHALL move the focus; Esc or a press outside SHALL close it, Esc giving
the focus back to Help.

#### Scenario: Report a bug from Help
- **WHEN** the human clicks Help, then Report a bug
- **THEN** the Report a bug page opens and the menu is closed

#### Scenario: Getting started from Help
- **WHEN** the human clicks Help, then Getting started
- **THEN** the menu is closed and the guide's welcome shows

#### Scenario: The folded rail
- **WHEN** the rail is folded to icons
- **THEN** Help shows only its icon, with `Help` as its tooltip and accessible name, and its menu
  opens beside the rail

#### Scenario: Esc
- **WHEN** the menu is open and the human presses Esc
- **THEN** the menu closes and the focus is on Help
