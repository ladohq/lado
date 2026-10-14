## Context

What LADO already has (main at 0.37.0):

| Piece | Where | What it gives |
|---|---|---|
| System info for an issue | `doctor.system_info`, `doctor.report(system, open_to_network, up_seconds)` | Markdown with no address, path, repository, session name, token or message. The System panel's clipboard copies it, plus the page's `browserLine` |
| Error journal | `telemetry.record` → `_journal` → `LADO_HOME/errors.jsonl` (+ `.1`, 1 MiB each) | per line: `at`, `lado`, `where`, `type`, `message`, `traceback`, `session`, `agent` |
| Scrubbing | `telemetry.scrub(where, exc, provider)` | `type`, `chain`, `stack` (`lado/<file>:<function>:<line>`, `<external>`), `where`, `provider`, `fingerprint`. It needs the live exception, so it cannot run on a journal line |
| The UI's System panel | `SystemPanel.tsx`, `GET /api/system` (`SystemInfo.report`) | the copy button, GitHub ↗ |

The journal's `message` and `traceback` name paths, sessions and repositories, so no
report may read them. `scrub` cannot be applied after the fact: a line keeps only text.
GitHub's new issue form takes `title` and `body` in its query. Long URLs fail (GitHub
answers 414 well before browsers' own limits; about 8 KB is the safe bound in practice).
`labels` in the query is applied only for users with triage rights.

Root cause: LADO has its facts and its errors, but no way to turn them into a report the
human can read and send, with nothing in it that names their work.

## Options

1. **Copy only**: a second clipboard button that adds the scrubbed errors to the system
   info, with no link. Cost: the least code. But the human still has to find the
   repository and paste the text, and the task asks for the issue form to open filled in.
2. **Chosen: a report and a link to GitHub's form**, built by the core for the CLI and the
   UI. The human sees it and opens the form, where they edit and submit it. Cost: one core
   module, one CLI command, one endpoint, one page and a rail item. No server, no token, no
   dependency. The URL bound limits how much fits, so the full text stays printable.
3. **Post through GitHub's API** (`gh issue create`, or a token). Cost: a login or a token
   to keep, and the text goes out without GitHub's form, where the human can still see
   and change it. Most users of the wheel have no `gh`. Rejected with the human.

Held against AGENTS.md's Design principles and ROADMAP:

- **Neutral core**: no provider is involved. The provider is one field of a journal line,
  filled by every provider's hooks alike.
- **One source of truth**: the system info stays `doctor.report`, and the scrubbed form
  stays `telemetry.scrub`, now written into the journal at capture (D2). The report and the
  link are built in one place, `bug_report.build`, for the CLI and the API (D1, D5). The
  browser line stays the page's `browserLine`.
- **No silent drops**: kinds of errors left out of the link are counted in the body (D4).
  Lines without the scrubbed form are shown, only without a stack (D2).
- **Only what is used**: one command with no flags, one read-only endpoint, one page.
- ROADMAP: support tooling around the current stage. Nothing to come depends on it or is
  blocked by it.

## Decisions

### D1. A core module `bug_report.py`

`src/lado/bug_report.py` holds `errors(now)` (the journal's lines of the last `WINDOW`, 30
days, from `errors.jsonl.1` then `errors.jsonl`, an unreadable line skipped), `kinds(lines)`
(the groups, newest first), and `build(system, server, browser=None, now=None)`, a
`Report(title, text, body, url, left_out)`. `text` is the whole report and `body` the
link's (cut, D4). Standard library only. At its top it imports only `telemetry`, `doctor`
and `update`: the CLI imports it inside the command (`tests/test_lazy_imports.py`).
**Why:** the CLI and the API need the same text and link, and a second builder in
TypeScript would drift.

### D2. The journal keeps the scrubbed form

`telemetry._journal` gets the exception's `scrub(where, exc, provider)` and writes its
`chain`, `stack`, `fingerprint` and `provider` into the line (`record` passes `provider`
on). The outbox event stays as it is. A line without these fields (0.37) is grouped by
`(type, where)` and shown without frames. The report never reads `message`, `traceback`,
`session` or `agent`. **Why:** scrubbing needs the live exception, and parsing a traceback
text back into frames is a second scrubber that could leak a path. It costs about 300
bytes per line in a file bounded at 1 MiB.

### D3. The report's text

```
### What happened

<!-- What did you do, what did you expect, and what happened instead? -->

<doctor.report(...)>            # "### LADO system info" and its lines
- Browser: Chrome 141 on macOS  # the page's line, UI only

### LADO errors (last 30 days, 2 kinds)
- KeyError at hook:turn_end (claude), 3 times, 2026-10-12 to 2026-10-14, LADO 0.37.0, 0.38.0
  - lado/hooks.py:handle:212
  - <external>
```

With no errors the section says `No LADO errors in the last 30 days.` A kind's count is
`once` or `N times`. Its days are `YYYY-MM-DD` (one day when first and last are the same),
and its versions are distinct, in the order first seen. The stack is shown innermost-last
as in the journal, at most `MAX_FRAMES` (12) of its innermost frames. **Why:** the
placeholder makes the human write the story first. The innermost frames are where the
bug is.

### D4. The link and its bound

`ISSUES_NEW = "https://github.com/ladohq/lado/issues/new"`, and the query is
`urlencode({"title", "body"}, quote_via=quote)`. `MAX_URL = 8000` characters. When the
link of the whole text is longer, the oldest kind is removed from the body, one at a time,
until it fits. The section's last line is then `- N more kinds of errors left out: lado
bug-report prints them all`, and the heading still counts all kinds. If even no kinds do
not fit (never seen: the system info is about 1.5 KB), the body is the system info only
and the line says all were left out. The title is `<type> at <where>` of the newest kind,
cut to 120 characters, or empty. No `labels` (out of scope). **Why:** GitHub refuses
longer URLs. The newest errors matter most.

### D5. `GET /api/bug-report?browser=<line>`

The endpoint answers `BugReport {title, text, url, left_out}`. It is read-only, under the
token (`guard`) but not `Guard.changes`: it changes nothing and goes nowhere. `browser` is
optional and must match `^- Browser: [A-Za-z0-9 .]{1,40} on [A-Za-z ]{1,20}$`, the shape
`browserLine` gives, else 422. So no free text from a request gets into a report. The
server passes its own `open_to_network` and its uptime as for `/api/system`. A plain `def`
(it runs the providers' `--version`, as `/api/system` does). `make web-types`.

### D6. `doctor.report`'s server line

`report(system, server)`, where `server` is a `ServerState(open_to_network, up_seconds)`
or None. The line reads `- Server: loopback only, up 2 h 14 min, schema 26` as today, and
`- Server: not running, schema 26` for None. The CLI reads the running server's
`server.json` (`server.run.running()`: its `host` decides `open to the network`). Its
uptime is unknown there, so the line reads `running, loopback only, schema 26`
(`up_seconds` None). `/api/system`'s report is unchanged. **Why:** the CLI has no server
of its own, and the line must not lie.

### D7. `lado bug-report`

`cli.cmd_bug_report`: it prints `bug_report.WARNING` (public issue, nothing sent until
submitted, edit it there, SECURITY.md's private reporting), a blank line, `text`, then
`Open a new issue: <url>`, all on stdout. It asks only when `sys.stdin.isatty()` and
`sys.stdout.isatty()` and `bug_report.can_show_browser()`: on macOS
`gui_session.place()` is `gui`; elsewhere `DISPLAY`, `WAYLAND_DISPLAY` or
`BROWSER` is set. A `y`/`yes` runs `webbrowser.open(url)`. If that returns False or
raises, it prints `could not open a browser: open the link above`. Enter, `n`, EOF and
Ctrl-C open nothing, and the exit is 0. Added to the commands that skip
`migrate_if_safe` (as `doctor`, `telemetry`), and refused nowhere, not even inside an
agent: with no terminal it only prints. **Why:** over ssh `webbrowser` would start a text
browser or fail. The human's `y` is the act that sends.

### D8. The UI

The rail's `rail-bottom` gets a `RailLink to="/report" name="Report a bug"
icon={<BugIcon />}` above Settings. There is a new `BugIcon` in `icons.tsx`, a route
`report` in `App.tsx` and a page `ReportBug.tsx`. `useTitle("Report a bug")`. The page
shows the warning paragraph with a SECURITY link, the `text` in `pre.log`, and an `<a
className="primary" href={url} target="_blank" rel="noreferrer">Open a new issue on GitHub
↗</a>`. **Copy text** uses `useCopy` and copies `text`, "Report copied". Loading shows
"Loading…", and a failure shows `.problem`. The report is fetched on mount, with
`browserLine(navigator.userAgent)` (moved to a shared module if the import would pull
SystemPanel in). The left-out line shows only in the link's body, never on the page.
**Why:** a page like Settings, as the human chose (mockup variant A). No new kind of
window.

### D9. Tests never open a browser

`tests/conftest.py` sets `BROWSER=true` for the test run, so `webbrowser` runs `true
<url>`, which does nothing. A guard test checks that it is set. The CLI tests also replace
`webbrowser.open` to see the call. **Why:** like `LADO_TELEMETRY=0`, a test that forgot to
patch must still open nothing.

### D10. Test layers

The test layers (AGENTS.md, Testing): unit for `bug_report` (grouping, window, both
files, the 0.37 line, the privacy scenario with a journal full of names, the bound with
40 kinds, the title), `telemetry._journal`'s new fields, `doctor.report`'s server line,
the CLI (tty and question, no tty, ssh-like environment, a newer schema, no migration),
and the API (TestClient: the answer, the browser check's 422). vitest for the page and the
rail item (collapsed tooltip). UI e2e: the rail item on a session's page opens `/report`,
the link's `href` starts with `https://github.com/ladohq/lado/issues/new?title=` (never
clicked), Copy text, and screenshots. No integration test: no behaviour crosses
processes. The journal's write is already covered by LAD-32's integration test, which
gets one assertion on the new fields.

### D11. Version and docs

A minor release (0.38.0): a new CLI command, an endpoint and a page. The CHANGELOG line goes
under `## 0.38.0 (unreleased)`. AGENTS.md: `bug_report.py` in Layout, `lado bug-report`
by `lado telemetry`'s paragraph, `doctor.report`'s server argument. `docs/design/ui.md`:
Structure's rail list, and a section "Report a bug (decided 2026-10-14, LAD-33)".
`docs/telemetry.md`: "Reporting a bug yourself". README: one line.

## Risks / Trade-offs

- A kind's `where` is `server:<route template>` or `cli:<command>`: names from code, never
  from data. A future capture that puts data into `where` would leak it into both
  telemetry and the report. `telemetry.scrub`'s rule already forbids it.
- GitHub may change the form's query parameters. The link would then open an empty form,
  and **Copy text** still works.
- The 8000 bound is conservative. A longer body might pass, but a refused link would be
  worse than fewer kinds.
