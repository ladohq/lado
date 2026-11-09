# LAD-249 container-layer-cache: review report

Pull request #262 `fix/lad-249-docker-layer-cache` → `main`. Scale: tweak. Head reviewed:
`eb73fbbd`. The CI cells `container (<arch>)` build LADO's image with BuildKit's GitHub Actions
cache in the scope `container-<arch>`: a pull request reads it and writes none, a push to `main`
reads and writes it (shard 1 only), the schedule and a dispatch build from nothing and write it
anew; the wheel's layer moves to the end of `docker/Dockerfile`; `release.yml` keeps building
without a cache. Delta: three added requirements of `continuous-integration`.

## Rounds

1. Local, precision, `origin/main...eb73fbbd`, with the change's spec read whole: every
   requirement and scenario has its code and a unit test; mutations of the guards (a
   `pull_request` branch that writes, no shard check) turn the tests red. Found F1, F2, F7.
2. External 1, Claude Code GitHub Action: F3 and F4 minor, F5 refuted, F6 not checkable before
   the merge. It read every risky file of the diff, not the openspec documents.

External rounds used: 1 of 1. Stand-ins: 0.

## The human's decisions

- **Question #5037** at the design gate: the daily run builds from nothing and writes the cache
  anew; the goal is the step `Image` at least 25 s shorter per architecture, the numbers and the
  decision at review when it is not.
- **Question #5092** at review: on amd64 the warm `Image` gains ~19 s, not 25 s (the `--load` of
  the ~2 GB image costs ~44 s); keep the cache as it is.
- **Gate `merge_ok`, approved** with no comment.

## Findings

| ID | Level | Finding | Outcome |
|---|---|---|---|
| F1 | minor | The pull request's description says arm64 reached the 25 s goal in every warm run; one run gained 23 s (3 of 4 runs and the median did) | declined: the table of numbers is right |
| F2 | minor | `docs/testing.md` says a pull request rebuilds only one layer; the wheel's `COPY` and `RUN` are two | declined: the meaning holds |
| F3 | minor | external: `ghaction-github-runtime` leaves the cache token to every later step, the container tests with the pull request's code included | declined: a pull request's token writes only its own ref's scope, which `main` never reads |
| F4 | minor | external: the guard on `release.yml` checks the words `cache-from`, `cache-to`, `type=gha` only | declined: exactly what the spec requires; the release builds by a plain `docker buildx build` |
| F5 | — | external: `wheel_too_early` may trip over a comment naming `npm install` or the wheel | refuted: `lines()` drops comment lines |
| F6 | — | external: ~2 GB per architecture may push the npm, uv and browser caches out of the 10 GB limit | residual risk: watch the cache's use with task 3.3 (2.4 GB of 10 GB used before) |
| F7 | important | AC-1 on amd64 not met: warm `Image` median 57 s against ≤ 51 s | accepted by the human (#5092) |

## Checks

`make lint` green; `make test` 6070 passed, 7 skipped; `openspec validate container-layer-cache
--strict` and `openspec validate --specs --strict` (82 passed) green; CI 27/27. Not run locally:
`make docker` and `make test-container` (no Docker in the build), integration, UI, JS, smoke and
live tests; CI ran them, the four container cells green.

## Left after the merge

- Task 3.3: the step `Image` times of the first pull request runs that read `main`'s cache,
  against the medians 76 s (amd64) and 66 s (arm64).
- F6: the cache's share of the 10 GB limit.
