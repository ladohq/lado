The plan with each step's code: `docs/superpowers/plans/2026-10-14-flake-races.md`.
Each fix starts with its race reproduced by hand, by a delay that is not committed (D7),
and the build report quotes that failure.

## 1. LADO: the UI server's stop

- [ ] 1.1 `server_run.stop` waits for the lock, then for the process (`_gone`: reap our
  own child, else signal 0; PermissionError counts as gone), within `STOP_TIMEOUT` (D1).
  Unit tests in `tests/test_server.py`: waits after the lock, the timeout error, a child
  reaped. Integration test: `lado ui` then `stop()`, pid gone, 5 times. Spec
  `server-stop`: "The server is gone when stop returns", "A server of the caller's own",
  "A process that outlives its lock".
- [ ] 1.2 `lado server` starts no statistics sender at its exit (D2). Unit test in
  `tests/test_cli_telemetry.py`. Spec: "The server ends after an uninstall".
  `tests/integration/test_uninstall_process.py` passes with `-m integration`.

## 2. LADO: a turn's end hand-over

- [ ] 2.1 `state.take_pending(..., become=)`, `runtime.hand_over(..., become=)`,
  `hooks._idle` in one transaction; the status is committed when nothing is taken (D3).
  Unit tests in `tests/test_state.py` (taken in one commit, nothing pending, a batch
  still unconfirmed) and `tests/test_runtime.py` (a sweep at the turn's end cannot type
  the batch). Spec `turn-end-hand-over`: all three scenarios. The integration tests in
  `tests/integration/test_agents.py` pass unchanged with `-m integration`. AGENTS.md
  "How agents talk" says one transaction.

## 3. LADO: a gate's time

- [ ] 3.1 `_add_event(at=)` and `_open_gate` give the event the gate's `created_at` (D4).
  Unit test in `tests/test_state.py` with the millisecond forced to turn. Spec
  `gate-history-order`: "The millisecond turns between the two rows".
- [ ] 3.2 `tests/ui/test_gates.py`: the move matched by its actor exactly, and no gate
  line in the last run group (D6). Spec: "The human's move after a gate". Run with
  `-m ui`.

## 4. Tests

- [ ] 4.1 The fake agent's `end_session(why)`, run once on SIGHUP, EOF or an error on
  stdin (D5). `test_stopping_a_session_…` and `test_finishing_a_worker_…` assert that no
  `ended` event follows the stop or finish; each runs 20 times with `-m integration -n0`.
- [ ] 4.2 `tests/test_terminal_socket.py`: `FakeTerminal.wait` for the written input and
  size (D6); 20 runs.
- [ ] 4.3 `web/src/Launch.test.tsx` (`ready()` waits for the suggested provider; Start's
  checks in `waitFor`) and `web/src/ArtifactTab.test.tsx` (title reset in `afterEach`,
  title checks in `waitFor`) (D6); `--repeat 20`; `make web` passes.
- [ ] 4.4 `tests/ui/test_chat.py`: the question test waits for `REC_MISSING` and nothing
  queued to the supervisor before it recommends (D6); 20 runs with `-m ui -n0`.
- [ ] 4.5 `tests/smoke/test_smoke.py`: wait up to 120 s for the endpoint's request (D6);
  collects with `-m smoke`.

## 5. Records

- [ ] 5.1 BACKLOG.md: the fixed entries are removed (the list in the plan, Task 10). Two
  entries found on the way are added: the chat's bottom when its last entry grows, and
  Codex's plugin clone at start. CHANGELOG.md has three lines under `0.37.1
  (unreleased)`. AGENTS.md Layout (`server/run.py`'s stop, `server` among the commands
  that do not kick).

## 6. Acceptance

- [ ] 6.1 `make lint`, `make test`, the changed integration and UI files with their
  markers, and `make web` pass (AC-8).
- [ ] 6.2 The local loops of 4.1-4.4 and 2.1's integration tests: 20 runs each,
  counted in the build report (AC-6).
- [ ] 6.3 On the pull request's last commit: 5 full CI runs green in a row, with no
  failed job, and `smoke macos-latest codex` green 20 times. The run and attempt ids are
  in the build report (AC-7).
