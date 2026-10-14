# Bug report: design

Task: LAD-33. Change: `openspec/changes/bug-report/` (proposal, deltas `bug-report` and
`error-journal`, `design.md` D1–D11). Mockup: run artifact
`task/lad-33/mockup-bug-report.html`; the human chose variant A (2026-10-14).

## Problem

A user who hits a LADO bug must find the repository, open an issue and collect the facts
by hand. LADO already has those facts (`doctor.report`) and its own errors
(`errors.jsonl`, LAD-32). But the journal's lines hold exception texts and tracebacks that
name paths, sessions and repositories, so they cannot be pasted as they are.

Root cause: no way to turn LADO's facts and errors into one report the human can read and
send, with nothing in it that names their work.

## What the user sees

In a terminal:

```text
$ lado bug-report
This text is for a new public issue on github.com/ladohq/lado. Nothing is sent until you
submit it there, and you can edit or delete any of it first. It holds no paths, session or
repository names, nor message texts. For a vulnerability, use private reporting instead:
https://github.com/ladohq/lado/security/advisories/new

### What happened

<!-- What did you do, what did you expect, and what happened instead? -->

### LADO system info
- LADO 0.38.0 (uv tool), Python 3.13.1
- OS: macOS 15.6 (arm64)
- Update: up to date (checked 2026-10-14 09:12)
- Statistics: on
- Server: running, loopback only, schema 26
- Home: default home
- tmux: 3.5a, socket lado
- git: 2.47.1
- Providers:
  - claude: 2.1.296 (tested 2.1.296)
  - codex: not installed
  - kilo: not installed
  - opencode: 1.18.35 (tested 1.18.35)
- Kits: sdlc 1.4.0 (official marketplace), default 0.38.0 (built-in)
- Sessions: 2 running, 5 stopped

### LADO errors (last 30 days, 2 kinds)
- KeyError at hook:turn_end (claude), 3 times, 2026-10-12 to 2026-10-14, LADO 0.37.0, 0.38.0
  - lado/hooks.py:handle:212
  - lado/hooks.py:_idle:340
  - <external>
- sqlite3.OperationalError at loop, once, 2026-10-13, LADO 0.37.0
  - lado/loop.py:run:118
  - <external>

Open a new issue: https://github.com/ladohq/lado/issues/new?title=KeyError%20at%20hook%3Aturn_end&body=...
Open it in the browser? [y/N]
```

The question comes only in a terminal where a browser can show. In the UI, **Report a
bug** sits on the rail above Settings on every page. It opens a page with the same
warning, the report (with a `- Browser:` line), **Open a new issue on GitHub ↗** and
**Copy text**.

## Options

1. A second copy button with the errors, and no link: the least code, but the human still
   pastes by hand.
2. **Chosen**: one report and a link to GitHub's new issue form, built by the core for the
   CLI and the UI. The human opens the form and submits it.
3. Posting through GitHub's API or `gh`: needs a token or a login, and it skips the form
   where the human sees the issue. Rejected.

## The rules that keep it private

- The report reads from the journal only `at`, `lado`, `where`, `type`, `chain`, `stack`,
  `fingerprint` and `provider`. It never reads `message`, `traceback`, `session` or
  `agent`.
- `stack` is `telemetry.scrub`'s, written at capture from now on (D2). A 0.37 line has
  none and shows no frames, rather than a traceback parsed back.
- The browser line comes from the page and is checked against `browserLine`'s shape
  (D5).
- Nothing goes out but by the human's `y` or click, and the issue goes up only when they
  submit GitHub's form.

## The bound

GitHub's form takes the text in its URL, safe up to about 8 KB. The link keeps the newest
kinds of errors that fit, and counts the rest in its body (D4). The printed report and the
page are never cut.

## The decisions in short

D1 `bug_report.py` builds the text and the link for both sides. D2 the journal keeps the
scrubbed form. D3 the text's layout. D4 the link, its bound and title. D5 `GET
/api/bug-report?browser=`. D6 `doctor.report(system, server)`. D7 `lado bug-report` and
when it asks. D8 the UI's rail item and page. D9 `BROWSER=true` in the tests. D10 the
test layers. D11 version 0.38.0 and the docs.
