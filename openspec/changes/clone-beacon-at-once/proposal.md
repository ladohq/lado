Task: LAD-79

## Why

The vitest case "a window whose page goes away during a clone cancels it at once with a
beacon" (`web/src/Launch.test.tsx`) failed in CI (job `ui (1)`, step `make web`, PR #71,
run 38796682385): `sendBeacon` was not called at line 1688. It failed locally too, once in
40 runs at eight runs in parallel, and passed 160 runs in a row another time.

Root cause, **LADO's defect that the test exposed**: the New session window adds its
`pagehide` listener for a running clone in a passive effect (`useEffect` keyed by the
running job's id, `web/src/Launch.tsx`, `LaunchDialog`). React commits the DOM that shows
the running clone (Cancel clone, the progress line) first and runs passive effects in a
later task of its scheduler. Between the two, the window shows a clone running but a
`pagehide` cancels nothing. A probe in the test proved it deterministically: at the
DOM mutation that first shows Cancel clone the window had 0 `pagehide` listeners, after
`findByRole` resolved 1. The test passes only because Testing Library's `findByRole`
waits for a `setTimeout(0)` after the DOM matched, which usually, not always, comes after
the scheduler's task (in Node `setImmediate`; their order is not fixed). The same window
exists at the end: the listener of a clone that ended is removed in a passive cleanup,
after the DOM shows the clone's end, so a `pagehide` there would send a second beacon for
a job that is done (the test's last check, `toHaveBeenCalledTimes(1)`, can flake the same
way).

For a user the window is a few milliseconds: a tab closed right as the clone starts is
not cancelled at once and the server cancels it only after `clone.ABANDONED` (150 s).
The spec says "at once".

## What Changes

- `LaunchDialog` adds and removes its `pagehide` listener in a layout effect
  (`useLayoutEffect`) instead of a passive one, so the listener exists in the same commit
  that shows the clone running and is gone in the commit that shows it ended. Nothing else
  of the window changes.
- The vitest case checks the moments that were racy, deterministically: it sends
  `pagehide` from a `MutationObserver` callback at the DOM change that first shows Cancel
  clone (expecting the beacon to the job's cancel route) and at the change that shows the
  clone's end (expecting no second beacon), besides its present checks. It fails on the
  code before the fix every time and is not weakened (no `waitFor` around the beacon's
  check).
- The session-clone spec's requirement on the clone job gets a scenario for a page that
  goes away the moment the clone shows running.
- CHANGELOG.md: one line under `## 0.40.0 (unreleased)`.

## Scope

The `pagehide` listener's effect in `web/src/Launch.tsx`, the vitest case in
`web/src/Launch.test.tsx`, the delta of `session-clone`, CHANGELOG.md.

## Out of scope

- Fixing only the test (wrapping the beacon's check in `waitFor`, or awaiting an extra
  tick): it would hide the product's window instead of closing it, and "at once" would no
  longer be checked.
- One listener for the dialog's life that reads the running job from a ref: closes the
  window as well, but needs a ref kept in step with `job` in every `setJob` path; the
  layout effect gets the same with one word changed.
- Other `useEffect`s of the UI that a test may read one render early: no failure seen;
  each gets its own task when it flakes (LAD-44 fixed two of that kind in tests).
- The server side of the cancel (`POST /api/clones/{id}/cancel`, `clone.ABANDONED`):
  correct and covered by its own tests.
- docs/design/ui.md: it already says the page "cancels it at once"; the fix makes the code
  meet it.

## Acceptance criteria

- AC-1: In the New session window, a `pagehide` dispatched at the DOM change that first
  shows the clone running (Cancel clone) sends exactly one beacon to
  `/api/clones/<id>/cancel`.
- AC-2: A `pagehide` dispatched at the DOM change that shows the clone's end (the new
  session's page) sends no further beacon; a `pagehide` before any clone sends none.
- AC-3: The vitest case fails on the code before the fix (shown in the build report) and
  passes after it; run 200 times locally, eight runs at a time, it passes every time.
- AC-4: `make web` passes, and the pull request's CI (`ci-ok`) is green.

## Impact

- `web/src/Launch.tsx`, `web/src/Launch.test.tsx`,
  `openspec/specs/session-clone/spec.md` (at archive), CHANGELOG.md.
- No API, schema, MCP or CLI change: a patch-kind fix, listed under the unreleased
  `0.40.0`.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a proven cause, one line of code and one
  test; reviewed for precision.
- Fix the code, not only the test: the race is the product's (a few milliseconds where
  the window shows a clone running that a closed tab would not cancel), and the spec says
  "at once". Options weighed: (a) `useLayoutEffect`, one word, the listener follows the
  commit both ways; (b) a listener for the dialog's life reading a ref of the running id,
  same effect but a ref to keep in step with every `setJob`; (c) a test-only `waitFor`,
  which hides the window. (a) is chosen; its long-term cost is none beyond a comment
  that says why it is a layout effect.
- The regression check is deterministic, not statistical: `pagehide` sent from a
  `MutationObserver` at the exact DOM change, which with a passive effect always comes
  before the listener (proved by a probe during the design: 0 listeners at that change,
  1 after `findByRole`). The 200 runs are a second check, not the proof.
- Test layer: vitest (unit, layer 1): the race is between React's commit and its
  scheduler in one page; no browser-only behaviour, no process crossed. No UI e2e test.
- A delta of `session-clone` (MODIFIED, the clone job's requirement): "at once" made
  precise as "from the change that shows the clone running to the change that shows its
  end", with a scenario; no other capability names the beacon (grep of
  `openspec/specs/` for `beacon` and `pagehide`).
- Patch-kind fix; ROADMAP and Design principles unaffected (UI only, no provider, no
  second source of truth).
