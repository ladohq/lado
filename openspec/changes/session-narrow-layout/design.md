## Context

Spec: LAD-189 spec §2 and §9, frames g2-* (`lad-189-mockup.html`, task LAD-193), the human's
decision on `PHONE_QUERY` (task comment of 2026-11-05), the answer #3750 (proposal) with run
artifact `mockup-narrow-layout.html`, and what LAD-192 and LAD-194 left here. Root cause and
options: proposal, Why. Against AGENTS.md: the change is above `providers/` and names no CLI, so
it works with every provider (neutral core); the human's choice stays in the two keys of
`prefs.ts` and the fold is derived, never stored (one source of truth); a terminal in control
holds its panel against a fold, and when the panel folds all the same control ends with no message
of its own, as every other end of control does, by the human's decision (#3788, review finding
F10); no field, option or API is added (only what is used). ROADMAP.md's coming stages touch nothing here;
LAD-195 and LAD-197 change what stands in the top bar and the tab bar and rely on D5's bar.

## Decisions

**D1. One pure rule.** `web/src/columns.ts` exports `fitColumns(input)`: from the room of
`.sessions` (the page beside the rail), the list's and the panel's stored choices, whether the
panel counts as opened by the human, and which column the human opened last, it returns what
shows now: `{ listFolded, panelFolded, panelWidth }`. It has no state: a column comes back
because the room did (rule 4в), the list before the terminals by the order of its steps, and the
stored choice is what it returns to (rule 4г). `.sessions`' width does not depend on the columns,
so the measure cannot loop. Steps: the wanted columns; then fold the panel when the human did not
open it or opened the list last, else the list; then narrow a panel the human opened to the room
less 420, down to `PANEL_WIDTH.min`; then fold the other one, and a list that fits beside the
folded panel stays open. Terminals nobody opened never stay beside a list that folded; terminals
the human opened do, also when the list came last. "Opened last" is the human's choice, so it is
stored (`lado.lastColumn`, design QA F1): pressing Sessions or a chip sets it even when the stored
choice is already open, and a reload shows what the human left; with none stored a tie goes by
rule 4б, the list folds. `listMax` of the same file bounds the list's
edge, so that a drag never makes the rule fold the list under the pointer. Rejected: CSS container
queries and writing the fold to prefs (proposal, options A and C).

**D2. Who holds what.** A hook `useSessionColumns` in `Sessions` holds both prefs and the room, and
gives the panel's part to `TerminalPanel` by the outlet's context; `TerminalPanel` gives back
whether a terminal is in control. `keep` stays the one writer of each key. `MAIN_MIN` goes;
`CHAT_MIN = 420` and `STRIP = 32` live in `columns.ts`, `--chat-min` and `--strip-w` in `tokens.css`,
and `tokens.test.ts` checks that they agree. `STRIP_WIDTH` becomes 48.

**D3. What the human chose.** `storedColumn` gives `chosen: stored !== null`: a panel counts as
opened by the human when it is stored open, which any act of theirs does (a chip, the strip's
buttons, the edge). `?terminal=` from a notification goes through `open`, so it counts too. The
panel's width is the human's only when it differs from the old default: a stored 480 was written
beside `collapsed` by `keep`, not chosen; from now on `keep` writes `width` only on a drag, and the
edge's double click removes it. `storedColumn`'s default by `(max-width: 900px)` goes (D6).

**D4. The rail.** `storedRailCollapsed` returns the stored choice or null; `Shell` takes null as
`useMedia("(max-width: 1599px)")`, so the default follows the window as the columns do.

**D5. The tabs' levels.** The links move into `.session-tabs-scroll` with `‹ ›` and the fade; Find
stays outside it, at the bar's right end. A layout effect on a `ResizeObserver` of the bar, and on
the counts, tries the levels in turn on `data-fit` and keeps the first that fits by
`scrollWidth`, before paint. The phone hides the icons already and takes the same levels. At level
3 the arrows scroll by the bar's width, and the shown tab is scrolled into view.

**D6. 601 to 900 px.** `useMedia("(max-width: 900px)")` is the third state of D2's hook: both
columns folded, whatever is stored, and a local `over: "list" | "terminals" | null` for this
window, written nowhere. CSS: `@media (min-width: 601px) and (max-width: 900px)` with
`html:has(.sessions)` gets the wide window's `height` and `overflow`, and `.app` its rows; the
stacking of `.sessions` and `.session-page` is replaced by the row strip over the session and the
strip on the right. `.session-list` and `.terminals` with `.over` are `position: absolute` in
`.content`, under the row of the strip (`--row-h`), so that Expand still covers the page, and under
the z-index of the artifact panel. The rule keys on `.sessions`, so Needs you
and the other pages scroll as before. `.terminals` reuses `over`, `escapeIsOurs` and `putBack`.

**D7. LAD-194's rules go, not layered.** With the page still the chat has a height at every width
of a session's page. So `ownHeight` in `Chat.tsx`, `usePageTop` and `--chat-top` go,
`.chat > .waiting-card`'s `sticky`, `.content:has(...)`'s `clip`, `html:has(.waiting-card.expanded)`,
and `underTheBar` and `NARROW` in `WaitingCard.tsx`. The 40 % is of the chat, as above 900 px. To
stay the same for the human: at 601 to 900 px the expanded card still takes the window under the
top bar, by `:has(.waiting-card.expanded)` hiding the strip with its grid row, the tabs and the team
row as the phone does, and CSS alone keeps the one thing left, no edge above the card. The
terminals' strip stays beside it. A window of 460 px or less hides the composer while a card shows.

**D8. The phone query.** `PHONE_QUERY` as the human decided. Nothing else in `usePhone` changes.
A window crossing 600 px goes through what a turned phone does: `TerminalPanel` already ends a
phone's terminal when the phone goes. `:root[data-phone]` rules then meet a mouse; tooltips stay on
hover, as their rule asks for a touch screen. The comments of `phone.ts`, `styles.css` and the
Purpose of `phone-layout` follow (an archive does not touch a Purpose: edit it in this pull request).

**D9. A tablet's keyboard.** `html { overflow: hidden }` takes away the page's scroll that brought
the composer above Safari's keyboard. `usePhoneViewport` so also runs for `(pointer: coarse) and
(min-width: 601px)`, and CSS sizes `.app` by `--phone-height` and `--phone-top`, as LAD-109 does for
a phone: on a session's page at 601 to 900 px, on every page above, where the whole app is the
window and `100dvh` is taller than the visible part on iPadOS 26 Safari (the human's check in the
iOS Simulator: 763 px of 688 to 734, and the card under the keyboard). Other pages at 601 to 900 px
scroll as before. Here it is checked with a faked height: the human repeats the check.

**D10. The strip's buttons.** Per agent of `agents` (the session's list), in its order, not per open
tab: the spec says per agent, and it is what F26 asks. `avatar()` of `FeedRow.tsx` gives the letter
and the colour; `StatusDot` the mark, with its working, idle and waiting looks. A stopped session
shows its agents the same way, and the button opens the panel with its "Agent not running". The
column of buttons scrolls; the caption stays under it.

**D11. The badge.** `badge(session)` in `Sessions.tsx`: `/^\p{L}+-(\d+)/u` on the label (the title,
or the name without one, as the frames show: `lad-77-checkout` titled `Checkout redesign` is `CR`),
else `initials`. The mark is added in `SessionStrip` by the strip's order. With a mark the badge's
font is 10 px, so that `154·2` stays in 32 px.

**D12. The phone's targets.** The title's button has `min-height: 44px` and no block padding. The
link's box is 33×44 by its padding, its margins of -10 and -8 px taking the room back, so nothing
else moves: a pseudo-element on the button took no taps in Chromium. Reading `styles.css` against
spec §9's table is task 6.2; by the human's answer #3762 the Team chips and the session's tabs stay
24 and 35 px.

**D13. Measures.** Spec §2's 556 px at 1024 comes from the frame's `termW: 360px`; its rule gives
366 px and 550 px. The rule stands, as in frame g2-1280 and at 1440.

**D14. First paint.** Before the room is known (the first frame) `fitColumns` is not applied, and
a terminal is not made: a panel that is about to fold opens no socket.

## Test layers

The whole of the rule is unit-tested as a pure function (vitest, `columns.test.ts`), each width and
each order of the human's acts. What needs real layout goes to UI e2e: the chat's width, the still
window, the panels over the session, the tabs' levels. No process is crossed, so no integration
test. Table: the plan.

## Risks

- UI tests that open a narrow window with a mouse now meet the phone layout: 11 files, listed in the
  plan; each decides whether its width becomes 601 or its check the phone's.
- An iPad's real keyboard (D9) and the real iPad at 1024, which already had a still window.
- A low window of 601 to 900 px (under about 420 px): the feed and context go to 0, then the composer
  leaves before the card's buttons, as above 900 px.
