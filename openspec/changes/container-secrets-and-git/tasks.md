Tests first in each section; each task is one commit. The plan with the code is
`docs/superpowers/plans/2026-10-16-container-secrets-and-git.md`.

## 1. The outside folder in agent_env

- [ ] 1.1 Unit tests (layer 1), `tests/test_agent_env.py`: a file is a variable, one
  trailing newline dropped, each file not used with its reason (bad name, reserved, over
  64 KiB, not text, subfolder; dotfiles silent), no folder, a relative or unlistable
  folder, the folder over the login shell, read anew, no value in a line. Plan, Task 1.
- [ ] 1.2 `agent_env.outside()`, `Outside`, `RESERVED`, `resolve()` merging it (D1, D2,
  D5, D12). `uv run pytest tests/test_agent_env.py -n auto`, `make lint`.

## 2. Warnings of a start, resume and spawn

- [ ] 2.1 Unit tests, `tests/test_runtime.py`: a start names the files not used; a
  provider-set name keeps LADO's value and is named; a spawn names only provider-set
  names. Plan, Task 2.
- [ ] 2.2 `runtime._outside_warnings` in `start_session` and `spawn_worker` (D3, D4).
  `uv run pytest tests/test_runtime.py -n auto`.

## 3. lado doctor

- [ ] 3.1 Unit tests, `tests/test_doctor.py` (and the bug report's): names and files not
  used, `none`, `no folder`, no check without the variable, no name or value in the
  report. Plan, Task 3.
- [ ] 3.2 `doctor.check_outside` in `run_checks`. `uv run pytest tests/test_doctor.py
  -n auto`.

## 4. Integration

- [ ] 4.1 `tests/integration/test_outside_variables.py` (layer 2, fake agent): a worker
  gets the folder's variable and a later file reaches only a later worker; a kit whose
  MCP server needs the variable starts with the file and is refused without; no value in
  LADO's logs. `uv run pytest -m integration -n auto
  tests/integration/test_outside_variables.py`. Plan, Task 4.

## 5. The image: secrets folder, git identity, gh

- [ ] 5.1 Unit tests, `tests/test_docker.py`: `LADO_ENV_DIR=/run/secrets` and no
  `LADO_AGENT_ENV`; compose's read-only secrets bind with `create_host_path: false`;
  compose's environment holds only `LADO_PORT`, `LADO_REPOS`, `LADO_GIT_NAME`,
  `LADO_GIT_EMAIL`; gh as github.com's credential helper; the entrypoint's git lines and
  warning. Plan, Task 5.
- [ ] 5.2 Dockerfile, compose.yaml, entrypoint.sh, `.gitignore`; the container tests'
  compose projects get their own `secrets` folder (`LADO_SECRETS`) (D6, D7, D8).
  `uv run pytest tests/test_docker.py -n auto`.

## 6. ssh without root's group

- [ ] 6.1 Unit tests, `tests/test_docker.py`: the rule names one program, no `SETENV`;
  the program takes no argument, checks the socket, sets its PATH; compose binds
  `${LADO_SSH_AGENT:-/dev/null}`; the profile's conditional `SSH_AUTH_SOCK`; no
  `group_add`. Plan, Task 6.
- [ ] 6.2 `docker/ssh-agent-socket.sh`, Dockerfile (program, rule, `/run/lado`),
  `.dockerignore`, compose.yaml, profile.sh, entrypoint.sh (D9, D10, D11).
  `uv run pytest tests/test_docker.py -n auto`.

## 7. Container tests

- [ ] 7.1 `tests/container/test_access.py` (layer 7): a kit with a variable starts and
  `docker inspect` holds no value; git identity with an apostrophe, and the warning
  without it; gh gives github.com its token; ssh through a root-owned socket (also after
  a restart), through one of the projects' owner, none without it; the ssh rule gives no
  root. `make docker`, `uv run pytest -m container -n0 tests/container/test_access.py`,
  then `make test-container`. Plan, Task 7.

## 8. Headers, AGENTS.md, CHANGELOG

- [ ] 8.1 Unit test: both headers name every step (secrets, git identity, `GH_TOKEN`, `gh
  auth login`, `LADO_SSH_AGENT` for Mac and Linux, `CLAUDE_CODE_OAUTH_TOKEN`, `opencode
  auth login`, `kilo auth login`, `mkdir -m 700 secrets`). Plan, Task 8.
- [ ] 8.2 Headers of compose.yaml and the Dockerfile; AGENTS.md (Layout `agent_env.py`,
  How agents talk, `docker/`, Commands' container paragraph); CHANGELOG under `0.40.0
  (unreleased)`.

## 9. Regression run and the pull request

- [ ] 9.1 `make lint`, `make test`, the integration file, `make docker && make
  test-container`, `openspec validate --specs --strict`, `openspec validate
  container-secrets-and-git --strict`; CI's `ci-ok` on the pull request.
- [ ] 9.2 The pull request's body carries the design doc's manual check step by step,
  starting with `env | grep LADO` and `unset`.
