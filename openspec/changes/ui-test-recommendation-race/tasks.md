## 1. The test

- [ ] 1.1 By hand, before the fix: in `test_a_gate_with_a_recommendation_that_disagrees`,
  right after `state.ask_recommendation(...)`, send the supervisor a message
  (`runtime.send_message(session, "human", "supervisor", "ping")`) and run the test
  alone: it fails with "The supervisor gave no recommendation" (AC-3). Do not commit the
  probe; quote the failure in the build report.
- [ ] 1.2 `tests/ui/test_gates.py`, `test_a_gate_with_a_recommendation_that_disagrees`:
  before `state.ask_recommendation(...)`, wait with `agent_helpers.wait_for` until
  `state.get_gate(1).recommendation_state == state.REC_MISSING` (the supervisor's turn on
  the gate's own request ended), then assert that no message of the session to the
  supervisor is in `state.PENDING` or `state.SENT` (`state.list_messages`). A comment says
  why: the re-ask is a notice from outside any turn, which the end of a turn still to come
  would mark missing (AC-1).
- [ ] 1.3 The test alone 20 times in a row, `uv run pytest -m ui -n0
  tests/ui/test_gates.py -k disagrees`, each run's exit status read (not piped), and
  `uv run pytest -m ui -n auto tests/ui/test_gates.py` 5 times in a row; all pass (AC-2).
- [ ] 1.4 `make lint` passes; the build report gives the counts (AC-4).
