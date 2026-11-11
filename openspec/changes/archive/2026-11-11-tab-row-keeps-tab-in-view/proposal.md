Task: LAD-267

## Why

The UI test `tests/ui/test_narrow_layout.py::test_tab_brings_each_tab_clear_of_the_bars_ends`
sometimes fails in a parallel run (`-n auto` with other UI files): after Tab reaches the
session's last tab (Artifacts), the button › ("More tabs") does not go
(`expect(more).to_have_count(0)`). Alone, and in later runs, it passes.

Symptom reproduced: with the page's `.woff2` fonts held until Tab has reached Artifacts and
then let through, the row of tabs grows from 313 to 318 px while its scroll stays at 85 (its
end is now 90), so the row is no longer at its end, Artifacts lies partly under the fade and ›
shows and stays. Without the hold the test passed 48 times of 48 under CPU load: under the load
of a parallel run Inter arrives late, after the keyboard reached the last tab.

Cause, in the product: `SessionTabs` (`web/src/Sessions.tsx`) keeps the shown tab in view
only when the tab or the level (`data-fit`) changes, and the tab the keyboard reached only on
its focus event. The trial that runs when the row or a tab changes its width (its
`ResizeObserver`: a font arriving, the window resized) chooses the level again and looks at
the ends, but leaves the row's scroll where it was. So a late change of widths at level 4
leaves the tab the human was looking at under the fade. Not a race in the test: the test is
right to expect the last tab clear and › gone.

Options weighed:

- A (taken, the human, 2026-11-11): whenever the trial runs, the row brings the tab the
  keyboard reached, else the shown tab, back clear of the fade. One rule for every cause of
  a width change. Long-term cost: a row the human scrolled aside with ‹ › comes back to the
  shown tab when the widths change (a window resize); small, and the shown tab in view is the
  rule already.
- B: the test waits for the fonts before Tab (as LAD-222 did for the strip's badge). Cheap,
  but the product keeps the defect, and `test_the_tab_shown_stands_clear_of_the_bars_ends`
  stays exposed the same way.
- C: a row at its end (or start) stays there after a width change; a scroll in the middle is
  left alone. Fixes this case only: a tab reached in the middle can still end under the fade.

## What Changes

- When the session's tabs or their bar change width (a font arriving, the window or the
  panel resized), the tab the keyboard reached, or else the shown tab, stands clear of the
  fade again, and ‹ › follow the row's new ends.
- One way of keeping a tab in view for the tab shown, the level changing and the widths
  changing.
- A patch (0.46.1): a UI fix, no API, CLI or schema change.

## Scope

- `web/src/Sessions.tsx`: `SessionTabs`, its trial and the effect that keeps the shown tab in
  view.
- Tests: UI e2e in `tests/ui/test_narrow_layout.py`.
- `docs/design/ui.md` (the session's tabs, `data-fit`).
- CHANGELOG.md under `## 0.46.1 (unreleased)`.

## Out of scope

- The terminals' tab bar (`Terminals.tsx`): it scrolls its tabs with `scrollIntoView` and
  has no levels; no failure is known there.
- Retries of the test, or waiting for the fonts in it: the cause is in the product (the
  brief: no retries).
- A press's focus: it still moves nothing, or the row would move under the pointer and lose
  the click (LAD-218).
- The levels themselves and the fade's size: unchanged.
