Task: LAD-64

## Why

LADO's Docker image exists only as LAD-52's research prototype
(`docs/research/docker-install/`): built by hand, on arm64 only, from a LADO on PyPI, with
four agent CLIs. No build or CI picks it up, so any change of LADO can break LADO in a
container unseen until someone builds it by hand. This is step T3 of the Docker install
plan (docs/research/docker-install-plan.md): the image in a lasting place, with Claude Code
only, built and smoke-tested in CI on amd64 and arm64, published nowhere yet. The goal it
serves (the human's, 2026-10-15): a user starts LADO from a published image with one
command and gets a working environment; each release publishes the images (T7).

## What Changes

- `docker/Dockerfile`: LADO's image. It installs LADO from a wheel given to its build (in
  CI the wheel `make dist`-style built from the pull request's code; at release, T7, the
  very wheel the Release workflow uploads to PyPI), and Claude Code only, at its pin
  (`scripts/smoke_ci.py`'s `PINS`, its provider's `TESTED_VERSION`). Every default is
  inside the image, so one `docker run` with no other file starts it:

  ```
  docker run -d --name lado -p 127.0.0.1:8765:8765 -v lado-home:/home/lado \
    -v ~/projects:/projects <image>
  ```

  The UI server listens on `0.0.0.0` at the port of `LADO_PORT` (8765 by default) under
  tini; the image sets `LADO_CONTAINER=1` and `LADO_REPOS=/projects` in its environment
  and, for the agents, whose environment comes from the login shell, in
  `/etc/profile.d/lado.sh` too, with the programs' `PATH`, `CLAUDE_CONFIG_DIR` and Claude
  Code's update check off. Node.js 22 with npm (for the agents and kits' MCP servers run by `npx`), git, tmux, gh and
  an ssh client are in it.
- `docker/compose.yaml`: an optional compose file of the same image. One variable,
  `LADO_PORT` (8765 by default), is both the server's port in the container and the
  published one, `127.0.0.1:${LADO_PORT}:${LADO_PORT}`; `LADO_PROJECTS` (required) is the
  host's projects folder, mounted at `/projects`; the home volume keeps LADO_HOME and
  Claude Code's login. No fixed container name: a second LADO beside the first is
  `LADO_PORT=8766 docker compose -p lado-2 up -d`, its link `docker compose -p lado-2 exec
  lado lado ui --no-open`.
- `make docker` builds the image (`lado:local`) from the working copy: the web UI's
  bundle, the wheel, the image.
- A new test layer, **container** (`tests/container/`, marker `container`, `make
  test-container`): against a built image, with real Docker, no model. The `docker run`
  command above with a port other than 8765 serves `/api/health` on the host's loopback;
  `lado doctor` in the container has no `[FAIL]` and says `in a container`; a Claude Code
  session against a fake endpoint (run in the container) gets to idle; `lado doctor` run
  with the environment of the agent's own process says `in a container`; the compose file
  serves `/api/health` and `lado ui --no-open`'s link on its `LADO_PORT`.
- CI: a job `container (amd64)` / `container (arm64)` on GitHub's native runners
  (`ubuntu-24.04`, `ubuntu-24.04-arm`) builds the image from the pull request's wheel and
  runs the container layer; it runs on every CI run, publishes nothing, and `ci-ok` needs
  it. `docker/` is not on the smoke's skip list, and the unit tests refuse it there.
- The image's base images are pinned by digest and Dependabot updates them (ecosystem
  `docker`, `/docker`).

## Scope

New: `docker/Dockerfile`, `docker/Dockerfile.dockerignore`, `docker/profile.sh` (the image's `/etc/profile.d/lado.sh`),
`docker/compose.yaml`, `tests/container/` (conftest, test), `tests/fake_endpoint.py` (the
smoke's 401 endpoint, moved out of `tests/smoke/conftest.py` and runnable as a script),
`tests/test_docker.py` (the Dockerfile's pins and its Claude Code version). Changed:
`Makefile` (`docker`, `test-container`), `pyproject.toml` (marker `container`, left out of
the default run), `.github/workflows/ci.yml` (job `container`, `ci-ok`'s needs),
`.github/dependabot.yml`, `scripts/smoke_ci.py` (`container <out>`: the same pass rule as a
smoke cell), `tests/test_ci_workflow.py`, `tests/test_smoke_ci.py`,
`tests/smoke/conftest.py`, AGENTS.md (Commands, Layout, Testing, CI), CHANGELOG.md.
Capabilities: `container` and `continuous-integration` change. No LADO code under
`src/` changes. No schema change. Version: no feature of LADO's own (build files, tests
and CI), so a patch-level change; it goes into 0.39.0, unreleased already.

## Out of scope

- Publishing the image (GHCR, tags, the release workflow): T7. Nothing is pushed anywhere.
- Which way the documentation leads with, `docker run` or compose, and the update line
  that names compose (`docker compose pull && docker compose up -d`, LAD-59): decided in
  T7/T8, once the image is published; until then the line stays.
- The projects at the host's path, `safe.directory`: T4. The image keeps the prototype's
  `/projects`.
- The uid of the projects' owner on a Linux host: T5. The image's user is uid 1000; the
  smoke keeps its repository in the home volume, so the runner's uid 1001 does not matter.
- Stopping and resuming sessions with the container, a new image on an old `lado.db`: T6.
- The ssh agent's socket and `group_add: ["0"]` of the prototype, tokens: T10. The socket's
  path exists only under Docker Desktop, so the compose file would fail on a Linux host.
- OpenCode, Kilo and Codex in the image: the human's decision of one image with Claude
  Code only (plan, section 0).
- mise: T9.
- The full smoke scenario (a worker, messages, a stop) in the container: the smoke outside
  the container runs it on Linux and macOS; the container layer checks what the image
  adds.
- The prototype in `docs/research/docker-install/` and the plan file: they stay as they
  are, the research's evidence (the plan is updated by lad-52's supervisor).
- A build cache for CI's image builds: added when the job's time asks for it.

## Impact

- New files under `docker/`; a new test layer and `make` targets; a CI job `ci-ok` needs.
- Spec: `container` gains the image's requirements; `continuous-integration` gains the
  container job and `docker/` among the paths never on the skip list.
- Users: nothing changes for an install without Docker; the image is built from a checkout
  only (`make docker`) until T7 publishes it.
