# LADO's image: LADO from the one wheel of its build, the four agent CLIs at their pins,
# the UI server on 0.0.0.0:$LADO_PORT. The Release workflow publishes it for each release
# as ghcr.io/ladohq/lado:<version> (amd64, arm64); `make docker` builds it from a checkout
# (lado:local). One command starts it:
#
#   docker run -d --name lado -p 127.0.0.1:8765:8765 -v lado-home:/home/lado \
#     -v "$HOME/projects:$HOME/projects" -e LADO_REPOS="$HOME/projects" \
#     ghcr.io/ladohq/lado:<version>
#   docker exec lado lado ui --no-open            # the UI's link with its token
#
# Update: `docker rm -f lado`, then the same `docker run` with the new version; the home
# volume keeps LADO's state, and the new version upgrades its lado.db after a backup. Back:
# the same with the version before (putting lado.db's backup back: compose.yaml's header).
# A second LADO: another --name, home volume and port; updating one leaves the other.
#
# The projects are mounted at the host's own path and named by LADO_REPOS, so a worker's
# worktree made here is one on the host too; on Linux the container's user takes the
# folder owner's uid. The command runs as lado also with `docker run --user root`; root in
# a running container: `docker exec -u 0`. Another port: -e LADO_PORT=8766 -p
# 127.0.0.1:8766:8766. compose.yaml runs the same image. The build context is the
# repository through Dockerfile.dockerignore's allowlist: one wheel (dist/), profile.sh and
# entrypoint.sh.

FROM ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 AS uv
FROM node:25-bookworm-slim@sha256:81db02c4b671288a03915da9534dbd54f96d0e7c24d80ccc54f5b36b2e684370 AS node
FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587

# tmux 3.3a and git 2.39 from Debian 12; tini reaps what tmux and the agents leave; gh and
# the ssh client for the agents' pushes; curl fetches gh's keyring (a binary .gpg).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git tmux tini procps less openssh-client locales sudo \
 && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

# Node 22 and npm from the official image, no NodeSource script: npm installs the agent CLIs,
# and the agents and kits' MCP servers run node and npx.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# The user lado (uid 1000, as the prototype). Programs live under /opt, outside the home
# volume, so a new image replaces them; the home volume keeps only state (LADO_HOME,
# Claude Code's login). /projects is LADO_REPOS, the human's projects.
COPY --from=uv /uv /usr/local/bin/uv
COPY docker/profile.sh /etc/profile.d/lado.sh
RUN useradd --create-home --uid 1000 --shell /bin/bash lado \
 && mkdir -p /opt/uv /opt/agents /projects \
 && chown lado:lado /opt/uv /opt/agents /projects

# The entrypoint (entrypoint.sh) gives lado the uid of the projects' owner at a container's
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
# git trusts every repository: the projects' owner may seem another user (git 2.39 has no
# `<path>/*` form, and the container has one user).
RUN git config --system --add safe.directory '*'

USER lado
WORKDIR /home/lado
ENV UV_TOOL_DIR=/opt/uv/tools \
    UV_TOOL_BIN_DIR=/opt/uv/bin \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    NPM_CONFIG_PREFIX=/opt/agents

# Installed as lado: a chown afterwards would copy the layer.
COPY --chown=lado:lado dist/lado-*.whl /tmp/wheel/
RUN uv tool install --python 3.13 /tmp/wheel/lado-*.whl \
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

ENV PATH=/opt/uv/bin:/opt/agents/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    SHELL=/bin/bash \
    LANG=en_US.UTF-8 \
    LADO_CONTAINER=1 \
    LADO_REPOS=/projects \
    CLAUDE_CONFIG_DIR=/home/lado/.claude \
    DISABLE_AUTOUPDATER=1 \
    LADO_PORT=8765

EXPOSE 8765
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/lado-entrypoint"]
CMD ["sh", "-c", "exec lado server --host 0.0.0.0 --port \"$LADO_PORT\""]
