# LAD-255 window-server-model-without-login: review report

Pull request #269 `hotfix/lad-255-server-model-without-login` → `main`. Scale: hotfix, depth
precision widened to breadth. Head reviewed: `25c2797a`. The New session and Resume windows offer
Claude Code and Codex without their login for the saved models of their server, take the one server
model by themselves in a new session, and refuse a built-in model in the Model field before the
start with the start's own login check. Delta: changes to `provider-logins`.

## Rounds

1. Local, breadth (widened from precision: the diff changes the meaning of `login_missing` in the
   API, the login check of `check_session_model` and the window's model pick). Lenses: spec, tests,
   silent failures, comments, types, general, architecture by AGENTS.md. Every requirement and
   scenario of the delta has its code and test; every task of `tasks.md` is checked. Found F1.
2. External 1, Claude Code GitHub Action: F2, refuted; its analysis gave F3. It read `launch.py`,
   `model_entries.py`, `models.py`, `Launch.tsx`, `LaunchModel.tsx`, `LaunchTeam.tsx` and
   `ModelPicker.tsx`, not the tests, docs or openspec.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F2 | — | external: `check_session_model` checks the login only for a start with no server, so a CLI that needs a login but does not take a server's whole process would get `ok` and a refused start | refuted: only Claude Code and Codex need a login, and both take a server's whole process; `runtime.check_login` cannot refuse where the condition skips it |
| F3 | minor | `if start.server is None` in `model_entries.py` repeats part of `runtime.check_login`'s rule and may drift for a future provider | declined: not reachable today; a hotfix for the RC |
| F1 | minor | switching Agent from a CLI with a picked model to a CLI without its login and one server model leaves the note "back to `<CLI>`'s default" although the field took the server model (`web/src/LaunchModel.tsx`) | declined: the note's text only; the field and the start are right |

## Found on the way

None.

## Checks

On `25c2797a`:
- `make lint` green; `tests/test_server_launch.py` and `tests/test_server_session.py` 159 passed;
  UI e2e `tests/ui/test_launch_model.py` and `tests/ui/test_launch.py` 50 passed;
  `openspec validate window-server-model-without-login --strict` valid,
  `openspec validate --specs --strict` 82 passed.
- CI: `ci-ok` SUCCESS (run 42672657748, attempt 2; the earlier red attempt was a GitHub Actions
  incident).

## Not checked

- Live tests with the real Claude Code and Codex on a server model through the UI: not run;
  `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/` did not
  change.
- The window's model check now reads `claude auth status` (about 0.1 s) for each built-in model,
  also for a logged-in CLI.
- "your server's models only" counts any saved model of the CLI, also on an unreachable server;
  the model's own check then refuses with its reason.
