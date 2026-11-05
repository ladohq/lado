## Context

Spec: LAD-189 spec §3 and §9, frames g3-* (`lad-189-mockup.html`, task LAD-194), the human's
decisions F43 and F45 and the six of 2026-11-05 (proposal, Out of scope; run artifact
`mockup-waiting-forks.html`). Root cause and options: proposal, Why. Against AGENTS.md: the change
is above `providers/` and names no CLI, so it works with every provider (neutral core); it adds no
field, option or API (only what is used); a disagreement is kept in the line (no silent drops);
the height stays in the one key of `prefs.ts` (one source of truth). ROADMAP.md's coming stages
touch nothing here; LAD-193, LAD-195 and LAD-196 change what stands around the card and rely on
D9's fold and on the footer being one element.

## Decisions

**D1. Three parts, shared by two panels.** `web/src/waitingParts.tsx` holds `CardTop` (title with
meta, then `CardContext`) and `CardFoot`; `AgentPanel` and `GatePanel` (`inTab`) fill them.
`GatePanel` outside a tab keeps its layout. A new module, because `WaitingCard.tsx` imports
`GateCard.tsx`. `.waiting-list` becomes `.waiting-context`, `.waiting-send` stays the buttons' row
inside `.waiting-foot`. The panel's padding moves to the parts, so that the line above the footer
runs from edge to edge.

**D2. The 40 % limit.** `.waiting-top` (title and context) has `flex: 0 10000 auto; min-height: 0;
max-height: var(--waiting-top-max, 40dvh)`. `Chat` measures `.chat` with `useHeight` where the
chat has a height of its own (a wide window, the phone layout) and passes it; the card sets
`--waiting-top-max` to 40 % of it. Elsewhere (Needs you, a window of 900 px or less) the fallback
applies: there `.chat` grows with its content, so a percentage or a size container would measure
itself. Rejected: `container-type: size` on `.chat`, which collapses it on those windows.

**D3. The human's height.** `--waiting-height` stays the whole card's, as the stored value is. In
`.sized` the height goes on `.waiting-top`, not on the card: `max(0px, given − head − foot)` by a
`useHeight` on the head and the foot, with `max-height: none`. The footer so never gives way to
it, with no rule to clip it. `WAITING_MIN` and `FEED_MIN` keep their meaning for the edge's bounds;
`onReset` clears the height, which now means the content's. A height kept from an earlier version
applies as it is.

**D4. The order of giving way is flex-shrink.** `.chat-feed` loses its least height while a card
shows (`.chat:has(> .waiting-card) > .chat-feed { min-height: 0 }`). Inside the panel, shrink
weights stand for the order: top 10000, choices 100, opened recommendation 10, field frame 1, the
buttons' row `flex: none`; least heights are one chip row, one line, and the field's height at
one line. The title has no least height, and the meta, under the title on a phone, is cut first.

**D5. Context's fade and "↓ more".** `CardContext` tracks overflow with a `ResizeObserver` and
`onScroll` (`scrollTop + clientHeight < scrollHeight − 1`) and renders the fade and the button
only then; the button lies outside the scrolling box, so it does not scroll away. `tabindex="0"`
always on a context that overflows or not: one Tab order, as Safari does not focus scrollers.
Fade by a pseudo-element on the wrapper, `--human-ground` to transparent, so both themes hold.
`onMore` is the card's `setExpanded(true)`, on Needs you too.

**D6. Title.** `-webkit-line-clamp: 2`. A small `useClamped` compares `scrollHeight` with
`clientHeight` after layout and on resize; when cut, `CardContext` starts with the whole text.
Gate meta `<run> · <state> · gate #<id>`, question `#<id>`, mono 12 `--muted`.

**D7. The recommendation line.** New `RecommendationBar` in `Recommendation.tsx`; `Recommendation`
stays for Flows. Given: a button with `aria-expanded`, the name, the orange part, then the text
flattened to one line (`oneLine`: Markdown marks out, white space collapsed) with CSS ellipsis; on a
phone `line-clamp: 2`. Opened: `Body` in a box of 3 lines, `overflow-y: auto`, `tabindex="0"`. In
the expanded card it is opened with no line limit, at most 40 % of the window (`40dvh`: the panel has no definite height for a percentage). Tooltip: the text
and the time. `asked` and `missing` keep their words, italic `--muted`; none asked, nothing, as
the living spec has it. The option's name goes through the card's `label` (`Continue`, `Cancel
run`); a choice the card lacks counts as none, as in `primaryOf`.

**D8. Fields.** `AnswerBox` takes `lines?: [least, most]`, default `[CARD_LINES, MOST_LINES]`, so
Flows stays; the card passes `[1, 4]`, expanded `[1, 8]`. The growth follows the text, not the focus:
frame g3-390-kbd shows a focused field of one line. `useGrow` is unchanged and still serves a field
in the context of several questions.

**D9. The composer's fold.** `WaitingCard` takes `onFold(fold | null)` from `Chat`, reporting
`{ line: string, write?: () => void }` by an effect; `Chat` keeps it and renders `ComposerFold`
instead of showing the composer, whose `folded` prop hides it (`hidden`) and switches off its drop
zone: it stays mounted, so its text, files and quote handling live on. `write` closes all the open
fields of the shown tab, so that the composer does come back, and focuses the composer. Reported only while `chat`, not `stopped`,
not `folds`, not `expanded`, or on a phone (D11). Needs you has no composer and passes nothing.
A quote: `onQuote` calls the same closing, besides folding an expanded card.

**D10. Drafts.** `drafts: Record<number, string>` in the card, kept beside `picks` and dropped with
them. Closing a field by the link stores `pickText` and sets the pick to `null`, as an unpick;
Other… and Skip question open with `drafts[id] ?? text`. Files already stay per question.

**D11. A phone's field in focus.** `onFocus` and `onBlur` on the panel set `typing` (phone, chat,
target matches `FIELD`, the next focus not in a field). `typing` puts `.typing` on the card, but
for the expanded card, which keeps its context to be read and has hidden the rest already. `:has`
hides the session's tabs (the human's decision of 2026-11-05, F2: under about 375 px the buttons
were cut; frame g3-390-kbd keeps them) and the Team row, and a field in the footer hides the
context and the choices' area (the human's decision of 2026-11-05, F16: under a recommendation
of two lines Send was cut under about 378 px, with the choices at their one row; this goes over
spec §3's order, in which the choices come before the recommendation; the field losing the
focus brings them back). A field in the context of several questions keeps it, and comes back
into its view when the card is laid out anew (the keyboard opening). The fold reports
"Commenting on gate #<id> above" with no `write`. A button pressed keeps the focus in the field,
so nothing moves under the finger. `fromField` and the expanding `onFocus` of LAD-126 go.

**D12. Send's reason.** A disabled button gets no pointer or focus events, so `Tooltip` wraps a
`span` around it while it is off for want of an answer, with `tabIndex={0}`: that makes it a
hint, which a tap shows too (`Tooltip.tsx`). Stopped: no tooltip, the note of `GatePanel`, moved to
one constant.

**D13. Chips.** `.waiting-option` gets the frames' radius 16. The ✓ is `aria-hidden`, shown while
the picked choice is the recommendation's, so the button's name stays the choice. The group is
named "Choices" for one question, and keeps "Answer to question #<id>" in the context of several.

**D14. Phone sizes** go in styles.css's section "Phone layout": `:root[data-phone]` rules for
`.waiting-tab`, `.waiting-expand`, `.waiting-option`, `.waiting-send` buttons and `.answer-box`. The
choices' limit is `--waiting-choices-max`: 160 px, on a phone 148 px.

**D15. The flaky test.** `test_an_own_answer_expands_the_card_above_the_keyboard` measures a field
scrolled into a list by the expansion, after `moveViewport`. The expansion and the scroll go, so
the test is replaced by AC-13's. The developer first reproduces the failure on main in a parallel
run or names why it cannot be, then removes the BACKLOG.md entry and says which it was. It was a
race of the test: `.app`'s height shows at once, but the field comes into view only after the next
frame (ResizeObserver, `cardHeight`, an effect), and `within` read it once, between the two.
Reproduced on main under load, 7 of 160: the field at 384–464 in an app of 400 px, 226–306 by
500 ms later. A footer's field needs no such scroll, so AC-13's test has no race (0 of 160).

**D16. The footer in a window that scrolls** (ui-review C1, the human's decision of 2026-11-05).
At 900 px or less `.chat` has no height of its own and the page scrolls, so nothing above could
hold the footer. The card takes `position: sticky; bottom: 0`, on `--ground`, so nothing shows through beside its
tabs. Sticky stops at `.chat`'s top, so a limit counted from the top bar left a grown card past
the window (F28): `Chat` measures where it stands on the page (`--chat-top`; a `ResizeObserver` on it and every
box around it, as whatever comes or goes above changes one of their heights, F29) and the card
is at most the room from there down, its parts giving way by D4, held in tests down to 420 px. The
floor, 220 px (a footer's least height) or half the window, keeps the context of a chat low on
the page, under an open sessions' list; there, and in a window under about 400 px, the footer
comes up with the page's scroll. `.content` had
`overflow: hidden`, which would be the box it sticks in: with such a card it clips instead. Sticky
stops at `.chat`, which an expanded card fills, so the expanded card has that height and
`html:has(.waiting-card.expanded)` stops the page, on Needs you too; so a resize of the window
scrolls it under the top bar again, or a window narrowed would strand it (F27). A fixed card was the other way;
its left edge would need the rail's width. The phone layout, whose app does not scroll, sets all
this back. The rest of LAD-193's layout stays.

**D17. A phone's field on Needs you** (the human's device check of 2026-11-05 at `merge_ok`, video
and report `pr218-phone-check-report`: the expanded card shrank to its tabs and the human typed
blind). `typing` now holds on any phone page, but only the chat's card takes `.typing`, whose rules
fold the chat. Needs you scrolls as a page, so while a field has the focus the visual viewport's
`resize` scrolls the footer into view. An expanded card has the page's room: `:has` hides the
notifications' offer and the session's heading while its field has the focus, and `.rec-bar.whole`
gives way as an opened one does, so the footer stays whole in 350 px. The button press keeps the
focus here too.

## Risks

- `:has` and `dvh` are in use already; nothing new for the browsers supported.
- Shrink weights are a ratio, not a strict order: at the extremes the choices' area can give a
  few pixels while the top is still above 0. The tests in a 420 px chat and at 440 px check that
  the buttons hold; a strict order would need JS measuring.
- A window of 900 px or less: the card sticks over the feed, and expanded it holds the page, so
  the session's tabs and Team are out of reach until it folds. The composer may stay past the
  window's edge: LAD-193 (D16).
- Single frames of the recording show the card cut while the keyboard moves (the report's
  "Minor"); whether an eye sees them, and whether they are Safari's own, is open.
- A real keyboard may leave less than 440 px (a small iPhone leaves about 350). Then the top goes
  to 0 first, as D4 says; the tests hold at 350 and 340 px, an imitation, not verified on a device.
- An Android back button closes the keyboard without a blur (F8): `typing` stays until a touch
  elsewhere. To be checked on a device with the iOS keyboard.
