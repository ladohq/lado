## MODIFIED Requirements

### Requirement: The Projects section takes the phone's screen in turns

On a phone the project list SHALL fill the screen and a project SHALL open in its place,
with a link `← All projects` above it. The list and the project's page SHALL each scroll by
themselves under the top bar to their end, the window not scrolling.

#### Scenario: On a phone
- **WHEN** the human opens `/projects/shop` on a phone
- **THEN** only the project shows, with `← All projects` above it, which opens the list

#### Scenario: A project's page longer than the phone's screen
- **WHEN** the human opens on a phone a project whose page is longer than the screen and
  scrolls it
- **THEN** the page scrolls under the top bar until its Delete project block is in sight,
  and the window itself does not scroll

#### Scenario: A project list longer than the phone's screen
- **WHEN** the human opens Projects on a phone with more projects than the screen holds and
  scrolls the list
- **THEN** the list scrolls under the top bar until its last project is in sight
