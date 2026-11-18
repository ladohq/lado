# LAD-297 git-server-doctor-hints: review report

Pull request #338 `feature/lad-297-git-server-doctor-hints` → `main`. Scale: full. Head
reviewed: `b1cd9f03`. `lado doctor` checks each saved git server, at once, with the check
of `lado git-server check`; a failed clone names the saved server and its Check or
Replace token, or offers to add a server for an unsaved host refused on access; the
Settings → Git servers page keeps one Replace token, an open ⓘ across a layout switch,
and busy author buttons.

## Rounds

1. Local, a full pass over `origin/main...b1cd9f03`: spec, tests, silent failures,
   comments, types, general, and the architecture against AGENTS.md; screenshots against
   `docs/design/ui.md` and the approved mockup. Found F1, F2.
   External 1, Claude Code GitHub Action, the whole pull request: E1–E4, no blocker or
   important.

External rounds used: 1 of 2. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the clone's reason names the host without its port, next to the server's full address | declined: wording; the full address stands in the same sentence |
| F2 | minor | `doctor.check_git_servers` does not catch an sqlite error when lado.db stays locked over 10 s | declined: the other doctor checks read lado.db the same way; the network case is covered |
| E1 | — | `except ValueError` would catch a `UnicodeDecodeError` of a broken token file | refuted: `read_token` decodes with `surrogateescape` and returns None for an unreadable file |
| E2 | minor | `?check=` is not read again inside an open page | declined: the note's links open a new tab; the query is read once per load by design |
| E3 | minor | two clicks in one tick may send Remove twice | declined: the button is disabled on the next render; a repeated Remove is harmless |
| E4 | minor | a comment that the scp form `git@host:path` parses as `ssh` | declined: `Address.parse` already says so, and a test covers both forms |

## Metrics

- Rounds: 1; local 1, external 1, stand-ins 0.
- Confirmed: local 2 (both minor), external 3 (all minor).
- Refuted: local 0, external 1 (E1).
- Findings in code changed by fixes: 0 (no fixing commits).

## Checks

- `make lint` clean; unit `test_doctor`, `test_clone`, `test_server_clones`,
  `test_git_servers` 553 passed; integration `test_git_server_access` 4 passed;
  `openspec validate git-server-doctor-hints --strict` valid.
- CI at `b1cd9f03`: 27 successful after `gh run rerun --failed` of `ui (3)`.
- Flake unrelated to the work: `tests/ui/test_launch.py::test_on_a_phone_every_field_and_button_of_the_window_is_a_44_px_target`
  (the kit chip's × on a phone), passed alone locally and on the rerun.
- Not run by the reviewer: `make test` as a whole (the developer's 5810 passed, CI
  green), `make web` (vitest 1978 passed for the developer, CI green), UI e2e (56 passed
  for the developer, CI green), `make test-live`.

## Residual risk

- The human's manual check (doctor against a real GitLab with a revoked token, a failed
  clone in the CLI and the UI, ⓘ on a real phone) was left to the human at the approval of the merge; the review did not see it.
- doctor may fail when lado.db stays locked over 10 s (F2).
- `make test-live` not run; no file of `providers/`, `hooks.py`, `mcp_server.py`,
  `runtime.py`, `agent_env.py` or `tests/live/` changed.
