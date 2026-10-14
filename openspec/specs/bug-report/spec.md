# bug-report Specification

## Purpose
How a user reports a LADO bug: `lado bug-report` and the UI's Report a bug page build one
scrubbed Markdown report (a "What happened" placeholder, the system info, LADO's own
errors of the last 30 days by kind) and a link to GitHub's new issue form, with nothing
that names the user's work, and nothing goes to the network until the human submits the
form.

## Requirements

### Requirement: The bug report holds the system info and LADO's recent errors, and nothing that names the user's work

LADO SHALL build one Markdown bug report for the CLI and the UI alike
(`bug_report.build`). It SHALL hold, in this order: a `### What happened` section with a
placeholder comment for the human; the system info of `doctor.report`; in the UI, the line
naming the page's browser and its OS; and a `### LADO errors` section. The report SHALL
NOT hold a path, a home folder, a session, agent or repository name, a message's text, an
exception's message or a traceback, whatever the journal's lines hold. From the journal it
SHALL take only each line's time, LADO version, `where`, type, `chain`, `stack` and
`provider`.

#### Scenario: A journal line full of names
- **WHEN** `errors.jsonl` has a line whose message is `no such file: /Users/ann/acme/.lado/worktrees/billing/dev`, whose traceback names `/Users/ann/acme`, with session `billing` and agent `dev`
- **THEN** the report contains none of `/Users/ann`, `acme`, `billing` or `dev` (as a session or agent), and it shows that error's type, `where` and stack

#### Scenario: No errors
- **WHEN** the journal has no line from the last 30 days
- **THEN** the errors section says `No LADO errors in the last 30 days.`

### Requirement: The report groups LADO's errors of the last 30 days by kind

The errors section SHALL hold the journal's lines from the last 30 days, read from
`errors.jsonl` and `errors.jsonl.1`, grouped by `fingerprint`. A line without one, as
LADO 0.37 wrote, SHALL be grouped by its type and `where`. The groups SHALL be ordered
newest first, by their latest line. Each kind SHALL show its type, `where`, its provider
when known, its count (`once`, `N times`), its first and last day, the LADO versions it
happened in, and its stack (LADO's frames as `lado/<file>:<function>:<line>`, others as
`<external>`), at most 12 frames from the innermost. A kind without a stack SHALL show no
stack lines.

#### Scenario: The same error three times
- **WHEN** a `KeyError` at `hook:turn_end` of provider `claude` was journaled on Oct 12, 13 and 14 by LADO 0.37.0 and 0.38.0
- **THEN** the report has one kind: `KeyError at hook:turn_end (claude), 3 times, 2026-10-12 to 2026-10-14, LADO 0.37.0, 0.38.0`, then its frames

#### Scenario: A line of LADO 0.37
- **WHEN** a line has no `fingerprint` or `stack`
- **THEN** it is grouped with the other lines of its type and `where` that have none, and its kind has no frames

#### Scenario: An old error
- **WHEN** a line of `errors.jsonl.1` is 31 days old
- **THEN** the report leaves it out

### Requirement: The issue link fits GitHub's bound

LADO SHALL make the report a link to GitHub's new issue form,
`https://github.com/ladohq/lado/issues/new?title=<title>&body=<body>`, at most 8000
characters long. The title SHALL be `<type> at <where>` of the newest kind of error, or
empty with no errors. When the link with the whole report is longer, LADO SHALL leave out
of its body the oldest kinds of errors, one by one, until it fits. The body SHALL then end
the errors section with `N more kinds of errors left out: lado bug-report prints them
all`. The report the CLI prints and the page shows SHALL never be cut.

#### Scenario: Many kinds of errors
- **WHEN** the journal has 40 kinds of errors in the last 30 days
- **THEN** the link is at most 8000 characters, its body holds the newest kinds that fit and the line naming how many were left out, and `lado bug-report` prints all 40

### Requirement: Nothing of the report leaves LADO without the human

Neither the CLI nor the UI server SHALL send the report, or any part of it, anywhere. The
form SHALL open only on the human's act: their `y` in `lado bug-report`, or their click on
the page's link. Above the report both SHALL say that the issue is public, that nothing is
sent until the human submits it on GitHub, where they can edit it, and that a
vulnerability goes to GitHub's private reporting (SECURITY.md). The test run SHALL never
open a browser.

#### Scenario: The page is opened
- **WHEN** the human opens the Report a bug page
- **THEN** the server reads the journal and the system facts and answers the page, and no request goes to GitHub until the human clicks Open a new issue on GitHub

### Requirement: lado bug-report prints the report and asks before it opens a browser

`lado bug-report` SHALL print the warning, the whole report and the line `Open a new
issue: <link>`. When stdin and stdout are terminals and a browser can show (macOS with the
process in the graphical session; elsewhere `DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER` set),
it SHALL then ask `Open it in the browser? [y/N]`. `y` SHALL open the link in the default
browser. Enter, `n`, EOF or Ctrl-C SHALL open nothing and exit 0. A browser that does not
open SHALL print `could not open a browser: open the link above`. Otherwise it SHALL ask
nothing. The command SHALL NOT migrate `lado.db`, and SHALL work with a `lado.db` of
another schema version or with none. Its `Server:` line SHALL say whether the UI server
runs (`not running`, or `running, loopback only` / `running, open to the network`; in a
container `running, in a container`, as the container's port publication, not LADO,
decides who reaches it).

#### Scenario: Over ssh on Linux
- **WHEN** the human runs `lado bug-report` over ssh, with no `DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER`
- **THEN** it prints the report and the link and asks nothing

#### Scenario: The human says yes
- **WHEN** the human runs it in a Mac's terminal in the graphical session and answers `y`
- **THEN** the default browser opens the link

#### Scenario: A database of a newer LADO
- **WHEN** `lado.db` has a newer schema than this LADO's
- **THEN** `lado bug-report` prints the report with `schema <n>`, and the database is unchanged

#### Scenario: The server in a container
- **WHEN** the human runs `lado bug-report` in a container (`LADO_CONTAINER=1`) whose UI
  server listens on `0.0.0.0`
- **THEN** its `Server:` line reads `running, in a container`, and the System panel's copy
  and the Report a bug page read `in a container, up <time>`

### Requirement: The UI shows Report a bug on every page

The rail SHALL have a **Report a bug** item with a bug icon above Settings, on every page,
with only its icon (its name as tooltip and accessible name) when the rail is collapsed.
It SHALL open the page `/report` (title "Report a bug"). The page SHALL load `GET
/api/bug-report?browser=<line>` with its browser line, and show the warning, the whole
report, **Open a new issue on GitHub ↗** (the report's link, opened in a new tab) and
**Copy text** (copies the report; "Report copied"). A failed load SHALL show its reason.
The page SHALL load the report anew on each visit; the change feed does not carry it.

#### Scenario: From a session's page
- **WHEN** the human is on a session's page and clicks Report a bug on the rail
- **THEN** the Report a bug page shows the report with a `- Browser:` line, and Open a new issue on GitHub links to `https://github.com/ladohq/lado/issues/new?…`
