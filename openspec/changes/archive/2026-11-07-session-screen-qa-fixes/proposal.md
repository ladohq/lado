Task: LAD-224

## Why

Design QA of main at 506dd44d, after LAD-196 and LAD-198, found two defects and four smaller
departures on the session screen (findings F46 to F51 of the report attached to the task).

- F46: after Esc or Cancel in Take control or Resume the focus is on `body`, so the next Tab starts
  at the top of the page.
- F47: on a phone held sideways the toggle Messages between agents cannot be reached. A stopped
  session's empty feed says the messages are hidden and offers no way to show them.
- F48, F49: the kit window's `.kit-alert` wears orange, which means "waits for the human", and a
  failed login looks like plain text with a stripe on its quote. Both break the notices rule.
- F50: a run's cut task cannot be read in the list, and on a waiting card it is orange.
- F51: a run's group can stand above Session and push it 65 rows down.

Causes:

- F46: every window opens with `showModal()` and goes when React removes it, without
  `dialog.close()`. The browser gives the focus back only on `close()`; checked in Chromium, a
  `close()` after the removal is too late as well. So all 13 `showModal` calls in 12 files have this
  defect, `SessionDetails.tsx` too: its `close()` is in a passive effect's cleanup.
- F47: the toggle lives in the team's row, and sideways that row is `display: none`; the tab bar's
  choice is rendered only outside the phone layout.
- F51: the group order is by newest record, and Session has no place of its own.

## What Changes

- A window of the UI closes through one hook, and the focus goes back to what opened it. A focus
  given back so shows no tooltip.
- On a phone held sideways the icon toggle stands at the right end of the session's tab row.
- `.kit-alert` becomes `.kit-warning`; a failed login's heading is a `.problem`, its quote has no
  stripe.
- A run's row and card show the whole task in a tooltip when something of it is hidden, at most 12
  lines and 600 characters. The task's line is `--muted` on a waiting card and row too.
- Session is the first group of the Artifacts tab.
- The browser console's errors on the screens this change touches are sorted in the build report.

## Scope

In: F46 to F51 above, the console errors, `docs/design/ui.md`, CHANGELOG.md.

The mockup-versus-build notes of the task need no edit: `openspec/specs/artifacts-list` already says
720 px, `openspec/specs/artifact-panel` already says Copy link, and the LAD-198 design doc records
both departures. The human closed this item on 2026-11-06.

## Out of scope

- F52 (the panel's 28 px buttons on a phone): decided together with LAD-216.
- F53 to F56: left as they are by the human's decision.
- The focus after a window's action succeeds and its opener is gone (Take control pressed, a Resume
  that starts the session, a Forget that leaves the page): unchanged, nothing was reported there.
- The login window: a `div` with `role="dialog"`, not a `showModal` window; its focus is not part of
  F46.
- A tooltip on a touch screen: a run's row is a link, and a tap opens the run, where "more" shows
  the whole task (`phone-layout`, "On a touch screen a hint's tooltip shows on a tap").
- `.kit-danger` in the kit removal window also has a border and no icon: not in the report, so it
  goes to the ledger under "Found on the way".

## Acceptance

- AC-1: Esc and Cancel in Take control and Resume put the focus back on the button that opened the
  window, and the next Tab goes on from there.
- AC-2: every other `showModal` window does the same, and `showModal` is called only in `modal.ts`.
- AC-3: a focus given back shows no tooltip, by the keyboard or the mouse.
- AC-4: at 844×390 and 568×320 with touch the toggle shows and works, in an empty feed too.
- AC-5: the kit windows' two warnings are warning notices, seen in the live window.
- AC-6: a failed login's heading is an error notice and its quote has no stripe, seen in the live
  window.
- AC-7: a run's tooltip shows the hidden task within its limits, and none when nothing is hidden.
- AC-8: a waiting run's task line is `--muted`.
- AC-9: a session of 100+ artifacts shows Session first.
- AC-10: the console errors of the touched screens are sorted in `build-report`.

## Impact

- `web/src`: a new `modal.ts`, the 12 files with `showModal`, `Tooltip.tsx`, `Sessions.tsx`,
  `Kits.tsx`, `LoginWindow.tsx`, `Flows.tsx`, `ListPage.tsx`, `ArtifactsTable.tsx`, `artifacts.ts`,
  `styles.css`.
- No server, API, schema or provider change: nothing crosses processes.
- Patch-level fixes, under `## 0.45.0 (unreleased)`; no version change.
