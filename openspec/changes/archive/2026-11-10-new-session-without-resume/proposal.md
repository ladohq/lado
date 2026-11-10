Task: LAD-261

## Why

Found in the manual check of 0.45.0rc2 (findings 1 and 2). In the New session window, `Resume
<name>` beside a new start resumes the stopped session with the model the window took from the
place's last launch, not with the session's own:

1. A Claude Code session `nologin` on `CloudClaude` is stopped; the folder's last launch is a Codex
   session on `CloudCodex`. The window's Team holds Codex CLI and `CloudCodex`; `Resume nologin`
   posts `model: "CloudCodex"` without a provider, the core refuses it (409 `"CloudCodex" is a
   model of Codex CLI, not of Claude Code`), and the session does not start.
2. A Claude Code session `solo` on `CloudClaude` is stopped, Claude Code is not logged in and has
   two saved server models. The window's Model field is refused (`… pick one.`) and `Resume solo`
   stays off until the human picks a model, though the session has its own.

Cause: the window has one Team for two buttons. Team is filled for a new session (from the
place's last launch and the suggestion), so `Resume <name>` (added by the change
new-session-window in 0.45.0) sends only the Team fields the human changed (`changedFrom` with
`onlyTouched` in `web/src/Launch.tsx`); the Model field, added in the same release, was left out
of that rule and is sent always, and the button is off by the readiness of the new session's
fields (`teamReady`), not of the resume.

Options weighed (the human's answers #5403, #5411):

- A: the Model field counts as the other Team fields do. Fixes both findings, keeps one Team that
  means two things for two buttons: the next field added to Team can repeat the defect.
- C: `Resume <name>` resumes the session as it was, with the task; Team is for the new session
  only. Clearer, but the window still holds two actions on two different teams.
- E (taken): New session is for a new session only: `Resume <name>` leaves the window. The human:
  the button confuses; a human who wants the stopped session back goes to it and resumes it there
  (its page, the session list), where the Resume window opens on the session's own team. Long-term
  cost: none; less code, one meaning for Team.

## What Changes

- The New session window has one start button. With a stopped session of the place's default
  name, it names the new session by the free name (`webapp-2`) as before, keeps the line
  `Session <name> stopped here <when>` under Where, which says why, and its button reads
  `Start new session <free name>` (in a project `Start new session in <title>`), the primary.
- Enter in a field of the window starts the new session, also beside a stopped session.
- The Resume window (a stopped session's Resume session) is unchanged.
- A patch (0.45.1): a fix, no API, CLI or schema change.

## Scope

- `web/src/Launch.tsx` (the second button, `resumeStopped`, `changedFrom`'s `onlyTouched`, `act`).
- Tests: vitest (`web/src/Launch.test.tsx`), UI e2e (`tests/ui/test_launch.py`,
  `tests/ui/test_launch_project.py`, `tests/ui/test_launch_model.py`).
- `docs/design/ui.md` (Launch and session control, "The name and Resume beside a new start").
- CHANGELOG.md under `## 0.45.1 (unreleased)`.

## Out of scope

- The Resume window and the ways to it (the session's page, the session list, `lado resume`):
  they open on the session's own team and have neither defect.
- A link or button to the stopped session in the line under Where: the human chose that the
  window does not lead back to it (#5411); the line only explains the free name.
- The core and the API: `POST /api/sessions/{name}/resume` is unchanged.
