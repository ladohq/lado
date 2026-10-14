Task: LAD-44

## Why

At the release of 0.37.0 (2026-10-13) CI failed on tests that passed when rerun. The
time-based fixes tried so far did not hold: the BACKLOG entries for these flakes guessed
at slow runners, but every one has a precise cause, found in the code and in the CI logs
and evidence. Four are defects of LADO itself that a user can meet; four are defects of
the tests; one was fixed already.

Root causes, one per symptom:

1. `test_uninstall_process.py::test_uninstall_leaves_nothing`: the UI server is still
   alive after the uninstall. **LADO's defect.** `server_run.stop`
   (`src/lado/server/run.py:335`) sends SIGTERM and returns as soon as the server's lock
   is free, but the server frees it before its process ends. `cli.main`'s `finally` then
   runs `telemetry.kick()` for `lado server`, and `telemetry.state()` makes `LADO_HOME`
   (`state.home()`) even with sending off. Measured: alive 0-35 ms after `stop()`
   returned in 11 of 15 runs on an idle Mac. So `lado server stop`, `lado update` and
   `lado uninstall` can go on while the old server lives, and a dying server can make the
   `LADO_HOME` that the uninstall has just deleted again.
2. `test_agents.py::test_messages_in_the_turn_end_output_are_delivered_once_confirmed`
   (`[fake]`, `[fake-stop]`) and `test_a_slow_turn_that_goes_on_from_the_turn_end_output_gets_it_once`:
   a batch arrives `typed` instead of `hook_output`. **LADO's defect.** At a turn's end
   `hooks._idle` marks the agent idle (`state.set_status`, one transaction) and then
   takes its queue (`runtime.hand_over` → `state.take_pending`, a second one). Between
   the two commits, the session loop's `runtime.sweep` sees an idle agent with a queue
   and types the queue into its window. The hook then gets nothing to print. The message
   is still delivered once (attempts 1, as the CI failure shows), but a Claude Code or
   Codex agent gets it pasted into its window and not as the turn-end hook's output. The
   retry delays the BACKLOG blamed play no part.
3. `tests/ui/test_gates.py::test_the_humans_answer_is_the_runs_move_at_the_bottom_with_its_comment`:
   "Locator expected to be in viewport". **LADO's defect, which the test's loose locator
   exposed.** In all four CI failures the locator matched two elements. It never failed on
   a scroll. `state._open_gate` inserts the gate and then its `gate_open` event, each with
   SQLite's `'now'` of its own statement. When the millisecond turns between them, the
   gate is older than the event that opened it. The chat sorts by time
   (`web/src/Chat.tsx`, `entries`) and puts an event before a gate only on equal times, so
   the gate's line "Lado waits for you #1" lands in the human's run group, above the event
   that opened it. The test's `filter(has_text="You")` then matches that line too ("waits
   for **you**").
4. `test_agent_liveness.py::test_stopping_a_session_tells_no_one_and_counts_what_it_dropped`:
   30 s timeout waiting for the supervisor's hook. **The fake agent's defect.** The test
   waits for the fake agent's `hung_up` mark, which only its SIGHUP handler writes. An
   idle fake agent is blocked reading stdin. When `lado stop` kills the pty, that read can
   end (EOF or EIO) before Python runs the pending SIGHUP handler. On EOF the agent runs
   its session-end hook without the mark; on EIO it dies with a traceback. Python 3.10
   checks for pending signals less often, so it fails mostly there. The same cause is in
   `test_finishing_a_worker_tells_no_one_it_stopped` (BACKLOG). LADO behaves correctly:
   a late session-end hook after a stop changes nothing.
5. `tests/test_terminal_socket.py::test_control_takes_input_and_resize`: input lost.
   **The test's defect.** It takes the `done` output frame as proof that every input was
   written. In `server/terminals.py` output and input are separate tasks, and leaving the
   `with` block cancels the input task before it writes `é`.
6. `web/src/Launch.test.tsx:216` and `web/src/ArtifactTab.test.tsx` "an image shows as an
   image". **The tests' defect.** Both read state that an effect sets after the render
   they wait for: the suggested provider (`setProvider` in an effect, which Start's
   readiness needs) and `document.title` (set in an effect, and left over from the
   previous test, `tool.py`). Neither timed out: the check ran one render early.
7. `tests/ui/test_chat.py::test_a_workers_question_with_the_supervisors_recommendation_open_and_closed`:
   the card shows "The supervisor gave no recommendation". **The test's defect.**
   `runtime.ask_human` writes the question and then, in a second transaction, the request
   for the lead's recommendation. The test recommends as soon as the question exists. The
   late request sets it back to `asked`, and the fake supervisor's turn end marks it
   `missing`. A real lead recommends only after it got the request.
8. Codex smoke on macOS, "the supervisor's turn reached no model API" (3 of 25 runs).
   **The test's defect.** `tests/smoke/test_smoke.py` counts the endpoint's requests
   straight after Codex's first input is confirmed, with no wait. In both failed runs'
   evidence Codex had sent its request a moment later (the screen shows the endpoint's
   401 and Codex reconnecting).
9. `test_a_gate_with_a_recommendation_that_disagrees`: fixed by LAD-38
   (`ui-test-recommendation-race`); no failure since.

## What Changes

LADO:
- `server_run.stop` returns only once the server's process has ended, within the same
  `STOP_TIMEOUT`; its own child is reaped. `lado server` no longer starts the statistics
  sender at its exit (the server already does it every `KICK_EVERY` while it runs). This
  applies to `lado server stop`, `lado update` and `lado uninstall`.
- A turn's end makes the agent idle (or background) and takes its queue in one write
  transaction, so the session loop never sees the agent idle with the queue it is about to
  print. A Claude Code, Codex, Kilo or OpenCode agent gets the queue at its turn's end in
  the hook's output whenever its CLI takes that output.
- A gate and its `gate_open` event are written with one time, so the chat shows the event
  first.

Tests:
- The fake agent ends its session the same way whichever comes first: SIGHUP, EOF or an
  error on its terminal. It runs the session-end hook once and writes its `hung_up` mark.
- The terminal socket test waits for the written input itself.
- The Launch and ArtifactTab vitest tests wait for the state they check. ArtifactTab
  clears `document.title` after each test.
- The chat's question test waits until the request for the lead's recommendation has been
  handled before it recommends, as the gates test of LAD-38 does.
- The gates test matches the human's move by its actor exactly.
- The Codex smoke waits for the request at the endpoint.

Records:
- BACKLOG.md: the entries of these flakes are closed with their causes. The stale entry
  "Flaky: UI e2e test of a question card under load" (its test no longer exists) is
  closed. What was found on the way goes in as new entries (Out of scope).
- CHANGELOG.md: the three LADO fixes under the unreleased patch heading.

## Scope

The nine symptoms above, each fixed at its root cause, and each LADO fix with a test at
the lowest layer that catches it.

## Out of scope

- **Re-sorting stored history in the UI** (an open gate never before its own `gate_open`
  event): only gates written before the fix can be out of order, by a millisecond. The
  human's decision: not worth a sort rule.
- **The chat does not stay at the bottom when its last entry grows in place** (the scroll
  rule follows a new last key only). It is a real defect, but no CI failure shows it.
  BACKLOG entry.
- **Codex clones its plugins repository at every start** (`<CODEX_HOME>/.tmp/plugins-clone-*`,
  ~300 MB of evidence per failed smoke). It slows Codex's start but did not cause the
  smoke failure, and a config key to switch it off needs a check by hand on a CLI version.
  BACKLOG entry.
- **`state.ask_recommendation` keeping a `given` recommendation**, or the question and
  its request in one transaction: in LADO only a lead that got the request recommends, so
  only the test's shortcut meets the gap (AGENTS.md, "Only what is used").
- **A suite-wide vitest `testTimeout`/`asyncUtilTimeout`**: neither vitest failure was a
  timeout. That stays with BACKLOG's "`make check` fails on timeouts" entry.
- **Deriving the suggested provider during render in Launch**: a product refactor whose
  only visible effect lasts one render; the test waits for the state instead.
- **A rerun plugin or longer timeouts**: they hide races instead of closing them.
- The other flakes of BACKLOG not seen at 0.37.0 (the "make check under load" family, the
  live-test flakes).

## Acceptance criteria

- AC-1: After `server_run.stop()` returns, the server's process no longer exists, and
  `lado server` never runs the statistics sender at its exit. Unit and integration tests
  prove both.
- AC-2: At a turn's end, the agent's idle (or background) status and the hand-over of its
  queue are committed in one transaction. A unit test shows that no session-loop sweep
  can take the queue between them, and the two integration tests in `test_agents.py` keep
  their strict channel assertions.
- AC-3: A gate and its `gate_open` event have equal `created_at` (unit test). The gates UI
  test's move locator matches exactly one element.
- AC-4: Each of the test-only fixes (causes 4-8) is in place as described in What
  Changes.
- AC-5: Before each fix, its race is reproduced once by hand by injecting a delay where
  the cause says (none committed), and the build report quotes the failure. Not for
  cause 8, whose evidence is CI's.
- AC-6: Each fixed test passes in a local loop: 20 runs alone (`-n0`, with its marker),
  and the vitest files with `--repeat 20`.
- AC-7: On the pull request's last commit, 5 full CI runs in a row are green with no
  failed job: the first run plus 4 reruns of the whole workflow. The job `smoke
  macos-latest codex` is green 20 times in a row (job reruns).
- AC-8: `make lint`, `make test`, the changed integration and UI test files with their
  markers, and `make web` pass.

## Impact

- `src/lado/server/run.py`, `src/lado/cli.py`, `src/lado/hooks.py`,
  `src/lado/runtime.py`, `src/lado/state.py`.
- Tests: `tests/integration/fake_agent.py`, `tests/integration/test_agent_liveness.py`,
  `tests/test_terminal_socket.py`, `tests/ui/test_chat.py`, `tests/ui/test_gates.py`,
  `tests/smoke/test_smoke.py`, `web/src/Launch.test.tsx`, `web/src/ArtifactTab.test.tsx`,
  and new unit and integration tests for the LADO fixes.
- No API, MCP tool, CLI option or schema change. A patch release (fixes only). AGENTS.md
  ("How agents talk": the order at a turn's end; Layout: `server/run.py`'s stop and the
  commands that kick).

## Decisions for the record

- Scale full (the human's choice): several modules (server, hooks/state, flows' history,
  tests) and a review by breadth.
- Every flake is fixed at its root cause. None gets a longer timeout or a retry.
- The fixes of LADO's defects go in the core, not around them in the tests.
- No new UI rule for already stored, out-of-order gates (the human's decision).
- The acceptance runs on CI are 5 full runs plus 20 of the Codex macOS smoke (the
  human's decision).
- Found-on-the-way defects go to BACKLOG.md and not into this task.
- Patch version: no feature, API or schema change.
