## Context

LADO's image (`docker/Dockerfile`) installs its programs under `/opt` (LADO in
`/opt/uv`, the four agent CLIs in `/opt/agents`), owned by uid 1000, and keeps state on
the home volume `/home/lado`. The entrypoint gives `lado` the projects owner's uid at a
container's first start (T4) and chowns the home volume when its files are another uid's;
`/opt` stays uid 1000's. An agent's environment is its login shell's, started from a
clean environment (`agent_env.resolve`: `HOME`, `USER`, `SHELL`, ... and the base `PATH`),
so only `/etc/profile.d/` (`docker/profile.sh` as `lado.sh`, the entrypoint's
`lado-repos.sh`, `lado-ssh-agent.sh`) and the volume's own `~/.profile` shape it; the
Dockerfile's `ENV` reaches the server and `docker exec` only. `/etc/profile.d/` is read in
name order: `lado-repos.sh`, `lado-ssh-agent.sh`, then `lado.sh`, so `lado.sh` can use
`$LADO_REPOS`.

Measured on 0.40.0 (`lado:local`, arm64): an agent's login shell has
`PATH=/opt/uv/bin:/opt/agents/bin:/usr/local/bin:/usr/bin:/bin:...`, `npm config get
prefix` `/usr/local` (root's: `npm i -g` fails), `uv tool dir` `~/.local/share/uv/tools`,
`uv tool dir --bin` `~/.local/bin`; Debian's `~/.profile` puts `~/.local/bin` first on
`PATH` only when it exists at the login. Kilo's and Codex's commands are `#!/usr/bin/env
node` scripts; Claude Code and OpenCode are native binaries.

LADO's instructions (`runtime.SUPERVISOR_INSTRUCTIONS`, `RUN_WORKER_INSTRUCTIONS`,
`WORKER_INSTRUCTIONS`, `READ_ONLY_INSTRUCTIONS`, `MESSAGING`) are appended to the kit's
role in `runtime._spec`, and each provider hands that text to its CLI its own way
(Claude Code `--append-system-prompt-file`, OpenCode and Kilo `instructions`, Codex
`developer_instructions`).

Root cause: the image has no way for an agent to get a toolchain, and the one place it
can write programs to (`~/.local`) is not where npm points nor fully on `PATH`.

## Decisions

### D1. The agents learn of mise from LADO's instructions, in a container only

`runtime.py` gets `CONTAINER_INSTRUCTIONS` (the common paragraph) with a supervisor's
sentence and a worker's sentence, appended in `_spec` when `update.in_container()`, after
`READ_ONLY_INSTRUCTIONS` and before `MESSAGING`; the supervisor's sentence when the agent
is the session's supervisor (`agent.name == SUPERVISOR`), the worker's otherwise (a flow
run's worker too). Wording, to be kept close:

> You run in LADO's container. A tool the project needs and lacks (go, cargo, java, ...):
> install it with mise, into the home volume, where it stays for every agent of this
> container. In the project's folder `mise install` installs what its version files name
> (`.tool-versions`, `mise.toml`, `.go-version`, `.python-version`, ...); a tool or
> version they do not name: `mise install <tool>@<version>`, then run it with
> `mise exec <tool>@<version> -- <command>`. Add no version file or other file to the
> project unless the human asks. Node is the image's Node 22; another Node only through
> `mise exec node@<version> -- ...`. make, gcc and g++ are installed; apt packages and
> databases cannot be installed: say so instead. A version mise refuses: report it, do
> not switch its checks off.
> Supervisor: Only you set a tool's default version for the whole container
> (`mise use -g <tool>@<version>`), which every agent gets where no version file names
> one; workers ask you for it.
> Worker: Do not set a tool's default version for the whole container (`mise use -g`):
> ask the supervisor.

Options: (1, chosen) LADO's instructions: one text, every provider through its own
channel for the role (neutral core; native, as the role itself is), no file on the
volume to drift; cost a paragraph in every agent's context in a container. (2) Each
CLI's global instructions file on the home volume (`~/.claude/CLAUDE.md`, OpenCode's and
Kilo's): three files, one per CLI, on a volume an old image wrote and the human may have
edited, and a global agent config LADO never touches. (3) A bash
`command_not_found_handle` through `BASH_ENV` printing the hint at the failure: it runs in
every bash script of the projects and depends on how each CLI starts its shell. Against
ROADMAP: the coming stages keep LADO's instructions as the one channel to all agents.

### D2. mise from its official image, pinned by digest

`FROM jdxcode/mise:<version>@sha256:<index digest> AS mise` and `COPY --from=mise
/usr/local/bin/mise /usr/local/bin/mise` before `USER lado`, so it is root's and no agent
replaces it (`mise self-update` cannot write there). The image is a static binary on
scratch for amd64 and arm64 (2026.10.12: 52 MB amd64, 59 MB arm64 compressed). The
version: the newest release at least 7 days old at build time (Dependabot's cooldown);
the digest is the multi-arch index's. Dependabot's `docker` ecosystem for `/docker` then
updates it with the other bases; `tests/test_docker.py`'s `unpinned` learns the stage
name `mise`. Options: (2) the release asset by `curl` with a SHA256 per architecture in
the Dockerfile: no Dependabot, two checksums by hand; (3) mise's apt repository: a
signing key to trust and a version pinned by hand.

### D3. mise's settings in its system config, its data at its defaults

`docker/mise.toml`, copied to `/etc/mise/config.toml` (mise's system config, which the
image owns and a new image replaces), sets `idiomatic_version_file_enable_tools = ["go",
"java", "python", "ruby"]` (the setting's form for the pinned version: the developer
checks it with `mise settings` in the image). Node is left out (D5). Data, config and
cache stay at mise's defaults (`~/.local/share/mise`, `~/.config/mise`, `~/.cache/mise`),
on the home volume; no `MISE_*_DIR` is set. `mise use -g` writes `~/.config/mise/config.toml`
on the volume. A uid change chowns them with the rest of the home (T4).

### D4. Projects under LADO_REPOS are trusted

`profile.sh` exports `MISE_TRUSTED_CONFIG_PATHS="$LADO_REPOS"` (after `lado-repos.sh`,
D-context), so a project's `mise.toml` there, a worktree's under `.lado/worktrees/` too,
needs no `mise trust`. The agents run the projects' code anyway (tests, builds), so this
gives nothing more. A folder outside `LADO_REPOS` (a warning, not a refusal) still asks
for `mise trust`. Not in the Dockerfile's `ENV`: it cannot follow `-e LADO_REPOS`, and the
human's `docker exec` can `mise trust`.

### D5. The image's programs first on PATH, mise's shims last

`profile.sh`: `export PATH="/opt/uv/bin:/opt/agents/bin:$PATH:$HOME/.local/bin:$HOME/.local/share/mise/shims"`.
A shim never shadows a program of the image: Node 22, npm and npx stay the image's, so
Kilo and Codex (`env node`) and kits' MCP servers (`npx`) keep the Node they are tested
with, whatever a project names. Go, Rust, Java and Python (the image has no `python` on
`PATH`) come from the shims. Debian's `~/.profile` on the volume still puts `~/.local/bin`
first once it exists, as on 0.40.0: an agent's `npm i -g` of a CLI then shadows the
baked-in one, which `lado doctor` shows as an untested version. The Dockerfile's `ENV
PATH` gets the same order with `/home/lado` for `$HOME`.

### D6. Installs under ~/.local, not /opt

`profile.sh` exports `NPM_CONFIG_PREFIX="$HOME/.local"` (packages in
`~/.local/lib/node_modules`, commands in `~/.local/bin`); uv keeps its defaults
(`~/.local/share/uv/tools`, `~/.local/bin`, Pythons in `~/.local/share/uv/python`). The
runtime `ENV` drops `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_PYTHON_INSTALL_DIR` and sets
`NPM_CONFIG_PREFIX=/home/lado/.local`; the build sets the `/opt` folders only in the
`RUN` lines that install LADO and the CLIs (`UV_TOOL_DIR=... uv tool install`,
`npm install -g --prefix /opt/agents` as now). LADO's own venv keeps its absolute links
into `/opt/uv/python`. An old volume needs no migration: nothing of 0.40.0 an agent
installed is under `/opt`, and its `uv tool` installs under `~/.local` keep working.
Options: (2) chown `/opt` to the new uid in the entrypoint's root phase: a copy of the
CLIs' 1.2 GB layer at the first start and installs still lost with each image.

### D7. Size and build time, before and after

Before (0.40.0 on GHCR): arm64 615 MB, amd64 761 MB compressed; `lado:local` arm64
2.43 GB on disk. CI run 39008559275: the step "Image" 46 s (arm64), 58 s (amd64); the
container jobs 4 min 10 s and 4 min 54 s. Expected after: mise +52-59 MB compressed
(~145 MB on disk); `make gcc g++ libc6-dev` +250 MB on disk (Debian's apt: 198 MB for
`make gcc libc6-dev`, 52 MB more for `g++`), ~75 MB compressed; so ~745 MB arm64,
~890 MB amd64 compressed, ~2.85 GB on disk; the step "Image" +10-20 s. The developer
measures both after the build (`docker image inspect`, the CI run's step times) and
puts the numbers in the pull request; well beyond these (the image over 1 GB compressed,
the container job over CI's 40 min ceiling) goes to the supervisor.

### D8. The build tools in the first apt layer

`make gcc g++ libc6-dev` join the first `apt-get install --no-install-recommends`, so the
lists are removed in the same layer.

### D9. Test layers

- Unit (`tests/test_docker.py`): the mise stage pinned by digest; mise copied before
  `USER lado`; the apt packages; `docker/mise.toml`'s enabled tools and its copy to
  `/etc/mise/config.toml`; the build context's allowlist names it; `profile.sh`'s exports
  against `ENV` (the PATH order, `NPM_CONFIG_PREFIX`, `MISE_TRUSTED_CONFIG_PATHS` in the
  profile only), no `/opt` install variable in the runtime `ENV`.
- Unit (`tests/test_runtime.py`): the paragraph and the supervisor's or worker's sentence
  in `_spec`'s prompt with `LADO_CONTAINER=1`, none without; a flow run's worker gets the
  worker's. The text is one string for all providers, so one provider suffices here.
- Container (`tests/container/`, new `test_toolchains.py`): `mise --version` at the pin in
  a login shell; a C and a C++ file built by make; a project's `.tool-versions` with Go,
  `mise install`, `go build`, then the container removed and started again on the same
  volume, `go version` still there (one Go download, ~70 MB, per CI cell); two `mise install` of that Go at once, both succeeding (mise's lock: the human was told so); a `mise.toml`
  under `LADO_REPOS` installs without trust; Node 22 first with `mise use -g node@20`
  and `mise exec`; with the projects folder of uid 1001 (`projects_volume`), `npm
  install -g` of a local `npm pack` tarball and `uv tool install` of a local package (no
  index) in a login shell, files under `~/.local`, both commands found by a new login
  shell; the same on an `old_home` volume of 0.40.0's layout.
- No integration test: no new behaviour crosses processes; the prompt's way to each CLI
  is covered already.

### D10. Release

A minor bump: `## 0.41.0 (unreleased)` in CHANGELOG.md (or the section LAD-87 opens).
