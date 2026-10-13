Task: LAD-48

## Why

The waiting card's expand button (docs/design/ui.md, The waiting card) shows the card over
the whole window: a portal into `document.body`, `.waiting-overlay` at z-index 50 over a
scrim. The artifact panel a chip opens is `position: fixed` at z-index 30 (scrim) and 31
(panel). So a chip clicked in the expanded card opens the panel under the card: the address
gets `?view=<record>`, the panel is there, and the human sees nothing. The root cause is
two overlays stacked by fixed z-indexes, the card's above the panel's, while the card is
the one that opens the panel.

On Needs you the card expands over the window too, and a chip there navigates to the
session's Activity tab and opens the panel over it: the panel is seen, but the Needs you
card goes, with the answers picked and not sent (the chat's card is another component).

## What Changes

- **The expanded card stays in its page** (`web/src/WaitingCard.tsx`, `styles.css`): no
  portal, no scrim, no window overlay. In the session's chat it takes the chat's whole
  area, the feed's and the composer's place, which are hidden while it is expanded; the
  session's head, its tabs and the team row stay seen and usable. On Needs you it takes
  the page's content area under the top bar: its session's name line stays above it, the
  other sessions and the agents waiting in their terminal are hidden while it is expanded.
  Approved mockup `mockup-expanded-card.html`, option A (screens 3, 4 and 7).
- The expand button, its icons, names and tooltips, the fold by its button or Esc, the
  focus back on the expand button, and the fold by itself when nothing waits stay as now.
  The card is no modal dialog any more: the page around it stays usable.
- **Esc closes the topmost**: while an artifact panel is open over an expanded card, Esc
  closes the panel only; the next Esc folds the card.
- **A chip on Needs you opens the panel over Needs you** (`web/src/Attachments.tsx`
  `useView`, `NeedsYou.tsx`, `paths.ts`): the page, its cards, their picks and an
  expanded card stay where they were; ×, Esc, a click on the scrim and Back close it, the
  focus back on the chip, as in a session. The address carries the record and its
  session (`?view=<record>&session=<name>`).
- docs/design/ui.md: The waiting card (Height and expand), Needs you, Artifacts, The panel.
- CHANGELOG.md: a line under `## 0.37.1 (unreleased)`.

## Scope

The waiting card's expanded view in the session's chat and on Needs you, and the artifact
panel on Needs you, in the web UI. Nothing in the core, the API, the MCP tools or the
schema.

## Out of scope

- Option B, the expanded card in the feed's place with the composer kept under it: less
  room for a long question, and the composer is not where a question is answered (the
  human's decision).
- Keeping the Needs you card over the whole window: a page's card expands within its page,
  the same rule in both places (the human's decision).
- A chip on Needs you that goes to the session's chat, as before: the picks not sent were
  lost on the way (the human's decision).
- Carrying the expanded state or the picks between Needs you and the chat ("In the chat"):
  two pages, two cards; the task is about seeing the artifact.
- A gate's or a run's chips on Flows: the panel already shows over a session's tab, and
  nothing covers it there.

## Acceptance criteria

- AC-1: In a session's chat, Expand shows the card over the chat's area only: the feed and
  the composer are hidden, the session's head, tabs and team row stay seen and clickable,
  no scrim; the card fills the chat's width and height.
- AC-2: A chip clicked in the expanded card in the chat opens the artifact panel on the
  right, seen over the card; the first Esc closes the panel and the focus goes back to the
  chip; the card stays expanded with its picks; the second Esc folds it and the focus goes
  to the expand button.
- AC-3: On Needs you, Expand shows that session's card over the page's content area under
  its session's name line; the other sessions' cards and the waiting agents' rows are
  hidden until it folds.
- AC-4: On Needs you, a chip (in a folded or an expanded card) opens the artifact panel over
  Needs you without leaving the page; ×, Esc, the scrim and Back close it; the card, its
  picks and its expanded state stay; the panel's Open in Artifacts tab and Open latest
  work as in a session.
- AC-5: The collapse button and Esc fold the card as now; the card folds by itself when
  nothing waits; on a window of 900 px or less the expanded card is as tall as the window
  under the top bar.
- AC-6: docs/design/ui.md and CHANGELOG.md say so; vitest and the UI e2e tests check AC-1
  to AC-5 and pass.

## Impact

- `web/src/WaitingCard.tsx`, `web/src/Chat.tsx`, `web/src/NeedsYou.tsx`,
  `web/src/Attachments.tsx`, `web/src/ArtifactPanel.tsx`, `web/src/paths.ts`,
  `web/src/styles.css`, `web/src/WaitingCard.test.tsx`, `web/src/NeedsYou.test.tsx`,
  `web/src/ArtifactPanel.test.tsx`, `tests/ui/test_chat.py`, a UI test of Needs you,
  `docs/design/ui.md`, CHANGELOG.md.
- No API, schema or MCP change: a fix, the patch (0.37.1).

## Decisions for the record

- Scale tweak: one component's expanded view and one page's panel, their shape known;
  review as a tweak.
- The card expands in place by CSS on its host, not by a portal with a lower z-index:
  layering two fixed overlays by number is what broke; in place, the panel is above the
  page as it is everywhere (design.md, D1).
- The Needs you panel names its session in the address, so Back, a reload and a link work
  as in a session (design.md, D3).
