## MODIFIED Requirements

### Requirement: The New session window clones from a URL

The New session window SHALL offer a clone as **Clone from URL…** in Where's group Somewhere
else (capability new-session-window). Its button **Clone and start in <folder>** SHALL be on
only when the branches are listed and the folder is `new` or `empty`. A listing failure SHALL
show under Repository URL with its hint and Copy.

#### Scenario: A listing that fails
- **WHEN** the listing of the URL fails as `ssh_denied`
- **THEN** its text and the hint `ssh -T git@github.com` show under Repository URL with
  Copy, and Clone and start is off

### Requirement: Clone from URL shows the URL, the folder, the branch and the session's settings

With Clone from URL the window SHALL show **Repository URL** (`✓ Found` once listed), **Branch**
(listed by the server half a second after the URL stops changing, `fetching branches…`
meanwhile; the default branch chosen and marked `(default)`; a filtering field above 30
branches), **Clone into** (the default folder until edited, with its state: `✓ New folder`,
`✓ Empty folder` or the refusal), then Task and Team as for a folder.

#### Scenario: Branches come by themselves
- **WHEN** the human types a URL and stops
- **THEN** the Branch field lists the remote's branches with the default one chosen, and
  Clone and start turns on

### Requirement: Use this clone takes a clone that is there as it is

For `same_repo` the button SHALL be **Use this clone**, with the note `LADO will use it as it
is: no clone, no pull, no branch switch`; it turns Where to that folder and changes nothing
on disk.

#### Scenario: A clone that is there
- **WHEN** Clone into is a clone of the same repository and the human presses Use this
  clone
- **THEN** Where shows that folder, and nothing on disk changed

### Requirement: After the clone the window starts the session

After the clone the window SHALL start the session as it does for a folder; a refused start
SHALL turn Where to the cloned folder and show the refusal there.

#### Scenario: A name taken after the clone
- **WHEN** the clone ends and the start is refused because the name is taken
- **THEN** Where shows the cloned folder with the refusal, and the clone stays
