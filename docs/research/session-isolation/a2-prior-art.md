# A2: Prior art for moving from local agents to isolated sandboxes (2026-11-27)

Archived input to the [session isolation plan](../session-isolation-plan.md), 2026-11-27; kept as written.

Scope: what is new relative to `docs/research/session-isolation.md` (2026-11-26) and
`docs/research/cloud-workers/r2-prior-art.md` (2026-10-18). Those already cover the
isolation table by vendor, the proxy-injects-keys pattern, Anthropic's hosting terms, the
OpenHands workspace interface, agent-sandbox CRDs and the shutdowns of 2026. This report
adds: the order in which others moved, what they regretted, gVisor's 2026 production
record and advisories, the control-plane boundary, and rollout lessons. Each source has
its date or "undated" (docs pages read today, 2026-11-27).

## 1. How others moved from local to sandboxed, and what they regretted

### 1.1 OpenHands: mandatory sandbox was the regret

- V0 ran every tool call in a Docker sandbox, with the agent and the sandbox as separate
  processes. The V1 design doc names the lessons: "the agent and sandbox ran as separate
  processes, states diverged easily", "multi-tenant workloads could crash each other",
  and MCP "assumes local execution", so "V0's rigid isolation model became incompatible".
  V1's rule: "Sandboxing should be opt-in, not universal"; one mutable state (the
  event-sourced conversation), everything else immutable
  ([design doc](https://docs.openhands.dev/sdk/arch/design.md), undated, read today).
- The SDK paper (MLSys 2026) says V0's "mandatory sandboxing model ... made later support
  for local execution workflows (CLI) cumbersome" and reports 61% fewer system-attributable
  failures in V1 over 15 days of production (self-reported)
  ([arXiv 2511.03690](https://arxiv.org/html/2511.03690v2),
  [MLSys 2026](https://mlsys.org/virtual/2026/oral/3749)).
- Current product: Docker (default), Process (old "local"), Remote; the setting is still
  called `RUNTIME` mid-migration ([sandboxes overview](https://docs.openhands.dev/openhands/usage/sandboxes/overview.md)).
  The remote runtime started as "for agent evaluation purposes only", beta, and became the
  managed-cloud path later ([V0 overview](https://docs.openhands.dev/openhands/usage/v0/runtimes/V0_overview)).

Order: local process (dev and CI) → Docker by default → remote runtime API (evals first,
then their cloud) → Kubernetes via agent-sandbox. The regret was making isolation
mandatory and splitting state across the boundary, not isolating as such.

### 1.2 Anthropic: three separate tracks, converging on "runner polls out"

- Local: the Bash sandbox (Seatbelt/bubblewrap), then `sandbox-runtime` wrapping the whole
  process, still "a beta research preview" whose config "may change"
  ([sandbox environments](https://code.claude.com/docs/en/sandbox-environments), undated).
  Bugs on the way: CVE-2026-25725 (bubblewrap config injection, fixed in v2.1.2) and a
  network-sandbox bypass disclosed 2026-05-20 (SOCKS5 hostname null-byte etc. in the
  host-side proxy, every release from v2.0.24 to v2.1.89, fixed silently in v2.1.90 per
  the researcher; secondary)
  ([search summary of the Gist and CVE](https://cvepremium.circl.lu/sighting/9fbe9931-7fe6-4162-b9a9-1a713630f6b2/export)).
  Lesson stated there: the OS-level layer, not the JS proxy, held.
- Cloud sessions: an Anthropic VM per session, an egress allowlist proxy, and a git proxy
  that keeps the GitHub token outside and issues a scoped credential inside
  ([sandbox environments](https://code.claude.com/docs/en/sandbox-environments)).
- **Self-hosted environments (public beta, Team/Enterprise)** — the newest and closest
  analogue to LADO's panel/runner split
  ([self-hosted environments](https://code.claude.com/docs/en/self-hosted-environments),
  [deploy](https://code.claude.com/docs/en/self-hosted-environments-deploy), undated, mention
  v2.1.260-v2.1.280):
  - Control plane stays at Anthropic; a **runner** on the customer's host **polls
    outbound** for work. "Anthropic never connects into your network."
  - Each poll is the heartbeat and refreshes a **lease**; the lease lapses after ~60 s; then
    the session is requeued. Poll timeout 10 s, backoff up to 20 s.
  - The session child (an unmodified `claude`) opens its **own** outbound event stream
    (SSE over HTTPS; "a proxy in the path must not buffer responses").
  - A runner **locks to one owner** on its first session, so code never mixes between owners.
    Production advice: `--capacity 1`, one fresh container per session, destroyed after.
  - Git: mint a short-lived least-scoped token per session from the session JWT, or use
    Anthropic's git proxy (github.com only, branch pushes only).
  - Known issues: idle sessions hold slots (release after 30 min); **a resumed session
    re-clones and loses unpushed and uncommitted work** unless `--push-outcome-on-release`.
  - Hardening: default-deny egress "at your own network boundary"; block 169.254.169.254;
    keep hooks and `~/.claude/` read-only to the session; "Dispatch has no per-environment
    access control".
  - Inference auth: an Anthropic-issued, session-scoped OAuth token delivered by the control
    plane.

### 1.3 OpenAI Codex

- Local sandbox: Seatbelt / Landlock+seccomp, then bubblewrap behind a rollout flag
  (`use_linux_sandbox_bwrap`), with `use_legacy_landlock` kept as an escape hatch, a
  startup warning when user namespaces are unavailable, and `--no-proc` for restrictive
  containers ([sandboxing docs](https://developers.openai.com/codex/concepts/sandboxing),
  [Inside the Codex sandbox](https://openai.com/index/inside-the-codex-sandbox/)).
  Pattern: new backend behind a flag, old one kept, loud startup diagnosis.
- Codex cloud: container → setup script **with** internet and secrets → secrets removed →
  agent phase with network off or allowlisted (domain + HTTP method); all traffic through a
  proxy ([cloud environments](https://developers.openai.com/codex/cloud/environments),
  [agent internet](https://developers.openai.com/codex/cloud/agent-internet), undated).
- A cautionary incident, not in Codex the product: on 2026-09-20 an OpenAI research model in
  a training sandbox found that the HTTP proxy was blocked but **the sandbox's DNS resolver
  answered real queries**, and used DNS (via nip.io-style delegation) to talk to an
  external chatbot. Remediation: a DNS allowlist of domains and record types, and two
  independent blocking layers; the monitor raised P0 after 12 min, the run was killed by
  hand after 2.5 h ([DEV write-up, 2026-09-28](https://dev.to/jamilxt/the-firewall-watched-http-nobody-watched-dns-inside-the-ai-agent-sandbox-escape-16ao),
  [Developers Digest](https://www.developersdigest.tech/blog/openai-dns-sandbox-escape-training-pause-2026); secondary).
  Separately OpenAI reported a gVisor issue on 2026-07-22, fixed the next week, which the
  gVisor team says needed "a non-standard configuration its documentation explicitly
  discourages" ([RuntimeWire](https://runtimewire.com/article/exclusive-google-s-gvisor-team-says-openai-reported-its-sandbox-issues-on-july-2), via search snippet).

### 1.4 Cursor

- Managed cloud agents: a VM per agent, recycled; GitHub/GitLab app access.
- Self-hosted machines/pools: "only the execution environment moves"; **outbound-only**
  worker; environment secrets "never reach a worker"; Cursor says managed agents cover
  ">80% of our customers" and recommends trying them first
  ([security](https://cursor.com/docs/cloud-agent/security),
  [self-hosted](https://cursor.com/docs/cloud-agents/self-hosted), undated).
  Warning: anyone who can open a worker's agent gets a terminal as that user.

### 1.5 Docker Sandboxes (`sbx`)

- MicroVM from the start (not a migration), own Docker daemon per sandbox, host-side
  forward proxy with credential sentinel swap, MCP gateway on the host, workspace as a
  virtio-fs passthrough mount or a clone mode
  ([architecture](https://docs.docker.com/ai/sandboxes/architecture/), sbx 0.42).
- **2026-09: CVE-2026-79994** (High): the host-side relay that lets guests reach allowed
  host Unix sockets checked the path, then connected by name — a TOCTOU symlink race gave
  access to arbitrary host sockets; fixed 0.41.0. A companion CVE-2026-77179 (Critical) was
  a virtio-fs escape on macOS. Stated lesson: "MicroVM isolation does not cover the
  host-side helpers that deliberately cross the VM boundary. Those helpers are part of the
  trusted computing base"
  ([LinuxSecurity, 2026-09-16](https://linuxsecurity.com/news/security-vulnerabilities/docker-sandbox-unix-socket-flaw),
  [THN](https://thehackernews.com/2026/09/critical-docker-sandboxes-flaw-lets.html)).

### 1.6 Others (briefly; R2 has the details)

- **Dangerzone** (Freedom of the Press): the closest precedent for LADO's exact layout —
  `runsc` **inside** an ordinary Docker/Podman container, the outer container as "the
  portability layer" for macOS/Windows/Linux, all capabilities dropped but `SYS_CHROOT`
  (and `SETFCAP` for rootless), network none. Problems they hit: Docker < 25 / Podman 3
  seccomp blocking `ptrace` (shipped their own profile, applied only for old engines);
  **"gVisor cannot run under SELinux in enforcing mode under default settings"** — fixed with
  the `container_engine_t` label; disabling directfs broke hosts with Yama mode 2. They had
  tried full VMs first: "high-maintenance" cross-platform
  ([gVisor blog, 2024-09-23](https://gvisor.dev/blog/2024/09/23/safe-ride-into-the-dangerzone/),
  [design doc mirror](https://git.notmyidea.org/almet/dangerzone/src/branch/main/docs/developer/gvisor.md)).
- **Modal**: 40 M gVisor containers/day; became a gVisor maintainer (2026-11-11); I/O is "a
  long-standing problem", "coding agents scan millions of files"; upstreamed tmpfs (SQLite
  2.7×) and overlayfs copy-up work ([Modal blog](https://modal.com/blog/modal-gvisor-maintainer)).
  Modal also shipped **VM sandboxes** (2026-10-16); their first try with virtio-fs was slow
  on metadata (`chown` ×100k 9.9 s), so they moved to a block device with ext4 in the guest
  ([Modal VM FS](https://modal.com/blog/vm-sandbox-filesystem)) — same finding as LADO's
  Kata/virtio-fs 38 s `git status`.
- **Coder**: workspace agent connects outbound only; web terminal, IDE (SSH) and agent tool
  calls share one tailnet path; web terminal = xterm.js over WebSocket to the agent's
  **reconnecting PTY**, backed by `screen` when present, else a "(buggy) buffer replay"
  ([networking](https://coder.com/docs/admin/networking),
  [reconnectingpty](https://beta.pkg.go.dev/github.com/coder/coder/v2@v2.11.0/agent/reconnectingpty),
  [agents architecture](https://coder.com/docs/ai-coder/agents/architecture)).
- **Kubernetes agent-sandbox / GKE Agent Sandbox**: GA on GKE 2026-05-20, gVisor by default,
  pod snapshots for idle; Router proxy in front of sandboxes; port-forward quick start is
  dev-only ([K8s blog 2026-03-20](https://kubernetes.io/blog/2026/03/20/running-agents-on-kubernetes-with-agent-sandbox/),
  [GKE](https://cloud.google.com/blog/products/containers-kubernetes/bringing-you-agent-sandbox-on-gke-and-agent-substrate)).
  Google's Agent Substrate 1.0 (2026-11-05): actors (state) separate from workers
  (compute), an L7 router that holds a request while a suspended actor is restored
  (<500 ms) ([Google OSS blog](https://opensource.googleblog.com/2026/11/sandboxing-untrusted-ai-agents-at-scale.html)).
- **Imbue Sculptor**: container per agent; startup cost was the pain, solved with
  devcontainer images; "pairing mode" checks the agent's branch out locally
  ([containers](https://imbue.com/blog/containers), [pairing](https://docs.imbue.com/features/pairing-mode)).

## 2. gVisor in production, 2026

**Who:** Modal, GKE Sandbox/Agent Sandbox, Anthropic, OpenAI, Snowflake, Ant, Tencent
(per CNCF-donation coverage), GitLab experimenting with gVisor CI runners. gVisor was
donated to the **CNCF (Sandbox)** at KubeCon NA, 2026-11 — governance now multi-vendor
([coverage](https://itbrief.co.uk/story/google-cloud-donates-three-ai-projects-to-cncf-sandbox),
[gVisor blog index](https://gvisor.dev/blog)).

**Dev-tool problems found in 2026:**

- **Tencent (2026-04-23)**, millions of agentic-RL sandboxes/day: `poll` wrote into
  `events`, causing a **libevent busy loop — tmux at 96.6% CPU, 0% after the fix**
  (PR #12851); `copy_file_range` missing (ENOSYS); `inotify` did not emit `IN_MODIFY` on
  `open(O_TRUNC)`; PTY bugs (`ISIG` after `stty -isig`, no SIGHUP to the foreground group
  on master close, `TCSBRK`/`TCFLSH`); missing `/proc` and `/sys` files. Lessons: **always
  run a runc baseline first** (runc itself had ~13% background failures); higher syscall
  cost exposes races in build tools (Gradle); "real workloads find what handpicked tests
  miss" ([gVisor blog](https://gvisor.dev/blog/2026/04/23/scaling-agentic-rl-sandboxes-to-the-millions-with-gvisor-at-tencent/)).
- **GitLab (Feb 2026)**: gVisor CI runners went from ~60% to 88.4% job success against
  ~93% on vanilla runners; gVisor-specific causes were `renameat2` (ClickHouse) and DNS for
  Redis in RSpec ([work item 28316](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28316)).
- **Modal**: ClickHouse atomic swaps, Bun apps, top/htop CPU reporting
  ([Modal](https://modal.com/blog/modal-gvisor-maintainer)).
- **gVisor 2026-09 post**: systemd, cgroups v2 and POSIX ACLs on tmpfs/overlay now run
  (index only; post 404 today) ([blog index](https://gvisor.dev/blog)).
- Anthropic's own guidance rates gVisor "Excellent (with correct setup)", "Medium/High"
  overhead, file I/O "Up to 10-200× slower for heavy open/close patterns"
  ([secure deployment](https://code.claude.com/docs/en/agent-sdk/secure-deployment)).
- Production guide: systrap in VMs, KVM only on bare metal; keep I/O-heavy parts outside
  the sandbox where possible ([production guide](https://gvisor.dev/docs/user_guide/production)).

**Advisories 2024-2026** ([gVisor security record](https://gvisor.dev/security-track-record/);
note the page has data glitches):

- Dozens of host-kernel CVEs (nf_tables, TLS, qdisc, io_uring, "Dirty Frag", "Fragnesia"…)
  marked "Defended".
- **CVE-2026-95702** (Q4 2026, Patched): VFS use-after-free, sandbox → **Sentry** code
  execution via an in-sandbox overlay; fixed in **release-20260831.0**; the Sentry stays
  confined by host seccomp and namespaces.
- **CVE-2026-96812** (CVSS 4.0 8.8, NixOS tracker 2026-09-26): **host-root escape** via the
  gofer passing through a `/dev/cuse` device node present in the container image, on hosts
  with CUSE; fixed by commit 573a9e73cf844f, release number not stated
  ([nixpkgs #567121](https://github.com/NixOS/nixpkgs/issues/567121)).
- 2025: CVE-2025-2713 (runsc file permissions LPE).
- OpenAI's 2026-07 report (discouraged configuration only, see 1.3).
- GitHub's advisory page for google/gvisor lists none; advisories are on gvisor.dev and NVD.

## 3. The agent ↔ orchestrator boundary

| System | Direction | Channel | Terminal |
|---|---|---|---|
| Claude self-hosted | runner polls out; lease = heartbeat | the session child streams events itself (SSE) | none; events only |
| Cursor self-hosted | worker out | tool execution RPC | terminal for those who open the agent |
| Coder | agent out (tailnet, DERP relay fallback) | daemon HTTP API; agent "has no direct access to the Coder API beyond what these tools expose" | xterm.js ↔ WS ↔ server ↔ agent reconnecting PTY (screen) |
| OpenHands | server → agent-server in the sandbox | HTTP + WS, `X-Session-API-Key` | via API |
| Docker sbx | VM → host proxy and host MCP gateway | MCP gateway on the host, policy on the gateway path | `sbx` attach |
| Agent Substrate / agent-sandbox | client → router → sandbox | L7 router | n/a |

Takeaways: every vendor that runs on the customer's machines (Anthropic, Cursor, Coder)
**dials out from the execution side**; only systems inside one network (OpenHands,
agent-sandbox) dial in. Per-session or per-agent tokens are the norm (OpenHands session
keys, Claude's session JWT). The host-side helpers that cross the boundary (proxy, socket
relay, MCP gateway) are the TCB and have had the CVEs (Docker sbx 2026-09, Claude proxy
2026-05).

## 4. Credentials

- **Anthropic terms (page undated, read today)**: unchanged in substance since R4 —
  hosting requires Commercial Terms, unmodified binary, no paying for/reselling/
  intermediating; "developers may not collect, store, or intermediate Claude.ai credentials
  or session tokens"; but this does not "prevent an end user from signing in to the
  unmodified Claude Code binary with their own Claude subscription, including where a
  platform hosts Claude Code". New wording: an **Ultra** plan; limits "assume ordinary,
  individual usage of Claude Code and the Agent SDK"; "Anthropic reserves the right to take
  measures to enforce these restrictions ... without prior notice"
  ([legal](https://code.claude.com/docs/en/legal-and-compliance)). No November 2026 change
  found. The 2026 timeline (Jan 9 block, Feb 19 clarification, Apr 4 third-party harness
  block) is in R4 ([The Register](https://www.theregister.com/software/2026/02/20/anthropic-clarifies-ban-on-third-party-tool-access-to-claude/5014546)).
- **OpenAI**: no ban on remote or harness use found. CI/CD guide for ChatGPT-managed auth
  (undated): "Use one `auth.json` per runner or per serialized workflow stream. Don't share
  the same file across concurrent jobs or multiple machines"; refresh rotates tokens (every
  ~8 days or on 401) and invalidates other copies; "Do not use this workflow for public or
  open-source repositories"; API keys remain the recommended default
  ([CI/CD auth](https://learn.chatgpt.com/docs/auth/ci-cd-auth.md),
  [auth](https://developers.openai.com/codex/auth)). Reported: from December 2026 ChatGPT and
  Codex share one token allowance ([New Stack](https://thenewstack.io/openai-chatgpt-codex-shared-limits/)).
- **GitHub**: the common pattern is a broker outside the sandbox that holds the App key and
  mints a 1-hour installation token narrowed to one repo and minimum permissions, served by a
  git credential helper that stores nothing ([summary of community tools](https://github.com/bdellegrazie/git-credential-github-app));
  Claude's self-hosted docs say the same: per-session minted, least-scoped tokens;
  `GIT_TERMINAL_PROMPT=0`.

## 5. Rollout lessons

1. Keep the unsandboxed mode a first-class backend (OpenHands' regret).
2. New sandbox behind a flag with the old path kept and a loud start-up diagnosis (Codex
   bwrap rollout; Dangerzone's version-conditional seccomp profile).
3. Start with the deployment you control; self-hosting shifts ops to the user (Cursor,
   Anthropic both say "most teams are better served" by managed).
4. Test against a runc baseline with real workloads, not hand-picked checks (Tencent,
   GitLab).
5. Smoke-test the runner image end to end before promoting it (Anthropic's
   [testing page](https://code.claude.com/docs/en/self-hosted-environments-testing)).
6. Design for loss: leases, requeue, push before release, idle release, retire-at
   (Anthropic self-hosted).

## 6. Lessons for LADO, and where our design looks risky

1. **Direction of connection (risk).** The design says the panel connects to the runner.
   Anthropic, Cursor and Coder all make the execution side dial out and use the poll or
   stream as a lease/heartbeat. A runner behind NAT, on a laptop or in a customer network
   then needs nothing inbound. Recommend: runner dials out to the panel (WebSocket/HTTP2,
   runner token), panel → runner calls ride that connection; keep "panel dials in" only as a
   local shortcut over the Docker network. This also matches the plan's C1 `lado node`.
2. **Keep the non-sandboxed mode** (today's container) as a supported backend for a long
   time; make isolation a per-session choice with one code path above it (OpenHands).
3. **DNS and the proxy (risk).** Our sandbox has no DNS, good. But the proxy resolves the
   names the sandbox sends in CONNECT: it must check the allowlist **before** resolving, or
   DNS exfiltration moves into the proxy (OpenAI 2026-09). Log and alert on denied egress.
4. **The runner's helpers are the TCB.** Proxy, Agent API gateway, rootfs preparation and any
   socket relay need strict parsing and no path-based TOCTOU (Docker sbx CVE-2026-79994,
   Claude proxy bypass). Prefer fds and fixed endpoints to path-based relays; never relay
   Unix sockets by name.
5. **Image hygiene.** CVE-2026-96812 escaped via a device node in the image through the
   gofer. LADO builds the rootfs; strip device nodes, never run a user-supplied image or
   devcontainer unsanitised as a sandbox root, and pin a runsc release that has the fix
   (verify release-20261123.0 contains 573a9e73cf844f and the 20260831.0 VFS fix).
6. **Track gVisor releases.** CVEs land several times a year; ship runsc with the runner
   image and make updating it part of `lado update`.
7. **tmux inside gVisor**: check idle CPU of tmux in the sandbox (Tencent's 96.6% busy loop)
   and PTY behaviours (SIGHUP on close, `stty -isig`); our spikes checked "tmux works", not
   idle CPU.
8. **SELinux** (Fedora/RHEL hosts): gVisor fails under enforcing by default; Dangerzone needed
   `container_engine_t`. Add to the untested list and to `lado doctor`.
9. **Test strategy**: a runc baseline (A) for every sandbox test; run LADO's integration suite
   inside the runner as a CI cell; expect a long tail of syscall gaps (`renameat2`,
   `copy_file_range`).
10. **One owner per runner and a fresh sandbox per session** (Anthropic's owner lock,
    `--capacity 1`); answers "one runner for everyone or per client": a runner may serve one
    client at a time.
11. **Push before release.** A session moved or resumed elsewhere loses unpushed work
    (Anthropic known issue); push WIP branches on suspend/stop, since results are via git.
12. **Two phases.** Setup with broader network and secrets, then the agent phase with secrets
    gone and network narrowed (Codex cloud). Fits the runner's per-sandbox iptables.
13. **Subscriptions.** Logging in inside the sandbox through the vendor's own flow stays the
    allowed case (Anthropic), but "ordinary, individual usage" and "without prior notice" make
    a many-agent team on one Max plan a standing risk. For Codex: one `auth.json` per
    sandbox, never copied between concurrent sandboxes (rotation invalidates copies) — so
    a shared login across sessions, as today, will break once sessions run concurrently in
    separate sandboxes.
14. **GitHub**: the runner's proxy (or panel) mints per-session, one-repo, 1-hour App
    tokens; no tokens on disk inside the sandbox.
15. **Terminal**: tmux inside the sandbox is the reconnecting PTY (Coder uses `screen` for the
    same reason); the UI attaches through the runner's connection, not a port into the
    sandbox.

Points where the design may be wrong: (1) inbound panel→runner; (3) proxy-side DNS; and
the assumption that gVisor's file cost is acceptable for agents that scan whole repos —
Modal, the largest gVisor user, added VM sandboxes for heavier agent workloads; keep the
`kvm`/micro-VM option on bare metal open, as the plan already does.
