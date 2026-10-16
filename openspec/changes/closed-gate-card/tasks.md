## 1. The comment once (D1)

- [ ] 1.1 `web/src/GateCard.tsx`: `GateLine` without `.gate-comment`; `web/src/styles.css`:
  the `.gate-comment` rule removed. Check: vitest of 4.1 (the line without the comment;
  the move keeps it).

## 2. The closing's event from the server (D3)

- [ ] 2.1 `src/lado/state.py`: `gates.closed_event` in the schema; `_add_event` returns
  its id; `update_run` stores the first event written after `_close_gate` as the closed
  gate's `closed_event` in the same transaction; `Gate.closed_event` read with the gate.
  Check: Python unit tests of D4 (an answer, a loop limit's continue and cancel,
  `flow-set`, a run's cancel, a gate state answered twice, two runs closing in turn, an
  open gate).
- [ ] 2.2 The migration: `SCHEMA_VERSION = 30`, `MIGRATIONS[29]` (the column, then the
  backfill: the run's first event after the gate's `gate_answer`, `#<id>` prefix);
  `tests/agent_helpers.previous_schema` / `schema_before` undo it. Check: a migration
  test from version 29 with gates closed each way, one open, one whose events are gone
  (NULL); the existing migration tests.
- [ ] 2.3 `src/lado/server/models.py`: `GateInfo.closed_by_event` with its comment;
  `make web-types` (commit `web/openapi.json` and `web/src/api.gen.ts`). Check: the
  server's gates test reads it from `GET /api/sessions/{name}/gates`; `make web`.
- [ ] 2.4 `web/src/Chat.tsx`: `gateOf` by `closed_by_event` (the time and state rules
  go), `moveOf(gate, events)` next to it; `Rows` passes the gate's move and the run's
  flow states to `GateLine`; fakes in tests get the field. Check: vitest in
  `web/src/feedRows.test.ts` (a gate visited twice; an event of the same time and state
  with another id not taken; none for an override or a cancel).

## 3. The opened card (D2)

- [ ] 3.1 `web/src/GateCard.tsx`: the opened card `.gate-closed-card` in D2's order: the
  question; the answer plaque `.gate-answer` (mini avatar, who, `OutcomeChip` and "→
  <state>" with a move, else the answer word; time; the comment as `Body breaks`); the
  folded **Note** line (`<details>`, summary + "· N artifacts", body as `Preview` of
  `CLOSED_NOTE_LINES = 6`, `Attachments short`); the folded **Supervisor** line
  ("recommended <option>", "· you agreed" / "· you answered otherwise", the lead's
  disagreement in orange; its text opened). The card stays a quote area of its session
  (`quoteArea`, selection-actions). `web/src/styles.css`: `.gate-closed-card`,
  `.gate-answer`, the folded lines' rules, after the mockup
  `task/lad-85/mockup-gate-expanded.html`, light and dark by the tokens. Check: vitest
  of 4.1; `make web`.

## 4. Tests

- [ ] 4.1 `web/src/Chat.test.tsx`: replace "a closed gate is a line with its answer and
  comment…" and "a closed gate opened shows the recommendation as one quiet line…" with
  tests of the delta's scenarios: The human rejects with a comment (one copy, under the
  move); The same gate answered twice; A gate closed otherwise (no reason under the line; on the cancel's line); A long
  note (30 lines, 2 artifacts: folded, then 6 lines, Show more, 2 chips); The
  recommendation folded; The answer agreed; Nothing to fold; Closed by an agent; the
  card still has no textbox, no option buttons and no reads. Check: `make web`.
- [ ] 4.2 `tests/ui/test_gates.py`: in the reject test the line no longer contains "split
  the form first", the move does; opening the line shows the question and the plaque
  with the comment, the Note line folded, then opened (`shot` of the line, the card, the
  opened note). Check: `uv run pytest -m ui tests/ui/test_gates.py`.
- [ ] 4.3 The tests catch the bug: 4.1's one-copy test fails on main's `GateCard.tsx`
  (a temporary checkout of that file, restored after); name the run in the build report.

## 5. Docs

- [ ] 5.1 `docs/design/ui.md` (Flow gates: "A closed gate is a quiet line…": the title and
  time without the comment; the opened card of D2; LAD-85, mockups
  `task/lad-85/mockup-gate-comment.html`, `task/lad-85/mockup-gate-expanded.html`; `GateInfo.closed_by_event` where the doc lists
  `GateInfo`); CHANGELOG.md, a line under `## 0.40.0 (unreleased)`.

## 6. Regression

- [ ] 6.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui tests/ui/test_gates.py
  tests/ui/test_chat.py`, `openspec validate closed-gate-card --strict`,
  `openspec validate --specs --strict`.
