Task: LAD-281

## Why

`tests/ui/test_layout.py::test_the_session_list_and_session_windows_give_the_focus_back` failed in
`ui (2)` of push run 42968074369 on `main` (2026-11-11): it opened New session, focused Cancel,
pressed Enter, and the window stayed open. The next push was green. LAD-252's CI measurement
(`docs/research/ci-speedup-check.md`, point 8) found it.

Cause: on opening, the window asks for the recent places (`GET /api/folders/recent`). When the
answer comes, it sets Where on the last place and moves the focus to Task (to Folder name without
recent places), as the requirement "The window opens on the last place" says. Under load the answer
came after the test had moved the focus to Cancel: the focus went to Task and Enter typed a newline
there. Reproduced in Chromium with the answer held back 1.5 s: it fails every time, the focus ends
in Task.

A human sees the same: one who opens the window and at once presses Tab or clicks another field
has the focus taken to Task when a slow answer comes, and what they type goes there.

## What Changes

- The window moves the focus to Task (or Folder name) on the recent places' answer only while the
  focus is still where the window put it at opening; once the human moved it within the window, it
  stays. Where is set on the last place as before.
- A UI test that holds the recent places back and moves the focus first: it fails on the old code
  every run, not only under load.

## Scope

In: the opening focus of the New session window, its UI test, `docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- The other focus moves of the window (a pick, a refusal, Check again): each follows an action of
  the human, not a late answer; Check again's already moves the focus only from the page's body.
- Retries of the UI tests: the task asks for the cause, not a retry.
- The Resume window: it opens on the session's folder without waiting for an answer.

## Acceptance

- AC-1: with the recent places held back, a focus the human moved within the window (Tab, a
  click) stays where they put it when the answer comes, and Where shows the last place.
- AC-2: with the focus untouched, the window still puts it in Task (Folder name without recent
  places) when the answer comes.
- AC-3: `test_the_session_list_and_session_windows_give_the_focus_back` passes, and the new test
  fails on the old code.

## Impact

- `web/src/Launch.tsx`; `tests/ui/test_layout.py` (or the New session window's UI test file).
- No server, API, schema or provider change. A patch release: a fix only.
