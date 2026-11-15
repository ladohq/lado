Task: LAD-279

## Why

Since LAD-249 (`container-layer-cache`) each CI cell `container (<arch>)` builds LADO's
image through a BuildKit builder of its own with GitHub's Actions cache (`type=gha`, scope
`container-<arch>`). The measurement of LAD-252 (`docs/research/ci-speedup-check.md`,
CI runs of 2026-11-09 to 2026-11-13) shows it does not pay:

- it saves 14 s (amd64) and 16 s (arm64) of the step `Image` of a pull request at the
  median (77 → 63 s, 66 → 50 s) and nothing at p90 on amd64 (92 s against 88): a cached
  build still downloads the cached layers (~1 GB) and loads the image into Docker;
- a container cell ends a green pull request's run in 1 of 65 runs (1.5 %), so the wait
  for CI gains about nothing;
- its 345 entries take 7.0 GB of the repository's Actions cache, which stands at 11.06 GB
  of its 10 GB limit: GitHub already evicts entries, and the browser and uv caches that do
  pay share that space;
- the daily build from nothing that writes it takes 96-243 s instead of 61-91 s.

The root cause: the cache only skips building layers that are cheap to build compared with
moving them (download from the cache, `--load` into the runner's Docker), and the cell is
not on the critical path, so its gain is not the wait's.

## Options

1. **Remove the cache** (chosen): the step `Image` is a plain `make docker` on the
   runner's own Docker, as before LAD-249. Long-term cost: none to keep; 14-16 s more per
   container cell, off the critical path; ~7 GB of the cache back for the caches that pay.
2. **Keep it, smaller**: one architecture only, or only the apt layer (`mode=min` already
   keeps only the final image's layers). Still a second builder, a third-party action
   for the runtime's token, per-event rules and their tests to maintain, for a few seconds
   that do not move the wait.
3. **A registry cache in GHCR** instead of GitHub's: frees the Actions cache, but the job
   would log in and hold `packages: write`, against the rule that the container job logs
   in to no registry and publishes nothing; same small gain.

## What Changes

- `.github/workflows/ci.yml`, job `container`: the steps `docker/setup-buildx-action` and
  `crazy-max/ghaction-github-runtime` go; the step `Image` runs `make docker` and
  `docker history lado:local`, with no builder, no cache flags and no per-event rule; its
  comment says why there is no cache (the measurement of LAD-252).
- `Makefile`: the variable `DOCKER_BUILD_FLAGS`, used only by that step, goes; `make
  docker` builds as it did before LAD-249.
- `docker/Dockerfile`: the wheel stays the image's last layer (a developer's local Docker
  reuses the layers before it); its comment no longer names CI's cache.
- `tests/test_ci_workflow.py`: the cache's tests go; a test that the job `container` uses no
  buildx, no `type=gha`, no `cache-from`/`cache-to`, and that `Image` is `make docker` then
  `docker history lado:local`. `tests/test_docker.py`: docstrings no longer name CI's
  cache.
- `docs/testing.md` (CI paragraph): the cells build the image from nothing in every run.
- The living spec `continuous-integration`: the cache's requirement is removed, a rule that
  the cells build without a layer cache is added, the wheel-last rule loses its reason in
  CI's cache.

## Acceptance criteria

- AC-1: The job `container` in `ci.yml` has no `setup-buildx-action`, no
  `ghaction-github-runtime`, and no `type=gha`, `cache-from`, `cache-to` or `--builder`;
  its step `Image` runs exactly `make docker` and then `docker history lado:local`; a unit
  test fails when any of them comes back.
- AC-2: The pull request's container cells are green on both architectures, and their log
  of `Image` shows a build from nothing (no `CACHED` layer, no cache import).
- AC-3: The Dockerfile still copies and installs the wheel after every agent CLI and
  openspec (the unit test of `tests/test_docker.py` stays green).
- AC-4: `make docker` takes no `DOCKER_BUILD_FLAGS` and builds `lado:local` as before;
  `release.yml` is unchanged and still builds without any cache.
- AC-5: `ci-ok`, the container job's every-run rule, its shards and its "nothing pushed, no
  registry login" rule are unchanged.
- AC-6 (after the merge, not blocking the pull request): a week after the merge the
  repository's Actions cache is under 10 GB with no `container-*` entry, and the median
  wait of a green pull request's run is not longer than the 8.2 min / 6.7 min (with / without
  the smoke) of LAD-252's measurement; checked with `docs/research/ci-speedup-check/measure.py`
  (`--caches`, and the wait over the week after the merge).

## Scope

- `.github/workflows/ci.yml` (job `container`), `Makefile` (`docker`),
  `docker/Dockerfile` (a comment), `tests/test_ci_workflow.py`, `tests/test_docker.py`
  (docstrings), `docs/testing.md`, the living spec `continuous-integration`.

## Out of scope

- Deleting the `container-*` entries from the Actions cache by hand (`gh cache delete`):
  GitHub evicts entries not accessed for 7 days, and the cache is already over its limit
  and evicting, so they leave within a week of the merge without a write to the
  repository's settings by an agent.
- Moving the wheel's layer back up in the Dockerfile: a developer's `make docker` and
  `make test-container` reuse the earlier layers in their local Docker, and the order
  costs nothing.
- `release.yml`: it never read a cache.
- The macOS smoke (LAD-280) and the flaky UI test (LAD-281): their own tasks. LAD-280 may
  also edit `ci.yml`; whichever merges second resolves the conflict.
- A CHANGELOG line and a version bump: nothing LADO's users see changes (CI only).

## Impact

- CI only; no code of LADO, no schema, no MCP tool or CLI change: neither a minor nor a
  patch bump of its own, no CHANGELOG line.
- The container cells' step `Image` takes ~15 s longer on a pull request; the daily run's
  build is shorter (nothing to export).
- Possible conflict with LAD-280 in `.github/workflows/ci.yml` (other jobs).
