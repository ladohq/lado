# gVisor spike, round 3: Docker Desktop on Windows

> The brief for round 3, short, **not run yet** (2026-11-26). Round 2 checked Windows
> only through Docker Engine inside WSL2 ([S4](s4-windows-wsl2.md)): GitHub's runner has
> no Docker Desktop. The kernel is the same, but Docker Desktop's own parts were not
> checked: its own VM, file sharing with `C:\`, the integration with the WSL
> distribution, ECI, and `docker compose` run from PowerShell. That is how Windows users
> will install LADO (`install.ps1`). About 1-1.5 hours per machine. Saved as written; the
> Russian preface for the human is replaced by this note.

## 0. Context and what we already know

LADO runs teams of AI coding agents (Claude Code, Codex, OpenCode, Kilo) in tmux. The
candidate layout is a `lado` container (control panel) plus a `runner` container. Inside
`runner`, each LADO session runs in its own gVisor sandbox (`runsc run`), in its own netns
whose iptables rules let it reach only a proxy in the runner. The same code must work on
macOS, Windows and Linux, installed with `docker compose` and an install script.

Two earlier rounds (macOS with Docker Desktop; Linux x86/arm64 and WSL2 with Docker Engine
28.0.4; runsc `release-20261123.0`) established the following. **Do not re-derive it;
check that it holds under Docker Desktop.**

- **Profile R+net works everywhere tested**, with this compose fragment for `runner`:

  ```yaml
  runner:
    init: true
    cap_drop: [ALL]
    cap_add: [SYS_ADMIN, NET_ADMIN, NET_RAW, SETUID, SETGID, SETFCAP]
    security_opt:
      - seccomp=./seccomp/runner-narrow.json   # fallback: runner.json
      - apparmor=unconfined                   # no AppArmor in WSL; harmless
      - no-new-privileges:true
    sysctls: [net.ipv4.ip_forward=1]
  ```

  - `runner.json` is Docker's default seccomp profile plus `pivot_root` and `chroot`.
  - `runner-narrow.json` additionally cuts the profile's `CAP_SYS_ADMIN` block down to
    `clone clone3 mount setns umount2 unshare`.
  - Each of the six capabilities is needed.
- **Profile R** (rootless runsc, no capabilities) is **not** a candidate any more: a process
  of the runner's uid can `ptrace` the sentries of other sandboxes. Skip R here.
- **WSL2 under Docker Engine:**
  - `/dev/kvm` exists, but `--platform=kvm` is slower than systrap (nested virtualization).
  - A bind mount from `C:` (drvfs/9p) breaks git as uid 1000 and is about 200× slower for
    small files.
  - ext4 inside WSL and a named volume behave like Linux.
  - Git for Windows checks files out with CRLF (`core.autocrlf=true`), and bash then fails
    with `set: -\r: invalid option`.
- **Speed, B/A on the container's disk (WSL2, Docker Engine):** `git status` 5.2×, small
  files 1.8×, 2000 exec 5.5×.
- Traps found so far:
  - the runsc release is a tarball (`…/release/<ver>/<arch>/gvisor.tar.bz2`), and runsc
    looks for `gvisor-bin/` beside itself;
  - a netns is single-use: recreate it before each run;
  - without `init: true` the runner collects zombies;
  - filter containers by label, not by name substring.

**Reuse the scripts of round 2** (the repository or tarball of the Linux/Windows runs:
`docker/Dockerfile`, `scripts/netns.sh`, `mkspec.py`, the smoke check, `bench.sh`,
`proxy.py`, the isolation and network checks, `seccomp/runner*.json`). Same scripts, same
numbers. **Check them out with LF line endings** (`git clone -c core.autocrlf=false`, or
`.gitattributes` with `* text=auto eol=lf`); otherwise you will hit the CRLF trap of round 2.

## 1. Rules

- No real secrets: no logins to agent CLIs, no API keys.
- Raised privileges only on this spike's containers. Record any Docker Desktop setting you
  change and restore it at the end.
- Everything goes in `%UserProfile%\gvisor-spike-3\` (or `~/gvisor-spike-3/` in the WSL
  distribution, if a step needs it; say which). Before starting, take a snapshot of
  `docker ps -a`, `images`, `volume ls`, `network ls` and `system df`; compare after cleanup.
- Label every container, network, volume and image `lado.spike=3`; clean up by that label.
- Report in `REPORT.md` next to the scripts, then pack the folder into
  `gvisor-spike-3.tar.gz` (or `.zip`). Send nothing anywhere yourself. REPORT.md must be
  readable without the archive.
- About 1–1.5 hours. When a step fails: the exact error, at most two or three variants,
  move on.

## 2. Environment (record all of it)

- Windows edition and build (`winver` or `[Environment]::OSVersion`), CPU model, cores,
  RAM, free disk; bare metal or VM. x86-64 or ARM64 (Snapdragon): say which, it matters.
- WSL: `wsl --version`, `wsl --status`, `wsl -l -v` (expect `docker-desktop` among the
  distributions), the kernel (`wsl -d docker-desktop uname -a` or `docker run --rm alpine
  uname -a`), and `%UserProfile%\.wslconfig` if it exists.
- Docker Desktop: version; backend (WSL2 or Hyper-V); resources (CPU, memory, disk);
  **Enhanced Container Isolation** (on or off; it is a paid-plan feature); "Use containerd
  for pulling and storing images"; WSL integration with which distributions.
- `docker version`, `docker info` in full: storage driver, cgroup version, Security Options,
  default runtime.
- KVM: `docker run --rm --device /dev/kvm alpine ls -l /dev/kvm`.
- The seccomp profile Docker Desktop's engine uses by default: record the engine version and
  take `default.json` from `moby/moby` at that tag (as in round 2), so the narrow profile can
  be rebuilt on top of it if the provided one fails.

## 3. Checks

All on profile R+net unless said otherwise.

### 3.1 Install path: `docker compose` from PowerShell

This is the main new question. LADO's users on Windows will run `docker compose up` from
PowerShell (through `install.ps1`), with the compose file and the seccomp profile on the
Windows disk.

1. Put `compose.yaml` with the fragment above (plus a `build:` of the runner image) and
   `seccomp/runner-narrow.json` in `%UserProfile%\gvisor-spike-3\`. Run
   `docker compose up -d --build` **from PowerShell**, not from WSL.
   - Does the relative path in `security_opt: seccomp=./seccomp/…` resolve? If not, what
     form works (absolute Windows path, forward slashes, `${PWD}`)? Record the exact error.
   - Does the image build when the build context was checked out by Git for Windows with
     its defaults (CRLF)? Try once on purpose with CRLF, then with LF; record what breaks
     (a shell script `COPY`'d into the image and run, a JSON profile).
2. The same `compose.yaml` started from inside the WSL distribution (Docker Desktop's WSL
   integration), for comparison: same result?
3. Run the smoke check (sandbox starts; `git status`; tmux send-keys and capture;
   `codex sandbox -- true`; curl through the proxy) with `runner-narrow.json`. If it fails,
   try `runner.json`, then find the difference.

### 3.2 Privileges and compatibility

1. Short privileges table with `runsc run`: P1 `--privileged`, R+net with `runner.json`,
   R+net with `runner-narrow.json`, P6 plain defaults. One table.
2. The full compatibility list of round 2 (git clone/status/worktree, tmux and `-L lado`,
   `uv sync` + `lado --version`, `npm ci`, gcc, the four CLIs' `--version` and screens,
   `codex sandbox`, bwrap, `unshare -U -r`, ps/df/meminfo/ulimit, inotify in the sandbox and
   on a volume), as uid 1000 in the sandbox.

### 3.3 Where repositories can live: four places

Measure W2 (all three parts), W6py and W7, median of three runs, A (plain container) and
B (R+net), with limits `--cpus 4 --memory 4g` (or less; record them):

1. **local:** the container's own disk / the sandbox's rootfs;
2. **named volume;**
3. **a Windows folder** (`C:\Users\<you>\…`) bind-mounted by Docker Desktop's file sharing
   (`-v C:\Users\…:/work` from PowerShell). This is Docker Desktop's own mechanism, not the
   drvfs of round 2. Does git clone work there as uid 1000? What are the owner and mode
   bits? Does `chmod -x` show in `git status`?
4. **a folder in the WSL distribution's ext4** (`\\wsl$\Ubuntu\home\<user>\x`, mounted from
   inside the distribution), if a distribution with WSL integration is present.

Also, once: a clone **from PowerShell with Git for Windows** into place 3, then
`git status` inside the sandbox. Is it clean, or do CRLF and mode bits show as changes?

### 3.4 Network and isolation

1. The proxy-only setup (iptables in the runner): for uid 1000 and for root inside the
   sandbox, direct internet and other proxy ports blocked, the proxy reachable, rules
   unchanged after the attempts.
2. Isolation: two `runsc run -d` sandboxes with separate rootfs copies and the runner marker
   with a random string. Processes, files, TCP to the other sandbox, the runner's services,
   `docker.sock`: all closed?
3. Docker Desktop specific: can the sandbox reach `host.docker.internal` or the Windows
   host's services directly (bypassing the proxy)? It must not.

### 3.5 Docker Desktop features (optional, if available)

- **ECI** (Enhanced Container Isolation), if the plan has it: switch it on, try to start the
  runner with the fragment above. ECI is expected to refuse or change `cap_add` and
  `security_opt`; record the exact behaviour. We need to know whether LADO must tell users
  "turn ECI off" or can live with it. Switch it back off afterwards.
- **Hyper-V backend**, if offered: repeat 3.1 step 3 and W2 + W7 on local.
- **`--platform=kvm`** with `devices: [/dev/kvm]`, if `/dev/kvm` reaches the container: W2 and
  W7 on local against systrap.
- **Restart survival:** stop Docker Desktop (or `wsl --shutdown`) and start it again. Does
  `docker compose up -d` bring the runner back with its sandboxes' state on the volume? (The
  sandboxes themselves need not survive; record what does.)

## 4. Report format

1. **Summary** (5–10 lines): does R+net work under Docker Desktop; does the PowerShell
   compose path work as written (and what had to change); where repositories can live; the
   main speed numbers next to round 2's WSL2 numbers; ECI's answer; blockers; what was cut.
2. **Environment.**
3. **Install path (3.1).**
4. **Privileges and compatibility (3.2).**
5. **Places for repositories (3.3):** one table, A, B and B/A per place, with round 2's WSL2
   column for comparison.
6. **Network and isolation (3.4).**
7. **Docker Desktop features (3.5)**, whatever was done.
8. **Problems and surprises.**
9. **Cleanup:** the snapshots before and after match.

## 5. Cleanup

Remove everything labelled `lado.spike=3`, and any buildx builder you created with its
state volume, by name. Restore the Docker Desktop settings you changed (ECI, backend,
resources). Compare against the snapshot taken before. Leave the spike folder in place.
