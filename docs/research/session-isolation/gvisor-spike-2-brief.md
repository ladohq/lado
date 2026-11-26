# gVisor spike, round 2: Linux, Windows and a narrow seccomp profile

> The brief for round 2. Round 1 (macOS, [S1](s1-macos.md)) showed that gVisor works
> inside a Docker Desktop container. Round 2 asks three questions: the same on **Linux**
> (with KVM, AppArmor, the `kvm` platform); the same on **Windows** (WSL2); and whether a
> **narrow seccomp profile** can replace `seccomp=unconfined`, and how many rights the
> runner really needs. One brief for all machines; each machine wrote its own report:
> [S2](s2-macos-phase-b.md) (macOS, Phase B only), [S3](s3-linux.md) (Linux),
> [S4](s4-windows-wsl2.md) (WSL2). Saved as given to the agents; the Russian preface
> for the human is replaced by this note.

## 0. Context and what we already know

LADO runs teams of AI coding agents (Claude Code, Codex, OpenCode, Kilo) in tmux. The
candidate layout is a `lado` container (control panel, core, keys, a proxy) plus a `runner`
container. Inside `runner`, each LADO session runs in its own gVisor sandbox (`runsc run`).
The same code must work on macOS, Windows and Linux.

The first spike (macOS 27, Apple M2, Docker Desktop 4.100, runsc `release-20261123.0`)
established the following. **Do not re-derive it; check that it still holds on your
machine.**

- **Profile R+net works.** `cap_add: [SYS_ADMIN, NET_ADMIN]`,
  `security_opt: [seccomp=unconfined, apparmor=unconfined]`,
  `sysctls: [net.ipv4.ip_forward=1]` and `init: true`. In the runner, each sandbox gets a
  netns with a veth pair and NAT. `config.json` points `linux.namespaces` → `network` at
  `/var/run/netns/sN`, and the sandbox is started with `runsc --ignore-cgroups run`. With
  this, Phase 2 passes as uid 1000, and so do nested bwrap, `unshare -U` and
  `codex sandbox`.
- **Profile R** is `seccomp=unconfined`, no capabilities, and `runsc --rootless` run as uid
  1000 of the runner. It works, but only for root inside the sandbox, with network `none` or
  `host` only, and without nested sandboxes.
- **P5 and P6 fail.** P5 is `SYS_ADMIN` with the default seccomp; P6 is the plain defaults.
  The causes are `pivot_root` EPERM and `clone` with namespace flags EPERM.
- **`runsc do` with a network** works only under `--privileged`, because it runs
  `sysctl -w` itself. Use `runsc run` everywhere except quick smoke tests.
- **Speed vs a plain container, on the container's own disk:**
  - CPU: 1.0×.
  - Tests: about 2×.
  - `git status`: about 6×.
  - exec: about 4.7×, roughly 1 ms per exec.
  - Small files from one process: 1.5×.

  A macOS bind mount (VirtioFS) is 21× slower for `git status` even without gVisor.
  `--file-access-mounts=exclusive` gains at most 10%. `--overlay2=root:self` (the default) is
  the right choice.
- **Network.** iptables in the runner's netns limits a sandbox to the proxy only (`FORWARD`
  from `veth-+`, `INPUT` reject), and nothing inside the sandbox can undo it. Docker's DNS
  `127.0.0.11` is not reachable from the netns. With a proxy, the sandbox needs no DNS.
- **Isolation.** Processes, files and the runner marker were all closed. The network
  between sandboxes stays open until the iptables rules are in place. In R+net the
  sentry runs as uid 0 of the runner with reduced capabilities.
- **Traps already found:**
  - The release is now an archive. `…/release/<ver>/<arch>/gvisor.tar.bz2` contains `runsc`,
    `containerd-shim-runsc-v1` and `gvisor-bin/` (`gvisor_sentry`, `runsc-netgofer`, ...),
    and runsc looks for them beside itself. The old `/runsc` URL returns 404.
  - A netns is single-use: gVisor takes eth0's address and does not give it back. Recreate
    the netns before each run.
  - Without `--init` the runner collects zombie processes.
  - `docker ps --filter name=spike-` matches a substring and also catches buildx builders.
    Filter by exact names or by a label.
  - Codex 0.172 uses `codex sandbox [COMMAND]`, without `linux`.

**Reuse the first spike's scripts if you have them** (`gvisor-spike.tar.gz` from the macOS
run: `docker/Dockerfile`, `scripts/netns.sh`, `mkspec.py`, `p2-compat.sh`, `bench*.sh`,
`proxy.py`, `p5-probe.sh`). Same scripts, same numbers, comparable results. If you do not
have them, write your own from the description above and the first brief.

**Pin runsc to `release-20261123.0`,** the version of the first spike. Optionally, add one
row with the latest release.

## 0.1 Update after Phase B on macOS (report `report-0fd8e24e.md`)

Phase B is done on macOS. Results:
- **R+net:** Docker's default seccomp profile plus `pivot_root` and `chroot` is enough
  (`runner.json`). Capabilities: `cap_drop: [ALL]` plus `SYS_ADMIN NET_ADMIN NET_RAW SETUID
  SETGID SETFCAP`, and `no-new-privileges` works.
- **R:** the default profile plus `clone mount umount2 pivot_root chroot`
  (`runner-rootless.json`), with no capabilities.
- The sentry runs in its own user namespace and does not hold the runner's SYS_ADMIN or
  NET_ADMIN.
- Docker 29 keeps the default profile at `vendor/github.com/moby/profiles/seccomp/default.json`.

Take `seccomp/runner.json`, `runner-rootless.json` and the scripts from that run's tarball
(`gvisor-spike-2.tar.gz`) as the starting point. **On Linux and Windows, Phase B shrinks to
four steps:**
1. Confirm that `runner.json` + the six capabilities pass the smoke check and the isolation
   check here. If not, find the difference.
2. AppArmor (Linux only): is `apparmor=unconfined` needed, or does `docker-default` (or a
   small custom profile) work?
3. Optional: narrow the `CAP_SYS_ADMIN` block of the profile (`bpf`, `perf_event_open`,
   `fsopen`/`fsmount`, `syslog`, `sethostname`, ...) to what runsc needs.
4. Optional, profile R: can one sentry `ptrace` another sentry under the same uid 1000
   (Yama `ptrace_scope`, dumpable)?

Phase A (with speed) and the platform appendix stay as they are; on Windows, Phase A.3 can
be limited to W2, W6py and W7 in the three bind places.

## 1. Rules (unchanged)

- No real secrets: no logins to agent CLIs, no API keys.
- Raised privileges only on this spike's containers. Record any Docker setting you change
  and restore it at the end.
- Everything goes in `~/gvisor-spike-2/`: scripts, Dockerfile, raw logs, CSV. Before
  starting, take a snapshot of `docker ps -a`, `images`, `volume ls`, `network ls` and
  `system df`; compare it after cleanup.
- Label every container, network, volume and image `lado.spike=2` and clean up by that
  label.
- Report in `~/gvisor-spike-2/REPORT.md`, then pack it:
  `tar czf ~/gvisor-spike-2.tar.gz -C ~ gvisor-spike-2`. Send nothing anywhere yourself.
  End with the paths and the Summary for the human. REPORT.md must be readable without the
  tarball.
- About 2–3 hours per machine. When a step fails: the exact error, at most two or three
  variants, move on.

## 2. Environment (record all of it)

- OS, kernel (`uname -a`), distribution and version, CPU model, cores, RAM, free disk.
  Bare metal or VM; for a VM, the cloud and the instance type.
- Docker: `docker version`, `docker info` in full. Note the storage driver, cgroup version
  and driver, Security Options (seccomp, apparmor, selinux, userns, rootless), the default
  runtime, and whether `runsc` is already registered as a runtime (it must not be needed).
- Security modules on the host: `cat /sys/kernel/security/lsm`, `aa-status` (AppArmor),
  `getenforce` (SELinux), and
  `sysctl kernel.apparmor_restrict_unprivileged_userns kernel.unprivileged_userns_clone user.max_user_namespaces`.
- KVM: `ls -l /dev/kvm` on the host, `grep -cE 'vmx|svm' /proc/cpuinfo`, and
  `docker run --rm --device /dev/kvm alpine ls -l /dev/kvm`.
- Landlock: `docker run --rm --privileged alpine sh -c 'mount -t securityfs none /sys/kernel/security 2>/dev/null; cat /sys/kernel/security/lsm'`.
  Also run a real check: a small C or Python program that calls
  `landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)` inside an
  **unprivileged** container, and print the ABI version or the error. The first spike could
  not see Landlock at all; we want a real answer.

## 3. Phase A: the first spike's checks on this machine

Repeat the first spike's phases in a reduced form, with the same scripts, on profiles
**R+net** and **R**:

1. **Privileges (short):** run P1, P2, R+net, R, P5 and P6 with `runsc run` (not `do`),
   and say for each whether it starts. One table.
2. **Compatibility:** the first spike's full Phase 2 list (git, tmux, uv, npm, gcc, four
   CLIs with screens, `codex sandbox`, bwrap, `unshare -U`, inotify). R+net is mandatory;
   R is optional.
3. **Speed:**
   - Plain container (A) against gVisor R+net (B), on the container's disk (local):
     W1 (`--no-local` clone of django from a local bare cache), W2 (all three parts), W3 and
     W4 warm, W5 (the same pytest subset), W6py, W7 and W8.
   - The same on a **bind mount** of a host folder, for the bind-mount question of your
     platform (see your appendix).
   - Median of three runs.
   - Limits `--cpus 4 --memory 4g`, or less if the machine is smaller; record them.
4. **Network:** the proxy-only setup (iptables in the runner, as in the first spike's 6.3a).
   Check that it holds against root inside the sandbox.
5. **Isolation:** the first spike's Phase 5 (two `runsc run -d`, separate rootfs from
   `spike-sandbox`, the runner marker with a random string), on R+net with the iptables
   rules applied.

## 4. Phase B: a narrow seccomp profile instead of `unconfined` (all platforms)

**Goal:** the smallest change to Docker's default seccomp profile under which R+net (and, as
a second step, R) still passes Phase A's smoke check. The smoke check is:
- the sandbox starts;
- git status;
- tmux send-keys and capture;
- `codex sandbox -- true`;
- curl through the proxy.

Steps:

1. Take Docker's default profile for **this engine version**: `profiles/seccomp/default.json`
   from `moby/moby` at the tag that matches `docker version`. Record the URL and commit. Save
   it as `seccomp/default.json`.
2. Start with the default profile plus R+net's capabilities. Note that Docker's default
   profile already allows some calls only when `CAP_SYS_ADMIN` is present (the
   `includes.caps` blocks). Record what still fails.
3. Find the blocked calls. Use any of:
   - the kernel audit log (`SCMP_ACT_LOG` instead of `SCMP_ACT_ERRNO` as `defaultAction`,
     then `dmesg` or `journalctl -k | grep -i seccomp`);
   - `strace -f` of runsc in a privileged copy of the runner;
   - bisecting by adding calls.

   Expected candidates: `pivot_root`, `mount`, `umount2`, `unshare`, `setns`, `clone` and
   `clone3` with namespace flags, `ptrace` (systrap), `process_vm_readv/writev`,
   `seccomp`, `keyctl`, `bpf`?, `perf_event_open`?. Check every one; do not assume.
4. Make `seccomp/runner.json`: the default profile plus the minimal additions, each with a
   comment in the report saying why it is needed (which runsc component calls it, for what).
5. Run Phase A's smoke check with `runner.json`, then Phase A.5 (isolation) once more.
6. **AppArmor** (Linux with AppArmor only): check whether `apparmor=unconfined` is really
   needed. Try Docker's `docker-default` profile. If it blocks `mount` or `pivot_root`, try a
   small custom profile (load it with `apparmor_parser`), and record what it needs.
7. **Capabilities:** try dropping capabilities from Docker's default set that runsc does not
   need (`--cap-drop ALL` plus only what is needed). Record the smallest set that works for
   R+net.

**Result:**
- `runner.json` in full in the tarball, and the diff against `default.json` in the report;
- the final compose fragment for `runner`: `cap_add`/`cap_drop`, `security_opt`, `sysctls`,
  `init`, `devices`;
- a statement of what an escape from the sentry would get with this profile, compared with
  `unconfined`.

## 5. Phase C (optional, last): a micro-VM for comparison

Only on a Linux machine with `/dev/kvm`, and only when A and B are done. Pick the easiest:
- Kata Containers 4.x as a Docker or containerd runtime on the host;
- Firecracker's `firecracker` with a ready kernel and an ext4 rootfs of `spike-sandbox`.

Measure W2 (status), W6py, W7 and W8 in it, on the guest's own disk. This gives one row
"micro-VM" next to A and B. It answers how much faster a micro-VM is than gVisor on our
workloads. Record the setup effort honestly; it matters as much as the numbers.

## 6. Report format

1. **Summary** (5–10 lines): whether R+net and R work here, the final narrow profile, the
   main speed numbers next to the macOS ones, blockers, and what was cut.
2. **Environment.**
3. **Phase A:** privileges, compatibility, speed (tables A, B and B/A, with a column for
   the macOS spike's B/A for comparison), network, isolation.
4. **Phase B:** the seccomp diff with reasons, AppArmor, capabilities, the final compose
   fragment, what an escape gets.
5. **Phase C**, if done.
6. **Platform appendix results** (section 7 or 8).
7. **Problems and surprises.**
8. **Cleanup:** the snapshots before and after match.

## 7. Appendix: Linux

Machine: preferably **Ubuntu 24.04 or newer on bare metal** or on a cloud VM with nested
virtualization: AWS C8i/M8i, GCP Intel, Azure Dv5. Not Hetzner Cloud, not Graviton. Docker
Engine from Docker's apt repository, not Docker Desktop for Linux. If a second machine is
at hand, Fedora with SELinux is a useful extra row for Phase A.1 and the smoke check.

Additionally:

- **Platform `kvm`:** start the runner with `--device /dev/kvm` and run the sandbox with
  `--platform=kvm`. Run Phase A.3's speed set with systrap and with kvm, and say which is
  faster where.
  - Does `kvm` need anything beyond `--device /dev/kvm`, such as group membership?
  - Does it work in profile R (rootless)?
- **AppArmor userns restriction:** Ubuntu 24.04 restricts unprivileged user namespaces
  through AppArmor (`kernel.apparmor_restrict_unprivileged_userns=1`). Check:
  - whether it affects R (rootless runsc);
  - whether it affects nested bwrap or `codex sandbox` inside the sandbox in R+net.

  Record the sysctl value. Do not change it on the host unless you also record the effect
  of leaving it as is.
- **Bind mounts:** a bind mount of a host ext4 folder. Here we expect close to native
  speed in A. Measure A and B on bind against local, so we see gVisor's own cost on a bind
  mount without VirtioFS in the way.
- **Rootless Docker** (optional): if time allows, try R and R+net under rootless Docker
  (`dockerd-rootless-setuptool.sh`), and say which profile still works there.
- **Podman** (optional): the same with rootful `podman run`, a smoke check only.

## 8. Appendix: Windows

Machine: Windows 11 x86-64 with Docker Desktop on the **WSL2 backend** (the default).
Record:
- the Windows build;
- the WSL version (`wsl --version`);
- the kernel inside WSL (`wsl uname -a`);
- Docker Desktop's version and settings: WSL2 or Hyper-V backend, resources, and Enhanced
  Container Isolation (it must be off).

Additionally:

- **KVM:**
  - Is `/dev/kvm` available in WSL2 (`wsl ls -l /dev/kvm`)?
  - Is `nestedVirtualization` set in `%UserProfile%\.wslconfig`?
  - Does `docker run --rm --device /dev/kvm alpine ls -l /dev/kvm` work under Docker Desktop?

  If `/dev/kvm` reaches the container, run `--platform=kvm` as in the Linux appendix.
- **Bind mounts, three places, measured as in A.3:**
  1. a folder on the Windows disk (`C:\Users\...`, through Docker Desktop's file sharing);
  2. a folder inside the WSL2 distribution's ext4 (`\\wsl$\...`, for example
     `/home/<user>/x` in Ubuntu-on-WSL, mounted from there);
  3. a named volume.

  We expect (1) to be very slow. Record how much, for A and B.
- **Line endings and permissions:** after a clone on bind (1), check that `git status` is
  clean (`core.autocrlf`, the executable bit). Record any surprises.
- If Docker Desktop offers the Hyper-V backend on this machine, optionally repeat Phase A.1
  and A.3 (W2 and W7 only) on it.

## 9. Cleanup

Remove everything labelled `lado.spike=2`. Also remove any buildx builder you created, and
its state volume, by name. Restore the Docker settings and the host sysctls you changed.
Compare against the snapshot taken before. Leave `~/gvisor-spike-2/` in place.
