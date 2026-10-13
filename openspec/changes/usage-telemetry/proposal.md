Task: LAD-32

## Why

The maintainer cannot tell how many people use LADO, which versions they run, or which
errors they hit, so tasks are prioritised blind. PyPI's download counts are no answer: CI
runs and mirrors inflate them, and they say nothing of errors.

Root cause: LADO keeps no account of its own failures in one place and has no channel to
its maintainers. Unexpected exceptions land in four unrelated logs without LADO's version
(`hooks.log`, `loop.log`, `server.log`, `update.log`; none of them bounded in size), an
unexpected exception of a CLI command or of an MCP tool is written nowhere (the CLI prints
a traceback, the MCP SDK turns it into "Error executing tool"), and nothing ever leaves the
machine but the update check's look at PyPI. What LADO does is in `lado.db` (`events`), but
no one but the user sees it, and `lado forget` deletes it with the session.

## What Changes

- **One error journal.** Every unexpected exception of a LADO process (a CLI command, a
  hook, `lado mcp`'s tools, the session loop, the UI server) is written as one JSON line
  to `LADO_HOME/errors.jsonl`, with the time, LADO's version, where it happened and the
  full traceback. It is local only and bounded in size. `hooks.log` and `loop.log` get
  the same size bound, and `server.log` is rotated when the server starts.
- **Usage statistics, with the human's consent** (`lado telemetry`): LADO asks once
  whether it may send anonymous statistics and its own errors to the maintainers. The
  question is a banner under the UI's top bar and a `[y/N]` question of `lado start` and
  `lado ui` in a terminal. Until it is answered nothing is sent, and also with
  `DO_NOT_TRACK=1` or `LADO_TELEMETRY=0`. The choice is kept in `LADO_HOME` and changed
  in the UI's Settings (a new section, Usage statistics) or with `lado telemetry on|off`.
- **What is sent**, to PostHog Cloud EU over plain HTTPS with the standard library:
  - **A daily report**: a random install ID, LADO's and Python's version, OS and
    architecture, the installer (uv tool, pipx, dev), the installed agent CLIs with
    their versions, the kits (built-in and official ones by name, others counted), and
    counts since the last report: sessions started or resumed, agents spawned per
    provider, flow runs, gates, turn errors, LADO errors.
  - **Each LADO error**: its type, its stack within LADO's own code (file, function and
    line), where it happened (CLI command, hook event, MCP tool, loop, API route) and the
    provider.
  - Never a path, repository, session or agent name, message, prompt, argument, key, or an
    exception's text.
  - `lado telemetry show` and the UI print exactly what the next send would carry.
- **The consent covers a list of fields** (`docs/telemetry.md`). When a later LADO sends a
  new kind of data, it asks again and names what is new.
- `lado telemetry status` and the System panel's new row `Statistics` say whether it
  sends, why not, and when it last sent; `doctor.report` gets a `- Statistics:` line.
- Docs: `docs/telemetry.md` (public: what, where, how to switch it off), AGENTS.md,
  docs/design/ui.md, README, CHANGELOG.md.

## Scope

A new module `src/lado/telemetry.py` (consent, journal, outbox, the daily report, the
sender), the error capture in `cli.py`, `hooks.py`, `mcp_server.py`, `loop.py` and
`server/app.py`, the log bounds, `lado telemetry` (`status`, `on`, `off`, `show`, and a
hidden `send`), the consent question of `lado start` and `lado ui`, the API (`GET` and
`POST /api/telemetry`, `GET /api/telemetry/preview`, `SystemInfo.telemetry`), the web UI
(the banner, Settings → Usage statistics, the System panel's row), the tests' environment
(`LADO_TELEMETRY=0` in `tests/conftest.py`), docs.

## Out of scope

- **Reporting an error as a GitHub issue** (`lado bug-report`, the UI's button): its own
  task, LAD-33. It builds on this change's journal and scrubbing.
- **`lado stats`, a local view of usage**: its own task, LAD-34. It may reuse the daily
  report's counts.
- **Opt-out or sending before the human answers**: the human chose an explicit question.
  Opt-out is what developer communities pushed back on (Audacity 2021, GitLab 2019, Go
  2023, Fedora 2023).
- **The modal dialog on the UI's first open** (mockup 1B): the human chose the banner (1A).
- **Sentry, a self-hosted endpoint or an SDK dependency**: PostHog's HTTP API carries
  both the counts and the errors, with no new dependency ("standard library first").
- **Publishing the aggregated data** (as Homebrew and Go do): not now. `docs/telemetry.md`
  says what is collected.
- **The browser's own JavaScript errors** in the UI: only the Python side is LADO's
  runtime. Possible later.
- **The PostHog project key itself**: the human creates the PostHog project and puts its
  key into `telemetry.PROJECT_KEY` before the release. Without a key LADO asks nothing and
  sends nothing, and says so.
- **Errors from before the human said yes**: nothing is queued while the choice is open
  or off. The local journal keeps them.
- **The agent CLIs' own telemetry**: LADO changes nothing there (Codex's analytics stay
  switched off as before).

## Acceptance criteria

- AC-1: An unexpected exception in a CLI command, a hook, an MCP tool of `lado mcp`, a pass
  of the session loop and an API request of the UI server each adds one line to
  `LADO_HOME/errors.jsonl` with time, LADO version, `where`, the exception's type and
  message and the traceback; LADO's own refusals (`LadoError` and the other errors the
  CLI and the tools print as reasons) add none; the journal, `hooks.log` and `loop.log`
  keep at most their size bound plus one rotated file, and `server.log` is rotated at the
  server's start when over its bound.
- AC-2: With no choice made, `lado start` and `lado ui` in a terminal (stdin and stderr
  ttys, not inside an agent, no `DO_NOT_TRACK`/`LADO_TELEMETRY=0`, an endpoint present)
  ask once `Send them? [y/N]`; Enter or `n` is off, `y` is on; the choice is kept; without
  a terminal nothing is asked and nothing is sent.
- AC-3: With no choice made, the UI shows the banner under the top bar on every page;
  Send statistics or Don't send makes the choice and the banner goes; What is sent shows
  the next daily report.
- AC-4: Settings has a section Usage statistics with Send / Don't send, the state's line
  (last sent, not chosen yet, or off by the environment, its switch disabled) and links to
  the preview and to `docs/telemetry.md`; the System panel has a row `Statistics`, and the
  copied report has `- Statistics: on|off|not chosen` (and why off).
- AC-5: `lado telemetry status|on|off|show` work as in the mockup; `on` and `off` are
  refused inside an agent; `show` prints the next daily report and the errors waiting, the
  very JSON the sender would post.
- AC-6: With the choice on, LADO sends at most one daily report per 24 hours and the
  queued errors (one event per error kind with its count), from a detached sender that
  never delays a command, a hook or a loop pass; a failed send keeps them for the next try;
  with the choice off, the queue is emptied and nothing is sent; with `DO_NOT_TRACK=1` or
  `LADO_TELEMETRY=0` nothing is queued or sent whatever the choice.
- AC-7: No event carries a path, a repository, session or agent name, a message, a
  prompt, a command's argument or an exception's text; an error's stack names only frames
  of LADO's own package.
- AC-8: When LADO's list of fields is newer than the one the human said yes to, the
  choice counts as not made and the question names the new fields.
- AC-9: The test runs never send (`LADO_TELEMETRY=0` in `tests/conftest.py`); the tests
  of sending use a local endpoint.
- AC-10: `docs/telemetry.md`, AGENTS.md, docs/design/ui.md, README and CHANGELOG.md say
  so; the tests named in the plan pass.

## Impact

- New: `src/lado/telemetry.py`, `docs/telemetry.md`, `web/src/Telemetry.tsx` (banner and
  Settings section), tests.
- Changed: `cli.py`, `hooks.py`, `mcp_server.py`, `loop.py`, `server/app.py`,
  `server/models.py`, `server/run.py`, `doctor.py`, `web/src/Shell.tsx`,
  `Settings.tsx`, `SystemPanel.tsx`, `styles.css`, `web/openapi.json`,
  `web/src/api.gen.ts`, `tests/conftest.py`, AGENTS.md, docs/design/ui.md, README.md,
  CHANGELOG.md.
- Minor version: a new CLI command and API endpoints; part of 0.37.0, already the next
  minor. No schema change: everything lives in files under `LADO_HOME` (D2).

## Decisions for the record

- Scale full: new behaviour across every LADO process, the CLI, the API and the UI, with
  product questions settled with the human in three rounds (#4199, #4203, #4214). Review
  breadth first.
- Root cause, the options and the chosen one are in `design.md` (Options).
- Engineering decisions D1–D14 in `design.md`: files under `LADO_HOME/telemetry/`, not
  `lado.db`; a detached sender behind a flock; counts derived from `lado.db` at send
  time; the scrubbing of stacks to LADO's frames; PostHog's batch API with no person
  profiles and no GeoIP; the consent's field list version.
- Test layers: unit for the module, the CLI, the API and each capture point; integration
  with the fake agent for a failing hook's journal and queue and for the loop's send to a
  local endpoint (they cross processes); vitest for the banner, the Settings section and
  the panel's row; UI e2e for the banner and Settings with screenshots. No live or smoke
  test: nothing changes in how a provider runs.
- Related tasks filed with the human's yes: LAD-33 (bug report), LAD-34 (`lado stats`);
  order LAD-32, then LAD-33, LAD-34 any time after LAD-32.
