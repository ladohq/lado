## 1. The regression test

Redesigned after the first build: the `MutationObserver` test of commit cc0cfa3 passed in
Chromium on the code before the fix (CI run 39246518194), so it does not catch the gap;
it is replaced.

- [ ] 1.1 `tests/ui/test_chat.py`: replace
  `test_a_second_esc_the_moment_the_panel_is_gone_folds_the_card` with
  `test_a_second_esc_while_the_page_is_busy_folds_the_card`, in the same place. As
  before: `running_session`, `asked_with_a_plan`, expand the card, pick `myself`, open the
  chip, wait for the panel. Before `page.goto`, `page.add_init_script` wraps
  `MessagePort.prototype.postMessage`: while `window.__slowScheduler` is true, each call is
  counted in `window.__delayedPosts` and made 1000 ms later with `setTimeout`; otherwise
  it is made at once. With the panel shown, `page.evaluate` sets `__slowScheduler` to
  true; then `page.keyboard.press("Escape")`, `expect(panel).to_have_count(0)`, at once
  `page.keyboard.press("Escape")` again, then `expect(card).not_to_have_class(expanded)`
  and `assert page.evaluate("window.__delayedPosts") > 0` (the delay took effect: should
  React's scheduler stop using `MessageChannel`, the test fails loudly instead of passing
  for nothing). The docstring says why: React's scheduler runs the router transition's
  render, and then its passive effects, in tasks posted through `MessageChannel`; delaying
  them stands for a busy runner and holds the gap between the commit that removes the
  panel and those effects open for a second, where the second Esc lands (LAD-99). No
  focus check (the proposal, Out of scope).
- [ ] 1.2 Before the fix, through CI (Chromium does not start in the container): the PR
  branch gets the new test's commit on top of cc0cfa3 with no fix (the fix commits 99b32ad
  and 18ea19a are not pushed yet: reorder them locally to go after it); push, and read
  the new test's result in the ui jobs (AC-1). Red with the card still expanded: quote
  the failure in the build report, then push the fix. Green: the gap is not the cause of
  the flake; do 1.3, then report `redesign` with its data.
- [ ] 1.3 Only when 1.2 is green: one temporary commit, not for merge, that runs
  `test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost` 100
  times in the ui jobs (`--keep-duplicates` with the node id repeated, or a temporary
  `parametrize`), with `console.debug` lines from the card's and the panel's Esc
  listeners and from each change of the card's `expanded`, each with
  `performance.now()`; on a failure the test prints the page's console. Revert it after
  the run. At most 3 CI runs for 1.2 and 1.3 together; the build report gives each run's
  id and result.

## 2. The fix

- [x] 2.1 `web/src/WaitingCard.tsx`: the effect that adds the expanded card's Esc listener
  (deps `[expanded, viewing]`) becomes a `useLayoutEffect`; its comment says why (the
  panel opens and closes in a router transition, whose passive effects come after the
  panel is already shown or gone).
- [x] 2.2 `web/src/ArtifactPanel.tsx`: the effect that adds the panel's Esc listener
  becomes a `useLayoutEffect`, so it goes in the commit that removes the panel.
- [ ] 2.3 With the fix, the new test passes in CI; `cd web && npx vitest run
  src/WaitingCard.test.tsx src/ArtifactPanel.test.tsx` passes unchanged (AC-1, AC-2).

## 3. Documents

- [x] 3.1 `docs/design/ui.md`, The waiting card: after "the next Esc folds the card" add
  that the card's and the panel's Esc listeners change in a layout effect, in the commit
  that shows or removes the panel, so a quick second Esc still folds the card.
- [x] 3.2 CHANGELOG.md, under the next patch's `## X.Y.Z (unreleased)` heading (added on
  top when missing): "A quick second Esc after closing an artifact panel over the expanded
  waiting card folds the card; it was sometimes lost."

## 4. Checks

Chromium does not start in LADO's container (no system libraries, no apt): the UI e2e
runs are CI's ui jobs.

- [ ] 4.1 In CI with the fix, one run only (it counts in 1.3's limit of 3 only when 1.3
  ran): a temporary commit, reverted after, runs
  `test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost` and
  the new test 30 times each in the ui jobs (as 1.3 repeats them), which run with `-n 2`;
  all pass; the build report gives the run's id and counts (AC-3).
- [ ] 4.2 `make lint` and `make web` pass locally; CI is green on the PR's last commit
  (AC-4).
