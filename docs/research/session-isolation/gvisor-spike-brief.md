# gVisor spike: brief for an agent on a clean macOS machine

> The brief for round 1, run by an agent on the human's macOS machine; its report is
> [S1](s1-macos.md). The agent checks whether gVisor sandboxes (LADO's future `runner`)
> can run inside an ordinary Docker Desktop container: with which minimal privileges,
> whether our tools and the agent CLIs start, how much slower it is, whether the network
> can be closed, and whether the sandboxes are really apart. Saved as given to the agent;
> the Russian preface for the human is replaced by this note.

## 0. Context and goal

LADO runs teams of AI coding agents (Claude Code, Codex, OpenCode, Kilo) in tmux. Today it
ships as one Docker container where all sessions share one OS user. We are considering this
layout: a `lado` container (control panel, core, keys, proxy) plus a `runner` container.
Inside `runner`, every LADO session runs in its own **gVisor** sandbox (`runsc`).

The same code must work on macOS and Windows (Docker Desktop) and on Linux. That is why we
want gVisor *inside an ordinary container* and not installed as a Docker runtime on the host.

**Answer these questions with evidence:**

1. Does `runsc` start sandboxes inside a container under Docker Desktop on macOS? What is the
   **minimal** set of container privileges it needs?
2. Do our tools work inside such a sandbox: git, tmux, Python with uv, Node with npm, gcc/make,
   and the four agent CLIs?
3. How much slower are typical agent workloads than in a plain container: git, `npm ci`,
   `uv sync`, tests, many small files, fork/exec? Measure both on a host bind mount and on the
   container's own disk.
4. Can a sandbox's network be limited to one destination, our future proxy?
5. Are two sandboxes in one `runner` really isolated from each other and from `runner`?

**This is a spike: measure and report; do not build a product.** About 2–3 hours. When a
step fails, record the exact error, try at most two or three reasonable variants, then move
on. A clear "does not work, because…" is a valid result.

**Priorities, if time runs short.** Phases 1 and 5 matter most, then Phase 2, then Phase 4
step 3a (iptables: whether "all traffic through the proxy" can work at all), then Phase 3's
**W2, W6 and W7 on bind**. Cut in this order, and say in the report what was cut:
1. section 9's optional VMM rerun;
2. W5 (tests) in the *local* place: keep it on *bind* only, and use the subset;
3. W1's network clone repeats: clone django from the network **once** into a local cache,
   then time only `git clone --no-local` from that cache;
4. W3/W4 warm runs;
5. Phase 4 step 3c.

## 1. Rules

- **No real secrets.** Do not log in to any agent CLI and use no API keys. For the CLIs we
  only need to know that they start and draw their UI.
- `--privileged`, `seccomp=unconfined` and so on are allowed **only on the test containers of
  this spike**.
- If you change a Docker Desktop setting, record it and put it back at the end.
- Keep every script, Dockerfile and raw log in one folder, `~/gvisor-spike/`. They go into
  the report.
- At the end, remove the spike's containers, images and networks (section 10).

## 2. Environment (record all of it)

- Hardware and macOS: `sw_vers`, `uname -a`, `sysctl -n machdep.cpu.brand_string`, the chip
  (M1/M2/M3/M4), RAM, free disk.
- Docker Desktop:
  - If it is missing, install it (`brew install --cask docker`, then start it once; the human
    may have to accept the license in its window). Record how it was installed.
  - `docker version`, `docker info`. Keep the full output, especially the kernel version,
    cgroup version and driver, Security Options (seccomp, cgroupns) and the OS.
  - The VMM and file-sharing settings (Settings → General → Virtual Machine Options: Apple
    Virtualization framework or Docker VMM; file sharing: VirtioFS, gRPC FUSE or osxfs).
- KVM and nested virtualization inside the Docker VM:
  - `docker run --rm --privileged alpine sh -c 'ls -l /dev/kvm; grep -cE "vmx|svm" /proc/cpuinfo; uname -a'`
  - On arm64 there is no vmx/svm. Note whether `/dev/kvm` exists.
- Landlock: `docker run --rm alpine sh -c 'cat /sys/kernel/security/lsm 2>/dev/null; dmesg 2>/dev/null | grep -i landlock'`.
  This one is informational only.

## 3. The runner image

Build a test image `spike-runner`, Debian bookworm, native arch (arm64 on Apple Silicon). It
holds:

- gVisor `runsc` (and `containerd-shim-runsc-v1`, not needed), from the official release:
  ```
  ARCH=$(uname -m)   # aarch64 or x86_64
  URL=https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}
  curl -fsSLO ${URL}/runsc -fsSLO ${URL}/runsc.sha512
  sha512sum -c runsc.sha512 && chmod a+rx runsc && mv runsc /usr/local/bin/
  ```
  Record the exact version (`runsc --version`).
- Tools: `git tmux curl ca-certificates python3 build-essential iproute2 iptables procps
  psmisc bubblewrap time hyperfine` (if `hyperfine` is not in apt, use GNU `time` with
  repeats).
- Node 22 (NodeSource or the official tarball), `uv` (official install script).
- The agent CLIs, global npm installs: `@anthropic-ai/claude-code`, `@openai/codex`,
  `opencode-ai`, `@kilocode/cli`. If one does not install on arm64, record that.
- A non-root user `agent` (uid 1000) for the workloads.

Keep the Dockerfile in the report.

## 4. Phase 1: does runsc start, and with which privileges?

Use `runsc do`, the simplest form: it runs a command in a sandbox over the container's own
root filesystem. Base command:

```
runsc --rootless=false --network=sandbox do /bin/sh -c 'uname -a; id; cat /proc/version; echo OK'
```

Inside gVisor, `dmesg` and `/proc/version` show gVisor's own messages. That proves the
command really ran in the sandbox.

**What to expect, so you do not lose time on the search:**
- P5 and P6 will most likely fail. Docker's default seccomp profile blocks `unshare`, `mount`
  and `ptrace`, which runsc needs. Try each of them once, record the error, and move on.
- `--ignore-cgroups` will probably be needed in every profile: the container cannot create
  cgroups of its own.
- `--network=sandbox` makes runsc create a veth pair itself, which probably needs
  `NET_ADMIN`. If a profile fails only with the sandbox network, retry it with
  `--network=none` and `--network=host` before you add `NET_ADMIN`.

Run it in `spike-runner` started with each privilege profile below, **from most to least
permissive**. For each profile, also try these runsc flag variants until one passes:
`--ignore-cgroups`, `--rootless`, `--network=host`, `--network=none`, `--platform=systrap`
(the default), `--platform=kvm` (expected to fail on macOS; record the error). A variant
**replaces** the matching flag of the base command rather than being added beside it:
`--rootless` replaces `--rootless=false`, and `--network=host` replaces `--network=sandbox`.

First run `runsc help run`, `runsc help do` and `runsc flags`, and keep their output in the
logs. Flag names and defaults change between releases. Where this brief names a flag that
your version spells differently, use your version's flag and say so in the report.

| # | `docker run` options |
|---|---|
| P1 | `--privileged` |
| P2 | `--cap-add SYS_ADMIN --security-opt seccomp=unconfined --security-opt apparmor=unconfined` |
| P3 | P2 + `--cap-add NET_ADMIN --cap-add SYS_PTRACE` *(only if P2 fails)* |
| P4 | `--security-opt seccomp=unconfined` (no added caps) |
| P5 | `--cap-add SYS_ADMIN` (default seccomp) |
| P6 | defaults (no options), as LADO's container runs today |

Then a realistic form: an OCI bundle with its own rootfs (`runsc spec` + `runsc run`). Make
the rootfs with `docker export` of an image **without runsc**: build `spike-sandbox`, which
is `spike-runner` minus `/usr/local/bin/runsc` (a separate Dockerfile stage), and record
that `find rootfs -name 'runsc*'` finds nothing. Bind a host folder into it as `/work`. Run
it with the minimal profile that passed `runsc do`.

**Network for `runsc run`.** Unlike `runsc do`, `runsc run` does not set up a network
itself: the sandbox gets the network namespace named in `config.json`. By default that is
the runner's own namespace. For a sandbox network of its own, create a namespace with a
veth pair per sandbox (`ip netns add s1`, `ip link add veth-s1 type veth peer name eth0
netns s1`, addresses, a route, NAT in the runner), and point `config.json`'s
`linux.namespaces` `network` entry at `/var/run/netns/s1`. This needs `NET_ADMIN`. If R does
not have `NET_ADMIN`, run the network parts of Phases 2, 4 and 5 in **R + NET_ADMIN** and
say so in the report. Keep the script that sets up a namespace; Phases 4 and 5 reuse it.

Enable forwarding when you start the runner: `--sysctl net.ipv4.ip_forward=1` (compose:
`sysctls: [net.ipv4.ip_forward=1]`). `/proc/sys` is read-only inside a non-privileged
container, so `sysctl -w` there fails even with `NET_ADMIN`. Include this in profile R's
compose fragment if the network parts need it.

**Result:** a matrix "profile × runsc flags → works / error (first line)", and the minimal
profile that works for `runsc run` with a bind mount. That minimal profile is used in all
later phases; call it **R**.

## 5. Phase 2: compatibility inside the sandbox

Inside a gVisor sandbox (profile R, as user `agent`, with network) check each item. Record
✅/❌ and the first error line.

- `git --version`. Clone `https://github.com/ladohq/lado`; then `git status`, `git log -5`,
  `git worktree add ../wt -b spike` with a commit in the worktree.
- tmux:
  - `tmux new-session -d -s t 'bash'`;
  - `tmux send-keys -t t 'echo hello' Enter`;
  - `tmux capture-pane -p -t t` (must show hello);
  - a second session over a custom socket (`tmux -L lado ...`).
- Python and uv: `uv sync` in the cloned repo, `uv run lado --version`.
- Node: `node -e 'console.log(1)'`, `npm ci` in `web/`.
- Build: `gcc` hello world, `make --version`.
- Agent CLIs:
  - `claude --version`, `codex --version`, `opencode --version`, `kilo --version`;
  - then start each one interactively in a tmux window for ~10 s and `capture-pane`. It is
    fine if it asks for a login; what matters is that it draws its UI and does not crash.
    Put the captured screens in the logs.
- Codex's own sandbox inside gVisor:
  - `codex sandbox -- true` (if the syntax differs in this Codex version, run
    `codex sandbox --help` and use its Linux form);
  - `bwrap --unshare-all --ro-bind / / true`;
  - `unshare -U -r true`.

  Today all of these fail in LADO's plain container. Does gVisor make them work?
- Misc: `ps aux`, `df -h`, `cat /proc/meminfo | head`, `ulimit -a`, inotify
  (`python3 -c` with a loop that watches a file, or `inotifywait` if available).

## 6. Phase 3: speed

Compare **A = plain container** (`spike-runner`, no runsc, default profile) and **B = gVisor
sandbox** (profile R, `runsc run`). Same image, same CPU and memory limits (e.g. `--cpus 4
--memory 8g`).

Before you set the limits, check how much memory and how many CPUs Docker Desktop's VM has:
`docker info --format '{{.MemTotal}} {{.NCPU}}'`, and Settings → Resources. The limits must
fit inside them, with room left for the VM itself. With less than about 10 GB in the VM, use
`--memory 4g` (or half the VM's memory) for both A and B. Record the VM's resources and the
limits you used.

Run each workload in two places:

- **bind**: a folder from the macOS host bind-mounted into the container (this is how LADO's
  workspace works today);
- **local**: the container's own filesystem or a named volume.

Run each workload **3 times** (warm one run first where it makes sense) and report the
**median** wall time.

**The numbers that matter most are W2 and W6 on bind.** There, two layers stack up: Docker
Desktop's VirtioFS from macOS, and gVisor's gofer on top of it. The slowdown may be several
times.

gVisor has two file-access flags; check them in `runsc flags` first:
- `--file-access` is for the root filesystem; its default is `exclusive`.
- `--file-access-mounts` is for bind mounts; its default is `shared`.

Measure B on **bind** twice: with `--file-access-mounts=shared` (the default) and with
`--file-access-mounts=exclusive`. Report both. On **local**, the workloads run on the
sandbox's root filesystem, so there `--file-access` is the one that matters; keep its
default unless you have time to compare.

| # | Workload |
|---|---|
| W1 | `git clone https://github.com/django/django` (full history) — network+disk; then `git clone --no-local` of that clone (disk only) |
| W2 | in the django clone: `git status` ×20, `git log --stat -n 300 >/dev/null`, `git grep -n "def " >/dev/null` |
| W3 | LADO repo: `uv sync` with a cold cache (`UV_CACHE_DIR` fresh), then warm |
| W4 | LADO `web/`: `npm ci` with a cold npm cache, then warm |
| W5 | LADO unit tests: `uv run pytest -n 4 -q -x` (limit 15 min; if a subset is needed, take `tests/test_state.py tests/test_runs.py tests/test_kits.py`, and record what was run) |
| W6 | small files: create 20 000 files of 1 KB in 200 folders, then `find . -type f | wc -l`, then `rm -rf` |
| W7 | fork/exec: `for i in $(seq 2000); do /bin/true; done` |
| W8 | CPU: `python3 -c "sum(i*i for i in range(30_000_000))"` |

**Where B's writes go on local.** gVisor can put a writable overlay over the root
filesystem: `--overlay2=root:self` keeps the upper layer on disk, next to the rootfs, and
`--overlay2=root:memory` keeps it in RAM. Check your version's default in `runsc flags`.
With the upper layer in memory, "local" in B measures RAM, not disk, and the comparison with
A is not fair; under `--memory 4g` a django clone or `npm ci` may also run out of memory.
So:
- for the A/B comparison, use an upper layer on disk (`root:self`) or no overlay
  (`--overlay2=none`, writing into the bundle's rootfs, which is on the runner's disk);
- try `root:memory` only as an extra row, and watch the memory (`docker stats` of the
  runner);
- for every B number, record the `--overlay2` value and where the upper layer lies.

Record which flags were used for each B number.

**Result:** a table workload × place with A, B and B/A.

## 7. Phase 4: network

Inside a gVisor sandbox (profile R):

1. `--network=none`: `curl https://example.com` must fail. Record it.
2. Default (`--network=sandbox`): curl to `https://example.com` and `https://api.anthropic.com`
   works. Check DNS.
3. **Only one destination allowed.**
   - Create a docker network `spike-net`. Start a container `spike-proxy` on it: any small
     HTTP proxy, e.g. `tinyproxy`, or `python3 -m http.server` as a plain target. Start the
     runner on `spike-net`.
   - Restrict the sandbox's outbound traffic to the proxy only. Try in this order:
     a) iptables rules in the runner container's network namespace (needs `NET_ADMIN`; note
        whether it was already in R);
     b) any runsc network option that helps;
     c) `--network=none` plus a unix socket or a forwarded port to the proxy, if (a) and (b)
        fail.
   - Check from inside the sandbox: the proxy is reachable, `https://example.com` directly is
     not, and `https://example.com` *through* the proxy works.
   - Check that the agent inside the sandbox cannot undo the restriction: as user `agent`,
     and as root inside the sandbox, try `iptables -F`, `ip route`, and so on.

**Result:** which way of restricting works, with exact commands.

## 8. Phase 5: isolation

In one runner container (profile R) start two long-running sandboxes, **S1** and **S2**,
**only with `runsc run -d`**. Each gets **its own rootfs**: a separate copy of the exported
filesystem per bundle, e.g. `bundles/s1/rootfs` and `bundles/s2/rootfs`. Each also gets its
own bind-mounted folder (`/work/s1`, `/work/s2`) and its own marker file and process (`sleep
1000` named via `exec -a s1marker`).

**Do not use `runsc do` in this phase.** `runsc do` gives the sandbox the runner's own root
filesystem with an overlay on top. S1 would then "see" the runner's `/usr/local/bin/runsc`
and `/root` by construction, and the results would be false.

The bundles' rootfs come from `spike-sandbox` (no runsc, see Phase 1). After the export,
put a marker file in the runner itself, outside the bundles, e.g. `/root/runner-marker`
with a random string. **Judge access to the runner's filesystem only by this marker:** if S1
can find the file or its string, the sandbox can reach the runner's filesystem. Files that
exist in both the runner and the rootfs copy, such as `/usr/bin/git`, prove nothing.

Give S1 and S2 each its own network namespace (see "Network for `runsc run`" in Phase 1),
with its own addresses, so their netstacks can be tested against each other.

From inside S1 try to:

- see S2's processes (`ps aux`, `/proc/*/cmdline`) and runner's processes;
- read or write S2's folder (look for it under `/`, by host path, through `/proc/*/root`);
- send a signal to S2 or to runner's processes;
- reach runner's filesystem outside the mounted folders: look for `runner-marker` and its
  string (`find / -name 'runner-marker*'`, `grep -r` for the string where it is cheap);
  `/var/run/docker.sock` must not exist anywhere;
- reach S2 over the network (if both have netstack: S2's IP or listening port), and runner's
  services on localhost.

Also, as root inside S1:

- `mount`, `cat /proc/1/environ`;
- try to load a module;
- `dmesg`;
- note what the sandbox reports about itself.

**Result:** a table "attempt → blocked / succeeded". Anything that succeeded is important;
describe it exactly.

## 9. Report format

Write `~/gvisor-spike/REPORT.md`, in Russian or English. Pack the folder:
`tar czf ~/gvisor-spike.tar.gz -C ~ gvisor-spike`. Send nothing anywhere yourself. At the
end, print the two paths (`~/gvisor-spike/REPORT.md`, `~/gvisor-spike.tar.gz`) and the
Summary to the human in your final message; the human passes the files on to LADO. Keep
REPORT.md readable on its own, without the tarball. Structure:

1. **Summary** (5–10 lines): do it / don't do it, the minimal privileges, the main slowdowns,
   blockers, and what was cut for time.
2. **Environment** (section 2), with the Docker Desktop settings.
3. **Privilege matrix** (Phase 1) and profile R exactly as `docker run` options and as a
   compose fragment (`cap_add`, `security_opt`, `devices`, ...).
4. **Compatibility table** (Phase 2).
5. **Speed table** (Phase 3) with A, B, B/A, and the runsc flags used.
6. **Network** (Phase 4): what works, exact commands, whether the agent can undo it.
7. **Isolation** (Phase 5): the table.
8. **Problems and workarounds** found along the way; anything surprising.
9. **Optional:** if there is time, rerun Phase 1 (profile R only) and W1/W6 with the other
   VMM setting (Apple Virtualization ↔ Docker VMM), then restore the original setting.

## 10. Cleanup

```
docker ps -a --filter name=spike- -q | xargs -r docker rm -f
docker network rm spike-net 2>/dev/null
docker image rm spike-runner spike-sandbox 2>/dev/null
```

Restore any Docker Desktop setting you changed. Leave `~/gvisor-spike/` in place.

## Note for a later Linux run

The same brief should be run on a Linux host (bare metal or a cloud VM). Additionally:

- try `--device /dev/kvm` with `--platform=kvm`, and compare its speed with systrap;
- skip section 2's Docker Desktop parts.
