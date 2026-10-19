Task: LAD-99

## Why

Symptom: `tests/ui/test_chat.py::test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost`
fails now and then at its second Esc (CI run 39150756993, commit e859751, job ui (2),
`uv run pytest -m ui -n 2 --shard 2/2`): the artifact panel is gone, the focus is back on
the chip, the card is still expanded, and the second Esc leaves it expanded (`expected not
to have class expanded`). A rerun of the job passed.

Suspected cause: a defect of the UI, not of the test. The test already waits for what the
human sees (the panel gone, the chip focused) before its second Esc; the UI may not be
ready yet at that moment.

- The expanded waiting card listens for Esc on `document` only while no artifact panel is
  open (`WaitingCard.tsx`: an effect on `[expanded, viewing]`, `viewing` being `?view=` in
  the address). The listener is added and removed in `useEffect`, a passive effect.
- The panel closes by deleting `?view=` with `setSearchParams`. React Router 8 runs every
  navigation inside `React.startTransition` (`BrowserRouter`, `react-router`
  `dist/development/lib/dom/lib.js`), so the render that removes the panel is a
  transition. React's scheduler runs that render, and later the passive effects of its
  commit, in tasks it posts through `MessageChannel`.
- Between that commit and those effects the panel is gone from the page, the chip has the
  focus (the panel's `setTimeout(() => back.focus())`), and the card has no Esc listener:
  an Esc in that gap does nothing. On a busy CI runner Chromium may run Playwright's next
  key press, an input task, ahead of the scheduler's task. The same gap exists the other
  way round: after the panel opens, the card's old listener still folds the card on Esc.
- The panel's own Esc listener (`ArtifactPanel.tsx`) is also removed in a passive effect,
  so in the same gap it still runs on Esc: it schedules the focus back to the chip, which
  would take the focus from the expand button after the card folds.

What is confirmed so far (first build): the gap is real in jsdom with React's real
scheduler (a probe, not committed: with `useEffect` the card misses the Esc, with
`useLayoutEffect` it gets it). In Chromium, an Esc sent from a `MutationObserver` right
after the panel's removal did not miss (CI run 39246518194, the code before the fix):
React likely flushes the passive effects there in the same task, through a synchronous
update during that commit (the removed panel had the focus, and Chromium sends a blur),
before the observer's microtask. So that test cannot hold the gap open, and the cause is
confirmed in a browser only by a test that delays the scheduler's own tasks (the tasks).

## What Changes

- `web/src/WaitingCard.tsx`: the expanded card's Esc listener is added and removed in a
  layout effect (`useLayoutEffect`) instead of a passive one, so it changes in the same
  commit that shows or removes the artifact panel.
- `web/src/ArtifactPanel.tsx`: the panel's Esc listener likewise, so it goes in the commit
  that removes the panel.
- A new UI e2e test holds the gap open by delaying the tasks React's scheduler posts
  (standing for a busy runner), presses Esc twice and checks that the card folds; it fails
  on the code before the fix.
- The living spec says the next Esc folds the card however soon after the panel is gone.

## Scope

The two Esc listeners, one new UI e2e test, the delta of `chat-question-card`, a line in
`docs/design/ui.md` and in CHANGELOG.md. When the new test passes on the code before the
fix, the gap is not the flake's cause: the build stops with a diagnostic run of the old
test in CI and returns to the design with its data (the tasks).

## Out of scope

- A wait or retry in the test before its second Esc: the human sees the same state the
  test waits for, so the test is right; a wait would hide a real defect (a quick double
  Esc). A rerun plugin in pytest: the task forbids it, and it hides the race.
- Reading `?view=` at the moment of the key press (a ref, or a look at the page for
  `.artifact-panel`) and keeping the card's listener for as long as the card is expanded:
  it works, but it puts a second, hand-kept copy of the panel's state next to the one
  React renders (AGENTS.md, "One source of truth"), and the panel's own listener would
  still linger.
- Opting out of React Router's transitions for the panel (`flushSync` around
  `setSearchParams`): it fights the router for one component, and every other passive
  listener tied to the address would keep the gap.
- The `MutationObserver` test of the first build: it passes in Chromium on the code before
  the fix (Why), so it guards nothing.
- Shipping `useLayoutEffect` without a test seen red on the code before it: the human
  chose to confirm the cause first.
- Running the UI tests in LADO's container: Chromium lacks its system libraries there and
  apt is not available; CI's ui jobs are the browser.
- Other Esc listeners (`Shell.tsx`'s drawer, `Terminals.tsx`, menus, dialogs): none of
  them hands Esc over to a panel that opens and closes through the address; no failure
  of theirs is known.
- The focus when the second Esc comes before the panel's `setTimeout` focus (within the
  same task as the first): no human types that fast, and the new test checks the fold,
  not the focus, for that reason.

## Acceptance criteria

- AC-1: With an expanded waiting card and an artifact panel open from its chip, and
  React's scheduler tasks delayed by a second, a second Esc pressed as soon as the panel
  is gone folds the card (the new UI e2e test, which also checks that the delay took
  effect); on the code before the fix the same test fails in CI (the run's id and the
  failure quoted in the build report).
- AC-2: The first Esc still closes the panel only and leaves the card expanded with its
  picks; Esc on an expanded card with no panel still folds it with the focus on the
  expand button (the existing vitest and UI e2e tests pass unchanged).
- AC-3: With the fix, in one CI run (`-n 2`), the old test and the new one pass 30 times
  each; no retry inside pytest.
- AC-4: `make lint` and `make web` pass; CI is green on the PR's last commit.

## Impact

- `web/src/WaitingCard.tsx`, `web/src/ArtifactPanel.tsx`, `tests/ui/test_chat.py`,
  `docs/design/ui.md`, CHANGELOG.md, the living spec `chat-question-card`.
- No API, schema, MCP or CLI change. A patch: a fix only. CHANGELOG.md gets one line under
  the next patch's `(unreleased)` heading: a quick second Esc folds the expanded card.
- The parallel task LAD-102 edits `tests/ui/test_chat.py`: the new test goes right after
  the existing one, so a conflict, if any, is two added blocks next to each other.
- CI: at most 3 runs for the proof (before the fix, the diagnostic, the repeat), each with
  temporary commits reverted before review.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a suspected cause; review by precision.
- The cause is sought in the UI (a passive effect after a transition), so the UI is fixed
  and the existing test is left as it is (the task: "if the cause is in the UI, fix the
  UI").
- The fix is `useLayoutEffect` for both listeners: the listeners then follow exactly what
  React has put on the page, with no second copy of the state (see Out of scope).
- The regression test is a UI e2e test: only a real browser with React's real scheduler
  has the gap; under vitest's `act` every effect is flushed before the next event.
- The test delays `MessagePort.prototype.postMessage` (React's scheduler's tasks) by
  1000 ms from the first Esc on: it is what a busy runner does to the gap, made
  deterministic, and far longer than Playwright's round trips. It counts the delayed
  posts and asserts there were some, so a React that stops using `MessageChannel` makes
  the test fail rather than pass for nothing (AGENTS.md, "No silent drops").
- Proof through CI, at most 3 runs: Chromium does not start in the container; the human
  chose CI over a run on their Mac.
- Neutral core: a web UI change; no provider is involved.
