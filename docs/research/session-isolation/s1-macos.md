# S1: gVisor inside a Docker Desktop container on macOS (round 1)

Date: 2026-11-25, about 2 hours of work. Brief: [gvisor-spike-brief.md](gvisor-spike-brief.md)
plus local amendments in `BRIEF-local.md`. The machine was not clean: LADO's own Docker
container runs on it; it was stopped for the measurements and started again afterwards.
Translated from the Russian report (session artifact `report-702d5317`); all tables and
numbers are kept. The report refers to its raw logs and scripts (`logs/…`, `scripts/…` in
the spike folder `~/gvisor-spike/`); **they are not committed to this repository**.

## 1. Summary

- **It works.** runsc `release-20261123.0` starts sandboxes inside an ordinary Docker
  Desktop container (Apple M2, VM linuxkit 7.0.14, cgroup v2). There is no `/dev/kvm`, so
  the platform is systrap; KVM does not work.
- **The minimal privileges for `runsc run` with a bind mount:**
  `--security-opt seccomp=unconfined` with no added capabilities; runsc runs with
  `--rootless` as uid 1000 of the runner (profile **R**). R's limits: network `none`/`host`
  only; only root works inside the sandbox; nested sandboxes (bwrap, `unshare -U`,
  `codex sandbox`) do not work.
- **The full profile R+net:** `SYS_ADMIN + NET_ADMIN`, `seccomp`/`apparmor=unconfined`,
  `--sysctl net.ipv4.ip_forward=1`. Each sandbox gets its own netns, the agent runs as
  uid 1000, and all of Phase 2 passes: git, tmux, uv, npm, gcc, the four CLIs, and also
  bwrap, `unshare` and `codex sandbox`.
- Profiles P5 (`SYS_ADMIN` with the default seccomp) and P6 (as LADO runs today) **do not
  work**: Docker's default seccomp blocks `pivot_root`, `mount` of proc and `clone` with
  namespaces.
- **Speed.** CPU with no loss (1.0×). Downloads (`uv sync`/`npm ci` with a cold cache) about
  1.0-1.15×. LADO's tests about 2×. The heaviest is whatever does many `stat`/`exec`:
  `git status` 4-6×, fork/exec about 4.5× (≈1 ms per exec), small files on bind 2.3×
  (without exec). VirtioFS alone, even without gVisor, slows `git status` down **21 times**
  (9.1 s against 0.43 s): gVisor on the local disk (2.5 s) is faster than a plain container
  on a macOS bind mount (9.1 s).
- **Network limited to one destination works:** iptables in the runner's netns (R+net), or
  rules that a neighbouring container with `NET_ADMIN` puts into the runner's netns (R).
  Neither the agent nor root inside the sandbox can remove them.
- **Isolation.** Processes, files, the runner marker and `docker.sock` are closed in both
  profiles. Without iptables rules the sandboxes see each other over the network; in R they
  share the runner's localhost.
- **What was cut:** the rerun on the other VMM (section 9); the network clone of django was
  done once (A, 373 s at ≈0.8 MB/s) instead of comparing A and B; step 4.3c
  (`--network=none` and a unix socket) was not done because 3a works. Everything else was
  done in full.

**Recommendation:** do it. Profile R+net for the runner, a netns and iptables per sandbox,
repositories and worktrees on the container's own disk (a volume), not on a macOS bind
mount.

## 2. Environment

| | |
|---|---|
| Mac | MacBook Air, Apple M2, 8 cores, macOS 27.0 (26A428), Darwin 27.0.0 arm64 |
| Disk | 460 GB, 81 GB free before the spike, 78 GB after |
| Docker Desktop | 4.100.0 (246961), Engine 29.9.3, containerd v2.4.2, runc 1.5.3 (`logs/02-env.txt`) |
| VM | Apple Virtualization framework, VirtioFS, Rosetta on, 8 CPU, 8 GB (7.75 GiB visible) |
| VM kernel | 7.0.14-linuxkit aarch64, cgroup v2, cgroupfs driver, Security Options: seccomp, cgroupns |
| KVM | no `/dev/kvm` even with `--privileged`; vmx/svm 0 (arm64) |
| Landlock | `/sys/kernel/security/lsm` not visible in the container (not even with `--privileged`) |
| runsc | `release-20261123.0`, spec 1.2.1 |
| Image | Debian bookworm arm64, Node 22.23.5, uv 0.13.10, claude 2.1.332, codex-cli 0.172.0, opencode 1.19.6, kilo 7.8.32 |

Docker Desktop's settings were not changed. Limits for A and B: `--cpus 4 --memory 4g`,
because the VM has only 8 GB.

## 3. Privileges (Phase 1)

`runsc do /bin/sh -c 'uname -a; id; cat /proc/version; echo OK'`; ✅ means the sandbox shows
`Linux version 4.19.0-gvisor`. Full output: `logs/04-p1-matrix.txt`, `logs/04-p1-P*-full.log`.

| runsc flags \ profile | P1 privileged | P2 SYS_ADMIN+unconfined | P3 P2+NET_ADMIN+SYS_PTRACE | P4 seccomp=unconfined | P5 SYS_ADMIN | P6 defaults |
|---|---|---|---|---|---|---|
| `--network=sandbox` | ❌ cgroup busy | ❌ `ip link add` (no NET_ADMIN) | ❌ `sysctl -w ip_forward` | ❌ `ip link add` | ❌ `ip link add` | ❌ `ip link add` |
| `sandbox --ignore-cgroups` | ✅ | ❌ `ip link add` | ❌ `sysctl -w` | ❌ | ❌ | ❌ |
| `none --ignore-cgroups` | ✅ | ✅ | ✅ | ❌ needs CAP_SYS_ADMIN for chroot | ❌ sandbox exited (`pivot_root` EPERM) | ❌ `fork/exec /proc/self/exe` EPERM |
| `host --ignore-cgroups` | ✅ | ❌ `ip link add` | ❌ `sysctl -w` | ❌ | ❌ | ❌ |
| `--rootless none --ignore-cgroups` | ✅ | ✅ | ✅ | ✅ | ❌ sandbox exited | ❌ EPERM |
| `--rootless host` | ❌ cgroup busy | ✅ | ✅ | ✅ | ❌ sandbox exited | ❌ EPERM |
| `none … --platform=systrap` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `--platform=kvm` | ❌ no `/dev/kvm` | ❌ | ❌ | ❌ | ❌ | ❌ |

Causes:

- P5: `error setting up chroot: pivot_root failed … operation not permitted`
  (`logs/04-p5-debug.txt`). Docker's default seccomp.
- P6: `gofer: fork/exec /proc/self/exe: operation not permitted` (`clone` with namespace
  flags).
- `--network=sandbox` of `runsc do` makes the veth itself and runs
  `sysctl -w net.ipv4.ip_forward=1`. In a non-privileged container `/proc/sys` is read-only,
  and `sysctl -w` fails even with `NET_ADMIN` and `--sysctl ip_forward=1`
  (`logs/04-p2-netadmin-do.txt`). So `runsc do` with a network works only under
  `--privileged`; `runsc run` with a netns from `config.json` does not need it.

**`runsc run`, an OCI bundle, rootfs from `spike-sandbox` (it has no runsc:
`find rootfs -name 'runsc*'` gives 0), bind `/work` from macOS:**

| profile | result |
|---|---|
| P4 + `runsc --rootless` as the runner's root | starts, but uid 1000 in the sandbox sees the files as `nobody` and cannot write (`Invalid argument`); only uid 0 writes |
| **P4 + `runsc --rootless` as the runner's uid 1000, root inside** | ✅ read and write; on macOS the files belong to the Mac user |
| P4 + plain runsc | ❌ `can't run sandbox process in minimal chroot since we don't have CAP_SYS_ADMIN` |
| **P2 (+ NET_ADMIN, `--sysctl ip_forward=1` for the network)** | ✅ uid 1000 inside, read and write |

### Profile R (minimal)

```
docker run --security-opt seccomp=unconfined --user 1000:1000 --init ... spike-runner
# in the runner:
runsc --rootless --network=none|host --ignore-cgroups --root=$HOME/runsc-root run ID
```
```yaml
runner:
  user: "1000:1000"
  init: true
  security_opt: [seccomp=unconfined]
```
In the spec the process runs as uid 0 (in R only this uid maps to files).

### Profile R+net (working, all phases pass)

```
docker run --cap-add SYS_ADMIN --cap-add NET_ADMIN \
  --security-opt seccomp=unconfined --security-opt apparmor=unconfined \
  --sysctl net.ipv4.ip_forward=1 --init ... spike-runner
# in the runner, per sandbox: scripts/netns.sh up sN N, then
runsc --ignore-cgroups run ID      # config.json: linux.namespaces network -> /var/run/netns/sN
```
```yaml
runner:
  init: true
  cap_add: [SYS_ADMIN, NET_ADMIN]
  security_opt: [seccomp=unconfined, apparmor=unconfined]
  sysctls: [net.ipv4.ip_forward=1]
```
`SYS_PTRACE` is not needed. `apparmor=unconfined` changes nothing on Docker Desktop (there
is no AppArmor); whether it is needed on a Linux host with AppArmor was not checked here.

## 4. Compatibility (Phase 2)

Script `scripts/p2-compat.sh`; output `logs/05-p2-R.txt`, `logs/05-p2-Rnet.txt`, per check
`logs/05-p2-*-checks/`, the CLI screens `screen-*.txt`.

| check | R (rootless, root inside) | R+net (uid 1000 `agent`) |
|---|---|---|
| git clone lado, status, log, worktree + commit | ✅ | ✅ |
| tmux: session, send-keys, capture-pane, socket `-L lado` | ✅ | ✅ |
| `uv sync`, `uv run lado --version` → 0.48.0 | ✅ | ✅ |
| `node -e`, `npm ci` in `web/` (220 packages) | ✅ | ✅ |
| gcc hello world, make 4.3 | ✅ | ✅ |
| `--version` of claude, codex, opencode, kilo | ✅ | ✅ |
| UI in tmux for 12 s: Claude (theme choice), Codex (Sign in with ChatGPT), OpenCode, Kilo | ✅ | ✅ |
| `codex sandbox -- true` (in 0.172 without `linux`) | ❌ `bwrap: setting up uid map: Operation not permitted` | ✅; writing to `/etc` from it is denied |
| `bwrap --unshare-all --ro-bind / / true` | ❌ same | ✅ |
| `unshare -U -r true` | ❌ `write failed /proc/self/uid_map` | ✅ |
| ps, df, meminfo, ulimit, dmesg (gVisor's messages) | ✅ | ✅ |
| inotify in the sandbox and on the macOS bind mount | ✅ | ✅ |

In LADO's plain container bwrap, `unshare` and `codex sandbox` do not work; in gVisor with
R+net they work. This removes today's problem with Codex's sandbox.

## 5. Speed (Phase 3)

A: the plain container `spike-runner`, defaults, uid 1000. B: an R+net sandbox,
`runsc run`, uid 1000, `--overlay2=root:self` (the default: the upper layer on the
runner's disk), `--file-access=exclusive`, `--file-access-mounts=shared` (the default).
Both `--cpus 4 --memory 4g`. bind means a macOS folder (VirtioFS), local means the
container's disk (in B the sandbox's rootfs on the runner's disk). Median of three runs,
seconds. Raw data: `logs/06-bench.csv`; scripts `scripts/bench*.sh`. No run failed.

| workload | bind A | bind B | B/A | local A | local B | B/A |
|---|---|---|---|---|---|---|
| W1 `git clone --no-local` django (≈300 MB, full history) | 17.98 | 29.41 | 1.64× | 12.31 | 18.99 | 1.54× |
| W2 `git status` ×20 (django) | 9.10 | 36.68 | **4.03×** | 0.43 | 2.53 | **5.95×** |
| W2 `git log --stat -n 300` | 0.37 | 0.66 | 1.77× | 0.26 | 0.39 | 1.51× |
| W2 `git grep -n "def "` | 0.44 | 1.35 | 3.06× | 0.04 | 0.15 | 3.80× |
| W3 `uv sync`, cold cache (network) | 95.72 | 93.93 | 0.98× | 90.84 | 93.50 | 1.03× |
| W3 `uv sync`, warm cache | 1.01 | 1.90 | 1.88× | 0.05 | 0.09 | 1.86× |
| W4 `npm ci`, cold cache (network) | 13.24 | 15.18 | 1.15× | 18.55 | 18.86 | 1.02× |
| W4 `npm ci`, warm cache | 3.46 | 7.40 | 2.14× | 1.70 | 2.08 | 1.23× |
| W5 pytest `-n 4`, subset* | 16.85 | 32.61 | 1.93× | 14.10 | 32.02 | 2.27× |
| W6 20 000 files of 1 KB, through `head` (20 000 execs) | 13.19 | 48.49 | 3.68× | 6.03 | 30.48 | 5.05× |
| W6 `find \| wc -l` | 0.13 | 0.14 | 1.07× | 0.01 | 0.04 | ≈4× |
| W6 `rm -rf` | 2.61 | 3.95 | 1.51× | 0.15 | 0.31 | 2.07× |
| W6py the same files from one Python process** | 5.18 | 11.83 | **2.28×** | 0.38 | 0.58 | 1.53× |
| W6py walk with `os.walk` | 0.14 | 0.15 | 1.13× | 0.01 | 0.03 | ≈2× |
| W6py `shutil.rmtree` | 2.46 | 3.77 | 1.54× | 0.14 | 0.18 | 1.25× |
| W7 2000 × `/bin/true` | 0.46 | 2.01 | **4.36×** | 0.45 | 2.14 | **4.72×** |
| W8 CPU, Python | 0.98 | 0.99 | 1.01× | 0.99 | 1.00 | 1.01× |

\* `tests/test_state.py tests/test_runs.py tests/test_kits.py` with
`-x -p no:cacheprovider`; the full suite was not run.
\*\* W6py was added because W6 in fact measures mostly exec (20 000 runs of `head` at ≈1 ms
each in gVisor), not the filesystem.

The network clone of django (W1-net) was done once, in A: 373.5 s at ≈0.8 MB/s, so it
measures the network. The cold W3/W4 are bound by the network too, so there A ≈ B.

**Variants of B's flags** (medians, s):

| workload | B default | bind `--file-access-mounts=exclusive` | local `--overlay2=none` | local `--overlay2=root:memory` |
|---|---|---|---|---|
| W1 clone, bind / local | 29.41 / 18.99 | 29.12 | 20.98 | 19.63 |
| W2 status ×20, bind / local | 36.68 / 2.53 | 33.31 (3.66×) | 3.90 (9.16×) | 2.73 |
| W2 grep, bind / local | 1.35 / 0.15 | 1.36 | 0.21 | 0.15 |
| W6 create, bind / local | 48.49 / 30.48 | 50.92 | 31.00 | 29.50 |
| W6py create, bind | 11.83 | 11.72 | – | – |
| W6 rm, bind / local | 3.95 / 0.31 | 3.45 | 0.32 | 0.16 |

`exclusive` on bind gains up to 10% on `git status` and up to 12% on `rm`, but forbids
changes to the folder from outside the sandbox while it runs; that does not suit a shared
workspace. On local, `root:self` (the default) is better than `none`. `root:memory` is not
faster than `root:self` and takes memory; during the measurements the runner took about
530 MB.

**Profile R** (rootless, `--network=host`, root inside), medians, s: W6py create bind 12.23
/ local 0.62; W6py rm bind 3.79 / local 0.18; W7 bind 2.30 / local 2.14; W8 1.11-1.16. That
is the same as R+net, plus about 10% on CPU in W8.

Conclusions:

1. gVisor's main penalty falls on system calls: an exec about 1 ms against 0.23 ms,
   `stat`/`lstat` 4-6 times dearer. The file access flags change almost nothing.
2. A macOS bind mount is dear even without gVisor: `git status` in A on bind is 21 times
   slower than in A on local. The sandbox on the local disk (2.53 s) is almost 4 times
   faster than a plain container on bind (9.10 s). If repositories are kept on a volume,
   gVisor costs less than today's bind mount.
3. For agents that run many small `git` and shell calls, expect a slowdown of about
   1.5-2× on real work (tests 2×, builds 1.2-2×) when the repository is on the local disk.

## 6. Network (Phase 4)

Output: `logs/07-p4-Rnet.txt`, `logs/07-p4-R-sidecar.txt`, rules
`logs/07-p4-iptables-rules.txt`.

1. `--network=none`: `curl https://example.com` → `Could not resolve host`, only `lo` in
   the sandbox. ✅
2. Own netns (veth + NAT, `scripts/netns.sh`), no restrictions: DNS works, example.com 200,
   api.anthropic.com 404, so there is a connection. ✅
3. **Proxy only** (`spike-proxy`, an own HTTP CONNECT proxy `scripts/proxy.py`, port 3128,
   network `spike-net`):

   **3a, R+net, iptables in the runner's netns: works.**
   ```
   iptables -N SPIKE-SANDBOX
   iptables -A SPIKE-SANDBOX -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
   iptables -A SPIKE-SANDBOX -d $PROXY -p tcp --dport 3128 -j ACCEPT
   iptables -A SPIKE-SANDBOX -j REJECT --reject-with icmp-admin-prohibited
   iptables -I FORWARD -i veth-+ -j SPIKE-SANDBOX
   iptables -I INPUT   -i veth-+ -j REJECT          # the runner's own services
   ```
   R+net already has NET_ADMIN.

   **A variant for R (the runner has no NET_ADMIN), sandbox `--network=host`: works.** A
   neighbouring container puts the rules into the runner's netns:
   ```
   docker run --rm --network container:spike-r-rl --cap-add NET_ADMIN spike-runner sh -c '
     iptables -A OUTPUT -o lo -j ACCEPT
     iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
     iptables -A OUTPUT -d $PROXY -p tcp --dport 3128 -j ACCEPT
     iptables -A OUTPUT -j REJECT'
   ```
   The runner itself (uid 1000, and even root without NET_ADMIN) cannot remove them:
   `iptables … Permission denied`. In LADO the `lado` container could play this role.

   3b: runsc has no separate "one destination only" flag (`--network`: sandbox/host/none;
   there are the experimental `--netgofer` and `--pause-external-networking`), so it was
   not needed. 3c was not done.

Checks from inside (the same for uid 1000 and root in the sandbox, in both variants):

| check | result |
|---|---|
| proxy `http://proxy:3128/` | ✅ 200 |
| example.com directly, by name and by IP | ✅ blocked (DNS does not pass, TCP reject) |
| example.com through the proxy (`curl -x`) | ✅ 200, the CONNECT shows in the proxy's log |
| another port of the proxy host, the runner over veth | ✅ blocked |
| `iptables -F` / `-P OUTPUT ACCEPT` inside | no effect: `Failed to initialize nft: Protocol not supported`, legacy has no table |
| `ip route del/add`, `ip addr add`, `ip link set down` | `RTNETLINK answers: Operation not permitted` |
| raw and packet sockets | `PermissionError` |
| example.com after all attempts | ✅ still blocked; the runner's rules unchanged (empty `diff`) |

DNS: the sandbox needs its own `resolv.conf`. Docker's DNS `127.0.0.11` (user-defined
networks) is not reachable from the netns. For the "proxy only" scheme the sandbox needs no
DNS at all: the proxy resolves the names.

## 7. Isolation (Phase 5)

Two `runsc run -d` sandboxes, each with its own copy of the rootfs from `spike-sandbox`, its
own bind (`/work/s1`, `/work/s2`), a process `exec -a sNmarker sleep 1000`, and in S2
`nc :8080` listening. The runner marker: `/root/runner-marker` with a random string; access
to the runner's filesystem is judged only by it. In the runner, services on
`127.0.0.1:9999` and `0.0.0.0:9998`. Checks from S1 as root (`scripts/p5-probe.sh`; output
`logs/08-p5-Rnet.txt`, `logs/08-p5-R.txt`).

| attempt from S1 | R+net | R |
|---|---|---|
| processes of S2 and the runner (`ps`, `/proc/*/cmdline`) | closed (4-5 own pids visible) | closed |
| S2's folder: search for `s2-secret*` over `/`, `/proc/*/root` | closed (not found) | closed |
| the runner marker: by name and by string | closed | closed |
| `runsc` in the sandbox | absent | absent |
| `/var/run/docker.sock` | absent | absent |
| signals to S2 and the runner | closed: other pids not visible | closed |
| TCP to S2 | **open** `10.200.2.2:8080` without iptables | **open** `127.0.0.1:8080`: shared localhost |
| the runner's `127.0.0.1:9999` | closed (own loopback) | **open** |
| `<runner ip>:9998` | **open** without iptables | **open** |
| `mount -t tmpfs` as root | `permission denied` | `permission denied` |
| `modprobe`/`insmod` | no modules (`/lib/modules/4.19.0-gvisor`) | same |
| `iptables`, `ip link add` | not supported / EPERM | same |
| `dmesg` | gVisor's messages ("Starting gVisor…") | same |
| `/proc/1/environ` | only the variables from the spec | same |
| what it reports about itself | `Linux s1 4.19.0-gvisor`, uid_map `0 0 4294967295` | same |

R+net's network holes are closed by the rules of 6.3a: FORWARD reject for everything but the
proxy, so S1→S2 and S1→runner are blocked. In R the runner's shared loopback cannot be closed
from inside the runner: the sandboxes can reach each other's localhost services. R would need
`--network=none` and a unix socket (not checked).

**How gVisor's processes run in the runner** (`logs/08-p5-process-users.txt`):

- R+net: the sentry and the gofer run as uid 0 of the runner with reduced capabilities
  (sentry `CapEff 0x8001f`, gofer `0x4001f`), with seccomp, `NoNewPrivs`. If the agent
  escapes from the sentry, it is root in the runner with SYS_ADMIN and NET_ADMIN, but only
  inside the runner. *(Corrected by [S2](s2-macos-phase-b.md): the sentry runs in its own
  user namespace and does not hold the runner's SYS_ADMIN or NET_ADMIN.)*
- R: all sentries of all sandboxes run as **one uid 1000** of the runner. After an escape
  from one sandbox the agent is the same uid as the other sandboxes' sentries. If sandboxes
  must be isolated from that too, each needs a uid of its own. *(Confirmed as a real hole in
  [S3](s3-linux.md) 4.6.)*

## 8. Problems, workarounds, surprises

1. **gVisor's release format changed.** `…/release/latest/${ARCH}/runsc` returns 404. Now
   there is only `gvisor.tar.bz2` (or `.tar.zstd`) with `runsc`,
   `containerd-shim-runsc-v1` and a folder `gvisor-bin/` (`gvisor_sentry`,
   `runsc-netgofer`, `runsc-fd-parking`…); runsc looks for them beside itself. The
   Dockerfile puts the archive into `/usr/local/bin` and is pinned to `20261123.0`.
2. **`runsc do` with a network** needs `sysctl -w` and so works only under `--privileged`.
3. **A netns is single-use.** At start gVisor takes the IP of the netns's eth0 into its
   netstack and does not give it back after exit. The netns must be recreated before each
   run (`netns.sh down/up`).
4. **Without the netns in `config.json`** and with `--network=sandbox`, the sandbox would
   land in the runner's netns and share its interface; the spec must always name its own
   netns (or a new empty one).
5. **Rootless:** only uid 0 is mapped. The agent as uid 1000 sees files as `nobody` and
   cannot create them. Workaround: run runsc as the runner's uid 1000, and root in the
   sandbox. Nested user namespaces do not work in this mode.
6. **Zombies.** Without init the runner piles up `[gvisor_sentry] <defunct>`,
   `[runsc-fd-parkin]` after each sandbox. `--init` or tini is needed.
7. **Codex 0.172:** `codex sandbox [COMMAND]…`; the `linux` subcommand is gone.
8. **The machine's slow network** (≈0.8 MB/s on the clone). Cold `uv`/`npm` and W1-net are
   bound by it. `git clone --mirror` from GitHub also pulls `refs/pull/*`; `--bare` was used
   for the cache.
9. **Docker.raw grows.** Free space on the Mac fell from 81 to 62 GB during the spike
   (3 GB images, 3 GB rootfs copies per runner). After the cleanup 78 GB: Docker Desktop
   gives space back with a delay.
10. **A cleanup detail:** `docker ps --filter name=spike-` matches a substring and caught
    `buildx_buildkit_spike-builder0`. Because of that `docker buildx rm` did not remove the
    volume `buildx_buildkit_spike-builder0_state` (4.7 GB); it was removed by hand together
    with the image `moby/buildkit:buildx-stable-1`.

## 9. Rerun on the other VMM

Skipped: switching the VMM needs a switch in Docker Desktop's window and a VM restart.

## 10. Cleanup and the machine's state

Removed: the `spike-*` containers, the network `spike-net`, the volume `spike-cache`, the
images `spike-runner`, `spike-sandbox`, `debian:bookworm`, `moby/buildkit:buildx-stable-1`,
the builder `spike-builder` and its volume. `docker ps/images/volume ls/network ls/system df`
match the snapshot before the spike (`logs/00-snapshot-before.txt` and
`logs/99-snapshot-after.txt`), including the earlier build cache of 82 entries / 5.8 GB.
`lado-lado-1` is running again, `http://127.0.0.1:8765/` answers 200. Docker Desktop's
settings were not changed. Only the folder `~/gvisor-spike/` remains.

## Next steps (proposed)

- Replace `seccomp=unconfined` with a profile of our own: Docker's default profile plus the
  calls runsc needs (`pivot_root`, `mount`, `unshare`, `clone` with namespaces, `ptrace`
  for systrap). This is checkable and narrows the runner's rights a lot.
- The same spike on Linux: `--platform=kvm` with `/dev/kvm`, AppArmor, exec compared with
  systrap.
- A prototype: a runner with init, a netns and iptables per session, the workspace on a
  volume, the proxy in `lado`.

## Files (in the spike folder, not committed)

- `BRIEF-local.md`: the brief's amendments for this machine.
- `docker/Dockerfile`: the images `spike-sandbox` and `spike-runner`.
- `scripts/`: `p1-*` (Phase 1), `runner.sh`, `mkspec.py`, `netns.sh` (bundles and netns),
  `p2-compat.sh`, `bench*.sh`, `summarize.py`, `p4-*`, `proxy.py`, `p5-*`.
- `logs/`: everything by section number, the raw CSV and the snapshots before and after.
