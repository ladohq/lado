#!/bin/sh
# LADO's image: between tini and the command (the UI server). Three phases, by who runs it:
#
# 1. lado at a container's first start (the marker is there): reruns itself as root through
#    the sudo rule for this script alone, when the container lets it become root and its
#    root file system is writable; else it warns and goes on as phase 3 with uid 1000
#    (no-new-privileges, `--cap-drop`, `--read-only`).
# 2. root: deletes that rule and the marker before anything else, so no process started
#    later, an agent included, can become root through them; gives lado the uid and gid of
#    LADO_REPOS's owner (not uid 0: Docker Desktop shows a bind mount so; not gid 0, root's
#    group), gives lado its home volume, writes LADO_REPOS for the agents' login shells,
#    and drops back to lado; a step of these that fails is a warning. Where the entrypoint
#    was replaced, the rule stays: this phase runs nothing by its caller's PATH, so the
#    rule still runs only this script's steps.
# 3. lado with no marker (after phase 2, or a restart, which keeps the uid taken): warns in
#    `docker logs` about a LADO_REPOS that is not mounted or not writable, then runs the
#    command.
set -eu
SELF=/usr/local/bin/lado-entrypoint
RULE=/etc/sudoers.d/lado-entrypoint
MARK=/etc/lado/first-start

# Give lado uid $1 and gid $2 (not 0, root's group: lado keeps its own). -o: the host's ids
# may be taken in the image already (gid 100 is users).
take_owner() {
    if [ "$2" != 0 ] && [ "$2" != "$(id -g lado)" ]; then
        groupmod -o -g "$2" lado && usermod -g "$2" lado || return 1
    fi
    if [ "$1" != "$(id -u lado)" ]; then
        usermod -o -u "$1" lado || return 1
    fi
}

# Whether sudo can make this process root: not under no-new-privileges, and with the
# capabilities the root phase uses in the bounding set (CHOWN, DAC_OVERRIDE, FOWNER,
# SETGID, SETUID), which `--cap-drop` takes away.
may_become_root() {
    status=$(cat /proc/self/status) || return 1
    case $status in *"NoNewPrivs:	1"*) return 1 ;; esac
    bounding=$(printf '%s\n' "$status" | sed -n 's/^CapBnd:[[:space:]]*//p')
    [ -n "$bounding" ] && [ $((0x$bounding & 0xcb)) = $((0xcb)) ]
}

# Whether / is mounted read-only (`--read-only`, Kubernetes' readOnlyRootFilesystem): the
# root step could write neither /etc/passwd nor the profile there.
read_only_root() {
    case $(awk '$5 == "/" { print $6 }' /proc/self/mountinfo) in
    ro | ro,*) return 0 ;;
    *) return 1 ;;
    esac
}

if [ "$(id -u)" = 0 ]; then
    PATH=/usr/sbin:/usr/bin:/sbin:/bin
    if ! rm -f "$RULE" "$MARK"; then
        echo "lado: warning: could not remove the sudo rule $RULE and the marker $MARK" >&2
    fi
    # A step here that fails is a warning, and the server starts as lado all the same: a
    # container that stopped here would only restart into the same failure. A rule left
    # behind is harmless, as below; a marker left behind brings this phase back next start.
    # The rule stays in a container whose entrypoint was replaced, and SETENV lets its
    # caller set any variable: nothing here runs by the caller's PATH, which comes back
    # only after the drop to lado.
    saved=${LADO_ENTRYPOINT_PATH:-$PATH}
    repos=${LADO_REPOS:-/projects}
    if [ -d "$repos" ]; then
        owner=$(stat -c '%u %g' "$repos")
        uid=${owner% *}
        gid=${owner#* }
        if [ "$uid" != 0 ] && ! take_owner "$uid" "$gid"; then
            echo "lado: warning: could not give lado the uid and gid of LADO_REPOS's owner ($uid:$gid): it keeps $(id -u lado):$(id -g lado)" >&2
        fi
    fi
    # usermod moves only the files the old uid owned: a home volume of an earlier container
    # with another uid follows only so.
    if [ -n "$(find /home/lado \( ! -user lado -o ! -group lado \) -print -quit)" ] &&
        ! chown -R lado:lado /home/lado; then
        echo "lado: warning: could not give lado everything under /home/lado" >&2
    fi
    # The agents' environment comes from the login shell, not the container's.
    quoted=$(printf '%s' "$repos" | sed "s/'/'\\\\''/g")
    if ! printf "export LADO_REPOS='%s'\n" "$quoted" >/etc/profile.d/lado-repos.sh; then
        echo "lado: warning: could not write LADO_REPOS for the agents: theirs stays /projects" >&2
    fi
    # sudo replaced PATH by its secure_path and set its own variables.
    unset LADO_ENTRYPOINT_PATH SUDO_COMMAND SUDO_USER SUDO_UID SUDO_GID
    export HOME=/home/lado USER=lado LOGNAME=lado
    exec /usr/bin/setpriv --reuid=lado --regid=lado --init-groups -- /usr/bin/env PATH="$saved" "$SELF" "$@"
fi

if [ -e "$MARK" ] && [ "$(id -un 2>/dev/null)" = lado ]; then
    # The image's /etc/profile.d/lado-repos.sh, which only root writes, keeps /projects.
    kept="lado keeps uid $(id -u) instead of the owner's of ${LADO_REPOS:-/projects}, and the agents' LADO_REPOS is /projects"
    if ! may_become_root; then
        echo "lado: warning: the container may not become root (no-new-privileges or dropped capabilities): $kept" >&2
    elif read_only_root; then
        echo "lado: warning: the container's root file system is read-only: $kept" >&2
    else
        export LADO_ENTRYPOINT_PATH="$PATH"
        exec sudo -E -n "$SELF" "$@"
    fi
fi

# git's identity for the agents' commits (LADO_GIT_NAME, LADO_GIT_EMAIL), in lado's global
# config on the home volume at every start: a container made again with a new .env takes
# the new values. Each value is one argument, never evaluated.
for key in name email; do
    if [ "$key" = name ]; then value=${LADO_GIT_NAME:-}; else value=${LADO_GIT_EMAIL:-}; fi
    if [ -n "$value" ] && ! git config --global "user.$key" "$value"; then
        echo "lado: warning: could not write git's user.$key" >&2
    fi
done
# Outside any repository, so only the global and system configs answer.
if [ -z "$(cd / && git config user.name)" ] || [ -z "$(cd / && git config user.email)" ]; then
    echo "lado: warning: git has no user.name or user.email: agents cannot commit; set LADO_GIT_NAME and LADO_GIT_EMAIL" >&2
fi

# The host's ssh agent (compose's LADO_SSH_AGENT): a socket of the projects' owner works as
# it is; Docker Desktop's is root's in the container, and its own sudo rule gives it to lado
# at every start, as Docker Desktop's restart makes it root's again. ssh-add exits 2 when it
# cannot connect (0 or 1: keys or none).
SOCK=/run/lado/ssh-agent.sock
ssh_status() { SSH_AUTH_SOCK=$SOCK ssh-add -l >/dev/null 2>&1 && echo 0 || echo $?; }
if [ -S "$SOCK" ] && [ "$(ssh_status)" = 2 ]; then
    owner=$(stat -c %u "$SOCK")
    reason="ssh-add cannot connect"
    if [ "$owner" = 0 ]; then
        if ! may_become_root; then
            reason="no root to give it to lado (no-new-privileges or dropped capabilities)"
        elif ! sudo -n /usr/local/bin/lado-ssh-agent-socket; then
            reason="lado-ssh-agent-socket failed"
        fi
    fi
    if [ "$(ssh_status)" = 2 ]; then
        echo "lado: warning: lado (uid $(id -u)) cannot use the ssh agent socket of uid $owner: $reason" >&2
    fi
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
