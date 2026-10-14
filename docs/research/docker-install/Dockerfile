# LAD-52 prototype: LADO and the four agent CLIs in one image.
# Evidence for docs/research/docker-install.md, not a shipped artifact: no build or CI
# picks this file up.
#
#   docker compose -f docs/research/docker-install/compose.yaml up -d --build
#   docker exec lado lado ui --no-open            # the UI's link with its token

FROM debian:bookworm-slim

ARG LADO_VERSION=0.37.0
# The agent CLIs at the versions LADO is tested with (scripts/smoke_ci.py, PINS).
ARG CLAUDE_VERSION=2.1.295
ARG CODEX_VERSION=0.162.0
ARG OPENCODE_VERSION=1.18.35
ARG KILO_VERSION=7.8.8
ARG NODE_MAJOR=22

# tmux 3.3a and git 2.39 from Debian 12; tini reaps the processes tmux and the agents
# leave; openssh-client and gh for pushing from inside.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git tmux tini procps less openssh-client gnupg locales \
 && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen \
 && curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

# The agents' PATH comes from the user's login shell (agent_env.resolve runs
# `$SHELL -ilc`), and Debian's /etc/profile sets PATH anew: add LADO's folders there.
# Claude Code keeps .claude.json in CLAUDE_CONFIG_DIR when it is set, so its whole
# login is in one folder of the home volume; its self-update is off.
RUN printf '%s\n' \
      'export PATH="/opt/uv/bin:/opt/agents/bin:$PATH"' \
      'export CLAUDE_CONFIG_DIR="$HOME/.claude"' \
      'export DISABLE_AUTOUPDATER=1' \
      'export LANG=en_US.UTF-8' \
      > /etc/profile.d/lado.sh \
 && useradd --create-home --uid 1000 --shell /bin/bash lado \
 && mkdir -p /opt/uv /opt/agents && chown lado:lado /opt/uv /opt/agents

# Programs live under /opt, outside the home volume, so a new image replaces them;
# the home volume keeps only state (LADO_HOME, the CLIs' logins and configs).
# Installed as lado: a chown afterwards would copy the layer.
USER lado
WORKDIR /home/lado
ENV UV_INSTALL_DIR=/opt/uv/bin \
    UV_TOOL_DIR=/opt/uv/tools \
    UV_TOOL_BIN_DIR=/opt/uv/bin \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    NPM_CONFIG_PREFIX=/opt/agents
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh \
 && /opt/uv/bin/uv tool install "lado==${LADO_VERSION}" \
 && npm install -g --prefix /opt/agents \
      "@anthropic-ai/claude-code@${CLAUDE_VERSION}" \
      "@openai/codex@${CODEX_VERSION}" \
      "opencode-ai@${OPENCODE_VERSION}" \
      "@kilocode/cli@${KILO_VERSION}" \
 && npm cache clean --force
ENV PATH=/opt/uv/bin:/opt/agents/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    SHELL=/bin/bash \
    LANG=en_US.UTF-8 \
    CLAUDE_CONFIG_DIR=/home/lado/.claude \
    DISABLE_AUTOUPDATER=1

EXPOSE 8765
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["lado", "server", "--host", "0.0.0.0", "--port", "8765"]
