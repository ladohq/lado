# Phone layout — design

Task: LAD-95. Change: `openspec/changes/phone-layout/` (proposal, delta
`specs/phone-layout/spec.md`, `design.md` D1–D9). Mockup: run artifact
`task/lad-95/mockup-phone.html` (navigation A, "Menu ☰", chosen; B, the bottom bar,
turned down). Survey of today: run artifacts `task/lad-95/phone-now-*.png`.

## Goal

From a phone's browser the human follows a session and answers it: the feed and the
runs, gates and questions (also on Needs you), a message to the supervisor, artifacts,
Stop. The computer's design does not change (the human's condition).

## When the phone layout applies

| Screen | Pointer | Layout |
|---|---|---|
| ≤ 600 px wide | coarse | phone, `data-phone="tall"` (or `short` when also ≤ 500 px high) |
| ≤ 500 px high | coarse | phone, `data-phone="short"` |
| anything | fine (mouse, trackpad) | as before this change |
| a tablet (820×1180, 1180×820) | coarse | as before this change |

The query is in `web/src/phone.ts` only; the Shell mirrors it to `<html data-phone>`;
every phone rule of `styles.css` is in one section "Phone layout" under
`:root[data-phone]`.

## Screens

### Every page

- The rail is hidden. The top bar: Menu (☰, the Needs you badge), then the page's title
  or the session's compact head; on the right the change feed's mark (a dot while live,
  "reconnecting…" otherwise; it opens the system panel) and `↑ X.Y.Z` when a newer LADO is
  out.
- Menu opens the rail as a drawer, 260 px, from the left, with names; a scrim dims the
  page. An item, the scrim, Esc or a route change close it.
- The window does not scroll; `.content` does (the computer's wide-window rules, D4).

### A session's page

- Top bar: Menu · status dot · title (button) · live dot · Stop. 52 px upright, 44 px
  sideways; no wrap; the title cut with "…".
- The title opens `SessionDetails`, a bottom sheet: status and run time; the folder whole
  with Copy path; git; the kits with versions (tooltips on a tap); the CLI with version and
  mode; Rename, Copy link, All sessions; a close button.
- No session strip. Tabs without icons, all four within 360 px.
- Activity: the Team row; the feed scrolls by itself; a flow event's line starts at the
  feed's left edge (`--text-start` at the row's padding), its first line actor, chips and
  time, its text wrapped under it; the waiting card at most 50% of the chat, no edge; the
  composer at the bottom, 16 px text, no keys hint.
- Sideways (`short`): the card minimized by the layout (D5), a tab shows it expanded over
  the chat; no Team row and no "to" line.
- Terminals: no panel or strip; a team chip or Open terminal shows the terminal expanded
  over the screen with Close terminal (D7).

### Sessions

- `/sessions` is the list, full width (search, "+", groups); a row opens the session.

### Kits

- The three tabs fit 360 px: the session tabs' compact style (no icon room, smaller
  padding).

### Unchanged on a phone

Needs you, Flows, Agents, Artifacts (with the panel over the whole screen below 464 px, as
now), New session, Settings, Projects, Home, Report a bug: they already fit; they only lose
the rail.

## What a computer keeps

With a mouse nothing matches `PHONE_QUERY`, so `data-phone` is never set and no rule of
the section applies; the components' phone branches (`usePhone()` null) render as today.
Guarded by `tests/ui/test_phone.py::test_a_computer_keeps_its_layout` at 1280×800,
800×900 and 390×844, and by the whole UI e2e suite unchanged.

## docs/design/ui.md

A new section "Phone layout (decided 2026-10-18, LAD-95)" after "Notifications": the
table above, the screens, D1's single query, what is hidden and where it went, the
sideways card, terminals over the screen, tooltips on a tap. Structure's rail paragraph
and the Session head section get one line each pointing to it.

## Version

A UI feature: the next minor, 0.41.0 (CHANGELOG.md `## 0.41.0 (unreleased)`).
