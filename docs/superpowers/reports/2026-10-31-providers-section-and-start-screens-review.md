# LAD-163 providers-section-and-start-screens: review report

Pull request #186 `feature/lad-163-providers-section-and-start-screens` → `main`. Scale:
full, review in breadth first. Head reviewed last: `6632fd11` (= the remote head). The
Providers and environment section shows only fixable problems, keeps the last check and
refreshes it in the background (↻); Claude's Bypass Permissions and New MCP server screens
are dismissed through the agent's own `--settings`; an agent with no hook 30 s after its
CLI starts waits with the reason "Waiting for an answer in its terminal"; LADO's writes to
Claude's config go to loop.log only; a manual resume is refused without the login,
the automatic one still waits for it. `providers/claude.py`, `hooks.py`, `runtime.py`
and `loop.py` changed: live tests may be wanted.

## Rounds

- **Round 1** (`837d938f...b5d3632a`): a local pass in breadth. F1 blocker, F2 and F3
  important.
- **Round 2** (`b5d3632a..122297cb`): a local precision pass over the fixes; external 1
  of 2 (Claude Code GitHub Action): no blockers, E1-E4. The external reviewer did not
  read `web/src/*`, the tests or the docs.
- **Round 3** (`122297cb..6632fd11`), after the first archive failed strict validation
  (three requirements of `provider-logins` over 500 characters, the new capability
  `agent-start-screens` without a Purpose): only the two spec files changed, the
  requirements shortened with their details moved into scenarios, a `## Purpose` added;
  their meaning checked line by line. External 2 of 2: no blockers, E5.

External rounds used: 2 of 2. The external reviewer is of the same model family, so its
"no findings" weighs less.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | blocker | `ruff format --check` red on `tests/test_update.py`; CI unit red | fixed in `8b9a068a` |
| F2 | important | `lado update` to a LADO before 0.44 resumed sessions with `--wait-for-login`, which the old argparse refuses: every session `failed` | fixed in `3ae75a9e` (`WAIT_FOR_LOGIN_SINCE`), test in `tests/test_self_update.py` |
| F3 | important | A failed poll or POST during a check left ↻ spinning and dead | fixed in `122297cb`, 2 vitest tests |
| E1 | minor | If `Thread.start()` raises in `provider_check.start()`, `_thread` stays set and no check runs until the server restarts | declined: only on exhausted OS threads; the human decides |
| E5 | minor | No scenario of its own for a manual resume of a project session whose login is in the project's secrets | declined: the requirement's text and the code (`agent_layers(sess.project)`) cover it |
| E2-E4 | — | external: RESUME refused before "already running", the 30 s false alarm undocumented, two transactions for `seen` | refuted (`runtime.py` order, `docs/design/agents.md`, not a defect) |

Found on the way (outside the task): none.

## Checks

- Local on `122297cb`: `make lint` green; `make test` 4510 passed; integration of the
  changed files, vitest and `openspec validate providers-section-and-start-screens
  --strict` green. The code did not change after `122297cb`.
- On `6632fd11`: the archive, then `openspec validate --specs --strict` 52 passed.
- CI on `6632fd11`: all 23 jobs green, `ci-ok` included (smoke on Linux and macOS).

## Not verified

- Live tests (`make test-live`) were not run; `providers/claude.py`, `hooks.py`,
  `runtime.py` and `loop.py` changed.
- The UI and the tests were reviewed only locally.
- The 30 s threshold may briefly show "Waiting for an answer in its terminal" on a slow
  machine; it clears by itself (documented).
- An update 0.43 → 0.44 run by the old version's code does not resume a session without
  its login once: the accepted risk of D9.
