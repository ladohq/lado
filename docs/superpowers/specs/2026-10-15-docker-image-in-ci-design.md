# LADO's Docker image in the repository, built and smoke-tested in CI: design

Task: LAD-64. Change: `openspec/changes/docker-image-in-ci/` (proposal, deltas `container`
and `continuous-integration`, `design.md` D1-D13). Step T3 of the Docker install plan
(docs/research/docker-install-plan.md); research docs/research/docker-install.md and its
prototype `docs/research/docker-install/`.

## Problem

The image exists only as LAD-52's prototype: built by hand on one Mac (arm64), from a LADO
on PyPI, with four agent CLIs, and picked up by no build or test. Any change of LADO, or of
the CLIs' pins, can break LADO in a container, and nobody sees it until someone builds the
prototype again. amd64, the architecture of most Linux hosts, Intel Macs and Windows, was
never built.

Root cause: the image is a hand-made artifact outside the build, so nothing ties it to the
code it packages.

## Goal

The human's end goal (2026-10-15): a user starts LADO from a published image with
practically one command and gets a working environment; each release publishes the images.
This step makes the image a built and tested part of the repository, without publishing it:

- the image holds exactly the LADO of the code under test (in CI the pull request's wheel;
  at a release, T7, the wheel PyPI gets);
- one `docker run`, with no other file, starts it; an optional compose file runs the same
  image with one port variable;
- CI builds it on amd64 and arm64 and checks, with real Docker and no model, that it serves
  the UI, that `lado doctor` is clean, and that a Claude Code agent in it starts and knows
  it runs in a container.

## What the user sees

From a checkout (until T7 publishes the image):

```
$ make docker                     # the web UI's bundle, the wheel, the image lado:local
$ docker run -d --name lado -p 127.0.0.1:8765:8765 \
    -v lado-home:/home/lado -v ~/projects:/projects lado:local
$ docker exec lado lado ui --no-open
http://127.0.0.1:8765/?token=<token>
```

Another port: `-e LADO_PORT=8766 -p 127.0.0.1:8766:8766`. With compose, from `docker/`:

```
$ LADO_PROJECTS=~/projects docker compose up -d
$ docker compose exec lado lado ui --no-open
$ LADO_PROJECTS=~/projects LADO_PORT=8766 docker compose -p lado-2 up -d   # a second one
```

Inside: LADO's UI server on `0.0.0.0:$LADO_PORT` under tini, Claude Code at its pin, git,
tmux, gh, an ssh client and Node 22 with npm; `lado doctor` says `in a container`; the New session window
starts in `/projects`; Claude Code's login and LADO_HOME live in the home volume and outlive
a new container.

## Approach

- `docker/Dockerfile` on `debian:bookworm-slim` (by digest): Debian 12's tmux 3.3a and git
  2.39; Node 22 and npm copied from the official `node` image (by digest), kept for the
  agents and `npx` MCP servers, without NodeSource's script; uv copied from its official
  image (by digest); LADO from the one wheel of the build context, into `/opt/uv`; Claude
  Code (a native binary that npm's postinstall puts in place) into `/opt/agents`; the
  user `lado`, uid 1000, made with `useradd`.
- The agents' environment comes from the login shell (`agent_env.resolve`), so
  `docker/profile.sh`, the image's `/etc/profile.d/lado.sh`, sets what `ENV` sets for them:
  `LADO_CONTAINER`, `LADO_REPOS`, `PATH`, `CLAUDE_CONFIG_DIR`, `DISABLE_AUTOUPDATER`, `LANG`;
  a unit test keeps the two the same.
- `docker/compose.yaml`: `LADO_PORT` both inside and published on `127.0.0.1`; no fixed
  container name; `LADO_PROJECTS` required; no ssh socket (T10: its path exists only under
  Docker Desktop).
- A new test layer, Container (`tests/container/`, marker `container`): host-side pytest
  driving the `docker` CLI against a built image. The 401 endpoint of the smoke tests moves
  to `tests/fake_endpoint.py` and runs inside the container.
- CI's job `container` per architecture on native runners: `make docker`, then
  `scripts/smoke_ci.py container`, red on any skip; `ci-ok` needs it; it runs on every CI
  run.

Alternatives and the reasons for each choice: design.md, Context and D1-D13.

## Requirements and their test layers

| Requirement (spec) | Layer | Tests |
|---|---|---|
| container: one docker run starts the UI server | 7, Container | `test_docker_run_serves_the_ui_on_its_port`, `test_lado_doctor_is_clean_in_the_container` |
| container: LADO from the wheel given to the build | 7, Container | `test_docker_run_serves_the_ui_on_its_port` (health's version = the wheel's; `/` serves `index.html`) |
| container: the agents know they run in a container | 7, Container | `test_a_claude_session_gets_to_idle_and_knows_the_container` |
| container: Claude Code only, at its version; pinned bases | 1, Unit | `tests/test_docker.py` |
| container: Node 22 and npx for the agents | 1, Unit + 7, Container | `tests/test_docker.py` (the node stage); `test_node_and_npx_are_on_the_login_shells_path` |
| container: compose publishes one port number | 1, Unit + 7, Container | `tests/test_docker.py` (the port line); `test_compose_serves_on_lado_port` |
| CI: builds and smoke-tests the image on two architectures | 1, Unit | `tests/test_ci_workflow.py`, `tests/test_smoke_ci.py` |
| CI: `docker/` never on the skip list | 1, Unit | `tests/test_ci_workflow.py` (`SMOKE_RUNS`) |

Regression: `make lint`, `make test` (unit), `uv run pytest -m smoke -n0 -k claude` once
locally after `Endpoint` moves (the smoke's own CI cells run it on every provider), and
`make docker && make test-container` locally when Docker is there; CI runs the rest.

## Acceptance criteria

- AC-1: CI's `container (amd64)` and `container (arm64)` build the image from the run's
  wheel and pass; `ci-ok` needs them.
- AC-2: `docker run` with `-e LADO_PORT=<p> -p 127.0.0.1:<p>:<p>` serves `/api/health` on
  the host with the wheel's version and the UI's `index.html`; without `LADO_PORT`, port 8765.
- AC-3: `lado doctor` in the container exits 0 with no `[FAIL]`, its LADO line ends with
  `in a container`, Claude Code is `ok`, the other CLIs `info`.
- AC-4: a Claude Code session against the fake endpoint gets its supervisor to idle, and
  `lado doctor` run with the agent's process environment says `in a container`; the
  agent's process is the `claude` binary itself.
- AC-5: `docker/compose.yaml` publishes `127.0.0.1:${LADO_PORT}:${LADO_PORT}`; its
  `lado ui --no-open` link names that port; it refuses to start without `LADO_PROJECTS`.
- AC-6: the image has Claude Code at `PINS["claude"]` and no other agent CLI, and Node 22
  with npm and npx on the agents' `PATH`; its bases are
  pinned by digest; Dependabot watches `/docker`; unit tests keep each.
- AC-7: `docker/` is not on the smoke's skip list, and a unit test refuses it there.
- AC-8: nothing is pushed to any registry.
- AC-9 (by hand, Mac): `docker run` (or `docker compose up -d` from `docker/`): the link
  from `lado ui --no-open` opens in the host's browser; a second container with
  `LADO_PORT=8766` and its own volume runs beside the first.
