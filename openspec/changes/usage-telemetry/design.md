## Context

LADO runs as many short and long processes: the CLI a human runs, the agents' hooks
(`lado hook`, one process per hook, within the CLI's time limit), `lado mcp` per agent,
the session loop per session (`lado loop`) and the UI server. Each handles its own
unexpected exceptions in its own way:

| Process | Today |
|---|---|
| CLI | the known errors (`cli.main`'s except list) print `lado: <reason>`; anything else ends in Python's traceback on stderr, kept nowhere |
| hook | `hooks.main` writes the traceback to `hooks.log`, exits 0 |
| `lado mcp` | `_reasons` passes the known errors on; any other becomes the SDK's "Error executing tool", kept nowhere |
| session loop | `RepeatedErrors` writes the traceback to `loop.log` |
| UI server | uvicorn writes "Exception in ASGI application" and the traceback to `server.log` |

None of these lines carries LADO's version, and none of the logs is bounded (here
`server.log` is 381 KB). The only network LADO uses of its own is the daily update check
(`update.check`, PyPI's JSON), cached in `update-check.json`. Usage is in `lado.db`: `events`
of kind `spawned` (detail `role <r>, provider <p>`), `session_resume`, `flow_start`,
`gate_open`, `turn_error`, and `sessions.created_at`; `lado forget` deletes a session's
rows.

Root cause: no single account of LADO's own failures, and no channel to the maintainers.

## Options

1. **Local only: one error journal, plus a report the human sends by hand** (Flutter's
   crash log, `brew gist-logs`). Cost: no server, no privacy duty; but the maintainer
   learns nothing of users who do not report, and gets no usage numbers. It does not meet
   the human's goal (how many users, which versions, which errors). Its report part is
   LAD-33, kept.
2. **Opt-in counters, Go style** (`go telemetry local|on|off`): local by default, an
   upload only after `on`, a public list of counters. Cost: a small own endpoint and its
   upkeep. Honest, but almost no one opts in by themselves, so the numbers are too few for
   the human's goal.
3. **Opt-out analytics and an error tracker** (Next.js, .NET, Codex, Claude Code). Cost:
   none in the free tiers, and the most data. But it is the pattern developer communities
   pushed back on, the IP address and install ID are personal data under GDPR, and the
   SDKs add dependencies.
4. **Chosen with the human: one explicit question, then sending** (Nuxt's first-run
   question, with Go's transparency). Nothing leaves before a yes. The yes covers a
   published list of fields, `show` prints exactly what goes, and the human can say no or
   switch it off at any time. The data goes to PostHog Cloud EU over its HTTP API, with the
   standard library. Long-term cost: one module, a few hooks into the error paths, three
   endpoints and a UI section; the PostHog project (free up to 1M events a month) is the
   human's. A move to another backend touches only the sender (D10).

Held against AGENTS.md's Design principles and ROADMAP:

- **Neutral core**: nothing depends on a provider. The provider is one more property of
  an event, and every provider's hooks and `lado mcp` go through the same capture.
- **One source of truth**: the counts are derived from `lado.db` when the report is
  built (D8), never kept as a second tally. The consent lives in one file, read by the
  CLI, the API and the sender. The field list lives in `telemetry.FIELDS`, and
  `docs/telemetry.md` is checked against it by a test.
- **No silent drops**: errors over the queue's bound are counted and the count is sent
  (D6). A failed send stays queued. A switched-off LADO says why (the environment
  variable that did it).
- **Only what is used**: three commands, one setting, no levels.

Stage 7's desktop app and the later Projects run the same server and CLI, so they get
this as they are.

## Decisions

- **D1. One module, `telemetry.py`, standard library only.** It holds the consent, the
  journal, the outbox, the scrubbing, the daily report and the sender. It imports
  `state` (for `home()` and the counts) and `lado.__version__` lazily; nothing
  heavier at its top, since every hook imports it (`tests/test_lazy_imports.py` is
  extended).
- **D2. Files under `LADO_HOME`, not `lado.db`.**
  - Files: `errors.jsonl` (the journal), `telemetry/consent.json` (`{"choice": "on"|"off",
    "fields": <int>, "at": <ISO>}`), `telemetry/id` (a uuid4 made on the first send),
    `telemetry/outbox/*.json` (one queued error each), `telemetry/sent.json` (the last
    report's time and the last send's time and result), `telemetry/dropped` (D6),
    `telemetry/send.lock`.
  - Why: a hook and `lado mcp` must record an error also when `lado.db` has another schema
    (the `SchemaError` path) or is locked, and no migration is needed.
  - Writes are atomic: a temporary file, then a rename; the journal is appended with
    `O_APPEND`, one `write` per line.
  - Mode 600 for the journal, which holds tracebacks with paths, and for the consent and
    id files.
- **D3. The journal: `telemetry.record(where, exc, provider=None)`.** Never raises.
  - It appends `{"at", "lado", "where", "type", "message", "traceback"}` to
    `errors.jsonl`, and, when sending is on (D4), queues the scrubbed event (D5) in the
    outbox.
  - `where` is `cli:<command>`, `hook:<neutral event>`, `mcp:<tool>`, `loop` or
    `server:<route path template>`. The session and agent go into the local line only,
    as `session` and `agent`, never into the event.
  - Bound: when `errors.jsonl` passes `JOURNAL_MAX` (1 MiB), it is renamed to
    `errors.jsonl.1` (an older `.1` is replaced) before the append. The same helper,
    `telemetry.bounded_append(path, text)`, writes `hooks.log` and `loop.log`.
    `server/run.py` renames `server.log` to `server.log.1` at the server's start when it
    passes the bound.
- **D4. When sending is on.** `telemetry.state()` returns a `State`: `choice` (`on`,
  `off`, None), `fields_ok` (the stored `fields` ≥ `FIELDS_VERSION`), `off_by` (the
  variable that switches it off) and `endpoint` (whether there is a key or
  `LADO_TELEMETRY_URL`). Sending is on only when all of these hold:
  - `choice == "on"` and `fields_ok`;
  - no `off_by`: `DO_NOT_TRACK` set and not `0` or empty, or `LADO_TELEMETRY=0`;
  - `endpoint`.

  A stored `on` with an older `fields` counts as not chosen (`choice` stays `on` in the
  file, and the question names `new_fields`: `FIELDS` entries whose `since` is greater
  than the stored version). `FIELDS_VERSION` starts at 1.
- **D5. Scrubbing.**
  - An error event carries:
    - `type`: the exception class's `__module__.__qualname__`, `builtins.` dropped;
    - `chain`: the types of `__cause__`/`__context__`, at most 3;
    - `stack`: the traceback's frames whose file is under the `lado` package folder, as
      `lado/<relative path>:<function>:<line>`; each run of other frames becomes one
      entry, `<external>`;
    - `where` with its argument cut to the command, event, tool or route template (no
      ids);
    - `provider`;
    - `fingerprint`: the first 16 hex digits of sha256 of the type and the `lado` frames'
      `file:function` list, without line numbers, so that a moved line keeps the group.
  - Never `str(exc)`, locals or argv.
  - The daily report has only the fields `FIELDS` lists (D8).
  - A unit test feeds an exception whose message and locals hold a path, a session name
    and a token, and checks that none of them is in the JSON.
- **D6. The outbox and its bounds.** One file per error. A writer that finds
  `OUTBOX_MAX` (200) files or more writes none and appends one byte to
  `telemetry/dropped`. The sender sends the file's length as `errors_dropped` in the next
  report, then truncates it. The sender groups the outbox by `fingerprint`: one
  `$exception` event per group, with `count` and the first and last time; then it removes
  the files it sent. Turning sending off removes the outbox and `dropped`.
- **D7. A detached sender, behind a lock.**
  - `telemetry.kick()` is cheap (a few `stat`s, no network). When sending is on and
    something is due (a daily report 24 h after the last one, or a non-empty outbox) and
    the last attempt is older than `RETRY_AFTER` (15 min), it starts `lado telemetry
    send` as a detached process (`interpreter.run_module`, its own session, stdin, stdout
    and stderr to `/dev/null`, as `self_update.start_detached` does).
  - Callers:
    - `cli.main` after a human's command (not `hook`, `mcp`, `loop`, `telemetry send`);
    - the session loop at most once per `KICK_EVERY` (10 min) of its passes;
    - the UI server at its start and every `KICK_EVERY`, in a thread.
    A hook never kicks: it only queues, so its time limit is never at risk.
  - `lado telemetry send` takes an exclusive `flock` on `telemetry/send.lock` without
    waiting (a second one exits 0). It writes the attempt's time first, builds the batch
    (the report when due, the outbox's groups) and posts it with `SEND_TIMEOUT` (2 s, as `update.CHECK_TIMEOUT`) per socket operation and no retry inside the try; the process sets `signal.alarm(SEND_DEADLINE)` (30 s) first, as `urllib`'s timeout does not cover DNS resolution, so a hanging name lookup ends it too and frees the lock.
    On 2xx it removes what it sent and writes `sent.json`; on any failure it keeps them
    and writes the reason to `sent.json` (shown by `status`).
- **D7a. An unreachable endpoint is invisible to the user.** No process but the
  detached sender opens a connection; `kick` only checks files and starts a process
  (a failed start is swallowed: the next kick tries again). The sender catches every
  `OSError`, `urllib.error.URLError`, `http.client.HTTPException`, `ssl.SSLError`,
  timeout and non-2xx answer (and any other exception: recorded in the local journal
  only, never queued, so a broken sender cannot feed itself), prints nothing (its
  output is `/dev/null`) and writes the reason to `sent.json`. The bounds hold however
  long it lasts: the outbox's `OUTBOX_MAX` with the drop count (D6), one report whose
  window starts at the last report that went through (D8), one try per `RETRY_AFTER`
  (15 min), each within `SEND_DEADLINE`. The same holds for any endpoint, PostHog or the
  human's own (`ENDPOINT`, `LADO_TELEMETRY_URL`). Proxies: `urllib` follows the
  standard `https_proxy` / `no_proxy` variables; nothing more.
- **D8. The daily report is derived from `lado.db` when it is built.** The window runs
  from `sent.json`'s last report, or 24 h back for the first one, to now. Fields:
  - `install`, `lado`, `python`, `os` (`platform.system().lower()`), `arch`;
  - `installer`: `update.installer()`'s kind, else `dev` for an editable or folder
    install, else `other`;
  - `providers`: name → version, for the installed ones (`doctor.provider_status`);
  - `kits`: built-in and official-marketplace kit names, and the count of the others;
  - `sessions`: rows created in the window plus `session_resume` events;
  - `agents`: per provider, from `spawned` events' `provider <p>` (a helper in `state`
    parses it, next to where the detail is written);
  - `runs` (`flow_start`), `gates` (`gate_open`), `turn_errors` (`turn_error`),
    `lado_errors` (lines of `errors.jsonl` in the window), `errors_dropped`.

  A `lado.db` with another schema, or none, gives the report without the counts and
  `db: "unreadable"`. Sessions forgotten within the window are missing from the counts;
  `docs/telemetry.md` says so.
- **D9. The consent question.**
  - In the CLI, `telemetry.ask_if_needed(command)` runs at the start of `cmd_start` and
    `cmd_ui`, before any clone or start. It asks only when all of these hold: the
    choice is not made (D4); there is no `off_by`; there is an endpoint; stdin and stderr
    are ttys; and `LADO_AGENT` is unset.
  - It prints the text of mockup 4 to stderr, `[y/N]`, and stores the answer. EOF or
    Ctrl-C is no answer: nothing is stored and the command goes on.
  - The UI's banner shows while `GET /api/telemetry` says `ask: true`, which is the same
    condition without the ttys.
- **D10. PostHog, one function.**
  - `telemetry._post(batch)` posts `{"api_key": PROJECT_KEY, "batch": [...]}` to
    `ENDPOINT` (`https://eu.i.posthog.com/batch/`; `LADO_TELEMETRY_URL` replaces it for
    tests and turns on a test key).
  - Each event has `event` (`lado_daily` or `$exception`), `distinct_id` (the install ID),
    `timestamp` and `properties`. The properties carry the fields, `"$process_person_profile":
    false` (no person profiles) and `"$geoip_disable": true`.
  - An error is PostHog's `$exception` with `$exception_list`: one entry with `type`, a
    `value` of `"<type> in <where>"` (no message), a `stacktrace` of `"raw"` frames
    (`platform: "custom"`, `lang: "python"`, `filename`, `function`, `lineno`,
    `in_app: true`), plus `$exception_fingerprint`, `where`, `provider`, `count`,
    `first_at`, `last_at`.
  - `PROJECT_KEY = ""` until the human sets it. Empty means no endpoint (D4): nothing is
    asked or sent, and `status` says `this LADO has no statistics endpoint`.
  - The project's "Discard client IP data" setting is the human's (docs/telemetry.md
    says it is on).
- **D11. The CLI.**
  - `lado telemetry status` (the default) prints `statistics: on|off|not chosen`, the
    reason when off by the environment (with the stored choice), the time of the last
    send and its error, and the waiting counts.
  - `on` and `off` store the choice with the current `FIELDS_VERSION`. Both are refused
    inside an agent (`LADO_AGENT`), as `lado answer` is. `off` also empties the outbox.
  - `show` prints the next report and the grouped errors as the JSON `_post` would send,
    with the key left out.
  - `send` is hidden from the help.
  - None of them migrates `lado.db` (they are added beside `doctor` in `cli.main`'s
    no-migrate list).
- **D12. The capture points.**
  - `cli.main`: an exception outside its known list → `record("cli:<command>")`, then
    re-raised (the traceback stays as today). `KeyboardInterrupt` and `SystemExit` are
    not recorded.
  - `hooks.main`'s `except Exception` → `record("hook:<neutral event or native>",
    provider=...)`, beside the `hooks.log` line.
  - `mcp_server._reasons`: any other `Exception` → `record("mcp:<tool>")`, then
    re-raised. `_reasons` gets the tool's name.
  - `loop.RepeatedErrors.failed` → `record("loop")` once per new error, not for its
    repeats.
  - `server/app.py`: an `exception_handler(Exception)` → `record("server:<route
    template>")`, answering 500 as today.
  - `state.SchemaError` is never recorded: it is the upgrade path's expected refusal.
- **D13. The API and the UI.**
  - `GET /api/telemetry` returns `TelemetryInfo {choice, on, ask, off_by, endpoint,
    last_sent, last_error, waiting, new_fields}`. `POST /api/telemetry {choice}` runs
    under `Guard.changes`, refused 409 with `off_by` set. `GET /api/telemetry/preview`
    returns `{report, errors}`.
  - `SystemInfo.telemetry` is the status line, and `doctor.report` adds `- Statistics:
    ...`.
  - The UI:
    - `web/src/Telemetry.tsx` holds `StatisticsBanner` (in `Shell` after
      `UpdateStatus`, mockup 1A) and `StatisticsSetting` (the last section of
      Settings, mockup 2);
    - the System panel's row `Statistics` (mockup 3) links to `/settings`.
    - The banner is fetched once per page load and after its own POST. It is not in the
      change feed: a choice made in the CLI shows after a reload.
- **D14. Tests never send.** `tests/conftest.py` sets `LADO_TELEMETRY=0` as it sets
  `LADO_NO_UPDATE_CHECK=1`. A fixture `telemetry_endpoint` removes it and runs a local
  HTTP server that keeps every request, set as `LADO_TELEMETRY_URL`.

## Risks / Trade-offs

- Few people may say yes. The banner and the CLI question still reach every
  interactive user once, which was the human's choice over opt-out.
- A user's own fork or editable install sends as `installer: dev`, by its owner's choice
  (#4214); PostHog filters it out.
- A user whose network blocks PostHog never learns of it unless they look at `lado telemetry status` or Settings: the price of never disturbing them; the maintainer sees fewer reports from such places.
- PostHog is a third-party processor. `docs/telemetry.md` names it, its region, and what
  it receives. A later move to another endpoint changes `_post` only, plus
  `FIELDS_VERSION` if the fields change.
- The install ID is per `LADO_HOME`, so a user with two homes counts twice. This is
  accepted.
