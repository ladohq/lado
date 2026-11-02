Task: LAD-164

## Why

Symptom: LADO's Docker install is the recommended one, yet a person who is not a
programmer stops on its steps. They must check the shell for stray `LADO_*` variables,
make a folder, download `compose.yaml`, write `.env` by hand (the newest version's number
from the releases page, the workspace's full path, git's name and email, the ssh agent's
socket), make the workspace folder, then run two `docker compose` commands and copy the
link. An update is four more steps by hand, and Windows has no way at all ("not checked
yet").

Cause: the Docker way was built as a compose file plus a guide (changes `image-on-ghcr`,
`projects-at-host-path`, `container-secrets-and-git`). Everything the computer itself knows
(the version of the release, the home folder, `git config`, the ssh agent, a free port, the
computer's network name) is still typed in by the human. Nothing runs these steps for
them.

The human's decisions (questions #2083 and #2092 of this run; the research in the run's
artifact `research-installers`):

- One POSIX script, `install.sh`, for macOS, Linux and Windows inside WSL2, attached to
  every GitHub release as `compose.yaml` is, run as `curl -fsSL
  https://github.com/ladohq/lado/releases/latest/download/install.sh | sh`.
- Windows: a thin `install.ps1` for PowerShell, `irm
  https://github.com/ladohq/lado/releases/latest/download/install.ps1 | iex`, that checks
  Docker Desktop, finds or offers to install Ubuntu in WSL, and runs the same `install.sh`
  inside it. The human checks it by hand on a real Windows before the release.
- The script asks only what it cannot learn: the workspace folder (default `~/workspace`,
  made when missing) and git's name and email (not asked when the computer's `git config
  --global` has them). The version is the script's own release; the port 8765 or the next
  free one; the ssh agent when there is one. `--yes` takes every default.
- Without Docker it stops and says where to get it; it never installs Docker. A Docker
  Desktop installed but not running is started and waited for.
- At the end it starts LADO, waits for the server, prints the UI's link and opens it in
  the browser.
- The same command again updates to its release, keeping `.env`, `secrets/` and the home
  volume, and opens the link; it never goes back to an older version.
- The phone: always asked, after a warning in plain words; Enter means no; `--phone` and
  `--no-phone` answer beforehand.
- The texts of the scripts are English, as all of LADO.

Options weighed (root cause: nothing runs the steps the computer can answer itself):

- (a, taken) A shell script per release, stamped with its version, plus a thin PowerShell
  front for Windows that runs the same script in WSL. One implementation of the steps;
  the release's file is what a user gets, so the script and its `compose.yaml` and image
  always agree. Long-term cost: a POSIX shell script of a few hundred lines kept by unit
  tests (fake `docker` and friends on PATH, a pty for the questions) and a container test;
  the `.ps1` is checked by text and by hand only (CI's Windows runners have no Linux
  containers).
- (b) An installer inside the image (`docker run ghcr.io/ladohq/lado setup`). Nothing to
  download but Docker, but the image does not see the host's `git config`, ssh agent,
  free ports or browser, and to run compose it needs the host's Docker socket, which is
  root on the host. Rejected.
- (c) A native Windows way with the workspace on `C:\`. The container mounts the workspace
  at the host's own path (requirement "The compose file mounts the workspace at the
  host's path"), so a worker's worktree opens on the host; a `C:\…` path does not exist in
  a Linux container, an NTFS mount is many times slower and loses the files' modes. It
  would also be a second installer. Rejected.
- (d) Documentation only (WSL steps, a better guide). Costs nothing, but leaves the steps
  with the human. Rejected.

Held against the design principles: neutral core (no Python of LADO changes; the scripts
know no agent CLI); one source of truth (the version is stamped from the release tag; the
script downloads that tag's `compose.yaml` and never keeps a copy; `.env` stays the one
place of settings, which the manual way reads too); no silent drops (every stop names what
is wrong and what to do; a stray shell variable, a missing git identity, a changing ssh
socket or IP is said); only what is used (`--dir` and `--image` exist for the container
test and the release check, which use them).

## What Changes

- **`docker/install.sh`** (new): checks Docker, writes or updates `.env` in
  `~/lado-docker` (or `--dir`), downloads its release's `compose.yaml`, starts LADO, waits
  for the server, prints and opens the UI's link; a rerun updates. Flags `--yes`,
  `--phone`, `--no-phone`, `--version`, `--dir`, `--image`, `--source`, `--no-open`,
  `--help`.
- **`docker/install.ps1`** (new): the PowerShell front for Windows.
- **The release workflow** stamps both scripts with the tag's version
  (`scripts/stamp_installers.py`) and attaches them to the GitHub release beside
  `compose.yaml`.
- **README's Install → Docker and Update → Docker** become the installer's one line per
  system; **docs/install.md**'s Docker section leads with it and keeps the manual compose
  way below it as "By hand"; the Systems row names Windows through `install.ps1`.
- `docker/compose.yaml`'s header names the installer as the short way.
- docs/release.md: the RC check runs the RC's `install.sh` (macOS) and `install.ps1`
  (Windows) once.
- CHANGELOG.md: `## 0.44.0 (unreleased)`, Added. A feature: the minor version (0.44.0,
  already the unreleased one, no RC tagged yet; if 0.44.0's RC is tagged before this
  merges, main is frozen and the line goes under a new `## 0.45.0 (unreleased)`).

## Scope

- `install.sh`: fresh install, rerun with the same version, update, refused downgrade, the
  phone's question and flags, a second LADO's container never replaced.
- `install.ps1`: Docker Desktop's check and start, Ubuntu in WSL found or offered, Docker's
  WSL integration checked, `install.sh` of the same release run in Ubuntu.
- The release's assets, stamped.
- README, docs/install.md, docs/release.md, the compose header, CHANGELOG.md.
- Tests: unit (the scripts with fakes, the stamp, the workflow, the docs), container (a
  real install, rerun and update with real Docker).

## Out of scope

- Installing Docker itself: on a Mac Docker Desktop is a graphical install, on Linux it
  needs sudo; the script names where to get it.
- Windows without WSL2 (Docker Desktop on the old Hyper-V backend, Windows Pro only):
  Docker Desktop's own default needs WSL2, and the workspace must be a Linux path; the
  `.ps1` says so.
- A second LADO by the script for users: README stays one LADO in `~/lado-docker`;
  `--dir` is documented in `--help` and docs/release.md only, for checks. The guide's
  manual second LADO stays.
- Logging in to the agent CLIs: the UI's Settings → Providers and environment does it.
- Going back to an older version: the guide's manual way back stays; the script refuses.
- Removing LADO: the guide's removal stays.
- Checksums or signatures of the scripts: they come from the GitHub release over https,
  as `compose.yaml` does; the guide shows the download-read-run way too.
- A PyPI install script: the PyPI way is for people who already have their CLIs.

## Acceptance criteria

- AC-1: On a Linux or macOS machine with Docker running and no LADO, `curl -fsSL
  https://github.com/ladohq/lado/releases/latest/download/install.sh | sh` asks for the
  workspace (Enter: `~/workspace`, made), takes git's name and email from `git config
  --global` (asks only when missing), asks about the phone (Enter: no), writes
  `~/lado-docker/.env` and the release's `compose.yaml`, starts the container, prints
  `http://127.0.0.1:<port>/?token=…` and opens it in the browser; the UI answers.
- AC-2: With `--yes`, or with no terminal, it asks nothing and takes the defaults; a
  missing git identity is then said as a warning.
- AC-3: Docker missing, or `docker compose` missing: the script stops before it writes
  anything, naming Docker Desktop's page (macOS, WSL) or Docker Engine's install (Linux).
  Docker Desktop installed but not running on macOS: it is started and waited for up to
  120 s. A Docker the user may not use (permission denied): the script says how to join
  the `docker` group and stops.
- AC-4: Port 8765 taken: the next free port up to 8799 goes into `.env` and the link.
- AC-5: `LADO_*` or `COMPOSE_*` variables in the shell do not reach the script's compose;
  the script names them and says to unset them before running compose by hand.
- AC-6: A LADO container of the same compose project made from another folder: the
  script stops and names that folder; nothing is replaced.
- AC-7: The phone, answered yes (or `--phone`): the warning is printed before the
  question; `.env` gets `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=<name>.local` (Linux
  without mDNS: the current address, with a warning that it may change); the end prints
  the phone's link and the hint `live → QR code`.
- AC-8: A rerun with `.env` of an older version: `compose.yaml.bak` is kept, the release's
  `compose.yaml` downloaded, only `LADO_VERSION` changed in `.env` (other lines, the
  user's own too, kept), `secrets/` and the home volume untouched, the link opened. The
  same version: nothing rewritten, the container started, the link opened. A newer
  version in `.env`: refused, pointing to the guide's way back. `--phone` / `--no-phone`
  on a rerun add or remove the two lines.
- AC-9: An unstamped `install.sh` (the repository's file) without `--version` refuses.
- AC-10: Every GitHub release has `install.sh` and `install.ps1` stamped with its version
  beside `compose.yaml`; `releases/latest/download/install.sh` is the newest final's.
- AC-11: On Windows 11 with Docker Desktop, `irm …/install.ps1 | iex` in PowerShell: with
  no Ubuntu in WSL it offers `wsl --install -d Ubuntu` and says to rerun after Ubuntu's
  first start; with Ubuntu and Docker's WSL integration it runs the same release's
  `install.sh` there, and the link opens in Windows' browser; without the integration it
  says where to switch it on. Checked by hand by the human before the release.
- AC-12: README's Docker install and update are the one line (and the PowerShell line);
  docs/install.md leads with it, keeps the manual way and names the download-read-run
  way.
