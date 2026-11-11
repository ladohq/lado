## Context

`SessionTabs` (`web/src/Sessions.tsx`) chooses the level of its tabs (`data-fit`) by a trial,
`choose`, run before the first paint and again from a `ResizeObserver` on the row and on each
tab. At level 4 the row scrolls; `keepInView` sets its `scrollLeft` by `tabScroll` so a tab
stands clear of the 56 px fade at each end that has more. It is called from two places: a
layout effect on `[tab, fit]` (the shown tab) and the row's `onFocus` for a focus that is
`:focus-visible` (the tab the keyboard reached). `choose` ends with `lookAtEnds`, which sets
whether ‹ and › show from the scroll as it is. So after a width change at the same level the
scroll stays where it was: with Inter arriving after Tab reached Artifacts the row grew by
5 px and its end moved past the scroll.

## Decisions

### D1. One function picks the tab to keep: the keyboard's, else the shown one

A function of the row (`keepTabInView(row)`) finds the tab to keep: the row's tab that has the
focus and matches `:focus-visible`, else the tab with `aria-current="page"`; it calls
`keepInView` on it and then `lookAtEnds`. Both the `[tab, fit]` effect and `choose` call it,
so the level changing and the widths changing keep the same tab: otherwise a level change
right after Tab would bring the shown tab back over the one the keyboard reached. The
`onFocus` handler stays as it is (it already keeps the focused tab, and only for the
keyboard).

### D2. `choose` keeps the tab after it sets the level

`choose` calls `keepTabInView` after `box.dataset.fit` is set and before `setFit`, in place of
its `lookAtEnds`. Below level 4 the row does not scroll (`scrollWidth <= clientWidth`), so
setting `scrollLeft` changes nothing there; no level check is needed. No new observer: the
existing one already fires on the font, the window and the panel.

### D3. A press's focus still moves nothing

A tab focused by a press is not `:focus-visible`, so `keepTabInView` keeps the shown tab,
which the press is about to make the shown one; between the press and the navigation a width
change is not expected. The rule of LAD-218 (the row does not move under the pointer) holds.

### D4. The tests are UI e2e

The bug lives in real layout, a real font and a `ResizeObserver`; jsdom has none of them, so
the lowest layer that sees it is the browser (AGENTS.md, Testing, layer 4). The new test holds
the page's `.woff2` responses (`page.route`) until Tab has reached Artifacts, then lets them
through and waits for `document.fonts` to be loaded: it reproduces the flake every time
without load. A second test widens the tabs by a style (`letter-spacing`) while Flows is
shown by a click, so the shown-tab half of D1 is covered without depending on the font's
metrics. `tabScroll`'s unit test (`Layout.test.tsx`) is unchanged: the arithmetic is not
touched.

## Risks

- A row scrolled aside with ‹ › comes back to the shown tab on a width change (window
  resize, a font). Accepted by the human: the shown tab in view is the rule already.
- The font may already be in the browser's cache in the test: the route holds the response
  whatever the cache says only when the browser asks; each test's context is new (no shared
  cache), and the test asserts that the row's width did change after the release, so a test
  that no longer reproduces fails loudly instead of passing silently.
