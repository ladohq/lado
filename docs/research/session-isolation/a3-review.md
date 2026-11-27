# A3: Critical review of the session-isolation research (gVisor spikes)

Archived input to the [session isolation plan](../session-isolation-plan.md), 2026-11-27; kept as written.

Read-only review, 2026-11-27. The bar: a cloud LADO where each session is isolated, reached
step by step through small releases that never break local use, one solution for
macOS/Windows/Linux, installed with docker compose and an install script.

Sources: `docs/research/session-isolation.md` (SI), its reports S1-S4, the three briefs and
the two diagrams; `docs/research/cloud-workers-plan.md` (Plan); `cloud-workers/r4-credentials.md`
(R4); `docker/compose.yaml`, `docker/Dockerfile`, `docker/install.sh`; `docs/design/agents.md`;
and a skim of `logins.py`, `agent_env.py`, `terminal.py`, `server/terminals.py`, `runtime.py`.

## Verdict in one paragraph

The spikes answer the question they were set well: can runsc run inside an ordinary
container on all three platforms, with what rights, and does it keep two sandboxes apart.
That part is solid. They do **not** show that the target design is right for LADO.
No agent ever ran a turn. The speed numbers are for a place repositories cannot live in.
The tested network layout (proxy in a separate container) is not the target (proxy and
Agent API inside the runner). The security write-up leaves out that the runner is real
root with `SYS_ADMIN` on a Linux host. And the biggest change for users gets one line in
the open questions: repositories move off the host into a Docker volume, the supervisor
leaves the human's checkout, logins become per sandbox. It is fine to call gVisor "the
base candidate". Treating it as decided before the seam (stage B) exists is premature.
The seam is most of the work, and it pays off for any sandbox technology.

---

## 1. Do the measurements support the conclusions?

### 1.1 The headline speed numbers measure the wrong place (strong)

SI 4.2 reports B/A "on the container's own disk": the sandbox's rootfs with
`--overlay2=root:self`. The overlay's upper layer belongs to the sandbox and is dropped
with it. A session's repository has to survive a runner restart, so in the target it
lives on a **volume bound into the sandbox through the gofer** (SI 7: "a volume with the
sessions' repositories"). That path was measured only on Linux and WSL2, and it is much
worse:

| | rootfs (headline) | volume / bind through the gofer |
|---|---|---|
| Linux x86 `git status` | 5.26x | 7.80x (S3 3.3, ext4 bind) |
| Linux arm64 `git status` | 7.29x | 13.32x |
| Linux x86 `uv sync` warm | 2.55x | 5.69x (arm64 9.59x) |
| WSL2 `git status` | 5.2x | **11.2x** (S4 3.3, named volume) |
| WSL2 create 20 000 files | 1.8x | 5.8x |
| macOS | 5.95x | **not measured**. SI 4.3 lists "container disk / volume" as one row, but S1 measured only rootfs and VirtioFS bind |

The B "local" file-creation result faster than A (0.54x, SI 4.2; S3 6: 0.39 s vs 0.72 s)
is a warning sign. gVisor's overlay writes do not reach the disk the way runc's do, so
"local" partly measures memory. The round-3 brief repeats the headline 5.2x for WSL2 as
the number to compare against, although the volume number (11.2x) is the relevant one.

### 1.2 Statistical weakness is larger than stated

- Medians of 3, with no spread reported, on 2-vCPU Azure VMs, under `--cpus 2` on a 2-vCPU
  machine. The limit gives the benchmark nothing beyond what dockerd and the runner's own
  processes need, and systrap's stub threads compete for the same two cores.
- The **ratio itself**, not only the seconds, moved about 2x between two VMs of one type:
  `git status` 5.26x vs 2.56x, tests 2.87x vs 2.39x (S3 3.3). So "5-7x" really means
  "somewhere in 2.5-7x".
- The Kata and kvm columns compare A and B from **another VM** (S3 6: "indicative"). Kata
  was rejected partly on these numbers. The text admits nested KVM is not representative,
  but the summary (SI 1.7) still reads as a comparison.
- macOS was a single fanless MacBook Air. The A/B order and any thermal throttling are not
  recorded.
- W5 "LADO's tests" is three test files (S1 5 footnote). The full suite (`-n auto`,
  integration with real tmux) was never run.

### 1.3 What was never measured but decides the design

1. **A real agent session.** Every brief says "no logins, no keys", so no model turn, no
   tool calls, no hook ever fired in a sandbox. S1 5 conclusion 3 ("expect 1.5-2x on real
   work") is an extrapolation from microbenchmarks. LADO has timing-sensitive parts that
   gVisor's syscall cost hits directly, and none was tried:
   - a Python process per hook event;
   - `hooks.MCP_READY_TIMEOUT` and the `lado.mcp_stdio` fast start (0.05 s vs 0.38 s,
     agents.md);
   - the fingerprint's 2 s `fingerprint.BUDGET` while `git status` is 5-11x slower: on a
     large repo the read-only check turns into `repo_check_failed`;
   - bracketed-paste typed delivery.
2. **Memory per sandbox and density.** One data point: "the runner took about 530 MB"
   (S1 5). There is nothing for a session of supervisor plus 2-3 Node CLIs, and nothing on
   page-cache duplication from separate rootfs copies. A laptop on Docker Desktop's
   default memory (the S1 VM had 8 GB) may fit far fewer sessions than today's single
   container.
3. **Disk per sandbox.** S1 8.9: "3 GB rootfs copies per runner", and Docker.raw dropped
   19 GB in one spike. LADO's real image (four CLIs, Chromium libraries, glab, mise) times
   N sessions, all inside one opaque Docker.raw.
4. **Sandbox start time** (rootfs, netns, runsc run, tmux ready), and teardown with
   `io_uring` denied (SI 9 lists it as open).
5. **Long-running stability**: sentry memory growth, leaked netns and veths, fd-parking
   processes, zombies over hours. Today's sessions run for days.
6. **No cgroups per sandbox** (`--ignore-cgroups`, SI 9). One session's runaway
   `npm install` or fork bomb starves every other session, and an OOM inside the runner's
   memory limit can kill the runner, which is all sessions at once. This is a design hole,
   not a footnote.

---

## 2. Correctness and security of the design

### 2.1 An escape from the runner: the write-up stops one hop too early (strong)

S2 6 shows the runner as **root in the init user namespace with 6 capabilities, including
SYS_ADMIN**. Docker gives no userns remap by default, so on a **Linux host** that is host
uid 0 holding SYS_ADMIN. SI 5's "what an escapee gets" stops at "Docker's deny list again,
six capabilities instead of sixteen". It does not say what that means for the host:

- `mount`, `unshare`, `setns` and `clone` with namespaces stay open (needed by runsc).
  With `apparmor=unconfined` (the plan's default on Linux, Plan 1), that is the classic
  SYS_ADMIN container-escape surface: on a cgroup v1 host the `release_agent` route, and
  in general every kernel bug reachable through mount and userns code.
- The runner also holds every session's keys in its proxy's memory, the Agent API gateway,
  and the terminals' ptys. So a compromised runner means every session and every key. The
  two-layer design (sentry, then runner) is sound, but the second layer is thinner than
  "six capabilities" suggests.
- **Docker Desktop** puts a VM boundary in between, but that VM shares `/Users` (macOS) or
  the Windows drives with the host by default, and today's compose bind-mounts the
  workspace. So "an escape lands in the VM" still reaches the human's files.

What follows:
- On Linux hosts with AppArmor, `lado-runner-lite` should be **required, not optional
  hardening** (SI 5).
- Its `mount,` rule allows any mount (S3 4.3). Narrowing it is untested.
- Loading it needs host root (`apparmor_parser`). That contradicts "nothing installed on
  the host", which was the very argument used against Kata (S3 6).
- SELinux hosts (Fedora, RHEL) are untested. A `container_t` process mounting may simply
  fail, so "one solution for Linux" is unproven.
- Rootless Docker and Docker with userns-remap, which would turn runner root into an
  unprivileged host uid, are untested (SI 9).

### 2.2 Network: the tested layout is not the target layout (strong)

- In the spikes the proxy was a **separate container** (`spike-proxy` on `spike-net`,
  S1 6.3), and `INPUT -i veth-+ -j REJECT` closed the runner itself. In the target
  (SI 7, the topologies diagram) the key proxy **and** the Agent API gateway run **inside
  the runner**. So the sandbox must reach the runner's own process that holds every
  session's keys, and INPUT needs holes. That layout was not tested.
- **IPv6 was not tested at all.** The rules are `iptables` only, with no `ip6tables`.
  gVisor's netstack speaks IPv6, and a veth gets a link-local `fe80::` address. Any runner
  service bound to `::` may be reachable over link-local from the sandbox.
- **The proxy is the exfiltration channel.** The spike proxy was a plain CONNECT proxy
  with no allowlist. With CONNECT and TLS, the proxy sees only host names:
  - It cannot inject keys or check branches. That needs `ANTHROPIC_BASE_URL=http://proxy`
    style routing per CLI, or TLS interception with its own CA (R4 3.2). Neither was tried.
  - Any allowlist that includes `github.com`, `registry.npmjs.org` or `pypi.org` lets data
    out (a push with an attacker's token, `npm publish`), and so does the model API with
    another key (R4 3.4 quotes Anthropic saying exactly that).
  - "Branch checks" on push are not possible on a CONNECT tunnel.
  - The allowlist's content and its UX (a repo whose tests need `example.org`) are not
    designed.
- Per-sandbox identity at the proxy: the source IP of the veth is unforgeable from inside
  (S1 6, `ip addr add` refused), which is good. It still has to be written down as *the*
  mechanism, and recreating the netns per run must not reuse a dead sandbox's address
  while its connections drain.

### 2.3 Subscription logins: isolation means less for most local users

SI 8.5 and Plan 1: "only API keys can stay out of the sandbox". Today Settings → Agent CLIs
keeps one Claude Code token and one Codex login for all agents (compose.yaml header:
"Codex's is shared by every Codex agent"; `logins.py`: one login window per provider). With
sandboxes:

- A subscription token must sit **in every sandbox**. A compromised session gets it, so
  "keys never in the sandbox" is false for the users who most likely make up the majority
  locally.
- Refreshing credentials cannot be copied into N sandboxes. R4 1.1: `/login` refresh
  races. R4 1.2: OpenAI says not to share `auth.json` across concurrent jobs. That leaves
  `claude setup-token` (static), or **one Codex device-auth per session**: a clear
  usability regression. Nobody has designed how the panel would keep these per sandbox.
- SI 8.5 stretches R4's legal reading, which is about a **hosted** service, to a user's
  own proxy on their own machine. LADO already stores the user's token today. The
  technical question (does Claude Code work with a placeholder OAuth token and an
  injecting `ANTHROPIC_BASE_URL`?) is untested. Both should be settled separately, not
  folded into one "impossible".

### 2.4 Git: credentials and a hazard the research misses

- Push credentials: the plan has the runner's proxy inject git tokens and check branches,
  which does not work over CONNECT (2.2). The local alternative is cheaper: **the sandbox
  has no push credentials at all, and the trusted side fetches the branch from the volume
  and pushes.**
- **Hazard:** whoever runs git on a sandbox-written repository runs code the agent
  controls. `.git/config` settings such as `core.fsmonitor`, `core.hooksPath`,
  `diff.external` and filters execute programs. Today the core runs git in worktrees all
  the time: the fingerprint, `finish_worker`'s `merge-base --is-ancestor`, merges, work
  state (Plan 4.1 C6). With isolation, every such call must run either inside the sandbox
  or with the repository's config neutralised. Neither the research nor the plan mentions
  this. Today's image even sets `safe.directory '*'` system-wide (Dockerfile), which is
  fine today and wrong for a panel that reads sandbox repos.

### 2.5 Panel to runner: direction and authentication are undesigned

- SI 8.3 reverses Plan C1 (an outbound node). Outbound-from-worker is the industry norm
  (CI runners, kubelet-style agents) because it needs no inbound port and works behind NAT.
  The hybrid topology's laptop runner is behind NAT by definition.
- Trust ("the panel decides, the panel holds keys") is a property of the protocol, not of
  who dials. Recommend: the runner dials out with an enrollment token, mutual
  authentication on the channel, and the same channel locally over the Docker network
  ("a local runner has no special path", SI 7).
- Locally, the runner's control API (start a sandbox, receive keys) must be authenticated
  even on the compose network. The spikes had no control API at all.

---

## 3. Usability and operability gaps

1. **Where the human's files are (the largest gap).** Today compose bind-mounts the
   workspace at the host's own path "so a worker's worktree made in the container is one
   on the host too" (compose.yaml), and the supervisor works in the human's checkout.
   Under SI 8.2 repositories live on a Docker volume, and results arrive "as a branch
   through git". Concretely:
   - no IDE on the worktree;
   - no running the app from the host;
   - no `git diff` in the human's own tools;
   - the "remote" to fetch from does not exist (the volume is not addressable from the
     host);
   - for the non-technical users LADO also serves, "git fetch" is not an answer.

   This is a product change to the core workflow, listed only as an open question (SI 9).
   It needs its own design: a git remote served by the panel, a sync, or keeping the
   bind mount, which on macOS users already accept at 21x for A (S1 5) and which may be
   tolerable as an opt-in.
2. **Data loss.** Unpushed session work lives only in Docker.raw. Docker Desktop's
   "Clean / Purge data", `docker system prune --volumes`, or a reset wipes it. Host backups
   (Time Machine) see one opaque file, if they see it at all. Today the work sits in the
   user's workspace.
3. **Login flows from a proxy-only sandbox.**
   - Codex's browser login uses a localhost callback that the host's browser cannot reach;
     device-auth must be enabled in ChatGPT settings (R4 1.2).
   - OpenCode and Kilo OAuth have the same problem.
   - Claude's paste-code flow works.
   - Every vendor's auth and token-refresh endpoints must be on the allowlist (R4 3.4).
   - Today's login windows (`logins.py`) are global tmux sessions. Per-sandbox logins mean
     new UI.
4. **The UI terminal and `lado attach`.** These become host → panel → runner →
   `runsc exec` → `tmux attach` inside the sandbox. S1 tested tmux send-keys and capture
   *inside* the sandbox and the CLIs' screens for 12 s. An interactive pty from outside
   through `runsc exec` (resize, SIGWINCH, latency, `terminal.py`'s viewer sessions and
   `ignore-size`) was not tested.
5. **Native installs.** gVisor is Linux-only. The PyPI install on macOS (`uv tool install
   lado`, keychain through `gui_session`) cannot be isolated this way. "One solution"
   therefore means native stays unisolated permanently, or is deprecated. The research
   should say which.
6. **Restarts and updates.**
   - Every sandbox is a process of one runner container. A runner image update (runsc,
     CLIs), `docker compose restart`, or a Docker Desktop restart or reboot kills all
     sessions. Overlay contents are lost: mise toolchains, `npm -g` and anything installed
     in the sandbox, which today persist on the home volume (Dockerfile).
   - Today LADO resumes sessions after a container restart. Whether resume works across a
     runner restart is untested; the round-3 brief has a restart check, not yet run.
   - The seccomp profile "must be rebuilt on top of each engine version's default"
     (SI 9). Docker Desktop updates the engine by itself, and a newer runc using the new
     mount API (`fsopen`/`fsmount`, which S2 8 saw runc call at container start) could
     break the narrow profile after an automatic update. A loud automatic fallback to
     `runner.json` and CI against new engines are needed.
7. **Debugging.** gVisor errors were opaque (`gofer: fork/exec /proc/self/exe: operation
   not permitted`, S1 3). `dmesg` is fake. Debug logs are runsc's `--debug-log`.
   `lado bug-report` and `doctor` would need to collect them. Not addressed.

---

## 4. Alternatives dismissed too early

1. **Per-session plain containers (runc), with the same netns and proxy-only egress, as
   the first step.** This is the A baseline in every benchmark, but it was never assessed
   as a candidate.
   - Against the realistic threat (a prompt-injected agent reading another session's
     files or secrets, or exfiltrating over the network) it gives the same isolation table
     as gVisor at 1x speed. What it lacks is protection from kernel bugs.
   - It need not hand anyone the Docker socket: the runner can run `runc`/`crun` the way
     it runs `runsc`, with a similar profile.
   - Making the runtime a per-runner setting (`runc | runsc | kata`) behind one runner
     protocol fits "small releases": ship isolation at no speed cost, and make gVisor the
     default once real sessions show the cost is acceptable.
2. **Docker Sandboxes** (Docker Desktop's micro-VM sandboxes for agents, in SI 2's own
   table). This is hardware isolation on macOS and Windows with no nested KVM inside a
   container, which is exactly what the research found impossible by other routes. Not
   tried. Its limits (Docker Desktop only, licensing, API) need checking, and it may
   decide the Mac story.
3. **Landlock / bubblewrap in today's container** (stage 1, SI 2). ABI 8 on Linux, ABI 7
   on WSL2, unclear on Docker Desktop. It is cheap and protects files now, before the
   seam. More important: with a seccomp profile that allows user namespaces, the CLIs'
   **own** sandboxes (Codex's bwrap and Claude Code's sandbox-runtime with its proxy)
   might work in today's container. That fits "Native over injected", needs no new
   architecture, and was not tried (LAD-151 was only shown to work *inside gVisor*).
4. **Sysbox.** Rightly not the base: it needs a host install, is Linux only, and is what
   ECI is built on. Plan C2 records "not part of the research". Fine.
5. **Apple `container` / krunkit, Docker VMM.** macOS-only and a host install, which
   conflicts with "one solution". It is fair to defer them, but the Docker VMM rerun was
   skipped (S1 9) and it costs one toggle.
6. **Kata in the cloud only.** Reasonable. Cloud VMs are nearly always nested, though, so
   the cloud will mostly run gVisor systrap at the 2-vCPU-VM numbers (exec about 3 ms).
   Bare metal is a cost choice, not a default.

---

## 5. Solid, plausible, wrong

### Solid
- runsc runs inside an ordinary container on Docker Desktop (macOS), Linux Engine x86 and
  arm64, and WSL2 Engine. P5 and P6 fail for the stated reasons. Six capabilities are the
  minimum, and the seccomp delta is `pivot_root` and `chroot` (S1-S4).
- Profile R must go: the cross-sentry `ptrace` was shown with Yama 1 (S3 4.6).
- The sentry sits in its own userns without the runner's capabilities (S2 6). The round-1
  worry was rightly corrected.
- IPv4 netns plus iptables hold against root inside the sandbox. Processes, files and
  `docker.sock` are closed.
- Never `C:\` (drvfs). The CRLF trap is real. CPU costs nothing. Syscall-heavy work is
  several times slower. `kvm` does not help on nested virtualisation.
- Codex's bwrap works inside gVisor.
- Local isolation needs the seam first (SI 8.4).

### Plausible but unproven, with the cheapest settling experiment
| Claim | Cheapest experiment |
|---|---|
| "Real work 1.5-2x" (S1 5) | One scripted LADO session (Claude supervisor plus Codex worker) on `tests/fake_endpoint.py` or one real key, repo **on a volume**, A vs B, wall clock per turn. Then LADO's own `make test-integration` (fake agent, real tmux, hooks, MCP) and the full `make test` inside one sandbox. About half a day. |
| Repos on a volume are fast enough | W2, W5 and W6py with the repo on a volume through the gofer on macOS Docker Desktop. One hour. |
| Laptop density is fine | 1, 3 and 6 idle sessions (3 CLIs each): `docker stats`, VM `meminfo`, start time, disk per sandbox for a rootfs copy vs a **shared read-only lower** (re-run the isolation table for the shared lower). Two hours. |
| Proxy-in-runner is safe | Move the proxy and a dummy gateway into the runner, re-run the isolation table, plus an IPv6 link-local probe and `ip6tables -L`. One hour. |
| Key injection and git checks through the proxy | Claude Code with `ANTHROPIC_BASE_URL=http://proxy` and a placeholder key. Codex `model_providers`. `git push` through a smart-HTTP relay with `url.insteadOf`. Half a day. |
| Logins work from a sandbox | Codex device-auth, Claude paste-code, OpenCode OAuth through the proxy only. One shared Claude `/login` credential in 2 sandboxes over a refresh. Two hours. |
| Narrow profile survives engine updates | The narrow profile on Docker Desktop 4.100 / Engine 29 and the newest Engine; Fedora with SELinux; rootless Docker. Run in CI cells. |
| Runner restart and resume | `docker compose restart runner` and a Docker Desktop restart: what survives on the volume, and does LADO's resume work (round 3, 3.5). |
| Stability | An 8-hour soak of 3 sandboxes looping git and pytest: sentry RSS, fds, netns leaks. |
| The numbers themselves | One ≥8-vCPU non-burstable machine, 10 interleaved A/B reps, report the IQR. |
| runc-per-session as step 1 | Same runner, `runc` instead of `runsc`, same netns and proxy: the isolation table and W2/W7. One hour. |

### Wrong or overstated
1. **SI 1.4 / 4.2 speed headline.** It is for ephemeral rootfs. Volume-backed numbers are
   1.5-2x worse (WSL2 11.2x), and macOS on a volume is unmeasured (1.1).
2. **SI 1.5 / 6: "the runner's services … out of reach"; "nothing inside can undo it".**
   True for IPv4, in a layout with the proxy outside the runner. Untested for IPv6 and for
   the target layout, where the runner's services must be reachable (2.2).
3. **SI 5: AppArmor as "optional hardening"; "nothing installed on the host".** With root
   and SYS_ADMIN in the init userns on a Linux host, `unconfined` is the weak point. The
   profile needs a host-side install, the same objection raised against Kata (2.1).
4. **SI 7 topology table: local "How the user gets the code: git".** This is presented as
   a detail. It breaks today's main workflow and its compose contract (3.1). For a plan
   whose rule is "each step leaves the local mode unchanged" (Plan 2), this conflict has
   to be resolved before gVisor is adopted.
5. **SI 8.5**, as worded, turns a hosted-service legal constraint into a technical law for
   self-hosted use (2.3).

---

## 6. A sequence that keeps local use intact

1. **Seam (stage B), behaviour unchanged.** MCP and hooks over HTTP with per-agent tokens;
   the panel the only writer of `lado.db`; git operations on worktrees moved behind an
   interface that can run *inside* a sandbox (2.4). Local stdio stays the default.
2. **Egress proxy, opt-in, in today's container.** `HTTPS_PROXY` for agents, a logged
   allowlist, base-URL key injection for API-key users. Learn the allowlist from real use
   before enforcing it.
3. **An isolated session, opt-in.** The runner with a pluggable runtime (runc first, runsc
   as an option). Repos stay on the workspace bind by default, with a volume as a
   performance option. Each session's results reach the host checkout through a git
   remote the panel serves. Per-sandbox cgroups.
4. **Default on** only after the density, real-session and restart experiments above, and
   after Docker Desktop on Windows (round 3).

Each step ships alone and can be rolled back. None moves the human's files before there is
a designed way to get them back.
