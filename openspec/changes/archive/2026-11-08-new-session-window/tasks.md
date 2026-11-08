## 1. The core

- [x] 1.1 `runtime.free_name` and the agent's step `last_any` "your last session" (D3, D4); `docs/cli.md`. Check: `tests/test_runtime.py`.
- [x] 1.2 Each provider's words for its permission modes, `ModeWords`, `mode_words()` (D7); Claude Code's `auto` and `manual` only as confirmed by `claude --help`. Check: `tests/test_providers.py`.
- [x] 1.3 `src/lado/setup.py`: preview and make of a plain folder, the refusals, the rollback (D8). Check: `tests/test_setup.py`.

## 2. The server

- [x] 2.1 `free_name` in `FolderInfo`, `ProjectLaunch`, `CloneTarget`; project repositories in `/api/folders/recent` (D2, D3); `make web-types`. Check: `tests/test_server_launch.py`, `tests/test_server_project_launch.py`, `tests/test_server_clones.py`.
- [x] 2.2 `ProviderInfo.mode_words` (D7); `make web-types`. Check: `tests/test_server_providers.py`.
- [x] 2.3 `FolderInfo.setup` and `where: {kind: "setup", path, include}` (D9); `make web-types`. Check: `tests/test_server_launch.py`, `uv run pytest -m integration tests/integration/test_setup_start.py`.

## 3. The window

- [x] 3.1 `InfoTip.tsx` (D10). Check: `web/src/InfoTip.test.tsx` in `make web`.
- [x] 3.2 Where as one combobox, `LaunchWhere.tsx`; the switch, the Workspace row and the Recent chips go (D1, D11). Check: `web/src/LaunchWhere.test.tsx`.
- [x] 3.3 Task, Team (`LaunchTeam.tsx`), the set-up panel (`LaunchSetup.tsx`), the footer and its reasons, the two buttons, the Resume window, the draft, the frame (D5, D6, D12, D13, D14), by `mockup-new-session.html`. Check: `web/src/Launch.test.tsx`, `LaunchTeam.test.tsx`, `LaunchSetup.test.tsx`.
- [x] 3.4 The rail's Launch becomes New session. Check: `web/src/Shell.test.tsx`, `App.test.tsx`.

## 4. Browser tests and documents

- [x] 4.1 UI e2e: scenario 1 end to end, a recent project repository, a plain folder set up and started, the phone's footer in view, the focus after a refusal and after Esc; the existing tests moved off the switch, Advanced, First message, Launch and Resume it. Check: `uv run pytest -m ui tests/ui/test_launch.py tests/ui/test_launch_project.py tests/ui/test_launch_model.py tests/ui/test_stopped_session.py`.
- [x] 4.2 Screenshots of A(a), A(b), A(d), A(g), A(h) at 1440 and 390 as run artifacts. Check: against `mockup-new-session.html`.
- [x] 4.3 `docs/design/ui.md` (Launch and session control), `docs/design/modules.md`, CHANGELOG.md under `## 0.45.0 (unreleased)`. Check: read against the specs.
- [x] 4.4 The regression run of the plan's "Tests per requirement". Check: all green.
