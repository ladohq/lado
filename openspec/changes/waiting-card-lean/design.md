## Context

Spec: `ui-design/gate-card-lean-3` (spec, design-system, mockup, brief, critique; attached to
LAD-266), the human's decisions of 2026-11-10 (proposal, Out of scope), audit
`ui-review/gate-card-audit`. Root cause and options: proposal, Why. The base is main's card
(option B): LAD-194's three parts stay, and what the design changes is changed in them; LAD-195's
Retry and waiting buttons, LAD-196's stopped note, LAD-193's 601 to 900 px layout and LAD-194's
phone keyboard stay as they are.

Against AGENTS.md: the change is above `providers/` and names no CLI, so it works with every
provider (neutral core). The one new field, `GateInfo.note_by`, is used by the tab's tooltip
(only what is used) and comes from the note the gate keeps, the same source as
`RecommendationInfo.by` (one source of truth). A disagreement keeps its words in the block's
aria-label and the icon's tooltip, never dropped (no silent drops). ROADMAP.md's coming stages
add no part to the card. The change bumps the minor: a new API field and a redesign are no fix.

## Decisions

**D1. Head, report, footer.** `waitingParts.tsx` keeps three parts with new roles. `CardHead`
(was the title in `CardTop`) is `.waiting-head` outside the scroll, `flex: none`, `h3` 15/600 on
`--human-head`, radius `0 9px 0 0` (`9px 9px 0 0` on a run's page, which has no tabs), one line
with `text-overflow: ellipsis` (the human's decision of 2026-11-10). `useClamped` stays and now
decides the tooltip: a cut `h3` gets `tabindex=0` and the UI's `Tooltip` with the whole text (a
tap shows it on a touch screen, as the `h3` is no button); the whole text is no longer repeated in
the report. Its meta (`<run>
· <state> · gate #<id>`, `#<id>`) goes. The card's tab panel gets `aria-labelledby` on the `h3`
when there is a head, else on the tab. `CardContext` becomes the report, `.waiting-scroll`,
`flex: 1 1 auto; min-height: 56px; overflow: auto`, still the region "Context of the card" with
`tabindex=0`. `CardFoot` stays, with `border-top: 1px solid color-mix(in srgb, var(--human) 35%,
transparent)` only when no splitter stands above it. The current `.waiting-head` (the tabs' row)
is renamed `.waiting-tabs-row`, so the name matches the design's.

**D2. The height.** The 40 % rule on the top (`--waiting-top-max`, `TOP_SHARE`) goes; `.chat >
.waiting-card` gets `max-height: 50%` as in 0.44, the phone too (the design's "62 % of the chat
under the chrome" is the same 50 % of `.chat` measured from the page). Inside, the head, the
splitter and the footer are `flex: none`; only `.waiting-scroll` shrinks, to 56 px. The human's
height (`--waiting-height`, `.sized`) stays the whole card's and still never cuts the footer
(`--waiting-rest`, D3 of LAD-194), now with the head counted in it. The order of giving way of
LAD-194 (choices' area, opened recommendation, field) stays for a footer taller than its room, as
the 601 to 900 px and phone requirements rely on it; the recommendation's box (D4) takes the
opened recommendation's place in it.

Built (agreed with the supervisor on 2026-11-10): a `max-height` on the whole card cut its footer
in a low chat, where the tabs, the head and the footer alone take more than half, and the footer
measured in that state fed the limit back. So the half of the chat (`--waiting-max`, measured)
is the report's to keep: `max-height: max(56px, var(--waiting-max) − var(--waiting-rest))`, the
rest being the tabs, the head, the footer and the panel's borders, measured always; such a card
is taller than half, its report at 56 px. With a field of the footer in focus, on a phone the
head gives way before the recommendation (its band's padding moves to its text, so it can go to
nothing), and on any touch screen (a tablet's keyboard, a phone's expanded card) the report
gives way past 56 px, then the head, so the field and the buttons stay above the keyboard.
Scenario "Made smaller" uses 300 px: 230 px is below the least of a card whose head and footer
never give way.

**D3. The fade.** `useMore` stays the one measure (`scrollTop + clientHeight < scrollHeight −
1`, on scroll, resize, and content); its class becomes `has-more` on the box itself, and the fade
is a `mask-image` on it (report 22 px, recommendation 26 px), not a pseudo-element over a ground,
so it holds on any ground and in both themes. "↓ more" goes with its button. Needs you and Flows
(`whole`) compute nothing: no mask, no `max-height`.

**D4. The recommendation.** One component, `Recommendation`, in every place; `RecommendationBar`,
`oneLine`, `unmarked` and their tests go. Given: `.rec` (`--panel`, 1 px `--line`, radius 6,
padding 8/12), a head of `MiniAvatar` + "supervisor recommends **<option>**" (the card's label of
the option; without one of the card's options, "supervisor"), the time right, 12 `--muted`; then
`.rec-text`, `Body` in a box `max-height: var(--adv)`, `overflow: auto`, `overscroll-behavior:
contain`, `tabindex=0`. `--adv` is the splitter's height (D5), by default 82 px (4 lines) and 42
px (2) on a phone. `role="note"` with the aria-label "Supervisor's recommendation" and, when it
disagrees, ", disagrees with the step's report" on a gate or ", disagrees with <agent>" on a
question; then `.rec.against` has a `--warn` frame and `AlertIcon` (16 px, `--warn`) before the
avatar in a `Tooltip` with that text. A gate whose note's author is the lead (`rec.by === LEAD`)
shows no disagreement. `asked`: the italic muted line "Supervisor is preparing a recommendation…",
no block; `missing` and none: nothing (`WAITING.missing` goes from the UI; `lado answer` keeps
its own). Props: `rec`, `options`, `label`, `kind` ("gate" | "question"), `whole`.

**D5. The recommendation's splitter.** The shared `Splitter` (`edge="top"`, `grip`, label "Resize
the recommendation"), placed by the panel between `.waiting-scroll` and `.waiting-foot` only in
the chat, with a given recommendation, not in the `whole` card. `width` is `--adv`; bounds `min`
20 (one line), `initial` 82 (phone 42), `max` = min(the text's whole height, the room the report
gives down to 56 px plus what the feed gives down to its 160 px), measured with `useHeight` on
the report, the text's box and the text (built so, agreed with the supervisor on 2026-11-10: on
a phone the report is at 56 px from the start, and the room at which it is 56 px alone left the
splitter nothing to move; once the report is at its least the card grows into the feed, as its
edge does). `onReset` goes back to
`initial`. The value is one in the browser, `lado.recommendationHeight` in `prefs.ts`, as the
card's `lado.waitingHeight` is: one for every card and session. CSS: in the column's flow, 8 px
high over the border (`margin: -4px 0`), a 1 px line of `--human` 35 % always, 2 px `--action` on
hover, focus and drag; a phone 24 px (`margin: -12px 0`, `touch-action: none`). In the expanded
card it stays, with more room for `max`.

**D6. No splitter tooltip.** `Splitter` takes `hint = true`; `hint={false}` leaves out its `title`.
The card's two splitters pass `false`; the artifact panel's and the columns' keep theirs (the
artifact panel is out of scope). Rejected: dropping `title` whenever `grip` is set, which would
change the artifact panel too.

**D7. The tabs.** A gate's tab keeps `gate.run` (it is the run's name already), `max-width:
220px` (170 at 600 px or less) with an ellipsis, and gets a `Tooltip` of two `.tooltip-line`s:
"step <state>" and, when the gate keeps a note, "report by <note_by>". The tooltip shows on hover
and focus only: the tab is a button, so `Tooltip`'s touch rule shows none on a tap. `.waiting-tab-
count` wears `--count-ink` on `--raised`, 11/600.

**D8. `GateInfo.note_by`.** `gate_info` sets it from `runs.recommendation_by(gate)`, already
called there for the recommendation; `None` for a gate with no note. `make web-types` regenerates
`openapi.json` and `api.gen.ts`. No schema change: the note's actor is stored.

**D9. Chips.** `Note` and `Reads` give one `.chips` row: the note's attachments, then `reads`,
without a `full_name` seen before. `Attachments` takes `titled` (the card's): the chip shows the
artifact's `title`, else the short name, and no size, no `title` attribute; its aria-label stays
"Open artifact <full name>". `Reads` uses the same chip (a found artifact's title, else its short
name; before the list loads a muted name as now). "It reads" and `.gate-read-about` go; the
`ul aria-label="Artifacts it reads"` goes with the separate list. Chips 30 px (44 at 600 px or
less); on Needs you they are buttons as in the chat (they already open `useView`).

**D10. The note.** `.gate-note` loses its left border and padding; its summary 14/600, its body
14/1.45 with headings 14/600. `Preview`'s 20 lines and Show more stay (not in the design's words
to remove).

**D11. Fields.** `cardLines` returns `[1, MOST_LINES]` (8) in every state; `FIELD_LINES` goes.
The field is 40 px on one line, 44 px at 600 px or less; the gate's placeholder is "Comment for
the next step (optional)", at 600 px or less "Comment (optional)" by a `matchMedia` of the narrow
query (`usePhone` is not the width). The Flows card's 3 to 8 lines stay.

**D12. Questions.** Skip is a pill `.waiting-option.other` after Other…, "Skip", as in 0.44;
`SkipQuestion` and `.waiting-skip` go, and the text of the field stays "Why you skip it
(optional)". A question with no choices and a free answer is picked `{ own: "" }` ahead in
`pickOf` (counted answered only with words or files, as now), shows the field at once with the
placeholder "Your answer" and the aria-label "Your answer to: <question>", and has no Other…; Skip
toggles it to a skip and back. A tab of one question: its text the head, its details the report,
then in the footer the recommendation, the choices' area (`ChoicesArea` with Skip in it), the
field and Send. Several: no head; the list in the report with no padding, each question 12/16/14,
parted from the one before by the same 35 % line; each question's own recommendation is the same
block (D4), whole, as the report scrolls. "k of N answered" stays as in 0.44 and main, gone once
all are answered. As a pill among the choices, Skip scrolls with them when they scroll and
steps aside with them on a phone while a field has the focus (the supervisor's choice of
2026-11-10: the scenario "Six long choices in a low window" says Skip is among the choices and
Send in sight, no longer "Send and Skip"). On a phone the answer's buttons share the footer's
width and "k of N answered" takes its own line.

**D13. The composer.** On a computer the card no longer folds the composer: `foldLine` is only
for the phone's `typing` (gate: "Commenting on gate #<id> above"; question: "Answering question
#<id> above · Write to supervisor instead"), so `fields` and `closing` count only while `typing`.
`ComposerFold`, drafts and the quote's closing stay for the phone. "Choose an answer first" stays
on a Send that is off.

**D14. Needs you and Flows.** The card takes `whole` where it is not in a chat (Needs you) and
`GatePanel` takes it on a run's page: `.waiting-scroll` and `.rec-text` `overflow: visible;
max-height: none`, no `has-more`, no splitter. Flows' `Now` drops the `header.gate-head` with
`gateTitle` (kept for the closed gate's line) and renders `GatePanel` with the head (kicker "Waits
for you · <since>" in it, `--muted`, 12/600 caps), the note, the chips, the recommendation, the
comment and the buttons: `compact` goes, as nothing else uses it.

**D15. Tokens.** `tokens.css` adds `--count-ink: light-dark(#3d4350, #c9ced8)` and `--human-head:
light-dark(#f8e0c9, #46321f)`; `tokens.test.ts` checks their contrast (≥ 4.5:1 for `--count-ink`
on `--raised`, `--ink` and `--muted` on `--human-head`).

**D16. Tests by layer.** vitest for the logic a browser need not run: `has-more` by
`scrollHeight`, the recommendation's states and aria-labels, the tab's tooltip, chips' text,
`pickOf` of a question with no choices, Splitter's `hint`, the composer folding only on a phone.
UI e2e (`tests/ui`, marker `ui`) for layout and scroll: heights, the splitter's drag and keys,
whole cards on Needs you and Flows, the phone. Unit (`tests/test_server_gates.py`) for
`note_by`. No integration test: nothing crosses processes that the existing gate tests do not
cover.
