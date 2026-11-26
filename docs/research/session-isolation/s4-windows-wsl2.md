# S4: gVisor on Windows (round 2, WSL2 on a GitHub Actions runner)

Date: 2026-11-25. Brief: [gvisor-spike-2-brief.md](gvisor-spike-2-brief.md) (the updated
one, with section 0.1). Machine: GitHub's hosted runner `windows-2025`, with Ubuntu 24.04 on
WSL2 inside it and **Docker Engine 28.0.4, not Docker Desktop**: the hosted runner has no
Docker Desktop (Windows Server, licence, a reboot needed), and the runner's built-in Docker
runs Windows containers only. The WSL2 kernel is the one Docker Desktop runs on, so
everything that depends on the kernel (seccomp, KVM, userns, gVisor) carries over; what
depends on Docker Desktop itself (its file sharing with `C:\`, its VM `docker-desktop`, ECI)
is **not** checked here: that is round 3 ([gvisor-spike-3-brief.md](gvisor-spike-3-brief.md)).
Translated from the Russian report (session artifact `report-17630bda`); all tables and
numbers are kept. The report refers to raw logs in `runs/<id>/` and scripts in `repo/`;
**they are not committed to this repository**.

## 1. Summary

- **R+net and R work in WSL2.** `runner.json` from macOS and the six capabilities pass
  5/5; `runner-rootless.json` with no capabilities passes 4/4 (`codex sandbox` does not
  work in R by design). The WSL kernel has no userns restriction and no AppArmor, so R
  works at once, without a custom AppArmor profile (unlike Ubuntu 24.04).
- The narrow profile (the CAP_SYS_ADMIN block = `mount umount2 unshare setns clone
  clone3`): 5/5; each of the six capabilities is needed, as on Linux and macOS.
- **`/dev/kvm` exists in WSL2, `--platform=kvm` works** in R+net and R, but is **slower
  than systrap** (KVM here is nested in Hyper-V inside an Azure VM): `git status` 1.5×,
  exec 2.2× worse.
- Compatibility (A.2): 32 of 32. The "proxy only" network and isolation: as on Linux.
- **A bind mount from the `C:` disk (drvfs/9p) is unusable:** git as uid 1000 cannot clone
  (`chmod on .git/config.lock failed: Operation not permitted`); as root all files are
  `rwxrwxrwx root:root`, `chmod` has no effect, git itself sets `core.filemode=false`.
  Small files there are ≈200 times slower than on WSL's ext4 (A 74.7 s against 0.36 s), and
  in B another 1.4 times slower (107 s).
- **ext4 inside WSL and a named volume** behave like Linux: for A ≈ local, for B
  `git status` 1.45 times slower than local.
- **Line endings:** inside a Linux container git converts nothing. The problem is on the
  Windows side: Git for Windows by default (`core.autocrlf=true`) checked out our own test
  bed's scripts with CRLF, and bash in WSL failed on them (`set: -\r: invalid option`). The
  cure is `.gitattributes` with `eol=lf`.
- Landlock in the WSL kernel: ABI 7.
- What was cut: real Docker Desktop (and its file sharing), the Hyper-V backend, ECI: none
  on the runner. Speed only for W2, W6py, W7 (as the brief allows).

## 2. Environment

| | |
|---|---|
| Windows | Windows Server 2025 Datacenter, 10.0.26100 (WSL says Windows 10.0.26100.33828); Azure VM, AMD EPYC (7763 / 9V74 in different runs), 2 logical CPUs; Hyper-V, VirtualMachinePlatform and WSL enabled |
| WSL | 3.0.5.0, kernel 6.18.58.1-microsoft-standard-WSL2, WSLg 1.0.79; `wsl --status`: Default Version 2; `.wslconfig` not set (nested virtualization works by default) |
| Distribution | Ubuntu 24.04 (`wsl --install -d Ubuntu-24.04 --web-download`, ≈3 min); WSL sees ≈3.8 GB of memory, an ext4 disk of 1 TB (virtual) |
| Docker | Engine 28.0.4 from get.docker.com inside WSL (`VERSION=28.0.4`, as on the Linux runners), overlay2, cgroup v2 + systemd, Security Options: seccomp |
| LSM in the WSL kernel | `capability,landlock,yama,safesetid,selinux,bpf,ima`; no AppArmor; no `apparmor_restrict_unprivileged_userns`; `yama.ptrace_scope=1`; `unshare -U -r` works on the WSL "host" |
| KVM | `/dev/kvm` `crw-rw---- root:kvm` in WSL, reaches the container (`--device /dev/kvm`) |
| Docker Desktop | absent; ECI and the Hyper-V backend cannot be checked |

Limits for A and B: `--cpus 2 --memory 3g`. Runs: `45690983704` (env, A.1, B, kvm, A.5),
`45693638299` (A.4, A.2, A.3, line endings v1), `45699779205` (line endings v2).

## 3. Phase A

### 3.1 Privileges (`runsc run`)

P1 ✅, P2 ✅, P5 ❌ (`pivot_root`), P6 ❌ (`gofer: fork/exec /proc/self/exe`), R+net ✅,
**R ✅** (no userns restriction).

### 3.2 Compatibility

R+net, the final profile, uid 1000: all 32 checks ✅
(`runs/45693638299/windows-wsl2/logs/50-compat.txt`), including the screens of the four
CLIs, `codex sandbox`, bwrap, `unshare -U`, inotify.

### 3.3 Speed: three bind places

A is a plain container, B is R+net (systrap). Median of three runs, s
(`runs/45693638299/windows-wsl2/logs/60-bench.csv`). "local" is the container's disk / the
sandbox's rootfs (WSL's ext4); "C:" is `/mnt/c/spike-bind` (drvfs, 9p); "WSL ext4" is the
distribution's folder `/root/spike-bind`; "volume" is a named Docker volume.

| workload | A local | B local | B/A | A C: | B C: | A WSL ext4 | B WSL ext4 | B/A | A volume | B volume | B/A | B kvm local |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| W2 `git status` ×20 | 1.24 | 6.44 | 5.2× | ❌ git | ❌ git | 0.83 | 9.30 | 11.2× | 0.83 | 9.32 | 11.2× | 9.86 |
| W2 `git log --stat` | 0.43 | 0.90 | 2.1× | ❌ | ❌ | 0.42 | 0.90 | 2.1× | 0.42 | 0.90 | 2.1× | 1.90 |
| W2 `git grep` | 0.11 | 0.45 | 4.1× | ❌ | ❌ | 0.09 | 0.60 | 6.7× | 0.08 | 0.63 | 7.9× | 0.74 |
| W6py create 20 000 files | 0.50 | 0.90 | 1.8× | **74.66** | **107.27** | 0.36 | 2.10 | 5.8× | 0.40 | 2.30 | 5.8× | 1.36 |
| W6py `os.walk` | 0.03 | 0.10 | 3.3× | 0.88 | 1.06 | 0.02 | 0.11 | 5.5× | 0.02 | 0.11 | 5.5× | 0.14 |
| W6py `rmtree` | 0.28 | 0.57 | 2.0× | 20.77 | 27.00 | 0.21 | 0.56 | 2.7× | 0.20 | 0.58 | 2.9× | 3.49 |
| W7 2000 × `/bin/true` | 2.33 | 12.83 | 5.5× | 2.22 | 12.58 | 2.23 | 13.15 | 5.9× | 2.17 | 13.06 | 6.0× | 27.80 |

On C: W2 was not measured: a clone of django cannot be created there (section 5). macOS for
comparison (B/A local): `git status` 5.95×, file creation 1.53×, exec 4.72×.

Conclusions:

1. On local and on ext4/volume B/A is of the same order as on Linux and macOS. An exec in
   WSL is dear even without gVisor (≈1.1 ms); with gVisor ≈6.4 ms.
2. WSL's ext4 and a volume are the same; for gVisor a bind through the gofer is dearer than
   local (`git status` 9.3 s against 6.4 s).
3. **C: is more than two orders of magnitude slower** on small files and breaks git. LADO
   on Windows must keep repositories in a volume or in WSL's ext4, never on `C:\`.

### 3.4 Network

`runs/45693638299/windows-wsl2/logs/40-net.txt`: for uid 1000 and root all checks OK, the
runner's rules unchanged, as on Linux.

### 3.5 Isolation

`runs/45690983704/windows-wsl2/logs/30-iso-*.txt`: R+net, all closed; R, all closed except
the shared localhost (TCP to S2, the runner's services), as on Linux and macOS.

## 4. Phase B

`runs/45690983704/windows-wsl2/logs/20-b.txt`:

| check | result |
|---|---|
| R+net, default 28.0.4 | ❌ `pivot_root` |
| R+net, `runner.json` from macOS | ✅ 5/5 |
| R+net, `runner-28.0.4.json` | ✅ 5/5 |
| R, `runner-rootless-28.0.4.json` | ✅ 4/4 |
| R, default | ❌ `re-executing self: operation not permitted` |
| narrow CAP_SYS_ADMIN block | ✅ 5/5 |
| without any one of the six capabilities | ❌ (the same errors as on Linux) |
| `SCMP_ACT_LOG`, R+net | through the fallback rule only `io_uring_setup`, `io_uring_register`, `mseal` |
| `SCMP_ACT_LOG`, R | `clone`, `mount`, `io_uring_setup` |

WSL has no AppArmor, so step B.6 does not apply. The final profiles and the compose fragment
are as in the Linux report ([S3](s3-linux.md) 4.4); `apparmor=` has no effect in WSL.

## 5. Windows appendix

- **KVM.** `/dev/kvm` exists in WSL2, `nestedVirtualization` in `.wslconfig` was not needed;
  `--device /dev/kvm` reaches the container; `--platform=kvm` works in R+net and R
  (`Config.Platform: kvm`), including with 0660 and no `--group-add` (as on Linux, the cause
  not found). Speed: the last column of table 3.3; worse than systrap everywhere.
- **Three bind places:** table 3.3.
- **Line endings and permissions** (`runs/45699779205/windows-wsl2/logs/70-crlf.txt`; the
  source is a local repository with an executable `run.sh` and a text file, cloned inside
  the container):

  | place | uid 1000 | root |
  |---|---|---|
  | C: (drvfs, `uid=0,gid=0`, without `metadata`) | ❌ no clone: `chmod on .git/config.lock failed: Operation not permitted` | a clone exists; all files `rwxrwxrwx root:root`; `chmod -x` has no effect; git sets `core.filemode=false`; LF is kept |
  | WSL ext4 | ✅ `100755` → `-rwxr-xr-x agent:agent`; `chmod -x` shows in `git status` | ✅ |
  | volume | (the volume's folder was not open to uid 1000: a mistake in the check) | ✅ as ext4 |

  CRLF does not appear inside Linux (`core.autocrlf` is not set). CRLF appears when Git for
  Windows checks the repository out (by default `autocrlf=true`): that is how our own scripts
  broke on this runner. For LADO this means: repositories that agents open in the sandbox
  are cloned from inside Linux (volumes/WSL), not from the Windows side.
- **Docker Desktop's Hyper-V backend:** not on the runner.

## 6. Problems and surprises

1. The hosted Windows runner **supports WSL2 and nested virtualization** (I expected not):
   Ubuntu installs in ≈3 minutes, `/dev/kvm` is there.
2. The runner's built-in Docker runs Windows containers only; Linux containers only through
   Docker Engine in WSL (or Docker Desktop, which is absent).
3. Git for Windows checks files out with CRLF; bash in WSL fails on `\r`.
4. WSL has ≈3.8 GB of memory; a 3 GB limit for A/B is almost all of it.
5. My mistake in the first version of the permissions check: the lado repository has not one
   `100755` file, so there was nothing to compare; the second version uses a test repository
   of its own.

## 7. Cleanup

The runner is disposable, the VM is destroyed after the job; the snapshots before and after
are in the logs but mean nothing. The host's settings were not changed (no sysctl in WSL was
touched beyond what Docker needs).
