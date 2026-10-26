## ADDED Requirements

### Requirement: An upgraded lado.db takes every write a new one takes

Every write of LADO to `lado.db` SHALL succeed on a database migrated from any earlier
schema as on one made by this LADO. Where a migration cannot give an old database what a
new one has (SQLite cannot add a DEFAULT to an existing column: `messages.body` of a
database made before LADO 0.7.0, schema below 5, has none), each insert SHALL give that
column its value itself.

#### Scenario: A resume on a database from before 0.7.0
- **WHEN** `lado.db` was made at schema 1 and migrated to the current schema, an agent's
  turn ended on a temporary API error, and its planned resume is due
- **THEN** the session loop queues LADO's resume message to the agent (its body empty),
  the plan is dropped, and the loop's pass goes on with no error

#### Scenario: Every message insert names its body
- **WHEN** LADO's code inserts a row into `messages`
- **THEN** the insert names the column `body`
