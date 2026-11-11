## 1. The row (web)

- [ ] 1.1 `tests/ui/test_session_list.py`: a failing test first, in the light and the dark
  theme (`@pytest.mark.parametrize("theme", ...)` as the file's first test). The sessions
  (`/api/sessions` routed): one `tmux_gone`, one `loop_down` with a gate waiting, one running.
  For each trouble row the `.status` element's computed `color` equals the resolved `--danger`
  (read from an element styled `color: var(--danger)`, e.g. the head's or a `.danger-text`),
  its `::before` `background-color` is that colour and its `border-style` is `none`; the
  `loop_down` row is under Needs you (AC-1, AC-2, AC-3). Screenshots of the list in both
  themes as run artifacts.
- [ ] 1.2 `web/src/styles.css` by D1 and D2. `make web` green.

## 2. Documents and regression

- [ ] 2.1 `docs/design/ui.md`: the session list's rows (about line 518) say the status of a
  session in trouble is in `--danger` after a full `--danger` dot, the head's (LAD-229); Look
  (about line 3682) names the list's row beside the head where `--danger` marks a session
  that needs an action (AC-4).
- [ ] 2.2 CHANGELOG.md, `## 0.46.1 (unreleased)` on top, `### Fixed`: a broken session stands
  out in the session list, its status in red as in its head (AC-5).
- [ ] 2.3 BACKLOG.md: remove the entry "A row's trouble status is grey where the design says
  red" (AC-5).
- [ ] 2.4 Regression: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_session_list.py tests/ui/test_layout.py`, `openspec validate trouble-row-red
  --strict` and the trial archive of the settings' Checks.
