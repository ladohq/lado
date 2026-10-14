# LAD-33 bug-report: review report

Pull request #34 `feature/lad-33-bug-report` → `main`. Scale: full, minor (0.38.0: a new
CLI command, an API endpoint and a UI page), review depth breadth first. Head reviewed
last: `17a90b0` (= the remote head); the archive commit follows it. No schema change;
CHANGELOG.md's unreleased section is `0.38.0`. `providers/`, `hooks.py`, `mcp_server.py`,
`runtime.py`, `agent_env.py` and `tests/live/` are untouched: no live tests needed.

## Rounds

- **Round 1** (`8d8537c..17a90b0`, the whole pull request): a local breadth pass over
  every lens (the spec, tests, silent failures, comments and the PR description, types, a
  general pass, the architecture against AGENTS.md), then external round 1 by the Claude
  Code Action (request at 08:05:45 UTC, "Claude finished" at 08:07 UTC): no blocker, no
  important finding. 1 of 2 external rounds used.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local: architecture (one source of truth) | the browser line's shape is written twice, `BROWSER_LINE` in Python and `browserLine` in TS, with no shared case table | confirmed | minor | declined: every output of `browserLine` matches the pattern today; if they drift, the page shows the 422's text, no leak |
| F2 | 1 | local: silent failures | `telemetry.record` now calls `scrub` before it writes the journal line, so a failing `scrub` loses the line too | confirmed | minor | declined: `scrub` only reads type names and walks the traceback, `_frames` already catches `ValueError`/`OSError`; no real input makes it fail |
| F3 | 1 | local: reuse | the CLI repeats the server's `ipaddress…is_loopback` rule for `server.json`'s host | confirmed | minor | declined: two lines; `server.json` always holds an IP literal |
| E1 | 1 | external | the journal's `type`, `where`, `lado` and frames are only checked to be strings | confirmed (hardening) | minor | declined: only LADO writes the journal; named in design.md, Risks |
| E2 | 1 | external | a failing `scrub` loses the journal line | confirmed | minor | merged into F2 |
| E3 | 1 | external | pin both forms of the `Server:` line in `test_doctor.py` | refuted | — | `tests/test_doctor.py:581-585` pins all four forms |

| Source | Confirmed | Refuted |
|---|---|---|
| local | 3 (F1, F2, F3) | 0 |
| external, Claude Code Action | 2 (E1, E2 = F2) | 1 (E3) |

## Spec check

- Every requirement of the `bug-report` delta and the modified `error-journal`
  requirement has code and a test: privacy (`test_bug_report.py`, a journal line full of
  names; the CLI; the API), the 30-day window over both files, a 0.37 line, 12 frames, 40
  kinds within 8000 characters, a 120-character title; the CLI's tty, question, `y` /
  Enter / EOF / Ctrl-C, ssh, mac `gui` / `remote`, a newer schema without migration, no
  `lado.db`, a server open to the network; the API's 422 for a foreign browser line and
  401 without a token; vitest and UI e2e for the menu item and the page; the LAD-32
  integration test checks the new journal fields.
- Every task 1.1–8.1 of `tasks.md` checked; decisions D1–D11 kept; nothing beyond the
  scope (no labels, no logs, no sending through an API).
- The PR description matches the diff; the UI matches `docs/design/ui.md` and mockup
  variant A.

## Checks

- Reviewer on `17a90b0`: `make lint` clean; `make test` 2927 passed;
  `tests/integration/test_telemetry_processes.py` 3 passed (`-m integration`); UI e2e
  `test_report_bug_page.py`, `test_system_panel.py`, `test_layout.py` 14 passed (`-m ui`);
  `make web` vitest 708 passed, types not stale; `openspec validate bug-report --strict`
  and `openspec validate --specs --strict` passed.
- CI on `17a90b0` green: check (3.10, 3.13), ui, js, smoke × 8.

## Found on the way

None.

## Not checked

- `make check` and the whole integration suite locally: green CI covers them.
- `make test-live`: no provider touched.
- A real browser opening (`webbrowser.open` on a Mac or Linux) and GitHub accepting a link
  of about 8000 characters, by hand; the 8000 bound is conservative by design.
