## MODIFIED Requirements

### Requirement: On a phone the rail opens as a menu

In the phone layout the rail SHALL not be shown. Menu SHALL open
the rail over the page from the left, with each section's icon and name, the Needs you
count, New session, Report a bug and Settings, and dim the rest of the page. Choosing an
item, a tap on the dimmed page, or Esc SHALL close it; on closing the focus SHALL go back to
Menu.

#### Scenario: Going to Kits
- **WHEN** the human taps Menu, then Kits
- **THEN** the Kits page opens and the menu is closed

#### Scenario: A tap beside the menu
- **WHEN** the menu is open and the human taps the dimmed page
- **THEN** the menu closes and the page under it is as it was
