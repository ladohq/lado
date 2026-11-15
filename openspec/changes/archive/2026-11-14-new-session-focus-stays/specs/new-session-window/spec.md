## MODIFIED Requirements

### Requirement: The window opens on the last place

The New session window SHALL open with Where on the first recent place and the focus in
Task; with no recent places, on New empty folder with the focus in Folder name; opened from a
project's page, on that project (and repository). It SHALL show no message above Where. When the
recent places come after the human moved the focus within the window, the window SHALL set Where
and leave the focus where the human put it.

#### Scenario: Back where the human worked
- **WHEN** the latest started session ran in `~/workspace/webapp`, and the human opens New
  session
- **THEN** Where shows `webapp`, the folder is checked, the focus is in Task, and the start
  button names the place

#### Scenario: The first session ever
- **WHEN** LADO has no sessions and the human opens New session
- **THEN** Where shows New empty folder and no message stands above it

#### Scenario: The recent places come late
- **WHEN** the human opens New session and moves the focus to Cancel before the recent places
  come
- **THEN** Where shows the last place once they come, the focus stays on Cancel, and Enter
  closes the window
