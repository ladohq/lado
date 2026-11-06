## MODIFIED Requirements

### Requirement: On a phone the change feed's mark is a dot or a word

In the phone layout the change feed's mark SHALL be a dot while the
feed is live and the no-network icon on the warning ground, named "reconnecting…", while it is
lost (capability connection-loss), and SHALL open the system panel
as before while live; a newer LADO's `↑ X.Y.Z` SHALL stay beside it.

#### Scenario: The feed is lost
- **WHEN** the change feed reconnects
- **THEN** the mark is the no-network icon in place of the dot, named "reconnecting…"
