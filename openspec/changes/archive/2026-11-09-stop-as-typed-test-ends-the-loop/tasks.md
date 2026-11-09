## 1. The tests

- [x] 1.1 By hand, before the fix: in `test_a_stop_as_the_message_is_typed_refuses_it_on_a_tmux_server_left_empty`,
  after `stop_as_it_types(monkeypatch)`, wrap `runtime._sweep_sent` with `monkeypatch` so it
  sleeps 0.6 s first, and run the test alone, `uv run pytest -m integration -n0
  "tests/integration/test_human_messages.py::test_a_stop_as_the_message_is_typed_refuses_it_on_a_tmux_server_left_empty"`:
  it fails with `Failed: DID NOT RAISE LadoError` (AC-2). Quote the failure in the build report.
- [x] 1.2 `tests/agent_helpers.py`: a helper that ends session `session`'s loop: its pid from the
  session's last `loop started, pid N` line in `state.home() / "loop.log"`, the process ended
  (`os.kill`), then `loop.wait_stopped` with a timeout; `pytest.fail` with what it found when no
  such line exists or the loop is still running (AC-1).
- [x] 1.3 `tests/integration/test_human_messages.py`: `refused_by_the_stop` calls the helper first,
  with a comment that the session loop would otherwise hand the message over in its own
  process, past the patched typing (AC-1). With the probe of 1.1 both tests pass; remove the
  probe (AC-2).
- [x] 1.4 Each of the two tests alone 20 times in a row (`-n0`) and `uv run pytest -m integration
  -n auto tests/integration/test_human_messages.py` 3 times in a row, each run's exit status
  read (not piped); all pass (AC-3). The build report gives the counts.

## 2. Checks

- [x] 2.1 `make lint` passes (AC-4).
- [x] 2.2 `make test` passes (`tests/agent_helpers.py` is shared with unit tests).
- [x] 2.3 `openspec validate stop-as-typed-test-ends-the-loop --strict` passes.
