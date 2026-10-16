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
truth: the core that writes the closing also names its event, the UI no longer infers it,
and the comment has one place in the feed (the move); only what is used: one API field,
read by the chat in two places (the comment under the move, the card's plaque).

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

### D3. The server names the event that closed a gate (the human, at design_ok: B)

`GateInfo` gets `closed_by_event: int | None`: the id of the run's event that the gate's
closing wrote (a `flow` move, a `flow_set` or a `flow_cancel`); None while the gate is
open, or when no such event is found. `state.py` derives it, next to `_close_gate`, which
writes the events it reads: the run's first event after the gate's `gate_answer` event
(found by its `#<id>` prefix, which `_close_gate` writes). No schema change, no migration:
old gates get it from their events as new ones do. `session_gates` and `get_gate` read it
in the same query as the gate (a subquery), not one query per gate.

The chat links by id, without a guess:
- `gateOf(event, gates)`: the gate whose `closed_by_event` is the event's id, for a
  `flow` event of the human (the comment under the move); the time and state rules go.
- `moveOf(gate, events)`, next to it: the `flow` event whose id is the gate's
  `closed_by_event`. With it, the plaque's chip is `OutcomeChip` (direction by the run's
  flow states, as on the move's line) and "→ <to_state>"; without it (an override, a
  cancel, or the event not in the feed yet: the gate and its events come over the live
  feed one by one), the chip is the answer word, neutral (`.run-outcome`), and no target.

Options weighed (the human chose B): A, keep the guess and memoise it per render: no API
change, but it repeats the core's write order in the browser and, after D1, a miss hides
the only copy of the comment in the folded feed; C, no "→ <state>" in the plaque: the
guess stays for the comment under the move. A stored column `gates.closed_event` would be
exact without reading the `gate_answer` prefix, but needs a migration and a backfill by
the same derivation: not worth it while the transaction holds the order.

### D4. Tests at the lowest layer

- Python unit (`tests/test_state.py` or the gates' test module, and the server's model
  test): `closed_by_event` is the `flow` move's id after `runs.answer` (approve, reject,
  a choice, a loop limit's continue), the `flow_set`'s after `runs.force`, the
  `flow_cancel`'s after a run's cancel and a loop limit's cancel; None for an open gate;
  a run that answers the same gate state twice gets each gate its own move; another
  run's events written between two closings never count. `GET …/gates` carries it.
- vitest (`web/src/feedRows.test.ts`, `web/src/Chat.test.tsx`): `gateOf` and `moveOf` by
  id (a gate visited twice; an event of the same time and state but another id not
  taken); each scenario of the delta.
- UI e2e (`tests/ui/test_gates.py`): one test in Chromium after a real answer, with
  screenshots of the line and the opened card (the developer's UI rule).

No integration test: nothing crosses processes that the unit tests of `state` and the
server do not reach (the UI e2e runs the real server and lado.db).
