Task: LAD-194

## Why

Symptom (audit of LAD-189, findings F14, F18, F19): on a gate's tab the comment field and the
supervisor's recommendation lie under the card's inner scroll with no sign of anything below,
while Approve stays in sight. A gate is easy to approve without seeing either, and the
recommendation is the main argument for the decision. By default the card takes about 41 % of
the window's height, whatever it holds. With Other… open, "Your own answer" stands right above
the composer: two fields to the same reader, and Skip reads as one more choice.

Cause: since LAD-28 the card has two parts, a list that scrolls and a Send row that does not.
Everything but the buttons went into the list, also what the human must act on, so its height
rule (half the chat) and its scroll apply to the answer as much as to the context. LAD-126 then
patched the phone, where the list left no room for a field, by expanding the card on a field's
focus.

Options weighed:

- A: keep the list and show a fade at its lower edge. Smallest diff; the field and the
  recommendation stay hidden behind a scroll, only better announced.
- B (taken, LAD-189 spec §3): title, context and footer; only the context scrolls, the footer
  is always whole and outranks any height limit. The phone needs no expansion any more. It costs
  a rewrite of the panel's layout and of the tests that measure it.
- C: move the answer out of the card into the composer. One field for everything, and one
  place for the human's words; it breaks a gate's comment with files, a tab of several questions
  and Needs you, which has no composer.

## What Changes

- An open tab of the waiting card is a title (at most 2 lines), a context (the one part that
  scrolls, with a fade and "↓ more") and a footer (recommendation, comment or choices, buttons)
  that is always whole. The card is as high as its content; title and context together are at
  most 40 % of the chat, and the footer does not count in that.
- A footer taller than its room gives way in spec §3's order; the buttons are always in sight.
- The recommendation is one line in the card, with its disagreement right after the option.
- The card's fields open 1 line high and grow to 4.
- Skip is a text button "Skip question" beside Send; it behaves as before.
- While a field of Other… or Skip question is open, the composer folds into a line, and its link
  brings the composer back and keeps the field's words.
- A Send that is off has the tooltip "Choose an answer first".
- On a phone a field's focus no longer expands the card: the context and the Team row go, the
  composer folds. The card's targets are 44 px.

## Scope

The waiting card, in a session's chat and on Needs you, at every width, and the composer's fold.
The web UI alone: no API, schema, MCP or CLI change. `docs/design/ui.md` and CHANGELOG.md in the
same pull request. The minor is not bumped by this change: `0.45.0 (unreleased)` is open.

## Out of scope

- The error and Retry under the buttons when the connection is lost: LAD-195, as planned there.
- The layout of narrow widths: LAD-193. The card must not depend on it, so its limit uses the
  window where the chat has no height.
- `PHONE_QUERY`: LAD-193 too; the card reads `usePhone()` as it is.
- Stop and the menu at 44 px, the composer's Send: not the card's; spec §9 lists them for the
  tasks of those parts.
- A gate's card on a run's page in Flows: it scrolls with its page and has no such problem. Its
  field and recommendation block stay as they are.
- Expand at 85 % of the height (spec §3): the human's decision of 2026-11-05 keeps the card
  filling the chat, because Esc, Skip to chat and the phone rest on it, and 85 % leaves a strip of
  feed of no use.
- Skip that dismisses at once: the human's decision of 2026-11-05 keeps the comment and Send; a
  dismissal cannot be taken back, and a tab of several questions is sent as one.
- One question at a time in a tab of several: the human's decision of 2026-11-05; it needs a
  pager that neither spec nor frames have, and hides the other questions.
- A real iOS Safari keyboard: nobody in the run has a device. Frame g3-390-kbd is an imitation;
  the human checks it before the merge, and the build report says "not verified".

## Acceptance criteria

- AC-1: at 1440, 768 and 390 px wide, with a long context, on a gate and on a question, the
  recommendation, the field or choices and the buttons are in sight without scrolling; only the
  context scrolls.
- AC-2: the card is as high as its content; title and context together are at most 40 % of the
  chat; at 1440×900 with terminals open a usual gate's card is about 292 px high (was 372).
- AC-3: a cut context fades over 28 px and shows "↓ more", which expands the card; both go at
  the end of the scroll and in the expanded card. The context is a focusable region.
- AC-4: the title is at most 2 lines with "…", the whole text first in the context; the meta
  stands at its right, on a phone under it.
- AC-5: with a long question and six choices at 1440 and 390, and in a chat 420 px high, the
  buttons are in sight; the choices' area is by content to 4 rows (about 160 px; a phone 148 px),
  then scrolls with a fade.
- AC-6: the states "no recommendation asked", `asked`, `missing`, given and given with a
  disagreement each show as specified, and the recommended option stays primary or picked
  with ✓. A click opens the line to 3 lines that scroll; the expanded card shows it whole.
- AC-7: the fields open 1 line high, 36 px (a phone 44 px), and grow to 4 lines (8 expanded).
- AC-8: Skip question is a text button beside Send, opens "Why you skip it (optional)", and goes
  with Send.
- AC-9: while Other…'s or Skip's field is open the composer is the line "Answering question
  #<id> above · Write to supervisor instead"; its link and a quote bring the composer back, the
  field's draft and files survive, and so does the composer's own text.
- AC-10: a tab of several questions lists them in the context, and Send with the count stands in
  the footer.
- AC-11: a Send off for want of an answer has the tooltip "Choose an answer first".
- AC-12: the height the edge gives is kept for all cards, the footer never gives way to it, and a
  double click gives back the content's height.
- AC-13: on a phone with the app 440 px high a field's focus keeps the card unexpanded, hides the
  Team row and the context, folds the composer, and keeps field, buttons and line in sight.
- AC-14: on a phone the card's tabs, Minimize, Expand, fields, chips and buttons are 44 px high.
- AC-15: on Needs you, and on a window of 900 px or less, title and context are at most 40 % of
  the window, and the footer follows them.
- AC-16: light and dark themes match frames g3-*; `docs/design/ui.md` and CHANGELOG.md are updated;
  the flaky test of BACKLOG.md is settled, its cause named.

## Impact

`web/src/WaitingCard.tsx`, `GateCard.tsx`, `Recommendation.tsx`, `attachFiles.tsx`,
`fieldHeight.ts`, `Chat.tsx`, `Composer.tsx`, `styles.css`, a new `web/src/waitingParts.tsx`;
their vitest files; `tests/ui/test_gates.py`, `test_chat.py`, `test_phone.py`,
`test_needs_you.py`; `docs/design/ui.md`, CHANGELOG.md, BACKLOG.md. Living specs:
chat-question-card, lead-recommendation, phone-layout.
