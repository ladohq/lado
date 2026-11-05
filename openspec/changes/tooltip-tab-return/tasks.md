## 1. The failing tests

- [x] 1.1 `web/src/Tooltip.test.tsx`, requirement "A focus that returns with the window shows
  no tooltip": a button really focused (`button.focus()` after a press, and without one, with
  `:focus-visible` as jsdom gives it), then `fireEvent.blur` and `fireEvent.focus` with
  `activeElement` unchanged and no `relatedTarget`: no tooltip; one shown before the blur goes.
  Fails before 2.1. Run: `cd web && npx vitest run src/Tooltip.test.tsx`.
- [x] 1.2 Same file, requirement "A focus that moves within the page still shows a tooltip":
  after that return, a blur with the focus really gone and a focus with a `relatedTarget`
  shows it; `fireEvent.mouseEnter` shows it after `TOOLTIP_DELAY_MS`; a `left` gone stale (the
  focus moved away while the page was away) does not eat the next focus from another element.
- [x] 1.3 `tests/ui/test_session_list.py`, marker `ui`, all scenarios of both requirements in
  full Chromium with real tab switches (design D2). The clicked row and the row with Shift
  scenarios: Shift fails before 2.1. Run: `uv run pytest -m ui -n0 tests/ui/test_session_list.py
  -k returns`.

## 2. The fix

- [x] 2.1 `web/src/Tooltip.tsx`: the ref `left`, set in `onBlur`, read in `onFocus`
  (design D1); the header comment says a focus that comes back with the window shows nothing.
  1.1 to 1.3 pass.
- [x] 2.2 `make lint`, `make test`, `make web` and `uv run pytest -m ui
  tests/ui/test_session_list.py tests/ui/test_sessions_strip.py` green.

## 3. Docs

- [x] 3.1 `docs/design/ui.md`, **Tooltips**: a focus that returns with the tab or window shows
  no tooltip; Tab or the pointer does (LAD-207).
- [x] 3.2 `CHANGELOG.md`, `## 0.45.0 (unreleased)`, Fixed: a bold title and at most three lines
  in the user's words (a tooltip no longer pops up when you come back to LADO's tab).
- [x] 3.3 `openspec validate tooltip-tab-return --strict` passes.
