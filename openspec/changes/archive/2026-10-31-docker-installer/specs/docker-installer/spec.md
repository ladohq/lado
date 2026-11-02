## Purpose

LADO's one-line Docker installers: `install.sh` for macOS, Linux and WSL2, and
`install.ps1`, which runs it in Ubuntu inside WSL on Windows. One command installs or
updates LADO's container, asking only what the computer cannot tell.

## ADDED Requirements

### Requirement: The installer is one POSIX script

`docker/install.sh` SHALL run under a POSIX `sh` (dash, bash, macOS' sh) on macOS, Linux
and Linux inside WSL2, read from a pipe (`curl -fsSL <url> | sh`) or run as a file, and
without root.

#### Scenario: Read from a pipe under dash
- **WHEN** a test pipes the script into `dash` with `--yes`
- **THEN** it runs to its end as it does as a file

### Requirement: The installer installs its own release

The installer SHALL install the version stamped in it (`LADO_INSTALL_VERSION`), or the
one `--version` names, and SHALL take that version's `compose.yaml` only from its release
(`https://github.com/ladohq/lado/releases/download/v<version>/compose.yaml`), or from the
folder `--source` names.

#### Scenario: The version's compose file
- **WHEN** an `install.sh` stamped `0.44.0` installs
- **THEN** it downloads `releases/download/v0.44.0/compose.yaml` and writes
  `LADO_VERSION=0.44.0`

#### Scenario: A local compose file
- **WHEN** it runs with `--source <folder>`
- **THEN** it copies `<folder>/compose.yaml` and downloads nothing

### Requirement: An installer without a version refuses

A copy without a stamp and without `--version` SHALL refuse before it changes anything,
with `lado install: this install.sh carries no version: take the release's
(https://github.com/ladohq/lado/releases/latest/download/install.sh) or pass --version
X.Y.Z`.

#### Scenario: An unstamped copy
- **WHEN** the repository's `docker/install.sh` runs without `--version`
- **THEN** it exits non-zero with the refusal, and no folder, `.env` or container is made

### Requirement: The installer checks Docker before it changes anything

Before it makes a folder or writes a file, the installer SHALL check that `docker` is on
PATH, that `docker compose version` answers and that `docker info` answers, and each
failure SHALL stop it with what is wrong and what to do. It SHALL NOT install Docker nor
run `sudo`.

#### Scenario: No Docker on Linux
- **WHEN** `docker` is not on PATH on Linux
- **THEN** the script exits non-zero naming Docker Engine's install page and `curl -fsSL
  https://get.docker.com | sh`, and `~/lado-docker` does not exist

#### Scenario: No Docker on macOS or in WSL
- **WHEN** `docker` is not on PATH on macOS or in WSL
- **THEN** it names Docker Desktop's download page

#### Scenario: No compose
- **WHEN** `docker compose version` fails
- **THEN** it names Docker's compose plugin

#### Scenario: Permission denied
- **WHEN** `docker info` fails with `permission denied` on its socket
- **THEN** the script names `sudo usermod -aG docker $USER` and a new login, and stops

#### Scenario: The daemon is not running on Linux
- **WHEN** `docker info` fails otherwise on Linux
- **THEN** it names `sudo systemctl start docker`

### Requirement: The installer starts Docker Desktop on macOS

On macOS, when `docker info` fails and Docker Desktop is installed, the installer SHALL
start it (`open -a Docker`), say that it waits for it, and wait up to 120 seconds for
`docker info` before it stops.

#### Scenario: Docker Desktop not running
- **WHEN** `docker info` fails at first on macOS and answers after `open -a Docker`
- **THEN** the script says it is waiting for Docker Desktop and goes on once it answers

### Requirement: A fresh install asks for the workspace

On a folder without `.env` the installer SHALL ask for the workspace folder with the
default `~/workspace` shown, Enter taking it; a `~` SHALL be expanded, a path that is not
absolute SHALL be asked again, and a missing folder SHALL be made and said.

#### Scenario: The default by Enter
- **WHEN** the question is answered by Enter in a pty
- **THEN** `.env` has `LADO_WORKSPACE=<home>/workspace` and the folder exists

#### Scenario: A relative workspace
- **WHEN** the answer is `projects`
- **THEN** the question is asked again, saying it needs a full path

### Requirement: A fresh install takes git's identity from the computer

The installer SHALL take `LADO_GIT_NAME` and `LADO_GIT_EMAIL` from the computer's `git
config --global user.name` and `user.email`, and SHALL ask only for the one that is
missing.

#### Scenario: The computer's identity
- **WHEN** the computer's git config names `Ann Lee` and `ann@example.com`
- **THEN** `.env` has `LADO_GIT_NAME="Ann Lee"` and `LADO_GIT_EMAIL=ann@example.com`, and
  neither was asked

#### Scenario: No identity
- **WHEN** the computer has no git identity and the questions are answered `Ann Lee` and
  `ann@example.com`
- **THEN** `.env` has both

### Requirement: Questions come from the terminal, or their defaults are taken

The installer SHALL read its questions from `/dev/tty`, so a piped script asks them too.
With `--yes`, or with no terminal, it SHALL ask nothing, take the defaults and say so; a
git identity it then lacks SHALL be left out of `.env` with a warning that the agents
cannot commit until `LADO_GIT_NAME` and `LADO_GIT_EMAIL` are set there.

#### Scenario: No terminal
- **WHEN** the script runs with no terminal and the computer has no git identity
- **THEN** it asks nothing, writes `.env` without `LADO_GIT_NAME` and `LADO_GIT_EMAIL`,
  and warns that the agents cannot commit

### Requirement: The installer picks a free port

A fresh install SHALL write `LADO_PORT=8765`, or the first port up to 8799 that nothing
listens on at this computer's loopback; with none free it SHALL stop and say so.

#### Scenario: Port taken
- **WHEN** something listens on 127.0.0.1:8765
- **THEN** `.env` has `LADO_PORT=8766` and the printed link has `:8766`

### Requirement: The installer gives the agents the ssh agent there is

A fresh install SHALL write `LADO_SSH_AGENT`: on macOS `/run/host-services/ssh-auth.sock`
(Docker Desktop's), elsewhere `$SSH_AUTH_SOCK` when it is a socket, saying that this path
may change at a new login; with neither it SHALL write none and say that git over ssh is
off.

#### Scenario: macOS
- **WHEN** a fresh install runs on macOS
- **THEN** `.env` has `LADO_SSH_AGENT=/run/host-services/ssh-auth.sock`

#### Scenario: Linux without an agent
- **WHEN** `SSH_AUTH_SOCK` is unset on Linux
- **THEN** `.env` has no `LADO_SSH_AGENT` and the script says git over ssh is off

### Requirement: The installer's folder and its compose project

The installer SHALL work in `~/lado-docker`, made when missing, or in the folder `--dir`
names; a folder other than `~/lado-docker` SHALL get `COMPOSE_PROJECT_NAME=lado-<folder's
name>` in its `.env` (made a valid compose name), so it never meets the default LADO's
container. `--image <name>` SHALL write `LADO_IMAGE=<name>`.

#### Scenario: Another folder
- **WHEN** the script runs with `--dir /tmp/lado-check`
- **THEN** `.env` there has `COMPOSE_PROJECT_NAME=lado-lado-check`, and compose runs
  under that name

#### Scenario: A local image
- **WHEN** it runs with `--image lado:local`
- **THEN** `.env` has `LADO_IMAGE=lado:local` beside `LADO_VERSION`

### Requirement: The installer's .env is the manual way's

Every line the installer writes to `.env` SHALL be a variable the compose header names,
so the guide's manual steps and compose read it as they read a hand-written one.

#### Scenario: Only the header's variables
- **WHEN** `tests/test_install_sh.py` collects the names the script writes
- **THEN** each is named in `docker/compose.yaml`'s header

### Requirement: The shell's LADO and COMPOSE variables do not reach the installer's compose

The installer SHALL run compose without any `LADO_*` or `COMPOSE_*` variable of the shell
it was started from, and when there were any it SHALL name them and say to `unset` them
before running `docker compose` by hand in that shell.

#### Scenario: A stray LADO_VERSION
- **WHEN** the shell has `LADO_VERSION=0.30.0` and the script installs `0.44.0`
- **THEN** compose runs without that variable, and the script names `LADO_VERSION` with
  the advice to unset it

### Requirement: The installer never replaces another folder's LADO

Before it starts compose, the installer SHALL look for a container of its compose project
made from another folder (compose's label `com.docker.compose.project.working_dir`); when
there is one it SHALL stop, naming that folder, and change nothing of it.

#### Scenario: A manual LADO elsewhere
- **WHEN** a container of project `lado` was made from `/Users/ann/lado` and the script
  runs for `~/lado-docker`
- **THEN** it exits non-zero naming `/Users/ann/lado`, and that container is untouched

### Requirement: The installer starts LADO and waits for its link

After writing its files the installer SHALL run `docker compose up -d` in its folder and
wait, up to 180 seconds, until `docker compose exec -T lado lado ui --no-open` prints the
link; a server that does not answer in time SHALL stop it with the last lines of `docker
compose logs lado`.

#### Scenario: The server does not answer
- **WHEN** `lado ui --no-open` keeps failing for the whole wait
- **THEN** the script exits non-zero and prints the tail of the container's log

### Requirement: The installer prints and opens the link

The installer SHALL print the link, say it is worth a bookmark (the token stays across
restarts), and open it: `open` on macOS, `xdg-open` on Linux with a display, Windows'
browser from WSL (`wslview` when present, else `cmd.exe /c start`); with `--no-open`, or
when no opener works, it SHALL only print it.

#### Scenario: The end of a fresh install
- **WHEN** the fake compose's `lado ui --no-open` prints `http://127.0.0.1:8765/?token=abc`
- **THEN** the script prints that link and runs the opener with it

#### Scenario: No opener
- **WHEN** it runs with `--no-open`
- **THEN** it prints the link and runs no opener

### Requirement: The phone is asked after its warning, no by default

A fresh install SHALL ask `Open LADO on your phone too? [y/N]` after a warning that whoever
on the same network gets the link can run commands as the user, that it travels
unencrypted (plain HTTP), and that a laptop is open on every network it joins; Enter
SHALL mean no. `--phone` and `--no-phone` SHALL answer it beforehand; `--yes` alone means
no.

#### Scenario: Enter means no
- **WHEN** the phone's question is answered by Enter
- **THEN** the warning was printed before it, and `.env` has no `LADO_LISTEN`

#### Scenario: --yes
- **WHEN** it runs with `--yes` and no `--phone`
- **THEN** `.env` has no `LADO_LISTEN`

### Requirement: The phone's yes publishes LADO under the computer's name

A yes SHALL write `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST`: on macOS
`<LocalHostName>.local`, from WSL the Windows computer's name with `.local`, on Linux
`<hostname>.local` when avahi runs, else the computer's current network address with a
warning that it may change. The end SHALL then also print the link for another device
and the hint `live → the QR code` in the UI.

#### Scenario: Yes on macOS
- **WHEN** it is answered `y` on macOS whose LocalHostName is `ann-mbp`
- **THEN** `.env` has `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=ann-mbp.local`, and the
  end prints the other device's link and the QR hint

#### Scenario: Linux without mDNS
- **WHEN** it is answered `y` on Linux with no avahi
- **THEN** `LADO_PUBLIC_HOST` is the current address and the script warns it may change

### Requirement: A rerun keeps the phone's choice unless a flag changes it

On a folder with `.env` the installer SHALL not ask about the phone and SHALL keep what
`.env` says; `--phone` SHALL add the two lines and `--no-phone` remove them.

#### Scenario: Phone added later
- **WHEN** a rerun has `--phone` and `.env` has no `LADO_LISTEN`
- **THEN** `.env` gets `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST`, its other lines kept

### Requirement: A rerun updates an older LADO and keeps its settings

On a folder whose `.env` has an older `LADO_VERSION` (PEP 440 order of `X.Y.Z` and
`X.Y.ZrcN`), the installer SHALL ask nothing, keep `compose.yaml` as `compose.yaml.bak`,
put its version's `compose.yaml` in place, change only `.env`'s `LADO_VERSION` line, run
`docker compose up -d`, and say that `.env`, `secrets/` and the home volume stay and that
`diff compose.yaml.bak compose.yaml` shows a hand-made change.

#### Scenario: An update
- **WHEN** `.env` has `LADO_VERSION=0.43.0` and a line `LADO_SECRETS=./secrets`, and the
  script is `0.44.0`
- **THEN** `compose.yaml.bak` is the old file, `.env` has `LADO_VERSION=0.44.0` and still
  `LADO_SECRETS=./secrets`, and `docker compose up -d` ran

#### Scenario: A release candidate after its final
- **WHEN** `.env` has `0.44.0rc2` and the script is `0.44.0`
- **THEN** it updates

### Requirement: A rerun of the same version only starts LADO

On a folder whose `.env` has the installer's own version, it SHALL rewrite no file, run
`docker compose up -d` and print and open the link.

#### Scenario: The same version
- **WHEN** `.env` has the script's own version
- **THEN** no file changes, compose starts and the link is printed

### Requirement: The installer never goes back to an older version

On a folder whose `.env` has a newer `LADO_VERSION`, the installer SHALL refuse, change
nothing, and name the guide's way back (docs/install.md, "Go back to the version
before").

#### Scenario: A downgrade
- **WHEN** `.env` has `LADO_VERSION=0.45.0` and the script is `0.44.0`
- **THEN** it exits non-zero naming the guide's way back, and nothing changes

### Requirement: Every stop of the installer says what and what to do

Every failure SHALL exit non-zero with a line starting `lado install:` that names what
failed and the next step; a failed download SHALL name its URL. `.env` and `compose.yaml`
SHALL be written to a temporary file and moved in place only when complete, so a failure
leaves them as they were.

#### Scenario: A download fails
- **WHEN** the fake curl fails for `compose.yaml` on an update
- **THEN** the script exits with a `lado install:` line naming the URL, and the old
  `compose.yaml` and `.env` are unchanged

### Requirement: The Windows front is a PowerShell script of its release

`docker/install.ps1` SHALL run in Windows PowerShell 5.1 and PowerShell 7 without
administrator rights, as `irm <url> | iex`, and SHALL run inside WSL's Ubuntu the
`install.sh` of its own stamped version (`releases/download/v<version>/install.sh`),
passing `-Yes`, `-Phone` and `-NoPhone` as `--yes`, `--phone` and `--no-phone`, with the
terminal for its questions. A copy without a stamp SHALL refuse.

#### Scenario: The script's text
- **WHEN** `tests/test_install_ps1.py` reads `docker/install.ps1`
- **THEN** it has the stamp placeholder and the release's `install.sh` address of its
  version, and maps the three switches

#### Scenario: It parses
- **WHEN** `pwsh` is on PATH (GitHub's Ubuntu runners have it)
- **THEN** the PowerShell parser reads `install.ps1` with no error

#### Scenario: A real Windows
- **WHEN** the human runs the release candidate's `install.ps1` on Windows 11 with Docker
  Desktop (docs/release.md's check)
- **THEN** LADO starts in Ubuntu and its link opens in Windows' browser

### Requirement: The Windows front checks Docker Desktop first

`install.ps1` SHALL check that `docker` is on PATH and `docker info` answers; Docker
Desktop missing SHALL name its download page and stop; installed but not running, it SHALL
be started and waited for up to 120 seconds.

#### Scenario: No Docker Desktop
- **WHEN** `tests/test_install_ps1.py` reads the script
- **THEN** its stop for a missing `docker` names Docker Desktop's download page

### Requirement: The Windows front finds or offers Ubuntu in WSL

`install.ps1` SHALL take a WSL distribution named `Ubuntu*`, never `docker-desktop*`. With
none it SHALL say that LADO runs in Ubuntu inside WSL, offer `wsl --install -d Ubuntu`
(administrator rights, maybe a restart), and then say to open Ubuntu once, make its user
and run the same command again. WSL missing or refused SHALL be said as Docker Desktop's
need of WSL2.

#### Scenario: No Ubuntu
- **WHEN** `tests/test_install_ps1.py` reads the script
- **THEN** it skips `docker-desktop` distributions, offers `wsl --install -d Ubuntu`, and
  says to run the command again after Ubuntu's first start

### Requirement: The Windows front checks Docker inside Ubuntu

`install.ps1` SHALL check that `docker` answers inside the Ubuntu it took; when not, it
SHALL name Docker Desktop's Settings → Resources → WSL integration and that distribution,
and stop.

#### Scenario: No WSL integration
- **WHEN** `tests/test_install_ps1.py` reads the script
- **THEN** its stop names `Settings → Resources → WSL integration`
