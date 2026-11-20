Task: LAD-305

## Why

Symptom: `tests/ui/test_artifacts_tab.py::test_the_session_screens_changed_hold_at_every_width[chromium-light-390]`
failed once in CI at line 203 (PR #344, run 44615535193, attempt 1, job `ui (2)`, head
`bf4bea6e`): 5 s after `page.goto(.../sessions/<s>/flows)` the link `ship/x` was not there.
The page's aria snapshot showed the banner with `status: connecting…` and an empty `main`.
That pull request did not touch the test, and the rerun of the failed jobs passed.

Why the page was empty: the web UI loads the session list only on the change feed's `reset`
(`web/src/live.ts`, `load()` on `reset`; the first load and the load after a gap are one
path). The `reset` comes only after `/api/events` opens. Until then the session's page does
not know the session and draws nothing. So for those 5 s the feed's stream did not open:
`connecting…` is the word for "before the first open" (`Link`).

What is ruled out:

- **Load.** Measured on 2026-11-20 with a throwaway test in the failed test's exact order
  (log in, set the theme, go to Flows at once), 390×844, two fake sessions: idle, the
  stream opened in about 20 ms and `ship/x` showed in about 0.2 s. Under 48 busy CPU loops,
  a disk writer with fsync and 6 xdist workers, 52 runs all passed, the slowest at 0.4 s
  to `live` and 0.4 s more to the link. A 5 s stall is not a slow path stretched by load.
- **A pattern.** In the last 200 CI runs (since 2026-11-12) this is the only failed UI job
  whose page hung at `connecting…`.

Where the stall was (the browser never sent the request, the server took 5 s to answer its
headers, or SQLite's busy wait in `feed.check` or the `database` dependency) cannot be told
from this one case: the server runs with `access_log=False`, and the test's failure records
only the aria snapshot.

Options weighed:

- A (taken, the human's choice, #7634): the test waits, after each `goto`, for the banner's status
  to read `live`, up to 15 s (the bound `test_connection.py` already uses for a stream
  coming back). While it waits it records the browser's requests of `/api/events` (sent,
  headers answered with their status, or failed with the reason), and a timeout fails with
  that record. A `live` that comes but takes more than 2 s passes and leaves the same
  record as a warning in the run's log (the human's addition at `design_ok`), so a stall
  shorter than the bound is seen too. Long-term cost: one helper of the UI tests; a stall
  longer than 15 s fails again, but with the side it happened on, which is what a cause
  task needs.
- B: the session's pages load their lists over plain HTTP at once, not only on the feed's
  `reset`, so a slow stream leaves a page showing the session. A product change visible to
  the human, against `live.ts`'s one load path, with every page to check; not a fix of a
  flake.
- C: a 15 s `expect` timeout for every UI test. Every real failure of the UI tests waits
  three times longer, and no evidence comes of it.

## What Changes

- **A helper `goto_live(page, url)`** in `tests/ui/test_main_screen.py`, next to `log_in`:
  it goes to the URL and waits up to 15 s for the banner's status to read `live`. While it
  waits it records each request of `/api/events` the page makes and what came of it; on a
  timeout it fails with the record and the status's word. When `live` comes after more than
  2 s, the test goes on and the helper issues a `UserWarning` with the same record and the
  time `live` took, which pytest's warnings summary prints in the CI log of a passed run.
- **The test `test_the_session_screens_changed_hold_at_every_width`** goes to each of its
  four pages (the session's Flows and Artifacts, the empty session's Flows and Artifacts)
  through `goto_live`. Its checks stay as they are.

## Scope

In: `tests/ui/test_main_screen.py` (the helper), `tests/ui/test_artifacts_tab.py` (the test),
`docs/testing.md` (the UI e2e layer names the helper).

## Out of scope

- **Other UI tests' `page.goto`**: every UI test's first screen waits for the same stream,
  but this one stall in 200 runs is the only one seen; moving them all to the helper is a
  wide change with nothing to show for it now. A test that fails the same way later takes
  the helper in its own task.
- **The product's behaviour while the stream does not open** (option B): a change the human
  sees, its own task if wanted.
- **The stall's cause**: not findable from one case; the helper's record is what the next
  occurrence brings for a task of its own.
- **The server's access log in tests**: the browser's record already tells whether the
  request went out and when its answer's headers came; the server's log would be a second
  record of the same.

## Impact

- Users see nothing: tests only. No CHANGELOG line.
- Version: patch.
- No API, MCP, CLI or schema change; no delta spec (no behaviour rule changes): archive with
  `--skip-specs`.
