## Context

The Docker way is `docker/compose.yaml` (the release's asset `compose.yaml`) plus `.env`
written by hand, as docs/install.md's Docker section and README describe; the container
tests (`tests/container/`) run the compose header's commands with real Docker, and
`tests/test_docker.py` holds the guide, README and the header to each other. The release
workflow's job `github-release` uploads `dist/*` and `docker/compose.yaml`
(`tests/test_release_workflow.py`). The image's server keeps its token in the home
volume (`server/auth.py`), so the link `lado ui --no-open` prints stays the same across
restarts and updates; in a container that command prints exactly the local link on stdout
and, with `LADO_LISTEN`, the `From another machine: …` line on stderr (container spec,
"lado ui in a container prints the link for the host's browser").

The human's answers: #2083 (one script, questions only for what the computer cannot
answer, no Docker install, the link opened, rerun = update, English) and #2092 (Windows
by a thin `install.ps1` over WSL's Ubuntu, checked by hand by the human; the phone asked
after its warning, Enter = no). Research: run artifact `research-installers`.

## Goals / Non-Goals

Goals: one command installs or updates LADO's container on macOS, Linux and Windows; the
human types only what the computer cannot know; every stop says what to do.

Non-goals: see the proposal's Out of scope.

## Decisions

### D1. Two files in `docker/`, one implementation

`docker/install.sh` holds every step; `docker/install.ps1` (about a hundred lines) only
gets Windows to an Ubuntu shell with Docker and runs the same `install.sh` of its version
there (`wsl.exe -d <distro> -- sh -c 'curl -fsSL <url> | sh -s -- <args>'`). Why not a
native `.ps1`: the workspace must be a Linux path (proposal, option c), so Windows' own
filesystem is no place for it; why not the steps in Python (`lado` is not on the host):
the host has only Docker and a shell. They live in `docker/` beside the compose file they
install; `docker/Dockerfile.dockerignore` is an allowlist, so the image does not get them.

### D2. The version is stamped at release, never looked up

The repository's files carry `LADO_INSTALL_VERSION=` (sh) and `$LadoVersion = ''` (ps1).
`scripts/stamp_installers.py <version> <out-dir>` writes copies with the version, failing
when a placeholder is not exactly once; the job `github-release` runs it with
`${GITHUB_REF_NAME#v}` into `$RUNNER_TEMP/installers` and uploads both files beside
`compose.yaml` (asset names are the base names). So `latest/download/install.sh` is the
newest final's and installs exactly that final's `compose.yaml` and image; an RC's script
installs the RC (the release check uses it). Rejected: asking GitHub's API for the latest
(rate limit of 60 an hour without a token, a second source of truth that may differ from
the script's own compose file), or following the `releases/latest` redirect at run time
(a pinned `download/v<version>/install.sh` would then install something else).
Unstamped (a copy from the repository): refuse unless `--version` is given; tests always
pass it.

### D3. POSIX sh, questions from /dev/tty, no dependency beyond the base system

`#!/bin/sh`, `set -eu`, no bashisms (tests run it under `dash` and `bash`; `sh` on
macOS is bash in POSIX mode). Under `curl | sh` stdin is the script, so every question
reads from `/dev/tty`; when `/dev/tty` cannot be opened, or with `--yes`, the defaults are
taken and said (`No terminal: taking the defaults.`). Tools used: `curl`, `uname`,
`mkdir`, `mv`, `sed` (only `sed -e` to a temporary file, never `-i`, which differs between
GNU and BSD), `grep`, `awk`; optional `git` (identity), `nc` or `lsof` (ports), `open` /
`xdg-open` / `wslview` / `cmd.exe` (browser), `scutil`, `hostname`, `systemctl`. The whole
script is wrapped in a `main "$@"` called on its last line, so a download cut in the middle
runs nothing.

### D4. The steps, in order

1. Parse flags: `--yes`, `--phone`, `--no-phone`, `--version X`, `--dir D`, `--image I`,
   `--source S`, `--no-open`, `--help`. An unknown flag stops.
2. The version (D2). Remember and `unset` every `LADO_*` and `COMPOSE_*` of the
   environment (the names are printed at the end with the advice to unset them).
3. Docker (spec "The installer checks Docker before it changes anything"); on macOS, start
   Docker Desktop and poll `docker info` every 2 s up to 120 s.
4. The folder: `--dir` or `$HOME/lado-docker`. With `.env` there: a rerun (D6); otherwise a
   fresh install (D5).
5. Another folder's LADO: `docker ps -a --filter label=com.docker.compose.project=<project>
   --format '{{.Label "com.docker.compose.project.working_dir"}}'`; any value other than
   the folder (after `cd -P`) stops.
6. Files: `compose.yaml` downloaded to `compose.yaml.new` (`curl -fsSL`, or `cp` from
   `--source`), `.env` built in `.env.new`, then both moved in place (D6 keeps the `.bak`).
7. `docker compose up -d` in the folder; then `docker compose exec -T lado lado ui
   --no-open` every 2 s up to 180 s; stdout's one line is the link, stderr's `From another
   machine: <url>` the phone's.
8. Print, open (D8), and the final notes (stray variables, git identity, ssh, phone).

### D5. A fresh install's values

- Workspace: asked (`Workspace folder, the only one the agents see [~/workspace]:`); `~`
  and `~/` expanded with `$HOME`; must start with `/`; made with `mkdir -p`.
- Git: `git config --global --get user.name` / `user.email` when `git` exists; a missing one
  is asked; under `--yes` left out with the warning.
- Port: from 8765 to 8799, the first where `nc -z 127.0.0.1 <port>` fails (or, without
  `nc`, `lsof -nP -iTCP:<port> -sTCP:LISTEN` finds nothing; with neither tool, 8765 and a
  note). A port taken by another program on another address is not seen; compose then
  fails on `up` and its error is shown with the hint to set `LADO_PORT` in `.env`.
- ssh: macOS `/run/host-services/ssh-auth.sock`; else `[ -S "$SSH_AUTH_SOCK" ]`.
- Project: `~/lado-docker` keeps compose's `name: lado`; another folder writes
  `COMPOSE_PROJECT_NAME=lado-<basename>` lowercased, other characters to `-` (compose's
  rule: `[a-z0-9][a-z0-9_-]*`).
- `.env` starts with a comment: written by LADO's installer on <date>, the guide's
  address, and that a rerun of the install line updates. Values with a space are quoted
  (`LADO_GIT_NAME="Ann Lee"`); a `"` or `$` in a name or email is refused and asked again
  (compose's `.env` quoting would change it).

### D6. A rerun: compare versions, then update, start or refuse

`.env`'s `LADO_VERSION` (also accepted under its line's surrounding spaces and quotes)
against the script's, by a small `awk` comparison of `X.Y.Z[rcN]`: numbers part by part,
a final above its RCs. A version neither form parses (a dev build `0.44.0.dev1`): refuse
and name the guide's update by hand. Older: `cp compose.yaml compose.yaml.bak` (the one
backup, replaced each update, as the guide's), the new file moved in, `.env` rewritten
through `sed` with only the `LADO_VERSION=` line replaced (the first such line; a second
is left and warned). `--phone` / `--no-phone` on a rerun add or delete the
`LADO_LISTEN` and `LADO_PUBLIC_HOST` lines. A folder with `compose.yaml` but no `.env`,
or `.env` without `LADO_VERSION`: refuse, naming the guide (a hand-made setup the script
does not understand). An `.env` of the old name `LADO_PROJECTS` is left as it is: compose
still accepts it.

### D7. The phone's names

Yes writes `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST`:
- macOS: `scutil --get LocalHostName` + `.local`;
- WSL (`/proc/sys/kernel/osrelease` contains `microsoft`/`WSL`): `cmd.exe /c hostname`
  (CR stripped) + `.local` — Windows answers mDNS for its own name; the Windows run by
  hand checks it;
- Linux: `systemctl is-active --quiet avahi-daemon` → `$(hostname).local`; else the first
  address of `hostname -I` (or `ip -4 route get 1.1.1.1`'s `src`), with the warning that
  it changes with the network.
`share-access`'s rule refuses a bad `LADO_PUBLIC_HOST` loudly in the container, so a
wrong name is seen in the UI and the log, not lost.

### D8. Opening the browser

macOS `open <url>`; WSL `wslview` when on PATH, else `cmd.exe /c start "" "<url>"`
(the link has no `&`); Linux `xdg-open` only with `DISPLAY` or `WAYLAND_DISPLAY`; a
failure of the opener is ignored after the link is printed. The link is printed in any
case, first.

### D9. Windows: what `install.ps1` does

- `Set-StrictMode`, `$ErrorActionPreference = 'Stop'`; runs as a script block from
  `irm | iex`, so it uses no `$PSScriptRoot`; works in 5.1 (no `?.`, no `&&`).
- Docker: `Get-Command docker`; `docker info` fails → start
  `"$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"` when it exists, poll up to 120 s.
- WSL: `wsl.exe -l -q` (its output is UTF-16: read with `[Console]::OutputEncoding` set to
  Unicode for the call, NULs stripped); take the first `Ubuntu*`, skip `docker-desktop*`;
  none → explain, `Read-Host 'Install Ubuntu now? [y/N]'`, `wsl.exe --install -d Ubuntu`,
  then the rerun note, exit 0; `wsl.exe` missing or failing → Docker Desktop needs WSL2.
- Docker in Ubuntu: `wsl.exe -d <d> -- docker version --format '{{.Server.Version}}'`;
  failing → name Settings → Resources → WSL integration and `<d>`, stop.
- Run: `wsl.exe -d <d> --cd ~ -- sh -c "curl -fsSL '<url>' | sh -s -- <flags>"`; its exit
  code becomes the script's. The questions reach the user through WSL's console.
- The Windows run by hand (human, before the release) is the only test of behaviour;
  tests read its text and parse it with `pwsh` when present.

### D10. Tests by layer

- Unit (`tests/test_install_sh.py`): `install.sh` under `dash` and `bash` with fakes on a
  PATH of their own: `docker` (a Python script logging argv and env to a file, answering
  `compose version`, `info`, `ps`, `compose up`, `compose exec … lado ui --no-open` by
  per-test settings), `curl` (copies a fixture `compose.yaml`, or fails), `git`, `uname`,
  `open`, `scutil`, `hostname`, `nc`, `sleep` (returns at once, so no test waits); a
  temp `HOME`. Questions through Python's `pty`. Each
  requirement of the delta gets a test there, but the real Docker ones.
- Unit (`tests/test_install_ps1.py`): text checks, and the parser through `pwsh` when on
  PATH (skipped otherwise; GitHub's Ubuntu runners have `pwsh`).
- Unit: `tests/test_stamp_installers.py`, `tests/test_release_workflow.py`,
  `tests/test_docker.py` (README, guide, header).
- Container (`tests/container/test_install.py`, real Docker, `lado:local`): a fresh
  install with `--yes --no-open --version <lado's> --source docker --image <IMAGE> --dir
  <prefixed tmp>`, its link answers `200`; a rerun of the same version changes no file;
  `.env` set to `0.0.1` → an update keeps `compose.yaml.bak` and the user's line; `--phone`
  → the `From another machine` link printed. No integration test: no LADO process crosses
  another here, and the container layer is the lowest with real Docker.
- By hand: macOS with Docker Desktop and Windows 11, on the RC (docs/release.md).
- No shellcheck in CI (a new tool for one file); the developer runs it once locally
  through `mise exec shellcheck@latest`.

## Risks / Trade-offs

- `curl | sh` runs what the server gives: mitigated by the release asset over https
  (as `compose.yaml` today), `main` called on the last line, and the guide's
  download-read-run way.
- The `.ps1` is not tested by CI: the human's run on the RC is the gate; antivirus may
  flag `irm | iex`, so the guide gives the download-and-run form too (`irm … -OutFile
  install.ps1; powershell -ExecutionPolicy Bypass -File install.ps1`).
- WSL's Windows name over mDNS and Windows' firewall prompt for the phone are checked only
  by hand.
