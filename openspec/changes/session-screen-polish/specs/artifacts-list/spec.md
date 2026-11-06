## Purpose
How the session's Artifacts tab lists its artifacts when they are many or the column is narrow: a
two-line list, groups by scope that fold, and what the tab says when it is empty.

## ADDED Requirements

### Requirement: A narrow column lists artifacts in two lines

When the Artifacts tab is narrower than 720 px, each artifact SHALL be a row about 48 px high with
its type's icon, the name in mono 13 600 and the title on one line, and under them the type in a word,
the author, the time and the size in 12 px `--muted`. A long line SHALL be cut with "…".

#### Scenario: Terminals open
- **WHEN** the human opens Artifacts in a column of 436 px with `task/lad-1/design`, a Markdown
  record titled "The change"
- **THEN** its row is about 48 px high, its first line says `task/lad-1/design · The change`, and its
  second says `Document · analyst · 4 min ago · 18.2 KB`

#### Scenario: A wide column
- **WHEN** the same tab is 900 px wide
- **THEN** it shows the table with its six columns, the media type among them

### Requirement: A row of the narrow list keeps its change in a tooltip

A row of the narrow list SHALL show the latest record's summary only as the UI's tooltip on the
row's link, and SHALL open the panel on a click anywhere on it or Enter on the link, the focus going
back to the link when the panel closes. A modified click SHALL open the artifact's page in a new tab.

#### Scenario: Hover
- **WHEN** the human holds the pointer over a row whose latest summary is "Second round"
- **THEN** the tooltip says "Second round"

#### Scenario: No summary
- **WHEN** the latest record has no summary
- **THEN** no tooltip shows

#### Scenario: Back from the panel
- **WHEN** the human presses Enter on a row's link and closes the panel with Esc
- **THEN** the focus is on that link

### Requirement: A hundred artifacts go in groups by scope

A session with 100 artifacts or more, counted over all its artifacts, SHALL show them in groups by
scope, in the list and in the table, while the scope filter is All scopes. A group's heading SHALL
name "Session" or the run and count its rows shown. The group with the newest record SHALL come first,
and each group SHALL keep the newest first. In a group a row SHALL show the name without its run part.

#### Scenario: 115 artifacts
- **WHEN** the human opens Artifacts of a session with 115 artifacts in the session and three runs
- **THEN** four groups show, the one with the newest record first

#### Scenario: 99 artifacts
- **WHEN** the session has 99 artifacts
- **THEN** no group shows

#### Scenario: A type filter
- **WHEN** a session of 115 artifacts is filtered to Images and 3 match
- **THEN** the groups that hold them show with their counts of matches, and the others do not

#### Scenario: One scope
- **WHEN** the human picks one run in the scope filter
- **THEN** the list is flat, each row with its name without its run part

### Requirement: A long run's name leaves the row and the tools their shape

In the narrow list a run part of a name SHALL take at most about a third of the row, cut at its
start, so the artifact's name stays in sight. The scope filter SHALL stay inside the column however
long a run's name is.

#### Scenario: A long run
- **WHEN** the column is 366 px wide and a run's name has 80 characters
- **THEN** the filter's right edge is inside the column, on the search's line, and a row reads
  `…-all-screens/report-12 · The report`

### Requirement: The groups fold as the human left them

The Session group and an open run's group SHALL start open, and an ended run's group folded, on
entering the tab or when the group first appears, never later, and never for a group with the focus.
A group's heading SHALL be a button with `aria-expanded` and `aria-controls`. The human's fold SHALL
be kept in the browser per session and scope. While the search has text, each group with a match
SHALL show open and its heading SHALL not fold.

#### Scenario: A run ends under the human
- **WHEN** the focus is on a row of an open run's group and that run ends
- **THEN** the group stays open with the focus on the row, and folds the next time the tab is entered

#### Scenario: First visit
- **WHEN** the human first opens Artifacts of a session with an open run and two ended ones
- **THEN** Session and the open run's group are open and the two ended ones folded

#### Scenario: A reload
- **WHEN** the human opens an ended run's group and reloads the page
- **THEN** that group is open

#### Scenario: Search
- **WHEN** the human searches for a name that only a folded group holds
- **THEN** that group shows open with the match

#### Scenario: Keyboard
- **WHEN** the focus is on a folded group's heading and the human presses Enter
- **THEN** the group opens and `aria-expanded` is true

### Requirement: An empty Artifacts tab says where artifacts come from

A session without artifacts SHALL show the heading "No artifacts yet" and under it "Agents save
plans, reviews, images and mockups here (write_artifact)."

#### Scenario: A new session
- **WHEN** the human opens Artifacts of a session with no artifact
- **THEN** both lines show, and no search or filter
