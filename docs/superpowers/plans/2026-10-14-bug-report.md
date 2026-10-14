# Bug report: implementation plan

**Goal:** `lado bug-report` and the UI's **Report a bug** (a rail item and a page) build a
scrubbed report from `doctor.report` and the error journal, and open GitHub's new issue
form filled in only on the human's act (LAD-33).

**Architecture:** a new core module `src/lado/bug_report.py` (`errors`, `kinds`, `build`,
`can_show_browser`, `WARNING`) builds the text and the link for the CLI
(`cli.cmd_bug_report`) and the API (`GET /api/bug-report`). `telemetry._journal` writes
the scrubbed form into each journal line. `doctor.report` takes the server's state. The UI
gets a rail item, a route `/report` and the page `ReportBug.tsx`.

**Spec:** `openspec/changes/bug-report/` (proposal, deltas `bug-report` and
`error-journal`, `design.md` D1–D11). **Design doc:**
`docs/superpowers/specs/2026-10-14-bug-report-design.md`. **Mockup:** run artifact
`task/lad-33/mockup-bug-report.html`, variant A.

Each task: tests first, then the code, then the named test run, then a commit (message in
the repository's style, `(LAD-33)` at the end).

## Task 1: the journal keeps the scrubbed form (D2)

**Files:** `src/lado/telemetry.py`, `tests/test_telemetry.py`,
`tests/integration/test_telemetry_processes.py`.

1. Tests: `record("hook:turn_end", exc, "claude", "s", "w1")` writes a line with `chain`,
   `stack` (LADO frames `lado/...:<fn>:<line>`), `fingerprint` equal to the outbox
   event's, and `provider` `claude`, besides the old fields. With sending off, the same
   fields and nothing queued. The integration test of a failing hook asserts `stack` and
   `provider` in its line.
2. Code: `_journal(where, exc, session, agent, provider)` merges `scrub(...)` minus
   `type`/`where` (already there). `record` computes `scrub` once for both the line and
   the event.
3. `uv run pytest tests/test_telemetry.py -n auto`, `uv run pytest -m integration -n auto
   tests/integration/test_telemetry_processes.py`; commit.

## Task 2: `doctor.report`'s server line (D6)

**Files:** `src/lado/doctor.py`, `src/lado/server/app.py`, `tests/test_doctor.py`,
`tests/test_server_system.py`.

1. Tests: `report(system, ServerState(False, 8040))` gives `- Server: loopback only, up 2
   h 14 min, schema 26` (as before), `ServerState(True, None)` gives `- Server: running,
   open to the network, schema 26`, and None gives `- Server: not running, schema 26`.
   `/api/system`'s `report` is unchanged.
2. Code: `ServerState` dataclass, `report(system, server)`, the call in `app.py`.
3. `uv run pytest tests/test_doctor.py tests/test_server_system.py -n auto`; commit.

## Task 3: the report and the link (D1, D3, D4)

**Files:** `src/lado/bug_report.py`, `tests/test_bug_report.py`,
`tests/test_lazy_imports.py`.

1. Tests (journal lines written as JSON into a `tmp_path` `LADO_HOME`, `now` fixed):
   - grouping by `fingerprint`, newest first; a 0.37 line grouped by `(type, where)`, with
     no frames; `once` / `3 times`; one day or `A to B`; versions distinct in order;
     at most 12 frames, the innermost kept;
   - the window: a 31-day-old line in `errors.jsonl.1` is out, a 29-day-old one is in;
     an unreadable line is skipped;
   - privacy (spec: "A journal line full of names"): message, traceback, session and agent
     naming `/Users/ann/acme`, `billing`, `dev`, and none of them in `text`, `body` or
     `url`;
   - no errors: `No LADO errors in the last 30 days.`, empty title;
   - the bound: 40 kinds give `len(url) <= 8000`, the left-out line with the right N, the
     newest kinds kept, `text` with all 40; the title `<type> at <where>` of the newest,
     cut to 120;
   - `build(..., browser="- Browser: Chrome 141 on macOS")` puts the line after the system
     info;
   - `bug_report` is not imported by `import lado.cli` (lazy imports).
2. Code: `WINDOW`, `MAX_URL`, `MAX_FRAMES`, `ISSUES_NEW`, `WARNING`, `Report`, `errors`,
   `kinds`, `build`.
3. `uv run pytest tests/test_bug_report.py tests/test_lazy_imports.py -n auto`; commit.

## Task 4: `lado bug-report` (D7, D9)

**Files:** `src/lado/bug_report.py` (`can_show_browser`), `src/lado/cli.py`,
`tests/conftest.py`, `tests/test_cli_bug_report.py`.

1. Tests (stdin/stdout ttys faked, `webbrowser.open` replaced):
   - no tty: the warning, the text and `Open a new issue: https://github.com/ladohq/lado/issues/new?title=`
     printed, no question, no open;
   - tty, Linux with `DISPLAY`: the question; `y` opens the link, Enter and EOF do not,
     exit 0; `webbrowser.open` returning False prints `could not open a browser: open the
     link above`;
   - tty, Linux with none of `DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER`: no question;
   - macOS: `LADO_MACOS_PLACE=remote` gives no question, `gui` gives one;
   - a newer `lado.db` schema: the report prints `schema <n>`, and the database's
     `user_version` is unchanged; no `lado.db`: it prints;
   - the server line: no server is `not running`; a fake `server.json` with host
     `0.0.0.0` and the lock held is `running, open to the network`;
   - `BROWSER` is `true` in the test run (the guard).
2. Code: the subcommand (help "print a bug report for a new GitHub issue, and open it"),
   no `migrate_if_safe`, `cmd_bug_report`; `BROWSER=true` in `tests/conftest.py`.
3. `uv run pytest tests/test_cli_bug_report.py tests/test_cli.py -n auto`; commit.

## Task 5: the API (D5)

**Files:** `src/lado/server/app.py`, `src/lado/server/models.py`,
`tests/test_server_bug_report.py`, `web/openapi.json`, `web/src/api.gen.ts`.

1. Tests (TestClient): `GET /api/bug-report` answers `title`, `text`, `url`,
   `left_out`; with `browser=- Browser: Firefox 131 on Linux` the text has that line;
   `browser=<a line with a newline>` or `- Browser: /Users/ann` is 422; without the token
   it is 401 as the other endpoints.
2. Code: `BugReport` model, the route (a plain `def`); `make web-types`, both files
   committed.
3. `uv run pytest tests/test_server_bug_report.py -n auto`, `make web`; commit.

## Task 6: the UI (D8)

**Files:** `web/src/icons.tsx`, `web/src/Shell.tsx`, `web/src/App.tsx`,
`web/src/ReportBug.tsx`, `web/src/api.ts`, `web/src/ReportBug.test.tsx`,
`web/src/Layout.test.tsx` (or the rail's test), `web/src/styles.css`.

1. vitest: the rail has **Report a bug** above Settings, and collapsed it keeps its name as
   tooltip and accessible name; the page shows Loading…, then the warning, the text and
   the link (`href` = `url`, `target=_blank`), and Copy text copies `text` ("Report
   copied"); a failed load shows the reason; the request carries `browser=` from
   `browserLine`.
2. Code to the mockup's variant A (the real `primary` and `ghost` classes; `pre.log`
   styles shared with the System panel's).
3. `make web`; commit.

## Task 7: UI e2e (D10)

**Files:** `tests/ui/test_bug_report.py`.

1. On a session's page (fake agent), click **Report a bug** on the rail: the page
   `/report` shows `### LADO system info` and `- Browser:`, and the link's `href` starts
   with `https://github.com/ladohq/lado/issues/new?title=` (never followed). Copy text
   shows "Report copied". The rail collapsed still shows the icon with its tooltip.
   `shot` of the page and of the collapsed rail.
2. `uv run pytest -m ui tests/ui/test_bug_report.py`; commit; attach the screenshots to
   the build report.

## Task 8: docs (D11)

**Files:** `AGENTS.md`, `docs/design/ui.md`, `docs/telemetry.md`, `README.md`,
`CHANGELOG.md`.

1. AGENTS.md: `bug_report.py` in Layout; `lado bug-report` beside `lado telemetry`'s
   paragraph; `doctor.report(system, server)`; the journal's new fields in
   `telemetry.py`'s entry; `BROWSER=true` beside `LADO_TELEMETRY=0` in the tests'
   environment paragraph.
2. `docs/design/ui.md`: Structure's rail list (Report a bug above Settings), a section
   "Report a bug (decided 2026-10-14, LAD-33)" with the page and `GET /api/bug-report`.
3. `docs/telemetry.md`: "Reporting a bug yourself" (what the report holds, that it is
   your act, GitHub's form). README: one line. CHANGELOG: `## 0.38.0 (unreleased)` (add it
   when missing), one line.
4. `make lint`; commit.

## Regression run

Before the build report: `make lint`, `make test` (`-n auto`), `uv run pytest -m
integration -n auto tests/integration/test_telemetry_processes.py`, `uv run pytest -m ui
tests/ui/test_bug_report.py tests/ui/test_system_panel.py tests/ui/test_layout.py`, `make
web`, `openspec validate bug-report --strict` and `openspec validate --specs --strict`.
CI runs the rest.

## Tests per requirement

| Requirement | Tests |
|---|---|
| bug-report: holds the system info and errors, nothing that names the user's work | `test_bug_report.py` (privacy, no errors, browser line) |
| bug-report: groups the errors of the last 30 days by kind | `test_bug_report.py` (grouping, window, 0.37 line, frames) |
| bug-report: the issue link fits GitHub's bound | `test_bug_report.py` (40 kinds, title) |
| bug-report: nothing leaves without the human | `test_cli_bug_report.py` (no open without `y`, the `BROWSER` guard), `test_server_bug_report.py`, `tests/ui/test_bug_report.py` (link never followed) |
| bug-report: `lado bug-report` prints and asks | `test_cli_bug_report.py` |
| bug-report: the UI shows Report a bug on every page | `ReportBug.test.tsx`, the rail's vitest, `tests/ui/test_bug_report.py` |
| error-journal (modified): the line holds the scrubbed form | `test_telemetry.py`, `tests/integration/test_telemetry_processes.py` |
