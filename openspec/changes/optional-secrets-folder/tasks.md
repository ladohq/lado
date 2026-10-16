Tests first in each section; each task is one commit.

## 1. The null device in agent_env

- [ ] 1.1 Unit tests (layer 1), `tests/test_agent_env.py`: `LADO_ENV_DIR=/dev/null` gives
  no values and no line; a regular file still gives `not a folder`; a missing path no line.
  `tests/test_runtime.py`: a start with `LADO_ENV_DIR=/dev/null` has no warning about it.
- [ ] 1.2 `agent_env.outside()`: a character device with `os.devnull`'s `st_rdev` is no
  folder (D1); its docstring and the module's say so. `uv run pytest
  tests/test_agent_env.py tests/test_runtime.py -n auto`, `make lint`.

## 2. lado doctor

- [ ] 2.1 Unit tests, `tests/test_doctor.py`: in a container (`LADO_CONTAINER=1`) the
  null device and no folder give `[info] … /run/secrets: none` with the hint naming
  `LADO_SECRETS=./secrets`; outside a container `/dev/null` gives `no folder` with no
  hint; a regular file warns in both; exit code 0.
- [ ] 2.2 `doctor.check_outside` (D3). `uv run pytest tests/test_doctor.py -n auto`.

## 3. compose, the headers

- [ ] 3.1 Unit tests, `tests/test_docker.py`: the secrets bind's source is
  `${LADO_SECRETS:-/dev/null}`, read-only, `create_host_path: false`; neither header's
  first start has `mkdir`; both headers name `LADO_SECRETS=./secrets` (compose) or the
  `-v …:/run/secrets:ro` (Dockerfile); the header's update is the `curl -fLO` of
  `releases/download/v<version>/compose.yaml`, then `docker compose up -d`; the address
  matches the release workflow's tag and asset.
- [ ] 3.2 `docker/compose.yaml` (default and header: optional secrets, the update's
  download, `.env`/`secrets/`/volume stay) and `docker/Dockerfile`'s header (D2, D4, D5).

## 4. README, the guide, CHANGELOG, design docs

- [ ] 4.1 Unit tests, `tests/test_docker.py`: the guide's and README's start have no
  `mkdir`; "The agents' variables" has `LADO_SECRETS=./secrets` and `mkdir -m 700
  secrets`; the guide's and README's update download the version's `compose.yaml` before
  `docker compose up -d`; the guide's update equals the header's; the guide says to carry
  over a change made by hand.
- [ ] 4.2 README.md (Docker install, Update › Docker), docs/install.md (opening, Start,
  The agents' variables, Update the container, A second LADO: "a `secrets/` of its own or
  none", Docker run, pitfalls). `make test`.
- [ ] 4.3 CHANGELOG.md: amend the 0.40.0 lines of LAD-76 and LAD-83 (D6).
- [ ] 4.4 docs/design/modules.md (the image's secrets bind) and docs/design/agents.md (the
  null device is no layer), true to the code.

## 5. Container tests

- [ ] 5.1 `tests/container/conftest.py`: the `compose` fixture's `LADO_SECRETS` becomes
  optional (a test without it gets compose's default).
- [ ] 5.2 Layer 7: a project with no `LADO_SECRETS` and no `secrets/` starts; `lado
  doctor` exits 0 with `[info] Variables from outside: /run/secrets: none`; `docker compose
  logs lado` has no line about `/run/secrets` or `LADO_ENV_DIR`; a session with the fake
  endpoint reaches idle.
- [ ] 5.3 Layer 7: a project in a folder of its own, a copy of `compose.yaml`, `.env` with
  `LADO_SECRETS=./secrets`, `secrets/` (700) with a fake `GH_TOKEN`: an agent's shell has
  it; doctor `[ok  ] … GH_TOKEN`. `uv run pytest -m container -n0 tests/container/<file>`
  after `make docker`; else CI.

## 6. Checks and the pull request

- [ ] 6.1 `make lint`, `make test`, `openspec validate optional-secrets-folder --strict`,
  `openspec validate --specs --strict`; grep `openspec/specs/` for `./secrets` and `refuses
  to start` and resolve every hit in the delta.
- [ ] 6.2 The pull request's description holds the check by hand on a Mac, with a
  `git worktree add` of the branch so the human's checkout stays where it is: a fresh
  terminal, `env | grep -E '^(LADO|COMPOSE)_'` and `unset` each name printed; `make
  docker` in the worktree; then
  1. a minimal start without `secrets/` (a new folder, `compose.yaml` of the branch,
     `.env` with `LADO_IMAGE=lado:local`, an own `COMPOSE_PROJECT_NAME` and port): the UI
     opens, `lado doctor` shows the `[info]` line, `docker compose logs lado` has no
     `/run/secrets` line, `docker compose exec -it lado claude` logs in;
  2. `LADO_SECRETS=./secrets` in `.env`, `mkdir -m 700 secrets`, a `GH_TOKEN`
     (`printf %s "$(gh auth token)" > secrets/GH_TOKEN`), `docker compose up -d`: an
     agent's shell answers `gh api user` with the human's login;
  3. an update from 0.39.0: a folder with 0.39.0's `compose.yaml` and `.env`, its own
     project name and port, started; then the guide's update step with the branch's
     `compose.yaml` in place of the download and `LADO_IMAGE=lado:local`; the home volume
     and its sessions are there.
  What each step should show, and removal of only these projects' containers and volumes
  by name (`docker compose down`, `docker volume rm <project>_home`); no `prune`.
