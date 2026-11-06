## Purpose
Where the keyboard's focus goes when a modal window of the web UI closes.

## ADDED Requirements

### Requirement: A closed window gives the focus back to what opened it

When a modal window of the UI closes by Esc, Cancel or its close button, the focus SHALL go back to
the element that had it when the window opened, while that element is still in the page. The next
Tab SHALL go on from there.

#### Scenario: Take control, Esc
- **WHEN** the human opens Take control with the keyboard and presses Esc
- **THEN** the window closes and the focus is on the Take control button

#### Scenario: Take control, Cancel
- **WHEN** the human opens Take control with the keyboard and presses Cancel
- **THEN** the window closes and the focus is on the Take control button

#### Scenario: Resume, Esc
- **WHEN** the human opens Resume from the stopped session's bar and presses Esc
- **THEN** the window closes and the focus is on Resume session

#### Scenario: Resume, Cancel
- **WHEN** the human opens Resume from the head and presses Cancel
- **THEN** the window closes and the focus is on the head's Resume

#### Scenario: Another window
- **WHEN** the human opens Forget, Finish, Share or Add kit from its button and presses Esc
- **THEN** the focus is on that button

#### Scenario: The next Tab
- **WHEN** a window closed and the focus went back to its button
- **THEN** Tab moves to the element after that button, not to the page's start
