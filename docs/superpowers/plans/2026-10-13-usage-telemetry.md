# Usage statistics and LADO's own errors: implementation plan

**Goal:** one bounded journal of LADO's unexpected exceptions for every process, and,
after the human's yes, anonymous daily statistics and LADO's errors sent to PostHog
Cloud EU, with `lado telemetry`, a banner and a Settings section (LAD-32).

**Architecture:** a new standard-library module `src/lado/telemetry.py` holds the
consent, the journal, the outbox, the scrubbing, the daily report (derived from
`lado.db` when it is built) and the sender. Five capture points call
`telemetry.record`. A detached `lado telemetry send`, started by `telemetry.kick` from
the CLI, the session loop and the UI server, posts one batch under a flock. The API and
the UI read `telemetry.state()`.

**Tech stack:** Python 3.10+ standard library (`urllib.request`, `fcntl`, `json`,
`hashlib`, `traceback`), FastAPI/pydantic for the API, React + TypeScript (vitest),
pytest (unit, integration with the fake agent, UI with Playwright).

**Spec:** `openspec/changes/usage-telemetry/` (proposal, deltas `error-journal` and
`usage-telemetry`, `design.md` D1–D14). **Design doc:**
`docs/superpowers/specs/2026-10-13-usage-telemetry-design.md`. **Mockup:** run artifact
`task/lad-32/mockup-consent.html` (1A, 2, 3, 4; not 1B).

Each task: tests first, then the code, then the named test run, then a commit (message in
the repository's style, `(LAD-32)` at the end).

## Global constraints

- Standard library only in `telemetry.py`; nothing heavy at its top (every hook imports
  it). `lado.__version__` is read inside functions.
- Files (D2): `LADO_HOME/errors.jsonl` (+ `.1`), `LADO_HOME/telemetry/{consent.json,id,
  sent.json,dropped,send.lock,outbox/}`; journal, consent and id are mode 600.
- Constants: `JOURNAL_MAX = 1 << 20`, `OUTBOX_MAX = 200`, `OUTBOX_MAX_AGE = 30 * 86400`, `DROPPED_MAX = 1_000_000`, `REPORT_MAX_WINDOW = 30 * 86400`, `SEND_TIMEOUT = 2.0` (as `update.CHECK_TIMEOUT`), `SEND_DEADLINE = 30`,
  `RETRY_AFTER = 15 * 60`, `REPORT_EVERY = 24 * 3600`, `KICK_EVERY = 10 * 60`,
  `FIELDS_VERSION = 1`, `ENDPOINT = "https://eu.i.posthog.com/batch/"`,
  `PROJECT_TOKEN = ""` (the human sets it before the release), `TEST_TOKEN = "phc_test"`.
- Environment: off when `DO_NOT_TRACK` is set to anything but `""` or `"0"`, or
  `LADO_TELEMETRY == "0"`; `LADO_TELEMETRY_URL` replaces `ENDPOINT` and, with an empty
  `PROJECT_TOKEN`, uses `TEST_TOKEN`. `tests/conftest.py` sets `LADO_TELEMETRY=0`.
- `where` values: `cli:<command>` (argparse's command, with the subcommand for
  `kits`/`marketplaces`/`artifacts`/`telemetry`, e.g. `cli:kits add`),
  `hook:<neutral event name, else native>`, `mcp:<tool>`, `loop`, `server:<route path
  template>`.
- Texts, exactly:
  - CLI question: the five lines of the design doc, then `Send them? [y/N] `. With new
    fields, the first line is `LADO now also sends: <field>, <field>.`, followed by the
    same lines.
  - CLI answers: `statistics: on (lado telemetry off to stop)`, `statistics: off`.
  - `status` lines:
    - `statistics: on (chosen <YYYY-MM-DD>)`
    - `statistics: off`
    - `statistics: not chosen (lado telemetry on|off)`
    - `statistics: off: <VAR>=<value> is set (your choice: <on|off|not chosen>)`
    - `statistics: off: this LADO has no statistics endpoint`
    - `last sent: <YYYY-MM-DD HH:MM> · waiting: <n> report[s], <k> error[s]`
    - `last try failed: <reason>`
  - Refusal inside an agent: `lado telemetry on|off is for the human, not an agent`.
- UI texts:
  - the banner of mockup 1A;
  - Settings section `Usage statistics`, legend `Send anonymous statistics and errors
    to LADO's maintainers`, segments `Send` / `Don't send`;
  - the state lines of mockup 2;
  - the panel row `Statistics` with `sending · last <time>`, `off`, `not chosen`, or
    `off: <VAR>=<value>`;
  - the report line `- Statistics: on|off|not chosen|off by <VAR>`.
- Version: part of 0.37.0 (CHANGELOG `## 0.37.0 (unreleased)`). After the models change,
  run `make web-types` and commit both generated files.

## Review focus

1. A hook that fails while `lado.db` has another schema still writes its journal line
   (the journal does not touch `lado.db`): Task 2's SchemaError-adjacent test.
2. `cli.main` re-raises after recording, so an unexpected error still prints its
   traceback and exits non-zero, and `KeyboardInterrupt` writes nothing: Task 2's CLI
   tests.
3. The question never blocks a non-interactive `lado start` (a pipe, an agent's
   `start_session` path, the UI server's start): Task 3's no-tty tests, and
   `runtime.start_session` itself never asks.
4. An exception whose text, locals or a non-LADO frame's file name hold a home path, a
   session name or a token leaves no trace of them in an event: Task 1's scrub test with
   all three.
5. An endpoint that is unreachable or hangs (refused port, 403, a server that accepts and
   never answers, a DNS lookup that hangs, a TLS error): nothing but `status` and
   Settings shows it, the sender ends within `SEND_DEADLINE`, and the queue stays bounded:
   Task 3's unreachable-endpoint tests and Task 4's integration test.
6. Two `lado telemetry send` at once, and a send that dies half way (killed after the
   post, before the removal): one sends, the other exits 0; the half-done one at worst
   sends an error group twice, never loses it: Task 3's lock and removal-order tests.

---

### Task 1: The telemetry core (consent, journal, scrubbing, outbox)

**Files:**
- Create: `src/lado/telemetry.py`
- Create: `tests/test_telemetry.py`
- Modify: `tests/conftest.py` (`os.environ["LADO_TELEMETRY"] = "0"` next to
  `LADO_NO_UPDATE_CHECK`, and a fixture `telemetry_on(monkeypatch)` that deletes
  `LADO_TELEMETRY` and `DO_NOT_TRACK`, sets `LADO_TELEMETRY_URL` to a URL of a local
  server, below, and writes the consent `on`)
- Modify: `tests/test_lazy_imports.py` (`lado.telemetry` imports no `urllib.request`,
  `lado.doctor` or `lado.update` at its top)

**Interfaces (produces):**

```python
FIELDS: dict[str, int]          # field name -> FIELDS version it came in; v1 lists all D8 fields and the error's
FIELDS_VERSION = 1

@dataclass(frozen=True)
class State:
    choice: str | None            # "on" | "off" | None, as stored
    chosen_at: str | None
    fields_ok: bool               # stored fields >= FIELDS_VERSION
    off_by: str | None            # "DO_NOT_TRACK=1" | "LADO_TELEMETRY=0" | None
    endpoint: bool
    @property
    def on(self) -> bool: ...     # choice == "on" and fields_ok and not off_by and endpoint
    @property
    def ask(self) -> bool: ...    # (choice is None or (choice == "on" and not fields_ok)) and not off_by and endpoint
    @property
    def new_fields(self) -> list[str]: ...

def state(environ: Mapping[str, str] | None = None) -> State
def choose(choice: str) -> None            # writes consent.json {"choice","fields":FIELDS_VERSION,"at"}; "off" also clears()
def clear() -> None                        # removes outbox/* and dropped
def bounded_append(path: Path, text: str, limit: int = JOURNAL_MAX, mode: int = 0o644) -> None   # never raises
def record(where: str, exc: BaseException, provider: str | None = None,
           session: str | None = None, agent: str | None = None) -> None                     # never raises
def scrub(where: str, exc: BaseException, provider: str | None) -> dict   # the error event's properties (D5)
def queued() -> list[dict]                 # the outbox's events, oldest first
def dropped() -> int
```

- [ ] **Step 1: Write the failing tests** in `tests/test_telemetry.py`:
  - `test_state_not_chosen_asks` (with an endpoint) and `test_state_without_endpoint_never_asks`;
  - `test_do_not_track_switches_off` (parametrize `"1"`, `"true"`, `"yes"` → off; `""`,
    `"0"` → not off) and `test_lado_telemetry_0_switches_off`;
  - `test_old_fields_count_as_not_chosen` (consent `{"choice":"on","fields":0}` with
    `FIELDS = {"a": 0, "b": 1}`, monkeypatched, gives `ask` and `new_fields == ["b"]`);
  - `test_choose_off_clears_outbox`;
  - `test_record_writes_journal_line` (keys `at, lado, where, type, message, traceback,
    session, agent`; mode 600);
  - `test_record_queues_only_when_on`;
  - `test_record_never_raises` (`LADO_HOME` a file, not a folder);
  - `test_bounded_append_rotates` (a 1.1 MiB file and an old `.1` → the old `.1` gone,
    the big file is `.1`, the new file holds only the line);
  - `test_outbox_bound_counts_drops` (`OUTBOX_MAX` monkeypatched to 2, three records →
    2 files, `dropped() == 1`; and with `DROPPED_MAX` monkeypatched to 2, the `dropped` file
    never passes 2 bytes);
  - `test_scrub_leaves_no_path_name_or_token`:

    ```python
    def test_scrub_leaves_no_path_name_or_token(tmp_path):
        secret, path, name = "sk-live-123", "/Users/ann/work/app", "my-session"
        def fail(token=secret, where=path):
            raise OSError(f"cannot open {path} for {name}")
        try:
            fail()
        except OSError as exc:
            event = telemetry.scrub("hook:turn_end", exc, "claude")
        text = json.dumps(event)
        for leak in (secret, path, name, "ann"):
            assert leak not in text
        assert event["type"] == "OSError"
        assert all(f.startswith("lado/") or f == "<external>" for f in event["stack"])
    ```

    The test file is outside `lado/`, so its frames are `<external>`. Add a second case
    that raises from inside a LADO function (e.g. `state.home` with a monkeypatched
    `Path.mkdir`) and checks that a `lado/...` frame is present;
  - `test_fingerprint_ignores_line_numbers`.
- [ ] **Step 2:** `uv run pytest tests/test_telemetry.py -n0 -x`: FAIL (no module).
- [ ] **Step 3: Implement** `telemetry.py` per D1–D6.
  - The package folder is `Path(__file__).parent`. A frame is LADO's when its resolved
    file is under it; render it `lado/<relative posix path>:<co_name>:<lineno>`.
  - Collapse each run of other frames into one `<external>`.
  - `type` is `f"{cls.__module__}.{cls.__qualname__}"` without a leading `builtins.`.
  - `chain` follows `__cause__` or else `__context__`, at most 3.
  - The fingerprint is `sha256("\n".join([type, *lado file:function]))[:16]`.
  - The outbox file name is `f"{time.time_ns()}-{os.getpid()}-{secrets.token_hex(4)}.json"`,
    written to a `.tmp` file and renamed.
  - The journal and `dropped` are written with `os.open(..., O_APPEND|O_CREAT|O_WRONLY,
    mode)`, one `os.write` per line or byte.
- [ ] **Step 4:** `uv run pytest tests/test_telemetry.py tests/test_lazy_imports.py -n auto`:
  PASS.
- [ ] **Step 5: Commit** `LADO keeps one journal of its unexpected errors and queues them
  only with the human's yes (LAD-32)`.

### Task 2: The capture points and the log bounds

**Files:**
- Modify: `src/lado/cli.py` (`main`: after the known-errors `except`, add `except
  Exception: telemetry.record(f"cli:{_where(args)}", exc); raise`)
- Modify: `src/lado/hooks.py`
  - `main`'s `except Exception` → also `telemetry.record(f"hook:{neutral or event}",
    exc, provider=current.provider, session=session, agent=agent)`, guarding for
    `current`/`neutral` being unset;
  - `_log` → `telemetry.bounded_append(state.home() / "hooks.log", ...)`.
- Modify: `src/lado/mcp_server.py` (`_reasons(tool: str)`: after the known errors,
  `except Exception as exc: telemetry.record(f"mcp:{tool}", exc, session=..., agent=...);
  raise`; every `with _reasons():` names its tool)
- Modify: `src/lado/loop.py`
  - `RepeatedErrors.failed` records once per new error, given `where="loop"` and the
    session by its owner; the server's feed passes `where="server:feed"`;
  - `log` uses `bounded_append`.
- Modify: `src/lado/server/app.py` (`@app.exception_handler(Exception)` records
  `server:<request.scope["route"].path>` and returns the 500 Starlette would)
- Modify: `src/lado/server/run.py` (before opening `server.log` for a new server: rename
  it to `server.log.1` when it is over `telemetry.JOURNAL_MAX`)
- Test: `tests/test_cli.py`, `tests/test_runtime.py` (the hook's tests),
  `tests/test_mcp_server.py`, `tests/test_loop.py`, `tests/test_server_system.py` (or the
  server test file holding the app's handlers), `tests/test_telemetry.py`

**Interfaces:** consumes `telemetry.record`, `telemetry.bounded_append`,
`telemetry.JOURNAL_MAX`.

- [ ] **Step 1: Write the failing tests**:
  - `test_unexpected_cli_error_is_journaled_and_reraised` (monkeypatch `cmd_ls` to raise
    `TypeError`; `pytest.raises(TypeError)`; one line `where == "cli:ls"`);
  - `test_cli_refusal_is_not_journaled` (a `LadoError`);
  - `test_keyboard_interrupt_is_not_journaled`;
  - `test_failing_hook_is_journaled` (monkeypatch `hooks.handle` to raise; `main`
    returns 0; the journal line has `hook:turn_end`, the agent and the provider;
    `hooks.log` has its traceback as before);
  - `test_schema_error_in_hook_is_not_journaled`;
  - `test_mcp_unexpected_error_is_journaled` (a tool whose runtime call raises
    `RuntimeError`; the tool's error as before; one line `mcp:send_message`);
  - `test_loop_journals_a_repeated_error_once`;
  - `test_server_500_is_journaled` (test client with `raise_server_exceptions=False`, a
    route monkeypatched to raise; `where == "server:/api/sessions"`);
  - `test_server_log_rotates_at_start`;
  - `test_server_log_copy_truncated_while_running` (a log over the bound opened with
    `O_APPEND` by the test as the server's stdout is; after the check, `.1` has the old
    content, the log is empty, and a write through the open descriptor lands at offset 0's
    new end).
- [ ] **Step 2:** run them: FAIL.
- [ ] **Step 3: Implement.** `_where(args)` is `args.command` plus the subcommand's
  `dest` value when the command has subcommands. Never the arguments.
- [ ] **Step 4:** `uv run pytest tests/test_cli.py tests/test_runtime.py
  tests/test_mcp_server.py tests/test_loop.py tests/test_server_system.py
  tests/test_telemetry.py -n auto`: PASS.
- [ ] **Step 5: Integration test** `tests/integration/test_telemetry.py::test_failing_hook_journals_and_queues`
  (marker `integration`):
  - start a session with the fake agent under the `telemetry_on` fixture;
  - run `lado hook <native turn-end event> <session> <agent> <instance>` as a subprocess
    with a malformed payload, which the fake provider's `parse_event` rejects;
  - assert exit 0, one `errors.jsonl` line `hook:...`, and one outbox file whose JSON
    has no session or agent name.

  Run with `uv run pytest -m integration -n auto tests/integration/test_telemetry.py`.
  If the fake provider accepts any payload, give the test a `parse_event` failure through
  the fake's existing switches, never a new production flag.
- [ ] **Step 6: Commit** `Every LADO process journals its unexpected errors; its logs stay
  under 1 MiB (LAD-32)`.

### Task 3: The daily report, the sender and `lado telemetry`

**Files:**
- Modify: `src/lado/telemetry.py` (`report`, `batch`, `send`, `kick`, `ask_if_needed`,
  `_post`)
- Modify: `src/lado/state.py`
  - `spawned_provider(detail) -> str | None` next to where `spawned`'s detail is
    written, and a test that the writer and the parser agree;
  - `usage_counts(since: str) -> dict`: one read-only query per count, by `created_at`.
- Modify: `src/lado/cli.py`
  - the `telemetry` command with `status` (default), `on`, `off`, `show`, and a hidden
    `send`; none of them migrates (beside `doctor` in `main`);
  - `telemetry.ask_if_needed()` first in `cmd_start` and `cmd_ui`;
  - `telemetry.kick()` in `main`'s `finally` for every command but `hook`, `mcp`, `loop`
    and `telemetry send`.
- Create: `tests/test_cli_telemetry.py`
- Modify: `tests/test_telemetry.py`, `tests/conftest.py` (a fixture `telemetry_endpoint`:
  `http.server.ThreadingHTTPServer` on 127.0.0.1:0 in a thread that records each
  request's JSON body and answers a status set by the test, 200 by default; it sets
  `LADO_TELEMETRY_URL`)

**Interfaces (produces):**

```python
def report(now: datetime | None = None) -> dict | None     # the lado_daily event, None when not due
def batch(now: datetime | None = None) -> list[dict]       # report (if due) + one $exception per fingerprint
def send() -> int                                          # `lado telemetry send`: lock, batch, _post, bookkeeping; always 0
def kick() -> None                                         # cheap; maybe starts a detached `lado telemetry send`
def ask_if_needed(stdin=sys.stdin, stderr=sys.stderr) -> None
def status_lines(s: State | None = None) -> list[str]
def last_sent() -> tuple[str | None, str | None]           # (time of the last good send, last failure reason)
```

- [ ] **Step 1: Write the failing tests**:
  - `test_report_counts_window` (make a db with sessions, `spawned` events of two
    providers, a `flow_start`, a `gate_open`, a `turn_error`, some inside and some
    outside the window; check each count and `agents == {"claude": 2, "codex": 1}`);
  - `test_report_without_db` (`db: "unreadable"`, no counts);
  - `test_report_not_due_within_24h`;
  - `test_batch_groups_by_fingerprint` (3 records of one kind and 1 of another → 2
    `$exception` events, counts 3 and 1);
  - `test_exception_event_shape` (D10: `$exception_list[0].stacktrace.type == "raw"`,
    frames `platform == "custom"`, `lang == "python"`, `in_app`; properties
    `$process_person_profile is False`, `$geoip_disable is True`; no `value` beyond
    `"<type> in <where>"`);
  - `test_send_posts_and_empties` (`telemetry_endpoint`; the body's `api_key ==
    TEST_TOKEN`; the outbox is empty; `sent.json` has the time);
  - `test_send_failure_keeps_everything` (endpoint answers 500; then a second `send`
    within `RETRY_AFTER` posts nothing; `last_sent()[1]` names the failure);
  - `test_send_removes_only_what_it_sent` (an error recorded during the post stays);
  - `test_second_sender_exits` (hold the flock in the test; `send()` returns 0 and posts
    nothing);
  - `test_send_off_or_env_off_posts_nothing`;
  - `test_unreachable_endpoint_is_silent` (parametrize: a closed port; the endpoint
    answering 403; a socket server that accepts and never answers; `socket.getaddrinfo`
    monkeypatched to sleep past the deadline, with `SEND_DEADLINE` monkeypatched to 1;
    an `ssl.SSLError` raised by a monkeypatched opener): `send()` returns 0 within
    `SEND_DEADLINE` + 1 s, prints nothing to stdout or stderr (`capsys`), keeps the
    outbox, writes `sent.json`'s `error`, releases the lock;
  - `test_old_outbox_files_are_dropped_and_counted` (a file 31 days old is removed
    before the batch and `dropped()` grows by one);
  - `test_report_window_at_most_30_days` (`sent.json`'s last report 45 days ago → `since`
    is 30 days back);
  - `test_long_outage_stays_bounded` (`OUTBOX_MAX` 3, ten records and five failed tries
    → 3 files, `dropped() == 7`, `batch()` holds one `lado_daily` whose `since` is the
    last good report);
  - `test_sender_crash_is_journaled_not_queued` (a bug inside `batch`: one
    `errors.jsonl` line, no outbox file);
  - `test_kick_starts_nothing_when_nothing_due` (monkeypatch the spawn);
  - `test_kick_spawns_detached_when_due` (asserts the argv ends `telemetry send` and
    `start_new_session=True`).
  - In `tests/test_cli_telemetry.py`:
    - `test_status_lines` for each state;
    - `test_on_off_refused_inside_agent`;
    - `test_show_prints_the_batch`, equal to `batch()` without `api_key`;
    - `test_start_asks_on_tty_and_stores` (fake tty streams answering `y\n`, `\n`, `n\n`;
      EOF stores nothing);
    - `test_start_does_not_ask_without_tty`, `test_start_does_not_ask_inside_agent`,
      `test_ui_asks_too`;
    - `test_question_names_new_fields`;
    - `test_telemetry_commands_do_not_migrate`.
- [ ] **Step 2:** run them: FAIL.
- [ ] **Step 3: Implement** per D7–D11.
  - The sender writes `sent.json` `{"report_at", "sent_at", "tried_at", "error"}`,
    first `tried_at`, then, after a 2xx, `report_at`/`sent_at`.
  - It removes the outbox files it read only after a 2xx.
  - `kick` spawns `interpreter.run_module("lado.cli", "telemetry", "send")` with
    `start_new_session=True`, stdin, stdout and stderr `DEVNULL`, `close_fds=True`, as
    `self_update.start_detached` does.
  - `installer` is `update.installer()` → its `kind`, else `dev` when lado's
    distribution has a `direct_url.json` with `dir_info`, else `other`.
  - `providers` comes from `doctor.provider_status` for the installed ones (import
    inside the function).
  - `kits` names the built-in kits and the installed ones whose `marketplace ==
    "official"`; the others are counted.
- [ ] **Step 4:** `uv run pytest tests/test_telemetry.py tests/test_cli_telemetry.py
  tests/test_state.py -n auto`: PASS.
- [ ] **Step 5: Commit** `lado telemetry and the question of lado start and lado ui; a
  detached sender posts the daily report and LADO's errors (LAD-32)`.

### Task 4: The loop and the server kick the sender

**Files:**
- Modify: `src/lado/loop.py` (`telemetry.kick()` when `KICK_EVERY` has passed since the
  loop's last kick, after the pass, never inside the `try` that decides the loop's end)
- Modify: `src/lado/server/app.py` or `server/run.py` (in the lifespan: a daemon thread
  that calls `kick()` at the start and every `KICK_EVERY`; stopped by the shutdown)
- Test: `tests/test_loop.py`, `tests/integration/test_telemetry.py`

- [ ] **Step 1: Write the failing tests**:
  - `test_loop_kicks_every_interval` (unit, `KICK_EVERY` monkeypatched, `kick`
    recorded);
  - integration `test_loop_sends_to_local_endpoint`: with `telemetry_on` and
    `telemetry_endpoint` (no new environment variable for the interval: the loop's own
    kick is covered by the unit test), start a session, record an error with
    `telemetry.record("loop", ...)` from the test process, and run `lado telemetry send`
    as a subprocess. Assert the endpoint got one batch with a `$exception` and a
    `lado_daily`, and that the outbox is empty.
  - integration `test_start_with_unreachable_endpoint`: with `telemetry_on` and
    `LADO_TELEMETRY_URL` at a closed local port, `lado start` of a repo exits 0 and its
    stdout and stderr hold no word of the endpoint; `lado telemetry send` run after it
    exits 0 and `lado telemetry status` shows `last try failed:`.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** `uv run pytest tests/test_loop.py
  -n auto` and `uv run pytest -m integration -n auto tests/integration/test_telemetry.py`:
  PASS.
- [ ] **Step 5: Commit** `The session loop and the UI server start the statistics sender
  when something is due (LAD-32)`.

### Task 5: The API, SystemInfo and the report line

**Files:**
- Modify: `src/lado/server/models.py`
  - `TelemetryInfo {choice: str | None, on: bool, ask: bool, off_by: str | None,
    endpoint: bool, last_sent: str | None, last_error: str | None, waiting: int,
    new_fields: list[str]}`;
  - `TelemetryChoice {choice: Literal["on", "off"]}`;
  - `TelemetryPreview {report: dict | None, errors: list[dict]}`;
  - `SystemInfo.telemetry: str`.
- Modify: `src/lado/server/app.py` (`GET /api/telemetry`, `POST /api/telemetry` under
  `Guard.changes`, 409 `Refused` when `off_by`; `GET /api/telemetry/preview`)
- Modify: `src/lado/doctor.py` (`System.telemetry`, the report's `- Statistics: ...`
  line after `- Update:`)
- Modify: `web/openapi.json`, `web/src/api.gen.ts` (`make web-types`)
- Test: `tests/test_server_system.py`, `tests/test_doctor.py`

- [ ] **Step 1: Write the failing tests**:
  - `test_get_telemetry_states`;
  - `test_post_telemetry_on_off` (and `off` empties the outbox);
  - `test_post_refused_when_env_off`;
  - `test_post_needs_guard` (no token or a bad Origin → refused);
  - `test_preview_equals_batch`;
  - `test_system_info_has_telemetry`;
  - `test_report_has_statistics_line` (each state).
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** `uv run pytest
  tests/test_server_system.py tests/test_doctor.py -n auto`, then `make web-types` and
  `make web`: PASS.
- [ ] **Step 5: Commit** `API: the statistics choice, its preview and the System panel's
  line (LAD-32)`.

### Task 6: The web UI

**Files:**
- Create: `web/src/Telemetry.tsx`
  - `StatisticsBanner`: rendered in `Shell` after `<UpdateStatus />`; class
    `update-banner stats-banner`;
  - `StatisticsSetting`: the last section of `Settings`;
  - `statisticsLine(info)`: the panel row's text.
- Create: `web/src/Telemetry.test.tsx`
- Modify: `web/src/Shell.tsx`, `web/src/Settings.tsx`, `web/src/SystemPanel.tsx` (the
  row `Statistics` after `git`: a `Link` to `/settings`; and the `Copy system info` text
  is the server's report, unchanged), `web/src/api.ts`, `web/src/styles.css`
  (`.stats-banner`, `.stats-buttons`, `.stats-what` as in the mockup)
- Create: `tests/ui/test_telemetry.py` (marker `ui`, screenshots with `shot`)
- Modify: `tests/ui/test_system_panel.py` (the row)

- [ ] **Step 1: Write the failing vitest tests**:
  - `the banner shows while ask is true and goes after Send statistics` (POSTs `{choice:
    "on"}`);
  - `Don't send posts off`;
  - `What is sent loads the preview once`;
  - `no banner when ask is false`;
  - `Settings shows Send checked and the last-sent line`;
  - `Settings: not chosen yet`;
  - `Settings: disabled with the variable when off_by`;
  - `the panel's row texts and link`.
- [ ] **Step 2:** `make web`: FAIL. **Step 3:** implement to mockup 1A, 2, 3 (texts in
  Global constraints). **Step 4:** `make web`: PASS.
- [ ] **Step 5: UI e2e** `tests/ui/test_telemetry.py`:
  - a server under `telemetry_on` minus the stored consent, so `ask` is true;
  - the banner shows (screenshot), What is sent opens (screenshot), Send statistics →
    the banner is gone and Settings shows Send (screenshot);
  - a second test with `DO_NOT_TRACK=1` in the server's environment shows the disabled
    section (screenshot).

  Run with `uv run pytest -m ui tests/ui/test_telemetry.py tests/ui/test_system_panel.py`.
- [ ] **Step 6: Commit** `The UI asks once about statistics and shows the choice in
  Settings and the System panel (LAD-32)`.

### Task 7: Docs

**Files:**
- Create: `docs/telemetry.md`:
  - what is sent, with each field of `FIELDS` in a table `| field | since | what |`;
  - what is never sent;
  - where it goes (PostHog Cloud EU, no person profiles, no GeoIP, client IP discarded
    in the project);
  - how often;
  - how to see it (`lado telemetry show`, What is sent);
  - how to switch it off (Settings, `lado telemetry off`, `DO_NOT_TRACK=1`,
    `LADO_TELEMETRY=0`);
  - the local journal;
  - that a forgotten session's day is missing from the counts.
- Modify: `tests/test_telemetry.py` (`test_docs_list_every_field`: parse the table's
  first column and compare with `FIELDS`)
- Modify:
  - `AGENTS.md`:
    - Layout: `telemetry.py`;
    - the logs' bound;
    - How agents talk: the capture points;
    - the tests' `LADO_TELEMETRY=0`, beside `LADO_NO_UPDATE_CHECK`;
    - the CLI section: `lado telemetry`.
  - `docs/design/ui.md`:
    - a new section `### Usage statistics (decided 2026-10-13, LAD-32)` with the banner,
      the Settings section and the panel row, the API, and the mockup's name;
    - Settings' list gets the section.
  - `README.md`: one paragraph and a link to `docs/telemetry.md`.
  - `CHANGELOG.md` under `## 0.37.0 (unreleased)`:
    - LADO asks once whether to send anonymous statistics and its errors (Settings,
      `lado telemetry`, `DO_NOT_TRACK`);
    - `errors.jsonl`; logs bounded;
    - API: `/api/telemetry`, `SystemInfo.telemetry`.
- [ ] **Step 1:** write the docs test: FAIL. **Step 2:** write the docs. **Step 3:**
  `uv run pytest tests/test_telemetry.py -n auto -k docs`: PASS.
- [ ] **Step 4: Commit** `docs/telemetry.md says what LADO sends and how to switch it off
  (LAD-32)`.

### Task 8: Regression run

- [ ] `make lint`
- [ ] `make test` (report the counts)
- [ ] `uv run pytest -m integration -n auto tests/integration/test_telemetry.py
  tests/integration/test_session_loop.py tests/integration/test_server_process.py`
- [ ] `uv run pytest -m ui tests/ui/test_telemetry.py tests/ui/test_system_panel.py`
- [ ] `make web`
- [ ] `openspec validate usage-telemetry --strict` and `openspec validate --specs --strict`
- [ ] Each command's output goes to a log outside the tree, and its exit status is read
  (sdlc's review traps). CI runs the full `make check` and the smoke after the push.
