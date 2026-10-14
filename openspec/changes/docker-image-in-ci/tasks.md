Follows docs/superpowers/plans/2026-10-15-docker-image-in-ci.md; each task there has the
tests' code and the commit.

## 1. The fake endpoint as a module and a script

- [x] 1.1 Unit tests first (layer 1), `tests/test_fake_endpoint.py`: in process, 401 with
  Anthropic's and OpenAI's body and the requests kept; as a script on its port, each
  request a JSON line in its log. Plan, Task 1.
- [x] 1.2 `tests/fake_endpoint.py` (D9), `tests/smoke/conftest.py` imports it. `uv run
  pytest tests/test_fake_endpoint.py -n0`; the smoke collects (`-m smoke --collect-only`),
  and passes for `claude` where Claude Code is installed.

## 2. The container cell of smoke_ci.py

- [x] 2.1 Unit tests first, `tests/test_smoke_ci.py`: `container <out>` runs `uv run pytest
  -m container -n0 -v` into `container.log`, installs nothing, is red on a skip or a
  non-zero exit, keeps the evidence, and a missing `<out>` is a usage error. Plan, Task 2.
- [x] 2.2 `scripts/smoke_ci.py`: `cell`, shared by `run` and `container` (D11). `uv run
  pytest tests/test_smoke_ci.py -n0`.

## 3. The image and its compose file

- [x] 3.1 Unit tests first, `tests/test_docker.py`: Claude Code's default is
  `PINS["claude"]`, no other CLI, Node 22 from the official image's stage, bases pinned by
  digest, no piped install script, `profile.sh` and `ENV` the same, tini and the server's command, the context's allowlist,
  compose's port line, no container name, `LADO_PROJECTS` required, nothing only Docker
  Desktop has, Dependabot's `docker` entry. Plan, Task 3.
- [x] 3.2 `docker/Dockerfile`, `docker/Dockerfile.dockerignore`, `docker/profile.sh`,
  `docker/compose.yaml` (D1-D7), `make docker`, `.github/dependabot.yml` (D12). `uv run
  pytest tests/test_docker.py -n0`; with Docker, `make docker` builds, and the image prints
  the wheel's `lado --version`, `claude --version` 2.1.295 (a native binary), `node
  --version` 22 and `npx --version`.

## 4. The Container test layer

- [x] 4.1 Marker `container` out of the default run, `make test-container` (D8).
- [x] 4.2 Container tests (layer 7), `tests/container/`: `docker run` serves `/api/health`
  with the wheel's version and the UI on its `LADO_PORT`, the note in `docker logs`, `lado
  ui --no-open`'s link; 8765 without `LADO_PORT`; `lado doctor` clean, `in a container`,
  Claude Code ok and the other CLIs info; `node` 22 and `npx` in a login shell; a Claude
  Code session against the fake endpoint idle, the pane's process being the `claude` binary
  itself, its environment holding `LADO_CONTAINER=1` and its `lado doctor` saying `in a
  container` (D9, D10); compose on its `LADO_PORT` and refusing without
  `LADO_PROJECTS`. Plan, Task 4. With Docker: `make docker && make test-container`; `make
  test` collects none of them.

## 5. CI

- [x] 5.1 Unit tests first, `tests/test_ci_workflow.py`: the job `container` per
  architecture on its native runner, every run, `make docker` then `smoke_ci.py container`,
  its out uploaded always, nothing pushed; `ci-ok` needs it; `docker/` refused on the skip
  list. Plan, Task 5.
- [x] 5.2 `.github/workflows/ci.yml`: job `container`, `ci-ok`'s needs (D11). `uv run
  pytest tests/test_ci_workflow.py tests/test_workflow_security.py -n0`.

## 6. Docs and the regression run

- [x] 6.1 AGENTS.md (Commands, Layout, Testing: the Container layer, the CI paragraph) and
  CHANGELOG.md, 0.39.0 (D13). Plan, Task 6.
- [x] 6.2 Regression: `make lint`, `make test`, `openspec validate --specs --strict`,
  `openspec validate docker-image-in-ci --strict`; with Docker `make test-container`; with
  Claude Code `uv run pytest -m smoke -n0 -k claude`.
- [ ] 6.3 The pull request's CI: `container (amd64)`, `container (arm64)` and `ci-ok`
  green, the jobs' times in the build report.
- [ ] 6.4 By hand on a Mac (AC-9): the `docker run` link in the host's browser, a second
  LADO with `LADO_PORT=8766` and `-p lado-2` beside it; screenshots as run artifacts.
