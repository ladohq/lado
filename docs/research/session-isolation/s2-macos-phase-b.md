# S2: a narrow seccomp profile instead of `unconfined` (round 2, Phase B, macOS)

Date: 2026-11-25, about 1.5 hours. Brief: [gvisor-spike-2-brief.md](gvisor-spike-2-brief.md),
Phase B only (the human's choice), on the same machine as the first spike
([S1](s1-macos.md)). Linux, Windows, the whole of Phase A and Phase C were not done here.
Translated from the Russian report (session artifact `report-0fd8e24e`); all tables and
numbers are kept. The report refers to its raw logs, profiles and scripts (`logs/…`,
`seccomp/…`, `scripts/…` in the spike folder `~/gvisor-spike-2/`); **they are not committed
to this repository**.

## 1. Summary

- **R+net works with Docker's default profile plus two calls: `pivot_root` and `chroot`.**
  `seccomp=unconfined` is no longer needed. Capabilities: `--cap-drop ALL` plus **six**:
  `SYS_ADMIN NET_ADMIN NET_RAW SETUID SETGID SETFCAP`. `no-new-privileges` works too. All
  five smoke checks pass (start, git status, tmux, `codex sandbox`, curl through the proxy
  with the direct way out closed), and so does the whole isolation check.
- **R works with the default profile plus five calls: `clone`, `mount`, `umount2`,
  `pivot_root`, `chroot`**, with no capability at all (`--cap-drop ALL`,
  `no-new-privileges`, `--user 1000:1000`). R's limits are as before: only root inside,
  network `host`/`none`, shared loopback, no nested sandboxes.
- **The sentry runs in a user namespace of its own.** In R+net: its own userns, mntns,
  pidns and the sandbox's netns; `uid_map 0 0 4294967295` (identity), rights only inside
  its own userns (`chown dac_override dac_read_search fowner fsetid sys_ptrace`), an almost
  empty root (`etc`, `proc`), `NoNewPrivs`, 2-4 seccomp filters. It does **not** have the
  runner's SYS_ADMIN and NET_ADMIN. The first report's conclusion ("an escape from the
  sentry gives root in the runner with SYS_ADMIN and NET_ADMIN") was wrong.
- `apparmor=unconfined` cannot be checked here: Docker Desktop has no AppArmor. That stays
  for Linux.
- The security difference from `unconfined`: for everything that runs in the runner's
  context (runsc before it sets its own filters, the gofer, any process of the runner), the
  whole of Docker's deny list applies again: `io_uring`, `keyctl`, `userfaultfd`, `kexec`,
  kernel modules, `ptrace` without `SYS_PTRACE` and so on. Plus nine capabilities of the
  default set are dropped.

## 2. Environment

The same as in the first spike: MacBook Air M2, macOS 27.0, Docker Desktop 4.100.0, Engine
29.9.3 (git `70efc0e`), containerd 2.4.2, runc 1.5.3, VM kernel 7.0.14-linuxkit aarch64,
cgroup v2, Security Options `seccomp (builtin)`, `cgroupns`; no AppArmor and no SELinux.
runsc `release-20261123.0`. The images `spike-sandbox`/`spike-runner` from the first spike's
Dockerfile with pinned versions (claude 2.1.332, codex 0.172.0, opencode 1.19.6, kilo
7.8.32, uv 0.13.10, Node 22.23.5) and `strace`, `capsh`, `jq` (`docker/Dockerfile`,
`logs/03-build.txt`). Runner limits `--cpus 4 --memory 4g`. Docker Desktop's settings were
not changed.

## 3. Docker's default profile

`seccomp/default.json`, source in `seccomp/SOURCE.txt`: tag `docker-v29.9.3`, commit
`70efc0e31da3a115fc87574d1b786fa2b867c346` (the same as the engine's git commit). In moby 29
the file lives at `vendor/github.com/moby/profiles/seccomp/default.json`
(`moby/profiles/seccomp v0.2.4`); the old path `profiles/seccomp/default.json` gives 404.

What in it matters for runsc:

| call | in the default profile |
|---|---|
| `pivot_root` | **absent altogether** (denied even with SYS_ADMIN) |
| `mount`, `umount2`, `unshare`, `setns`, `clone` with namespace flags, `clone3`, `bpf`, `perf_event_open`, `fsopen`… | only with `CAP_SYS_ADMIN` in the container's set |
| `clone` without namespace flags | always |
| `clone3` without SYS_ADMIN | an explicit `ERRNO` = `ENOSYS` (38) |
| `chroot` | only with `CAP_SYS_CHROOT` in the container's set |
| `ptrace`, `process_vm_readv/writev` | always (kernel ≥ 4.8) |
| `seccomp`, `memfd_create` | always |
| `io_uring_*`, `keyctl`, `userfaultfd` | absent |

The built-in profile and this file passed through `--security-opt seccomp=…` give the same
error (`logs/10-try-01-*`, `10-try-02-*`), so the file is the one the engine uses.

## 4. R+net

Reference point: `unconfined` passes 5/5 (`logs/10-try-00-Rnet-unconfined.txt`).

### 4.1 Seccomp

| step | result |
|---|---|
| default + SYS_ADMIN, NET_ADMIN | ❌ `error setting up chroot: pivot_root failed … operation not permitted` (as P5 in the first spike) |
| + `pivot_root` | ✅ 5/5 (`logs/10-try-03-Rnet-pivot.txt`) |
| `defaultAction: SCMP_ACT_LOG` + `pivot_root` | ✅ 5/5; in the kernel log only `io_uring_setup` (runsc), `io_uring_register` and `mseal` (sentry) (`logs/11-dmesg-seccomp-all.txt`) |

Both `mount proc` (`Unable to mount a new instance of the procfs`) and the fallback to a bind
show **under `unconfined` too** (checked in runsc's debug log): it is the kernel that refuses,
not seccomp. Docker masks `/proc` paths (`/proc/kcore`, `/proc/keys`, `/proc/sys`…), and a new
proc instance cannot be mounted over them. runsc falls back to a recursive bind by itself;
this is not an error.

`io_uring_setup` and `mseal` are deliberately **not added**: runsc only warns "This slows down
gVisor sandbox teardown", and io_uring is a large kernel attack surface. `mseal` is optional
for the sentry.

### 4.2 Capabilities

`--cap-drop ALL`, then Docker's default set with SYS_ADMIN and NET_ADMIN, and each
capability removed in turn (`logs/20-caps-sweep.txt`):

| removed | result | what breaks |
|---|---|---|
| CHOWN, DAC_OVERRIDE, FSETID, FOWNER, MKNOD, SETPCAP, NET_BIND_SERVICE, KILL, AUDIT_WRITE | ✅ | not needed |
| NET_RAW | ❌ | sentry: `failed to createSocket for eth0: unable to create raw socket` (AF_PACKET on the sandbox netns's eth0) |
| SETUID, SETGID, SETFCAP | ❌ | `cannot create gofer process: gofer: fork/exec /proc/self/exe: operation not permitted`: runsc creates a userns for the gofer and the sentry and writes `uid_map`/`gid_map`; to map uid 0 the kernel (≥ 5.12) also requires SETFCAP |
| SYS_CHROOT | ❌ | `failed to chroot to "/root"`, but only because of the profile's rule: with `chroot` in the profile and without SYS_CHROOT ✅ (`logs/10-try-26-*`) |
| NET_ADMIN | 4/5 | runsc works, but the runner cannot create the veth and iptables (`netns.sh`); needed for the netns-and-proxy scheme |
| SYS_ADMIN | ❌ | neither netns nor runsc |

It is better to drop SYS_CHROOT and put `chroot` into the profile: the runner's root without
SYS_CHROOT cannot chroot by itself, and runsc does it in its own userns, where it has the
right.

### 4.3 The result for R+net

`seccomp/runner.json` = `default.json` plus one rule:

```diff
@@ after the last rule of syscalls @@
+    {
+      "names": ["pivot_root", "chroot"],
+      "action": "SCMP_ACT_ALLOW",
+      "comment": "runsc (spike 2)"
+    }
```

- `pivot_root`: runsc boot (sandbox) and the gofer move their root into an empty folder
  (`error setting up chroot`, `failed to change the root file system`). Without it no
  sandbox starts.
- `chroot`: runsc, while preparing the root; in Docker's profile it is tied to the
  container's CAP_SYS_CHROOT, which we drop.

```yaml
runner:
  init: true
  cap_drop: [ALL]
  cap_add: [SYS_ADMIN, NET_ADMIN, NET_RAW, SETUID, SETGID, SETFCAP]
  security_opt:
    - seccomp=./seccomp/runner.json
    - apparmor=unconfined          # check separately on Linux with AppArmor
    - no-new-privileges:true
  sysctls: [net.ipv4.ip_forward=1]
```

Checked in full (`logs/10-try-28-Rnet-final.txt`): 5/5; isolation
(`logs/31-iso-Rnet-final.txt`) below.

## 5. R (rootless)

Reference point: `unconfined` passes 4/4. `codex sandbox` does not work in R by design
(`bwrap: setting up uid map`); it is not part of R's smoke check (`logs/10-try-40-*`). With the
default profile: `Error executing inside namespace: re-executing self: fork/exec
/proc/self/exe: operation not permitted`.

The LOG mode did **not** help here: rootless runsc passes under it, but the kernel log has
not one entry of it, only the calls of runc itself at container start (`open_tree`,
`fsopen`, `fsconfig`, `fsmount`, `logs/42-R-log-syscalls.txt`). I did not find the cause.
The set was found by search: all candidates together, then each removed in turn
(`logs/43-R-sweep.txt`):

| removed | result |
|---|---|
| `clone` | ❌ `re-executing self: fork/exec /proc/self/exe` (a new userns and other namespaces) |
| `mount` | ❌ `error converting mounts: mount("", "/proc/self/fd/18", "", 0x84000)` (MS_REC\|MS_SLAVE) |
| `umount2` | ❌ `error umounting the old root file system` |
| `pivot_root` | ❌ `pivot_root failed` |
| `unshare`, `setns` | ✅ not needed |

With `--cap-drop ALL`, `chroot` is added (`failed to chroot to "/root"`, the same profile
rule as in R+net). `seccomp/runner-rootless.json` = `default.json` plus
`["clone", "mount", "umount2", "pivot_root", "chroot"]`. The rule for `clone` is
unconditional, so it allows namespace flags too.

```yaml
runner:
  user: "1000:1000"
  init: true
  cap_drop: [ALL]
  security_opt:
    - seccomp=./seccomp/runner-rootless.json
    - apparmor=unconfined          # check separately on Linux with AppArmor
    - no-new-privileges:true
```

Checked: 4/4 (`logs/10-try-48-R-min5-noCaps.txt`); isolation (`logs/32-iso-R-final.txt`)
below.

## 6. Isolation with the final profiles

Two `runsc run -d` sandboxes, each with its own copy of the rootfs from `spike-sandbox` (no
runsc in it), its own `/work/sN`; the marker `/root/runner-marker` with a random string; the
runner's services on `127.0.0.1:9999` and `0.0.0.0:9998`. In R+net each has its own netns
and the "proxy only" rules. Checks from S1 as root (`scripts/p5-probe.sh`).

| attempt from S1 | R+net (`runner.json`) | R (`runner-rootless.json`) |
|---|---|---|
| processes of S2 and the runner | closed | closed |
| S2's files, the marker by name and by string | closed | closed |
| `docker.sock` | absent | absent |
| TCP to S2 | closed (`No route to host`) | **open** (shared `127.0.0.1`) |
| the runner's `127.0.0.1:9999` | closed | **open** |
| `<runner ip>:9998` | closed | **open** |
| `mount`, modules, iptables, `ip` as root | refused | refused |

R's network holes are the same as in the first spike: they follow from `--network=host`,
not from the profile.

### What runs in the runner (`scripts/ns-inspect.sh`)

| process | R+net | R |
|---|---|---|
| runner, PID 1 | init userns `4026531837`; root with 6 capabilities | init userns; uid 1000, no capabilities |
| sentry (`runsc-sandbox boot`) | own userns, mntns, pidns; the sandbox's netns; `uid_map 0 0 4294967295`; CapEff = CapBnd = `chown dac_override dac_read_search fowner fsetid sys_ptrace`; root `etc proc`; NoNewPrivs; 2-4 filters | own userns; the runner's netns; `uid_map 0 1000 1`; CapEff `… net_bind_service net_admin sys_ptrace` (in its own userns) |
| gofer | own userns and mntns; `uid_map 0 0 4294967295`; `chown dac_override dac_read_search fowner fsetid sys_chroot`; root = the sandbox's rootfs | own userns; `uid_map 0 1000 1` |

## 7. What an escapee gets

Two cases must be told apart.

**Code runs in the sentry** (a bug in its implementation of system calls). It stays under
runsc's filter **and** under the runner's profile: the filters stack, and the stricter one
applies. runsc's filter for the sentry is already very narrow, so `runner.json` adds almost
nothing here. The sentry's namespaces protect:

- R+net: uid 0 of the runner for files (the mapping is identity), but rights only in its
  own userns. CAP_DAC_OVERRIDE and the like act on the files visible in its mntns, and that
  is almost empty; plus the file descriptors the sentry holds (the connection to the gofer).
  The network is only its own netns, where the runner's iptables rules cannot be removed.
  The runner's SYS_ADMIN and NET_ADMIN are out of reach.
- R: uid 1000 of the runner, only it is mapped. The sentries and gofers of the other
  sandboxes have the same uid. The default profile allows `ptrace`, so whether one sentry
  can trace another (Yama, dumpable) is **not checked**. *(Checked later in
  [S3](s3-linux.md) 4.6: it can.)*

**Code runs in the runner's context** (a bug in runsc before the filters are set, a bug in
the gofer, a kernel vulnerability reachable from the gofer). Here the runner's profile,
capabilities and AppArmor are the whole protection:

- `unconfined`: any system call is available, including `io_uring`, `keyctl`, `bpf`,
  `kexec`, `userfaultfd`, `perf_event_open`, with SYS_ADMIN and NET_ADMIN and Docker's
  default set.
- `runner.json`: Docker's deny list applies again; only `pivot_root` and `chroot` are
  allowed beyond it. 6 capabilities instead of 16. But SYS_ADMIN still opens, in Docker's
  profile, `bpf`, `perf_event_open`, `fsopen`/`fsmount`, `mount`, `unshare`, `setns`,
  `syslog`, `sethostname`… (the block `includes.caps: CAP_SYS_ADMIN`). It can be narrowed
  further by removing from this block what runsc does not need. That is the next step, not
  checked here. *(Done in [S3](s3-linux.md) 4.1.)*
- `runner-rootless.json` (R): uid 1000 with no capabilities, plus `clone` with namespace
  flags, `mount`, `umount2`, `pivot_root`, `chroot`. The kernel's features are reachable
  only through an unprivileged user namespace, but that kernel attack surface stays open.

## 8. Problems and surprises

1. **The profile's path in moby 29 changed:** it is now
   `vendor/github.com/moby/profiles/seccomp/default.json`.
2. **`SCMP_ACT_LOG` and rootless runsc.** For R+net the log works (`type=1326` in the VM's
   dmesg), and for rootless runsc on the same kernel not one entry appears. Search by
   elimination turned out more reliable. Counting by the number of dmesg lines is
   unreliable too: the ring buffer shifts, so count by timestamp
   (`scripts/dmesg-seccomp.sh`).
3. **`mount proc` fails under `unconfined` too** because of Docker's masked `/proc` paths.
   This is not seccomp; runsc falls back to a bind by itself.
4. **`includes.caps` in Docker's profile looks at the container's capability set**, not at
   the process's rights. So `chroot` in rootless runsc (uid 1000, chroot inside its own
   userns) fails with `--cap-drop ALL`, although the kernel does not need the runner's
   CAP_SYS_CHROOT.
5. **Preparing the bundle.** Unpacking the rootfs (`tar` with owners) needs CAP_CHOWN,
   which the minimal set lacks. Here the rootfs was prepared once in a volume
   (`spike-rootfs`) and by a separate privileged `docker exec`. In LADO this must be done
   not by the runner but by the image build or the `lado` container.
6. **My own bug in the scripts** `b-rnet.sh`/`b-r.sh` (zsh does not split a variable into
   words; in the second, an extra argument was taken for the LOG flag). The wrong runs were
   redone; the tables hold only the repeated ones.

## 9. What was not done

- The whole of Phase A (except the smoke check and isolation), Phase C, the Linux and
  Windows appendices.
- AppArmor (Docker Desktop has none).
- Narrowing the `CAP_SYS_ADMIN` block of Docker's profile and the `ptrace` check between
  sentries in R.
- The effect of denying `io_uring` on sandbox teardown time was not measured.

## 10. Cleanup

Everything labelled `lado.spike=2` was removed (the `spike-*` containers, the network
`spike-net`, the volumes `spike-rootfs`, `spike-rootfs-1000`, the images `spike-runner`,
`spike-sandbox`), the builder `spike2-builder` and the image `moby/buildkit:buildx-stable-1`.
Comparison of `logs/00-snapshot-before.txt` and `logs/99-snapshot-after.txt`: everything of
mine is gone, the earlier build cache (88 entries) is in place. **One difference is not
mine:** the container `lado-guide-lado-1` (image `lado:local`, port 8766), the volume
`lado-guide_home` and the network `lado-guide_default` disappeared during the spike. The
container had been started seconds before the first snapshot, apparently from another
session; my cleanup removed only objects labelled `lado.spike=2` or named `spike-*`, and
Docker's events (the last 256 are kept) no longer show the removal. `lado-lado-1` was not
touched and runs, `:8765` answers 200. Docker Desktop's settings were not changed.

## Files (in the spike folder, not committed)

- `docker/Dockerfile`, `seccomp/` (`default.json`, `runner.json`, `runner-rootless.json`,
  `SOURCE.txt`, the intermediate `try-*.json`).
- `scripts/`: `try.sh` (one attempt: runner, bundle, smoke), `smoke.sh`, `smoke-inner.sh`,
  `mkprofile.py`, `b-rnet.sh`, `b-caps*.sh`, `b-rnet-final.sh`, `b-r.sh`, `b-r-sweep.sh`,
  `b-iso.sh`, `b-iso-r.sh`, `p5-*.sh`, `ns-inspect.sh`, `dmesg-seccomp.sh`, `snapshot.sh`,
  `build.sh`, `runner.sh`, `mkspec.py`, `netns.sh`, `proxy.py`.
- `logs/`: `10-try-*` one attempt each, `20-caps-sweep.txt`, `43-R-sweep.txt`, `3x-iso-*`,
  `11-dmesg-*`, the snapshots before and after.
