## 1. The helper

- [x] 1.1 `tests/integration/test_project_sessions.py`, `_approve_and_start` (integration
  layer: the race crosses `lado mcp`, the hooks and the fake agent): add
  `wait_for(lambda: idle(session), "the supervisor idle", session)` before the
  `artifact_write` message and again before `runtime.answer_question`; the docstring says
  why, in a line or two.
- [x] 1.2 Proof that it closes both windows, in a throwaway copy outside the tree, nothing of
  it committed: `await asyncio.sleep(4)` after `self._lado_call(...)` in `mcp_server`'s
  `call_tool` for `spawn_worker` and `ask_human`; `uv run pytest -m integration -n0` on
  `test_project_secrets.py`, `test_project_variables.py`, `test_project_secrets_canary.py` and
  `test_project_sessions.py` passes. Say so in `build-report`.
- [x] 1.3 Unslowed, `test_every_agent_of_a_session_gets_its_project_s_secrets` and
  `test_a_project_secret_is_found_nowhere_else` each pass 20 times in a row with
  `-m integration -n0`; say so in `build-report`.
- [x] 1.4 `make lint` green, and `uv run pytest -m integration -n auto` on
  `tests/integration/test_project_sessions.py` green; report the tests as numbers.
