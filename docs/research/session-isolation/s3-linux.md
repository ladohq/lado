# S3: gVisor on Linux (round 2, GitHub Actions runners)

Date: 2026-11-25. Brief: [gvisor-spike-2-brief.md](gvisor-spike-2-brief.md) (the updated
one, with section 0.1). Machines: GitHub's hosted runners `ubuntu-24.04` (x86_64, with
`/dev/kvm`) and `ubuntu-24.04-arm` (aarch64, no KVM), a private repository
`kao73/gvisor-spike`. Translated from the Russian report (session artifact
`report-d9e9480c`); all tables and numbers are kept. The report refers to the raw logs of
each run in `runs/<id>/` and to the scripts in `repo/` (a snapshot of the spike repository);
**they are not committed to this repository**.

## 1. Summary

- **R+net works on Linux with the macOS profile unchanged.** `runner.json` (Docker's default
  profile plus `pivot_root` and `chroot`), `cap_drop: [ALL]` plus the six capabilities
  `SYS_ADMIN NET_ADMIN NET_RAW SETUID SETGID SETFCAP` and `no-new-privileges` pass all five
  smoke checks on x86 and on arm64. None of the six can be removed.
- **The profile can be narrowed further:** the `CAP_SYS_ADMIN` block of Docker's profile is
  cut down to `mount umount2 unshare setns clone clone3` (17 calls leave the block: `bpf`,
  `perf_event_open`, `fsopen`/`fsmount`/`open_tree`/`move_mount`, `syslog`, `sethostname`
  and others), and everything works.
- **AppArmor: `docker-default` does not fit** (it denies `mount`; neither R+net nor R
  starts). **A custom profile `lado-runner-lite` works** for R+net and for R: it is
  `docker-default` with `mount`, `umount`, `pivot_root`, `userns` allowed and without the
  rules on writing to `/proc` (they hit runsc), but with the denials of `/sys/**`,
  `sysrq-trigger`, `kcore`.
- **R on Ubuntu 24.04 does not work with `apparmor=unconfined`** because of
  `kernel.apparmor_restrict_unprivileged_userns=1`. It works if this sysctl is 0, or
  **without changing the host, with the `lado-runner-lite` profile** (the rule `userns,`).
- **`--platform=kvm` works** in R+net and in R; nothing but `--device /dev/kvm` is needed.
  But on the runner (KVM nested in an Azure VM) kvm is not faster than systrap: `git status`
  is ≈24% faster, while exec, tests, `git log` and small files are 1.3-3.3 times slower.
- **Speed B/A on the container's disk** (x86, 2 vCPU): CPU 1.04×, tests 2.4-2.9×,
  `git status` 2.6-5.3×, exec 6.3-8.9× (≈3 ms per exec against ≈1 ms on macOS), small files
  from one process 0.5-1.1×. On arm64 everything is worse (tests 4.5×, `git status` 7.3×).
  A bind mount of ext4 hardly differs from local in A; in B `git status` on bind is 1.5
  times slower than on local.
- **Compatibility (A.2) in full**, 32 of 32 checks in R+net with the final profile,
  including the four CLIs with screens, `codex sandbox`, bwrap, `unshare -U`, inotify.
- **Network and isolation of R+net are fully closed**; in R the shared localhost is open
  (as on macOS).
- **`ptrace` in R is a real hole:** a uid 1000 process in the runner traces the sentry and
  the gofer of another sandbox and reads their memory even with Yama `ptrace_scope=1`.
- **Landlock is there:** ABI 8 from an unprivileged container with the default seccomp.
- **Phase C (Kata 4.4.0, QEMU):** on the guest's own disk `git status` 0.86 s (A 1.40,
  gVisor 3.59), but CPU 2× and tests 2× worse than gVisor: KVM is nested here; through
  virtio-fs `git status` 38 s. It needs changes on the host (`daemon.json`, `/opt/kata`, a
  dockerd restart).
- What was cut: Rootless Docker, Podman and Fedora/SELinux were not done; the runners are
  Azure VMs with 2 vCPU, so the absolute seconds are noisy; compare the ratios.

## 2. Environment

| | x86_64 (`ubuntu-24.04`) | aarch64 (`ubuntu-24.04-arm`) |
|---|---|---|
| Machine | Azure VM (`systemd-detect-virt`: microsoft), AMD EPYC 9V74, 2 vCPU, 7.7 GB, swap 2 GB | Azure VM, Neoverse-N2, 2 vCPU, 7.7 GB |
| OS, kernel | Ubuntu 24.04.5, 7.0.0-1017-azure | Ubuntu 24.04.5, 7.0.0-1017-azure |
| Disk | 72 GB, 13 GB free (after removing ≈40 GB of preinstalled software) | 72 GB, 34 GB free |
| Docker | Engine 28.0.4 (git 6430e49), containerd 2.4.2, runc 1.5.3, overlay2, cgroup v2 + systemd, Security Options: apparmor, seccomp (builtin), cgroupns; runsc not registered as a runtime | same |
| LSM | `lockdown,capability,landlock,yama,apparmor,ima,evm`, AppArmor 123 profiles | same |
| sysctl | `apparmor_restrict_unprivileged_userns=1`, `unprivileged_userns_clone=1`, `yama.ptrace_scope=1`; on the host `unshare -U -r` fails | same |
| KVM | `/dev/kvm` present (`crw-rw---- root:kvm`, 0666 after a udev rule), svm; reaches the container | absent |
| Landlock | ABI 8 (default seccomp and `unconfined`) | ABI 8 |

Limits for A and B: `--cpus 2 --memory 3g` (the machine has 2 vCPU). runsc
`release-20261123.0`; the CLI versions as in the first spike (`logs/03-versions.txt`).
Docker's default profile for 28.0.4: `seccomp/default-28.0.4.json` from `moby/moby` tag
`v28.0.4`, commit `6430e49a55ba…` (= the engine's git commit), path
`profiles/seccomp/default.json`. It differs from 29.9.3 only by new calls (`mseal`,
`listmount`, `statmount`, `*xattrat`, `uretprobe`) and the `socket` rules.

Runs: `45688443996` (env, A.1, B, kvm, ptrace, A.5, A.4 on x86), `45691044381` (A.2, A.3 on
x86; B, A.3 on arm64), `45697843345` (kvm against systrap on one machine), `45702983077`
(Phase C; the failed attempts `45697843345`/c and `45701615330`: the Kata 4.x layout).

## 3. Phase A

### 3.1 Privileges (`runsc run`)

| profile | x86 and arm64 | error |
|---|---|---|
| P1 `--privileged` | ✅ | |
| P2 SYS_ADMIN + `unconfined` | ✅ | |
| P5 SYS_ADMIN, default seccomp | ❌ | `pivot_root` (sandbox exited) |
| P6 defaults | ❌ | `gofer: fork/exec /proc/self/exe: operation not permitted` |
| R+net | ✅ | |
| R (`apparmor=unconfined`) | ❌ | `re-executing self: fork/exec /proc/self/exe: permission denied`: AppArmor's userns restriction (section 4.3) |

### 3.2 Compatibility (R+net, the final profile, uid 1000)

All 32 checks of the first spike ✅ (`runs/45691044381/linux-x86_64/logs/50-compat.txt`):
git clone/status/worktree, tmux and `-L lado`, `uv sync` + `lado --version` (0.48.0),
`npm ci`, gcc, `--version` and screens of all four CLIs, `codex sandbox -- true` (writing to
`/etc` from it is denied), bwrap, `unshare -U -r`, ps/df/meminfo/ulimit, inotify in the
sandbox and on bind, dmesg.

### 3.3 Speed

A is a plain container, B is R+net with the final profile (`runsc run`, systrap,
`--overlay2=root:self`). local = the container's disk / the sandbox's rootfs, bind = a host
ext4 folder. Median of three runs, s. macOS is the first spike's B/A (local; in brackets
bind on VirtioFS).

| workload | x86 A local | x86 B local | **x86 B/A local** | x86 B/A bind | arm64 B/A local | arm64 B/A bind | macOS B/A |
|---|---|---|---|---|---|---|---|
| W1 `clone --no-local` django | 17.82 | 25.02 | 1.40× | 1.46× | 1.96× | 2.02× | 1.54× |
| W2 `git status` ×20 | 0.69 | 3.65 | **5.26×** | 7.80× | 7.29× | 13.32× | 5.95× (4.03×) |
| W2 `git log --stat` | 0.30 | 0.44 | 1.44× | 1.44× | 1.78× | 1.85× | 1.51× |
| W2 `git grep` | 0.05 | 0.23 | 4.33× | 6.30× | 5.42× | 8.28× | 3.80× |
| W3 `uv sync` cold* | 0.90 | 1.29 | 1.42× | 1.62× | 2.16× | 3.11× | 1.03× |
| W3 `uv sync` warm | 0.04 | 0.10 | 2.55× | 5.69× | 3.08× | 9.59× | 1.86× |
| W4 `npm ci` cold* | 2.74 | 4.46 | 1.63× | 1.67× | 2.52× | 2.61× | 1.02× |
| W4 `npm ci` warm | 1.83 | 3.00 | 1.63× | 1.93× | 2.70× | 3.07× | 1.23× |
| W5 pytest subset | 31.12 | 89.31 | **2.87×** | 2.83× | 4.47× | 4.58× | 2.27× |
| W6py create 20 000 files | 0.35 | 0.39 | 1.12× | 3.00× | 1.75× | 4.29× | 1.53× |
| W6py `os.walk` | 0.01 | 0.04 | 2.33× | 2.47× | 3.19× | 3.52× | ≈2× |
| W6py `rmtree` | 0.19 | 0.27 | 1.47× | 1.84× | 1.68× | 2.35× | 1.25× |
| W7 2000 × `/bin/true` | 0.68 | 6.04 | **8.86×** | 8.62× | 7.87× | 7.33× | 4.72× |
| W8 CPU | 1.00 | 1.04 | 1.04× | 1.03× | 1.07× | 1.07× | 1.01× |

\* "cold" here is a fresh `UV_CACHE_DIR`/npm cache, but the runner's network is very fast,
so this is hardly the network, unlike macOS (0.8 MB/s there, A ≈ B).

A rerun on another machine of the same type (run `45697843345`, local only): `git status`
2.56×, tests 2.39×, exec 6.27×, file creation 0.54× (B faster than A). The spread between
VMs of one type is up to two times, so the order of magnitude is more reliable than single
numbers.

Conclusions:

1. gVisor's penalty on Linux is of the same kind as on macOS: system calls. An exec on the
   runner is dearer (≈3 ms against ≈1 ms on the M2); probably because of systrap in an Azure
   VM with 2 vCPU. LADO's tests 2.4-2.9× (macOS 2.3×).
2. On Linux an ext4 bind mount is almost free for A (`git status` 0.68 against 0.69), and in
   B through the gofer it costs another 1.5× (5.32 against 3.65). Here too repositories are
   better kept on the container's disk or a volume.
3. The arm64 runner (Neoverse-N2) is noticeably worse than x86 and the M2 for gVisor.

### 3.4 Network (R+net, the final profile, the "proxy only" rules)

`runs/45688443996/linux-x86_64/logs/40-net.txt`. For uid 1000 and for root in the sandbox:
the proxy 200; example.com directly and 1.1.1.1 blocked; through the proxy 200; another port
of the proxy and the runner's services over veth blocked; `iptables -F`,
`ip route/addr/link` and raw sockets from inside change nothing; the runner's rules are
unchanged after the checks.

### 3.5 Isolation

`runs/45688443996/linux-x86_64/logs/30-iso-*.txt`. Two `runsc run -d` sandboxes, own rootfs
copies, the runner marker with a random string.

| attempt from S1 | R+net (`runner.json`, 6 caps, iptables) | R (`runner-rootless.json`, no caps) |
|---|---|---|
| processes of S2 and the runner | closed | closed |
| S2's files, the marker by name and by string | closed | closed |
| `docker.sock` | absent | absent |
| TCP to S2 | closed | **open** (shared `127.0.0.1`) |
| the runner's services (`127.0.0.1:9999`, `:9998`) | closed | **open** |

Processes in the runner (R+net): the sentry in its own userns/mntns/pidns, the sandbox's
netns, `uid_map 0 0 4294967295`, CapEff `chown dac_override dac_read_search fowner fsetid
sys_ptrace`; the gofer in its own userns with `… sys_chroot`. The same as on macOS.

## 4. Phase B

`runs/45688443996/linux-x86_64/logs/20-b.txt` (x86) and
`runs/45691044381/linux-aarch64/logs/20-b.txt` (arm64); the results on both architectures
matched line by line.

### 4.1 Seccomp

| profile | R+net | R |
|---|---|---|
| default 28.0.4 | ❌ `pivot_root` | ❌ `clone` (`re-executing self`) |
| `runner.json` from macOS (based on 29.9.3) | ✅ 5/5 | |
| `runner-28.0.4.json` (the same on top of 28.0.4) | ✅ 5/5 | |
| `runner-rootless-28.0.4.json` | | ✅ 4/4, only with the userns sysctl 0 or `lado-runner-lite` |
| **narrow: the CAP_SYS_ADMIN block = `mount umount2 unshare setns clone clone3`** | ✅ 5/5 | |
| the CAP_SYS_ADMIN block = `mount umount2 clone` | ❌ the runner does not create a netns (`ip netns add` = `unshare` + `setns`) | |

The `SCMP_ACT_LOG` log works here for rootless runsc too (on macOS it did not): in R+net
only `io_uring_setup` (runsc), `io_uring_register`, `mseal` (sentry) go through the fallback
rule; in R, `clone` (56 on x86, 220 on arm64); R's other calls were found by elimination on
macOS.

The final narrow profile: `seccomp/runner-narrow-28.0.4.json` = default 28.0.4, in the rule
`includes.caps: [CAP_SYS_ADMIN]` only `clone clone3 mount setns umount2 unshare` are kept,
plus the rule `ALLOW [pivot_root, chroot]`. Removed from the block:
`bpf fanotify_init fsconfig fsmount fsopen fspick lookup_dcookie mount_setattr move_mount
open_tree perf_event_open quotactl quotactl_fd setdomainname sethostname syslog umount`.

### 4.2 Capabilities

With `runner.json` each of the six was removed in turn (x86 and arm64): without SYS_ADMIN
and NET_ADMIN the runner does not create a netns; without NET_RAW the sentry does not open
the raw socket on eth0; without SETUID, SETGID or SETFCAP the gofer does not start. The set
is minimal, as on macOS.

### 4.3 AppArmor and the userns restriction

| AppArmor | userns sysctl | R+net | R |
|---|---|---|---|
| `unconfined` | 1 (default) | ✅ | ❌ `unprivileged_userns` denies `setuid`/`setgid`, `exec /proc/self/exe` |
| `unconfined` | 0 | ✅ | ✅ |
| `docker-default` | 1 and 0 | ❌ the runner does not create a netns (`mount` denied) | ❌ `mount(… 0x84000) permission denied` |
| `lado-runner` (`docker-default` + mount/pivot_root/userns) | 1 | ❌ `mkdir /proc/fs/proc: permission denied` | ❌ |
| **`lado-runner-lite`** | **1** | ✅ | **✅** |
| `lado-runner-lite` | 0 | | ✅ |

`lado-runner-lite` (`repo/apparmor/lado-runner-lite`, loaded with `apparmor_parser -r -W`):

```
profile lado-runner-lite flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  network, capability, file, umount, mount, pivot_root, userns,
  signal (receive) peer=unconfined,
  signal (send,receive) peer=lado-runner-lite,
  ptrace (trace,read,tracedby,readby) peer=lado-runner-lite,
  unix, dbus,
  deny @{PROC}/sysrq-trigger rwklx,  deny @{PROC}/kcore rwklx,
  deny /sys/[^f]*/** wklx, … (as in docker-default), deny /sys/kernel/security/** rwklx,
}
```

`docker-default`'s rules on writing to `/proc/*` (except the pid folders) break runsc: inside
its chroot it creates `/proc/fs/proc`, and AppArmor sees that as a write to `/proc/fs/…`. In
this profile `mount,` allows any mount; narrowing it to what runsc needs (proc, bind,
`MS_SLAVE|MS_REC`, `pivot_root`) is the next step, not checked here.

The userns restriction does **not** affect nested bwrap and `codex sandbox` in R+net (they
are in gVisor's own user namespace): the smoke checks with `codex sandbox` pass with sysctl
1.

### 4.4 The final compose fragment

```yaml
runner:
  init: true
  cap_drop: [ALL]
  cap_add: [SYS_ADMIN, NET_ADMIN, NET_RAW, SETUID, SETGID, SETFCAP]
  security_opt:
    - seccomp=./seccomp/runner-narrow.json   # or runner.json
    - apparmor=lado-runner-lite              # on hosts with AppArmor; the installer loads the profile
    - no-new-privileges:true
  sysctls: [net.ipv4.ip_forward=1]
  devices: [/dev/kvm]                        # only if the kvm platform is chosen
```

For R the same, but `user: "1000:1000"`, `cap_drop: [ALL]` without `cap_add`,
`runner-rootless.json`, and on Ubuntu 24.04 `apparmor=lado-runner-lite` is required (or the
userns sysctl 0 on the host).

### 4.5 What an escapee gets

- **Code in the sentry (R+net):** its own userns with an identity `uid_map`, rights only in
  it, an almost empty root, the sandbox's netns with the runner's rules, runsc's filter on
  top of `runner.json`. The runner's SYS_ADMIN/NET_ADMIN are out of reach. The narrow
  profile adds almost nothing here.
- **Code in the runner's context (R+net):** the narrow profile, 6 capabilities instead of
  16, and `lado-runner-lite` instead of `unconfined`. Compared with `unconfined`, closed are
  `io_uring`, `keyctl`, `userfaultfd`, `kexec`, modules, `bpf`, `perf_event_open`, the new
  mount API; AppArmor denies writing to `/sys` and `sysrq-trigger`. Open are `mount`,
  `unshare`, `setns`, `clone` with namespaces: runsc does not work without them.
- **R:** see 4.6.

### 4.6 `ptrace` between sandboxes in R

`runs/45688443996/linux-x86_64/logs/24-ptrace.txt`. Two rootless sandboxes; from the runner,
a uid 1000 process (this is what an escape from a sandbox to the runner's level would look
like):

| target | Yama 1 | Yama 0 |
|---|---|---|
| another sandbox's sentry (`uid_map 0 1000 1`) | `/proc/PID/environ` and `mem` are readable, `strace -p` attaches | same |
| another sandbox's gofer | same | same |

The cause: the sentry's user namespace was created by a uid 1000 process, and the owner of a
userns has CAP_SYS_PTRACE in it, so Yama scope 1 does not stop it. The sentry itself, having
escaped, is in its own child userns and cannot reach its neighbours this way, but any escape
to the runner's level in R opens all sandboxes. **R needs a separate uid per sandbox** (or
R+net).

## 5. Linux appendix

- **kvm.** Only `--device /dev/kvm` is needed. It works with `/dev/kvm` 0660 `root:kvm`, and
  for R (uid 1000) too, without `--group-add`; why uid 1000 opens a 0660 device was not
  found out (the platform is certainly kvm: `Config.Platform (--platform): kvm`, and without
  the device runsc fails). Speed on one machine (`45697843345`, local, s):

  | workload | A | B systrap | B kvm |
  |---|---|---|---|
  | `git status` ×20 | 1.40 | 3.59 | **2.73** |
  | `git log --stat` | 0.27 | **0.45** | 0.76 |
  | `git grep` | 0.08 | 0.21 | **0.18** |
  | pytest | 35.12 | **83.96** | 107.25 |
  | create 20 000 files | 0.72 | **0.39** | 0.65 |
  | `rmtree` | 0.37 | **0.25** | 0.83 |
  | 2000 exec | 1.01 | **6.35** | 8.66 |
  | CPU | 0.82 | 0.84 | 0.88 |

  On nested virtualization kvm wins only on the `stat`-heavy `git status`; on exec, tests
  and files it loses. On bare metal the picture may differ; there was none here.
- **The userns restriction:** section 4.3.
- **bind ext4:** section 3.3: almost free for A, +50% on `git status` for B.
- Rootless Docker, Podman, Fedora/SELinux: not done.

## 6. Phase C: micro-VM (Kata Containers)

Run `45702983077`, `repo/ci/c.sh`, `logs/80-kata.*`. Kata Containers **4.4.0** (the latest
release, the static archive `kata-static-4.4.0-amd64.tar.zst`), runtime-rs only, hypervisor
**QEMU** (`configuration-qemu-runtime-rs.toml`, q35), guest kernel 6.18.62, 2 vCPU, 3 GB.
Plugged into Docker as a runtime through `daemon.json` (`runtimes.kata.runtimeType` = the
path to `containerd-shim-kata-v2`) with a dockerd restart. The same `bench.sh` in two places:
K-local, the container's rootfs that Kata gives the guest over virtio-fs; K-blk, an ext4
block device (a host loop file, `--device`), that is **the guest's own disk**.

Median of three runs, s. A and B are from another VM of the same type (run `45697843345`),
so the comparison is indicative:

| workload | A (runc) | B gVisor systrap | B gVisor kvm | **Kata, own disk** | Kata, virtio-fs |
|---|---|---|---|---|---|
| W2 `git status` ×20 | 1.40 | 3.59 | 2.73 | **0.86** | 38.20 |
| W2 `git log --stat` | 0.27 | 0.45 | 0.76 | 0.38 | 0.66 |
| W2 `git grep` | 0.08 | 0.21 | 0.18 | 0.10 | 1.68 |
| W5 pytest | 35.12 | 83.96 | 107.25 | 168.00 | 170.21 |
| W6py create | 0.72 | 0.39 | 0.65 | 0.40 | 13.96 |
| W6py `os.walk` | 0.02 | 0.04 | 0.05 | 0.07 | 0.34 |
| W6py `rmtree` | 0.37 | 0.25 | 0.83 | 0.22 | 5.09 |
| W7 2000 exec | 1.01 | 6.35 | 8.66 | 10.25 | 10.04 |
| W8 CPU | 0.82 | 0.84 | 0.88 | **1.65** | 1.65 |

Conclusions:

1. **On the guest's own disk a micro-VM pays almost nothing for the filesystem:**
   `git status` and small files at the level of a plain container (3-4 times faster than
   gVisor).
2. **But on this machine Kata loses to gVisor on CPU (2×), exec (1.6×) and tests (2×):**
   KVM is nested in an Azure VM here, and each exit from the guest is dear. On bare metal
   CPU and exec in a micro-VM are usually close to native, so this row does **not** show
   how Kata will behave for a user.
3. **virtio-fs (the container's rootfs) is disastrous:** `git status` 27 times worse than A.
   So for a micro-VM, repositories must live on the guest's block disk, not on a shared
   folder.

**Effort.** The install takes 24 s, but three iterations went on 4.x being organised
differently from 3.x (runtime-rs only, other paths to the shim and the configurations,
plugged in through `daemon.json`). The main point: Kata needs **changes on the host**
(`/dev/kvm`, an install into `/opt/kata`, `daemon.json`, a dockerd restart, its own block
disk through a loop device), so it does not fit the "everything inside an ordinary
container" scheme for which gVisor was chosen. On macOS (no nested virtualization on the M2)
and in Docker Desktop it does not work at all.

## 7. Problems and surprises

1. **Ubuntu 24.04's userns restriction** breaks rootless runsc with `apparmor=unconfined`,
   and `docker-default` breaks R+net too; a custom AppArmor profile is needed.
2. **The host's bind folder** belongs to the runner machine's user, and the runner's root
   without CAP_DAC_OVERRIDE cannot write into it. On macOS VirtioFS hid this. Folders for
   `/work` must belong to the sandbox's uid or be open for writing.
3. **`SCMP_ACT_LOG` writes here for rootless runsc too**, unlike Docker Desktop on macOS.
4. **Kata 4.x** ships with runtime-rs only; the path to the shim and the configurations
   differs from 3.x (`/opt/kata/runtime-rs/bin/containerd-shim-kata-v2`), and it has to be
   plugged into Docker through `daemon.json` (`runtimes.kata.runtimeType`).
5. **Bugs of my own test bed** (fixed; the tables hold only the repeated runs): `pgrep -f`
   found the script itself; W5 without a clone of lado in the kvm set; the first isolation
   runs on bind without write rights.

## 8. Cleanup

GitHub's runners are disposable: the VM is destroyed after the job, so the comparison of the
snapshots before and after formally exists (`logs/00-snapshot-before.txt`,
`logs/99-snapshot-after.txt`) but means nothing. The host sysctls
(`apparmor_restrict_unprivileged_userns`, `yama.ptrace_scope`) and the rights of `/dev/kvm`
were restored after the changes (`sysctl restored: 1` in the logs). Nothing was created
locally on the Mac except this folder and `~/gvisor-spike-gha*`.
