## 1. State

- [ ] 1.1 `src/lado/state.py`: `agents.window_at` (D1), migration step 35 with the
  `UPDATE` for existing rows, `SCHEMA_VERSION = 35`, `Agent.window_at`,
  `state.window_opened(session, name)`. `tests/agent_helpers.py`: `schema_before` and
  `previous_schema` undo step 35. A unit test: a schema-34 row gets
  `window_at = created_at` (AC-4). `make test`.

## 2. The window check

- [ ] 2.1 `src/lado/runtime.py`: `window_opened` after `tmux.new_window` in
  `spawn_worker` and after `tmux.new_session` in `start_session` (D2); `check_windows`
  by D3 with `SPAWN_DEADLINE` and `SPAWN_DIED`; its docstring says why the mark.
- [ ] 2.2 `tests/test_liveness.py` (unit): no mark and many looks → left alone; no mark
  past 60 s → ended with `SPAWN_DIED` and the supervisor told; the existing two-looks
  tests kept with the mark (AC-2, AC-3). Each new test fails without 2.1.
- [ ] 2.3 `tests/integration/test_agent_liveness.py`: a worker whose spawn stalls 1 s in
  `tmux.new_window` reaches idle with its task delivered and no `ended` event (AC-1);
  fails without 2.1. `uv run pytest -m integration -n auto
  tests/integration/test_agent_liveness.py`.

## 3. Documents

- [ ] 3.1 `docs/design/agents.md`, the window check in the item on `runtime.agent_ended`:
  the window mark, the dead-spawn deadline and its reason.
- [ ] 3.2 CHANGELOG.md, `### Fixed` under `## 0.43.0 (unreleased)`: a worker whose start
  was slow is no longer shown stopped before it ran, with its task dropped.

## 4. Checks

- [ ] 4.1 The flaky test 40 times, 16 at once
  (`seq 40 | xargs -P 16 -I{} uv run pytest -m integration -n0 -q <node id>`): all pass,
  counts in `build-report` (AC-5).
- [ ] 4.2 `make lint`, `make test`, the integration file of 2.3 with `-m integration`,
  `openspec validate late-agent-window --strict`; CI green on the last commit (AC-5).
