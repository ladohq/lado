#!/bin/sh
# LADO's Docker installer: one command installs or updates LADO's container on macOS, Linux
# and Linux in WSL2 (on Windows, install.ps1 runs this script in Ubuntu):
#
#   curl -fsSL https://github.com/ladohq/lado/releases/latest/download/install.sh | sh
#
# It checks Docker, writes .env in ~/lado-docker from what this computer knows (asking only
# for the workspace folder, git's identity when git has none, and the phone), downloads its
# release's compose.yaml, starts LADO, waits for it and opens its link. Run again, it
# updates LADO to its release and keeps .env, secrets/ and the home volume. The steps by
# hand, and everything they mean: docs/install.md#docker. Options: --help.
#
# The release stamps its version below (scripts/stamp_installers.py); the repository's copy
# has none and asks for --version.
set -eu

LADO_INSTALL_VERSION=

REPO=https://github.com/ladohq/lado
GUIDE=https://github.com/ladohq/lado/blob/main/docs/install.md
DESKTOP=https://www.docker.com/products/docker-desktop/

say() { printf '%s\n' "$*"; }
die() {
    printf 'lado install: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
LADO's Docker installer: installs LADO's container in ~/lado-docker, or updates it there.

  curl -fsSL https://github.com/ladohq/lado/releases/latest/download/install.sh | sh
  sh install.sh [options]

Options:
  --yes            ask nothing, take every default (no phone)
  --phone          open LADO to the phone too (every device of this network)
  --no-phone       this computer only; on an update, close it to the network again
  --no-open        print LADO's link, do not open a browser
  --version X.Y.Z  install this release instead of the script's own
  --dir FOLDER     work in FOLDER instead of ~/lado-docker (for checks: a LADO of its own)
  --image NAME     run the image NAME (e.g. lado:local) instead of the release's
  --source FOLDER  take compose.yaml from FOLDER instead of the release
  --help           this text

The guide: https://github.com/ladohq/lado/blob/main/docs/install.md#docker
EOF
}

parse() {
    yes=0 phone='' open_link=1 version='' dir='' image='' source=''
    while [ $# -gt 0 ]; do
        case $1 in
        --yes | -y) yes=1 ;;
        --phone) phone=yes ;;
        --no-phone) phone=no ;;
        --no-open) open_link=0 ;;
        --version | --dir | --image | --source)
            [ $# -ge 2 ] && [ -n "$2" ] || die "$1 needs a value: see --help"
            case $1 in
            --version) version=$2 ;;
            --dir) dir=$2 ;;
            --image) image=$2 ;;
            --source) source=$2 ;;
            esac
            shift
            ;;
        --help | -h)
            usage
            exit 0
            ;;
        *) die "unknown option $1: see --help" ;;
        esac
        shift
    done
}

# Prints <, = or > for how release $1 stands to release $2 (X.Y.Z, or X.Y.ZrcN before its
# X.Y.Z); fails for a version of another form, a development build's too.
version_cmp() {
    awk -v a="$1" -v b="$2" '
        function key(v, out,   p, n) {
            if (v !~ /^[0-9]+\.[0-9]+\.[0-9]+(rc[0-9]+)?$/) return 0
            n = split(v, p, /\.|rc/)
            out[1] = p[1] + 0; out[2] = p[2] + 0; out[3] = p[3] + 0
            out[4] = (n == 4 ? p[4] + 0 : 1e9)
            return 1
        }
        BEGIN {
            if (!key(a, x) || !key(b, y)) exit 2
            for (i = 1; i <= 4; i++)
                if (x[i] != y[i]) { print (x[i] < y[i] ? "<" : ">"); exit 0 }
            print "="
        }'
}

# The shell's LADO_* and COMPOSE_* would beat .env for compose: none reaches this script's.
scrub_env() {
    stray=$(env | grep -E '^(LADO|COMPOSE)_[A-Za-z0-9_]*=' | cut -d= -f1 | tr '\n' ' ')
    stray=${stray% }
    for name in $stray; do
        unset "$name"
    done
}

find_platform() {
    case $(uname -r 2>/dev/null) in
    *[Mm]icrosoft* | *WSL*) platform=wsl ;;
    *) case $(uname -s) in Darwin) platform=mac ;; *) platform=linux ;; esac ;;
    esac
}

check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        if [ "$platform" = linux ]; then
            die "Docker is not installed: install Docker Engine (https://docs.docker.com/engine/install/, or curl -fsSL https://get.docker.com | sh), then run this again"
        fi
        if [ "$platform" = wsl ]; then
            die "docker is not here in WSL: in Docker Desktop turn on Settings → Resources → WSL integration for this distribution (or install Docker Desktop, $DESKTOP), then run this again"
        fi
        die "Docker is not installed: install Docker Desktop ($DESKTOP), start it, then run this again"
    fi
    docker compose version >/dev/null 2>&1 ||
        die "docker compose does not answer: install Docker's compose plugin (https://docs.docker.com/compose/install/), then run this again"
    if err=$(docker info 2>&1 >/dev/null); then
        return 0
    fi
    case $err in
    *"permission denied"* | *"Permission denied"*)
        die "you may not use Docker: add yourself to its group (sudo usermod -aG docker \$USER), log in again, then run this again"
        ;;
    esac
    case $platform in
    mac) start_docker_desktop ;;
    wsl) die "Docker does not answer in WSL: start Docker Desktop in Windows and turn on its Settings → Resources → WSL integration for this distribution, then run this again" ;;
    *) die "Docker's daemon does not answer: start it (sudo systemctl start docker), then run this again" ;;
    esac
}

start_docker_desktop() {
    open -a Docker >/dev/null 2>&1 ||
        die "Docker does not answer and Docker Desktop does not start: install it ($DESKTOP), start it, then run this again"
    say "Waiting for Docker Desktop to start (up to 2 minutes)..."
    tries=0
    while [ $tries -lt 60 ]; do
        sleep 2
        if docker info >/dev/null 2>&1; then
            return 0
        fi
        tries=$((tries + 1))
    done
    die "Docker Desktop did not answer in 2 minutes: start it from Applications, wait until it runs, then run this again"
}

# The value of the last line of .env setting $1 (compose takes the last), unquoted.
env_value() {
    awk -v k="$1" '
        $0 ~ "^[ \t]*" k "[ \t]*=" {
            v = $0; sub(/^[^=]*=[ \t]*/, "", v); sub(/[ \t]+#.*$/, "", v); sub(/[ \t]+$/, "", v)
            if (v ~ /^".*"$/ || v ~ /^'\''.*'\''$/) v = substr(v, 2, length(v) - 2)
            found = v
        }
        END { print found }' "$dir/.env"
}

# Compose's project of the folder: compose.yaml's `lado` in ~/lado-docker, else its own.
find_project() {
    if [ -f "$dir/.env" ]; then
        project=$(env_value COMPOSE_PROJECT_NAME)
    elif [ "$dir" != "$HOME/lado-docker" ]; then
        project=lado-$(basename "$dir" | tr '[:upper:]' '[:lower:]' | sed -e 's/[^a-z0-9_-]/-/g')
    else
        project=
    fi
    [ -n "$project" ] || project=lado
}

# A container of the same compose project made from another folder is another LADO.
check_other_folder() {
    made=$(docker ps -a --filter "label=com.docker.compose.project=$project" \
        --format '{{.Label "com.docker.compose.project.working_dir"}}' 2>/dev/null) || made=
    real=$dir
    if [ -d "$dir" ]; then
        real=$(cd -P "$dir" && pwd)
    fi
    other=$(printf '%s\n' "$made" | awk -v a="$dir" -v b="$real" 'NF && $0 != a && $0 != b { print; exit }')
    [ -z "$other" ] ||
        die "a LADO of the compose project $project runs from another folder, $other: update it there ($GUIDE#update-the-container), or remove it first; nothing was changed"
}

# The answer to a question in $reply: read from the terminal (under `curl | sh` stdin is
# the script), or the default.
ask() {
    reply=
    if [ "$interactive" = 1 ]; then
        printf '%s' "$1" >/dev/tty
        IFS= read -r reply </dev/tty || reply=
    fi
    [ -n "$reply" ] || reply=$2
}

# Whether $1 may go into .env as it is: compose would read a ", $ or \ in it otherwise.
plain() {
    case $1 in *'"'* | *'$'* | *\\* | *'`'*) return 1 ;; esac
}

# A ~ the human typed is expanded here: the shell never sees the answer.
# shellcheck disable=SC2088
ask_workspace() {
    while :; do
        ask "Workspace folder, the only one the agents see [~/workspace]: " "~/workspace"
        case $reply in
        "~") reply=$HOME ;;
        "~/"*) reply=$HOME/${reply#"~/"} ;;
        esac
        [ "$reply" = / ] || reply=${reply%/}
        if ! plain "$reply"; then
            say "It may not hold \", \$, \\ or \`: take another folder."
        else
            case $reply in /*) break ;; esac
            say "It needs a full path, starting with / or ~/."
        fi
        [ "$interactive" = 1 ] || die "the workspace folder $reply is not a full path: give one starting with / or ~/"
    done
    workspace=$reply
}

# git's identity for the agents' commits: the computer's, else asked; $1 is user.name or
# user.email, the answer in $reply (empty: none).
identity() {
    found=
    if command -v git >/dev/null 2>&1; then
        found=$(git config --global --get "$1" 2>/dev/null) || found=
    fi
    if [ -n "$found" ] && plain "$found"; then
        reply=$found
        return 0
    fi
    while [ "$interactive" = 1 ]; do
        ask "$2" ""
        if [ -z "$reply" ] || plain "$reply"; then
            return 0
        fi
        say "It may not hold \", \$, \\ or \`."
    done
    reply=
}

pick_port() {
    if command -v nc >/dev/null 2>&1; then
        probe=nc
    elif command -v lsof >/dev/null 2>&1; then
        probe=lsof
    else
        port=8765
        notes="$notes
Neither nc nor lsof is here to find a free port: LADO takes 8765."
        return 0
    fi
    port=8765
    while [ $port -le 8799 ]; do
        if [ $probe = nc ]; then
            nc -z 127.0.0.1 $port >/dev/null 2>&1 || return 0
        else
            lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1 || return 0
        fi
        port=$((port + 1))
    done
    die "every port from 8765 to 8799 is taken on this computer: stop a program that listens on one, then run this again"
}

find_ssh_agent() {
    ssh_agent=
    if [ "$platform" = mac ]; then
        ssh_agent=/run/host-services/ssh-auth.sock # Docker Desktop's way to the Mac's agent
    elif [ -S "${SSH_AUTH_SOCK:-}" ]; then
        ssh_agent=$SSH_AUTH_SOCK
        notes="$notes
The agents use your ssh agent at $ssh_agent; its path may change at a new login: run this again after one."
    else
        notes="$notes
No ssh agent here: git over ssh is off for the agents (https and GH_TOKEN still work)."
    fi
}

phone_warning() {
    warned=1
    say ""
    say "LADO's link holds its key: anyone on the same network who gets it can run commands as you, it travels unencrypted (plain HTTP), and a laptop is open on every network it joins, a café's too."
}

ask_phone() {
    if [ -n "$phone" ]; then
        return 0
    fi
    if [ "$interactive" = 1 ]; then
        phone_warning
        ask "Open LADO on your phone too? [y/N]: " n
        case $reply in [yY]*) phone=yes ;; *) phone=no ;; esac
    else
        phone=no
    fi
}

# This computer's name for another device of the network, in $public_host.
find_public_host() {
    public_host=
    case $platform in
    mac) public_host=$(scutil --get LocalHostName 2>/dev/null) || public_host= ;;
    wsl) public_host=$(cmd.exe /c hostname 2>/dev/null | tr -d '\r\n' | tr '[:upper:]' '[:lower:]') || public_host= ;;
    *)
        if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet avahi-daemon 2>/dev/null; then
            public_host=$(hostname 2>/dev/null) || public_host=
        fi
        ;;
    esac
    if [ -n "$public_host" ]; then
        public_host=$public_host.local
        return 0
    fi
    public_host=$(hostname -I 2>/dev/null | awk '{ print $1 }') || public_host=
    if [ -z "$public_host" ]; then
        public_host=$(ip -4 route get 1.1.1.1 2>/dev/null |
            awk '{ for (i = 1; i < NF; i++) if ($i == "src") { print $(i + 1); exit } }') || public_host=
    fi
    [ -n "$public_host" ] ||
        die "this computer has no network address for the phone: join a network, then run this again with --phone"
    notes="$notes
The phone reaches LADO at this computer's address now, $public_host, which may change with the network: then run this again with --phone."
}

# compose.yaml of the release (or --source) into compose.yaml.new.
fetch_compose() {
    if [ -n "$source" ]; then
        cp "$source/compose.yaml" "$dir/compose.yaml.new" ||
            die "cannot copy $source/compose.yaml: check that --source names a folder with compose.yaml"
        return 0
    fi
    url=$REPO/releases/download/v$version/compose.yaml
    curl -fsSL -o "$dir/compose.yaml.new" "$url" ||
        die "cannot download $url: check the network and that the release v$version exists, then run this again"
}

# A value for .env, quoted when compose would read it otherwise.
quoted() {
    case $1 in
    *[!A-Za-z0-9_./@:+-]*) printf '"%s"' "$1" ;;
    *) printf '%s' "$1" ;;
    esac
}

write_env() {
    {
        say "# Written by LADO's installer on $(date +%Y-%m-%d); running the install line again updates LADO."
        say "# Every setting: $GUIDE#docker"
        say "LADO_VERSION=$version"
        say "LADO_WORKSPACE=$(quoted "$workspace")"
        say "LADO_PORT=$port"
        if [ -n "$git_name" ]; then say "LADO_GIT_NAME=$(quoted "$git_name")"; fi
        if [ -n "$git_email" ]; then say "LADO_GIT_EMAIL=$(quoted "$git_email")"; fi
        if [ -n "$ssh_agent" ]; then say "LADO_SSH_AGENT=$(quoted "$ssh_agent")"; fi
        if [ "$phone" = yes ]; then
            say "LADO_LISTEN=0.0.0.0"
            say "LADO_PUBLIC_HOST=$public_host"
        fi
        if [ "$project" != lado ]; then say "COMPOSE_PROJECT_NAME=$project"; fi
        if [ -n "$image" ]; then say "LADO_IMAGE=$(quoted "$image")"; fi
    } >"$dir/.env.new"
}

fresh_install() {
    [ ! -e "$dir/compose.yaml" ] ||
        die "$dir has a compose.yaml but no .env: a LADO set up by hand, which this installer does not change; update it by hand ($GUIDE#update-the-container)"
    ask_workspace
    git_name='' git_email=''
    identity user.name "Your name for the agents' git commits: "
    git_name=$reply
    identity user.email "Your email for the agents' git commits: "
    git_email=$reply
    if [ -z "$git_name" ] || [ -z "$git_email" ]; then
        notes="$notes
Warning: the agents cannot commit until LADO_GIT_NAME and LADO_GIT_EMAIL are set in $dir/.env; then run this again."
    fi
    pick_port
    find_ssh_agent
    ask_phone
    if [ "$phone" = yes ]; then
        if [ -z "$warned" ]; then phone_warning; fi
        find_public_host
    fi
    mkdir -p "$dir"
    fetch_compose
    write_env
    if [ ! -d "$workspace" ]; then
        mkdir -p "$workspace" || die "cannot make the workspace folder $workspace: make it yourself, or take another, then run this again"
        say "Made $workspace"
    fi
    mv "$dir/compose.yaml.new" "$dir/compose.yaml"
    mv "$dir/.env.new" "$dir/.env"
    say "Wrote $dir/.env and $dir/compose.yaml for LADO $version."
}

# .env again in .env.new: every LADO_VERSION line set to $1 (none when empty); with $2
# the phone's two lines dropped and, for --phone, added anew; with an image $3 every
# LADO_IMAGE line replaced by its one; every other line kept.
rewrite_env() {
    awk -v ver="$1" -v drop="$2" -v img="$3" '
        ver != "" && /^[ \t]*LADO_VERSION[ \t]*=/ { print "LADO_VERSION=" ver; next }
        drop && /^[ \t]*LADO_(LISTEN|PUBLIC_HOST)[ \t]*=/ { next }
        img != "" && /^[ \t]*LADO_IMAGE[ \t]*=/ { next }
        { print }' "$dir/.env" >"$dir/.env.new"
    if [ "$phone" = yes ]; then
        say "LADO_LISTEN=0.0.0.0" >>"$dir/.env.new"
        say "LADO_PUBLIC_HOST=$public_host" >>"$dir/.env.new"
    fi
    if [ -n "$3" ]; then say "LADO_IMAGE=$(quoted "$3")" >>"$dir/.env.new"; fi
}

rerun() {
    current=$(env_value LADO_VERSION)
    [ -n "$current" ] ||
        die "$dir/.env sets no LADO_VERSION: a setup this installer does not understand; update it by hand ($GUIDE#update-the-container)"
    relation=$(version_cmp "$current" "$version") ||
        die "$dir/.env runs LADO $current, a version this installer does not update (a development build?): update it by hand ($GUIDE#update-the-container)"
    if [ "$relation" = ">" ]; then
        die "$dir/.env runs LADO $current, newer than this installer's $version, and it never goes back: to go back, see $GUIDE#go-back-to-the-version-before; nothing was changed"
    fi
    if [ "$phone" = yes ]; then
        phone_warning
        find_public_host
    fi
    new=
    if [ "$relation" = "<" ]; then new=$version; fi
    if [ -n "$new" ] || [ ! -f "$dir/compose.yaml" ]; then
        fetch_compose
    fi
    new_image=''
    if [ -n "$image" ] && [ "$(env_value LADO_IMAGE)" != "$image" ]; then new_image=$image; fi
    if [ -n "$new" ] || [ -n "$phone" ] || [ -n "$new_image" ]; then
        drop=0
        if [ -n "$phone" ]; then drop=1; fi
        rewrite_env "$new" $drop "$new_image"
    fi
    if [ -n "$new" ] && [ -f "$dir/compose.yaml" ]; then
        cp "$dir/compose.yaml" "$dir/compose.yaml.bak"
    fi
    if [ -f "$dir/compose.yaml.new" ]; then mv "$dir/compose.yaml.new" "$dir/compose.yaml"; fi
    if [ -f "$dir/.env.new" ]; then mv "$dir/.env.new" "$dir/.env"; fi
    if [ -n "$new" ]; then
        say "Updated LADO $current → $version in $dir."
        notes="$notes
.env, secrets/ and the home volume stay as they were; the old compose.yaml is compose.yaml.bak: diff compose.yaml.bak compose.yaml shows a change you made to it by hand."
    else
        say "LADO $version is installed in $dir: starting it."
    fi
    if [ -z "$phone" ] && [ -n "$(env_value LADO_LISTEN)" ]; then phone=yes; fi
}

start_lado() {
    say "Starting LADO..."
    (cd "$dir" && docker compose up -d) ||
        die "docker compose up -d failed in $dir, its error above: when another program has LADO's port, set another LADO_PORT in $dir/.env and run this again"
}

# The UI's link, once the server answers, in $link; another device's in $other_link.
wait_link() {
    errors=$dir/.install-ui.err
    tries=0
    while [ $tries -lt 90 ]; do
        if (cd "$dir" && docker compose exec -T lado sh -c 'curl -fsS -o /dev/null "http://127.0.0.1:${LADO_PORT:-8765}/api/health"') >/dev/null 2>&1 &&
            link=$(cd "$dir" && docker compose exec -T lado lado ui --no-open 2>"$errors"); then
            case $link in
            http*)
                other_link=$(sed -n -e 's/^From another machine: //p' "$errors")
                rm -f "$errors"
                return 0
                ;;
            esac
        fi
        sleep 2
        tries=$((tries + 1))
    done
    rm -f "$errors"
    (cd "$dir" && docker compose logs --tail 30 lado) >&2 || true
    die "LADO did not answer in 3 minutes: its log is above; see $GUIDE#docker"
}

open_url() {
    [ "$open_link" = 1 ] || return 0
    case $platform in
    mac) open "$1" ;;
    wsl)
        if command -v wslview >/dev/null 2>&1; then
            wslview "$1"
        else
            cmd.exe /c start "" "$1"
        fi
        ;;
    *)
        if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$1"
        fi
        ;;
    esac >/dev/null 2>&1 || true
}

main() {
    parse "$@"
    version=${version:-$LADO_INSTALL_VERSION}
    [ -n "$version" ] ||
        die "this install.sh carries no version: take the release's ($REPO/releases/latest/download/install.sh) or pass --version X.Y.Z"
    version_cmp "$version" "$version" >/dev/null ||
        die "$version is no LADO release: pass --version X.Y.Z or X.Y.ZrcN"
    scrub_env
    find_platform
    check_docker

    interactive=0
    if [ "$yes" = 1 ]; then
        say "Taking the defaults (--yes)."
    elif (: </dev/tty) 2>/dev/null; then
        interactive=1
    else
        say "No terminal: taking the defaults."
    fi
    notes='' warned=''
    dir=${dir:-$HOME/lado-docker}
    case $dir in /*) ;; *) dir=$PWD/$dir ;; esac
    # ~/lado-docker/ is ~/lado-docker, not a second LADO's folder.
    while [ "$dir" != / ] && [ "${dir%/}" != "$dir" ]; do dir=${dir%/}; done
    trap 'rm -f "$dir/.env.new" "$dir/compose.yaml.new"' EXIT
    find_project
    check_other_folder
    if [ -f "$dir/.env" ]; then
        rerun
    else
        fresh_install
    fi
    start_lado
    wait_link

    say ""
    say "LADO $version runs: $link"
    say "Keep it as a bookmark: its key stays the same across restarts and updates."
    if [ "$phone" = yes ]; then
        if [ -n "$other_link" ]; then say "On your phone: $other_link"; fi
        say "Or in LADO: live → the QR code."
    fi
    if [ -n "$notes" ]; then
        printf '%s\n' "$notes" | sed -e '1d'
    fi
    if [ -n "$stray" ]; then
        say "Your shell sets $stray, which beat .env when you run docker compose by hand: unset $stray first."
    fi
    open_url "$link"
}

main "$@"
