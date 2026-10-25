# LAD-144 by-hand-way-back: review report

Pull request #169 `hotfix/lad-144-by-hand-way-back` → `main`. Scale: hotfix, reviewed for
precision; the diff touches only `Plan.by_hand` and the new `update.uv_bin_dir`, which
print commands and act on no data, so the review did not widen to breadth, but read the
`restore` path and `_way_back` apart. Head reviewed last: `151b0b0c` (= the remote head).
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
unchanged, so no live tests are needed before the merge.

## Rounds

- **Round 1** (local, precision and the spec, `origin/main...1af9e6fd`): F1-F4.
- **Round 2** (local, precision, the delta `1af9e6fd..151b0b0c`: 952c7e0f, 2165912d,
  cc3bc031, 151b0b0c): no new findings. Checked: `uv_bin_dir` gives None for a receipt it
  cannot read and skips an entry that is not a table; `PIPX_HOME` only for
  `venvs/<name>`; the spec's three requirements match the tests; the BACKLOG entries in a
  commit of their own.
- **External 1** (Claude Code GitHub Action; request comment 6401303869 at
  18:12:43Z, "Claude finished" at 18:13:31Z): no blocking findings; E1, E2. It read the
  risky files (`src/lado/self_update.py`, `src/lado/update.py`, the three test files),
  not the documents, CHANGELOG, BACKLOG or openspec files.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less. F1 was in code changed by the developer's cleanup before
review (the restore line built with `shlex.join`).

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the restore line's paths are not absolute for a relative `LADO_HOME`, though the spec asks for absolute ones | confirmed | minor | fixed in 2165912d (`.absolute()`); test `test_the_commands_by_hand_of_an_older_schema_put_the_copy_back[True]`, red before |
| F2 | 1 | local | no test holds the order pip first (D1) | confirmed | minor | fixed in 2165912d: the case `pip_beside_a_receipt`, shown to fail with the order swapped |
| F3 | 1 | local | pipx with `--suffix`: the line installs the venv `lado` without the suffix | confirmed | minor | declined: the receipt's options are out of the design's scope; the human reads the line before running it |
| F4 | 1 | local | uncommitted edits in the worktree: the head under review was not the last | confirmed | important (process) | fixed in 952c7e0f and 2165912d; with them `PIPX_HOME` and `UV_TOOL_BIN_DIR` from the receipt (decision #1589), with tests |
| E1 | ext 1 | external | with an unknown installer on the way back, pasting the whole list restores the old copy and starts the current LADO, which migrates it forward again: records after the migration are lost and the version does not change | confirmed | minor | declined: needs two rare conditions together, and the plan warns of the loss just above the list; the human decides at the merge gate |
| E2 | ext 1 | external | `UV_TOOL_DIR = where.parent` for the layout `<tool_dir>/<name>` | refuted | — | the reviewer itself concluded no change is needed: uv names the tool's folder by the package |

## Checked against the spec

Every requirement and scenario of `update-by-hand` is covered by code and a unit test;
every task of `tasks.md` is checked; the design's decisions hold, nothing beyond the
scope. The pull request's description matches the diff (the uv/pipx folders, absolute
paths, the BACKLOG entries).

## Checks

On 151b0b0c: `make lint` 0; `tests/test_update.py tests/test_self_update.py
tests/test_server_system.py` 170 passed; `openspec validate by-hand-way-back --strict`
valid, `openspec validate --specs --strict` 48 passed; CI 23/23 pass, `ci-ok` pass. The
developer's `make test` 4289 passed, 2 skipped.

## Found on the way

In BACKLOG.md (cc3bc031): P2, the automatic path (`update._uv_tool`, `_pipx`) passes no
`UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`/`PIPX_HOME` to the installer; P3, with a relative
`LADO_HOME` the reads of `lado.db` fail on `as_uri()`.

## Not checked

The commands by hand are never run as a shell: the tests compare their text. uv 0.13.1
and pipx 1.18.4 with these variables were checked by hand by the developer, not
reproduced in review. The new tests' red on the old code was not reproduced in review
(the build report says it).
