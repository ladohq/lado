Task: LAD-109

## Why

Symptom: in the web UI on an iPhone (Safari of iOS 26, its address bar floating at the
bottom), the bottom of a session's chat is cut off and cannot be scrolled to: the
composer's lower half (the second screenshot of the task) and, with the waiting card
expanded, its "Send answer to …" button (the first). Below the cut Safari draws a solid
bar up to its own controls.

Suspected cause (from the CSS and the screenshots; not reproduced in a browser, as
Chromium does not start in the analyst's container, and an emulator does not reproduce
Safari's bars): the phone layout (LAD-95, `phone-layout`) makes the window not scroll,
`html` and `body` `height: 100%; overflow: hidden`, and sizes the app `100dvh`. On iOS 26
Safari `100dvh` is taller than the box of `html`, which ends above Safari's bottom bar, so
`body` clips the app's last 40-50 px: the composer, or the expanded card's Send row. The
on-screen keyboard has a second gap: the viewport's `interactive-widget=resizes-content`
keeps the composer above the keyboard on Android, but Safari ignores it and pans the
whole page up instead, the top bar off the screen while the human types.

## What Changes

- On a phone the app is as high as the part of the window the human sees, in place of
  `100dvh`, so the browser's bars never cut it: fixed in place, its height and top from
  the visual viewport (below); without one (an old browser) the viewport's height.
- On a phone a small hook of `phone.ts` follows `window.visualViewport` (its height and
  its offset from the page's top) and puts them on `<html>` as two CSS variables; the
  app takes its height and its top from them. With the keyboard open, the app shrinks to
  the part above it: the top bar stays, the feed and the card get less room (the card
  still at most half the chat, its list scrolling), and the composer and the card's Send
  row stay above the keyboard; on Android, where the window already resizes, the values
  are the same as without the hook.
- A computer is not touched: every rule is under `:root[data-phone]`, and the hook runs
  only while the phone layout is on.
- `docs/design/ui.md`, Phone layout, "The app's window": says the above in place of
  `100dvh`.

## Scope

`web/src/phone.ts` (the hook), `web/src/Shell.tsx` (calls it next to `data-phone`),
`web/src/styles.css` (the section "Phone layout"), their unit tests, a UI e2e test in
`tests/ui/test_phone.py`, `docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- `viewport-fit=cover` and `env(safe-area-inset-*)` padding: the content would run under
  Safari's glass bar, and the safe-area insets do not include that bar's height, so the
  composer would still sit under it; without `cover` Safari keeps the page out of the
  notch and the home indicator itself.
- A computer's narrow window (a mouse, ≤ 900 px), which scrolls as a page: not in the
  task, and its window can be scrolled to the cut part.
- The web app installed to the home screen (standalone mode): LADO has no manifest for it.
- Safari's own keyboard accessory bar and its tint: Safari's chrome, outside the page.
- Variant A for the keyboard (CSS only, Safari pans the page and the top bar goes off the
  screen while typing): turned down by the human in favour of the app shrinking above the
  keyboard.

## Acceptance criteria

- AC-1: On a phone (Chromium with a touch screen, 390×844) with a question waiting, the
  composer and the card's Send button lie wholly within the visible part of the window,
  without scrolling; with the card expanded, its Send button too.
- AC-2: When the visible part of the window is smaller than the window (the keyboard or a
  browser bar; in the test, `window.visualViewport` replaced by one 300 px lower), the
  app's bottom is at the visible part's bottom, the top bar at its top, the composer and
  the card's Send button within it, the card at most half the chat's height; when it grows
  back, the app does too.
- AC-3: With a mouse at any window size, and on a tablet, the layout is as before: the
  app's height and position are unchanged and `<html>` has no variable of the hook.
- AC-4: By hand on an iPhone in Safari with the bottom bar (the task's screenshots): the
  composer, a question's and a gate's card, and the expanded card's Send button are whole
  above Safari's bar; tapping the composer keeps the top bar in sight and the composer
  above the keyboard.
- AC-5: `make lint`, `make web`, the unit tests and `uv run pytest -m ui
  tests/ui/test_phone.py` pass; CI is green on the pull request's last commit.

## Impact

- Web UI only: no API, schema, MCP or CLI change. A fix: CHANGELOG.md gets a line under
  `## 0.42.0 (unreleased)`; the version is not bumped here (a patch-level change).
- The parallel task LAD-108 edits the session's head in the web UI: it may touch
  `styles.css`'s phone section (the top bar) and `Shell.tsx`; this change keeps to the
  section's frame rules (`.app`, `html`, `body`) and to one call in `Shell.tsx`, so a
  conflict, if any, is small.

## Decisions for the record

- Scale hotfix: a defect with a clear symptom; one CSS section, one hook; review by
  precision.
- The fallback height, without a visual viewport, is `100%` of the viewport (the fixed
  app's containing block), not `100svh`: `svh` assumes the bars expanded and is reported
  unreliable on iOS 26. Being fixed, the app is not clipped by `body`; no phone browser of
  today lacks `visualViewport`, so the fallback is not met on a phone.
- The hook writes CSS variables on `<html>` (`--phone-height`, `--phone-top`) rather than
  a React state: the frame's CSS stays the one place that sizes the app, and a resize does
  not render the tree again.
- The app follows `visualViewport.offsetTop` too (`position: fixed` at that top): Safari
  pans the page when the keyboard opens even with `overflow: hidden`, and the top bar
  must stay in sight.
- No `visualViewport` (an old browser): the variables are not set and the CSS fallback
  (`100%`, top 0) applies.
- Test layers: unit (vitest) for the hook (sets and clears the variables, follows
  `resize` and `scroll`, nothing without a phone); UI e2e for the layout, as only a
  browser lays it out; Safari's bars themselves only by hand (AC-4), no automated
  browser here reproduces them.
