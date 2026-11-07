Task: LAD-232

## Why

Symptom: `tests/test_uninstall.py::test_the_agents_processes_are_taken_before_the_stop_and_waited_for`
failed once in CI with `assert [False] == [True]` at `assert seen == [True]` (run 42307165261,
attempt 1, `unit (3.13)`; 1 failed, 4829 passed). That run's pull request, LAD-219, changed
neither `src/lado/uninstall.py` nor this test, and the rerun passed.

Cause: the test races its own thread; the product is right. The test's `ended` flag says "the
agent has ended", but its thread sets it only after `agent.terminate()`, `agent.wait()` and a
wake-up. `uninstall._ended` counts a zombie as ended, as the living spec says (requirement
"Everything of this LADO_HOME stops"). So the uninstall may go on the moment the process dies,
and read the repositories while the thread has yet to run `ended.set()`.

Confirmed on 2026-11-07, Python 3.13, with the test unchanged:

- By elimination, from the CI failure. The test got past `assert code == 0` and the assertion
  on `taken`, so the pane's pid was taken and `_wait_for_agents` returned without its error.
  It returns so only when `_ended(agent.pid)` is true, which a running `sleep` cannot give: the
  process had died, and only the flag was late.
- Reproduced unaided: 40 runs on one CPU shared with 24 busy loops gave 1 failure, the same
  `assert [False] == [True]`. On two CPUs with 8 busy loops, 40 runs gave none.
- Reproduced at will: a pause in the thread after `agent.wait()` of 0.05 s failed 12 runs of
  12, and of 0.005 s or 0.02 s none of 12. So the thread loses when it falls behind by about one
  `AGENTS_POLL`, 0.05 s, which a loaded CI runner can do.

Options weighed:

- A (taken): the test asks the process itself. In the `_repos` hook `agent.poll() is not None`
  replaces `ended.is_set()`, and the thread only sends the signal: no `agent.wait()`, no flag.
  The check becomes the fact the test's docstring states, and nothing is left to be late.
  Long-term cost: none; one thread and one flag fewer. The thread's `agent.wait()` must go
  with the flag: `Popen.wait` holds `_waitpid_lock` while it blocks, and `Popen.poll` answers
  `None` when it cannot take that lock, so with the wait kept the same race returns.
- B: the thread sets the flag before `agent.terminate()`. Stable, but the check weakens: it
  says the signal was about to go, not that the process ended, so a product that reads
  the repositories between the two passes.
- C: the `_repos` hook waits for the flag, `ended.wait(5)`. Stable, but it removes the check:
  a product that does not wait at all passes, as the flag comes a second later anyway.
- D: the hook asks `uninstall._ended(agent.pid)`. Stable, but the code under test judges
  itself: a wrong `_ended` agrees with `_wait_for_agents`.
- E: the product waits until a zombie is reaped. It would change the right behaviour to spare
  a test: an agent whose parent, the tmux server, has ended waits for init, which the uninstall
  cannot do, and each uninstall would run into `AGENTS_TIMEOUT`.

Option A was tried on a temporary copy of the edit: 120 runs of 120 passed on the one CPU with
24 busy loops, 40 of 40 on the two CPUs with 8, and with `_wait_for_agents` replaced by a no-op
the test failed at `assert seen == [True]`, so it still catches a product that does not wait.

## What Changes

- In that test the thread's `hangup` only sleeps and terminates the agent. The flag `ended` goes.
- The `_repos` hook records `agent.poll() is not None`.
- A short comment says why the thread must not wait for the agent.

## Scope

- That one test in `tests/test_uninstall.py`.

## Out of scope

- `src/lado/uninstall.py`: the behaviour is right and matches the living spec (Why).
- The spec `uninstall`: its rule does not change, so there is no delta.
- `test_an_agent_that_ended_but_was_not_reaped_counts_as_ended`: it has no thread and holds the
  zombie rule on its own.
- `ended` in `tests/integration/test_server_process.py`: another flag, which the test waits for
  with `ended.wait(5)`; it has no such race.

## Impact

- Tests only. No behaviour rule changes, so there is no delta; archive with `--skip-specs`.
- Version: nothing users see, so no CHANGELOG.md line and no version bump of its own (the
  patch rule at most).
- Neutral core, one source of truth, no silent drops: untouched, as `src/` does not change.
  ROADMAP.md's coming stages do not touch this test.
- After the change the agent stays a zombie until the hook's `poll`, so this test always goes
  through `_ended`'s zombie branch. Its branch of a process already gone stays held by
  `test_an_agent_that_does_not_end_stops_before_the_repositories`, whose pid 4242424 does not
  exist.
