#!/bin/sh
# LADO's image: between tini and the command (the UI server). Three phases, by who runs it:
#
# 1. lado at a container's first start (the marker is there): reruns itself as root through
#    the sudo rule for this script alone.
# 2. root: deletes that rule and the marker before anything else, so no process started
#    later, an agent included, can become root through them; gives lado the uid and gid of
#    LADO_REPOS's owner (not uid 0: Docker Desktop shows a bind mount so; not gid 0, root's
#    group), gives lado its home volume, writes LADO_REPOS for the agents' login shells,
#    and drops back to lado. Where the entrypoint was replaced, the rule stays: this phase
#    runs nothing by its caller's PATH, so the rule still runs only this script's steps.
# 3. lado with no marker (after phase 2, or a restart, which keeps the uid taken): warns in
#    `docker logs` about a LADO_REPOS that is not mounted or not writable, then runs the
#    command.
set -eu
SELF=/usr/local/bin/lado-entrypoint
RULE=/etc/sudoers.d/lado-entrypoint
MARK=/etc/lado/first-start

if [ "$(id -u)" = 0 ]; then
    PATH=/usr/sbin:/usr/bin:/sbin:/bin
    rm -f "$RULE" "$MARK"
    # The rule stays in a container whose entrypoint was replaced, and SETENV lets its
    # caller set any variable: nothing here runs by the caller's PATH, which comes back
    # only after the drop to lado.
    saved=${LADO_ENTRYPOINT_PATH:-$PATH}
    repos=${LADO_REPOS:-/projects}
    if [ -d "$repos" ]; then
        owner=$(stat -c '%u %g' "$repos")
        uid=${owner% *}
        gid=${owner#* }
        if [ "$uid" != 0 ]; then
            # -o: the host's ids may be taken in the image already (gid 100 is users). A
            # group 0 is root's: lado keeps its own.
            if [ "$gid" != 0 ] && [ "$gid" != "$(id -g lado)" ]; then
                groupmod -o -g "$gid" lado
                usermod -g "$gid" lado
            fi
            if [ "$uid" != "$(id -u lado)" ]; then
                usermod -o -u "$uid" lado
            fi
        fi
    fi
    # usermod moves only the files the old uid owned: a home volume of an earlier container
    # with another uid follows only so.
    if [ -n "$(find /home/lado \( ! -user lado -o ! -group lado \) -print -quit)" ]; then
        chown -R lado:lado /home/lado
    fi
    # The agents' environment comes from the login shell, not the container's.
    quoted=$(printf '%s' "$repos" | sed "s/'/'\\\\''/g")
    printf "export LADO_REPOS='%s'\n" "$quoted" >/etc/profile.d/lado-repos.sh
    chmod 644 /etc/profile.d/lado-repos.sh
    # sudo replaced PATH by its secure_path and set its own variables.
    unset LADO_ENTRYPOINT_PATH SUDO_COMMAND SUDO_USER SUDO_UID SUDO_GID
    export HOME=/home/lado USER=lado LOGNAME=lado
    exec /usr/bin/setpriv --reuid=lado --regid=lado --init-groups -- /usr/bin/env PATH="$saved" "$SELF" "$@"
fi

if [ -e "$MARK" ] && [ "$(id -un 2>/dev/null)" = lado ]; then
    export LADO_ENTRYPOINT_PATH="$PATH"
    exec sudo -E -n "$SELF" "$@"
fi

repos=${LADO_REPOS:-/projects}
case $repos in
/*)
    if [ ! -d "$repos" ]; then
        echo "lado: warning: LADO_REPOS is not a folder in the container: $repos; mount the host's folder at this same path" >&2
    elif probe=$(mktemp "$repos/.lado-write-check.XXXXXX" 2>/dev/null); then
        rm -f "$probe"
    else
        echo "lado: warning: LADO may not write in LADO_REPOS $repos" >&2
    fi
    ;;
esac
exec "$@"
