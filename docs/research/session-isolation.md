# Research: session isolation (gVisor spikes)

The question: how can LADO's sessions be isolated from each other and from the machine, the
same way on macOS, Windows and Linux, locally and in a cloud, without asking the user to
install anything beyond Docker. Research of 2026-11-25 and 2026-11-26: a desk study, then
two rounds of hands-on spikes on real machines; no product code changed. It continues the
cloud workers research ([cloud-workers.md](cloud-workers.md)) on the local side; the
decisions it led to are in the living plan,
[cloud-workers-plan.md](cloud-workers-plan.md) (section 1, 2026-11-26). **Since 2026-11-27
the work is planned in [session-isolation-plan.md](session-isolation-plan.md)** (experiments,
threat model, milestones); some claims below were corrected then, see
[Corrections](#corrections-2026-11-27). The reports, the briefs and two diagrams are in
[session-isolation/](session-isolation/):

| Report | What about |
|---|---|
| [S1](session-isolation/s1-macos.md) | round 1, macOS (Docker Desktop, Apple M2): privileges, compatibility, speed, network, isolation |
| [S2](session-isolation/s2-macos-phase-b.md) | round 2 Phase B on macOS: a narrow seccomp profile, the minimal capabilities, what an escapee gets |
| [S3](session-isolation/s3-linux.md) | round 2, Linux x86 and arm64 (GitHub runners): AppArmor, `ptrace` in R, the `kvm` platform, Kata |
| [S4](session-isolation/s4-windows-wsl2.md) | round 2, Windows WSL2 with Docker Engine (not Docker Desktop): bind places, line endings, KVM |

The briefs the spike agents worked from: [round 1](session-isolation/gvisor-spike-brief.md),
[round 2](session-isolation/gvisor-spike-2-brief.md),
[round 3](session-isolation/gvisor-spike-3-brief.md) (Docker Desktop on Windows, not run
yet). The reports were written in Russian and are kept here in English with all their
tables and numbers. They refer to raw logs, scripts and seccomp profiles (`logs/`, `runs/<id>/`,
`scripts/`, `seccomp/`) that stayed in the spike folders and **are not committed**; the
profiles' content is given in the reports as diffs.

The inputs of the plan of 2026-11-27, archived beside the reports:

| File | What about |
|---|---|
| [A1](session-isolation/a1-code-seams.md) | the code seams per-session sandboxes need, rechecked at `main` 1e565441 |
| [A2](session-isolation/a2-prior-art.md) | how others moved from local agents to sandboxes, gVisor in production in 2026 |
| [A3](session-isolation/a3-review.md) | a critical review of this research |
| [Review of plan v1](session-isolation/review-plan-v1.md) | points K1-K14 |
| [Review of plan v2](session-isolation/review-plan-v2.md) | points P1-P10, with a recheck of the reports, A1 and A2 |

## Corrections (2026-11-27)

A3 and the second review rechecked this research against its reports. What is now known to
be wrong or overstated; the places in the text carry a short "Corrected" note:

- **The speed headline** (1.4, 4.2) was measured on the sandbox's own disk
  (`--overlay2=root:self`), where a repository cannot live. On a bind or a volume gVisor is
  much slower: `git status` 7.8× on Linux (ext4 bind), 11.2× in WSL2 (named volume). The
  macOS volume was not measured; the row "container disk / volume" of 4.3 is the container
  disk only. The numbers are medians of three runs on 2 vCPU, and the ratio itself moved
  about 2× between two VMs.
- **"The runner's services are out of reach"** (1.5, 6) holds only for IPv4 and with the
  proxy outside the runner, as in the spikes. IPv6 was not tested, and in the target layout
  the proxy and the Agent API gateway run inside the runner.
- **AppArmor `lado-runner-lite`** (5) is required on Linux hosts with AppArmor, not
  optional: the runner is root with `SYS_ADMIN` in the host's user namespace, and
  `unconfined` is the weak point. Loading it needs host root.
- **Dangerzone**, cited during the planning as a precedent, backs only "runsc in a container
  as a portability layer", not our privilege profile: it uses rootless runsc, drops all
  capabilities but `SYS_CHROOT`, has no network and one single-use sandbox. Its rootless
  profile is our profile R, which stays dropped (ptrace between sentries, 8.1); a uid per
  sandbox is experiment E15 of the plan.
- **"The code through git"** (7, 8.2) is not a detail: it changes today's main workflow. The
  plan keeps both modes, bind and volume, chosen per project (its Q3).
- **The subscription caveat** (8.5) is a legal constraint on a hosted service, not a
  technical rule for self-hosting (A3 2.3).
- **The connection direction** (7, 8.3) is preliminarily reversed: the runner connects to the
  panel (the plan's Q1).

1. [Summary](#1-summary)
2. [Where LADO stands and how others isolate](#2-where-lado-stands-and-how-others-isolate)
3. [What was tried](#3-what-was-tried)
4. [Results by platform](#4-results-by-platform)
5. [The runner's profile](#5-the-runners-profile)
6. [Network and isolation](#6-network-and-isolation)
7. [The target layout and three topologies](#7-the-target-layout-and-three-topologies)
8. [Findings that change the design](#8-findings-that-change-the-design)
9. [Open questions and untested gaps](#9-open-questions-and-untested-gaps)

## 1. Summary

1. **gVisor inside an ordinary container works on every platform tested:** Docker Desktop on
   macOS (M2), Docker Engine on Linux x86 and arm64, Docker Engine in WSL2. A `runner`
   container runs one gVisor sandbox (`runsc run`) per session; nothing is installed on the
   host, the runner is started by `docker compose` like LADO's image today.
2. **The runner needs a narrow set of rights, not `--privileged`:** `cap_drop: [ALL]` plus six
   capabilities, Docker's default seccomp profile plus `pivot_root` and `chroot` (narrower
   still on Linux), `no-new-privileges`, `init`, and the `ip_forward` sysctl (section 5).
3. **Inside the sandbox everything LADO needs works:** git with worktrees, tmux with
   `-L lado`, uv, npm, gcc, the four agent CLIs with their screens, inotify. Codex's own
   sandbox (bwrap), which fails in LADO's container today, works inside gVisor.
4. **The cost is in system calls:** CPU 1.0×, LADO's tests 2-3× (4.5× on arm64), `git status`
   5-7×, an exec 5-9× (1-6 ms each). It is the same everywhere in kind. A macOS bind mount
   costs more than gVisor does (21× for `git status` without gVisor), and a bind from `C:\`
   on Windows breaks git, so repositories live on a Docker volume. *Corrected 2026-11-27:
   these ratios are on the sandbox's own disk; on a bind or a volume `git status` is 7.8×
   (Linux) and 11.2× (WSL2), on macOS not measured ([Corrections](#corrections-2026-11-27)).*
5. **Each sandbox gets its own netns, and iptables in the runner let it reach only a proxy.**
   Nothing inside the sandbox, root included, can undo it. Processes, files, other sandboxes,
   the runner's services and `docker.sock` are all out of reach. *Corrected 2026-11-27:
   over IPv4, with the proxy outside the runner; IPv6 and a proxy inside the runner are not
   tested ([Corrections](#corrections-2026-11-27)).*
6. **Rootless runsc (profile R) is dropped:** a process of the runner's uid can `ptrace` every
   other sandbox's sentry (section 8). R+net, with a root runner and a user namespace per
   sentry, is the base.
7. **A micro-VM (Kata) is faster on files on its own disk, but needs the host changed** and
   does not run under Docker Desktop at all; gVisor's `kvm` platform was slower than systrap
   on nested virtualization. Both stay options for bare-metal Linux.
8. **The human's direction (2026-11-26):** gVisor in a plain container is the base
   isolation candidate for local, cloud and hybrid; one universal runner that the panel
   connects to; internet only through the runner's proxy; research continues, no
   development yet. The plan records it ([cloud-workers-plan.md](cloud-workers-plan.md)).

## 2. Where LADO stands and how others isolate

From the desk study of 2026-11-25 (in Russian, a session artifact; condensed here).

**Today all sessions share one container and one OS user,** so any agent can read other
sessions' worktrees, all project variables and secrets, git server tokens, model keys and
the CLIs' logins (Codex's `auth.json` is one for all); write to the shared `lado.db` and type
into other agents' windows through the shared tmux server; and reach any address on the
network. Codex's bubblewrap sandbox does not start in Docker (LAD-151), so Codex runs with
`danger-full-access`. The one boundary is the whole LADO container, and the documentation
says so ([projects.md](../design/projects.md), "The security boundary").

| Level | Who | What it gives |
|---|---|---|
| git worktree only | Claude Squad, Conductor, Vibe Kanban, **LADO today** | files and branches apart, but not processes, keys or network |
| OS sandbox per command | Claude Code (`sandbox-runtime`: Seatbelt/bubblewrap + proxy), Codex CLI (Seatbelt, Landlock + seccomp) | writes only in its folder, network through a proxy; free at start; weakest against kernel exploits |
| container | OpenHands, container-use (Dagger), Imbue Sculptor, Codex cloud, Daytona | own processes, home and network; a shared kernel |
| gVisor (a user-space kernel) | Modal, GKE agent-sandbox | a strong boundary without KVM; slower I/O |
| micro-VM | E2B, Vercel Sandbox (Firecracker), Fly Sprites, Devin, Docker Sandboxes (`sbx`), Microsandbox (libkrun), Northflank/Kata, Cloudflare | own kernel, a hardware boundary; start in 0.1-1 s |

The common practices worth taking: the control panel outside and the agent inside, with a
narrow channel (RPC) between them, not a shared filesystem; keys injected by a proxy outside
the sandbox, only for allowed addresses, with a placeholder inside; an egress allowlist
enforced outside the guest; a full clone inside the sandbox and the result through a push.
The weak spot of all of them: the repository's own files (a `.env` in the working folder).

**Why not a micro-VM first.** LADO's container on a Mac has no `/dev/kvm`, and nested
virtualization does not reach it (checked in the container itself), so Firecracker, Kata and
Cloud Hypervisor cannot start there. Firecracker has no shared filesystem, only block
devices. And without the seam (MCP and hooks over the network with a token per agent, keys
behind a proxy), an agent inside any VM would still need the panel's database and tokens:
no isolation at all. The study's staging, unchanged in substance by the spikes:

| Stage | What | Protects from |
|---|---|---|
| 0. Today | a separate LADO (container and volume) per client | clients mixing |
| 1. Inside today's container | Landlock per session (a cheap safeguard, possible at once) | accidental or prompt-injected reads of other sessions' files; incomplete while the agent needs `lado.db`, tmux and tokens |
| 2. The seam (cloud workers stage B) | MCP and hooks over the network with a per-agent token; the panel the only writer of the DB; keys and git through a proxy; an egress allowlist | stolen keys, a forged agent |
| 3. A sandbox per session | the runner of this research: gVisor, later Kata or a micro-VM where available | everything but kernel bugs (runc) or almost everything (gVisor, micro-VM) |
| 4. A micro-VM per session | the same seam, the VM brought up by the host | escapes through the kernel |

## 3. What was tried

| Round | Machine | Brief | What |
|---|---|---|---|
| 1 | MacBook Air M2, macOS 27.0, Docker Desktop 4.100 (Engine 29.9.3), Apple Virtualization, VirtioFS | [round 1](session-isolation/gvisor-spike-brief.md) | privilege matrix P1-P6, compatibility, speed A against B (bind and local), network, isolation: [S1](session-isolation/s1-macos.md) |
| 2, Phase B | the same Mac | [round 2](session-isolation/gvisor-spike-2-brief.md) | a narrow seccomp profile, capability sweep, namespaces of the sentry: [S2](session-isolation/s2-macos-phase-b.md) |
| 2 | GitHub runners `ubuntu-24.04` (x86, KVM) and `ubuntu-24.04-arm`, Azure VMs with 2 vCPU, Docker Engine 28.0.4 | round 2 | Phase A again, Phase B, AppArmor, `ptrace` between sentries, `--platform=kvm`, Kata 4.4.0: [S3](session-isolation/s3-linux.md) |
| 2 | GitHub runner `windows-2025`, Ubuntu 24.04 on WSL2, Docker Engine 28.0.4 | round 2 | Phase A and B, three bind places, line endings, KVM: [S4](session-isolation/s4-windows-wsl2.md) |
| 3 | Windows 11 with Docker Desktop | [round 3](session-isolation/gvisor-spike-3-brief.md) | `docker compose` from PowerShell, Docker Desktop's file sharing, ECI: **not run yet** |

All rounds used runsc `release-20261123.0`, the same image (Debian bookworm with git, tmux,
Python and uv, Node 22, gcc, claude 2.1.332, codex 0.172.0, opencode 1.19.6, kilo 7.8.32),
no logins and no keys. **A** is a plain container, **B** is a gVisor sandbox in profile
R+net (`runsc run`, systrap, `--overlay2=root:self`), both under the same CPU and memory
limits, median of three runs.

Two runner profiles were compared:

- **R+net**: the runner runs as root with a few capabilities; runsc gives each sandbox its
  own user namespace and a netns with a veth pair; the agent is uid 1000 in the sandbox.
- **R**: rootless runsc as uid 1000 of the runner with no capabilities; only root inside the
  sandbox, network `none` or `host`, no nested sandboxes.

## 4. Results by platform

### 4.1 Does it start

| Profile | macOS | Linux x86 / arm64 | WSL2 |
|---|---|---|---|
| P1 `--privileged` | ✅ | ✅ | ✅ |
| P5 `SYS_ADMIN`, Docker's default seccomp | ❌ `pivot_root` | ❌ `pivot_root` | ❌ `pivot_root` |
| P6 Docker's defaults (LADO's container today) | ❌ `clone` with namespaces | ❌ | ❌ |
| R+net, final profile (section 5) | ✅ | ✅ | ✅ |
| R (rootless) | ✅ | ❌ with `apparmor=unconfined` (Ubuntu's userns restriction); ✅ with `lado-runner-lite` | ✅ |
| `--platform=kvm` | ❌ no `/dev/kvm` | ✅ x86 | ✅ |

Compatibility in R+net as uid 1000: 32 of 32 checks on Linux and WSL2, all of round 1's
list on macOS.

### 4.2 Speed, B/A on the container's own disk

B/A is the gVisor sandbox's time over the plain container's, on the same machine. The macOS
numbers are from an M2 with `--cpus 4`; Linux and WSL2 from Azure VMs with 2 vCPU, whose
absolute times vary up to 2× between VMs of one type, so compare orders of magnitude. The
last two columns are from one Linux x86 VM (run `45697843345`, A on that VM): gVisor's `kvm`
platform and Kata 4.4.0 (QEMU, the guest's own ext4 disk), both on **nested** KVM.
*Corrected 2026-11-27: a session's repository does not live on this disk; for a bind or a
volume see 4.3 ([Corrections](#corrections-2026-11-27)).*

| Workload | macOS M2 | Linux x86 | Linux arm64 | WSL2 | Linux x86, gVisor kvm | Linux x86, Kata |
|---|---|---|---|---|---|---|
| W1 `git clone --no-local` django | 1.54× | 1.40× | 1.96× | – | – | – |
| W2 `git status` ×20 | 5.95× | 5.26× | 7.29× | 5.2× | 1.95× | **0.61×** |
| W2 `git log --stat -n 300` | 1.51× | 1.44× | 1.78× | 2.1× | 2.81× | 1.41× |
| W2 `git grep` | 3.80× | 4.33× | 5.42× | 4.1× | 2.25× | 1.25× |
| W3 `uv sync`, warm | 1.86× | 2.55× | 3.08× | – | – | – |
| W4 `npm ci`, warm | 1.23× | 1.63× | 2.70× | – | – | – |
| W5 pytest (3 test files, `-n 4`) | 2.27× | 2.87× | 4.47× | – | 3.05× | 4.78× |
| W6py 20 000 files, one process | 1.53× | 1.12× | 1.75× | 1.8× | 0.90× | 0.56× |
| W6py `os.walk` | ≈2× | 2.33× | 3.19× | 3.3× | 2.5× | 3.5× |
| W6py `rmtree` | 1.25× | 1.47× | 1.68× | 2.0× | 2.24× | 0.59× |
| W7 2000 × `/bin/true` | 4.72× | 8.86× | 7.87× | 5.5× | 8.57× | 10.1× |
| W8 CPU, Python | 1.01× | 1.04× | 1.07× | – | 1.07× | 2.01× |

On the same VM gVisor systrap gave `git status` 2.56×, tests 2.39×, exec 6.27×, file creation
0.54×: that VM's A was slower than the main x86 run's, which is why the ratios differ from
the "Linux x86" column. An exec costs ≈1 ms in gVisor on the M2, ≈3 ms on the Azure VM and
≈6.4 ms in WSL2 (≈1.1 ms there even without gVisor). Cold `uv sync` and `npm ci` follow the
network: 1.0× on macOS's slow line, 1.4-1.6× on the runners' fast one.

**Kata on nested KVM** is not what a user's bare-metal machine would show: on files it beats
both gVisor and runc (`git status` 0.86 s against runc's 1.40 s and gVisor's 3.59 s), but
each exit from the guest is dear here, so CPU, exec and tests are worse than gVisor. Through
virtio-fs (the container's rootfs shared into the guest) Kata's `git status` took 38 s, 27×
worse than runc.

### 4.3 Where repositories can live

| Place | A `git status` ×20 | B `git status` ×20 | Verdict |
|---|---|---|---|
| macOS, container disk (a volume not measured; corrected 2026-11-27) | 0.43 s | 2.53 s | use |
| macOS, bind mount of a Mac folder (VirtioFS) | 9.10 s | 36.68 s | 21× slower without gVisor; avoid |
| Linux, container disk | 0.69 s | 3.65 s | use |
| Linux, bind of a host ext4 folder | 0.68 s | 5.32 s | free for A, +50% for B; works, the folder must be writable by the sandbox's uid |
| WSL2, container disk | 1.24 s | 6.44 s | use |
| WSL2, named volume / WSL ext4 bind | 0.83 s | 9.32 s / 9.30 s | use (a volume) |
| WSL2, bind from `C:\` (drvfs, 9p) | ❌ | ❌ | git cannot clone as uid 1000; small files ≈200× slower (74.7 s against 0.36 s); never |

`--file-access-mounts=exclusive` gains at most 10% on a bind mount and forbids changes from
outside while the sandbox runs; `--overlay2=root:self` (the default) is the right choice on
the local disk; `root:memory` is not faster and takes RAM. On Windows, Git for Windows
checks files out with CRLF by default, and bash in WSL then fails (`set: -\r: invalid
option`): repositories the agents open are cloned from inside Linux.

## 5. The runner's profile

The final compose fragment for the runner, profile R+net (S2 4.3, S3 4.4, round 3's brief):

```yaml
runner:
  init: true                                 # otherwise the runner collects zombie sentries
  cap_drop: [ALL]
  cap_add: [SYS_ADMIN, NET_ADMIN, NET_RAW, SETUID, SETGID, SETFCAP]
  security_opt:
    - seccomp=./seccomp/runner-narrow.json   # fallback: runner.json
    - apparmor=unconfined                    # or lado-runner-lite where the installer loads it
    - no-new-privileges:true
  sysctls: [net.ipv4.ip_forward=1]           # /proc/sys is read-only inside the container
  # devices: [/dev/kvm]                      # only with --platform=kvm
```

- **Seccomp.** `runner.json` is Docker's default profile for the engine's version plus one
  rule allowing `pivot_root` (runsc's boot and gofer move their root; without it no sandbox
  starts) and `chroot` (Docker ties it to `CAP_SYS_CHROOT`, which is dropped).
  `runner-narrow.json` additionally cuts the default profile's `CAP_SYS_ADMIN` block down to
  `clone clone3 mount setns umount2 unshare`, removing 17 calls (`bpf`, `perf_event_open`,
  the new mount API, `syslog`, `sethostname`, …). `io_uring_setup` and `mseal` are
  deliberately not added: runsc only warns that teardown is slower.
- **Capabilities.** Each of the six is needed: SYS_ADMIN and NET_ADMIN for the netns and
  iptables, NET_RAW for the sentry's raw socket on eth0, SETUID, SETGID and SETFCAP for runsc
  to write the user namespace maps of the gofer and the sentry. The other ten of Docker's
  default set go.
- **AppArmor** (Linux hosts that have it). `unconfined` works for R+net, also with
  Ubuntu 24.04's `apparmor_restrict_unprivileged_userns=1`. Docker's `docker-default`
  breaks it (it denies `mount`). A custom profile `lado-runner-lite` (`docker-default` with
  `mount`, `umount`, `pivot_root` and `userns` allowed and without the `/proc` write rules
  that hit runsc, keeping the denials of `/sys/**`, `sysrq-trigger`, `kcore`) works for
  R+net and R; it is optional hardening, loaded by the installer with `apparmor_parser`.
  *Corrected 2026-11-27: required, not optional, on Linux hosts with AppArmor
  ([Corrections](#corrections-2026-11-27)).*
  Its text is in S3 4.3. macOS's Docker Desktop and WSL2 have no AppArmor.
- **What an escapee gets.** From the sentry: its own user namespace with rights only there,
  an almost empty root, its own netns under the runner's rules; not the runner's SYS_ADMIN or
  NET_ADMIN. From the runner's context (a bug before runsc sets its filters, in the gofer, or
  a kernel bug reachable from it): Docker's deny list again (`io_uring`, `keyctl`,
  `userfaultfd`, `kexec`, modules, `bpf`, `perf_event_open`), six capabilities instead of
  sixteen; `mount`, `unshare`, `setns` and `clone` with namespaces stay open, as runsc needs
  them.

Profile R (rootless) needed `runner-rootless.json` (the default plus `clone mount umount2
pivot_root chroot`), no capabilities, and on Ubuntu 24.04 `lado-runner-lite` or the userns
sysctl at 0; it is not a candidate any more (section 8).

## 6. Network and isolation

Per sandbox the runner creates a netns with a veth pair and NAT, and `config.json` points
the sandbox's network namespace at it; the netns is single-use (gVisor keeps eth0's
address), so it is recreated before each run. The "proxy only" rules in the runner's netns:

```
iptables -N SPIKE-SANDBOX
iptables -A SPIKE-SANDBOX -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A SPIKE-SANDBOX -d $PROXY -p tcp --dport 3128 -j ACCEPT
iptables -A SPIKE-SANDBOX -j REJECT --reject-with icmp-admin-prohibited
iptables -I FORWARD -i veth-+ -j SPIKE-SANDBOX
iptables -I INPUT   -i veth-+ -j REJECT          # the runner's own services
```

On all three platforms, for uid 1000 and for root inside the sandbox: the proxy answers,
direct internet (by name and by IP) is blocked, the proxy's other ports and the runner's
services are blocked, and `iptables -F`, `ip route/addr/link` and raw sockets from inside
change nothing. Docker's DNS `127.0.0.11` is not reachable from the netns; with a proxy the
sandbox needs no DNS. *Corrected 2026-11-27: this holds for IPv4 (no `ip6tables` rules were
set or tested) and for this layout, where the proxy is a separate container; in the target
layout the proxy and the Agent API gateway are inside the runner (experiment E3 of the
plan).*

Isolation, two `runsc run -d` sandboxes with separate rootfs copies, judged by a random
marker in the runner:

| Attempt from sandbox S1 | R+net with the rules | R |
|---|---|---|
| S2's and the runner's processes, signals | closed | closed |
| S2's files, the runner's marker | closed | closed |
| `docker.sock`, `runsc` | absent | absent |
| TCP to S2, the runner's services | closed | **open** (shared localhost) |
| `mount`, modules, iptables as root | refused | refused |
| a runner process `ptrace`s another sandbox's sentry | n/a (each sentry in its own userns) | **succeeds**, even with Yama 1 |

## 7. The target layout and three topologies

Two diagrams drawn during the research (in Russian, as drawn):
[isolation-architecture.html](session-isolation/isolation-architecture.html) (the first
draft: its key and git proxy sits in the panel, which the second diagram supersedes) and
[lado-topologies.html](session-isolation/lado-topologies.html) (the current one). In words:

**Two parts everywhere.** The **panel** (`lado`): the UI server, the core with `lado.db` as
its only writer, the session loop, the message queue, flow runs and artifacts, the stored
keys and logins, and a list of runners. The **runner**: an Agent API gateway plus a key and
git proxy, the runner agent (starts runsc, prepares rootfs, a netns and iptables per sandbox,
holds the sessions' tmux and pty for the UI's terminals), a volume with the sessions'
repositories, and one gVisor sandbox per session holding its tmux, agents, clone and
worktrees, and thin `lado mcp` / `lado hook` that only call the API.

- **Keys** are stored in the panel; a runner gets them for the time of a session and keeps
  them only in its proxy's memory; sandboxes never see them. A stricter mode for untrusted
  runners was sketched: the runner's proxy forwards to the panel, and the panel injects the
  keys.
- **Internet** always goes out from the runner through its proxy (key injection, allowlist,
  branch checks), never through the panel.
- **The result** of a session comes back as a branch through git. Nobody needs the Docker
  socket: the runner brings its sandboxes up itself.
- **The runner is the same everywhere**: one image, one protocol. The panel connects to a
  given runner; how (an SSH tunnel or another one, a reverse connection for a runner behind
  NAT) is not designed yet. A local runner has no special path.

The three topologies:

| | Local | Cloud | Hybrid |
|---|---|---|---|
| Where the panel is | the laptop | a server | a cloud or a home server, always on |
| Where sessions run | the laptop | the server | any connected runner: the laptop, own servers, a cloud |
| Panel → runner | the Docker network | the Docker network | the panel connects to each given runner |
| Isolation | gVisor | gVisor; with KVM optionally a micro-VM (Kubernetes: a pod per session, RuntimeClass gVisor or Kata) | the runner decides: gVisor everywhere, a micro-VM where KVM is |
| How the user gets the code | git (or a bind mount: slow) | git through a remote | git through a remote |
| Pros | nothing but Docker; data stays on the machine except model requests | sessions run while the laptop is closed; resources | sessions run where convenient; the panel and history always reachable |
| Cons | sessions stop when the laptop sleeps | a server, TLS and a login; files only through git; keys on the server | a runner list, keys per session, reconnects and an event buffer on the runner |

A whole session lives on one runner, and the panel chooses which. In the hybrid the panel can
also sit on the laptop, but then sessions on other runners get no answers while it sleeps.
For paid hosting for other people, only users' own API keys (BYOK); Claude and ChatGPT
subscriptions are not possible there (see below).

## 8. Findings that change the design

1. **Profile R is dropped.** In R all sentries run as one uid of the runner, and the owner of
   a user namespace has `CAP_SYS_PTRACE` in it, so any escape to the runner's level reads the
   memory of every other sandbox (S3 4.6). R would need a uid per sandbox; R+net already
   gives each sentry its own user namespace. Round 1's worry that an escape from the sentry
   in R+net lands as root with the runner's SYS_ADMIN was wrong (S2 1).
2. **Repositories go on a Docker volume and results through git**, on every platform: never
   on `C:\` on Windows, not bind-mounted on macOS. This makes "the result is a branch" the
   default locally too, not only in a cloud.
3. **The proxy is in the runner, not in the panel**, and the panel connects to the runner,
   not the other way round. This differs from the plan's stage C1, where `lado node`
   connects outbound to the panel; a runner behind NAT then needs a reverse tunnel. Recorded
   as an open question in the plan. *Corrected 2026-11-27: the direction is preliminarily
   reversed, the runner connects to the panel ([plan](session-isolation-plan.md), Q1).*
4. **Local isolation needs the seam first.** A sandboxed agent can no longer write `lado.db`
   or drive tmux, so MCP and hooks over the network with a per-agent token (stage B of the
   cloud plan) are needed for the local mode too, not only for clouds. Stage B may have to
   come earlier.
5. **Subscription logins stay inside the sandbox.** A proxy can inject API keys, but a Claude
   Pro/Max or ChatGPT OAuth token must sit in the container that runs the CLI; a proxy
   swapping it is the "intermediating" Anthropic forbids
   ([R4](cloud-workers/r4-credentials.md) 3.2). Only API keys can stay out of the sandbox.
6. **The `kvm` platform and micro-VMs are options, not the base.** On nested virtualization
   (cloud VMs, WSL2) `kvm` was slower than systrap; Kata needs host changes and does not run
   under Docker Desktop. systrap is the default; `kvm` and Kata/Firecracker only on bare
   metal, where they still need measuring.
7. **Codex's sandbox works again** inside gVisor (bwrap in gVisor's own user namespace), so
   `danger-full-access` (LAD-151) need not be the rule in the runner.
8. **Operational traps for the runner:** gVisor's release is now a tarball (`runsc` looks for
   `gvisor-bin/` beside itself); a netns per run; `init: true`; the rootfs is unpacked by the
   image build or the panel, not by the runner (it lacks `CAP_CHOWN`); a bind folder must
   belong to the sandbox's uid; `runsc do` with a network needs `--privileged`, so `runsc
   run` is used.

## 9. Open questions and untested gaps

- **Round 3, Docker Desktop on Windows** ([brief](session-isolation/gvisor-spike-3-brief.md)):
  `docker compose` from PowerShell with a relative seccomp path, a build context checked out
  with CRLF, Docker Desktop's own file sharing from `C:\`, `host.docker.internal` bypassing
  the proxy, ECI (it may refuse `cap_add` and `security_opt`), the Hyper-V backend, survival
  of a Docker Desktop restart. Round 2 tested only Docker Engine inside WSL2.
- **The narrow profile on Docker 29 / Docker Desktop.** `runner-narrow.json` was checked on
  Engine 28.0.4 (Linux, WSL2); on macOS (Engine 29.9.3) only `runner.json` was. The profile
  must be rebuilt on top of each engine version's default; how LADO ships and updates it is
  open.
- **AppArmor:** `lado-runner-lite` allows any `mount`; narrowing it to what runsc needs is
  not checked. How the installer loads it, and what happens on hosts without
  `apparmor_parser`, is not designed.
- **Not tested:** SELinux (Fedora), rootless Docker, Podman, Kubernetes with a gVisor
  RuntimeClass, the `kvm` platform and Kata on bare metal, Firecracker, Docker Desktop's other
  VMM on macOS, Apple `container` and nested KVM on M3+.
- **A uid per sandbox** would make R viable again; not tried (experiment E15 of the
  [plan](session-isolation-plan.md)).
- **How the panel connects to a runner** (an SSH tunnel, a reverse connection behind NAT),
  and how that fits the plan's outbound `lado node` (C1).
- **Where a user's own checkout meets the session's volume** locally: git only, or a sync.
- **One runner for everyone or a runner per client**, and resource limits per sandbox
  (cgroups are ignored with `--ignore-cgroups`).
- **The effect of denying `io_uring`** on sandbox teardown time, not measured.
- **Landlock** (stage 1): ABI 8 from an unprivileged container on Linux, ABI 7 in WSL2; on
  macOS's Docker Desktop round 1 could not see it in `/sys/kernel/security/lsm` (the desk
  study had reported ABI 8 by a direct call). Not pursued further.
- **Why uid 1000 opens a 0660 `/dev/kvm`** without the group: not found out.
