## Context

Root causes and the options weighed are in the proposal. This file holds the technical
choices the build follows. Everything lives under `tests/`; LADO itself does not change.

## Decisions

### D1. A test's processes are found by its `LADO_HOME` in their environment

Every process a test starts inherits or is given the test's `LADO_HOME`: the tmux server
is forked from the first `tmux` client, which runs with the test's environment
(`tmux.clean_env()` keeps `LADO_HOME`); agents get it from `providers/base.py` whatever
their environment source; the session loop, hooks, `lado mcp`, `lado server` and a real
CLI's children inherit it. Each test's `LADO_HOME` is a path of its own (`tmp_path`), so
the mark is exact. Parent-child trees (as `real_clis.agent_processes`) miss orphans and
the loop (`start_new_session`); process groups miss the daemonised tmux server. The
environment is the one mark all of them keep.

### D2. Reading another process's environment: `/proc` on Linux, `ps -E` on macOS

`tests/leftovers.py` lists the user's processes with their environment: on Linux by
reading `/proc/<pid>/environ` (NUL-separated; a process that ends or is not readable
meanwhile is skipped) and `/proc/<pid>/cmdline`; on macOS by `ps -E -ww -A -o
pid=,command=`, whose line is the command followed by the environment, matched as
`<NAME>=<value>` followed by a space or the line's end. Standard library only (no
psutil): two small readers, each unit-tested on a canned sample; the integration test
runs whichever the machine has. Another platform (none runs the suite) raises with a
clear message rather than finding nothing.

### D3. One sweep for all three `isolated` fixtures

`leftovers.sweep(home, wait=10)` waits for the processes marked with `home` (the caller
left out) to end, polling every 0.1 s, then SIGKILLs the rest and returns them as
`(pid, command)`; `leftovers.fail_if(left, after)` fails the test naming them. The
integration, UI and real-CLI `isolated` fixtures call it after `kill_tmux_server`
(integration: after `no_loop_left`, so a late loop is named as a loop). One helper, not
three copies (AGENTS.md, "Share, don't copy"). 10 s is the shared budget
(`leftovers.WAIT`); a green teardown ends as soon as nothing is left.

### D4. The run's mark is `LADO_TEST_PID`, the pytest process's own pid

`tests/conftest.py` sets `os.environ["LADO_TEST_PID"] = str(os.getpid())` at import, so
each xdist worker marks with its own pid (it imports the conftest itself) and a crashed
worker's processes are reaped like a killed run's. Not cleared for agents: they get the
test run's environment (`LADO_AGENT_ENV=inherit`); a live test whose agent takes another
environment still has the mark on its tmux server, whose kill ends the agents.

### D5. Reaping a dead run's leftovers at the start of a run

In `pytest_sessionstart` of the controller (or the only process without xdist):
`leftovers.reap_dead_runs()` SIGKILLs every process of the user whose `LADO_TEST_PID` is
not a living pid, then removes the `lado-test-*` sockets in the user's tmux folder
(`TMUX_TMPDIR` or `/tmp`, `tmux-<uid>`) on which `tmux -L <socket> list-sessions` gets no
server. A pid reused by an unrelated process makes the owner look alive: the leftover
then waits for a later run, which is the safe side. Nothing of a living run is touched,
so parallel runs of several worktrees stay apart.

### D6. The end-of-run check in every pytest process

`pytest_sessionfinish` in each pytest process: `leftovers.own_left()` kills what still
carries its own `LADO_TEST_PID` (itself left out, after a short wait as in D3), prints
each, and sets `session.exitstatus` to a failure when any was found. It covers every
layer, the unit tests included, and is what makes "after `make check` no `fake_agent.py`
and no `lado-test-*` server" a checked fact on every CI run.

### D7. The loop check keeps its rule, budget 10 s

`no_loop_left` waits up to `leftovers.WAIT` (10 s) instead of `5 * loop.INTERVAL`
(1.25 s). The rule it checks (a loop ends by itself once its tmux session is gone) is a
property of LADO worth keeping; 1.25 s is shorter than one pass may take under CI load. A
loop that never ends still fails the test; nothing is retried.

### D8. The UI `server` fixture kills its process itself

In its `finally`: `server_run.stop()` (its normal stop), then `process.wait(timeout=10)`;
on a timeout, `process.kill()` and `process.wait()`. The sweep (D3) would catch it too,
but as a test failure; the fixture owns the process it started and stops it whatever
`wait_ready` did.

## Risks

- **A new teardown failure where a process is slow to end.** The 10 s budget is about
  forty loop intervals and longer than any hangup hook takes in the integration runs; a
  failure names the process, so a real leak is told apart from load.
- **The macOS reader** depends on `ps -E` printing the environment of the user's own
  processes, which macOS does; the smoke tests on macOS run it in CI.
