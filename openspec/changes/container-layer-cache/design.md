## Context

`make docker` builds the web bundle, the wheel, then `docker build -f docker/Dockerfile -t
lado:local .` on the runner's default builder (driver `docker`). That builder cannot
export a cache to GitHub (`type=gha` needs BuildKit's `docker-container` driver or the
containerd image store). The wheel's layer sits before the agent CLIs.

## Decisions

### D1. The wheel's layer last

The `COPY --chown=lado:lado dist/lado-*.whl /tmp/wheel/` and its `uv tool install` move
after the openspec install, as the last `RUN` before `ENV`. They still run as `lado` with the
same `UV_*` variables, so `/opt/uv/tools` and `/opt/uv/bin` hold the same files. The
paragraph "Installed as lado: ..." moves with it.

### D2. A second builder, the image loaded into Docker

The cell sets up a BuildKit builder with `docker/setup-buildx-action` (driver
`docker-container`, pinned by SHA as every action of ci.yml) and passes `--builder <name>
--load` to the build, so the image lands as `lado:local` in the runner's Docker for the
container tests. GitHub's cache service needs the runtime's token and URLs in the build's
environment; `crazy-max/ghaction-github-runtime` (pinned by SHA) exports them for a CLI
build. Chosen over `docker/build-push-action`, which would replace `make docker` in CI and
so build the image by another command than the developers' (`make docker`).

### D3. Flags through make, chosen by the event

`Makefile`'s `docker` target becomes `docker build $(DOCKER_BUILD_FLAGS) -f
docker/Dockerfile -t $(LADO_IMAGE) .`, `DOCKER_BUILD_FLAGS` empty by default. The step
`Image` sets them by `github.event_name`:

| Event | Flags |
|---|---|
| `pull_request` | `--cache-from type=gha,scope=container-<arch>` |
| `push` (main) | `--cache-from` and `--cache-to type=gha,mode=min,scope=container-<arch>` |
| `schedule`, `workflow_dispatch` | `--no-cache` and `--cache-to` (same) |

A pull request reads the cache of `main` (GitHub lets a branch read its base's entries)
and writes none, so pull requests cannot fill the 10 GB limit. `mode=min` keeps only the
final image's layers: every expensive step is in the final stage, and the `FROM` stages
are pinned by digest and only copied from.

### D4. Shards (LAD-248)

When the container job gains a shard axis, only the cell of shard 1 per architecture
passes `--cache-to`; the others read only, so two cells never write one scope at once.

### D5. Tests that keep it

`tests/test_ci_workflow.py`: the step `Image`'s flags per event (D3), the scope per
architecture, no `cache-to` on `pull_request`, `--no-cache` on schedule and dispatch, the
builder set up before `Image`; `release.yml` holds no `cache-from`, `cache-to` or
`type=gha`. `tests/test_docker.py`: the wheel's `COPY` and install come after every CLI's
and openspec's install. The cache's effect itself (AC-1) is measured in the pull request's
CI, not by a test.

## Risks

- Restoring ~2 GB of layers and `--load` may eat part of the gain; AC-1 measures it. When
  the gain stays under 25 s per architecture, the build report says so with the numbers
  and the human decides at review whether to keep the cache (D1 helps in any case).
- A stale cache can hide a broken outside source for up to a day; the scheduled run (D3)
  bounds it, and the release builds from nothing.
