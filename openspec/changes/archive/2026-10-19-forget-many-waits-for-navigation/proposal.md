Task: LAD-111

## Why

Symptom: the vitest test `web/src/ForgetMany.test.tsx` "when the session open in the page
is forgotten, the page goes to /sessions" failed once in CI with "Unable to find an
element with the text: No session open" (PR #107, run 39247496368, attempt 2, job ui (1),
step `make web`); attempt 1 and local runs passed.

Cause, found and reproduced: after the forgets, `ForgetManyDialog.forget`
(`web/src/ForgetMany.tsx`) calls `navigate("/sessions")` and then `setFinished(true)` in
the same continuation. React Router 8 applies a navigation inside `React.startTransition`
(`MemoryRouter` and `BrowserRouter` alike, unless `useTransitions={false}`), while
`setFinished` is an urgent update. React commits the urgent update first: the window
shows Close, and the page under it switches to `/sessions` in a later render. The test
awaits only Close and then checks the page synchronously with `getByText`, so when the
transition's render lands after `findByRole` resolves, the check fails.

Reproduced locally: the test repeated 300 times (`test.each`) with the CPU loaded by
eight busy processes failed once (run 58). With the check changed to
`await screen.findByText("No session open")`, 1000 of 1000 passed under the same load.

The product is right: the page does go to `/sessions`, a render later than Close appears,
which no user can tell apart. Only the test assumes both land in one render.

## What Changes

- The test waits for the page under the window to show `/sessions`
  (`await screen.findByText("No session open")`) after Close appears, instead of
  checking it synchronously.
- At the human's word at the design's approval, the test "the sessions are forgotten one
  at a time in the list's order, each reported, and Esc waits" checks the page the same
  way (`await screen.findByText`) after `onClose` is called.

## Scope

`web/src/ForgetMany.test.tsx`, the two tests. Nothing in `src/` or in the UI's code.

## Out of scope

- `useTransitions={false}` on the test's `MemoryRouter`: the test would then route
  differently from the app's `BrowserRouter`, which keeps transitions, and could pass
  where the app behaves otherwise.
- Changing `ForgetMany.tsx` so the navigation and Close land in one render (`flushSync`
  around `navigate`, or showing Close only after the address changed): no user sees the
  one-render gap, and the change would add code that only a test needs.
- A retry in vitest (`retry`) or a rerun: the task forbids retries, and a retry would hide
  a real failure.
- Searching the other vitest tests for the same pattern (a synchronous check of the page
  after a navigation): not part of this task; the reviewer lists any found under "Found
  on the way".

## Acceptance criteria

- AC-1: The test awaits "No session open" after Close appears; its other steps and
  checks stay as they are; the "one at a time" test awaits it the same way after
  `onClose`.
- AC-2: Repeated at least 1000 times with the CPU loaded (a temporary, uncommitted
  `test.each` over the test, as in Why), the test passes every time; the build report
  gives the count and the load.
- AC-3: `make web` passes, and CI is green on the pull request's last commit.

## Impact

- `web/src/ForgetMany.test.tsx` only. No API, schema, MCP, CLI or UI change; no
  CHANGELOG.md line (nothing users see) and no version bump.
- No delta: no behaviour rule changes; the change is archived with `--skip-specs`.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom, its cause reproduced; review by precision.
- The fix is in the test, not the product: the product's order (Close, then the page) is
  a React Router 8 transition by design and invisible to users.
- `findByText` (a `waitFor` with the default 1 s timeout) over a bigger timeout or a
  `waitFor` around the check: the transition lands in the next scheduler task, far within
  the default.
- Test layer: unit (vitest, jsdom); the race is between React's urgent and transition
  updates, which vitest with React's real scheduler sees.
