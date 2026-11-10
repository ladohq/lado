Task: LAD-264

## Why

Hovering a session in the session list (and an icon of the folded strip) opens, after 0.3 s, a
360 px card right of the list: title, state, Project, Ran, Folder, Kits, CLI, Mode and a hint
`Open it and press Resume` (change session-card, LAD-223). The card covers the chat the human
reads, flashes on the rows the pointer crosses on its way, and repeats Details, which the title
in the session's head opens. The human approved removing it after the supervisor's UX review.

Cause: one card (`SessionTip` in `web/src/Sessions.tsx`) serves both the row and the strip's
icon, and it was made to hold every fact of the session, though the row already shows what
picks a session (title, name, what waits or how long it ran) and Details holds the rest.

The task asked for a one-line tooltip on a row whose title is cut. The row never cuts it: a
long title wraps (`.session-name`, `overflow-wrap: anywhere`), so that case does not occur and
the row gets no tooltip at all.

Options weighed:

- A (taken): the row has no tooltip; the strip's icon, which says nothing by itself (`154`),
  keeps a short one: the title and name, the state line. Long-term cost: none; less code, one
  place (Details) for the facts.
- B: cut a long title in the row with "…" and show it whole in a tooltip. A new way of hiding
  text the task did not ask for; more code (a cut check per row).
- C: keep the card and shorten its delay or move it. Keeps two places for the same facts.

## What Changes

- The rows of the session list show no tooltip on hover or keyboard focus.
- An icon of the folded strip shows a short tooltip right of it: the title in bold, the name
  in `--muted` after it when the session has a title, then the state line with the icon's mark
  (`Needs you: 1 gate`, `2 of 3 agents working`, `idle`, `stopped 5 h ago`, a trouble). A
  session in trouble in which something waits keeps `Needs you: …` on a line of its own, as its
  icon is the waiting one. As wide as its text, at most the UI's tooltip width (320 px); the
  UI's tooltip delay (0.3 s), at once on keyboard focus, Esc closes it.
- Gone from both: Project, Ran, Folder, Kits, CLI, Mode and the `Open it and press …` hint.
- Details (the head's title) is unchanged.
- A patch (0.45.1): a UI change, no API, CLI or schema change.

## Scope

- `web/src/Sessions.tsx`: `SessionRow`, `StripIcon`, `SessionTip`, `TipState`, `HOW_TO_GO_ON`,
  `KITS_SHOWN`.
- `web/src/styles.css`: the card's width and height rules.
- Tests: vitest (`web/src/Layout.test.tsx`), UI e2e (`tests/ui/test_session_list.py`,
  `tests/ui/test_sessions_strip.py`).
- `docs/design/ui.md` (the session list's rows and the strip).
- CHANGELOG.md under `## 0.45.1 (unreleased)`.

## Out of scope

- Details and the session's head: unchanged, by the task.
- `SessionInfo.project_title` and its feed: the head's `useAbout` asks its about again when the
  title changes, so the field stays though the tooltip no longer shows the project.
- The tooltip's delay (0.3 s), every tooltip of LADO has it (the task).
- The agents' popups of the team strip (`Team.tsx`), which share `.tip-facts` and `.tip-hint`:
  not part of the task; those classes stay.
- The phone: the list is the page there, with no strip; a tap opens the session.
