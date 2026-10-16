## Context

A closed gate is drawn by `GateLine` (`web/src/GateCard.tsx`) where the gate opened,
from `GateInfo` (question, note, note body, the note's attachments, answer, comment,
answered_by, answered_at, recommendation). The human's answer is also the run's move, a
`flow` event of `human` drawn by `RunEvents` (`web/src/Chat.tsx`), which finds its gate
with `gateOf` and draws the comment under it. `gateOf` guesses today: the run, a human
answer, the gate's state as the move's from or to state, and of those gates the one
answered nearest in time. Nothing in lado.db or the API links a gate to the event of its
closing. Every way to close a gate writes an event
that carries the answer: an option is a `flow` move of its answerer; `lado flow-set`
writes `flow_set` with the reason; a cancel writes `flow_cancel` with the reason. Events
and gates come whole to the chat (no window), so the move is always in the feed.

Every closing goes through `state.update_run` in one `BEGIN IMMEDIATE` transaction:
`_close_gate` writes the `gate_answer` event (`#<id> <answer>[: <comment>]`), then the
closing's own event follows (`runs.answer`: the `flow` move; `runs.force`: `flow_set`;
`_cancel`: `flow_cancel`). No other writer can come between them, so the closing's event
is the run's first event after the gate's `gate_answer`. Gates and `gate_answer` were
born together (5f0e932), so every closed gate has one.

Held against AGENTS.md and ROADMAP: no provider, the neutral core untouched; one source of
truth: the core that writes the closing also stores its event, the UI no longer infers it,
and the comment has one place in the feed (the move); only what is used: one API field,
read by the chat in three places (the comment under the move, the card's head and its plaque).

## Decisions

### D1. The comment leaves the gate's line; the line is a folded card

`GateLine` drops `.gate-comment` (and its CSS rule): no comment under a closed gate,
whoever closed it (the reason of an override or a cancel is on its event's line already).

Folded, a closed gate is one line in a card's frame (mockup
`task/lad-85/mockup-gate-line.html`, the human: option 2), so it reads as something that
opens: a `<button>` the card's whole width (`.gate-head`: the panel's background, a 1 px
border of `--line`, radius 8 px, 6 px by 8 px padding, sans 14 px ink; `--raised` on
hover; the focus ring of the UI), starting 8 px left of the text's column, holding:

- the gate's mini avatar with the flag (`avatar mini avatar-gate`, `GateIcon`), as the
  open gate's line;
- "Gate #<id>" in 600, then "<run> · <state>" muted;
- the answer chip: `OutcomeChip` by the closing's move (D3), direction coloured as on
  the move's line, the option's word (`reject`, `approve`, a choice); without a move
  (an override, a cancel, an old gate without its event) the word neutral
  (`.run-outcome`): `overridden`, `cancelled`, the option;
- "by you" for the human, else "by <agent>", muted;
- the time of the answer, muted, at the right; then a chevron (`▾`, an icon) turned up
  while open.

Its accessible name stays the sentence `gateTitle(gate): <answer> by <who>` (an
`aria-label`), with `aria-expanded`: what tests, links (`#gate-<id>`) and screen readers
know keeps its words. `gateTitle` stays the title of a run's page in Flows.

### D2. Opened, the card shows the question and the answer, the rest folded

Opened, the same frame grows down (`.gate-closed-card`: the head's bottom corners square
and its bottom border gone, the body under it with the frame's border, radius 0 0 8 px
8 px, 4 px 14 px 12 px padding, ink text at 14 px), in this order:

1. the question (`.gate-question`);
2. the answer plaque in the look of the human's reply in a question's card
   (`.question-answer`, `.answer-top`: `--action-ground`, the human's ground of the
   chat, not the orange of what waits; the first mockup's orange is dropped): the
   closer's mini avatar, who ("You" for the human, else the agent's name), the answer
   chip as the head's, "→ <state>" when the move is known (D3), the time at the right;
   under it the comment as `Body` with the human's line breaks (`breaks`), when there
   is one. A gate closed by an agent: the same plaque on `--raised` (as a dismissed
   reply, `.question-answer.dismissed`);
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

### D3. The gate keeps the event that closed it (the human, at design_ok: B, then the supervisor's "what I would still want")

`gates` gets a column `closed_event INTEGER` (NULL while open): the id of the run's event
that the gate's closing wrote, a `flow` move, a `flow_set` or a `flow_cancel`.
`state.update_run` stores it in the same transaction that closes the gate: the first of
the `events` it writes after `_close_gate` (`runs.answer`'s transition, `runs.force`'s
`flow_set`, `_cancel`'s `flow_cancel`); `_add_event` returns the id it inserted. The link
is written where both rows are written, not inferred later from their order.

Schema migration `MIGRATIONS[29]` (`SCHEMA_VERSION` 30): add the column, then fill it
once for gates closed before, by the order the transaction kept: the run's first event
after the gate's `gate_answer` event (`#<id>` prefix, written by `_close_gate` since the
gates were born, 5f0e932); a gate for which none is found stays NULL. The backup before a
migration (LAD-71) runs as for any other step; `tests/agent_helpers.previous_schema`
undoes this step.

`Gate.closed_event` is read with the gate's other columns; `GateInfo.closed_by_event:
int | None` gives it to the UI (no subquery, no extra query per gate).

The chat links by id, without a guess:
- `gateOf(event, gates)`: the gate whose `closed_by_event` is the event's id, for a
  `flow` event of the human (the comment under the move); the time and state rules go.
- `moveOf(gate, events)`, next to it: the `flow` event whose id is the gate's
  `closed_by_event`. With it, the plaque's chip is `OutcomeChip` (direction by the run's
  flow states, as on the move's line) and "→ <to_state>"; without it (an override, a
  cancel, an old gate left NULL, or the event not in the feed yet: the gate and its
  events come over the live feed one by one), the chip is the answer word, neutral
  (`.run-outcome`), and no target; a move without its gate shows no comment under it,
  and the comment stays in the gate's card.

Options weighed:
- A, keep the guess and memoise it per render: no API change, but it repeats the core's
  write order in the browser and, after D1, a miss hides the only copy of the comment in
  the folded feed. C, no "→ <state>" in the plaque: the guess stays for the comment.
  (The human chose B over both.)
- B as first designed, derived on read by "the run's first event after `gate_answer`":
  exact while every closing keeps that order, but a rule in a query to keep true; the
  supervisor's recommendation at design_ok asked for the link itself, and the human
  agreed: it is now stored at write time and the rule lives only in the one-time
  backfill.
- The link on the event instead (`events.gate`): the same fact, but `GateInfo` would
  need a join on `events` to give it; the gate's row is what the chat reads per gate.

Version: a schema migration bumps the minor; 0.40.0 (unreleased) is already that minor
(LAD-74's migration), so its CHANGELOG line goes there.

### D4. Tests at the lowest layer

- Python unit (`tests/test_state.py` or the gates' test module, and the server's model
  test): `closed_event` is the `flow` move's id after `runs.answer` (approve, reject,
  a choice, a loop limit's continue), the `flow_set`'s after `runs.force`, the
  `flow_cancel`'s after a run's cancel and a loop limit's cancel; None for an open gate;
  a run that answers the same gate state twice gets each gate its own move; another
  run's events written between two closings never count. The migration: a database of
  version 29 (`previous_schema`) with closed gates of each kind gets each one's event,
  an open gate and a gate whose events are gone stay NULL; `GET …/gates` carries it as
  `closed_by_event`.
- vitest (`web/src/feedRows.test.ts`, `web/src/Chat.test.tsx`): `gateOf` and `moveOf` by
  id (a gate visited twice; an event of the same time and state but another id not
  taken); each scenario of the delta.
- UI e2e (`tests/ui/test_gates.py`): one test in Chromium after a real answer, with
  screenshots of the folded card, the opened card and the human's move (the developer's
  UI rule), light and dark.

No integration test: nothing crosses processes that the unit tests of `state` and the
server do not reach (the UI e2e runs the real server and lado.db).

### D5. The human's move on the human's ground

In a run's group, every line of an event whose actor is the human (`RunEvents`: a `flow`
move answering a gate, a `flow_set`) stands on `--action-ground`, with its comment
under it, radius 8 px, reaching 8 px left of the line (`.run-event.mine`; mockup
`task/lad-85/mockup-gate-line.html`): the ground of the human's own messages
(`.feed-row.mine`) and of their replies in a question's card. An agent's lines keep no
ground. The comment's text stays ink at 14 px (`.run-comment`).
