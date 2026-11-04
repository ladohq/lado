## MODIFIED Requirements

### Requirement: Clone from URL shows the URL, the folder, the branch and the session's settings

With Clone from URL the New session window SHALL show a URL field, **Clone into** (the default folder, which
follows the URL until the human edits it) with the target folder's state, **Branch**
(listed by the server half a second after the URL stops changing, `fetching branches…`
meanwhile; the default branch chosen and marked `(default)`; a field that filters as the
human types when there are more than 30), and the folder's Name, Kits, Agent CLI and Permission mode.

#### Scenario: Branches come by themselves
- **WHEN** the human types a URL and stops
- **THEN** the Branch field lists the remote's branches with the default one chosen, and
  Clone and start turns on
