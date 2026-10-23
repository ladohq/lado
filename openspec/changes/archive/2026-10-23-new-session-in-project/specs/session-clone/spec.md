## MODIFIED Requirements

### Requirement: The New session window clones from a URL

The New session window SHALL have a switch **From scratch | Folder | Clone from URL |
Project** in its first field (capabilities session-scratch and projects). Its
button **Clone and start** SHALL be on only when the branches are listed and the folder is
`new` or `empty`. A listing failure SHALL show under the URL with its hint and Copy.

#### Scenario: A listing that fails
- **WHEN** the listing of the URL fails as `ssh_denied`
- **THEN** its text and the hint `ssh -T git@github.com` show under the URL with Copy, and
  Clone and start is off
