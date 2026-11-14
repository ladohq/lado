## 1. The helper

- [ ] 1.1 `agent_helpers.settled(session, agent)` (D1) with a docstring that says why idle is not
  enough and that the fake agent runs only typed commands; unit tests in
  `tests/test_agent_helpers.py` for AC-3 (busy; idle with a pending message; idle with a sent
  one; idle with only delivered or read ones, an unread body included) (check:
  `uv run pytest -n0 tests/test_agent_helpers.py`)

## 2. The two tests

- [ ] 2.1 Reproduce the `test_session_start.py` race once by forcing the window (D3, AC-4): the
  test fails with "start_session's result" not seen; note how in the build report, commit nothing
  of it
- [ ] 2.2 The approved-proposal test waits for the supervisor settled before the `askhuman`
  command and before `start_session b <id>` (AC-1) (check:
  `uv run pytest -m integration -n0 tests/integration/test_session_start.py`)
- [ ] 2.3 Reproduce the `test_flow_runs.py` race once the same way (the reminder queued after the
  gate answer): the step assertion fails; note how, commit nothing of it
- [ ] 2.4 `to_the_gate` waits for the worker settled after the gate (AC-2) (check:
  `uv run pytest -m integration -n0 tests/integration/test_flow_runs.py -k gate`)

## 3. Docs, backlog and regression

- [ ] 3.1 `docs/testing.md`: `settled` among the shared helpers, with when to use it rather than
  waiting for idle
- [ ] 3.2 BACKLOG.md, a commit of its own: P2 entry "integration tests send a human command
  before the agent's turn and its reminder are over" (the shape, the two cases of LAD-284, the
  helper to use; Size, Why here, Found: 2026-11-14, hotfix/lad-284-tests-wait-for-turn-end)
- [ ] 3.3 Regression (AC-5): `uv run pytest -m integration -n auto
  tests/integration/test_session_start.py tests/integration/test_flow_runs.py`, the same two
  files alone with `-n0`, `make test`, `make lint`,
  `openspec validate tests-wait-for-turn-end --strict`
