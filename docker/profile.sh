# LADO's image: what every login shell gets, so every agent (agent_env.resolve takes an
# agent's environment from `$SHELL -ilc`, not from the image's ENV). The Dockerfile's ENV
# sets the same for the server and `docker exec`; tests/test_docker.py keeps them the same.
# LADO_REPOS is the container's own (-e), so the entrypoint writes it to lado-repos.sh.
export PATH="/opt/uv/bin:/opt/agents/bin:$PATH"
export LADO_CONTAINER=1
export CLAUDE_CONFIG_DIR="$HOME/.claude"
export DISABLE_AUTOUPDATER=1
export LANG=en_US.UTF-8
# The agents' variables, one file each (a worker the supervisor's `lado mcp` spawns too).
export LADO_ENV_DIR=/run/secrets
# The host's ssh agent, when compose bound one (LADO_SSH_AGENT; /dev/null is none). Only
# here: the server needs none.
[ -S /run/lado/ssh-agent.sock ] && export SSH_AUTH_SOCK=/run/lado/ssh-agent.sock || true
