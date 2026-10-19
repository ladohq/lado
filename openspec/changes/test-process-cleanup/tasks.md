## 1. The helper

- [x] 1.1 `tests/leftovers.py`: list the user's processes with command and environment
  (D2: `/proc` on Linux, `ps -E -ww -A -o pid=,command=` on macOS, another platform
  raises); `marked(name, value)` the pids whose environment has `name=value`; `WAIT = 10`;
  `sweep(home, wait=WAIT)` (D3); `fail_if(left, after)`; `reap_dead_runs()` (D5);
  `own_left()` (D6). Module docstring says what each is for. Check: tasks 1.2 and 1.3.
  Built: macOS lists the user's own processes (`ps -E -ww -U <uid>`) and names each by a
  second `ps` without `-E`, so a name is the command, not the command and the environment.
- [x] 1.2 `tests/test_leftovers.py` (unit): the Linux reader on a fake `/proc` folder
  (environ with NULs, a pid that vanished, an unreadable one skipped); the macOS reader on
  a canned `ps -E` text (a value followed by a space, at the line's end, a longer value
  that only starts the same not matched). Check: `uv run pytest -n0 tests/test_leftovers.py`.
- [x] 1.3 `tests/integration/test_leftovers.py` (marker `integration`, real processes):
  `sweep` returns at once when nothing is marked; it kills a `sh -c 'trap "" HUP; sleep 60'`
  started with a `LADO_HOME` of the test's and names it, and leaves one with another
  `LADO_HOME` alone; `reap_dead_runs` kills a `sleep 60` whose `LADO_TEST_PID` is the pid
  of a process that has exited and leaves one whose mark is the test's own pid; it removes
  a `lado-test-*` socket of a tmux server killed with SIGKILL and keeps a living server's;
  `own_left` kills and names a marked `sleep 60` (each process the test starts is cleaned
  up in a `finally`). Check: `uv run pytest -m integration -n auto
  tests/integration/test_leftovers.py`. Built as `tests/integration/test_leftover_processes.py`:
  two test modules named `test_leftovers.py` break collection (no `__init__.py` in tests/).

## 2. The fixtures

- [x] 2.1 `tests/conftest.py`: `LADO_TEST_PID` set at import (D4); `pytest_sessionstart`
  of the controller or a lone process calls `reap_dead_runs` (D5); `pytest_sessionfinish`
  of each process calls `own_left` and fails the run on a leftover (D6). Check: `make test`
  green; by hand, a scratch unit test that starts `sleep 60` and leaves it makes the run
  fail naming it, and the process is gone after (not committed). Built: an xdist worker
  hands what it left to the controller (`workeroutput`, read in `pytest_testnodedown`);
  the controller checks its own mark after xdist stopped the workers, which carry it.
- [x] 2.2 `tests/integration/conftest.py`: `no_loop_left` waits `leftovers.WAIT` (D7);
  `isolated` calls `sweep` after it and fails on what is left (D3). Check: `uv run pytest
  -m integration -n auto tests/integration/test_agent_liveness.py
  tests/integration/test_session_loop.py tests/integration/test_agents.py`.
- [x] 2.3 `tests/ui/conftest.py`: `isolated` sweeps (D3); `server` kills its process when
  the wait times out (D8). Check: `uv run pytest -m ui -n auto tests/ui/test_layout.py`.
  Not run locally: Chromium does not start in LADO's container (no `libglib-2.0.so.0`);
  CI's UI shards run it.
- [x] 2.4 `tests/real_clis.py`: `isolated` sweeps (D3). Check: `uv run pytest -m smoke
  --collect-only -q` collects; the smoke runs in CI.

## 3. Regression and load

- [x] 3.1 The full integration and UI layers once each (`uv run pytest -m integration -n
  auto`, `uv run pytest -m ui -n auto`), one after another, under the check lock
  (`scripts/check_lock.py`, as `make test-integration` takes it): green, and every leak
  the sweep reports fixed at the fixture or test that made it (a new commit each, named
  in the build report). After them `pgrep -af 'fake_agent.py|lado-test-'` lists no process of this worktree
  (another worktree's run going at the same time is not this run's). The UI layer runs in
  CI only, as in 2.3; the integration layer reported no leak.
- [x] 3.2 LAD-96's test under load: `test_an_agent_whose_cli_asks_first_waits_until_the_human_answers`
  five runs in a row of `tests/integration/test_agent_liveness.py` with `-n auto` while
  one busy loop per CPU runs (`python -c 'while True: pass'`, killed after); all green,
  the times of the slowest teardown in the build report.
- [x] 3.3 A killed run: start `uv run pytest -m integration -n0
  tests/integration/test_agent_liveness.py`, SIGKILL pytest mid-run, see its tmux server
  and fake agents alive (`pgrep`), then run `uv run pytest -n0 tests/test_isolation.py`:
  they are gone after it. Result in the build report.

## 4. Docs

- [x] 4.1 `docs/testing.md`, beside the isolation paragraph: the sweep after each test,
  the run's mark `LADO_TEST_PID`, the reaping at a run's start and the check at its end,
  and the 10 s budget of the loop check. Check: read through. `docs/design/modules.md`
  names `tests/leftovers.py` beside the other shared helpers.
- [x] 4.2 `AGENTS.md` (Layout, tests): `leftovers.py` added to the shared helpers' line;
  the file stays within 200 lines (`tests/test_agents_md.py`). BACKLOG.md: the entry
  "Test runs leave `lado server` processes behind" removed. Check: `uv run pytest -n0
  tests/test_agents_md.py`.

## 5. Checks

- [x] 5.1 `make lint`, `make test`, `openspec validate test-process-cleanup --strict`,
  `openspec validate --specs --strict`. CI runs the integration, UI and smoke layers.
  Locally `make test` has two red tests outside this change, red on main too in LADO's
  container (Python 3.15: a folder no one may read): `test_clone.py::
  test_a_folder_that_cannot_be_read_is_refused_not_raised`, `test_server_clones.py::
  test_a_folder_that_cannot_be_read_is_400_not_500`; CI runs Python 3.10 and 3.13.
