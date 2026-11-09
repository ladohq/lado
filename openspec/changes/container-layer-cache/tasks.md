## 1. The image

- [x] 1.1 `docker/Dockerfile`: the wheel's `COPY` and `uv tool install` after openspec, before
  `ENV`, with their comment (design D1); the header's text still true. Check: a test in
  `tests/test_docker.py` that the wheel's lines come after every CLI's and openspec's
  install; `make test`; `make docker` and `make test-container` locally when Docker runs
  (else say so in the build report).
- [ ] 1.2 `Makefile`: `docker` passes `$(DOCKER_BUILD_FLAGS)` (empty by default) to `docker
  build` (D3). Check: `make -n docker` without and with the variable.

## 2. CI

- [ ] 2.1 `.github/workflows/ci.yml`, job `container`: the builder (`docker/setup-buildx-action`)
  and the runtime's variables (`crazy-max/ghaction-github-runtime`), both pinned by SHA,
  before `Image`; `Image` builds with `--builder <name> --load` and the flags per event of
  D3 in scope `container-${{ matrix.arch }}`; its comment says so. If LAD-248's shards are
  on `main` by then, only shard 1 writes (D4). Check: `tests/test_ci_workflow.py` per D5,
  one test per scenario of the delta; `make test`.
- [ ] 2.2 `tests/test_ci_workflow.py`: `release.yml` holds no `cache-from`, `cache-to` or
  `type=gha`. Check: `make test`.

## 3. Docs and the measurement

- [ ] 3.1 `docs/testing.md`, CI paragraph: the container cells' cache (who reads, who writes,
  the daily build from nothing, the release without one). Check: read against ci.yml.
- [ ] 3.2 The layering, locally (AC-1): `make docker DOCKER_BUILD_FLAGS="--builder <b> --load
  --cache-to type=local,dest=<dir> "` once, then a change of the version and again with
  `--cache-from type=local,src=<dir>`; quote the `CACHED` lines and both times in the
  build report. When Docker does not run locally, say so; the pull request's own CI then
  shows the build with the new flags (no cache to read yet) and its time.
- [ ] 3.3 After the merge (not blocking the pull request): the step `Image` times of the
  first pull request runs that read `main`'s cache, against 76 s / 66 s (AC-1).
