## Purpose

When a tooltip of the UI shows on a focus: a focus the keyboard moves to its trigger shows it,
and a focus the browser gives back with the tab or window does not.

## ADDED Requirements

### Requirement: A focus that returns with the window shows no tooltip

A tooltip SHALL NOT show when the focus comes back to its trigger because the browser tab or
window that lost the focus got it again, whatever the last input was and whether or not the
tooltip was shown before the leaving. A tooltip shown at the leaving SHALL go with the focus.

#### Scenario: A clicked row
- **WHEN** the human clicks a session in the list, moves the pointer away, goes to another
  browser tab and comes back
- **THEN** no tooltip shows

#### Scenario: A clicked row and a key
- **WHEN** the human clicks a session in the list, moves the pointer away, presses Shift, goes
  to another browser tab and comes back
- **THEN** no tooltip shows

#### Scenario: A row reached by the keyboard
- **WHEN** a session's row has the keyboard's focus and its tooltip, and the human goes to
  another browser tab and comes back
- **THEN** the focus is on the row and no tooltip shows

### Requirement: A focus that moves within the page still shows a tooltip

After the window's return a tooltip SHALL show as it does otherwise: at once when the keyboard
moves the focus to its trigger, and after its delay when the pointer enters the trigger.

#### Scenario: Tab away and back
- **WHEN** the focus came back to a row with the window, and the human presses Tab and then
  Shift+Tab
- **THEN** the row's tooltip shows

#### Scenario: The pointer after the return
- **WHEN** the focus came back to a row with the window, and the pointer enters the row
- **THEN** the row's tooltip shows after its delay
