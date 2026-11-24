## MODIFIED Requirements

### Requirement: A fresh start needs git to know the commits' author

Before it makes anything, a fresh start SHALL check that its commits have an author: LADO's
commit author, the project's author for a project's repository (capability
commit-authors), or else git's `user.name` and `user.email` in the target's nearest
existing folder (`git config --get`), and SHALL refuse otherwise with the text `nobody signs
the agents' commits: LADO has no commit author and git has no user.name or user.email`.
LADO SHALL NOT write an author into any git config.

#### Scenario: A developer's machine
- **WHEN** git's global config has `user.name` and `user.email` and LADO has no author
- **THEN** the check passes, and the first commit is theirs

#### Scenario: LADO's author on a machine without git's
- **WHEN** git has no `user.name` and LADO's author is `Ann Lee <ann@example.com>`
- **THEN** the check passes, and the first commit carries `Ann Lee <ann@example.com>`

### Requirement: The author's refusal says how to set the author where LADO runs

The refusal of a fresh start for a missing author SHALL carry the hint `Set the commit
author in Settings → Git servers, or run:` with the command `lado git-server author --name
"Your Name" --email you@example.com`, in LADO's container (`LADO_CONTAINER`) as elsewhere.

#### Scenario: The container without the variables
- **WHEN** LADO runs in its container whose `.env` has no `LADO_GIT_NAME` and LADO has no
  commit author
- **THEN** a fresh start is refused with the text and the hint naming Settings → Git
  servers, and nothing is made
