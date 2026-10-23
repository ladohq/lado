## Context

`runtime.check_windows` is the only sign that an agent whose CLI died without a hook has
ended. It must tell "the window is not made yet" from "the window is gone". Today it
guesses by the agent's age (`agents.created_at`, whole seconds) against one loop
interval, while the row is written before the slow part of the spawn. See proposal.md
for the reproduction.

## Decisions

### D1. A window mark in `agents`, not a longer allowance

A nullable column `window_at TEXT` (UTC, `strftime('%Y-%m-%d %H:%M:%f', 'now')`) on
`agents`, migration step 35 (`AGENTS_WINDOW_AT`, an `ALTER TABLE ... ADD COLUMN` plus
`UPDATE agents SET window_at = created_at` for the rows already there), `state.Agent`
gets `window_at: str | None = None`. A setter `state.window_opened(session, name)` sets
it for the row; a row that is gone (a failed spawn forgot it) is no error. Why: the
mark is the fact the check needs; any allowance by time is a guess that a stall beats.
The `events` table was weighed instead (no migration) and left: the check would read the
events of every agent on every pass, and an event is history, not state.

### D2. Where the mark is set

Right after `tmux.new_window` returns in `runtime.spawn_worker` (inside the `try`, so a
failure of the write undoes the spawn as any other), and right after `tmux.new_session`
returns in `runtime.start_session`. These are the only two calls that make an agent's
window (`grep new_window\|new_session src/lado`). A stop deletes the session's agent rows,
so a resume starts with no mark.

### D3. The check

For an agent not stopped and not listed:
- `window_at` is NULL and the row is younger than `SPAWN_DEADLINE = 60` s (a constant in
  `runtime`, by `created_at`): left alone, not counted as missing;
- `window_at` is NULL and the row is older: ended with `SPAWN_DIED = "its start ended
  before its window opened"` at once (one look: there was never a window to come back);
- otherwise as today: missing in this look and the one before → ended with
  `WINDOW_GONE`.
The one-interval allowance by `created_at` goes. 60 s: the tmux call alone may take
`tmux.TIMEOUT` (10 s); the rest of a spawn is local file work.

### D4. Tests

- Unit (`tests/test_liveness.py`): the check with no mark (old row, many looks: left
  alone), with no mark past the deadline (ended, `SPAWN_DIED`), with the mark (the
  existing two-looks tests); the test "an agent spawned within a loop interval is left
  alone" becomes "an agent whose window has not opened is left alone". The migration:
  the existing schema tests with `previous_schema` updated, plus one that a row of
  schema 34 gets `window_at = created_at`.
- Integration (`tests/integration/test_agent_liveness.py`): the test process wraps
  `tmux.new_window` to sleep 1 s (four loop intervals) before it for `w1`; the real
  session loop runs in its own process. Without D3 it fails as on CI (checked by hand in
  the design: 0.6 s is enough).

## Risks

- A spawn stalled more than 60 s between its row and its window would be ended: far
  beyond any stall seen, and it is said loudly with its own reason.
