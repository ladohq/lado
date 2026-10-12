Task: LAD-25

## Why

When the human answers an agent's question with one of its choices, the closed question
card in the session's chat shows that choice twice: marked "✓ <choice>" in the card's
faded list of choices, and again in bold "✓ <choice>" in the human's reply block under the
list ("You · answered"). The second one reads as if the human had typed it.

The root cause is two design decisions that were each right alone and add up to the
repeat (docs/design/ui.md): "Answer in the question card" (2026-10-07) put the reply,
choice included, in a block at the card's foot; later the closed card started marking the
chosen choice in its list. An answer in the human's own words is not repeated, since its
text is no choice.

## What Changes

- **UI** (`web/src/Question.tsx`, `Given`): in a closed card whose reply is a choice, the
  reply block keeps the small "Y", "You · answered" and the time, and shows only the
  comment that came with the choice, if any; it no longer repeats the choice. The choice
  stays marked "✓" in the card's list, as now. Approved mockup
  `mockup-closed-question.html`, option A.
- Unchanged: an answer in the human's own words (shown in the block as now), a dismissal
  and its comment, "Closed: the agent left", the open card, the quiet late line "You
  answered question #N ↑" with the answer's start (a link to the card, not a repeat
  inside it), and a reply whose question is not in the window.
- The `.answer-choice` style goes, as nothing uses it any more.
- docs/design/ui.md: "A question" and "Answer in the question card" say the block holds
  the comment of a choice, not the choice.
- CHANGELOG.md: one line under `## 0.37.0 (unreleased)`.

## Scope

The closed question card's reply block in the session's chat (and on Needs you, which
shows the same card). Nothing in the core, the API, the MCP tools or the schema.

## Out of scope

- Option B, no list of choices in a closed card: the human would not see what they chose
  from (the human's decision).
- Option C, the author and time beside the chosen choice with no reply block: a larger
  change of layout, and an own-words answer would look unlike a choice (the human's
  decision).
- The late line "You answered question #N ↑": it links to the card from where the answer
  was given; it is no repeat inside the card.

## Acceptance criteria

- AC-1: A closed card answered with a choice and no comment shows the choice once, marked
  "✓" in its list; its reply block has "You · answered" and the time, and no other text.
- AC-2: A closed card answered with a choice and a comment shows the choice once, in the
  list, and the comment in the reply block (Markdown with line breaks, as now).
- AC-3: A closed card answered in the human's own words shows those words in the reply
  block, as now; no choice in the list is marked.
- AC-4: A dismissal, a question closed by its agent's end, and the late line "You answered
  question #N ↑" (which still starts with the choice and its comment) look as they do now.
- AC-5: docs/design/ui.md and CHANGELOG.md say so; vitest and the UI e2e tests of the
  chat check AC-1 and AC-2 and pass.

## Impact

- `web/src/Question.tsx`, `web/src/styles.css`, `web/src/Chat.test.tsx`,
  `tests/ui/test_chat.py`, `docs/design/ui.md`, CHANGELOG.md.
- No API, schema or MCP change: a fix, part of the next release (0.37.0 is already the
  next version for other changes; alone it would be a patch).

## Decisions for the record

- Scale tweak: one component's look, its shape known; review as a tweak.
- A new capability `chat-question-card` in openspec: no living spec covers the chat yet,
  and the rule "a choice is shown once" is behaviour a user sees; docs/design/ui.md stays
  the UI's design record and is updated with it.
- Test layers: vitest (`Chat.test.tsx`) for the card's content, the lowest that sees it;
  the existing UI e2e tests of the chat (`tests/ui/test_chat.py`) assert the old block and
  are changed with it, with screenshots for the reviewer.
- `.answer-choice` is removed from styles.css rather than kept unused (only what is used).
