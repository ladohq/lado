## 1. The failing tests

- [x] 1.1 vitest by design.md's table. Run: `make web`.
- [x] 1.2 UI tests by design.md's table. Run: `uv run pytest -m ui <files>`.

## 2. The tabs

- [x] 2.1 The toggle as one component; `MessagesChoice` renders both forms (D2). Check: AC-2.
- [x] 2.2 Level 3 and `LAST_FIT` 4, the CSS (D1). Check: AC-1, AC-3, AC-4.
- [x] 2.3 The focus through the trial (D3). Check: AC-5.
- [x] 2.4 `tabScroll` for the tab shown and the focused one (D4). Check: AC-6.

## 3. Words and the tooltip

- [x] 3.1 `STATUS_WORDS` on the Agents tab, an agent's page, the update's list, the names (D5).
  Check: AC-7.
- [x] 3.2 The list button's tooltip, silent while open (D6). Check: AC-8.
- [x] 3.3 `moreName`'s number (D7). Check: AC-8.

## 4. Documents and checks

- [x] 4.1 docs/design/ui.md (the tabs' levels, Messages between agents, the Agents tab, the team's
  list button) and CHANGELOG.md under `## 0.45.0 (unreleased)`. Check: AC-9.
- [x] 4.2 Screenshots of each changed screen at 1100, 1140 and 1160 px and of the Agents tab, as
  run artifacts. Check: against `mockup-tabs-status.html`.
- [x] 4.3 The regression run of design.md. Check: AC-9.
