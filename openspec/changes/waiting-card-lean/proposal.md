Task: LAD-266

## Why

Symptom (audit `ui-review/gate-card-audit`, session gate-ui): in 0.45 the waiting card, what waits
for the human (a flow's gate, an agent's questions, the supervisor's recommendation), reads as
wordy. The recommendation is cut to one line and opens by a click, "↓ more" and "It reads" label
the parts, the composer folds into a sentence while an answer field is open, Skip became a text
button beside Send, and the question's line carries a mono meta `ship/x · check · gate #1` that
says again what the tab says. The human wants 0.44's look back, with only the changes of the
approved design (`ui-design/gate-card-lean-3`: spec, design-system, mockup, brief, critique).

Cause: LAD-194 (0.45) solved a real problem, the comment and the recommendation lying under the
card's scroll with no sign of them, by splitting each tab into a title, a context that alone
scrolls and a footer that is always whole, and then fitted the footer into its room by cutting
what stands in it: the recommendation to one line, the fields to 4 lines, Skip to a text button,
the composer to a line. Each cut added a word or a control to explain it. The footer that stays in
sight is right; the cuts are what reads as wordy.

Options weighed:

- A: revert the card's files to v0.44.0 and apply the design there. The simplest to compare with
  the mockup, but it also drops what 0.45 added to the card and the design keeps: a lost
  connection's Retry (LAD-195), a stopped session's note (LAD-196), the phone's keyboard
  (LAD-194), the 601 to 900 px layout (LAD-193). Each would have to be built again.
- B (taken): keep main's card and its parts (`waitingParts.tsx`), and change in place what the
  design changes: the question becomes a filled head, the recommendation a block whose text
  scrolls in its own box under the LADO `Splitter`, the fields and Skip as in 0.44, the composer's
  fold goes. The diff is larger than A's in the card and smaller in total, and nothing 0.45 fixed
  comes back.
- C: keep main's card and change only the words (titles, labels). Small, but the one-line
  recommendation and the 40 % rule stay, and these are what the human rejected.

## What Changes

In every card (a gate, a loop-limit gate, an agent's questions, a worker's question), in the chat,
on Needs you, on a run's page in Flows, on a phone and in the dark theme:

- The question is the card's head: a filled band (`--human-head`, a new token) the frame's width,
  no border and no line under it, one line with "…" whose tooltip shows the whole text (the
  human's decision of 2026-11-10: no scroll in the head). A tab of several questions has no head: each question keeps its number and text.
  The mono meta beside the question goes.
- In the chat only the report scrolls (a fade at its lower edge while more is below, no "↓ more");
  the recommendation, the comment and the buttons stay in sight. The card is at most half the
  chat, as in 0.44.
- The recommendation is a white block over the answer: "supervisor recommends **<option>**" and
  the time, then its text in a box of 4 lines (a phone: 2) that scrolls with a fade; no "more",
  no left band. A disagreement is an amber frame and ⚠, its words only for a screen reader and in
  the icon's tooltip. No recommendation, or a missing one, shows nothing.
- Between the report and the recommendation, in the chat, a LADO `Splitter` with its grip gives
  the recommendation more or less height; the height is kept in the browser. Neither the card's
  edge nor this one has a tooltip; each has only its name for a screen reader.
- A gate's tab shows its run's name and a tooltip of the step and who wrote the report. A tab's
  count wears `--count-ink` (a new token, ≥ 4.5:1).
- The documents of a gate are one row of chips with their titles, no size, no "It reads".
- Fields open on one line and grow to 8. A question without choices shows its field at once.
  Skip is a pill among the choices again, as in 0.44. Questions of a tab are parted by a line,
  not white blocks. The composer no longer folds on a computer.
- On Needs you and on a run's page the card is whole: no scroll inside it, no fade, no splitter;
  the page scrolls. A run's page shows the gate's report and chips too, with no "Gate #n · run ·
  state" title over it.
- The API gives a gate its report's author (`GateInfo.note_by`).

## Scope

The waiting card (`WaitingCard.tsx`, `GateCard.tsx`, `waitingParts.tsx`, `Recommendation.tsx`),
its use on Needs you (`NeedsYou.tsx`) and in Flows (`Flows.tsx`), the chat's fold
(`Chat.tsx`, `Composer.tsx`), `Splitter.tsx` (a switch for its tooltip), `tokens.css`,
`styles.css`; the server's `GateInfo` (`models.py`) and the generated types; `docs/design/ui.md`,
CHANGELOG.md. The minor is bumped: `0.45.1 (unreleased)` becomes `0.46.0 (unreleased)`.

## Out of scope

- The artifact panel a chip opens: the human's decision, it stays as in main.
- The loop-limit gate's words and behaviour ("loop limit reached at …: what next?", Continue,
  Cancel run with no confirmation): the human's decision; only the card's common rules apply.
- Sending a tab's answers: all at once, as in main (the human's decision); no pager. "Choose an
  answer first" on a Send that is off stays (the human's decision of 2026-11-10).
- The whole question repeated first in the report when the head is cut (main's rule): the
  head's tooltip shows it instead (the human's decision of 2026-11-10).
- Closed cards (a closed gate's line, a closed question's card) and `lado answer`'s texts,
  "The supervisor gave no recommendation." there included: the design does not touch them.
- The feed's lines of an open gate or question ("<agent> asked: … ↓"): as in 0.44 and main
  (brief, change 3).
- A tooltip on the tab on a touch screen: the UI's rule shows no tooltip of a button on a tap;
  the run and step are in Flows.
- The card's minimize, expand, the edge above it and the phone held sideways: as in main.
- The phone's keyboard (the human's decision of 2026-11-10, to be checked in a simulator after
  the build): as in main (LAD-194, checked on an iPhone): a field in focus hides the
  session's tabs, the Team row and the report, and the composer is the line "Commenting on gate
  #<id> above" / "Answering question #<id> above". The computer's fold goes.
- The 601 to 900 px layout (LAD-193): the card's footer and the composer stay in sight as there.

## Acceptance criteria

- AC-1: in a chat at 1440, 768 and 390 px, a gate with a long report and a long recommendation
  shows its head, the recommendation's line, the comment and the buttons without scrolling; only
  the report scrolls, with a fade while more is below it, gone at its end.
- AC-2: the card is at most 50 % of the chat; short of room only the report gives way, down to
  56 px.
- AC-3: the question is a head on `--human-head`, not inside the report's scroll, one line cut
  with "…" and a tooltip of the whole text (hover, focus, tap) when cut; no meta beside it; the
  agent's tab of several questions has no head.
- AC-4: a given recommendation is a block "supervisor recommends <option>" with the time, its text
  in a box of 4 lines (a phone: 2) that scrolls, with a fade until its end; no "more"/"less"; a
  disagreement is a `--warn` frame and ⚠ with the aria-label "…, disagrees with the step's report"
  / "…, disagrees with <agent>"; `asked` says "Supervisor is preparing a recommendation…";
  `missing` and none show nothing.
- AC-5: in the chat a splitter between the report and a given recommendation changes the
  recommendation's height (drag, ↑/↓, a double click back to 4 lines), kept after a reload; none
  without a recommendation, on Needs you or in Flows.
- AC-6: neither the card's edge nor the recommendation's splitter has a `title` or a tooltip;
  their names are the aria-labels "Resize the card" and "Resize the recommendation".
- AC-7: a gate's tab reads the run's name and its tooltip "step <state>" / "report by <author>";
  the tab's count is `--count-ink` on `--raised`.
- AC-8: a gate's documents are one row of chips showing each artifact's title (its short name
  without one), no size, no "It reads"; a chip opens the panel as in main, on Needs you too.
- AC-9: the card's fields open on one line (40 px; 44 px at 600 px or less, placeholder "Comment
  (optional)") and grow to 8 lines; a question without choices shows "Your answer" at once; Skip
  is a pill after the choices; questions of a tab are parted by a line of `--human` at 35 %.
- AC-10: on a computer an open Other… or Skip leaves the composer as it is; on a phone a field in
  focus folds it as in main.
- AC-11: on Needs you and on a run's page the card is whole (no `max-height`, no fade, no
  splitter), and the run's page shows the report and chips, with no "Gate #n · run · state".
- AC-12: the loop-limit gate's words and buttons are as in main.
- AC-13: light and dark match the mockup; `docs/design/ui.md` and CHANGELOG.md are updated.

## Impact

`web/src/WaitingCard.tsx`, `GateCard.tsx`, `waitingParts.tsx`, `Recommendation.tsx`,
`NeedsYou.tsx`, `Flows.tsx`, `Chat.tsx`, `Composer.tsx`, `Splitter.tsx`, `Attachments.tsx`,
`fieldHeight.ts`, `prefs.ts`, `tokens.css`, `styles.css`, `api.gen.ts`, `openapi.json`; their
vitest files; `src/lado/server/models.py`, `tests/test_server_gates.py`; `tests/ui/test_gates.py`,
`test_chat.py`, `test_phone.py`, `test_needs_you.py`, `test_flows_tab.py`,
`test_narrow_layout.py`; `docs/design/ui.md`, CHANGELOG.md. Living specs: chat-question-card,
lead-recommendation, phone-layout, flows-overview.
