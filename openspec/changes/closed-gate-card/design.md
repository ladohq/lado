## Context

A closed gate is drawn by `GateLine` (`web/src/GateCard.tsx`) where the gate opened,
from `GateInfo` (question, note, note body, the note's attachments, answer, comment,
answered_by, answered_at, recommendation). The human's answer is also the run's move, a
`flow` event of `human` drawn by `RunEvents` (`web/src/Chat.tsx`), which finds its gate
with `gateOf` and draws the comment under it. Every way to close a gate writes an event
that carries the answer: an option is a `flow` move of its answerer; `lado flow-set`
writes `flow_set` with the reason; a cancel writes `flow_cancel` with the reason. Events
and gates come whole to the chat (no window), so the move is always in the feed.

Held against AGENTS.md and ROADMAP: UI only, no provider, the neutral core untouched;
one source of truth: the comment has one place in the feed (the move), the opened card
reads the same `GateInfo`; only what is used: no new API field (the move is found among
the events the chat holds already).

## Decisions

### D1. The comment leaves the gate's line

`GateLine` drops `.gate-comment` (and its CSS rule). The line is its title
(`gateTitle(gate): <answer> by <who>`) and the time, for every closed gate, whoever
closed it: the reason of an override or a cancel is on its event's line already.

### D2. The opened view is a card: the question and the answer shown, the rest folded

Opened, the line shows a card under it (`.gate-closed-card`: the panel's background,
the line colour's border, radius 10 px, 12 px by 14 px padding, ink text at 14 px,
margin-left 14 px as `.gate-closed-text` today), in this order:

1. the question (`.gate-question`);
2. the answer plaque (`.gate-answer`: a 4 px left border of `--human` on
   `--human-ground`, as the open gate's card): the closer's mini avatar, who ("You" for
   the human, else the agent's name), the answer chip, "→ <state> · <time>" when the move
   is known (D3), else the time of `answered_at`; under it the comment as `Body` with
   the human's line breaks (`breaks`), when there is one;
3. a folded line **Note** when the gate has a note, a note body or attachments: its head
   is the note's summary in bold and "· N artifacts" (1 artifact) when it has any; opened,
   the note's body as a `Preview` of 6 lines (`CLOSED_NOTE_LINES`; the open card keeps its
   20, `NOTE_LINES`) with Show more, and its artifacts as chips (`Attachments short`);
4. a folded line **Supervisor** when a recommendation was given: "recommended <option>"
   (named as the card's buttons, `label`), then " · you agreed" or " · you answered
   otherwise" when the human answered and the recommendation names an option (the
   gate's answer compared with it as the core keeps both: the option's own word), and
   the lead's disagreement "· disagreed with <agent>" in orange as today; opened, the
   recommendation's text. Without an option: "Supervisor's recommendation".

The folded lines are `<details>` with a `<summary>`, as `RecommendationLine` is; their
labels in small capitals muted, a fixed column (as the mockup), the head cut with an
ellipsis on one line. Nothing of it is opened when the card opens. `RecommendationLine`
stays for the closed question's card.

### D3. The answer's move comes from the chat's events

`Rows` gives `GateLine` the human's or agent's move that closed it: the inverse of
`gateOf` (the first `flow` event whose `gateOf` is this gate), a new exported helper
`moveOf(gate, events)` in `Chat.tsx` next to `gateOf`. With it, the plaque's chip is
`OutcomeChip` (direction by the run's flow states, as on the move's line) and "→
<to_state>"; without it (an override, a cancel, a run whose flow is not known), the chip
is the answer word, neutral (`.run-outcome`), and no target.

### D4. Tests at the lowest layer

Rendering only, no process crossed: vitest in `web/src/Chat.test.tsx` covers each
requirement's scenarios (the line without the comment, the move with it, the card's
order, the folded lines, 6 lines and Show more, agreed / otherwise, a cancel by the
supervisor). One UI e2e in `tests/ui/test_gates.py` checks it in Chromium after a real
answer, with screenshots of the line and the opened card (the developer's UI rule).
