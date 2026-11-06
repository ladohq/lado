## 1. The fold of the terminals

- [ ] 1.1 `stoppedPanel` in `columns.ts`, `useSessionColumns` with the stopped session's name (D7).
  Check: `columns.test.ts`, `Layout.test.tsx`, `tests/ui/test_stopped_session.py`; AC-7.

## 2. The terminal

- [ ] 2.1 `stopped` on `TerminalPanel`, `StoppedTerminal`, control and Expand end on a stop (D8).
  Check: `Terminals.test.tsx`, `tests/ui/test_terminal_panel.py`; AC-8.

## 3. Resume in the head

- [ ] 3.1 `useResume`, `actionsOf(session, onActivity)`, `.session-resume-word` (D1, D2). Move the tests that
  press `Resume…` on Activity. Check: `Launch.test.tsx`, `connection.test.tsx`,
  `tests/ui/test_session_head.py`; AC-3, AC-5.

## 4. The bar and the feed

- [ ] 4.1 `StoppedBar`, the composer hidden, `stopped` off `Composer`, `stopFiles` (D3, D4, D6, D10).
  Check: `Chat.test.tsx`, `tests/ui/test_stopped_session.py`, `test_launch.py`,
  `test_connection.py`; AC-1, AC-2, AC-3, AC-9.
- [ ] 4.2 `emptyText` by the filter (D5). Check: `Chat.test.tsx`; AC-4.

## 5. The team on a phone

- [ ] 5.1 `Activity` leaves out `Team`, the toggle's words (D9). Check: `Layout.test.tsx`,
  `tests/ui/test_stopped_session.py`; AC-6.

## 6. Documents and regression

- [ ] 6.1 `docs/design/ui.md` (Session head, Terminal, Structure, Phone layout, the chat's feed) and
  the comments of `Terminals.tsx`, `SessionControl.tsx`, `Sessions.tsx`; one item in CHANGELOG.md
  under `## 0.45.0 (unreleased)`. Check: reading them against the code.
- [ ] 6.2 Regression: `make web`, `make test`, `make lint`, `uv run pytest -m ui <changed files>`,
  `openspec validate stopped-session-bar --strict`, the trial archive. Check: AC-10.
- [ ] 6.3 Screenshots of each changed screen at 1440, 768, 390 and in the dark theme as run
  artifacts, with the running URL for the second ui-review. Check: `build-report` lists them.
