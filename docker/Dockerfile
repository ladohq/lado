# LADO's image: LADO from the one wheel of its build, the four agent CLIs at their pins,
# the UI server on 0.0.0.0:$LADO_PORT. The Release workflow publishes it for each release
# as ghcr.io/ladohq/lado:<version> (amd64, arm64); `make docker` builds it from a checkout
# (lado:local). The guide, step by step: docs/install.md#docker. One command starts it:
#
#   docker run -d --name lado -p 127.0.0.1:8765:8765 -v lado-home:/home/lado \
#     -v "$HOME/workspace:$HOME/workspace" -e LADO_REPOS="$HOME/workspace" \
#     -e LADO_GIT_NAME="Ann Lee" -e LADO_GIT_EMAIL=ann@example.com \
#     ghcr.io/ladohq/lado:<version>
#   docker exec lado lado ui --no-open            # the UI's link with its token
#
# The agents' variables, optional, are files in a folder, one per variable (its name the
# file's, its value the content): `mkdir -m 700 secrets`, then add
# `-v "$PWD/secrets:/run/secrets:ro"` to the `docker run`. Without it there are none and
# LADO says nothing about it. They are read at each agent's start and never in `docker
# inspect`: GH_TOKEN
# (git over https to github.com and gh; or `docker exec -it lado gh auth login`),
# CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`; or log in once with `docker exec -it
# lado claude`), a kit's key, a model provider's key for OpenCode and Kilo (or `opencode
# auth login` / `kilo auth login` inside). Logins made inside stay on the home volume;
# Codex's is not covered yet. Every agent of the container can read every variable given
# to it; another LADO keeps its own folder. LADO_GIT_NAME and LADO_GIT_EMAIL are git's
# identity for the agents' commits, written at every start (without them `docker logs`
# warns). The host's ssh agent, for git over ssh: on a Mac add
# `-v /run/host-services/ssh-auth.sock:/run/lado/ssh-agent.sock` (Docker Desktop's), on
# Linux `-v "$SSH_AUTH_SOCK:/run/lado/ssh-agent.sock"`; every agent may then use the
# host's keys. compose.yaml names it LADO_SSH_AGENT.
#
# Update: `docker rm -f lado`, then the same `docker run` with the new version; the home
# volume keeps LADO's state, and the new version upgrades its lado.db after a backup. Back:
# the same with the version before (putting lado.db's backup back: compose.yaml's header).
# A second LADO: another --name, home volume and port; updating one leaves the other.
# Sessions: `docker stop` stops the container's sessions, as `lado stop` would, and `docker
# start` (or a new container on the same home volume) resumes them; sessions stopped by
# hand stay stopped. Each resumed session's supervisor takes one model turn at the start.
#
# The workspace is mounted at the host's own path and named by LADO_REPOS, so a worker's
# worktree made here is one on the host too; on Linux the container's user takes the
# folder owner's uid. The command runs as lado also with `docker run --user root`; root in
# a running container: `docker exec -u 0`. Another port: -e LADO_PORT=8766 -p
# 127.0.0.1:8766:8766. compose.yaml runs the same image. The build context is the
# repository through Dockerfile.dockerignore's allowlist: one wheel (dist/), profile.sh,
# entrypoint.sh, ssh-agent-socket.sh, ssh-agent-env.sh, ssh_known_hosts (GitHub's
# public host keys, the only keys in the image) and mise.toml.
#
# The projects' toolchains: make, gcc and g++ are here, and mise installs the rest (Go,
# Rust, Java, a Python, ...) into the home volume, where it stays for every agent after a
# new container or image; the agents are told so and do it themselves. By hand: `docker
# exec lado mise use -g go@1.23`. An agent's `npm install -g` and `uv tool install` go to
# ~/.local on the home volume too; the image's Node 22 stays first on PATH. The agents' base
# tools are here too (jq, rg, unzip, zip, xz, bzip2, patch, file, rsync, sqlite3, tree, lsof,
# nc), and openspec at its pin, its usage statistics and update check off. python3 and
# python are the image's Python 3.13, root's, unless a project's version file or `mise use
# -g` names another. The system libraries of Playwright's Chromium are here, for the UI
# tests; the browser itself comes from `make browser`, into the home volume. Other apt
# packages and databases are not covered.

FROM ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv
FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS node
FROM jdxcode/mise:2026.10.7@sha256:66d03744d53f7da73eb3065b166151d48314c652985bdc420881376a4458aa67 AS mise
FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587

# tmux 3.3a and git 2.39 from Debian 12; tini reaps what tmux and the agents leave; gh and
# the ssh client for the agents' pushes; curl fetches gh's keyring (a binary .gpg); make,
# gcc and g++ build the projects' Makefiles, Go's cgo and native modules of Node and Python.
# The agents' base tools, which the kits' scripts and the agent CLIs call before any project
# installs a thing: jq (JSON), ripgrep (Codex, OpenCode and Kilo search with rg), archives
# (unzip, zip, xz, bzip2), patch, file, rsync, sqlite3, tree, lsof and nc.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git tmux tini procps less openssh-client locales sudo \
      make gcc g++ libc6-dev \
      jq ripgrep unzip zip xz-utils bzip2 patch file rsync sqlite3 tree lsof netcat-openbsd \
 && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

# The system libraries of Playwright's Chromium, for the UI tests (`make test-ui`): the
# packages `playwright install-deps chromium` installs on Debian 12 (Playwright's `chromium`
# list), in a layer of their own. No fonts and no xvfb (the tests run headless, the UI's
# fonts come with its bundle); the browser itself is not here: `make browser` installs it
# into ~/.cache/ms-playwright on the home volume, at the project's own Playwright version.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcairo2 libcups2 \
      libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 libnspr4 libnss3 libpango-1.0-0 libx11-6 \
      libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
 && rm -rf /var/lib/apt/lists/*

# Node 22 and npm from the official image, no NodeSource script: npm installs the agent CLIs,
# and the agents and kits' MCP servers run node and npx.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# The user lado (uid 1000, as the prototype). Programs live under /opt, outside the home
# volume, so a new image replaces them; the home volume keeps state (LADO_HOME, Claude
# Code's login) and what the agents install (mise's tools, npm -g, uv tool). /projects is
# LADO_REPOS, the human's workspace.
COPY --from=uv /uv /usr/local/bin/uv
COPY docker/profile.sh /etc/profile.d/lado.sh
# mise, root's so no agent replaces it, with the image's settings (docker/mise.toml); the
# toolchains it installs, its config and cache stay at its defaults on the home volume.
COPY --from=mise /usr/local/bin/mise /usr/local/bin/mise
COPY docker/mise.toml /etc/mise/config.toml
RUN useradd --create-home --uid 1000 --shell /bin/bash lado \
 && mkdir -p /opt/uv/tools /opt/uv/bin /opt/agents /opt/tools /projects \
 && chown lado:lado /opt/uv/tools /opt/uv/bin /opt/agents /opt/tools /projects
# The Python LADO runs on (uv's 3.13), root's, /opt/uv with it: it answers every agent's
# python3, so no agent may change it (pip refuses it too, externally managed). No uv bin
# links (root's ~/.local/bin): python3 and python are links in /opt/fallback/bin, last on
# PATH, after mise's shims, so a project's Python through mise answers first.
RUN UV_PYTHON_INSTALL_DIR=/opt/uv/python uv python install 3.13 --no-bin \
 && rm -rf /root/.cache \
 && python=$(ls -d /opt/uv/python/cpython-3.13.*-linux-*-gnu/bin/python3.13) \
 && mkdir -p /opt/fallback/bin \
 && ln -s "$python" /opt/fallback/bin/python3 \
 && ln -s "$python" /opt/fallback/bin/python \
 && /opt/fallback/bin/python3 --version

# The entrypoint (entrypoint.sh) gives lado the uid of the workspace's owner at a container's
# first start, as root once, and writes LADO_REPOS for the agents (lado-repos.sh, /projects
# until then and where the container may not become root).
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/lado-entrypoint
# Its way to root: a sudo rule for it alone, and the marker of a first start; that run
# deletes both before anything else. Where the entrypoint is replaced the rule stays, and
# that run takes no program from its caller's environment, so the rule does only its work.
RUN printf '%s\n' 'lado ALL=(root) NOPASSWD:SETENV: /usr/local/bin/lado-entrypoint' > /etc/sudoers.d/lado-entrypoint \
 && chmod 0440 /etc/sudoers.d/lado-entrypoint \
 && visudo -cf /etc/sudoers.d/lado-entrypoint \
 && mkdir -p /etc/lado && touch /etc/lado/first-start \
 && printf "export LADO_REPOS='/projects'\n" > /etc/profile.d/lado-repos.sh
# The host's ssh agent: compose binds its socket at /run/lado/ssh-agent.sock, in a folder
# root's so no agent plants a file there. Docker Desktop's socket is root's in the
# container; at every start the entrypoint gives it to lado by this program, through a rule
# of its own that the first start leaves (no SETENV: the program gets a clean environment).
COPY --chmod=755 docker/ssh-agent-socket.sh /usr/local/bin/lado-ssh-agent-socket
# SSH_AUTH_SOCK when that is a socket: every login shell reads it, the entrypoint sources it
# for the server (Clone from URL over ssh).
COPY docker/ssh-agent-env.sh /etc/profile.d/lado-ssh-agent.sh
RUN printf '%s\n' 'lado ALL=(root) NOPASSWD: /usr/local/bin/lado-ssh-agent-socket' > /etc/sudoers.d/lado-ssh-agent \
 && chmod 0440 /etc/sudoers.d/lado-ssh-agent \
 && visudo -cf /etc/sudoers.d/lado-ssh-agent \
 && mkdir -p /run/lado && chmod 755 /run/lado
# GitHub's public host keys, so an agent's first ssh to github.com asks nothing (its shell
# cannot answer) and ssh still refuses a key that is not GitHub's. The only keys in the
# image: the human's own come at run time.
COPY --chmod=644 docker/ssh_known_hosts /etc/ssh/ssh_known_hosts
# git trusts every repository: the workspace's owner may seem another user (git 2.39 has no
# `<path>/*` form, and the container has one user). It gets github.com's https credentials
# from gh: GH_TOKEN, or gh's own login on the home volume (what `gh auth setup-git` writes;
# the empty helper drops any helper set before it).
RUN git config --system --add safe.directory '*' \
 && git config --system credential.https://github.com.helper '' \
 && git config --system --add credential.https://github.com.helper '!/usr/bin/gh auth git-credential'

USER lado
WORKDIR /home/lado

# Installed as lado: a chown afterwards would copy the layer. /opt only here and in the
# CLIs' and openspec's installs below: at run time an install goes to the home volume
# (NPM_CONFIG_PREFIX, uv's defaults under ~/.local).
COPY --chown=lado:lado dist/lado-*.whl /tmp/wheel/
RUN UV_TOOL_DIR=/opt/uv/tools UV_TOOL_BIN_DIR=/opt/uv/bin UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    uv tool install --python 3.13 /tmp/wheel/lado-*.whl \
 && rm -rf /tmp/wheel /home/lado/.cache

# The four agent CLIs at the versions LADO is tested with (scripts/smoke_ci.py's PINS;
# tests/test_docker.py keeps them the same), one layer each, so a moved pin rebuilds one.
# Each package puts its native binary in place for its architecture. Claude Code's update
# check is off (DISABLE_AUTOUPDATER); LADO switches the others' off per agent. Codex CLI
# is only installed: carrying its login into the agents is a later step.
ARG CLAUDE_VERSION=2.1.295
RUN npm install -g --prefix /opt/agents "@anthropic-ai/claude-code@${CLAUDE_VERSION}" \
 && npm cache clean --force
ARG CODEX_VERSION=0.162.0
RUN npm install -g --prefix /opt/agents "@openai/codex@${CODEX_VERSION}" \
 && npm cache clean --force
ARG OPENCODE_VERSION=1.18.35
RUN npm install -g --prefix /opt/agents "opencode-ai@${OPENCODE_VERSION}" \
 && npm cache clean --force
ARG KILO_VERSION=7.8.8
RUN npm install -g --prefix /opt/agents "@kilocode/cli@${KILO_VERSION}" \
 && npm cache clean --force

# openspec, which kits expect (sdlc's `expects.commands`), at its pin in /opt/tools: no
# agent CLI, so not in /opt/agents. Before mise's shims on PATH, so an openspec of the home
# volume does not shadow it. Dependabot does not read it: move the pin by hand. Its usage
# statistics and update check are off (OPENSPEC_TELEMETRY, OPENSPEC_NO_UPDATE_CHECK).
ARG OPENSPEC_VERSION=1.14.1
RUN npm install -g --prefix /opt/tools "@fission-ai/openspec@${OPENSPEC_VERSION}" \
 && npm cache clean --force

ENV PATH=/opt/uv/bin:/opt/agents/bin:/opt/tools/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/lado/.local/bin:/home/lado/.local/share/mise/shims:/opt/fallback/bin \
    NPM_CONFIG_PREFIX=/home/lado/.local \
    SHELL=/bin/bash \
    LANG=en_US.UTF-8 \
    LADO_CONTAINER=1 \
    LADO_REPOS=/projects \
    LADO_ENV_DIR=/run/secrets \
    CLAUDE_CONFIG_DIR=/home/lado/.claude \
    DISABLE_AUTOUPDATER=1 \
    OPENSPEC_TELEMETRY=0 \
    OPENSPEC_NO_UPDATE_CHECK=1 \
    LADO_PORT=8765

EXPOSE 8765
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/lado-entrypoint"]
CMD ["sh", "-c", "exec lado server --host 0.0.0.0 --port \"$LADO_PORT\""]
