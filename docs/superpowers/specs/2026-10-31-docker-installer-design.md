# One-line Docker install (LAD-164)

Change: `openspec/changes/docker-installer/` (proposal with AC-1..AC-12, the deltas of
`docker-installer` (new), `image-release` and `container`, `design.md` with D1-D10). This
document is the human's view: what a user gets, what was decided with the human, and how
it is checked. Research: the run's artifact `research-installers`. No UI changes
(docs/design/ui.md stays as it is).

## What a user gets

**macOS and Linux** (and Ubuntu inside WSL2), in a terminal:

```bash
curl -fsSL https://github.com/ladohq/lado/releases/latest/download/install.sh | sh
```

**Windows**, in PowerShell:

```powershell
irm https://github.com/ladohq/lado/releases/latest/download/install.ps1 | iex
```

A fresh install on a Mac with Docker Desktop and git set up looks like this:

```
LADO 0.44.0 installer

Docker: Docker Desktop is not running; starting it and waiting (up to 2 minutes)...
Docker: ok (29.0.1, compose v2.40.3)
Folder: /Users/ann/lado-docker (new)

Workspace folder, the only one the agents see [~/workspace]:
  made /Users/ann/workspace
Git identity for the agents' commits: Ann Lee <ann@example.com> (from your git config)
Port: 8765
ssh: Docker Desktop's ssh agent

LADO's link holds its key: anyone on the same network who gets it can run commands as
you, it travels unencrypted (plain HTTP), and a laptop is open on every network it joins,
a café's too.
Open LADO on your phone too? [y/N]:

Starting LADO (the first start downloads its image)...
LADO is running:

  http://127.0.0.1:8765/?token=…

Opened in your browser. Bookmark it: the link stays the same after restarts and updates.
To update later, run the same install line again.
```

- **It asks only what the computer cannot say:** the workspace (Enter: `~/workspace`,
  made), git's name and email only when `git config --global` lacks them, and the phone.
  `--yes` takes all defaults (the phone: no).
- **Without Docker it stops at once**, naming Docker Desktop's page (Mac, Windows) or
  Docker Engine's install (Linux). It never installs Docker and never runs sudo. A Docker
  the user may not use says how to join the `docker` group.
- **The phone**, answered yes or `--phone`: LADO is published on the network under the
  computer's name (`ann-mbp.local`), and the end prints a second link for the phone and
  the hint: in the UI, `live` → the QR code. Turn it on or off later: the same line with
  `--phone` or `--no-phone`.
- **The same line again updates** to the newest release: a copy of the old `compose.yaml`
  is kept, `.env`, `secrets/` and the home volume stay, only `LADO_VERSION` changes, and
  the link opens again. On the newest already, it just starts LADO and opens the link. It
  never goes back to an older version (the guide's way back stays).
- **It never touches another LADO**: a LADO container made by hand from another folder
  stops it, with that folder named.
- **Windows**: the PowerShell line checks Docker Desktop (starting it when it is not
  running), finds Ubuntu in WSL or offers to install it (`wsl --install -d Ubuntu`:
  administrator rights, maybe a restart; then open Ubuntu once and run the line again),
  checks that Docker Desktop's WSL integration is on for it, and runs the same installer
  inside it. The link opens in Windows' browser; the workspace is
  `\\wsl.localhost\Ubuntu\home\<you>\workspace` in Explorer.
- **The manual way stays** in docs/install.md, "By hand", for people who want each step;
  the guide also shows how to download the script, read it and then run it.

## Decided with the human

- One shell script for macOS, Linux and WSL, attached to every release; a thin
  PowerShell front for Windows that runs it in WSL's Ubuntu (#2083 point 1, #2092 point
  1: option (a)). Native Windows paths are not possible: the workspace must be a Linux
  path for the agents' worktrees to open on the computer.
- Questions only for the workspace and a missing git identity; everything else detected
  (#2083 point 2).
- No Docker install by the script; Docker Desktop started when installed (#2083 point 3).
- The link printed and opened (#2083 point 4).
- A rerun updates; no downgrade (#2083 point 5).
- Out of scope: a second LADO for users, the CLIs' logins, Windows without WSL2 (#2083
  point 6, #2092).
- The phone in scope, always asked after its warning, Enter = no (#2092 point 2).
- The scripts' texts are English (#2083 point 7).
- The human runs the RC's `install.ps1` on a real Windows before the release (#2092
  point 3).

## Decisions for the record

- The version is stamped into the scripts at release (D2): the script, its
  `compose.yaml` and its image always agree; no GitHub API call, no rate limit.
- POSIX `sh` with questions from `/dev/tty` (D3), so `curl | sh` asks too, and the whole
  script runs only once fully downloaded.
- `.env` and `compose.yaml` are written whole and moved in place (spec "Every stop of the
  installer says what and what to do"), so a failure leaves the old files.
- `--dir`, `--image`, `--source` exist for the container test and the release check
  (docs/release.md); README does not name them.
- Port: the first free from 8765 to 8799.
- Tests: the scripts run with fake `docker`, `curl` and friends (unit), and a real install
  with Docker (container layer); the PowerShell script by its text and its parser, and by
  the human's run.

## How it is checked

- `make test`: `tests/test_install_sh.py`, `tests/test_install_ps1.py`,
  `tests/test_stamp_installers.py`, `tests/test_release_workflow.py`,
  `tests/test_docker.py`.
- `make docker && make test-container`: `tests/container/test_install.py` (CI's container
  cell runs it on every push).
- The release check (docs/release.md, 4.5): the RC's `install.sh` on a Mac with Docker
  Desktop, and its `install.ps1` on Windows 11 with Docker Desktop, by the human.
