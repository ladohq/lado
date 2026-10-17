# Forget stopped sessions Implementation Plan

**Goal:** From the Stopped group's band the human forgets all stopped sessions, or the
ones they tick, in one window; the Stop popover can stop and forget a session in one press.

**Architecture:** UI only. `GroupHead` gets an optional action; `Sessions.tsx` passes the
bin to the Stopped band; a new `ForgetMany.tsx` holds the window, which loads each
session's forget preview and forgets the counted sessions one after another through the
existing API; `SessionControl.tsx`'s `StopPopover` gets `Stop and forget`.

**Tech Stack:** React + TypeScript (Vite), vitest, pytest-playwright.

**Spec:** `openspec/changes/forget-stopped-sessions/` (proposal AC-1…AC-9, the delta's
requirements, `design.md` D1–D8); `docs/superpowers/specs/2026-10-18-forget-stopped-sessions-design.md`.
Mockup: run artifact `task/lad-92/mockup-bulk-forget.html`, variant 1 and the Stop popover.

## Global Constraints

- No server, API, schema or CLI change; `web/openapi.json` and `web/src/api.gen.ts`
  untouched.
- The forget rules stay the core's: the UI never forgets a session it has no preview for,
  and passes `force` only for a session with open runs while the switch is on.
- Forgets run one at a time, in the list's order; previews may run in parallel.
- The UI's strings are English, exactly: "Forget stopped sessions…", "Forget stopped
  sessions?", "Their history (messages, runs, notes, gates) is deleted. This cannot be
  undone.", "All N", "1 open run" / "N open runs", "Left on disk: N worktrees of M
  sessions (remove them yourself if you need to)", "Also forget their N open runs (…)",
  "While this is off, … stay.", "Forget 1 session" / "Forget N sessions", "Forgetting K of
  N…", "forgotten", "Close", "Stop and forget", "Stops it, then deletes its history for
  good", "It has open runs: stop it, then forget it from the Stopped list.",
  "Stopping…", "Forgetting…".
- CHANGELOG.md: one line under the existing `## 0.41.0 (unreleased)`.

## Review Focus

- No session is forgotten that was not counted (cleared ticks, open runs with the switch
  off, a refused preview).
- A refused forget never stops the rest and never closes the window.
- Esc and the dialog's cancel do nothing while forgetting.
- The band's button never folds the group; the strip and the other bands have none.
- Stop and forget: a refused forget leaves a stopped session and says why.

## Requirement → tests

| Requirement | vitest | UI e2e (`tests/ui/test_launch.py`) |
|---|---|---|
| The Stopped group's band offers to forget its sessions | `GroupHead.test.tsx` (action drawn, no fold) | `test_forget_stopped_sessions` (button on Stopped only); `tests/ui/test_phone.py` `test_phone_forget_stopped` |
| The window lists the stopped sessions with a tick each | `ForgetMany.test.tsx` (all ticked, All, count, refused preview, search snapshot) | `test_forget_stopped_sessions` |
| A session with open runs is forgotten only with the switch | `ForgetMany.test.tsx` (off: skipped and named; on: force) | `test_forget_stopped_sessions_open_runs` |
| The sessions are forgotten one at a time, each reported | `ForgetMany.test.tsx` (order, one refused, close, navigate) | `test_forget_stopped_sessions` |
| Stop can forget the session in one go | `SessionControl.test.tsx` | `test_stop_and_forget` |

No integration test: nothing new crosses processes.

## Task 1: The band's action (D1)

**Files:** `web/src/GroupHead.tsx`, `web/src/GroupHead.test.tsx`, `web/src/styles.css`.

- [ ] `action?: ReactNode` after the fold button; `.group-action` (26 px, danger colour,
  hover `--raised`, focus ring as `.group-fold`).
- [ ] vitest: with an action the band has the button and a click on it does not call
  `onToggle`.
- [ ] Check: `cd web && npx vitest run src/GroupHead.test.tsx`.

## Task 2: The window (D2–D5, D7)

**Files:** `web/src/ForgetMany.tsx` (new), `web/src/ForgetMany.test.tsx` (new),
`web/src/styles.css`.

- [ ] `ForgetManyDialog({ sessions, onClose })`: a modal `<dialog class="question-dialog">`
  as `ForgetDialog`; previews in parallel; rows, All, the count, the switch and its line,
  the folded worktrees; the sequential forget with marks and `Forgetting K of N…`; close
  on all forgotten, Close otherwise; `/sessions` when the route's session was forgotten.
- [ ] vitest with a fake `api`: seven sessions all ticked → `Forget 7 sessions`; two
  cleared → 5; All cleared → off; open runs, switch off → not called for them, named as
  staying; switch on → called with `force: true` for them only; a refused preview → row
  off with reason; one refused forget → others called, window stays, Close; all ok →
  `onClose`; route session forgotten → `navigate("/sessions")`; calls in list order and
  never two at once; Esc while busy ignored.
- [ ] Check: `cd web && npx vitest run src/ForgetMany.test.tsx`.

## Task 3: The Stopped band opens it (D1, D3)

**Files:** `web/src/Sessions.tsx`.

- [ ] The Stopped `Group` passes the bin (`ForgetIcon` in `Tooltip`, "Forget stopped
  sessions…", `aria-haspopup="dialog"`) as `action`, and opens `ForgetManyDialog` with
  the group's sessions as shown (search applied, all of them even when folded).
- [ ] Check: `make web`.

## Task 4: Stop and forget (D6)

**Files:** `web/src/SessionControl.tsx`, `web/src/SessionControl.test.tsx` (new).

- [ ] The second danger button; off with open runs and the line; stop, forget, navigate;
  busy texts; a refused forget shown.
- [ ] vitest: calls `stopSession` then `forgetSession(name, false)` then navigates; off
  with open runs; a refused forget shows the reason and does not navigate.
- [ ] Check: `cd web && npx vitest run src/SessionControl.test.tsx`, `make web`.

## Task 5: UI e2e

**Files:** `tests/ui/test_launch.py`, `tests/ui/test_phone.py`.

- [ ] `test_forget_stopped_sessions`: three stopped sessions and a running one; the bin on
  Stopped only; the window lists three ticked; one cleared; `Forget 2 sessions`; the two
  leave the list and `state.get_session` is None for them; the third stays; the window
  closed. Screenshots of the band and the window.
- [ ] `test_forget_stopped_sessions_open_runs`: a stopped session with an open run (a run
  started with the fake flow, then the session stopped) shows `1 open run`; with the
  switch off it stays; with it on it is forgotten.
- [ ] `test_stop_and_forget`: a running session; Stop…, `Stop and forget`; the page is
  `/sessions` and the session is gone from state.
- [ ] `tests/ui/test_phone.py` `test_phone_forget_stopped`: the phone layout's Sessions
  page shows the bin on Stopped and it opens the window.
- [ ] Check: `uv run pytest -m ui tests/ui/test_launch.py tests/ui/test_phone.py`.

## Task 6: Docs

**Files:** `docs/design/ui.md`, `CHANGELOG.md`.

- [ ] ui.md, Launch and session control: a bullet **Forget stopped sessions** (the band's
  bin, the window, the rules, decided 2026-10-18, LAD-92, mockup
  `task/lad-92/mockup-bulk-forget.html`), Stop's bullet gets `Stop and forget`; the
  Sessions bullet's band description names the bin on Stopped.
- [ ] CHANGELOG.md under `## 0.41.0 (unreleased)`.
- [ ] Check: read through.

## Task 7: Regression

- [ ] `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py
  tests/ui/test_session_list.py tests/ui/test_phone.py tests/ui/test_layout.py`,
  `openspec validate forget-stopped-sessions --strict`.
