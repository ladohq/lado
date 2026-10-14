## Context

At the 0.37.0 release, nine tests failed in CI and passed when rerun. Their causes come
from the code, the CI logs and the smoke evidence (proposal, Why). The design takes each
cause where it starts: in LADO for causes 1-3, in the tests for causes 4-8. ROADMAP.md
makes LADO the tool LADO is developed with, so a red CI with no real failure costs every
flow run a rerun and a reviewer's doubt.

Design principles that apply: **No silent drops** (a message pasted instead of printed
still arrives, but by the channel LADO did not mean); **Neutral core** (the hand-over fix
is in `hooks`/`runtime`/`state`, the same for every provider; the fake agent's fix is in
the tests only); **Only what is used** (no new state for a test's shortcut).

## Decisions

### D1. `server_run.stop` waits for the process, not only for the lock

Options:
1. Wait for the lock, then poll the pid until it is gone, within `STOP_TIMEOUT`
   (chosen). About ten lines. The waiting stays in one place for every caller.
2. Hold the lock until the process exits (nothing after `with lock:`). This changes what
   the lock means and depends on the order things happen at exit, which is fragile.
3. Wait in the test only. That hides a real race that `lado update` and `lado uninstall`
   also have.

The poll: `os.waitpid(pid, os.WNOHANG)` first. When the pid is the caller's own child,
this reaps it and a zombie can never look alive. `ChildProcessError` means it is not the
caller's child: then `os.kill(pid, 0)`, where `ProcessLookupError` means the process is
gone. One deadline covers both waits. The error text at the timeout stays as it is.

### D2. `lado server` does not kick the statistics sender at its exit

`cli.main` already leaves out `update`, `uninstall` and `telemetry send`. `server` joins
them, with the reason in the comment: the server kicks every `KICK_EVERY` in
`server/run.housekeeping`, so nothing is lost, and a kick from a server that is dying
could make `LADO_HOME` again after an uninstall. Making `telemetry.state()` never create
`LADO_HOME` was rejected: other readers rely on `state.home()` making it, and once D1 is
in place the server's own exit is the only path left.

### D3. Idle and the hand-over in one transaction

Options:
1. One write transaction that sets the status and takes the queue (chosen). The status
   switch goes into `state.take_pending` as an optional first step (`become: str | None`):
   inside its `BEGIN IMMEDIATE`, `_set_status(db, session, recipient, become)` runs
   before the `idle_only` check. When nothing is taken (the check fails because a batch
   handed over before is still unconfirmed, or nothing is pending), the transaction
   commits the status alone and never rolls it back. `runtime.hand_over(session, recipient, channel, become=None)` passes it
   on. `hooks._idle` calls `hand_over(..., become=IDLE or BACKGROUND)` instead of
   `set_status` and then `hand_over`. Every other caller is unchanged.
2. Loosen the integration tests to accept `typed` when there was one attempt. This stops
   checking the very channel these tests exist for, and leaves the paste for real CLIs.
3. Run the session loop more slowly in those tests. That makes the race rarer but does
   not remove it.

The sender's rule stays as it is (queue first, take second). A message queued before the
hook's transaction is taken by it. A message queued after it finds the agent busy with a
sent batch (it waits), or idle with nothing sent (the sender types it). So a message is
still handed over exactly once. AGENTS.md's "a hook sets idle first and takes the queue
second" becomes "a hook sets idle and takes the queue in one transaction".

### D4. A gate's event takes the gate's time

`state._open_gate` inserts the gate, reads its `created_at` back by id, and writes the
`gate_open` event with that time. `_add_event` gets an optional `at: str | None`; when it
is given, the INSERT names `created_at`. This fits the chat's existing tie rule ("an event
before a gate: a gate opens in its event's transaction"), which was right in intent but
not true to the millisecond. Two alternatives were rejected. Setting both rows from one
Python time would give these two rows a different clock from every other row, which
SQLite stamps. A UI sort rule for stored rows was declined by the human.

### D5. The fake agent ends its session once, whatever ends its terminal

`tests/integration/fake_agent.py` gets `end_session(why)`, guarded to run once (a module
flag). When `FAKE_AGENT_HANGUP_HOOK=1` it runs `hook("session_end")` and reports
`hung_up=<the hook's result>` with `ended_by=why`; it never writes the mark without the
hook. The SIGHUP handler calls it and then `os._exit(0)`. `read_input` treats an
`OSError` on stdin as the end of input. `main`'s end-of-input path calls
`end_session("eof")` instead of a bare `hook("session_end")`. While the SIGHUP handler
runs inside `end_session`, the guard keeps the EOF path from running the hook a second
time. The tests' wait for `hung_up` stays. The test also asserts that no `ended` event
of either agent follows the `session_stop`: the late hooks changed nothing.

### D6. Test-only waits, each for the state it checks

- Terminal socket: `FakeTerminal` gets a `threading.Condition` that `write` notifies.
  The test waits, inside the `with` block and with a 5 s deadline, until `written` holds
  both inputs and `size` is `(120, 40)`. The `done` frame and its comment go.
- Launch: `ready()` also waits for `providerSelect().value` to be the suggested
  provider, and the synchronous `expect(startButton().disabled).toBe(false)` checks
  after a folder check (lines 216, 402, 413, 510, 643 today) become
  `await waitFor(...)`.
- ArtifactTab: `afterEach` sets `document.title = ""`, and each title check after a
  `findBy` becomes `await waitFor(() => expect(document.title).toBe(...))`.
- Chat question card: after the question exists, the test waits until its
  `recommendation_state` is `REC_MISSING` (the supervisor's turn on the request ended)
  and asserts that nothing to the supervisor is `pending` or `sent`. Only then does it
  recommend, as `test_gates.py` does since LAD-38.
- Gates move: the locator is the last run group's `li.run-flow` whose `.run-actor` text
  is exactly `You`. A new check asserts that the last run group has no
  `li.run-gate_open`.
- Codex smoke: the bare `assert asked` becomes `wait_for(lambda: fake_endpoint.requests,
  "the supervisor's turn at the endpoint", 120)`, with a comment saying why: Codex posts
  after its prompt-submit hook confirmed the input. For the other providers the earlier
  `turn_error` wait means this returns at once.

### D7. Proof: the race shown before the fix, then loops

For each cause in LADO and each of causes 4-7, the developer first makes the race happen
every time by hand, with a delay where the cause says: a `sleep` between the server's
lock release and its exit; between `set_status` and `hand_over`; between the gate's
INSERT and its event's; before the fake agent's signal handling; in `FakeTerminal.write`;
in the provider effect and the title effect; before the late `ask_recommendation`. The
developer quotes the failure in the build report. None of these delays is committed.
After the fix: the loops of AC-6 and the CI runs of AC-7.

### D8. Test layers

- D1: unit (`tests/test_server.py`): a fake pid
  alive for N polls, then gone; a child process reaped; the timeout error. Integration
  (`tests/integration/`): `lado ui --port 0`, then `server_run.stop()`, then the pid is
  gone, 5 times in a loop. The uninstall integration test is unchanged.
- D2: unit (`tests/test_cli_telemetry.py`, beside `test_main_kicks_after_a_human_s_command`): `cli.main(["server", ...])` with `serve` and
  `telemetry.kick` patched; the kick is never called.
- D3: unit (`tests/test_state.py` for `take_pending`, `tests/test_runtime.py` for the hook's path): `take_pending(...,
  become=IDLE)` sets the status and takes the queue in one commit; with an empty queue it
  leaves the agent idle with one `status` event. A probe wraps `state.connect` so that
  `runtime.sweep` runs on another connection right after the status UPDATE, before the
  commit. The sweep cannot type the batch: SQLite's write lock blocks it, or it finds the
  agent busy with a sent batch. The integration tests in `test_agents.py` keep their
  assertions.
- D4: unit (`tests/test_state.py`): with `strftime`'s millisecond forced to turn (a
  `sqlite3` function override, or a gate written across a patched clock), the gate's and
  its event's `created_at` are equal. UI e2e: the gates test as in D6.
- D5-D6: the tests themselves, at their own layers.

## Risks / Trade-offs

- D3 moves the status write into `take_pending`'s transaction. A hook that fails between
  the two calls today leaves the agent idle with its queue for the sweep. After the
  change there is no such gap, so nothing new is lost. The `status` event is written in
  the same transaction as before.
- D1 can make `lado server stop` take a few milliseconds more. A process that hangs at
  exit now gives the timeout error instead of a silent success, which is the point.
- D4 adds a read of the gate's row inside the transaction: one indexed SELECT.

## Migration

None: no schema change. Gates already stored keep their times (Out of scope).
