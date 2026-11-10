# LAD-262 doctor-login-line-server-models: review report

Pull request #271 `fix/lad-262-doctor-login-text` → `main`. Scale: tweak, depth precision.
Head reviewed: `2efb4252`. `lado doctor`'s login line for Claude Code or Codex without its login
no longer says that new sessions and workers are refused: it says that only its agents on the
model server's models start, and where to log in for its own models. Delta: changes to
`provider-logins`.

## Rounds

1. Local, precision, over the whole pull request `f43d6be4..2efb4252`: the diff, the delta,
   `tasks.md`. Both former scenarios of the modified requirement are kept, the Codex scenario is
   added, and each has its unit test. The new line is true by the code: `runtime.check_login`
   skips the login for a start on a server that takes the CLI's whole process, which Claude Code
   and Codex both do. The tests quote the line verbatim and were seen red. Found F1.
2. External 1, Claude Code GitHub Action: E1 and E2. It followed `needs_login` →
   `check_login` → `_held_for_login` and confirmed the line; it did not read the openspec files,
   which the local pass and the trial archive covered.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| E1 | minor | external: with no model server saved, the line still speaks of "your model server's models" | declined: the human chose this short line; naming whether a server is saved would be a second source of truth (option C), and the line stays true without one: nothing starts |
| F1 | — | `grep "are refused, a resumed agent"` finds `docs/superpowers/plans/2026-10-30-refuse-start-without-login.md` | refuted: LAD-161's plan, a record of past work |
| E2 | — | external: CHANGELOG says "their agents", doctor "its agents" | refuted: plural subject in CHANGELOG, one CLI in doctor |

## Found on the way

- P3: `openspec/specs/provider-logins/spec.md` (scenarios "Log in first" and "Resume without a
  login") still say `Settings → Agent CLIs and environment`; the code and docs/cli.md say
  `Settings → Agent CLIs`. Older than this change.

## Checks

On `2efb4252`:
- `make lint` green; `tests/test_doctor.py` 152 passed; the developer's `make test` 6083 passed,
  7 skipped; `openspec validate doctor-login-line-server-models --strict` valid; trial archive
  and `openspec validate --specs --strict` 82 passed.
- CI: 27/27 pass, `ci-ok` included, no reruns.

## Not checked

- Live tests: not run and not needed; `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`,
  `agent_env.py` and `tests/live/` did not change.
