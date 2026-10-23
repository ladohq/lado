Task: LAD-131

## Why

Symptom: the integration test
`tests/integration/test_agent_liveness.py::test_a_turn_that_ends_on_a_transient_error_is_resumed_until_the_resumes_are_spent`
failed on CI (PR #144, run 39837956220, job "integration (3.10, 1)") after 30 s waiting for
the supervisor to be told of the spent resumes. Its events: `w1: spawned`, then
`w1: ended its window closed without a session-end hook`, `w1: status stopped`, and only
after that `w1: mcp_ready`. The worker was alive: the session loop took it for ended
before its window existed, and dropped its task. A rerun of the job passed.

Cause (reproduced): the session loop's window check (`runtime.check_windows`) ends an
agent whose window it misses in two looks in a row, and leaves alone only an agent
younger than one loop interval by `agents.created_at`. But the spawn writes the agent's
row (`_add_agent`) before the slow part of the spawn: queueing its task, the provider's
launch command, the first-hook blocker, and the `tmux new-window` call itself. The window
exists only once that call returns. Two facts make the allowance too thin:

- it is one loop interval: 2 s in use, 0.25 s in the integration tests;
- `agents.created_at` is `datetime('now')`, whole seconds, so the agent looks up to 1 s
  older than it is; in the tests the allowance is often nothing at all.

With the spawn's process held 0.6 s before `tmux new-window` (a throwaway pytest plugin
around `tmux.new_window`), the test fails every time with exactly the CI events; with
0.3 s it passes. Unloaded, the gap is about 15 ms (32 runs, 16 at once); a loaded CI runner
stalls a process that long now and then (tests/integration/conftest.py records 0.7 s
for a paste's confirmation under load). The same race exists in use: a spawn that stalls
for a few seconds (a slow disk, a busy machine) leaves a running worker marked stopped,
its task dropped, and the supervisor told to finish it.

Options weighed:
- A (taken): the spawn marks the moment the agent's window opened (a new column of
  `agents`), right after `tmux new-window` / `new-session` returns. The window check
  leaves alone every agent without that mark, and counts its two looks only from it. No
  timing guess is left: tmux lists a window as soon as the call that made it returns. A
  spawn that died between its row and its window (its process killed) gets a deadline
  of its own (60 s from the row), so it is not left `starting` for ever. Cost: one
  schema migration, one write per launch.
- B: a longer allowance (e.g. a fixed 5 s instead of one loop interval) with
  millisecond `created_at`. No schema change, but still a guess: a longer stall ends a
  live agent again, and every agent that really dies before its first hook is found
  later (the tests that wait for that get slower).
- C: write the agent's row after its window opens. Not possible: the window's hooks and
  MCP server need the row at once, and the first-hook blocker writes to it before the
  window starts.

## What Changes

- `agents` gets a column for when the agent's window opened (schema 35). The spawn of a
  worker and the start (and resume) of a session's supervisor set it right after tmux
  made the window.
- The session loop's window check leaves an agent alone while its window has not opened,
  and ends it only when its window is gone in two looks in a row after it opened, as
  before. One loop interval of allowance is no longer needed.
- An agent whose window never opened within 60 s of its row (the spawning process died)
  is ended with the reason "its start ended before its window opened".
- A new living spec `agent-window-check`.
- CHANGELOG.md, `### Fixed` under `## 0.43.0 (unreleased)`.

## Scope

`src/lado/state.py` (column, migration, setter, `Agent` field), `src/lado/runtime.py`
(`spawn_worker`, `start_session`, `check_windows`), `tests/agent_helpers.py`
(`previous_schema`), unit tests in `tests/test_liveness.py` and `tests/test_state.py` (or
where the migration tests live), an integration test in
`tests/integration/test_agent_liveness.py`, `docs/design/agents.md`, CHANGELOG.md.

## Out of scope

- Raising the test's 30 s timeout or the loop interval in the tests: the timeout was
  not the cause; the task asks for the cause.
- Millisecond precision for `agents.created_at`: with the mark, the window check no
  longer measures from it but for the 60 s deadline, where a second does not matter.
- Other timeout flakes (BACKLOG.md, P1 "`make check` fails on timeouts"): other causes.
- Agents of a session started by an older LADO and still running across the upgrade:
  the migration marks their windows as opened (they run), so nothing changes for them.

## Acceptance criteria

- AC-1: A worker whose spawn is held 1 s between its row and `tmux new-window` (the
  test process stalls in `tmux.new_window`) is not ended: it reaches `idle`, gets its
  task, and has no `ended` event (an integration test with the fake agent; it fails
  without the fix).
- AC-2: An agent whose window opened and then is gone in two looks in a row is ended
  with "its window closed without a session-end hook", as today; one look is not enough
  (unit tests of `check_windows`, the existing ones kept).
- AC-3: An agent with no window mark is left alone however many looks miss its window,
  until 60 s after its row; past that it is ended with "its start ended before its
  window opened" (unit tests).
- AC-4: The migration to schema 35 adds the column and marks the windows of the
  agents already in lado.db as opened; `previous_schema` undoes it (unit test).
- AC-5: The flaky test passes in 40 runs, 16 at once
  (`uv run pytest -m integration -n0 <node id>` in a loop), reported in
  `build-report`; `make lint`, `make test` and
  `uv run pytest -m integration -n auto tests/integration/test_agent_liveness.py` pass;
  CI is green on the pull request's last commit.

## Impact

- A schema migration (34 → 35): a minor-level change, but `## 0.43.0 (unreleased)`
  is a minor already; the version is not bumped here. No MCP, CLI or API change.
- Neutral core: the window check and the mark are above `providers/`; they hold for
  every provider alike.
- Living spec: new `agent-window-check`.
