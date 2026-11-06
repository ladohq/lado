Task: LAD-193

## Why

Symptom (audit of LAD-189, findings F2, F3, F6, F8, F9, F16, F26): at 1100 px and less the
chat shrinks to 312 px and the Artifacts tab is cut off. At 900 px and less the whole page
scrolls: the composer lies past the window's edge, and an open gate is two screens below the
top. In a narrow window with a mouse the desktop layout breaks, and the title goes. In the
session strip `lad-154-epic` and `lad-189` wear the same `L1`. The terminal strip's dots are no
buttons, so one agent's terminal cannot be opened from it.

Cause: each column narrows itself on its own. `fitWidth` gives the list and the panel what is
left beside a least session of 360 px, and neither knows of the other, so nothing ever folds.
The stored `collapsed` is the only state, written by the human alone, so a fold made for room
has nowhere to live. At 900 px the app's model changes: the columns stack and the window
scrolls, and LAD-194 had to patch that for the card (a footer that sticks, a card that locks
the page). The phone query asks for a coarse pointer, so a mouse never gets the layout made
for that width.

Options weighed:

- A: CSS alone (container queries on the columns). No JS state; but a fold cannot depend on
  what the human opened, nor give a column back to the human's choice.
- B (taken, LAD-189 spec §2): one pure function decides from the room there is and the human's
  stored choices what shows now. The stored choice is never touched by a fold, so a column
  comes back by itself with no state to undo. It costs lifting the panel's prefs out of
  `TerminalPanel`.
- C: write the fold into the stored `collapsed`, as the buttons do. The smallest diff; the human's
  choice is lost on the first narrow window, which spec §2 rule 4г forbids.

## What Changes

- Above 900 px the chat is never narrower than 420 px: terminals the human did not open fold to
  their strip, else the list folds to its strip, and a folded column comes back by itself when
  there is room. Folding for room is never stored.
- The rail starts collapsed below 1600 px; the terminals start at 40 % of the session's area,
  360 to 640 px.
- A session's tabs give way in levels: no icons, no counts, then a fade and arrows.
- The terminal strip is 32 px with a button per agent; the list's strip is 48 px.
- At 601 to 900 px a session's page stands still as a wide window does: the feed scrolls inside
  it, the composer and an open gate are in sight at once, the session strip is a row, the
  terminals' strip stays on the right and open terminals lie over the session. The open list
  lies over the session too.
- The rules of LAD-194 for a window that scrolls go; what the human sees of the card stays.
- A window of 600 px or less is a phone with a mouse too.
- The strip's badges tell `lad-154-epic` from `lad-189`.
- On a phone the title and the link get 44 px high targets.

Decided with the human where the spec is silent or differs from the code (answer #3750,
2026-11-05, all as recommended; mockup `mockup-narrow-layout.html`):

- The open list at 601 to 900 px is a panel of 300 px over the session's column, on its left.
  Choosing a session, Esc, a click beside it and its button close it. There the list and the
  terminals start folded, and opening them is not remembered and changes no choice of a wide
  window.
- The list's strip keeps its vertical Sessions button above "+", which frame g2-1024-open lacks.
- A badge: a title or name that starts with `<word>-<number>` gives that number's last 3 digits,
  whatever follows; else the letters of the title, else of the name; a clash in the strip adds
  a mark (`154·2`). The spec's text says the title first, its frames show this.
- When folding is not enough (the rail opened by hand, terminals opened by the human, about
  901 to 1000 px) the panel narrows to its least 280 px, its stored width kept, then folds. The
  rail never folds by itself.
- The phone's title target is 44 px high; the link's 44 px high and 33 px wide, by the gaps at
  its sides, so that the title loses nothing.

Decided by the brief: the human's rule of 2026-11-05 on `PHONE_QUERY` (task comment), and that
Needs you does not change.

Scale: full. Version: a feature, the minor; `## 0.45.0 (unreleased)` already holds it.

## Acceptance criteria

- AC-1 At 901, 1024, 1101, 1280 and 1440 px the chat is at least 420 px wide, with the
  terminals opened by the human and not, on every tab of the session.
- AC-2 With nothing stored the rail is collapsed below 1600 px and expanded from 1600 px, and it
  follows the window; a choice made with its button wins and survives a reload.
- AC-3 With nothing stored the terminals are `clamp(360px, 40% of the session's area, 640px)`:
  the chat is 672 px at 1440, 576 px at 1280, and 672 px at 1024 with the terminals in their
  strip. A width set on the edge is kept.
- AC-4 Short of room, terminals the human did not open fold first; opened by the human, the
  list folds instead. A column folded so comes back by itself once it and 420 px fit, the list
  before the terminals.
- AC-5 A fold for room writes nothing to the browser's storage; the human's fold, opening or
  width survives a reload at any width.
- AC-6 A column the human opens while short of room stays open and the other one folds.
- AC-7 With the rail opened by hand and the terminals opened by the human at 901 px the chat is
  still 420 px: the panel narrows to 280 px, then folds. A terminal in control counts as opened
  by the human; if it folds all the same, control ends with no message of its own (the human's
  decision #3788).
- AC-8 The Artifacts tab is seen, or an arrow says there is more, at every width: first the
  icons go, then the counts, then a fade of 56 px and › of 26 px, and ‹ after a scroll.
- AC-9 The terminal strip is 32 px wide: Show the terminals, a button of 24×24 per agent of the
  session named `Open <agent>'s terminal` with its avatar, letter and status mark, then the
  caption Terminals. A button opens the panel on that agent.
- AC-10 At 768 and 880 px, on a session's page, the window does not scroll, and the composer and
  an open gate are in sight at once.
- AC-11 At 601 to 900 px the session strip is a row of 48 px: Sessions, "+", the badges. Sessions
  opens the list over the session as a panel of 300 px; choosing a session, Esc, a click beside
  it and Sessions close it, and the focus goes back to Sessions (not after a choice).
- AC-12 There the terminals' strip stays on the right; open, the panel lies over the session,
  `min(560px, 100% − 48px)` wide, and Esc closes it, the focus back on the strip. In control
  Esc stays the terminal's.
- AC-13 At 768×700 and 768×1024 the card's footer is in the window, the card expanded too, which
  fills the window under the top bar until it folds; there is no edge above the card.
- AC-14 Needs you and the other pages at 601 to 900 px scroll as before; Needs you's card does
  not change.
- AC-15 390 px with a mouse: the phone layout, the title in place. 768 to 1024 px on a touch
  screen, 1440 px on a touch laptop, a wide low window with a mouse: no phone layout. A phone
  held sideways as before.
- AC-16 In the strip `lad-154-epic` shows 154 and `lad-189 (session UI review)` 189; a clash shows
  `154·2`.
- AC-17 On a phone the title's target is 44 px high, the link's 44×33, and every target of
  spec §9's table has its size.
- AC-18 docs/design/ui.md, the comments of `phone.ts` and `styles.css` and CHANGELOG.md change in
  the same pull request.
- AC-19 After the build, ui-review as design QA against frames g2-*, the dark theme too.

## Out of scope

- The Team row inside the tab bar and the composer's hints (spec §6): LAD-197, which owns them.
  So `Yours | All` still wraps under the chips in a chat of 420 px (frame g2-1024-tabs).
- The dimming of Take control (F26's second half): LAD-198.
- The link's states when the connection is lost: LAD-195.
- The edge above the card at 601 to 900 px: the human asked that the card stays as it is for them
  (brief), so it does not come although the page no longer scrolls.
- Needs you and the other pages at 601 to 900 px: the brief keeps them; a still window for them
  would move their top bar and keyboard behaviour for no finding.
- The rail folding by itself: spec §2 names only the terminals and the list, and the rail is the
  human's own choice.
- The sections "What works" of both critiques.
- An iPad with its real keyboard: not checkable here, the human's check before the merge.
- Touch targets on an iPad: LAD-216.

## Impact

- `web/src/columns.ts` (new): the rule. `web/src/prefs.ts`, `Sessions.tsx`, `Terminals.tsx`,
  `Shell.tsx`, `phone.ts`, `Chat.tsx`, `WaitingCard.tsx`, `Splitter.tsx`, `tokens.css`,
  `styles.css`.
- `docs/design/ui.md`: Structure (rail, terminal panel, list strip, columns, the window never
  scrolls), Session head's strip words, The waiting card, Phone layout, Look. CHANGELOG.md.
- Specs: new capability `session-layout`; deltas of `phone-layout`, `chat-question-card`,
  `session-head`, `projects`.
- Tests: vitest and UI e2e (design.md, Test layers). UI tests that open a narrow window with a
  mouse now meet the phone layout and change.
- No API, schema, MCP or CLI change. Neutral core: no provider is involved.
