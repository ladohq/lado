## ADDED Requirements

### Requirement: A server's commit author is set and removed on its row

A row of Settings → Git servers SHALL have ✎ `Commit author`, opening a form under the row
with Name and Email (the saved author, else empty), Save author, Remove author (when one is
saved) and Cancel, which set and clear the author as `lado git-server author` does, its
refusals under Name or Email. A row with an author SHALL show `commits as <name> <<email>>`.

#### Scenario: Setting an author
- **WHEN** the human opens ✎ on `https://gitlab.corp.example`, types `Ivan Petrov` and
  `ivan.petrov@corp.example` and presses Save author
- **THEN** the form closes, `Agents commit to https://gitlab.corp.example as Ivan Petrov
  <ivan.petrov@corp.example>.` shows above the row, the row shows `commits as Ivan Petrov
  <ivan.petrov@corp.example>`, and `lado git-server list` prints the same author

#### Scenario: A wrong email
- **WHEN** the human types `ivan.petrov` in Email and
  presses Save author
- **THEN** `not an email address: name@host` shows under Email and nothing is saved

#### Scenario: Removing it
- **WHEN** the human opens ✎ on a server with an author and presses Remove author
- **THEN** the row no longer shows `commits as`, `Agents commit to <address> with your own
  git author again.` shows above it, and `lado git-server list` prints `-` for its author
