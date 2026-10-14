## Context

LAD-52's prototype (`docs/research/docker-install/Dockerfile`, `compose.yaml`) proved the
image by hand on a Mac (H1-H9): Debian bookworm-slim, Node from NodeSource's
`curl | bash`, uv from its `curl | sh`, `uv tool install lado==0.37.0` from PyPI, four agent
CLIs from npm, `/etc/profile.d/lado.sh` for the agents' `PATH`, tini, `lado server --host
0.0.0.0 --port 8765`, a compose file with a fixed container name `lado`, the ssh agent's
Docker Desktop socket and `group_add: ["0"]`. LAD-59 gave LADO `LADO_CONTAINER`, LAD-63 the
container note, `lado ui`'s host link and `LADO_REPOS`. CI (`.github/workflows/ci.yml`) has
no Docker step; `ci-ok` (`scripts/ci_ok.py`) needs every other job; the smoke's skip list
is guarded by `tests/test_ci_workflow.py`. The smoke tests (`tests/smoke/`) run a real CLI
against `Endpoint`, a stdlib 401 server in `tests/smoke/conftest.py`.

Root cause of the task: the image is a hand-made artifact outside every build and test, so
nothing ties it to the code it packages.

Options weighed for where the image's LADO comes from (the human chose 3, 2026-10-15):
1. PyPI by version (the prototype): CI would test the last release, not the pull request;
   a change that breaks LADO in a container shows only at a release. Cost: the very gap
   the task closes.
2. The source tree, built inside the Dockerfile (a Node and a uv stage): CI tests the pull
   request, but a release image is built from source a second time beside the wheel PyPI
   gets; two artifacts of one version that can differ (a build tool's update in between).
3. The wheel given to the build (chosen): one install path; CI gives the pull request's
   wheel, the release (T7) the wheel it uploads to PyPI, already kept as the artifact
   `dist`. Cost: a build needs the wheel first (`make docker` does both).

Options for how a user starts it (the human chose 3): compose only (two steps: a file and
`up`), `docker run` only (one command; an update repeats every flag), or an image whose
defaults are all inside, run by one `docker run`, with an optional compose file beside it
(chosen; which one the documentation leads with is T7/T8's).

Claude Code 2.1.295's npm package (read in its tarballs, 2026-10-15) is a wrapper of a
native binary: `bin/claude.exe` is a stub that its postinstall (`install.cjs`, run by Node)
replaces with the ELF binary of a per-platform package (`@anthropic-ai/claude-code-linux-x64`,
`-linux-arm64`, ...; `engines: node >=22`). Node runs the install only; the CLI's process is
the binary itself.

Against ROADMAP.md and AGENTS.md: no code under `src/` changes, so the neutral core is
untouched; the image carries one provider by the human's decision (plan, section 0), and
the layer's test is Claude Code's only, said in the spec; one source of truth for the CLI's
version (`PINS`, kept by a test) and for the port (`LADO_PORT`); nothing is dropped
silently: a container cell that skips fails.

## Decisions

- **D1. Files.** `docker/Dockerfile`, `docker/Dockerfile.dockerignore` (its build
  context's allowlist, D2), `docker/profile.sh` (copied to `/etc/profile.d/lado.sh`; a file
  of its own so it is read and reviewed as a file, not a `printf` chain),
  `docker/compose.yaml`. The research's prototype stays where it is, as evidence; nothing
  links the two.
- **D2. Build context: the repository, through an allowlist.** `docker build -f
  docker/Dockerfile -t lado:local .`; `docker/Dockerfile.dockerignore` (BuildKit reads the
  ignore file beside its Dockerfile) is `*`, `!dist/lado-*.whl`, `!docker/profile.sh`, so
  the daemon gets one wheel and one script, never `.lado/`, `.venv/` or `node_modules/`.
  The Dockerfile `COPY dist/lado-*.whl /tmp/wheel/` and installs it with `uv tool install
  --python 3.13 /tmp/wheel/lado-*.whl`, then removes it and uv's cache. `make docker`:
  `cd web && npm ci --no-audit --no-fund && npm run build`, `rm -rf dist && uv build
  --wheel` (one wheel, the bundle in it), then that `docker build`; not `make dist`, whose
  `make web` repeats the ui job's checks.
- **D3. Base `debian:bookworm-slim`, Node 22 from the official image, user `lado` made
  anew.** All pinned `@sha256:`. Debian 12 as the prototype (tmux 3.3a, git 2.39). Node 22
  and npm stay in the image for the agents and for kits' MCP servers run by `npx` (the
  human's decision, 2026-10-15): `COPY --from=node:22-bookworm-slim@sha256:...
  /usr/local/bin/node /usr/local/bin/node` and `/usr/local/lib/node_modules/npm`, then
  `ln -s` of `npm` and `npx` (`../lib/node_modules/npm/bin/npm-cli.js`, `npx-cli.js`) in
  `/usr/local/bin`; no NodeSource script, and no `node` user, as Debian's base has none:
  `useradd --create-home --uid 1000 --shell /bin/bash lado`, the prototype's way and uid.
  uv comes from `COPY --from=ghcr.io/astral-sh/uv:<version>@sha256:... /uv
  /usr/local/bin/uv`, its documented way, no `curl | sh`. LADO's Python is uv's 3.13 under
  `/opt/uv/python`. gh comes from GitHub's apt repository with its signed keyring, as the
  prototype; apt packages: `ca-certificates curl git tmux tini procps less openssh-client
  locales gh` (curl fetches the keyring, a binary `.gpg`, so no gnupg; it stays for the
  agents).
- **D4. Programs under `/opt`, state in the home volume.** As the prototype: LADO in
  `/opt/uv/tools` with its command in `/opt/uv/bin`, Claude Code with `npm install -g
  --prefix /opt/agents @anthropic-ai/claude-code@${CLAUDE_VERSION}` and `npm cache clean
  --force`; installed as `lado` so no `chown` copies a layer. `ARG
  CLAUDE_VERSION=<PINS["claude"]>`; no other CLI.
- **D5. Environment in two places, the same values.** `ENV` (for the server and `docker
  exec`) and `docker/profile.sh` (for login shells, so the agents) both set
  `PATH=/opt/uv/bin:/opt/agents/bin:$PATH`, `LADO_CONTAINER=1`, `LADO_REPOS=/projects`,
  `CLAUDE_CONFIG_DIR=$HOME/.claude`, `DISABLE_AUTOUPDATER=1`, `LANG=en_US.UTF-8`; `ENV`
  also `SHELL=/bin/bash` and `LADO_PORT=8765`. `LADO_PORT` is not in profile.sh: only the
  server reads it. A unit test checks that each variable profile.sh exports is in the
  Dockerfile's `ENV` with the same value (`$HOME` read as `/home/lado`), so the two cannot
  drift.
- **D6. The server's command.** `ENTRYPOINT ["/usr/bin/tini", "--"]`, `CMD ["sh", "-c",
  "exec lado server --host 0.0.0.0 --port \"$LADO_PORT\""]`, `EXPOSE 8765`, `USER lado`,
  `WORKDIR /home/lado`; `/projects` made and owned by `lado`. `lado server` takes no port
  from the environment, so the shell reads it; `exec` keeps tini's child the server.
- **D7. compose.yaml.** Service `lado`: `image: ${LADO_IMAGE:-lado:local}` (T7 changes the
  default to the published one), no `build:` (the build needs the wheel: `make docker`),
  no `container_name`, `hostname: lado`, `environment: LADO_PORT: ${LADO_PORT:-8765}`,
  `ports: ["127.0.0.1:${LADO_PORT:-8765}:${LADO_PORT:-8765}"]`, volumes `home:/home/lado`
  and `${LADO_PROJECTS:?set LADO_PROJECTS to your projects folder}:/projects`,
  `extra_hosts: ["host.docker.internal:host-gateway"]` (a local model on a Linux host,
  research H5; Docker Desktop has it), `restart: unless-stopped`. Its header comment gives
  the first start, the link, and a second LADO with `-p`.
- **D8. The container test layer.** Marker `container`, left out of the default run
  (`addopts`), `tests/container/`, `make test-container` (`uv run pytest -m container -n0
  -v`; serial: containers and ports). The image is `LADO_TEST_IMAGE` or `lado:local`; the
  tests skip when `docker` does not run or the image is missing (CI's pass rule makes a skip
  red). Each test names its containers, volumes and compose project `lado-test-<random>`,
  takes a free port, runs with `-e LADO_TELEMETRY=0 -e LADO_NO_UPDATE_CHECK=1`, and removes
  everything after itself (`docker rm -f`, `docker volume rm`, `docker compose down -v`),
  also on a failure. A failed test keeps `docker logs`, `lado log`, `hooks.log` and
  `loop.log` of the container in `real_clis.EVIDENCE`'s folder, as a smoke test does.
- **D9. The fake endpoint runs in the container.** `Endpoint` moves from
  `tests/smoke/conftest.py` to `tests/fake_endpoint.py` (stdlib only), which also runs as a
  script, `python fake_endpoint.py <port> <log file>` (one JSON line per request). The test
  copies it into the container (`docker cp`) and starts it with the image's Python
  (`/opt/uv/tools/lado/bin/python`) on `127.0.0.1` inside: no host address, no
  `host-gateway`, the same on a Mac and on Linux. Claude Code is pointed at it as in the
  smoke, but through the login shell, as a human would: the test appends `export
  ANTHROPIC_BASE_URL=... ANTHROPIC_AUTH_TOKEN=... CLAUDE_CODE_MAX_RETRIES=0
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` to `/home/lado/.profile` and writes
  `$CLAUDE_CONFIG_DIR/.claude.json` (onboarding done, bypass permissions accepted, the
  repository trusted).
- **D10. The session and the agent's environment.** The repository is
  `/home/lado/repo` in the home volume (one commit), so the projects mount and the uid
  (T5) do not matter. `docker exec <c> lado start /home/lado/repo --name smoke --provider
  claude --permission-mode bypassPermissions --no-attach`; the supervisor's status is read
  with the image's Python (`state.get_agent("smoke", "supervisor").status`) until `idle`
  (120 s). The agent's process is the supervisor window's pane process (`tmux -L lado
  display-message -p -t smoke:supervisor '#{pane_pid}'`): `lado.agent_env` execs the CLI in
  place, and Claude Code 2.x is a native binary, not a Node script (Context). The test
  asserts it: `readlink /proc/<pid>/exe` must be the file `readlink -f "$(command -v
  claude)"` names, else it fails naming both; no search for a likely process. `lado doctor` then runs with exactly its environment, `xargs -0 sh -c 'exec env
  -i "$@" lado doctor' _ < /proc/<pid>/environ`, and its LADO line must end with `in a
  container`; the environment must hold `LADO_CONTAINER=1`. Then `lado stop --all`.
- **D11. CI job `container`.** Matrix `arch: [amd64, arm64]` with `runner: ubuntu-24.04` /
  `ubuntu-24.04-arm`, name `container (<arch>)`, `timeout-minutes: 30`, no `needs`, no
  `if`: checkout, setup-uv (3.13), setup-node (lts), `make docker`, then `uv run python
  scripts/smoke_ci.py container "$RUNNER_TEMP/container"`, then upload that folder always
  (`container-<arch>`, 5 days). `smoke_ci.py container <out>` runs `uv run pytest -m
  container -n0 -v` into `<out>/container.log` with `run`'s pass rule and evidence copy
  (the two share one function). `ci-ok`'s `needs` gains `container`; `ci_ok.py` does not
  change (it must succeed). No `docker login`, no `push`, no buildx action: the runners'
  Docker builds natively.
- **D12. Guards.** `tests/test_docker.py`: the Dockerfile's `ARG CLAUDE_VERSION` default is
  `PINS["claude"][1]`; every `FROM` and `COPY --from` names `@sha256:`; profile.sh agrees
  with `ENV` (D5); no `curl ... | sh` or `| bash`; compose's port line is
  `127.0.0.1:${LADO_PORT:-8765}:${LADO_PORT:-8765}` and its `LADO_PORT` the same default.
  `tests/test_ci_workflow.py`: the container job's runners, its command, no `if`, its
  upload, and `docker/` in `SMOKE_RUNS`. `.github/dependabot.yml` gains `docker` for
  `/docker`, weekly, 7 days' cooldown, minor and patch grouped.
- **D13. Docs.** AGENTS.md: Commands (`make docker`, `make test-container`), Layout
  (`docker/`), Testing (a seventh layer, Container), the CI paragraph (job `container`).
  CHANGELOG.md, 0.39.0: one line, the image built from a checkout and tested in CI, not
  published yet. No version bump of its own.

## Risks / Trade-offs

- The job adds two runners of ~10 minutes to every run, parallel to the others, so the
  wall time grows only if it is the slowest; a build cache (buildx with the GitHub cache)
  is the next step if it is.
- Debian 12 ships git 2.39, above `runtime.GIT_MIN` (2.31); tmux 3.3a gives the rounded
  popup border.
- `ubuntu-24.04-arm` is free for public repositories only; the repository is public.
- The agent's environment is read from `/proc`, Linux only: the image is Linux.
