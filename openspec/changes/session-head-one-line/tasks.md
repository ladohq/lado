## 1. The failing tests

- [x] 1.1 vitest: `Layout.test.tsx`, `SessionDetails.test.tsx`, `Menu.test.tsx`,
  `Shell.test.tsx`, `Chat.test.tsx`, `SystemPanel.test.tsx`, `TitleEdit.test.tsx` by the plan's
  table. Run: `make web`.
- [x] 1.2 UI e2e: `tests/ui/test_session_head.py`, `test_phone.py`, `test_launch_project.py`,
  `test_project_page.py` by the plan's table, tests of the old line replaced. Run: `uv run
  pytest -m ui <files>`.

## 2. The facts

- [x] 2.1 `SessionDetails.tsx`: `SessionFacts` and the sheet around it, Copy URL in the row
  (D1). Check: `SessionDetails.test.tsx`, `test_phone.py`.

## 3. The line

- [x] 3.1 `styles.css`: `--head-h`, `.topbar`, the `52px` uses, shrinking, dead rules out
  (D6, D7). Check: the 48 px test.
- [x] 3.2 `Sessions.tsx`: `HeadLine` with breadcrumb, title button, words, branch, status dot
  without a stop (D8, D10). Check: `Layout.test.tsx`.
- [x] 3.3 `SessionControl.tsx`, `SystemPanel.tsx`: Stop's word, the link's tooltip, phone
  sizes (D9, D11, D12). Check: the width tests.

## 4. Details

- [x] 4.1 `DetailsPopover`, `useDismiss`'s event, the focus rule (D2, D3). Check: the closing
  tests.
- [x] 4.2 Rename in the line, the hint under it (D4). Check: the Rename test, the 48 px test.

## 5. Skip to chat

- [ ] 5.1 `Shell.tsx`'s slot, the link, `Chat`'s focus (D5). Check: the Tab and Skip tests.
  Not checked: with the terminals open, the default on a wide window, the first Tab of a fresh
  page lands in the terminal panel, not on `Skip to chat`; the human's decision is awaited.

## 6. Docs

- [x] 6.1 docs/design/ui.md as the design doc lists; comments of the files changed. Check:
  read against the code.
- [x] 6.2 CHANGELOG.md under `## 0.45.0 (unreleased)`. Check: docs/release.md's rules.

## 7. Regression

- [x] 7.1 The plan's Task 7, with screenshots light and dark as run artifacts.
