## 1. The window (web)

- [ ] 1.1 `web/src/Launch.test.tsx` (vitest): failing tests first. Beside a stopped session the
  window shows one start button, `Start new session webapp-2`, primary, and no `Resume webapp`;
  the line `Session webapp stopped here` stays (AC-1); Enter with Task empty posts `POST
  /api/sessions` for `webapp-2`, nothing to `/resume` (AC-2); in a project, `Start new session in
  Shop` alone (AC-3). The tests of `Resume webapp` beside a new start ("sends only what the human
  changed", "sends the fields the human changed", the Resume with a task, and the rest that press
  it) are removed or turned into these.
- [ ] 1.2 `web/src/Launch.tsx` by design D1 and D2: remove `resumeStopped`, the second button,
  the `two` layout, `changedFrom`'s `onlyTouched`; `act()` starts; keep `stopped` for the line
  under Where and the start button's label. Drop `.launch-buttons.two` from `web/src/styles.css`
  when nothing else uses it. Tests of 1.1 pass; `make web` green (lint, tsc, vitest, build).

## 2. In a browser (UI e2e)

- [ ] 2.1 `tests/ui/test_launch.py`: `test_scenario_1_a_new_session_beside_a_stopped_one_with_a_task`
  checks one button, primary, no Resume, and the start of `my-repo-2` with the task (AC-1).
  `tests/ui/test_launch_project.py`: the taken name shows `Start new session in Shop` alone (AC-3).
- [ ] 2.2 `tests/ui/test_launch_model.py`: the task's scenario 1 with the fake providers
  `fake-claude` (`CloudClaude`) and `fake-codex` (`CloudCodex`), neither logged in: a session on
  `fake-claude`/`CloudClaude` stopped, a later one on `fake-codex`/`CloudCodex` in the same folder;
  New session there offers no Resume; the stopped session's Resume window resumes it on
  `fake-claude` and `CloudClaude` (`state` shows its provider and model) (AC-4). Screenshot of the
  New session window beside a stopped session as a run artifact.

## 3. Documents and regression

- [ ] 3.1 `docs/design/ui.md`, Launch and session control: "The name and Resume beside a new
  start" becomes "The name beside a stopped session": the free name, the line under Where, one
  start button; Resume only from the session's page or list. Grep `docs/` for `Resume <name>`
  beside a new start and fix every hit.
- [ ] 3.2 CHANGELOG.md, `## 0.45.1 (unreleased)` (add it on top), Changed or Fixed: New session
  no longer offers Resume beside a stopped session; it starts a new one, and a stopped session is
  resumed from its page or the session list (AC-5).
- [ ] 3.3 Regression: `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_launch.py tests/ui/test_launch_project.py tests/ui/test_launch_model.py`,
  `openspec validate new-session-without-resume --strict` and the trial archive of the settings'
  Checks.
