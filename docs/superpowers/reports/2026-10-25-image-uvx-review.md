# LAD-148 image-uvx: review report

Pull request #171 `hotfix/lad-148-image-uvx` → `main`. Scale: hotfix, reviewed for
precision (the diff touches no business logic or user data). Head reviewed last:
`0455f214` (= the remote head), base `4f418717`. The image copies `/uvx` beside `/uv`
from the one pinned `uv` stage of `docker/Dockerfile`; a unit test of the Dockerfile, a
container test, docs/install.md and a CHANGELOG line under "Docker image".
`providers/`, `hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` and `tests/live/`
unchanged: no live tests needed. Schema migration: no.

## Rounds

- **Round 1** (`4f418717..0455f214`, the whole pull request): a local precision pass and
  a check against the `image-uvx` spec: its three scenarios are covered by the unit test
  and the container test, every task of `tasks.md` checked, nothing out of scope. The
  supervisor's points checked: in an agent's login shell mise's shims come after
  `/usr/local/bin` (`docker/profile.sh`, pinned by
  `test_profile_sets_what_env_sets_for_the_agents`), and the "Docker image" group of
  CHANGELOG.md follows "Fixed" as docs/release.md asks. **External 1** (Claude Code
  GitHub Action, request at 18:48:48Z, "Claude finished" at 18:49:39Z): read every
  changed code and docs file but the openspec texts; three minor findings.

External rounds used: 1 of 1. The external reviewer is of the same model family, so its
"nothing blocking" weighs less.

## Findings

| ID | Round | Source | Finding | Verdict | Severity | Decision |
|---|---|---|---|---|---|---|
| F1 | 1 | local | the container test looks only at `/opt/uv/tools`, while the scenario says nothing is installed under `/opt/uv` | confirmed | minor | declined: `/opt/uv` is root's and closed to `lado` (`test_the_agents_cannot_change_lados_python_and_make_environments`); the main check is the `uv ok` output |
| E1 | 1 | external 1 | `missing_uv_binaries` would count a flag (`--chown=…`) as a source | confirmed | minor | declined: no `COPY --from=uv` has flags; a flag would fail the test loudly |
| E2 | 1 | external 1 | the glob `cpython-3.13-*` in `--python` is fragile | confirmed | minor | declined: the same pattern is in the `uv tool install` test; the Dockerfile pins the layout |
| E3 | 1 | external 1 | uneven line wrap in the module docstring | confirmed | minor | declined: cosmetic |

## Checked against the spec

AC-1 to AC-3 hold; every scenario of the `container` delta is covered by a test; every
task of `tasks.md` checked; nothing out of scope. The pull request's description
matches the diff.

## Checks

`make lint` 0; `uv run pytest -n0 tests/test_docker.py` 94 passed, 1 skipped;
`make test` (by the developer) 4308 passed, 2 skipped; `openspec validate image-uvx
--strict` valid; `openspec validate --specs --strict` 49 passed; CI on `0455f214` 23 of
23 success, `ci-ok`, container amd64/arm64 included.

## Not checked

The container test was not run locally (no Docker in the agent's container), only in
CI. The PATH order against an existing mise shim of `uvx` is checked by the PATH's
construction, not by a run.
