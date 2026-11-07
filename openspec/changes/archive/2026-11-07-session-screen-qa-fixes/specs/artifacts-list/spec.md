## MODIFIED Requirements

### Requirement: The groups stay where they stood while the tab is open

On entering the tab or reloading, the Session group SHALL come first, then open runs' groups, then
ended runs' groups, the runs of each part with the newest record first. While the tab stays open the groups SHALL keep
their places: a new record goes in its group and changes its count, and a group that first appears
SHALL go to the end of its part.

#### Scenario: An ended run with the newest record
- **WHEN** the human opens Artifacts and an ended run holds the newest record
- **THEN** its group stands below the Session group and the open runs' groups

#### Scenario: Another run writes
- **WHEN** the human reads a group and an agent writes to a group lower down
- **THEN** no group moves, and that group's count grows by one

#### Scenario: A new run's first artifact
- **WHEN** a run with no group yet writes its first artifact while the tab is open
- **THEN** its group appears at the end of its part, and the groups above it stay

#### Scenario: Back on the tab
- **WHEN** the human leaves the tab and comes back
- **THEN** the groups stand by the rule of entering the tab

#### Scenario: 99 artifacts
- **WHEN** the session has 99 artifacts
- **THEN** no group shows

#### Scenario: A type filter
- **WHEN** a session of 115 artifacts is filtered to Images and 3 match
- **THEN** the groups that hold them show with their counts of matches, and the others do not

#### Scenario: One scope
- **WHEN** the human picks one run in the scope filter
- **THEN** the list is flat, each row with its name without its run part

#### Scenario: A run with the newest record
- **WHEN** the human opens Artifacts of a session of 131 artifacts and an open run holds the newest
  record
- **THEN** the Session group stands first and that run's group second
