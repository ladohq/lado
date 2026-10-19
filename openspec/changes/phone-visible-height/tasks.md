## 1. The app's height on a phone

- [x] 1.1 `web/src/styles.css`, section "Phone layout", the app's window: `:root[data-phone]`
  and its `body` keep `height: 100%; overflow: hidden; overscroll-behavior: none`;
  `:root[data-phone] .app` loses `100vh`/`100dvh` and takes `position: fixed; inset-inline: 0;
  top: var(--phone-top, 0px); height: var(--phone-height, 100%)` (or equivalent that keeps
  the app within `html`'s box when no variable is set). The section's comment says why
  (iOS 26 Safari: `100dvh` taller than the box `body` clips to; the keyboard). Check that
  the drawer (`.rail[data-open]`, `.menu-scrim`), the terminal over the screen, the
  session details' sheet and the artifact panel still cover the app as before.
- [x] 1.2 `web/src/phone.ts`: a hook (e.g. `usePhoneViewport(phone)`) that, while `phone`
  is set and `window.visualViewport` exists, writes `--phone-height` (its `height`, px) and
  `--phone-top` (its `offsetTop`, px) on `document.documentElement` at once and on the
  visual viewport's `resize` and `scroll`, and removes both variables and its listeners
  when `phone` turns null or on unmount. Its comment names LAD-109 and why
  (`interactive-widget` is ignored by Safari).
- [x] 1.3 `web/src/Shell.tsx`: call the hook next to the effect that mirrors `data-phone`.
- [x] 1.4 `web/src/phone.test.ts`: with a fake `visualViewport` (an `EventTarget` with
  `height` and `offsetTop`): the variables are set on a phone, follow `resize` and
  `scroll`, are removed when the layout leaves the phone and on unmount; none is set
  without a phone or without `visualViewport`. Run `make web`.

## 2. The UI e2e tests

- [x] 2.1 `tests/ui/test_phone.py`: at 390×844 on a touch screen with a question waiting
  (a long one, its list scrolling), the composer's and the card's Send button's boxes lie
  within `window.visualViewport.height`; after Expand, the card's Send button does too
  (AC-1).
- [x] 2.2 `tests/ui/test_phone.py`: an init script replaces `window.visualViewport` with a
  fake one 300 px lower than the window (and `offsetTop` 0), then dispatches `resize`: the
  `.app`'s bottom equals that height (±1 px), the top bar's top is 0, the composer and the
  Send button lie within it, the card is at most half the chat's height; growing it back
  and dispatching `resize` restores the app to the window's height (AC-2). A second case
  with `offsetTop` 120 (Safari's pan): the top bar's top is at 120 (±1 px).
- [x] 2.3 `tests/ui/test_phone.py`: `test_a_computer_keeps_its_layout` and
  `test_a_tablet_keeps_its_layout` also check that `<html>` has no `--phone-height` and the
  `.app` is not `position: fixed` (AC-3). Run `uv run pytest -m ui tests/ui/test_phone.py`
  and attach screenshots of the chat (question waiting), the expanded card and the
  shrunk app as run artifacts.
  Not done locally: Chromium does not start in the build's container (LAD-110), so the
  UI tests run in CI only, which does not keep the screenshots.

## 3. Documents

- [x] 3.1 `docs/design/ui.md`, Phone layout, "The app's window": the app is as high as the
  visible part of the window (`html`'s box, then `visualViewport` through `phone.ts`'s
  hook), and with the keyboard it shrinks above it, top bar kept; Safari ignores
  `interactive-widget` (LAD-109).
- [x] 3.2 CHANGELOG.md under `## 0.42.0 (unreleased)`: on a phone the composer, the
  waiting card and its Send button are no longer cut off by the browser's bottom bar, and
  with the keyboard open the page shrinks above it, the top bar kept.

## 4. Checks

- [x] 4.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_phone.py`
  pass; `openspec validate phone-visible-height --strict` passes; CI green on the pull
  request's last commit (AC-5). AC-4 is the human's check on an iPhone after the merge
  or on the branch. The UI tests ran in CI's two UI shards, not locally (LAD-110).
