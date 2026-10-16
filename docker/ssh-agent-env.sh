# LADO's image: the host's ssh agent, when compose bound one (LADO_SSH_AGENT; /dev/null is
# none). One rule for both who need it: every login shell reads it from /etc/profile.d (the
# agents' git over ssh), and the entrypoint sources it before the command (the UI server's
# clone and branch listing).
[ -S /run/lado/ssh-agent.sock ] && export SSH_AUTH_SOCK=/run/lado/ssh-agent.sock || true
