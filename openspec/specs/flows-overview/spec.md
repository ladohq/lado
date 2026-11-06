# flows-overview Specification

## Purpose
What the session's Flows tab says of its runs: the empty tab, the task on a run's card and row, and
what an opened event of a run's history adds to its line.

## Requirements

### Requirement: An empty Flows tab names the flows that can run

A session with no run SHALL show the heading "No flow runs yet" in place of the groups, and under it
"Runs appear when the supervisor starts a flow of the session's kits: <list>." The list SHALL name
each kit with flows and its flows, as `kit: flow, flow; kit: flow`. When every kit of the session
loads and none has a flow, the line SHALL be "This session's kits have no flows, so no runs will appear
here." While the kits are not read, or cannot be, the line SHALL end at "kits." with no list.

#### Scenario: Kits with flows
- **WHEN** the human opens Flows of a session of `sdlc` (flows `task`, `epic`) and `tracker`
  (none), with no run
- **THEN** the line ends "of the session's kits: sdlc: task, epic."

#### Scenario: No flows
- **WHEN** the session's kits load and have no flow
- **THEN** the line is "This session's kits have no flows, so no runs will appear here."

#### Scenario: A kit that does not load
- **WHEN** one of the session's kits does not load and the others have no flow
- **THEN** the line ends "of the session's kits." with no list

#### Scenario: Ended runs
- **WHEN** the session has ended runs and none open
- **THEN** Active says "No active runs" and History shows them, as before

### Requirement: The session's about names its kits' flows

`GET /api/sessions/{name}/about` SHALL give each kit's flow names in `flows`, as the next agent would
take the kit, and an empty list for a kit that does not load.

#### Scenario: A valid kit
- **WHEN** a session's kit has the flows `task` and `epic`
- **THEN** its entry says `flows: ["task", "epic"]`

#### Scenario: A kit not found
- **WHEN** a session's kit is not found
- **THEN** its entry has `valid: false` and `flows: []`

### Requirement: A run's card and row show its task

A run's card in Active and row in History SHALL show the first line of its task under its name, in
13 px `--muted`, on one line cut with "…". A run with a blank task SHALL show no such line.

#### Scenario: A long task
- **WHEN** a run's task starts with a line longer than the row
- **THEN** that line shows under the name, cut with "…", and the task's later lines do not show

#### Scenario: A blank task
- **WHEN** a run's task is blank
- **THEN** its row shows the name and its state line only

### Requirement: An opened event adds only what its line lacks

An opened step of a run's history SHALL show "Step took <time>" as one line under the event, then the
note's body when it has one, or "No comment." for the human's answer without one. It SHALL NOT repeat
who, the state, the outcome or the target.

#### Scenario: A step with a note
- **WHEN** the human opens "supervisor review done → check" that took 12 minutes and has a body
- **THEN** "Step took 12 min" shows on one line, then the body, and no Who, From, Outcome or To
