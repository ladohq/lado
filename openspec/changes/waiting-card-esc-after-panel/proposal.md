Task: LAD-99

## Why

Symptom: `tests/ui/test_chat.py::test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost`
fails now and then at its second Esc (CI run 39150756993, commit e859751, job ui (2),
`uv run pytest -m ui -n 2 --shard 2/2`): the artifact panel is gone, the focus is back on
the chip, the card is still expanded, and the second Esc leaves it expanded (`expected not
to have class expanded`). A rerun of the job passed.

Cause: a defect of the UI, not of the test. The test already waits for what the human
sees (the panel gone, the chip focused) before its second Esc; the UI is not ready yet at
that moment.

- The expanded waiting card listens for Esc on `document` only while no artifact panel is
  open (`WaitingCard.tsx`: an effect on `[expanded, viewing]`, `viewing` being `?view=` in
  the address). The listener is added and removed in `useEffect`, a passive effect.
- The panel closes by deleting `?view=` with `setSearchParams`. React Router 8 runs every
  navigation inside `React.startTransition`, so the render that removes the panel is a
  transition, and React runs the passive effects of a transition's commit in a later task,
  after the browser paints.
- Between that commit and those effects the panel is gone from the page, the chip has the
  focus (the panel's `setTimeout(() => back.focus())`), and the card has no Esc listener.
  An Esc in that window does nothing. On a loaded CI runner the window is long enough for
  Playwright's next key press. The same window exists the other way round: in the passive
  gap after the panel opens, the card's old listener still folds the card on Esc.
- The panel's own Esc listener (`ArtifactPanel.tsx`) is also removed in a passive effect,
  so in the same window it still runs on Esc: it schedules the focus back to the chip,
  which would take the focus from the expand button after the card folds.

## What Changes

- `web/src/WaitingCard.tsx`: the expanded card's Esc listener is added and removed in a
  layout effect (`useLayoutEffect`) instead of a passive one, so it changes in the same
  commit that shows or removes the artifact panel.
- `web/src/ArtifactPanel.tsx`: the panel's Esc listener likewise, so it goes in the commit
  that removes the panel.
- A new UI e2e test sends the second Esc at the very moment the panel leaves the page and
  checks that the card folds.
- The living spec says the next Esc folds the card however soon after the panel is gone.

## Scope

The two Esc listeners, one new UI e2e test, the delta of `chat-question-card`, a line in
`docs/design/ui.md` and in CHANGELOG.md.

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
- Other Esc listeners (`Shell.tsx`'s drawer, `Terminals.tsx`, menus, dialogs): none of
  them hands Esc over to a panel that opens and closes through the address; no failure
  of theirs is known.
- The focus when the second Esc comes before the panel's `setTimeout` focus (within the
  same task as the first): no human types that fast, and the new test checks the fold,
  not the focus, for that reason.

## Acceptance criteria

- AC-1: With an expanded waiting card and an artifact panel open from its chip, an Esc
  sent at the moment the panel leaves the page folds the card (the new UI e2e test); on
  the code before the fix the same test fails (shown by hand once, the failure quoted in
  the build report, the probe not committed).
- AC-2: The first Esc still closes the panel only and leaves the card expanded with its
  picks; Esc on an expanded card with no panel still folds it with the focus on the
  expand button (the existing vitest and UI e2e tests pass unchanged).
- AC-3: `test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost`
  passes 30 times in a row run alone (`-n0`) and `tests/ui/test_chat.py` passes 5 times
  in a row with `-n 2`, each run's exit status read; no retry inside pytest.
- AC-4: `make lint`, `make web` and `uv run pytest -m ui tests/ui/test_chat.py` pass; CI
  is green.

## Impact

- `web/src/WaitingCard.tsx`, `web/src/ArtifactPanel.tsx`, `tests/ui/test_chat.py`,
  `docs/design/ui.md`, CHANGELOG.md, the living spec `chat-question-card`.
- No API, schema, MCP or CLI change. A patch: a fix only. CHANGELOG.md gets one line under
  the next patch's `(unreleased)` heading: a quick second Esc folds the expanded card.
- The parallel task LAD-102 edits `tests/ui/test_chat.py`: the new test goes right after
  the existing one, so a conflict, if any, is two added blocks next to each other.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom and a found cause; review by precision.
- The cause is in the UI (a passive effect after a transition), so the UI is fixed and
  the existing test is left as it is (the task: "if the cause is in the UI, fix the UI").
- The fix is `useLayoutEffect` for both listeners: the listeners then follow exactly what
  React has put on the page, with no second copy of the state (see Out of scope).
- The regression test is a UI e2e test: only a real browser with React's real scheduler
  has the gap between a transition's commit and its passive effects; under vitest's `act`
  every effect is flushed before the next event, so a unit test cannot catch it.
- The test sends the second Esc from a `MutationObserver` on the panel's removal: its
  callback is a microtask right after the commit, before any later task, so the test is
  deterministic rather than a timing hope.
- Neutral core: a web UI change; no provider is involved.
