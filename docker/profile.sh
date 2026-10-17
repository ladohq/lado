# LADO's image: what every login shell gets, so every agent (agent_env.resolve takes an
# agent's environment from `$SHELL -ilc`, not from the image's ENV). The Dockerfile's ENV
# sets the same for the server and `docker exec`; tests/test_docker.py keeps them the same.
# LADO_REPOS is the container's own (-e), so the entrypoint writes it to lado-repos.sh.
# The image's programs first, so no mise shim shadows its Node 22; then the agents' own
# installs (npm -g, uv tool) and mise's shims, both on the home volume.
export PATH="/opt/uv/bin:/opt/agents/bin:$PATH:$HOME/.local/bin:$HOME/.local/share/mise/shims"
# `npm i -g` into ~/.local: /usr/local is root's and /opt is the image's.
export NPM_CONFIG_PREFIX="$HOME/.local"
# A project's mise.toml under the projects folder needs no `mise trust`. lado-repos.sh is
# read first by name, but a shell may sort the folder otherwise: read it here.
if [ -r /etc/profile.d/lado-repos.sh ]; then . /etc/profile.d/lado-repos.sh; fi
export MISE_TRUSTED_CONFIG_PATHS="$LADO_REPOS"
export LADO_CONTAINER=1
export CLAUDE_CONFIG_DIR="$HOME/.claude"
export DISABLE_AUTOUPDATER=1
export LANG=en_US.UTF-8
# The agents' variables, one file each (a worker the supervisor's `lado mcp` spawns too).
export LADO_ENV_DIR=/run/secrets
# The host's ssh agent: lado-ssh-agent.sh beside this file (docker/ssh-agent-env.sh), which
# the entrypoint sources for the server too.
