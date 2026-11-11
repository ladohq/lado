Task: LAD-246

## Why

Symptom: Vitest's `web/src/LoginSheet.test.tsx` > "OpenCode's sheet opens its own login
window at once, with Log out of one… when logged in" failed in CI (run 42515114557, job
`ui (1)`, step `make dist` → Vitest) with `TypeError: Cannot read properties of undefined
(reading 'url')` at `lastSocket().url` (line 238); it passes alone, in a full local run and
on the rerun. The same test failed once before in a full `make web` (BACKLOG.md, "Flaky: an
OpenCode test of `LoginSheet.test.tsx` in a full vitest run", 2026-11-06).

Cause: a race in the test, not a defect of the UI. `LoginWindow` creates its terminal's
socket (`TermLink.start()` → `new WebSocket`) in a passive effect (`useEffect`), which React
runs after it has put the window into the page. In the OpenCode test the window appears only
after the sheet's `fetch` of `POST /api/providers/opencode/login` resolves, outside `act`,
so React commits the window and schedules the effect for a later task. The test's
`await screen.findByLabelText("Text to send")` sees the field as soon as the window is in
the page (its `MutationObserver` fires on the commit) and resolves; when the effect has not
run yet, `FakeSocket.all` is empty and `lastSocket()` is `undefined`. On an idle machine the
effect almost always runs first; under CI's load it may not.

The same race was fixed in three Codex tests of the file by commit 3efcf1d0 ("Wait for the
login window's socket in the LoginSheet tests", CI run 41426024181): each waits for the
socket with `await waitFor(() => expect(FakeSocket.all).toHaveLength(1))` after the dialog
is found. The OpenCode test, which finds the window by its field rather than by its dialog,
was missed. Every test that reads the socket must remember that line, so the race comes back
with the next test that forgets it.

Options weighed:

- One more `waitFor` line in the OpenCode test: the smallest diff, but it is the fourth copy
  of a line each new test must remember; long-term cost: the next login test can repeat the
  flake.
- Taken: a helper in `web/src/fakes.ts` that waits until the n-th socket is made and returns
  it, used by every test of `LoginSheet.test.tsx` that reads a socket after an asynchronous
  open (the OpenCode test and the copies of the line). A test that reads the socket then
  cannot get `undefined`, and the wait is in one place.
- Changing `LoginWindow` to create its socket in a layout effect (`useLayoutEffect`): the
  socket would exist when the window is in the page, but the UI would change for a test, and
  xterm's `open` and the socket would run before the browser paints; rejected.

## What Changes

- `web/src/fakes.ts`: a helper `socketMade(n)` (async) that waits with Testing Library's
  `waitFor` until `FakeSocket.all` has `n` sockets and returns the n-th; a comment says why
  (the login window makes its socket in an effect, after the window is in the page).
- `web/src/LoginSheet.test.tsx`: the OpenCode test takes its first socket with
  `await socketMade(1)` instead of `lastSocket()` right after the field is found, and its
  second with `await socketMade(2)`; the Codex tests' `await waitFor(() =>
  expect(FakeSocket.all)...)` followed by `lastSocket()` become `await socketMade(n)`.
  Every assertion of the tests stays.
- BACKLOG.md: the entry "Flaky: an OpenCode test of `LoginSheet.test.tsx` in a full vitest
  run" goes: this change fixes it.

## Scope

`web/src/fakes.ts`, `web/src/LoginSheet.test.tsx`, BACKLOG.md. Nothing in the UI's code.

## Out of scope

- `web/src/LoginWindow.test.tsx` and the `window_()` helper of `LoginSheet.test.tsx`: they
  render the window themselves with `render`, which runs its effects inside `act` before it
  returns, so `lastSocket()` right after is safe; no change without a race.
- The UI's `LoginWindow` (a layout effect, or a socket made before the window shows):
  product code changed for a test; rejected above.
- Vitest retries (`retry`) or a longer timeout: they hide the race rather than close it.
- Other flaky Vitest tests in BACKLOG.md (Launch's): a different cause, their own entries.

## Acceptance criteria

- AC-1: No test of `LoginSheet.test.tsx` reads a login window's socket made by an
  asynchronous open (after a `fetch` the sheet awaits) without `await socketMade(n)`; the
  OpenCode test's first socket comes from `await socketMade(1)`. All assertions of the file
  stay.
- AC-2: The race is shown by hand once, before the fix: with the socket's creation in
  `LoginWindow`'s effect delayed by a `setTimeout` (a probe, not committed), the OpenCode
  test fails on `lastSocket().url` as in CI; with the fix and the same probe, it passes (the
  build report quotes both).
- AC-3: With the fix, `LoginSheet.test.tsx` passes 20 times in a row (`npx vitest run
  src/LoginSheet.test.tsx` from `web/`, each run's exit status read), and once more 5 times
  in a row under load (the whole Vitest suite running in parallel with it, or
  `stress`-like CPU load).
- AC-4: `make web` and `make lint` pass; CI is green.

## Impact

- Test files and BACKLOG.md only. No API, schema, MCP, CLI or UI change; no CHANGELOG.md
  line (nothing users see) and no version bump (a patch-level change, but tests only; it
  rides with 0.46.1 without gating it).

## Decisions for the record

- Scale hotfix: a defect with a clear symptom (CI's trace) and a cause shown in the code and
  in an earlier fix of the same file; review by precision.
- Fixed in the test, not in `LoginWindow`: the UI behaves right; the test assumed the socket
  exists as soon as the window is in the page.
- One helper instead of a fourth copy of the line: the wait lives in one place, next to
  `FakeSocket`, so a new login test gets it by asking for the socket; `lastSocket()` stays
  for the tests that render the window synchronously.
- Test layer: unit (Vitest, `make web`); the tests themselves, no new test.
- No delta spec: no behaviour rule changes; archived with `--skip-specs`
  (`.openspec.yaml` has `skip_specs: true`).
