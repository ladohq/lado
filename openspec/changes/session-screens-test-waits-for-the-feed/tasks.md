## 1. The helper

- [x] 1.1 `goto_live(page, url)` in `tests/ui/test_main_screen.py`, beside `log_in`: goes to
  the URL, waits up to 15 s for the banner's status `live` (D1), records the page's requests
  of `/api/events` while it waits and fails with the record on a timeout (D2); a `live` later
  than 2 s passes with the record as a `UserWarning` (D4). Check: by hand, in a throwaway
  copy of the test: with `/api/events` aborted by `page.route`, the failure names the URL,
  `connecting…` and the failed request; with the stream held 3 s by `page.route`, the test
  passes and pytest's warnings summary shows the record; the copy is not committed.

## 2. The test

- [x] 2.1 `test_the_session_screens_changed_hold_at_every_width` goes to its four pages through
  `goto_live` (D3). Check: `uv run pytest -m ui -n0 tests/ui/test_artifacts_tab.py -k
  session_screens_changed` 10 times in a row (a shell loop), and `uv run pytest -m ui -n 2
  tests/ui/test_artifacts_tab.py` once.

## 3. Docs

- [x] 3.1 docs/testing.md, the UI e2e layer: a sentence that a test whose first check of a page
  must not also wait for the change feed goes there with `goto_live`, which waits for `live`,
  names the stream's requests when it does not come, and warns with them when it comes after
  more than 2 s. Check: read it.

## 4. Regression run

- [x] 4.1 `make lint`, `make test`, `uv run pytest -m ui -n auto tests/ui/test_artifacts_tab.py
  tests/ui/test_main_screen.py`, `openspec validate session-screens-test-waits-for-the-feed
  --strict`, the trial archive with `--skip-specs`.
