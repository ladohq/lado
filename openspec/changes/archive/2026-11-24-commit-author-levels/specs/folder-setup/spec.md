## MODIFIED Requirements

### Requirement: Git's missing author keeps the set-up off

When nobody signs the commits where the folder is (no LADO commit author and no `user.name`
or `user.email` in git's config), the window SHALL show the note of the missing author (the
session-scratch capability's: the link to Settings and Check again), never a command or the
container's `.env` text, and keep the button off.

#### Scenario: No author
- **WHEN** nobody signs the commits and the human picks a plain folder
- **THEN** the note shows, the footer reads `To start: set the commit author`, and Check
  again checks the folder anew: until the answer the button reads `Checking…`, off with the
  focus on it
