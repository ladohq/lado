## 1. The regression test

- [ ] 1.1 `tests/ui/test_chat.py`, right after
  `test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost`: a new
  test `test_a_second_esc_the_moment_the_panel_is_gone_folds_the_card`. As that test:
  `running_session`, `asked_with_a_plan`, expand the card, pick `myself`, open the chip,
  wait for the panel. Then, with `page.evaluate`, put a `MutationObserver` on
  `document.body` (`childList`, `subtree`) that, on the first mutation after which no
  `.artifact-panel` is in the page, disconnects and dispatches
  `new KeyboardEvent("keydown", {key: "Escape", bubbles: true})` on `document`. Press Esc
  with `page.keyboard`. Expect the panel gone and the card not `expanded`. A docstring
  says why: the observer's microtask comes right after the commit that removes the panel,
  before React's passive effects of that transition (LAD-99). No focus check (the
  proposal, Out of scope).
- [ ] 1.2 By hand, before the fix: run the new test alone on the code before the fix
  (`uv run pytest -m ui -n0 tests/ui/test_chat.py -k second_esc`): it fails with the card
  still expanded. Quote the failure in the build report (AC-1).

## 2. The fix

- [ ] 2.1 `web/src/WaitingCard.tsx`: the effect that adds the expanded card's Esc listener
  (deps `[expanded, viewing]`) becomes a `useLayoutEffect`; its comment says why (the
  panel opens and closes in a router transition, whose passive effects come after the
  panel is already shown or gone).
- [ ] 2.2 `web/src/ArtifactPanel.tsx`: the effect that adds the panel's Esc listener
  becomes a `useLayoutEffect`, so it goes in the commit that removes the panel.
- [ ] 2.3 The new test passes; `cd web && npx vitest run src/WaitingCard.test.tsx
  src/ArtifactPanel.test.tsx` passes unchanged (AC-1, AC-2).

## 3. Documents

- [ ] 3.1 `docs/design/ui.md`, The waiting card: after "the next Esc folds the card" add
  that the card's and the panel's Esc listeners change in a layout effect, in the commit
  that shows or removes the panel, so a quick second Esc still folds the card.
- [ ] 3.2 CHANGELOG.md, under the next patch's `## X.Y.Z (unreleased)` heading (added on
  top when missing): "A quick second Esc after closing an artifact panel over the expanded
  waiting card folds the card; it was sometimes lost."

## 4. Checks

- [ ] 4.1 `uv run pytest -m ui -n0 tests/ui/test_chat.py -k esc_closes_the_topmost` 30
  times in a row and `uv run pytest -m ui -n 2 tests/ui/test_chat.py` 5 times in a row,
  each run's exit status read (not piped); all pass; the build report gives the counts
  (AC-3).
- [ ] 4.2 `make lint`, `make web`, `uv run pytest -m ui tests/ui/test_chat.py` pass (AC-4).
