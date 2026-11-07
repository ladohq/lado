## 1. The notice

- [ ] 1.1 `tests/ui/test_kits_page.py` (UI e2e, `-m ui`: only a browser resolves the look, and a
  real session makes the core's line): a kit from `small_kit`, a running session with
  `runtime.start_session(str(repo), session, None, "fake", ["default", "wiki"])`; in Remove wiki?
  the line holding the session's name passes `is_a_notice(line, "--warn-ground")`, Remove is
  enabled, and `shot` takes the window in the light and the dark theme. Written first, red on
  `.kit-danger`.
- [ ] 1.2 `web/src/Kits.tsx`: the line takes `className="kit-warning"`.
- [ ] 1.3 `web/src/styles.css`: the rule `.kit-danger` goes. `grep -rn kit-danger web/src tests`
  finds nothing.

## 2. Documents

- [ ] 2.1 `docs/design/ui.md`, Kits, **Remove**: the line about the running sessions is a warning
  notice, Remove stays open, and red is left for a refusal.
- [ ] 2.2 `BACKLOG.md`: the entry "`.kit-danger` in the kit removal window is no notice" goes.

## 3. The checks

- [ ] 3.1 `make lint`, `make web`, `make test`, `uv run pytest -m ui tests/ui/test_kits_page.py
  tests/ui/test_session_list.py`, `openspec validate kit-removal-notice --strict`,
  `openspec validate --specs --strict` and the trial archive of the settings.
- [ ] 3.2 Screenshots of the window in both themes as run artifacts, named in `build-report`.
