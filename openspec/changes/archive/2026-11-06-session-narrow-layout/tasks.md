## 1. The failing tests

- [x] 1.1 vitest by the plan's table: `columns.test.ts`, `prefs.test.ts`, `phone.test.ts`,
  `Layout.test.tsx`, `Terminals.test.tsx`, `Chat.test.tsx`, `tokens.test.ts`. Run: `make web`.
  (`Chat.test.tsx` needs none: nothing of `--chat-top` is left to look for.)
- [x] 1.2 UI e2e by the plan's table: `tests/ui/test_layout.py`, `test_gates.py`, `test_phone.py`,
  `test_sessions_strip.py`, `test_terminal_panel.py`, `test_tabs.py`, `test_needs_you.py`. Run:
  `uv run pytest -m ui <files>`. (The new ones are together in `test_narrow_layout.py`.)

## 2. The columns above 900 px

- [x] 2.1 `columns.ts`, `CHAT_MIN`, `STRIP`, the tokens (D1, D2). Check: `columns.test.ts`.
- [x] 2.2 `prefs.ts`: `chosen`, the width by a drag only, the rail's null (D3, D4). Check:
  `prefs.test.ts`.
- [x] 2.3 `useSessionColumns` in `Sessions.tsx`, `TerminalPanel` on it, control (D2, D14). Check: AC-1
  to AC-7 in `test_layout.py`.

## 3. The strips and the tabs

- [x] 3.1 The terminal strip: 32 px, a button per agent (D10). Check: `Terminals.test.tsx`, AC-9.
- [x] 3.2 The list's strip 48 px and the badges (D11). Check: `Layout.test.tsx`, AC-16.
- [x] 3.3 The tabs' levels (D5). Check: `test_tabs.py`, AC-8.

## 4. The still window

- [x] 4.1 601 to 900 px: CSS, the row strip, the strip on the right (D6). Check: AC-10.
- [x] 4.2 The list and the terminals over the session (D6). Check: AC-11, AC-12.
- [x] 4.3 LAD-194's rules out, the card as it was for the human (D7). Check: AC-13, AC-14,
  `test_gates.py`.
- [x] 4.4 A tablet's visible height (D9). Check: a test with a faked visual viewport.

## 5. The phone

- [x] 5.1 `PHONE_QUERY`, comments, the tests that used a mouse in a narrow window (D8). Check: AC-15,
  the plan's list of files.
- [x] 5.2 The Purpose of `openspec/specs/phone-layout/spec.md` (D8). Check: by reading.

## 6. Targets

- [x] 6.1 Title and link on a phone (D12). Check: `test_phone.py`, AC-17.
- [x] 6.2 Spec §9's table against `styles.css`, closing what is left. Check: `test_phone.py` measures
  each row.

## 7. Documents and the round

- [x] 7.1 `docs/design/ui.md` as the proposal's Impact names, CHANGELOG.md (AC-18). Check: by reading,
  `grep -n "900 px" docs/design/ui.md`.
- [x] 7.2 `make web`, `make lint`, `make test`, `uv run pytest -m ui <changed files>`,
  `openspec validate session-narrow-layout --strict`.
- [x] 7.3 Screenshots at 1440, 1280, 1024, 901, 768 and 390, dark too, as run artifacts; ui-review as
  design QA against frames g2-* (AC-19). Run artifact `design-qa`, its findings in section 8.

## 8. After the iPad check and design QA (the human's decision #3826)

- [x] 8.1 A touch screen wider than a phone fits the part it sees, above 900 px too (D9). Check:
  `phone.test.ts`, `test_phone.py` at 1180×734 and 1032×1366.
- [x] 8.2 The column opened last is stored (D1). Check: `prefs.test.ts`, `test_narrow_layout.py`.
- [x] 8.3 Level 1 of the tabs fits a chat of 420 px. Check: `test_narrow_layout.py`.
- [x] 8.4 The diamond on a waiting badge, the marks on the corner, the open badge in view, the link
  a target of 24×28 up to 1100 px. Check: `test_narrow_layout.py`.
- [x] 8.5 BACKLOG.md: buttons that do nothing with the rail opened by hand (review F5).
