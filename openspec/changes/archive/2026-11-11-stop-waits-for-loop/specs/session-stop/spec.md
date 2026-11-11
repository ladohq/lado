## Purpose
When a stop of a session is over: `lado stop`, `lado stop --all` and the UI's Stop return only
after the session's loop has ended, and the loop writes nothing into a LADO home that is gone.

## ADDED Requirements

### Requirement: A stop returns after the session's loop has ended

`lado stop <session>`, `lado stop --all` and the UI's Stop SHALL return only after the loop of
each session they stop (`lado loop <session>`) has ended. When a loop has not ended within
three loop intervals, the session SHALL stay stopped and the stop SHALL fail with
`session "<session>" is stopped, but its loop did not end (LADO_HOME/loop/<session>.lock is
held); see <LADO_HOME>/loop.log` (exit 1; with `--all` among the failures it names, after the
other sessions are stopped).

#### Scenario: The home deleted right after the stop
- **WHEN** session `s` runs, `lado stop s` returns, and LADO_HOME is deleted at once
- **THEN** after several loop intervals LADO_HOME, `lado.db` and `loop.log` do not exist

#### Scenario: Stop and start in a row
- **WHEN** `lado stop s && lado start s` runs on a running session `s`
- **THEN** `loop.log` says the first loop ended before the second started, and exactly one
  loop of `s` runs, the one started by the start

#### Scenario: A loop that does not end
- **WHEN** the lock `LADO_HOME/loop/s.lock` stays held after `lado stop s` marked `s` stopped
- **THEN** `lado stop s` exits 1 with the line naming the lock and `loop.log`, and `lado ls`
  shows `s` stopped

### Requirement: The session loop writes nothing into a deleted home

The session loop SHALL end, writing nothing, when `LADO_HOME/lado.db` does not exist before a
pass; it SHALL NOT make LADO_HOME, `lado.db` or `loop.log` again.

#### Scenario: The home deleted under a running loop
- **WHEN** LADO_HOME is deleted while the loop of session `s` runs
- **THEN** the loop ends at its next pass, and LADO_HOME does not exist afterwards
