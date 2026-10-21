## REMOVED Requirements

### Requirement: The default folder of a clone

**Reason**: Renamed: the folder is called the workspace (docs/design/projects.md).
**Migration**: Replaced by "The default folder of a clone, in the workspace when there is one", the same rule in the new words.

## ADDED Requirements

### Requirement: The default folder of a clone, in the workspace when there is one

A clone's folder SHALL be, unless the human gives one, `<parent>/<repo>`: `<parent>` is
the workspace (`LADO_REPOS`) when one is set, else `~/lado`; `<repo>` is the
URL's last path segment without a trailing `/` or `.git`. A given folder SHALL be a full
path (`~` allowed); a relative one SHALL be refused as the window refuses it today. The
folders above it SHALL be made when missing.

#### Scenario: Default folder
- **WHEN** the URL is `https://github.com/ladohq/marketplace.git/` and no folder is given
- **THEN** the folder is `~/lado/marketplace`

#### Scenario: Default folder in the workspace
- **WHEN** `LADO_REPOS=/Users/me/repos` and the human clones `git@github.com:acme/app.git`
  with no folder, by `lado start` or the New session window
- **THEN** the folder is `/Users/me/repos/app`, and the window's Clone into shows it
