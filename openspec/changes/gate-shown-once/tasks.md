## 1. No line for the gate's opening

- [ ] 1.1 `web/src/Chat.tsx`: `gate_open` out of `RUN_EVENT_LINES`, its comment saying
  the gate's opening is no line (its row is the gate's); `web/src/styles.css`: the
  `.run-gate_open .run-chip` selector out of the orange rule and its comment.
  Check: vitest of 2.1.

## 2. Tests

- [ ] 2.1 `web/src/Chat.test.tsx`: the test "a run's events in a row are one group…"
  without the `waits` line (its group counts and order follow); the test "gates are in
  time order…" with the order `["Message from you", "done", "Gate #1 waits", "ended"]`
  and renamed for it; a new test with an open gate and a closed one: no
  `li.run-gate_open` in the chat, each gate's row right after the group whose last line
  is the move that led to it, the question only in the gate's row (AC-1, AC-2).
  `cd web && npx vitest run src/Chat.test.tsx`.
- [ ] 2.2 UI e2e: `tests/ui/test_chat.py` (the check that the run group's last line says
  "waits for you" becomes: no line says it, the gate's row follows the group);
  `tests/ui/test_gates.py` (the comment on the gate's opening; no `li.run-gate_open` in
  the feed before and after the answer) (AC-1, AC-2). `uv run pytest -m ui
  tests/ui/test_chat.py tests/ui/test_gates.py`; screenshots of the open and the answered
  gate in the chat attached to `build-report`.

## 3. Documents

- [ ] 3.1 `docs/design/ui.md`, Flow events: `gate_open` is no line (LAD-135): the gate's
  row stands under the move that led to it; drop "`gate_open` "waits for you" (orange;
  the gate's line is under it)".
- [ ] 3.2 CHANGELOG.md, `## 0.43.0 (unreleased)`, Fixed: one line, the gate shows once
  in the chat.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `make web`, the UI tests of 2.2,
  `openspec validate gate-shown-once --strict`, `openspec validate --specs --strict`;
  CI green on the last commit (AC-3).
