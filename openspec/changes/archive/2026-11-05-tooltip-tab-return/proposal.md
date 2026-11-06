Task: LAD-207

## Why

Symptom (recorded by the human in Chrome on a build before LAD-192): click a session in the
list, go to another browser tab, come back: the session row's tooltip stands over the page
with the pointer nowhere near the row.

Cause: the clicked row keeps the focus. When the tab or window loses the focus the browser
sends the row a blur, and when it comes back the browser sends a focus to the same element.
`Tooltip`'s `onFocus` takes every focus that follows no press for the keyboard's, so it shows.

Checked on main ae840669 in full Chromium with real tab switches (`--browser-channel
chromium`, focus emulation off):

- click, leave, return: no tooltip. LAD-192 (`00e4edf7`, unreleased) added a `:focus-visible`
  test for another reason, and that hides the recorded steps.
- click, any key (Shift, Esc), leave, return: the tooltip shows: the key makes the browser
  count the focus as visible, though the row was never reached by the keyboard.
- keyboard focus on the row, leave, return: the tooltip shows again.

So the defect stays on main, in every tooltip of the UI, and no test covers it.

Options weighed (the human chose B, 2026-11-05):

- A: change nothing and close the task. No cost now, but the defect stays after a key press,
  and the recorded steps stay fixed only by a side effect no test holds.
- B (taken): a focus that comes back with the tab or window never shows a tooltip. One
  component, one ref. A keyboard user gets the tooltip again by Tab or the pointer.
- C: the tooltip comes back only when it was shown at the leaving. Keeps the keyboard case,
  but needs more state and still pops up over the page on the return.

## What Changes

- A focus that returns to its trigger with the tab or window shows no tooltip, whatever the
  last input was. A keyboard focus, a hover and a tap work as before.
- A UI test in full Chromium switches real tabs, as the default headless shell sends no
  focus events on a tab switch.
- docs/design/ui.md and CHANGELOG.md (0.45.0, Fixed) say so. A patch: a fix only; no API, no
  schema, no change of look, so no mockup.

## Scope

- `web/src/Tooltip.tsx`, and through it every tooltip of the UI.
- `web/src/Tooltip.test.tsx`, `tests/ui/test_session_list.py`.

## Out of scope

- A tooltip shown by the pointer while the human leaves by the keyboard (Cmd+Tab with the
  pointer on the row): it is the pointer's, and goes at the first move on the return; the
  task is about a focus that comes back.
- BACKLOG.md's "A tooltip can miss its keyboard focus after a click" (`pressed` left set): a
  defect of its own, the opposite symptom; it does not grow this task.
- Popovers and Details: they do not open on focus.

## Impact

- `web/src/Tooltip.tsx`; `web/src/Tooltip.test.tsx`; `tests/ui/test_session_list.py`.
- `docs/design/ui.md` (Tooltips); `CHANGELOG.md`.
- Spec: new capability `tooltip-focus`.
