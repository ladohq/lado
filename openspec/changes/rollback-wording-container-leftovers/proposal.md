Task: LAD-288

## Why

Three findings of 0.47.0rc1's manual check (LAD-286) and of CI on the commit "Release
0.47.0", all in the release's and the tests' own tooling; no user of LADO sees them.

**B. The rollback item names a line that never shows.** docs/release.md 4.4 tells the
human to read `lado update <final>`'s warning, and 0.47.0's checklist expects the sessions
started on the RC after `Sessions not in that copy are not started again:`. The line never
appears: `rc_check.py rollback` runs `lado stop --all` before `lado update <final>`, so the
update finds no running session, and its list of the sessions the copy lacks
(`self_update.Restore.missing`, the running sessions not in the copy) is empty. The
rollback names the same sessions itself, in its plan before `Roll back? [y/N]`:
`- not started again, not in the copy: <names>`. The script is built so on purpose
(LAD-51): it stops and starts the sessions itself, so it starts only those the copy has.

Options weighed:

- A (taken, the human's choice, #7684): the documents say where the line is. 4.4 says the
  plan of `rollback` names the sessions not started again and `lado update`'s warning
  names what the database loses; the spec of the plan names that line. Long-term cost:
  none; the script does not change.
- B: `rollback` leaves the stops to `lado update`, whose warning then names the sessions.
  Closer to the user's way back, but the mechanism of the rollback changes right before
  0.48.0rc1, with new tests; the user's way back is already checked on its own (4.4).

**E. Interrupted container tests leave containers, volumes and networks in Docker.** After
interrupted runs on 2026-11-13, 22 running `lado-test-*` containers, 23 volumes and 7
networks were left. Each test removes what it made in a finalizer, and pytest runs the
finalizers on a first Ctrl-C too. But a SIGTERM (a tool's timeout, `kill`), a SIGHUP (a
closed terminal), a SIGKILL or a second Ctrl-C during the teardown end pytest at once, and
nothing reaps it later: the run's prefix is random so that a run beside it (another
worktree) is never taken for one left behind. The session's end checks only containers and
volumes, not compose's networks (`<project>_default`) nor the image tags `folder` makes.

Options weighed:

- A (taken, the human's choice, #7684): SIGTERM and SIGHUP end the run as Ctrl-C does,
  through the finalizers; each run holds a lock of its own prefix while it lives, and the
  next run's start removes what a run whose lock is free left (containers, volumes,
  networks, tags of its prefix); the end's check covers networks and tags too. Leftovers
  no lock ties to a dead run (of runs before this change, or of another machine on the
  same Docker) are named with the one command that removes them, never removed. Long-term
  cost: one small module of the container tests, the same idea as `tests/leftovers.py`'s
  reaping of processes.
- B: remove every `lado-test-*` object at a run's start. Simple, but it breaks a run of
  another worktree that goes on meanwhile, which the prefix exists to protect.
- C: label every object with the run's pid and reap by pid. Docker gives no label to a
  volume that `docker run -v name:…` makes, and a pid says nothing across the Mac and a
  LADO container sharing one Docker Desktop.

**A flaky integration test.** CI 43732304223 failed once on
`tests/integration/test_flow_runs.py::test_the_humans_answer_moves_the_run_on_to_the_next_agent`
(line 305): it takes the last message to the worker as the step, but the last one was the
reminder of 0.47.0's unread check (`you have not read message #10 from lado: …`), which
the fake agent earns because it reads no bodies. A race in the test, not a defect of LADO.

## What Changes

- docs/release.md 4.4: the sessions not started again are named by `rollback`'s plan
  (`- not started again, not in the copy: …`), before its question; `lado update
  <final>`'s warning names what the database loses. 4.7 says a release's own item about
  going back quotes the plan's line for them, not the update's.
- A requirement of release-candidates names that line of `rollback`'s plan.
- The container tests: SIGTERM and SIGHUP run the teardown as Ctrl-C does; a run's lock of
  its prefix; the start's reaping of dead runs' containers, volumes, networks and tags; a
  warning naming leftovers of no known run with their removing command; the end's check
  of networks and tags; a container test that stops a run from outside and checks that
  nothing is left (test-processes).
- The integration and UI tests that take "the last message" to an agent pick the message
  they mean by its sender and summary.
- docs/testing.md: the container tests' cleanup on interruption and the reaping.

## Scope

- The wording of 4.4 and 4.7 in docs/release.md, and the spec of the rollback's plan.
- The container tests' cleanup: signals, lock, reaping, the warning, the end's check, its
  container test, docs/testing.md.
- The flaky test and the six other places that take the last message to an agent:
  `tests/integration/test_flow_runs.py` (lines 137, 304, 322, 354),
  `tests/integration/test_session_start.py:66`, `tests/integration/test_local_model_limits.py:38`,
  `tests/integration/test_unread_reminder.py:52`, `tests/ui/test_gates.py:660`; each is
  changed where a later message to the agent can come first, and left with a reason where
  it cannot.

## Out of scope

- Changing `rc_check.py rollback` (option B of finding B): the human's choice of the
  wording; the script does what its spec says.
- docs/releases/0.47.0.md: a released version's record; it keeps what was checked then.
- docs/releases/0.48.0.md: its going-back items do not quote the update's line; the
  release task writes the rest of the RC's section by 4.7 as changed here.
- Removing leftovers no lock ties to a dead run: they may be a live run of another machine
  or checkout; the warning names them and the command.
- Reaping by age: a long run of another worktree would be removed.
- A CHANGELOG line: no user of LADO sees the change.

## Impact

- `docs/release.md`, `docs/testing.md`.
- `tests/container/conftest.py`, `tests/container/container_helpers.py`, a new module
  of the container tests for the run's lock and the reaping, a new container test.
- `tests/integration/test_flow_runs.py` and the other tests named in Scope.
- Specs: release-candidates (added), test-processes (added).
- Patch-level: tests and docs only, no code of LADO, no schema, no CLI or MCP change.
