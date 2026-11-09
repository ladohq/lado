Task: LAD-249

## Why

Each CI cell `container (<arch>)` builds LADO's image from nothing: `make docker` runs a
plain `docker build` on the runner's default builder, which keeps no layer between runs.
The step `Image` takes a median of 76 s on amd64 and 66 s on arm64 (CI runs of 2026-11-05
to 2026-11-09), of which the first apt layer is ~51 s, the browser libraries ~7 s and the
four agent CLIs with openspec ~30 s; none of them depends on the pull request's code.

A cache alone would not help much: `docker/Dockerfile` copies the run's wheel and installs
it before the agent CLIs, and the wheel changes on every pull request, so every layer after
it (the CLIs, ~1.75 GB) would still be rebuilt each time.

## What Changes

- `docker/Dockerfile`: the wheel's `COPY` and its `uv tool install` move to the end, after
  openspec and before `ENV`, so every heavy layer comes before the one the run changes. The
  image holds the same files.
- `make docker` takes extra flags for its build (`DOCKER_BUILD_FLAGS`, empty by default);
  without them it builds as before.
- The CI cells `container (<arch>)` build with BuildKit's GitHub Actions cache, one scope
  per architecture: a pull request reads the cache and writes none; a push to `main`
  reads and writes it; the daily schedule and a manual dispatch build from nothing and
  write it anew, so a broken outside source (Debian, gh's repository, npm) shows within a
  day and the cache is at most a day older than `main`'s last push.
- The release workflow keeps building the published image from nothing, reading no cache.
- `docs/testing.md` (CI) and the Dockerfile's comments say so.

## Acceptance criteria

- AC-1: The pull request proves the layering: two local builds with a local BuildKit cache
  (`--cache-to/--cache-from type=local`), the second after a change of LADO's version, show
  every layer before the wheel `CACHED` (the build report quotes the log). The time is
  checked after the merge, as a pull request reads only the cache `main` writes: in the
  first pull request runs after the merge's run on `main`, the step `Image` is at least
  25 s shorter than its median before the change (76 s amd64, 66 s arm64) on each
  architecture, and its log shows those layers `CACHED`.
- AC-2: The image a pull request tests holds that pull request's wheel: the container tests
  pass, and `lado --version` in the image is the run's version.
- AC-3: A pull request's run writes no cache entry (no `cache-to` in its build); the push to
  `main` and the scheduled run write the entry of their architecture.
- AC-4: The scheduled and the dispatched runs build without reading the cache.
- AC-5: `release.yml` builds without any cache; a unit test fails when `cache-from` or
  `type=gha` appears in it.
- AC-6: `make docker` without flags builds `lado:local` as before; `make test-container` is
  green.
- AC-7: `ci-ok` and its rule, the container job's every-run rule and its "nothing pushed,
  no registry login" rule are unchanged.

## Scope

- `docker/Dockerfile` (order of the wheel's layer, comments), `Makefile` (`docker`),
  `.github/workflows/ci.yml` (job `container`), `tests/test_ci_workflow.py`,
  `tests/test_docker.py`, `docs/testing.md`, the living spec `continuous-integration`.

## Out of scope

- A registry cache in GHCR: the job would have to log in and hold `packages: write`, against
  the rule that the container job logs in to no registry; the GitHub cache (2.4 GB of 10 GB
  used) has room for the two scopes.
- A cache in `release.yml`: the published image is built from nothing, so no cache written
  by CI can enter it.
- Shards of the container tests and other CI speed-ups: LAD-248.
- Switching the runners' Docker to the containerd image store (the default builder could
  then use the cache without a second builder): it changes the daemon the container tests
  run against.
- A CHANGELOG line and a version bump: nothing LADO's users see changes (CI and the order of
  layers only).

## Impact

- CI only, plus the order of the image's layers; no code of LADO, no schema, no CHANGELOG
  line, no version bump.
- Conflicts with LAD-248 in ci.yml's job `container` (its shards): whichever merges second
  resolves them; with shards, only shard 1 of each architecture writes the cache.
