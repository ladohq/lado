## Context

A session's page draws nothing until the change feed's stream opens and its `reset` loads
the session list (`web/src/live.ts`). The failed test went to the Flows page and gave the
link `ship/x` Playwright's default 5 s, which also had to cover the stream's open. Once,
in CI, the stream did not open within that time; it is not reproducible locally, idle or
under load (proposal, Why).

## Decisions

### D1. The wait is for `live`, then the test's own checks

`goto_live(page, url)` calls `page.goto(url)`, then
`expect(page.get_by_role("banner").get_by_role("status")).to_have_text("live", timeout=15000)`.
The banner's status is the shell's link mark (`Shell.tsx`), on every page and at every
width (the failure's snapshot shows it at 390 px). After `live` the session list's load is
one request away, and the test's own `expect`s keep their 5 s for what is theirs to wait
for. 15 s is the bound `test_connection.py` gives a stream that comes back; the test's
limit of 120 s leaves room for four such waits.

Rejected: a longer timeout on the first `expect` of each page. It hides which wait was
long, and the record of D2 would have no place to hang.

### D2. The record of the stream's requests

Before `page.goto` the helper subscribes to the page's `request`, `response` and
`requestfailed` events and keeps, for each URL whose path is `/api/events`, the time since
the `goto` it was sent, its answer's status and time (Playwright's `response` comes with
the headers, which is what `EventSource.onopen` waits for) or the failure's text. It
unsubscribes when the wait ends, passed or not. On a timeout it raises `AssertionError`
with the URL, the status's word as it reads then, and one line per request, for example:

    the stream did not open within 15 s at http://127.0.0.1:41045/sessions/ui-a6/flows; status: connecting…
      /api/events sent at 0.31 s, no answer
    (no request of /api/events)    <- when none was sent

So the next occurrence tells the browser's side (nothing sent) from the server's (sent, no
headers) and from a refused stream (an answer of 401 or 503). No product code changes.

Rejected: the server's access log on in the UI tests (`run.py`, `access_log=False`). It
needs a test-only switch in the server, and the browser's record already tells the same.

### D3. Only this test takes the helper

The helper lives in `tests/ui/test_main_screen.py`, beside `log_in`, which other test files
import already, so a later task can use it without moving it. Only
`test_the_session_screens_changed_hold_at_every_width` changes, at its four `page.goto`
calls. The other UI tests are out of scope (proposal).

## Tests

- No new test: the change is a test's own wait. Checked by running the changed test (all 8
  of its parameters) 10 times in a row and once with `-n 2` beside the rest of its file,
  and once by hand with the stream blocked (`page.route("**/api/events**", lambda r: r.abort())`
  in a throwaway copy) to see the failure's text name the failed request. The throwaway copy
  is not committed.
- Regression: `make lint`, `uv run pytest -m ui -n auto tests/ui/test_artifacts_tab.py
  tests/ui/test_main_screen.py`; `make test` is not affected (no unit test imports these
  files) but runs as the settings' normal round.
