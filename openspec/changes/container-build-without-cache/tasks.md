## 1. CI

- [ ] 1.1 `.github/workflows/ci.yml`, job `container`: remove the steps
  `docker/setup-buildx-action` and `crazy-max/ghaction-github-runtime`; the step `Image`
  becomes `make docker` then `docker history lado:local`, with no `env`; its comment says
  the image is built from nothing in every run and why there is no layer cache (LAD-252's
  measurement: 14-16 s saved, 7 GB of the 10 GB cache). Check: `make test`.
- [ ] 1.2 `tests/test_ci_workflow.py`: remove the cache's tests (`image_build`,
  `build_flags`, `cache_flags` and the tests over them, the builder-order test); add
  `test_the_container_job_uses_no_layer_cache` (no `setup-buildx-action`,
  `ghaction-github-runtime`, `type=gha`, `cache-from`, `cache-to`, `--builder` in the job's
  YAML) and assert `Image`'s `run` is exactly `make docker\ndocker history lado:local\n`;
  keep `test_the_release_builds_without_any_cache`; the module docstring says the
  container job builds without a cache. Check: `make test`; the new test fails when
  `ci.yml`'s job is put back as on `main` (try it in the working tree, then restore).

## 2. The image's build

- [ ] 2.1 `Makefile`: remove `DOCKER_BUILD_FLAGS` and its comment; `docker` runs `docker
  build -f docker/Dockerfile -t $(LADO_IMAGE) .`. Check: `make -n docker`.
- [ ] 2.2 `docker/Dockerfile`: the wheel's comment says the wheel is last so a build that
  reuses earlier layers (a local Docker) rebuilds only from there, without naming CI's
  cache. `tests/test_docker.py`: the docstrings of `wheel_too_early` and
  `test_the_wheel_is_copied_and_installed_after_the_clis_and_openspec` say the same.
  Check: `make test`.

## 3. Docs

- [ ] 3.1 `docs/testing.md`, CI paragraph: drop the cache's sentences (scope, builder,
  who reads and writes); say each cell builds the image from nothing in every run, the
  wheel stays the last layer, the release builds without any cache. Check: read against
  `ci.yml`; `grep -rn "type=gha\|DOCKER_BUILD_FLAGS\|setup-buildx\|ghaction-github-runtime"
  docs/testing.md Makefile docker .github tests` finds only the tests that assert their
  absence.

## 4. Checks

- [ ] 4.1 `make lint`, `make test`, `openspec validate container-build-without-cache
  --strict` and the trial archive (`.lado/sdlc.md`, Checks).
- [ ] 4.2 The pull request's CI: the four container cells green; quote in the build report
  the step `Image`'s time per architecture and that its log has no `CACHED` layer (AC-2).
- [ ] 4.3 After the merge (not blocking the pull request): a week later, `measure.py
  --caches` shows the Actions cache under 10 GB with no `container-*` entry, and the
  wait's median over that week is not longer than LAD-252's (AC-6). Open until then.
