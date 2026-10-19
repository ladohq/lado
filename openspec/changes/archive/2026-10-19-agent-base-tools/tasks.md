## 1. The image (D1-D4)

- [x] 1.1 `docker/Dockerfile`: `jq ripgrep unzip zip xz-utils bzip2 patch file rsync
  sqlite3 tree lsof netcat-openbsd` in the first `apt-get install`, with the comment above
  it saying what they are for (D1). Check: 1.5, `make docker`.
- [x] 1.2 `docker/Dockerfile`: uv's Python 3.13 installed as root before `USER lado`
  (`UV_PYTHON_INSTALL_DIR=/opt/uv/python uv python install 3.13 --no-bin`); `/opt/uv/python`
  left root's, `/opt/uv/tools` and `/opt/uv/bin` `lado`'s; `/opt/fallback/bin` (root's)
  with the links `python3` and `python` to the installed `python3.13` (a glob, amd64 and
  arm64); LADO's `uv tool install` still finds it, or takes its path (D3: say which in the
  build report). Check: `make docker`, then section 2.
- [x] 1.3 `docker/Dockerfile`: `ARG OPENSPEC_VERSION=1.14.1` and its own `RUN npm install
  -g --prefix /opt/tools "@fission-ai/openspec@${OPENSPEC_VERSION}" && npm cache clean
  --force` after the four CLIs; `/opt/tools` made with `/opt/agents` (D2). Check: 1.5.
- [x] 1.4 `docker/Dockerfile`'s `ENV` and `docker/profile.sh`: `PATH`
  `/opt/uv/bin:/opt/agents/bin:/opt/tools/bin:` + the system's + `~/.local/bin` + mise's
  shims + `:/opt/fallback/bin`; `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1`
  (D4); each with its comment. Check: 1.5.
- [x] 1.5 `tests/test_docker.py`: the base packages in the first apt layer (a missing one
  named); `OPENSPEC_VERSION` an exact version, installed in a layer of its own under
  `/opt/tools`; "no other npm package" allows exactly the four CLIs and openspec;
  `/opt/tools` named only in the build's install lines; the Python install before
  `USER lado`; profile against `ENV` with the new `PATH` (fallback folder last) and the
  two variables. Check: `make test`.

## 2. Container tests (D7)

- [x] 2.1 `tests/container/test_toolchains.py` (or a new `test_base_tools.py` beside it,
  marker `container`): in a login shell from a clean environment on a new home volume,
  each base tool answers its version or help flag; `openspec --version` equals the
  Dockerfile's pin; `OPENSPEC_TELEMETRY=0` and `OPENSPEC_NO_UPDATE_CHECK=1` in the
  environment of the login shell and of `docker exec`.
- [x] 2.2 The same file: with an older openspec as mise's container default, `openspec
  --version` still answers the pin.
- [x] 2.3 The same file: `python3` and `python` answer 3.13 outside a project; a project
  with `.python-version` `3.12` after `mise install` answers 3.12, and its parent folder
  still 3.13; `python3 -m pip install` of a local package outside an environment is
  refused and the image's Python is root's and not writable by `lado`; `python3 -m venv`
  plus its pip installs a local package; `lado --version` still answers. Check: `make
  docker && make test-container PYTEST_ARGS="-k <file>"` locally once; CI's container
  cells (run in CI only: the developer's container has no Docker).
- [ ] 2.4 Size (D6): `docker image inspect` of `lado:local` before and after (arm64, and
  amd64 by `--platform linux/amd64`); the numbers in the pull request. Not done in the
  build: the developer's container has no Docker; the human measures it with 4.2's
  `make docker` and the numbers go into the pull request then.

## 3. Docs

- [x] 3.1 The Dockerfile's header: the base tools, openspec at its pin with statistics
  off, python3 giving way to a project's Python.
- [x] 3.2 `docs/install.md`, Docker, "The projects' toolchains": the list of tools the
  image has; `python3` is the image's 3.13 unless a project's version file or `mise use -g`
  names another; openspec is the image's, a mise-installed one is shadowed; shellcheck and
  other missing tools through mise.
- [x] 3.3 `docs/design/modules.md` (`docker/`): the apt list, `/opt/tools`, the PATH order
  with `/opt/fallback/bin`, the root-owned Python, the two variables of `ENV` and
  profile.
- [x] 3.4 CHANGELOG.md under `## 0.42.0 (unreleased)` (add the heading): the image's new
  tools, openspec at its pin with statistics off, python3.

## 4. Regression

- [x] 4.1 `make lint`, `make test`, `openspec validate --specs --strict`,
  `openspec validate agent-base-tools --strict`; CI's container and smoke cells green.
- [x] 4.2 The pull request's description carries the human's check: `make docker`,
  compose with `LADO_IMAGE=lado:local` on a new home volume, an sdlc session starts
  (openspec found), an agent runs `python3 --version`, `rg --version` and `jq --version`.
