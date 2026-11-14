## 1. The opening focus

- [ ] 1.1 A UI test in `tests/ui/test_launch.py` with the recent places held back: the focus moved
  to Cancel stays there when they come, Where shows the last place, Enter closes the window; it
  fails on the current code (check: `uv run pytest -m ui -n0 tests/ui/test_launch.py -k <name>`)
- [ ] 1.2 The same test's second case: the focus untouched lands in Task once the answer comes
- [ ] 1.3 `LaunchDialog` moves the focus on the recent places' answer only from the element focused
  at opening, or the body (D1); 1.1 and 1.2 pass, `make web` passes

## 2. Docs and regression

- [ ] 2.1 `docs/design/ui.md`, Launch and session control: the window keeps a focus the human moved
  before the recent places came
- [ ] 2.2 CHANGELOG.md under `## 0.46.3 (unreleased)`, Fixed: the New session window no longer
  takes the focus to Task when the recent places come late
- [ ] 2.3 Regression: `uv run pytest -m ui -n auto tests/ui/test_launch.py tests/ui/test_layout.py
  tests/ui/test_launch_project.py`, `make lint`, `openspec validate new-session-focus-stays --strict`
