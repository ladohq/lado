# LAD-97 server-token-never-empty: review report

Pull request #96 `hotfix/lad-97-empty-server-token` → `main`. Scale: hotfix; the local
pass was widened from precision to broad, as the change touches `auth.py`, the only check
of who may call the UI server (a security boundary). Head reviewed last: `82e226e` (= the
remote head), after a return from merge for a conflict with `main`. `providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and
`tests/live/` did not change, so live tests are not needed before the merge.

## Rounds

- **Round 1, local** (broad over `origin/main..54d9def`; lenses: spec, tests, silent
  failures, comments, types and invariants, general, architecture against AGENTS.md):
  F1, F2, F3 (minor).
- **Round 1, external** (Claude Code GitHub Action, request 23:04:31Z, "Claude finished"
  23:05:34Z): nothing blocking; agreed with declining F1–F3; one minor remark, F4. The
  external reviewer is of the same model family, so its "nothing blocking" weighs less.

- **Visit 2, local** (precision over `54d9def..82e226e`: the archive `1113bcf` and the
  merge of `origin/main` `3a8126c`, PR #94 LAD-95): the task's diff of `src/` and `tests/`
  against main is byte for byte the one of round 1; `git show --remerge-diff` shows the
  only conflict in CHANGELOG.md, resolved with both lines under the one
  `## 0.41.0 (unreleased)` and no line of main lost; the archive moved the change
  unchanged and the living spec matches the delta. No new findings. No external round:
  the cap was used in round 1 and no code changed.

External rounds used: 1 of 1.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | `_write` does not `fsync` before `os.replace`: after a power loss some file systems may leave the renamed file empty | confirmed | minor | declined: an empty file now gets a new token (`auth.py:40-42`), so no hole opens |
| F2 | 1 | local | `os.write`'s count is not checked (a short write) | confirmed | minor | declined: 44 bytes to a regular file; at worst a cut token gives 401, the server never opens |
| F3 | 1 | local | a kill between `mkstemp` and `os.replace` leaves `.server-token.*` (0600) in `LADO_HOME` | confirmed | minor | declined: the spec's "no temporary file" is about a failed write (OSError), which the test covers; owner-only, cosmetic |
| F4 | ext 1 | external | `path.read_text()` fails with a traceback on an unreadable file (`UnicodeDecodeError`, `IsADirectoryError`) | confirmed | minor (older than the change) | declined; under "Found on the way" |

Metrics: 2 local rounds (broad, then precision over the merge), 1 external, 0 substitutes. Local confirmed 3 (minor), refuted 0;
external confirmed 1 (minor), refuted 0. Findings in code changed by the developer's
cleanup: 0.

## Against the spec and design

- AC-1 (empty or whitespace-only file → new token): `test_an_empty_token_file_gets_a_new_token`.
- AC-2 (a token is kept): the existing `test_the_token_is_kept_in_lado_home_for_the_owner_only`;
  that the file is not rewritten is seen in the code only.
- AC-3 (atomic write, error with path and reason): the ENOSPC test, both with and without
  an earlier file; red on main.
- AC-4, AC-5 (empty Bearer, `?token=`, cookie → 401; `Guard("")` → `ValueError`):
  `test_the_server_refuses_an_empty_token`; only the `Guard("")` case is red on main.
- Deviation: `app.contract()` builds the app on `"unused"` instead of `""`, or making the
  OpenAPI schema would raise; the schema is unchanged.

## Checks

- `make lint` exit 0; `uv run pytest -n0 tests/test_server.py` 89 passed;
  `openspec validate --specs --strict` 33 passed; the change valid. The developer reports
  `make test` 3415 passed.
- CI on `54d9def`: 23/23 green with `ci-ok` (lint, unit, integration, ui, container,
  smoke).
- On `82e226e`: `openspec validate --specs --strict` 35 passed; CI 23/23 green with
  `ci-ok`. `make lint` and `make test` not rerun locally: the task's code did not change.

## Found on the way

- `auth.token()` fails with a traceback when the token file is not readable as text or is
  a directory (`auth.py:40`, on main too). Proposed for BACKLOG, P3, size XS: count such a
  file as missing, or raise `LadoError` with the path.

## Residual risk (not checked)

- The `bool(given)` guard in `Guard._valid` has no test that would fail without it: with
  a non-empty own token it cannot be reached.
- The manual check of tasks 3.2 was not repeated by the reviewer; it is in the pull
  request's description.
- Full `make test` and the integration tests were not run locally; CI ran them green.
