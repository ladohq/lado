Task: LAD-93

## Why

LADO's image has git, Python (through uv) and Node.js 22, and nothing else to build a
project with: an agent in the container cannot build or test a project in Go, Rust, Java
or C, and it cannot install their toolchains either (no root, no apt). Whatever it
manages to install outside the home volume is lost when the container is made again. So
today the container is of real use only for Python and JavaScript projects (step T9 of
`docs/research/docker-install-plan.md`; research H9 showed that mise on the home volume
works, but no agent was ever told to use it).

Checked on the 0.40.0 image (`lado:local`):

- An agent's environment comes from a login shell started from a clean environment
  (`agent_env.resolve`), so the Dockerfile's `ENV NPM_CONFIG_PREFIX=/opt/agents` and
  `UV_TOOL_DIR=/opt/uv/...` never reach it: its npm's prefix is `/usr/local`, root's, and
  **`npm i -g` fails for every agent, at any uid**. Its `uv tool install` already writes to
  `~/.local` on the home volume, but `~/.local/bin` is on `PATH` only when it existed at
  the login (Debian's `~/.profile`), so a tool installed is found from the agent's next
  start on.
- `docker exec` (the human's shell) does get that `ENV`: its `npm i -g` and `uv tool
  install` write to `/opt`, which stays uid 1000's after the entrypoint gives `lado` the
  projects owner's uid (T4), so they fail on a Linux host whose uid is not 1000, and what
  they install is lost with the next image anyway.
- Debian slim has no `make`, `gcc` or `g++`: Makefiles, Go with cgo and native modules of
  Node (node-gyp) and Python cannot build.

## What Changes

- **mise in the image**: `/usr/local/bin/mise` (root's, so no agent replaces it), from
  mise's official image pinned by digest like uv's and Node's, updated by Dependabot.
  Its data, config and cache stay at mise's defaults under `/home/lado`, on the home
  volume: a tool installed survives a recreation and an image update. Its shims folder is
  on every login shell's `PATH`, after the image's own programs.
- **The image's settings for mise** in its system config `/etc/mise/config.toml`
  (`docker/mise.toml`), which a new image replaces: the version files of Go, Java, Python
  and Ruby (`.go-version`, `.java-version`, `.python-version`, `.ruby-version`, ...) are
  read besides `.tool-versions` and `mise.toml`; every project under the projects folder
  (`LADO_REPOS`) is trusted, so its `mise.toml` needs no `mise trust`.
- **Node 22 of the image stays first** on `PATH`: Kilo and Codex start through `env node`
  in the project's folder and kits' MCP servers through `npx`, so a project's old Node
  would break the agents themselves. A project that needs another Node runs it through
  mise explicitly (`mise exec node@20 -- npm test`); `.nvmrc` and `.node-version` are not
  enabled.
- **Build tools**: `make`, `gcc`, `g++` and `libc6-dev` from Debian.
- **The agents' global installs on the home volume**: `npm i -g` and `uv tool install`
  write under `~/.local` (npm's prefix `$HOME/.local`, uv's defaults), and `~/.local/bin`
  is on every login shell's `PATH` from the start. The image's `ENV` no longer points
  installs at `/opt`; the baked-in agent CLIs and LADO stay in `/opt`.
- **The agents are told**, in LADO's instructions and only in a container, that mise is
  there: a missing tool the project needs is installed with mise (`mise install` in the
  project, by its version files; a tool or version they do not name with
  `mise install <tool>@<version>` and `mise exec`), nothing is added to the project unless
  asked, and apt packages and databases cannot be installed. Any agent may install; only
  the supervisor sets a tool's container-wide default version (`mise use -g`), and a
  worker that needs one asks it.
- **Docs**: docs/install.md (Docker: a section on the projects' toolchains; If something
  goes wrong in Docker), the Dockerfile's header, docs/design/modules.md (`docker/`),
  docs/design/agents.md (LADO's instructions), CHANGELOG.md.
- A minor release (a feature of the image and of the agents' instructions): the line goes
  under `## 0.41.0 (unreleased)`.

## Scope

- `docker/Dockerfile`, `docker/profile.sh`, the new `docker/mise.toml`,
  `docker/Dockerfile.dockerignore`.
- `src/lado/runtime.py`: the container paragraph of LADO's instructions.
- Tests: unit (`tests/test_docker.py`, `tests/test_runtime.py`), container
  (`tests/container/`).
- Docs as listed above.

## Out of scope

- **Other apt packages and databases** (PostgreSQL, Redis, system libraries a project
  links to): mise does not install them, and each is the project's own; the guide says
  so. A later task when a real project needs one.
- **A project's own dev container** (`.devcontainer`) and **Nix**: other ways to bring a
  toolchain, far larger (research 5.2).
- **The project's Node through `.nvmrc`**: decided against, see "Node 22 of the image
  stays first".
- **Enforcing the supervisor-only default version**: every agent has the shell and mise,
  and no CLI can take one command away; it is a rule in the instructions only.
- **Switching off mise's checks** (the GitHub attestations it asks of some prebuilt
  Python versions): a refused version is reported to the human, not forced.
- **Making `/opt` root's**: the baked-in CLIs are installed as `lado` to avoid a copied
  layer; the agents no longer write there, which is the task.
- **Codex**: nothing of it changes until T15; it gets the same instructions as any agent.
- **A `lado doctor` line for mise**: the container tests check mise; nothing asks for it.

## Impact

- The image grows by mise and the build tools; measured numbers in the pull request
  (design D7).
- An old home volume needs no migration: the settings live in `/etc`, the image's.
- LADO's instructions in a container are longer by one paragraph for every agent, on
  every provider.
