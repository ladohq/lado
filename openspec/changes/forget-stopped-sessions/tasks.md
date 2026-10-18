Plan: `docs/superpowers/plans/2026-10-18-forget-stopped-sessions.md` (each task's tests and steps).
Design doc: `docs/superpowers/specs/2026-10-18-forget-stopped-sessions-design.md`.

## 1. The band's action (D1)

- [x] 1.1 `GroupHead`'s optional `action`, `.group-action`; vitest. Check: `cd web && npx
  vitest run src/GroupHead.test.tsx`.

## 2. The window (D2–D5, D7)

- [x] 2.1 `ForgetMany.tsx`: ticks, All, count, open runs' switch, worktrees, the
  sequential forget, close or Close, `/sessions`; vitest. Check: `cd web && npx vitest run
  src/ForgetMany.test.tsx`.

## 3. The Stopped band opens it (D1, D3)

- [x] 3.1 `Sessions.tsx`: the bin on the Stopped band opens the window with the group's
  sessions as shown. Check: `make web`.

## 4. Stop and forget (D6)

- [x] 4.1 `StopPopover`'s `Stop and forget`; vitest. Check: `cd web && npx vitest run
  src/SessionControl.test.tsx`, `make web`. (The vitest went to `src/Launch.test.tsx`
  beside the existing Stop and Forget tests, whose fake server it shares.)

## 5. UI e2e

- [x] 5.1 `test_forget_stopped_sessions`, `test_forget_stopped_sessions_open_runs`,
  `test_stop_and_forget` in `tests/ui/test_launch.py`; `test_phone_forget_stopped` in
  `tests/ui/test_phone.py`. Check: `uv run pytest -m ui tests/ui/test_launch.py
  tests/ui/test_phone.py`.

## 6. Docs

- [x] 6.1 `docs/design/ui.md` (Launch and session control, the Sessions band),
  CHANGELOG.md under `## 0.41.0 (unreleased)`. Check: read through.

## 7. Regression

- [x] 7.1 `make lint`, `make test`, `make web`, `uv run pytest -m ui
  tests/ui/test_launch.py tests/ui/test_session_list.py tests/ui/test_phone.py
  tests/ui/test_layout.py`, `openspec validate forget-stopped-sessions --strict`.
