## Decisions

### D1. The blur tells a window's leaving from a focus that moved

When the tab or window loses the focus, `document.activeElement` stays on the trigger during
its blur; when the focus moves within the page it does not (measured in Chromium; the
standard behaviour of `activeElement`). `onBlur` keeps that in a ref, `left`:
`left.current = document.activeElement === event.currentTarget`.

`onFocus` shows nothing when `left.current` is set and `event.relatedTarget` is null, the
focus of a window that comes back; every blur sets `left` anew, so it needs no clearing. The
`relatedTarget` test keeps a stale `left` from eating a later Tab: when the focus moved
elsewhere while the page was away, the row's next focus comes from an element. The existing tests of `pressed` and
`:focus-visible` stay as they are.

Rejected: `window` focus and blur listeners per tooltip (a listener per trigger, and the
window's focus comes before the element's, so it needs the same ref); one document-level
"window is returning" flag (a module state for what one blur already says).

### D2. The tests

Unit, `Tooltip.test.tsx`: `fireEvent.blur` leaves `activeElement` alone, so a really focused
button with `fireEvent.blur` and `fireEvent.focus` is the window's leaving and return. A stub
answers `:focus-visible`: jsdom's depends on the events of the tests before.

UI: the default `page` fixture runs the headless shell, which sends no blur or focus on a tab
switch: a test there passes with the defect in place (measured). The test launches its own
browser with `browser_type.launch(channel="chromium")`, part of what `playwright install
chromium` installs, here and in CI, and switches off focus emulation over CDP
(`Emulation.setFocusEmulationEnabled`) after the navigation, which turns it back on, then uses `bring_to_front` on a second page and back.
