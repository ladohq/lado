## 1. The server

- [x] 1.1 `project_title` in `SessionInfo` (D1), `make web-types`. Check: `tests/test_server_*.py`.
- [x] 1.2 `set_project_title` touches the sessions (D2). Check: `tests/test_feed.py`.

## 2. The words and the row

- [x] 2.1 `work` and `about` without the count, `SessionRow` by D3, `ran` in the row (D4). Check: vitest in `web/src/Layout.test.tsx`.

## 3. The card

- [x] 3.1 `SessionTip` as labelled rows, state line, how to go on, kits cut (D4, D7, D8). Check: vitest, by the mockup.
- [ ] 3.2 `Tooltip`'s `side="right"` and the side with more room (D5), the card's CSS (D6). Check: vitest and `uv run pytest -m ui tests/ui/test_layout.py`.

## 4. Documents and checks

- [ ] 4.1 `docs/design/ui.md` (the rows' line, the card, the strip's icons, Tooltip) and CHANGELOG.md under `## 0.45.0 (unreleased)`, group Improved. Check: read against the specs.
- [ ] 4.2 Screenshots of the list and of the card's states, as run artifacts. Check: against `mockup-session-card.html`.
- [ ] 4.3 The regression run of design.md.
