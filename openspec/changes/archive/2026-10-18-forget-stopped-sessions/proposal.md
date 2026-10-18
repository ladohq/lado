Task: LAD-92

## Why

Over weeks of work the session list fills with stopped sessions nobody needs. Today a
session is forgotten only from its own head: open the session, press Forget…, confirm in
the window, then the next one. With twenty stopped sessions that is sixty clicks. The
core (`runtime.forget_session`), the API (`DELETE /api/sessions/{name}`) and `lado forget`
all take one session at a time, and the UI offers nothing that takes several.

Root cause: the UI's session actions are per session and live only in the session's head
(`SessionControl.tsx`; a Stop in the list row was turned down in feature/session-controls
as too easy to hit), so there is no place where the human acts on a group of sessions.

## What Changes

- **Forget stopped sessions… on the Stopped group's band**: a bin icon at the band's
  right end, in the colour of a dangerous action, whenever the group is drawn (folded or
  open). It opens a modal window listing the stopped sessions the list shows (all of
  them, or those matching the search), each with a tick, all ticked; "All N" ticks or
  clears them all. Each row says when the session stopped and, when it has open runs,
  how many. The worktrees left on disk are listed folded. The button says how many will
  be forgotten: `Forget N sessions`.
- **Open runs**: a session with open runs is forgotten only when the window's switch
  "Also forget their N open runs (…)" is on; while it is off those sessions stay and the
  button's count leaves them out. The rule of the single Forget, applied to many.
- **One at a time, each reported**: the window forgets the ticked sessions one by one
  through the existing API, each row turning to "forgotten" or to the core's reason; the
  list loses each row as it goes (the change feed). All forgotten: the window closes. Any
  refused: it stays with the reasons and a Close button. When the open session is among
  the forgotten, the page goes to `/sessions`.
- **Stop and forget** in the Stop popover of a running session: a second dangerous
  button that stops the session, then forgets it, then goes to `/sessions`. Off, with a
  line saying why, when the session has open runs.
- Docs: `docs/design/ui.md` (Launch and session control; the session list's group band),
  CHANGELOG.md under `## 0.41.0 (unreleased)`. A new minor: a UI feature (0.41.0 is
  already the next minor on main).

## Scope

- The web UI (`web/src/`): `GroupHead.tsx` (an optional action on the band),
  `Sessions.tsx` (the Stopped band's action), a new `ForgetMany.tsx` (the window),
  `SessionControl.tsx` (Stop and forget), `styles.css`, `icons.tsx` unchanged (the bin is
  `ForgetIcon`); vitest and UI e2e tests.
- `docs/design/ui.md`, CHANGELOG.md.

## Out of scope

- **Ticks in the session list itself** (a selection mode with a bar "3 selected ·
  Forget…"): shown in the mockup as variant 2 and turned down by the human; a new mode of
  the list (keyboard, search, folded group, phone) for nothing the window does not give.
- **The CLI** (`lado forget a b c`, `lado forget --stopped`): the human's decision; the
  request is about the UI, and the CLI can grow in a task of its own.
- **Forgetting sessions by themselves** (stopped longer than N days): irreversible and
  without the human's action; the human agreed to leave it out.
- **Forgetting running sessions from the window**: only stopped sessions, as today; a
  running one is stopped first (Stop and forget, or Stop).
- **A bulk endpoint in the server**: the window calls the existing preview and forget per
  session (design D2); no server, API, schema or CLI change.
- **Removing worktrees and branches**: forgetting leaves them on disk, as today; the
  window lists them.

## Acceptance criteria

- AC-1: With stopped sessions in the list, the Stopped band shows a bin button named
  "Forget stopped sessions…" (its tooltip the same), folded or open; Running and Needs you
  bands have none; with no stopped session there is no band and no button.
- AC-2: The button opens a modal window "Forget stopped sessions?" that lists every
  stopped session the list shows, ticked, each with when it stopped; with text in the
  search, only the matching ones.
- AC-3: Clearing ticks lowers the count on `Forget N sessions`; "All N" ticks or clears
  them all; with none ticked the button is off.
- AC-4: A session with open runs shows "N open run(s)"; while "Also forget their … open
  runs" is off it is not forgotten and not counted; with it on it is forgotten with its
  runs.
- AC-5: Pressing `Forget N sessions` forgets exactly the counted sessions, one at a time;
  each leaves the list; when all are gone the window closes by itself.
- AC-6: When one session is refused (e.g. resumed meanwhile), the others are still
  forgotten, the window stays open with that session's reason from the core, and Close
  closes it.
- AC-7: When the session open in the page is forgotten, the page goes to `/sessions`.
- AC-8: The Stop popover of a running session without open runs has `Stop and forget`;
  pressing it stops and forgets the session and goes to `/sessions`. With open runs the
  button is off and the popover says why.
- AC-9: The single Forget… and Stop work as before (the existing UI e2e tests pass
  unchanged).
