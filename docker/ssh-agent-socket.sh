#!/bin/sh
# LADO's image: gives the host's ssh agent socket at its one fixed path to lado while it is
# root's there (Docker Desktop's is, and is again after Docker Desktop restarts). Run as
# root through a sudo rule of its own, without SETENV (sudo's env_reset), by the
# entrypoint at every start. It takes no argument and changes only that socket's owner,
# keeping its group, so an agent that runs it gains nothing SSH_AUTH_SOCK does not give it
# already.
set -eu
PATH=/usr/bin:/bin
SOCKET=/run/lado/ssh-agent.sock
if [ "$#" -ne 0 ]; then
    echo "lado-ssh-agent-socket: takes no argument" >&2
    exit 2
fi
if [ -L "$SOCKET" ] || [ ! -S "$SOCKET" ]; then
    echo "lado-ssh-agent-socket: $SOCKET is not a socket" >&2
    exit 1
fi
[ "$(stat -c %u "$SOCKET")" = 0 ] || exit 0
chown --no-dereference "$(id -u lado)" "$SOCKET"
