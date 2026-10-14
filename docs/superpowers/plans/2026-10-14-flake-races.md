# Flake races Implementation Plan

**Goal:** Close each race behind the nine tests that failed at the 0.37.0 release, at its
root cause: three defects in LADO, four in the tests. None gets a longer timeout or a
retry.

**Architecture:** LADO fixes in `server/run.py` (stop waits for the process), `cli.py` (no
kick from `lado server`), `state.py`/`runtime.py`/`hooks.py` (idle and the hand-over in
one transaction) and `state.py` (a gate's event takes the gate's time). Test fixes in the
fake agent, the terminal socket test, two vitest files, two UI tests and the smoke test.

**Tech Stack:** Python 3.10+, SQLite, pytest (+ xdist, playwright), vitest/Testing
Library.

**Spec:** `openspec/changes/flake-races/` (proposal, three deltas, `design.md` D1-D8) and
`docs/superpowers/specs/2026-10-14-flake-races-design.md`.

## Global Constraints

- A patch release: no API, MCP tool, CLI option or schema change.
- No longer timeouts and no rerun plugin: each fix closes its race.
- Before each fix, its race is reproduced by hand with an injected delay (D7). The delay
  is never committed, and the failure is quoted in the build report.
- One commit per task. Messages in the repo's style: a plain sentence, then `(LAD-44)`.
- Run integration tests with `-m integration` and UI tests with `-m ui`. Read each exit
  status from a log file, never through a pipe (`.lado/sdlc.md`, Review traps).
- Edit with the edit tools, not `sed -i` or heredocs.

## Review Focus

- `take_pending(become=...)` when the agent still has an unconfirmed batch: the status
  must be committed and nothing taken (Task 3, its own test).
- `server_run.stop()` on a pid that belongs to another user, or one reused after exit:
  `kill(pid, 0)` raises `PermissionError`. Treat it as gone (the pid is no longer our
  server's) (Task 1, its own test).
- The sender's path after D3: a message sent in the same instant as the turn's end is
  handed over exactly once (Task 3, an existing integration test plus a unit test).
- A fake agent that gets both EOF and SIGHUP runs the session-end hook once (Task 5,
  counted in `inputs`/hooks log).
- The chat's old gates (stored before the fix) still render. No new sort rule (Out of
  scope); no test needed.

---

### Task 1: `server_run.stop` returns once the process has ended (D1)

**Files:**
- Modify: `src/lado/server/run.py:335-346` (`stop`)
- Test: `tests/test_server.py`, `tests/integration/test_server_stop.py` (new; check first
  whether an integration file for the UI server's process exists, e.g. one that tests
  `lado ui` in the background, and add the test there instead)

**Interfaces:**
- Produces: `stop() -> dict | None`, unchanged signature; `_gone(pid: int) -> bool`
  (module-private).

- [ ] **Step 1: Reproduce.** In a scratch copy (not committed), add `time.sleep(0.5)` in
  `cli.main`'s `finally` before `telemetry.kick()`. Run
  `uv run pytest -m integration -n0 tests/integration/test_uninstall_process.py::test_uninstall_leaves_nothing`
  and expect `assert not alive(server["pid"])` to fail. Quote it in the build report and
  remove the sleep.
- [ ] **Step 2: Failing unit tests** in `tests/test_server.py`:

```python
def test_stop_waits_for_the_process_after_its_lock(monkeypatch):
    polls = iter([True, True, False])  # the pid lives two polls after the lock is free
    monkeypatch.setattr(server_run, "running", lambda: {"pid": 4242})
    monkeypatch.setattr(server_run.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(server_run, "_held", lambda: False)
    monkeypatch.setattr(server_run, "_gone", lambda pid: not next(polls))
    assert server_run.stop() == {"pid": 4242}


def test_stop_names_a_process_that_outlives_its_lock(monkeypatch):
    monkeypatch.setattr(server_run, "STOP_TIMEOUT", 0.2)
    monkeypatch.setattr(server_run, "running", lambda: {"pid": 4242})
    monkeypatch.setattr(server_run.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(server_run, "_held", lambda: False)
    monkeypatch.setattr(server_run, "_gone", lambda pid: False)
    with pytest.raises(runtime.LadoError, match=r"pid 4242\) did not end in 0.2s"):
        server_run.stop()


def test_gone_reaps_a_child_and_reads_a_stranger():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 5
    while not server_run._gone(child.pid):
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert server_run._gone(child.pid)  # reaped: no zombie left
    assert not server_run._gone(os.getpid())  # alive, not our child
```

- [ ] **Step 3: Run** `uv run pytest -n0 tests/test_server.py -k "stop_waits or outlives or gone_reaps"`.
  Expected: FAIL (`_gone` is not defined).
- [ ] **Step 4: Implement.**

```python
def _gone(pid: int) -> bool:
    """Whether the process `pid` has ended: reaped when it is this process's child, else
    no longer there (a pid we may not signal is no longer our server's)."""
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == pid
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return True
    return False


def stop() -> dict | None:
    """Stop the running server and wait until its process has ended (its lock is freed
    a moment before); its server.json, or None when none runs."""
    info = running()
    if info is None:
        return None
    os.kill(info["pid"], signal.SIGTERM)
    deadline = time.monotonic() + STOP_TIMEOUT
    while _held() or not _gone(info["pid"]):
        if time.monotonic() > deadline:
            raise LadoError(f"the LADO server (pid {info['pid']}) did not end in {STOP_TIMEOUT:g}s")
        time.sleep(0.05)
    return info
```

- [ ] **Step 5: Integration test.** Start `lado ui --no-open --port 0` (as the uninstall
  test does), call `server_run.stop()`, and assert that `os.kill(pid, 0)` raises
  `ProcessLookupError`. Repeat 5 times in the test. Run with `-m integration -n0`.
- [ ] **Step 6: Run** the unit and integration tests plus
  `tests/integration/test_uninstall_process.py` with `-m integration -n0`. Expected:
  PASS.
- [ ] **Step 7: Commit** `The server's stop waits until its process has ended (LAD-44)`.

### Task 2: `lado server` starts no statistics sender at its exit (D2)

**Files:**
- Modify: `src/lado/cli.py:1505-1511` (the `kicks` rule and its comment)
- Test: `tests/test_cli_telemetry.py`

- [ ] **Step 1: Failing test**

```python
def test_the_server_kicks_nothing_at_its_exit(monkeypatch):
    """The running server kicks every KICK_EVERY; a kick at its exit could make LADO_HOME
    again after `lado uninstall` deleted it."""
    kicked = []
    monkeypatch.setattr(telemetry, "kick", lambda: kicked.append(1))
    monkeypatch.setattr(server_run, "serve", lambda *a, **k: 0)
    cli.main(["server", "--port", "0"])
    assert kicked == []
```

  (Patch whatever `cmd_server` calls: read `cli.cmd_server` first and patch that name.)
- [ ] **Step 2: Run** it and expect FAIL (`[1]`).
- [ ] **Step 3: Implement.** `kicks = args.command not in ("update", "server") and not
  removes`. Extend the comment: `nor from lado server, which kicks every KICK_EVERY while
  it runs (server/run.housekeeping): one at its exit could make LADO_HOME again after an
  uninstall`.
- [ ] **Step 4: Run** `uv run pytest -n0 tests/test_cli_telemetry.py`. Expected: PASS.
- [ ] **Step 5: Commit** `lado server starts no statistics sender at its exit (LAD-44)`.

### Task 3: A turn's end makes the agent idle and takes its queue in one transaction (D3)

**Files:**
- Modify: `src/lado/state.py` (`take_pending`, ~2370), `src/lado/runtime.py`
  (`hand_over`, ~1762), `src/lado/hooks.py` (`_idle`, ~249 and its docstring)
- Test: `tests/test_state.py`, `tests/test_runtime.py`
- Docs: AGENTS.md "How agents talk", the paragraph "Every path takes the queue the same
  way…": "a hook sets idle first and takes the queue second" becomes "a hook sets idle
  and takes the queue in one transaction".

**Interfaces:**
- Produces: `state.take_pending(session, recipient, mark, status=None, idle_only=False,
  channel=None, become: str | None = None)`;
  `runtime.hand_over(session, recipient, channel=state.TYPED, become: str | None = None)
  -> str`.

- [ ] **Step 1: Reproduce.** Locally (not committed), add `time.sleep(0.5)` in
  `hooks._idle` between `state.set_status(...)` and `runtime.hand_over(...)`. Run
  `uv run pytest -m integration -n0 "tests/integration/test_agents.py::test_messages_in_the_turn_end_output_are_delivered_once_confirmed"`
  and expect the channel assertion to fail with `typed`. Quote it and remove the sleep.
- [ ] **Step 2: Failing unit tests** in `tests/test_state.py` (use the file's existing
  fixtures for a session with an agent; read how its `take_pending` tests set one up):

```python
def test_take_pending_becomes_idle_and_takes_in_one_commit(agent_busy_with_one_pending):
    session, name = agent_busy_with_one_pending
    taken = state.take_pending(
        session, name, state.SENT, state.BUSY, True, state.HOOK_OUTPUT, become=state.IDLE
    )
    assert [m.channel for m in taken] == [state.HOOK_OUTPUT]
    assert state.get_agent(session, name).status == state.BUSY
    statuses = [e.detail for e in state.list_events(session) if e.kind == state.STATUS]
    assert statuses[-2:] == [state.IDLE, state.BUSY]


def test_take_pending_becomes_idle_with_nothing_to_take(agent_busy_with_nothing_pending):
    session, name = agent_busy_with_nothing_pending
    assert (
        state.take_pending(
            session, name, state.SENT, state.BUSY, True, state.HOOK_OUTPUT, become=state.IDLE
        )
        == []
    )
    assert state.get_agent(session, name).status == state.IDLE


def test_take_pending_keeps_the_status_when_a_batch_is_unconfirmed(
    agent_busy_with_a_sent_batch_and_one_pending,
):
    session, name = agent_busy_with_a_sent_batch_and_one_pending
    assert (
        state.take_pending(
            session, name, state.SENT, state.BUSY, True, state.HOOK_OUTPUT, become=state.IDLE
        )
        == []
    )
    assert state.get_agent(session, name).status == state.IDLE  # committed, not rolled back
```

  The fixtures are small helpers in the test file: `state.add_agent` plus
  `state.set_status(..., BUSY)`, and `state.queue_message` (plus a `take_pending` with
  mark SENT for the unconfirmed batch). Use the module's own setup helpers.
- [ ] **Step 3: Failing race test** in `tests/test_runtime.py`: patch
  `state._set_status` to call the original, then run `runtime.sweep(session, name)` on a
  thread and join it with a 0.5 s timeout (it blocks on SQLite's write lock or finds the
  agent busy). Then call `hooks._idle(...)` for a provider with `deliver_on_turn_end`
  (use the fake provider the file uses, or `providers.get("claude")`) with a turn-end
  `Event`. Assert that the hook returns the output with the message, that the message's
  channel is `hook_output` with one attempt, and that `tmux.send_text` (the recorder) got
  nothing. Before the fix, it fails with the message typed.
- [ ] **Step 4: Implement** in `state.take_pending`, right after `BEGIN IMMEDIATE`:

```python
        if become:
            _set_status(db, session, recipient, become)
        if idle_only and not db.execute(...).fetchone():
            db.execute("COMMIT" if become else "ROLLBACK")
            return []
```

  Add to the docstring: `become: set this status first, in the same transaction, and keep
  it whether or not anything is taken (a hook's switch to idle or background:
  lado.hooks._idle)`. In `runtime.hand_over`, add `become: str | None = None` and pass it
  through (`state.take_pending(session, recipient, state.SENT, state.BUSY, True, channel,
  become=become)`); the docstring names it. In `hooks._idle`:

```python
    background = turn_end is not None and turn_end.background
    by_output = (
        turn_end is not None
        and not turn_end.output_ignored
        and provider.capabilities.deliver_on_turn_end
    )
    channel = state.HOOK_OUTPUT if by_output else state.TYPED
    text = runtime.hand_over(
        session, agent, channel, become=state.BACKGROUND if background else state.IDLE
    )
```

  Steps 2-3 of the docstring become one step: `2. Mark idle and take the queue in one
  transaction (runtime.hand_over with become): the session loop never sees the agent
  idle with the queue this hook takes.` Keep the rest.
- [ ] **Step 5: Run** `uv run pytest -n auto tests/test_state.py tests/test_runtime.py
  tests/test_liveness.py tests/test_recommendation.py`. Then run
  `uv run pytest -m integration -n0 tests/integration/test_agents.py`. Expected: PASS.
- [ ] **Step 6: Edit AGENTS.md** (the sentence above), then commit `A turn's end makes the
  agent idle and takes its queue in one transaction (LAD-44)`.

### Task 4: A gate and its event share one time; the gates test matches its move exactly (D4, D6)

**Files:**
- Modify: `src/lado/state.py` (`_add_event` ~1461, `_open_gate` ~1700)
- Test: `tests/test_state.py`, `tests/ui/test_gates.py:126-145`

- [ ] **Step 1: Reproduce.** Locally, add `time.sleep(0.01)` after the gates INSERT in
  `_open_gate`. Run `uv run pytest -m ui -n0 tests/ui/test_gates.py -k humans_answer`
  (with `make web` built) and expect the strict-mode failure. Quote it and remove the
  sleep.
- [ ] **Step 2: Failing unit test** (a run that enters a gate, as the file's flow tests
  do, with the INSERT delayed by a patched `sqlite3` function or by patching
  `state._add_event` to sleep 5 ms before calling the original):

```python
def test_a_gate_and_its_event_share_one_time(gated_run, monkeypatch):
    original = state._add_event

    def late(*args, **kwargs):
        time.sleep(0.005)  # the millisecond turns between the gate and its event
        return original(*args, **kwargs)

    monkeypatch.setattr(state, "_add_event", late)
    gate = gated_run()  # enters an approval gate
    opened = [e for e in state.list_events(gate.session) if e.kind == state.GATE_OPEN][-1]
    assert opened.created_at == gate.created_at
```

  (Use the existing helpers that open a gate and read events and gates. Check that `Gate`
  carries `created_at`; if not, read it with `state.get_gate`.)
- [ ] **Step 3: Implement.**

```python
def _add_event(db, session, agent, kind, detail, run=None, at: str | None = None) -> None:
    if at is None:
        db.execute(
            "INSERT INTO events (session, agent, kind, detail, run) VALUES (?, ?, ?, ?, ?)",
            (session, agent, kind, detail, run),
        )
    else:  # a time of a row written with it (_open_gate)
        db.execute(
            "INSERT INTO events (session, agent, kind, detail, run, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session, agent, kind, detail, run, at),
        )
```

  In `_open_gate`, after the INSERT: `at = db.execute("SELECT created_at FROM gates WHERE
  id = ?", (gate.id,)).fetchone()[0]`, then `_add_event(..., gate.run, at)` with a
  comment: `the gate's own time: the chat shows an event before a gate of the same time`.
- [ ] **Step 4: Test fix** in `test_the_humans_answer_is_the_runs_move_at_the_bottom_with_its_comment`:

```python
    last = feed.locator(":scope > .run-group").last
    expect(last.locator("li.run-gate_open")).to_have_count(0)  # the gate stays above
    you = page.locator(".run-actor", has_text=re.compile(r"^You$"))
    move = last.locator("li.run-flow").filter(has=you)
```

  (Check the class names against `web/src/Chat.tsx`: `run-flow` for a flow event's line,
  `run-gate_open` for the gate-opened line. Use whatever the code names them.)
- [ ] **Step 5: Run** `uv run pytest -n0 tests/test_state.py -k share_one_time` and
  `uv run pytest -m ui -n0 tests/ui/test_gates.py`. Expected: PASS.
- [ ] **Step 6: Commit** `A gate and the event that opened it share one time (LAD-44)`.

### Task 5: The fake agent ends its session once, whatever ends its terminal (D5)

**Files:**
- Modify: `tests/integration/fake_agent.py` (`read_input` ~253, `hung_up` ~422, the end of
  `main` ~494, the module docstring on hang-up)
- Test: `tests/integration/test_agent_liveness.py` (~211-232)

- [ ] **Step 1: Reproduce.** Locally, add `time.sleep(0.3)` at the top of `hung_up`. Run
  `uv run pytest -m integration -n0 "tests/integration/test_agent_liveness.py::test_stopping_a_session_tells_no_one_and_counts_what_it_dropped"`
  and expect the 30 s timeout on the supervisor's hook. Quote it and remove the sleep.
- [ ] **Step 2: Implement.**

```python
ended = False  # the session-end hook has run (end_session)


def end_session(why: str) -> None:
    """End the session once, whatever came first: SIGHUP, the end of input, or an error
    reading the terminal (a killed pty can end the read before the signal is handled)."""
    global ended
    if ended:
        return
    ended = True
    if os.environ.get("FAKE_AGENT_HANGUP_HOOK") == "1":
        report(hung_up=hook("session_end"), ended_by=why)
    else:
        hook("session_end")


def hung_up(*_) -> None:
    """Its tmux window was killed: like Claude Code, it ends its session with the hook."""
    end_session("sighup")
    os._exit(0)
```

  In `read_input`: wrap `sys.stdin.readline()` with `try: ... except OSError: return text
  or None` (the terminal is gone: the end of input). At the end of `main`, replace
  `hook("session_end")` with `end_session("eof")`.

  Check first what `hook("session_end")` returns and what the tests read from `hung_up`.
  Keep the value they read.
- [ ] **Step 3: Test.** In `test_stopping_a_session_tells_no_one_and_counts_what_it_dropped`
  and `test_finishing_a_worker_tells_no_one_it_stopped`, after the waits, add an assertion
  that no `ended` event of either agent comes after the `session_stop` (or the
  `finished`) event. Read the events with `state.list_events(SESSION)` as the file does.
- [ ] **Step 4: Run** both tests 20 times each: `for i in $(seq 20); do uv run pytest -m
  integration -n0 <nodeid> > /tmp/lad44-live-$i.log 2>&1 || echo FAIL $i; done`, then
  the whole file once. Expected: no FAIL.
- [ ] **Step 5: Commit** `The fake agent ends its session once, whatever ends its terminal (LAD-44)`.

### Task 6: The terminal socket test waits for the written input (D6)

**Files:**
- Modify: `tests/test_terminal_socket.py` (`FakeTerminal` ~24-45, the test ~197-206)

- [ ] **Step 1: Reproduce.** Locally, add `time.sleep(0.2)` at the top of
  `FakeTerminal.write`. The test fails with `[b'ls\r']`. Quote it.
- [ ] **Step 2: Implement.**

```python
        self.changed = threading.Condition()
    ...
    def write(self, data: bytes) -> None:
        if self.mode != terminal.CONTROL:
            raise terminal.ReadOnly("view")
        with self.changed:
            self.written.append(data)
            self.changed.notify_all()

    def resize(self, size: tuple[int, int]) -> None:
        with self.changed:
            self.size = size
            self.changed.notify_all()

    def wait(self, done, timeout: float = 5.0) -> None:
        """Wait until `done()` holds: input and output are separate tasks of the socket."""
        with self.changed:
            assert self.changed.wait_for(done, timeout), (self.written, self.size)
```

```python
def test_control_takes_input_and_resize(client, session, terms):
    with logged_in(client).websocket_connect(URL + "?mode=control", headers=headers()) as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"type": "input", "data": "ls\r"}))
        ws.send_text(json.dumps({"type": "resize", "cols": 120, "rows": 40}))
        ws.send_text(json.dumps({"type": "input", "data": "é"}))
        terms[0].wait(lambda: len(terms[0].written) == 2 and terms[0].size == (120, 40))
    assert terms[0].written == [b"ls\r", "é".encode()]
    assert terms[0].size == (120, 40)
```

- [ ] **Step 3: Run** with the delay still in: PASS. Remove the delay and run 20 times:
  `uv run pytest -n0 tests/test_terminal_socket.py -k control_takes --count 20`, or a
  shell loop if pytest-repeat is not installed. Expected: PASS.
- [ ] **Step 4: Commit** `The terminal socket test waits for the input it checks (LAD-44)`.

### Task 7: The Launch and ArtifactTab vitest tests wait for the state they check (D6)

**Files:**
- Modify: `web/src/Launch.test.tsx` (`ready()` ~181-186; the sync checks at 216, 402,
  413, 510, 643), `web/src/ArtifactTab.test.tsx` (`afterEach` ~15; title checks)

- [ ] **Step 1: Reproduce.** Locally, wrap the body of Launch's provider effect
  (`Launch.tsx` ~290-296, `setProvider(...)`) in `setTimeout(() => ..., 50)`, and
  ArtifactTab's title effect (`ArtifactTab.tsx` ~40-45) likewise. Run `cd web && npx
  vitest run src/Launch.test.tsx src/ArtifactTab.test.tsx`. Expect line 216 and the image
  test to fail. Quote both and remove the delays.
- [ ] **Step 2: Implement.**

```ts
async function ready(path: string, more: Partial<FolderInfo> = {}) {
  folders[path] = folder(path, { provider: { name: "claude", reason: "only_installed" }, ...more });
  type(path);
  await screen.findByText(/✓ git repository · branch main/);
  await waitFor(() => expect(providerSelect().disabled).toBe(false));
  // The suggested provider is set in an effect after the folder's render: Start needs it.
  const suggested = folders[path].provider?.name;
  if (suggested) await waitFor(() => expect(providerSelect().value).toBe(suggested));
}
```

  Each `expect(startButton().disabled).toBe(false);` that follows a folder check becomes
  `await waitFor(() => expect(startButton().disabled).toBe(false));`.

  ArtifactTab:

```ts
afterEach(() => {
  cleanup();
  document.title = ""; // a tab's title is set in an effect: no test reads another's
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});
```

  Each `expect(document.title).toBe(X)` becomes `await waitFor(() =>
  expect(document.title).toBe(X))`, with `waitFor` imported.
- [ ] **Step 3: Run** with the delays in: PASS. Without them: `npx vitest run
  src/Launch.test.tsx src/ArtifactTab.test.tsx --repeat 20` (or a loop if the installed
  vitest lacks `--repeat`). Then `make web`. Expected: PASS.
- [ ] **Step 4: Commit** `The Launch and artifact tab tests wait for the state they check (LAD-44)`.

### Task 8: The chat's question test waits for the lead's request before it recommends (D6)

**Files:**
- Modify: `tests/ui/test_chat.py` (~95-115)

- [ ] **Step 1: Reproduce.** Locally, add `time.sleep(0.5)` in `runtime.ask_human` between
  `state.add_question` and the recommendation request. The test fails with "The
  supervisor gave no recommendation". Quote it and remove the sleep.
- [ ] **Step 2: Implement**, after the question is found:

```python
    # LADO asks the supervisor for its recommendation in a transaction after the
    # question's; recommending earlier, the request would set it back to asked and the
    # supervisor's turn on it mark it missing. So first that turn must have ended.
    agent_helpers.wait_for(
        lambda: state.get_message(question.id).recommendation_state == state.REC_MISSING,
        "the question's request handled",
        session,
    )
    queued = [
        m.summary
        for m in state.list_messages(session)
        if m.recipient == "supervisor" and m.state in (state.PENDING, state.SENT)
    ]
    assert queued == []
```

  (Use the getter the module has for one message. If there is none, find it in
  `state.list_messages`.)
- [ ] **Step 3: Run** `uv run pytest -m ui -n0 tests/ui/test_chat.py -k recommendation_open_and_closed`
  20 times in a loop, each exit status read from its log. Expected: PASS.
- [ ] **Step 4: Commit** `The chat's question test waits for the lead's request before it recommends (LAD-44)`.

### Task 9: The smoke test waits for the supervisor's request at the endpoint (D6)

**Files:**
- Modify: `tests/smoke/test_smoke.py:85-86`

- [ ] **Step 1: Implement.**

```python
    # Codex posts its first request after its prompt-submit hook confirmed the input, so
    # the confirmation can come first; for the others the turn_error above came after it.
    wait_for(lambda: fake_endpoint.requests, "the supervisor's turn at the endpoint", 120)
    asked = len(fake_endpoint.requests)
```

- [ ] **Step 2: Check** that it collects: `uv run pytest -m smoke --collect-only
  tests/smoke/test_smoke.py`. Locally it runs only with the CLIs installed; CI proves it
  (Task 11).
- [ ] **Step 3: Commit** `The smoke test waits for the supervisor's request at the endpoint (LAD-44)`.

### Task 10: Records

**Files:**
- Modify: `BACKLOG.md`, `CHANGELOG.md`, `AGENTS.md`

- [ ] **Step 1: BACKLOG.md.** Remove these entries, each fixed here (the commit message
  names them): "Flaky terminal socket test: input checked before it is written"; "Flaky
  vitest: an image's artifact tab keeps another test's page title"; "Flaky in WSL: a
  message of the turn-end output delivered `typed`"; "Flaky in CI: the gates UI test's
  scroll"; "Flaky in CI: the gates UI test of a recommendation that disagrees" (fixed by
  LAD-38); "Flaky in CI: `test_stopping_a_session_tells_no_one…` on 3.10"; "Flaky: integration test of a
  finished worker waits for a hook that never comes" (the same cause: an idle w1 reading
  stdin); "Flaky in CI: a slow turn's hook-output message was
  typed"; "Flaky in CI: the Codex smoke on macOS reached no model API"; and the stale
  "Flaky: UI e2e test of a question card under load". Add new entries in the file's
  template (tier, `Size:`, `Why here:`, `Found: 2026-10-14, feature/lad-44-flake-races`):
  P2 "The chat does not stay at the bottom when its last entry grows in place";
  P2 "Codex clones its plugins repository at every start" (~300 MB in a smoke's
  evidence, a slower start; a config key to switch it off needs a check by hand).
- [ ] **Step 2: CHANGELOG.md**, under `## 0.37.1 (unreleased)`:
  - `lado server stop`, `lado update` and `lado uninstall` wait until the old UI server's
    process has ended; a server that has stopped no longer makes `~/.lado` again after
    `lado uninstall`.
  - Messages queued during an agent's turn reach it in its turn-end hook's output
    whenever its CLI takes that output; a race sometimes pasted them into its window.
  - A gate in a session's chat always shows after the run's move that opened it.
- [ ] **Step 3: AGENTS.md** Layout, `server/run.py`: "the background start and stop (a
  stop returns once the server's process has ended)". `telemetry.py`'s list of commands
  that do not kick: add `server` (it kicks in `housekeeping`). Task 3 has already edited
  the "How agents talk" sentence.
- [ ] **Step 4: Commit** `Records of the flake races: BACKLOG, CHANGELOG, AGENTS.md (LAD-44)`.

### Task 11: Acceptance runs (AC-6, AC-7, AC-8)

- [ ] **Step 1:** `make lint`, `make test`, each changed integration file with
  `-m integration -n auto <files>`, each changed UI file with `-m ui <files>`, and
  `make web`. All green, each exit status read from its log.
- [ ] **Step 2:** The local loops of the tasks above are done (20 runs each) and their
  counts are in the build report.
- [ ] **Step 3:** Push, open the pull request, then run 4 reruns of the whole CI
  workflow on the last commit: `gh run rerun <id>`, waiting for each with `gh run watch
  <id> --exit-status`. All 5 attempts must be green with no failed job. Then rerun the
  job `smoke macos-latest codex` alone until it has 20 green runs (`gh run rerun <id>
  --job <job-id>`). The build report lists the run and attempt ids. A red attempt is a
  finding: find its cause and do not rerun past it.
