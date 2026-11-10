## Context

`web/src/Launch.tsx` computes `stopped`, a resumable session of the place's default name
(`name_state: "stopped_here"`; in a project, only one of that project). It drives three things:
the line `Session <name> stopped here <when>` under Where (`FolderNotes` in `LaunchWhere.tsx`, and
the project's notes), the start button's label `Start new session <free name>` / `Start new
session in <title>`, and the footer's second button `Resume <name>` with `resumeStopped`,
`changedFrom(stopped, true)`, the `two` layout of `.launch-buttons` and Enter's `act()`.

## Decisions

- **D1. Only the button goes; `stopped` stays.** The line under Where and the start button's
  label keep using `stopped`: they tell the human why the name is `webapp-2`. `resumeStopped`, the
  second button, the `two` class (and its CSS in `web/src/styles.css`, when nothing else uses it),
  the `onlyTouched` parameter of `changedFrom` and Enter's branch to `resumeStopped` are removed;
  `act()` becomes `start()`. The busy kind `resume` stays for the Resume window.
- **D2. The start button is always the primary.** With one button, `startButton(true)` in every
  case; the primary no longer follows Task.
- **D3. Tests at the lowest layer.** The buttons and Enter are the window's logic: vitest, the
  tests of `Resume <name>` beside a new start replaced by one that the window shows no Resume and
  Enter starts `webapp-2`. In a browser: the existing UI e2e of a new session beside a stopped one
  (`test_scenario_1_a_new_session_beside_a_stopped_one_with_a_task`) and the project's taken name
  are updated; the task's scenario 1 runs end to end with the fake providers `fake-claude`
  (`CloudClaude`) and `fake-codex` (`CloudCodex`), neither logged in: New session shows no Resume,
  and the Resume window of the stopped session resumes it on `fake-claude` and `CloudClaude`. No
  core change, so no unit or integration test of the server.
- **D4. A patch.** A fix of 0.45.0's window for 0.45.1; no API, MCP, CLI or schema change
  (`web/openapi.json` unchanged).
