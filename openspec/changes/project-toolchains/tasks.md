## 1. The image (D2, D3, D5, D6, D8)

- [x] 1.1 `docker/Dockerfile`: `make gcc g++ libc6-dev` in the first apt layer; the stage
  `FROM jdxcode/mise:<version>@sha256:<index digest> AS mise` and its binary copied to
  `/usr/local/bin/mise` before `USER lado`; `docker/mise.toml` copied to
  `/etc/mise/config.toml`; the `/opt` install folders only in the build's `RUN` lines;
  the runtime `ENV` with `NPM_CONFIG_PREFIX=/home/lado/.local` and D5's `PATH`, without
  `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_PYTHON_INSTALL_DIR`. Check: `make docker`.
- [x] 1.2 `docker/mise.toml` (the enabled version files, with a comment on why Node is not
  among them) and `docker/Dockerfile.dockerignore` (allow it). Check: `mise settings` in a
  login shell of the image lists the four tools. Also `disable_update_warning = true`: the
  binary is the image's pin, so mise's "a newer version is available" is no news for the
  agents. And `idiomatic_version_file_ignore_minimum_versions = true` (the human's check):
  go.mod's `go` line, a minimum, made mise warn on every call (deprecated, dropped in mise
  2026.11.0) and won over `.go-version`; its `toolchain` line is still read.
- [x] 1.3 `docker/profile.sh`: D5's `PATH`, `NPM_CONFIG_PREFIX`,
  `MISE_TRUSTED_CONFIG_PATHS="$LADO_REPOS"`, each with its comment. Check: section 3.
- [x] 1.4 `tests/test_docker.py`: the unit tests of D9 (mise pinned and root's, the apt
  packages, mise.toml and its copy, the allowlist, the profile against `ENV`, no `/opt`
  install variable at run time; `unpinned` knows the stage `mise`). Check: `make test`.

## 2. LADO's instructions (D1)

- [x] 2.1 `src/lado/runtime.py`: `CONTAINER_INSTRUCTIONS` with the supervisor's and the
  worker's sentence, appended in `_spec` when `update.in_container()`. Check: 2.2.
- [x] 2.2 `tests/test_runtime.py`: a worker, a flow run's worker and the supervisor with
  `LADO_CONTAINER=1`, and a session without it (the requirement's three scenarios).
  Check: `make test`.

## 3. Container tests (D9)

- [x] 3.1 `tests/container/test_toolchains.py`: mise at its pin in a login shell; make
  with C and C++; Go from `.tool-versions` built, kept after the container is made again
  on the same volume; two installs of the same Go at once; a `mise.toml` without trust;
  Node 22 first with `mise use -g node@20`, Node 20 through `mise exec`. Check: `make
  docker && make test-container PYTEST_ARGS="-k toolchains"` locally once; CI's container
  cells.
- [x] 3.2 The same file: `npm install -g` (a local `npm pack` tarball) and `uv tool
  install` (a local package) in a login shell with the projects folder of uid 1001, files
  under `/home/lado/.local`, both commands found by a new login shell; the same on an
  `old_home` volume, its sessions listed. Check: as 3.1.
- [x] 3.3 Size and time (D7): `docker image inspect` of `lado:local` before and after,
  the compressed sizes of CI's build if it reports them, the step "Image" of the pull
  request's CI run against run 39008559275; the numbers in the pull request. CI reports
  no compressed size: amd64's is from a local `--platform linux/amd64` build.

## 4. Docs

- [x] 4.1 `docs/install.md`, Docker: a section "The projects' toolchains" (mise is there,
  agents install what a project needs into the home volume, kept over updates; a tool by
  hand: `docker compose exec lado mise use -g go@1.23`; Node 22 stays first; `make`,
  `gcc`, `g++` are there; other apt packages and databases are not covered; `mise prune`
  frees this container's old versions only; a second LADO has its own tools). "If
  something goes wrong in Docker": `No version is set for shim`, a refused Python
  version (attestations), a `mise.toml` outside the projects folder (`mise trust`). No
  global `docker * prune`. Old versions are freed with `mise ls` and `mise uninstall
  <tool>@<version>` instead of `mise prune`: `tests/test_docker.py` keeps the word
  "prune" out of everything users read.
- [x] 4.2 The Dockerfile's header (mise, the build tools, installs on the home volume),
  `docs/design/modules.md` (`docker/`: mise.toml, the PATH order, the installs),
  `docs/design/agents.md` (LADO's instructions: the container paragraph),
  CHANGELOG.md (`## 0.41.0 (unreleased)`, or the section LAD-87 opened).

## 5. Regression and the human's check

- [x] 5.1 `make lint`, `make test`, `openspec validate --specs --strict`; CI's container
  and smoke cells green.
- [x] 5.2 The pull request's description carries the human's check by hand on a Mac,
  each step with its folder, commands and expected result: in a fresh terminal `env |
  grep -E '^(LADO|COMPOSE)_'` and `unset` each; the branch through `git worktree add`
  (the human's checkout keeps its branch), `make docker`, compose with
  `LADO_IMAGE=lado:local`; (1) a Go project without Makefile or cgo, with
  `.tool-versions` (`go 1.23.4`) in the projects folder: an agent asked to build it
  installs Go through mise by itself and `go build` succeeds; (2) `docker compose up -d
  --force-recreate`: `docker compose exec lado bash -lc 'cd <project> && go version'`
  answers 1.23.4 with no install; (3) an update from 0.40.0's image on the same volume
  (`LADO_IMAGE` unset, `LADO_VERSION=0.40.0`, a session and the logins made; then
  `lado:local`): the sessions resumed, the logins kept, an agent's `npm i -g` and `uv
  tool install` work. Only fake secrets in it.
