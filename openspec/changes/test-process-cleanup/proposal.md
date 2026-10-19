Task: LAD-55

## Why

Test runs leave live processes on the machine: fake agents (`fake_agent.py`), test tmux
servers (`tmux -L lado-test-…`), `lado server` processes and session loops, for hours or
days. They load a machine whose load already makes tests time out, and nobody notices
them: nothing in the suite checks that a test's processes are gone. Seen on 2026-10-14: a
UI test's server `lado-test-39db745c` with two fake agents (worktree lad-22), and two
orphaned fake agents with parent 1 from `test_stopping_a_session_tells_no_one_and_counts_what_it_dropped`
(worktree lad-44); BACKLOG.md "Test runs leave `lado server` processes behind" lists more
since 2026-10-06. The same root takes in LAD-96's flake: the teardown of
`test_an_agent_whose_cli_asks_first_waits_until_the_human_answers` failed in CI (run
39011239606, `integration (3.13, 2)`) with "session loops still running 1.25s after the
test: ['live']", and passed on a rerun.

Root causes (main, 3ae9876):

1. **Teardown trusts processes to end by themselves.** The `isolated` fixtures
   (`tests/integration/conftest.py`, `tests/ui/conftest.py`, `tests/real_clis.py`) run
   `tmux kill-server` and stop there: an agent that handles SIGHUP late or hangs in its
   session-end hook, or a process the test started outside tmux, is never checked or
   killed. The UI `server` fixture kills nothing when `wait_ready` times out (no
   `server.json`, so `server_run.stop()` finds no server) or `process.wait(timeout=10)`
   expires.
2. **A run stopped from outside has no teardown.** A command timeout, a second Ctrl-C, a
   cancelled CI job or a crashed xdist worker ends pytest without fixtures' teardown. The
   tmux server is a daemon and the session loop runs in a session of its own
   (`start_new_session`), so both outlive pytest with the agents under them, forever.
   The lad-22 leftover fits this. The lad-44 orphans date from 00:49, 15 minutes before
   commit c4b9e7c (LAD-44), which fixed how the fake agent ends on a killed terminal;
   most likely that bug, now fixed, but nothing would catch its return.
3. **The loop check's budget is too small for a loaded machine.** `no_loop_left` gives a
   session loop five intervals (1.25 s) to end after the tmux server is killed. The loop
   learns it at its next pass, after sleeping an interval; under CI load (scheduling, a
   SQLite wait, a tmux call) a pass can take longer. 46 integration tests (liveness,
   agents, session loop) under `-n auto` on a quiet machine left nothing behind and
   passed: the flake is load, not a loop that does not end.

## What Changes

- **A shared sweep of a test's processes** (`tests/leftovers.py`): every process a test
  starts carries the test's `LADO_HOME` in its environment (the tmux server, the agents
  and their hooks and `lado mcp`, the session loop, `lado server`, a real CLI and its
  children). After the tmux server is killed, the three `isolated` fixtures wait up to
  10 s for every process with that `LADO_HOME` to end, then kill the rest and fail the
  test, naming each (pid and command).
- **A run's mark** (`tests/conftest.py`): each pytest process sets `LADO_TEST_PID` to its
  own pid, which every process it starts inherits. At the start of a run, the run kills
  every process whose `LADO_TEST_PID` names a pid that is no longer alive, from any
  worktree of the machine, and removes stale `lado-test-*` tmux sockets; at its end, each
  pytest process kills the processes of its own mark still alive and fails the run,
  naming them.
- **The loop check** keeps its rule (a loop ends by itself once its tmux session is gone)
  with a budget of 10 s instead of five intervals; no retry inside pytest.
- **The UI `server` fixture** kills its process whatever `server_run.stop()` did.
- `docs/testing.md`: how a test's processes are swept and a run's leftovers reaped.
- BACKLOG.md: the entry "Test runs leave `lado server` processes behind" is removed, as
  this change does what it wants.

## Scope

The test suite's fixtures and a new test helper, tests of that helper, `docs/testing.md`,
AGENTS.md's line of shared test helpers, BACKLOG.md. No change to LADO itself (`src/`),
the CLI, the UI, the API or the schema. A patch release at most (tests and docs only);
no CHANGELOG.md line, as users see nothing.

## Out of scope

- A product change that records the processes of a session (the loop writing its pid,
  sessions registering their agents' pids): more product surface only for tests
  (AGENTS.md, "Only what is used"); the environment mark finds the same processes.
- A watchdog in the fake agent that exits when orphaned: it would hide a leak instead of
  failing the test that made it.
- Retries of a test inside pytest (pytest-rerunfailures and the like): ruled out by the
  task and by kit sdlc's flake policy.
- Container tests (`tests/container/`): their processes are Docker containers, which
  `container_helpers` already removes and checks by their own prefix.
- Leftovers of a run on another machine or in another PID namespace (a container's tests
  seen from the host): a process is only visible to the run that can list it.

## Impact

- `tests/leftovers.py` (new), `tests/conftest.py`, `tests/integration/conftest.py`,
  `tests/ui/conftest.py`, `tests/real_clis.py`.
- Tests: `tests/test_leftovers.py` (unit: parsing a process's environment),
  `tests/integration/test_leftovers.py` (real processes).
- `docs/testing.md`, `AGENTS.md` (the shared helpers' line), `BACKLOG.md`.
- New capability spec `test-processes`.
