## Context

The image installs Debian packages in one apt layer as root, then switches to `USER lado`
and installs LADO (`uv tool install --python 3.13`, with uv's Python downloaded into
`/opt/uv/python`, owned by `lado`) and the four agent CLIs (`npm install -g --prefix
/opt/agents`, one layer each). An agent's environment is its login shell's
(`agent_env.resolve`); `docker/profile.sh` (`/etc/profile.d/lado.sh`) sets it and the
Dockerfile's `ENV` sets the same for the server and `docker exec`, which
`tests/test_docker.py` keeps equal. `PATH` is `/opt/uv/bin:/opt/agents/bin`, the system's,
then `~/.local/bin` and mise's shims (`~/.local/share/mise/shims`), last so that no shim
shadows the image's Node 22.

Checked in this container (mise 2026.10.7): a mise shim whose tool has no version set for
the folder does not fail when the same command exists in a folder **after** the shims on
`PATH`. It runs that command. With no such command it fails with `No version is set for
shim`. uv's managed Python carries `EXTERNALLY-MANAGED`, so `pip install` into it is
refused. It also ships `pip`, `venv` and `ensurepip`. openspec 1.14.1 needs Node >= 20.19.
By default it sends usage statistics to `edge.openspec.dev` and checks npm for a newer
version. `OPENSPEC_TELEMETRY=0` and `OPENSPEC_NO_UPDATE_CHECK=1` switch each off.

## Decisions

### D1. The base tools come from Debian, in the first apt layer

`jq ripgrep unzip zip xz-utils bzip2 patch file rsync sqlite3 tree lsof netcat-openbsd`
join the existing `apt-get install` with `--no-install-recommends`. One layer, Debian's
versions, root's, updated by the base image's digest like tmux and git.

Options:
1. (chosen) Debian packages. No new source or pin to keep, and they are signed.
2. mise per tool. It needs a home volume and a first install, so a kit could not count on
   the tool, and several of these (`file`, `patch`, `lsof`) are not in mise's registry.
3. Static binaries downloaded at build time. Each needs a pin and a checksum to keep:
   long-term cost for nothing Debian lacks.

### D2. openspec is a pinned npm package under /opt/tools

`ARG OPENSPEC_VERSION=1.14.1` and `RUN npm install -g --prefix /opt/tools
"@fission-ai/openspec@${OPENSPEC_VERSION}" && npm cache clean --force`, as `lado`, after
the four CLIs (its own layer, so a moved pin rebuilds one). `/opt/tools` is made beside
`/opt/agents` and named only in the build's install line (as the other `/opt` folders).
`PATH` becomes `/opt/uv/bin:/opt/agents/bin:/opt/tools/bin:...`. openspec is not an agent
CLI: `/opt/agents` stays the four of `PINS`, and the unit test "no other npm package"
learns of the one extra package by its build argument.

Options:
1. (chosen) A pin in the image. It works on a clean home volume and is the same in every
   container of a version. A new openspec needs a new image and a hand edit of the pin,
   because Dependabot does not read npm packages inside a Dockerfile.
2. Install on demand through mise when a kit expects it. LADO has no such mechanism, and
   adding one (a kit installing commands) is a feature of its own: kit format, trust,
   network at session start.
3. Install into `/opt/agents`. It mixes a kit's tool into the agent CLIs' folder, which
   the tests and docs define as the four of `PINS`.

### D3. python3 is the image's Python 3.13, after mise's shims

The Python LADO runs on is installed as root before `USER lado`:
`UV_PYTHON_INSTALL_DIR=/opt/uv/python uv python install 3.13 --no-bin`, so that it does not
also write `python3.13` into root's `~/.local/bin`. `/opt/uv/python` stays root's: only
`/opt/uv/tools` and `/opt/uv/bin` are `lado`'s. LADO's `uv tool install --python 3.13` as
`lado` then finds it there and only reads it. If uv insists on a write (its `.lock`), the
build passes the interpreter's path (`--python /opt/uv/python/cpython-3.13-*/bin/python3.13`)
instead; the developer says which in the build report.

A root-owned folder `/opt/fallback/bin` holds two links, `python3` and `python`, to
`/opt/uv/python/cpython-3.13-linux-*-gnu/bin/python3.13`, resolved by a glob at build time
(amd64 and arm64). `PATH` ends with `:/opt/fallback/bin` after mise's shims, in the
`ENV` and in `profile.sh` alike.

Options:
1. (chosen) The image's 3.13 as a fallback after the shims. It adds 0 MB, a project's own
   Python wins (the shim fall-through checked above), and the interpreter is the one LADO is
   tested with.
2. Debian's `python3` (3.11, about 20 MB). It lands in `/usr/bin` before the shims and
   silently shadows a project's `.python-version`. That is the class of bug that the
   project-toolchains change avoided for Node only on purpose.
3. Put mise's shims before `/usr/bin`. That breaks the rule that the image's Node 22
   comes first, which Kilo, Codex and the kits' MCP servers need.

Leaving `/opt/uv/python` as `lado`'s was rejected: with the interpreter on every agent's
`PATH`, `pip install --break-system-packages` would change the Python LADO itself runs on.

### D4. openspec's statistics and update check are off

`OPENSPEC_TELEMETRY=0` and `OPENSPEC_NO_UPDATE_CHECK=1` go in the `ENV` and in
`profile.sh` (the unit test that keeps them equal learns the two names). The human's
choice: LADO's own statistics need a yes, and the image already turns off Claude Code's
update check. A user who wants them sets the variable with `-e` (server) or in the
profile of the home volume.

### D5. LADO's instructions do not change

The container paragraph (`runtime.CONTAINER_INSTRUCTIONS`) names what an agent could not
guess. Commands on `PATH` need no paragraph. Its sentence "make, gcc and g++ are
installed" stays true.

### D6. Measured size

The pull request gives `docker image inspect` sizes of `lado:local` before and after
(arm64 locally, amd64 by `--platform linux/amd64`). The task expects 30-40 MB.

### D7. Tests per requirement

- The image carries the agents' base tools: unit (`tests/test_docker.py`: each package in
  the first apt layer), container (each command answers in an agent's login shell from a
  clean environment).
- The image carries openspec at its pin: unit (the `ARG` is an exact version, its own
  layer under `/opt/tools`, `/opt/tools` named only in that line, `ENV` equal to the
  profile with the two variables), container (`openspec --version` equals the pin on a
  clean volume; with an older openspec set as the container default through mise (`mise use -g npm:@fission-ai/openspec@<older>`), it still
  answers the pin; the two variables in a login shell's environment).
- The image's python3 gives way to a project's Python: unit (the fallback folder last on
  `PATH` in `ENV` and profile, the Python install before `USER lado`), container (python3
  and python answer 3.13 outside a project; in a project with `.python-version` `3.12`
  after `mise install` they answer 3.12; `pip install` into the image's Python is
  refused and its files are root's; `python3 -m venv` works; LADO still serves).
- The image tells the agents they run in a container (modified): unit (profile and `ENV`),
  plus the existing container scenarios.
- No integration test: no LADO process behaviour changes. The container layer is the
  lowest one that runs the image.
- Regression: `make lint`, `make test`, `openspec validate --specs`, CI's container and
  smoke cells (the Dockerfile is off the smoke skip list).
