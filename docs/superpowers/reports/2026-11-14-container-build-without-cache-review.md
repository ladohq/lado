# LAD-279 container-build-without-cache: review report

Pull request #299 `fix/lad-279-container-build-without-cache` → `main`. Scale: tweak, depth
precision. Head reviewed: `69089be4`. CI's container cells build LADO's image with a plain
`make docker`, without the BuildKit builder and GitHub's Actions layer cache of LAD-249: the
cache saved 14-16 s of a cell off the critical path and took 7.0 GB of the 10 GB Actions cache
(LAD-252's measurement). `DOCKER_BUILD_FLAGS` goes from the Makefile; the wheel stays the
image's last layer.

## Rounds

1. Local, precision (`85dafa79..69089be4`), with the change checked against its delta, and
   external 1, Claude Code GitHub Action (no blockers; agreed with F1; raised F2). The external
   reviewer read every risky file of the diff (`ci.yml`, Makefile, Dockerfile, tests, docs,
   BACKLOG), not the openspec files, which the local round checked.

External rounds used: 1 of 1. Stand-ins: 0.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | the docstring of `wheel_too_early` (`tests/test_docker.py`) keeps a short line in mid-sentence after rewrapping | declined: style only, the loop converged |
| F2 | — | external: the living spec `continuous-integration` still describes the cache | refuted: the spec changes at archive; the trial archive was green with the new requirement |

## Spec check

- ADDED "The container cells build the image without a layer cache": `ci.yml`'s `Image` is
  `make docker` then `docker history lado:local`; `test_the_container_job_uses_no_layer_cache`
  fails on `main`'s `ci.yml` (checked by the reviewer).
- MODIFIED "The run's code changes only the image's last layers": the wheel is still last;
  its test green.
- REMOVED the cache's requirement: no `type=gha`, `DOCKER_BUILD_FLAGS`, `setup-buildx` or
  `ghaction-github-runtime` left but in the tests of their absence, the archive and the
  research.
- AC-2: no `CACHED` layer and no cache import in the log of `Image` (run 43616703972); 57-76 s
  per cell.

## Found on the way

None new. The leak of `LADO_LAUNCH_VARS` into the unit tests is in BACKLOG.md (P2, `ddb19780`).

## Checks

On `69089be4`:
- `make lint`: clean.
- `make test`: 6117 passed, 7 skipped, 1 failed:
  `tests/test_temp_dirs.py::test_the_users_tmpdir_is_the_parent_and_not_warned_of[shell]`,
  from the agent's environment (`LADO_LAUNCH_VARS`); it passes with the variable unset and is
  red on `main` too.
- `openspec validate container-build-without-cache --strict` valid; specs 83/83; trial archive
  83/83.
- CI run 43617443109: success, `ci-ok` success, the four container cells green.

Not run locally: integration, UI and smoke tests (CI ran them). No change to `providers/`,
`hooks.py`, `mcp_server.py`, `runtime.py`, `agent_env.py` or `tests/live/`.

## Residual risk

AC-6 (Actions cache under 10 GB with no `container-*` entry, the wait's median not longer than
LAD-252's 8.2 / 6.7 min) can be checked only a week after the merge; task 4.3 stays open.
