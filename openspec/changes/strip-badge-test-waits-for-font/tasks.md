## 1. The test

- [ ] 1.1 `tests/ui/test_narrow_layout.py`, `test_the_strips_badges_tell_task_sessions_apart`
  (UI e2e, the layer of the test itself): after `expect(icons).to_have_text(...)` and before
  the check, `icons.nth(2).evaluate("e => document.fonts.load(getComputedStyle(e).font,
  e.textContent).then(() => true)")`, with a comment on why: the text fills the box exactly,
  and the fallback font is wider. The check stays as it is.
- [ ] 1.2 The node id passes 20 times in a row with `-m ui -n0`; say so in `build-report`.
  Before the fix it failed 1 run in 5.
- [ ] 1.3 The same 20 runs pass with the response of the IBM Plex Mono file delayed by 0.7 s
  (a `page.route` kept out of the commit); say so in `build-report`.

## 2. The backlog

- [ ] 2.1 `BACKLOG.md`: the entry "Flaky UI test:
  `test_the_strips_badges_tell_task_sessions_apart`" is gone, and the entries around it are
  untouched. `grep -c test_the_strips_badges BACKLOG.md` says 0.

## 3. The checks

- [ ] 3.1 `make lint` and `uv run pytest -m ui tests/ui/test_narrow_layout.py` green; report
  the tests as numbers.
