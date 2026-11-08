# rail-help Specification

## Purpose
The rail's Help item and its menu (Documentation, GitHub, Report a bug), and the rail's Settings
cogwheel.

## Requirements

### Requirement: The rail has one Help item with a menu

The rail SHALL have, above Settings, on every page, an item **Help** with a question-mark icon
that opens a menu: `Documentation ↗` (`https://github.com/ladohq/lado#readme`) and `GitHub ↗`
(`https://github.com/ladohq/lado`), each in a new tab, then `Report a bug`, which opens
`/report`. The menu SHALL open beside the rail, its first item focused; the arrow keys SHALL move
the focus, and Esc or a press outside SHALL close it, Esc giving the focus back to Help.

#### Scenario: Report a bug from Help
- **WHEN** the human clicks Help, then Report a bug
- **THEN** the Report a bug page opens and the menu is closed

#### Scenario: The folded rail
- **WHEN** the rail is folded to icons
- **THEN** Help shows only its icon, with `Help` as its tooltip and accessible name, and its menu
  opens beside the rail

#### Scenario: Esc
- **WHEN** the menu is open and the human presses Esc
- **THEN** the menu closes and the focus is on Help

### Requirement: Help is marked on the Report a bug page

While `/report` is open, Help SHALL be marked as the rail's current item.

#### Scenario: On the Report a bug page
- **WHEN** the human opens `/report`
- **THEN** Help has the rail's current mark, and no other item has it

### Requirement: On a phone Help opens its menu in the drawer

In the phone layout Help SHALL open the same menu over itself within the drawer, as wide as the
drawer, its items 44 px high; choosing an item SHALL close the menu and the drawer.

#### Scenario: Documentation on a phone
- **WHEN** the human opens Menu, taps Help, then Documentation
- **THEN** the README opens in a new tab and the drawer is closed

### Requirement: Settings has a cogwheel

The rail's Settings and the list's General SHALL show a cogwheel with teeth, not a circle with
rays.

#### Scenario: The rail
- **WHEN** the human looks at the rail
- **THEN** Settings shows the cogwheel, and no icon of the rail is the circle with rays
