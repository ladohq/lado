Task: LAD-33

## Why

A user who hits a LADO bug has no easy way to tell the maintainers what happened. They
must find the repository, open an issue, and gather the facts the maintainer needs: the
LADO version, the agent CLIs, the system, and the error itself. LADO already holds all of
that. `doctor.report` (the System panel's "Copy system info") has the system facts without
paths or names. LAD-32 added `LADO_HOME/errors.jsonl`, where every unexpected exception of
a LADO process is kept. But the journal cannot be pasted as it is: each line holds the
exception's text and full traceback, and both name paths, sessions and repositories. Usage
statistics (LAD-32) send scrubbed errors only with the human's yes, and only to PostHog.
They are no report the human writes and sends.

Root cause: LADO has its facts and its errors, but no way to turn them into a report the
human can read and send as one issue, with nothing in it that names their work.

## What Changes

- **A bug report.** LADO builds a Markdown text for a new GitHub issue. It holds a
  placeholder "What happened" section for the human, the system info of `doctor.report`
  (plus the browser in the UI), and LADO's own errors of the last 30 days, grouped by kind.
  Each kind has its type, where it happened, the provider, how often, the first and last
  day, the LADO versions, and the stack within LADO's own code. The report never holds an
  exception's text or traceback, a path, a session, agent or repository name, or a
  message's text.
- **The issue link.** The report becomes a link to GitHub's new issue form of
  github.com/ladohq/lado, with the title and body filled in. The title is the newest
  error's `<type> at <where>`, or empty with no errors. The link fits GitHub's URL bound:
  the oldest kinds of errors are left out until it fits, and a line in the body says how
  many and that `lado bug-report` prints them all.
- **Nothing leaves without the human.** LADO itself sends nothing. The human sees the
  whole text first. Only their click (UI) or their `y` (CLI) opens the form, and the issue
  is posted only when they submit it on GitHub, where they can edit or delete anything.
  The text says the issue is public, and that a vulnerability goes to GitHub's private
  reporting (SECURITY.md).
- **`lado bug-report`** prints that warning, the full report and the link. In a terminal
  where a browser can show, it then asks `Open it in the browser? [y/N]` (Enter is no).
  Without a terminal, or over ssh with no graphical session, it only prints. It reads
  `lado.db` and never migrates it, so it works when the schema is the problem, as `lado
  doctor` does.
- **The UI**: a **Report a bug** item on the rail, above Settings, on every page (the bug
  icon alone with its tooltip when the rail is collapsed). It opens the page `/report`
  with the same warning, the whole report, **Open a new issue on GitHub ↗** and **Copy
  text**. The System panel's "Copy system info" stays as it is.
- **The error journal keeps the scrubbed form.** From now on each line of `errors.jsonl`
  also holds what `telemetry.scrub` makes of the exception (`chain`, `stack`,
  `fingerprint`, `provider`). The report reads only those fields and the line's time,
  version, `where` and type. A line of LADO 0.37 has none of them and is shown without its
  stack.
- Docs: `docs/telemetry.md` (a section on reporting a bug yourself), AGENTS.md (the new
  module, the CLI section), `docs/design/ui.md` (the rail's item and the Report a bug
  page), README, CHANGELOG.md. A minor release (0.38): a new CLI command, an API endpoint
  and a UI page.

## Scope

- A new core module `src/lado/bug_report.py`: it reads the journal, groups errors, builds
  the title and body, and builds the link within the bound.
- The scrubbed fields in `telemetry._journal`.
- `doctor.report` takes the server's state for its `Server:` line, so the CLI can describe
  a server that is not running.
- `lado bug-report` in `cli.py`.
- `GET /api/bug-report` in the UI server (`BugReport`); the rail's item, the page
  `ReportBug.tsx` and its route.
- The tests' guard against opening a browser: `BROWSER` set to a no-op in
  `tests/conftest.py`.
- Docs.

## Out of scope

- **Labels, assignees or an issue template.** GitHub applies `labels` from the form's link
  only for people with triage rights on the repository, so an outside user's issue would
  not get it. The maintainers label issues while triaging.
- **Logs as attachments** (`hooks.log`, `loop.log`, `server.log`, `update.log`). They hold
  session and agent names, message summaries and paths. The human may attach them by hand.
- **Posting the issue without a browser** (GitHub's API, `gh issue create`). That needs a
  token or a logged-in `gh`, and it would send the text without the human seeing GitHub's
  form. The human chose the form.
- **Editing the text inside LADO.** The human edits it in GitHub's form before submitting.
  LADO only shows it (the human's decision).
- **The exception's text, even scrubbed.** Messages hold paths and names in shapes no
  scrubber can know ("No such file: /Users/…/acme-billing/…"). The type, `where` and stack
  are enough to find the code.
- **The browser's own JavaScript errors.** They are not in the journal (as in LAD-32).
- **Sending the report to the statistics endpoint.** That channel is LAD-32's, with its own
  consent. A bug report is the human's own act.
- **A vulnerability report form.** The text only points to SECURITY.md's private reporting.
- **`lado stats` (LAD-34)**, which runs in parallel and touches `cli.py`, CHANGELOG.md and
  AGENTS.md. Only textual conflicts are expected, resolved by whichever branch merges
  second.

## Acceptance criteria

- AC-1: `lado bug-report` prints the "public issue" warning with the pointer to private
  vulnerability reporting, the report (a "What happened" placeholder, the system info,
  LADO's errors of the last 30 days grouped by kind, newest first), and a link
  `https://github.com/ladohq/lado/issues/new?title=…&body=…`.
- AC-2: In a terminal with a graphical session (macOS in the GUI session, or Linux with
  `DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER` set), it asks `Open it in the browser? [y/N]`.
  `y` opens the link, and Enter or `n` opens nothing. Without a terminal, or with no
  graphical session, it asks nothing and opens nothing.
- AC-3: The report holds no path, home folder, session, agent or repository name, message
  text, exception message or traceback, even when the journal's lines name them. It holds
  only types, `where`, providers, counts, days, versions and frames
  `lado/<file>:<function>:<line>` or `<external>`.
- AC-4: Each kind of error shows its type, `where`, provider (when known), its count, the
  first and last day, the LADO versions and its stack (at most 12 frames). A journal line
  without the scrubbed fields (LADO 0.37) is grouped by type and `where` and has no stack.
  Lines older than 30 days, from `errors.jsonl` or `errors.jsonl.1`, are left out.
- AC-5: The link is at most 8000 characters. When the full report does not fit, the
  oldest kinds of errors are left out of the link's body, which says `N more kinds of
  errors left out: lado bug-report prints them all`. The printed text and the page are
  never cut. The title is `<type> at <where>` of the newest error, or empty without
  errors.
- AC-6: The UI's rail has **Report a bug** above Settings on every page, also collapsed.
  It opens `/report`, which shows the warning, the whole report (with the browser line),
  **Open a new issue on GitHub ↗** (a link to the form, in a new tab) and **Copy text**.
- AC-7: Neither the CLI nor the UI server sends the report or any part of it anywhere. Their
  only network look is the daily update check that `lado doctor` and the System panel make
  too (none with `LADO_NO_UPDATE_CHECK=1`). The form opens only on the human's `y` or
  click. The test run never opens a browser.
- AC-8: `lado bug-report` works with a `lado.db` of another schema version, or with none,
  and never migrates it.
- AC-9: Each new line of `errors.jsonl` holds `chain`, `stack`, `fingerprint` and
  `provider` besides its earlier fields.
