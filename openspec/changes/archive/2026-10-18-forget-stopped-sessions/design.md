## Context

What forgetting a session is now (main at 0.41.0 unreleased):

| Piece | Where | Today |
|---|---|---|
| Core | `runtime.forget_preview`, `runtime.forget_session` | one stopped session; open runs only with `force`; worktrees and branches left on disk |
| API | `GET /api/sessions/{name}/forget-preview`, `DELETE /api/sessions/{name}?force=` | one session per call, guarded like the composer |
| CLI | `lado forget <session> [--force]` | one name |
| UI | `SessionControl.tsx` `ForgetDialog` | only in the session's head; after it, `/sessions` |
| UI | `SessionControl.tsx` `StopPopover` | `Stop <name>`, from `stop-preview` |
| List | `Sessions.tsx` `Group`, `GroupHead.tsx` | the Stopped band folds; no action on it |

Root cause: actions on sessions exist only one session at a time in its head, so the UI
has no place to act on several.

## Options

1. **Chosen: a window from the Stopped band that forgets the ticked sessions, calling the
   existing API per session.** Cost: one component (`ForgetMany.tsx`), an optional action
   on `GroupHead`, a second button in `StopPopover`; no server change. N previews and N
   forgets are N requests to a local server: tens of milliseconds each.
2. **A selection mode in the list** (ticks on rows, a bar below). Cost: a new state of the
   list that touches links, keyboard, search, folded groups, the strip and the phone.
   Turned down by the human (mockup variant 2).
3. **A bulk endpoint** (`POST /api/sessions/forget` with names, or `lado forget a b c`).
   Cost: a new API model, `make web-types`, a second path into the same core that must
   report per session anyway. Nothing the UI needs; the human left the CLI out.

Held against AGENTS.md's Design principles and ROADMAP:

- **Neutral core**: UI only; no provider is involved (forgetting touches LADO's state).
- **One source of truth**: the rules (stopped only, open runs only with force) stay in
  `runtime.forget_session`; the window reads the preview and calls the forget, and shows
  the core's reasons. The stopped sessions come from the list's own loaded `SessionInfo`,
  the same the Stopped group is made of.
- **No silent drops**: every ticked session ends as "forgotten" or with its reason; one
  skipped for its open runs is named as staying before the press.
- **Only what is used**: no new field, endpoint or setting.
- ROADMAP stage 7 (the desktop app and its web UI); nothing in the coming stages (ACP
  runtime, trackers) changes how a session is forgotten.

## Decisions

### D1. An optional action on `GroupHead`

`GroupHead` gets an optional `action?: ReactNode`, drawn after the fold button inside the
band's `<h3>` (`.group-head` already flexes). Only `Sessions.tsx`'s Stopped group passes
one. **Why:** the band is every list's heading; an action slot keeps one component and
leaves the other lists as they are.

### D2. The window calls the existing preview and forget per session

`ForgetMany.tsx` holds `ForgetManyDialog({ sessions, onClose })`. On open it loads
`getForgetPreview(name)` for every listed session in parallel; it forgets with
`forgetSession(name, force)` strictly one after another, in the list's order. **Why:** the
core decides each session as the single Forget does; one at a time keeps the progress and
the failures readable and never runs two forgets of one SQLite at once.

### D3. The snapshot of the list

The window lists the sessions the Stopped group shows when it opens (`groupOf(...) ===
"stopped"` and the search's match), fixed for its lifetime; a session stopped later does
not join it, one resumed meanwhile fails with the core's reason. **Why:** a list that
changes under the human's ticks is a list they did not confirm.

### D4. Counting and the open runs' switch

`counted = ticked ∧ previewed ∧ (open_runs = 0 ∨ force)`. The button says
`Forget ${counted.length} session(s)`; the switch appears when a ticked session has open
runs, its text naming the sessions and the sum of their runs; with it off a line "While
this is off, <names> stay." **Why:** the single Forget's rule (a tick for open runs), so a
bulk press never drops runs the human did not see.

### D5. After the press

Rows turn to `forgotten` or the reason (`ApiError.message`); `Forgetting K of N…`; ticks,
the switch, Cancel off; the dialog's `cancel` event ignored while busy. All forgotten:
`onClose()`. Any refused: buttons become a single Close. If the route's session
(`useParams`) is among the forgotten, `navigate("/sessions")` once at the end. **Why:** the
list itself shows the result through the change feed; the window only needs to say what
did not go.

### D6. Stop and forget

`StopPopover` gets a second `danger` button before `Stop <name>`: `await
stopSession(name); await forgetSession(name, false); navigate("/sessions")`. Off when
`stop-preview.open_runs` is not empty, with the line "It has open runs: stop it, then
forget it from the Stopped list." A refused forget leaves the popover open with the
reason (the session is stopped by then and its head shows Resume and Forget). Busy texts
`Stopping…`, then `Forgetting…`. **Why:** the core's stop, then the core's forget, with no
new endpoint; the open runs' guard mirrors D4.

### D7. Names and look

Band button: `icon-button`-like `.group-action` 26 px, `ForgetIcon`, `color: var(--danger)`,
in `Tooltip` "Forget stopped sessions…", `aria-haspopup="dialog"`. The window reuses
`.question-dialog`, `.left-on-disk` (in a `<details>`), `.switch`, `.question-buttons`;
its list `.forget-many-list` scrolls inside (max 50vh). Mockup:
`task/lad-92/mockup-bulk-forget.html`, variant 1 and the Stop popover. **Why:** the single
Forget's window and words, so the two read alike.

### D8. Tests

- vitest `ForgetMany.test.tsx`: ticks, All, the count, open runs and the switch, a refused
  preview, sequential calls in order with `force` per session, a refused forget keeps the
  window, all forgotten closes it, navigation for the open session.
- vitest `SessionControl.test.tsx` (new): Stop and forget calls stop then forget and
  navigates; off with open runs; a refused forget shows the reason.
- vitest `GroupHead.test.tsx`: the action is drawn and does not fold.
- UI e2e in `tests/ui/test_launch.py` (a real `lado server`, fake agent): three stopped
  sessions, one cleared, two forgotten, the third stays; a session with an open run left
  without the switch; Stop and forget from a running session's head.
- No integration test: nothing new crosses processes (the server and core are unchanged
  and already covered).
- Regression: `make test`, `make web`, `uv run pytest -m ui tests/ui/test_launch.py
  tests/ui/test_session_list.py tests/ui/test_phone.py`.
