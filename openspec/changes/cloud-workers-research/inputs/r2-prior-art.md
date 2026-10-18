# R2: Prior art for running coding agents remotely (state as of 2026-10-18)

Research for LADO's optional, cloud-agnostic remote execution (any agent CLI, self-hosted
Kubernetes too, perhaps a paid hosted offering later). Web research only; no repository
changes.

How to read this report:

- **Part 1** is the synthesis: the cross-cutting patterns (a)–(e) the brief asked for, plus
  credentials and terms, the 2026 market shifts, and what they mean for LADO.
- **Parts 2–4** are the per-product evidence, grouped as vendor-hosted agents,
  sandbox/runtime providers, and orchestrators/multi-agent tools.

Every factual claim carries a source URL. In Part 1, the inline links point at the
primary source, and the detailed citations are in Parts 2–4. "(secondary)" marks
third-party sources and "unverified" marks conflicting ones. Where two parts disagree, the
note says which source is more recent.

---

# Part 1. Synthesis

## 1.0 The 2026 landscape in five sentences

1. Every vendor with a hosted coding agent (Anthropic, OpenAI, Cursor, GitHub, Google,
   Cognition, Amp, Factory, Warp) runs **one VM or container per task or session**. Code
   is cloned in from git and comes back out as a branch or PR. Warm starts come from a
   filesystem snapshot taken after a setup script.
2. For self-hosting, the same vendors have converged on a **hosted control plane plus a
   customer-run worker that claims sessions from a queue over outbound HTTPS only**:
   Claude Code self-hosted environments, Managed Agents self-hosted sandboxes, Cursor
   self-hosted workers, Devin Outposts, Warp `oz-agent-worker`, and Factory Remote Control.
3. The **sandbox layer is a commodity with roughly the same five verbs everywhere**:
   create, exec/PTY, files, expose port, and suspend/delete. The providers are E2B,
   Daytona, Modal, Runloop, Morph, Vercel, Cloudflare, Fly, Docker `sbx`, and
   `kubernetes-sigs/agent-sandbox`. On Kubernetes, **agent-sandbox (v1.0.x, Apache-2.0)
   is becoming the standard**, and OpenHands already builds on it.
4. Open-source orchestrators split into two camps:
   - **"Agent-server inside the sandbox"**: OpenHands agent-server, `opencode serve`,
     Codex app-server, and ACP.
   - **"Unchanged CLI in a terminal"**: Claude Squad, Uzi, Superset, and LADO today, with
     Cursor and Amp using a shared tmux even in the cloud.

   Screen-scraping wrappers lost: Coder's AgentAPI is archived.
5. Hosted wrappers of third-party CLIs are a fragile business. Terragon and Bloop (Vibe
   Kanban) shut down, Omnara pivoted to its own agent loop, and Crystal was deprecated.
   **Anthropic's terms forbid a platform paying for, reselling or intermediating Claude
   usage, or storing Claude.ai credentials.** They do allow a user to sign in to the
   unmodified binary on a hosted platform
   ([legal](https://code.claude.com/docs/en/legal-and-compliance)).

## 1.1 (a) The control plane / sandbox split

Three placements of the control plane appear in practice:

| Shape | Agent loop runs | Tools / code run | Examples |
|---|---|---|---|
| **A. All in the sandbox** | in the sandbox (the CLI itself) | in the sandbox | Claude Code cloud sessions, Codex Cloud, Jules, Amp orbs, Kilo Cloud, Terragon, Open-Inspect, Docker `sbx`, Claude Code self-hosted runner (spawns a child `claude`) |
| **B. Loop in the control plane, tools in the sandbox** | vendor control plane | sandbox / worker | Managed Agents self-hosted sandboxes, Cursor self-hosted workers, Devin Outposts, Coder Agents, Omnara, container-use (inverted: the agent's tools *are* MCP calls into containers) |
| **C. Agent-server in the sandbox, UI/orchestrator outside** | sandbox, behind an HTTP/WS API | sandbox | OpenHands (agent-server + workspace), `opencode serve`, Codex app-server |

Common properties of the split:

- **The control plane owns** identity and auth, the session queue, the transcript and event
  log (often Postgres or a Durable Object), the UI, and the git provider integration.
  Examples: Open-Inspect runs one Durable Object per session as a WebSocket hub and event
  log ([repo](https://github.com/ColeMurray/background-agents)). Omnara keeps a Postgres
  event log so that any stateless worker can resume after a crash
  ([repo](https://github.com/omnara-ai/omnara)).
- **The sandbox owns** the filesystem, processes, a daemon of the platform's own, and
  (in shape A) the agent CLI. Each platform has its in-sandbox daemon:

  | Platform | In-sandbox daemon |
  |---|---|
  | E2B | `envd` ([infra](https://github.com/e2b-dev/infra)) |
  | agent-sandbox | `sandboxd` ([USER_GUIDE](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/packages/sandboxd/USER_GUIDE.md)) |
  | OpenHands | agent-server ([doc](https://docs.openhands.dev/sdk/arch/agent-server)) |
  | Coder | workspace agent ([arch](https://coder.com/docs/admin/infrastructure/architecture)) |
  | DevPod | injected agent ([providers](https://devpod.sh/docs/developing-providers/quickstart)) |
  | Open-Inspect | Supervisor + Bridge |

- **Connections go outbound from the sandbox or worker** whenever it is not on the
  platform's own network:

  | Who dials out | Source |
  |---|---|
  | Claude Code runner, long-polling `api.anthropic.com` (each poll renews a ~60 s lease and serves as the heartbeat) | [self-hosted](https://code.claude.com/docs/en/self-hosted-environments) |
  | Cursor `agent worker` | [self-hosted](https://cursor.com/docs/cloud-agent/self-hosted) |
  | Devin worker | [Outposts](https://docs.devin.ai/cloud/outposts/overview.md) |
  | Warp worker | [self-hosting](https://docs.warp.dev/agent-platform/cloud-agents/self-hosting) |
  | Factory `droid daemon --remote-control` to `relay.factory.ai` | [remote control](https://docs.factory.com/remote-control) |
  | Claude Remote Control | [docs](https://code.claude.com/docs/en/remote-control) |
  | `omnarad` | [repo](https://github.com/omnara-ai/omnara) |
  | Happy relay, end-to-end encrypted | [repo](https://github.com/slopus/happy) |

  Coder is the exception: it uses a Tailscale-based mesh with a DERP relay fallback
  ([networking](https://coder.com/docs/admin/networking)).
- **Kubernetes always means one Pod or Job per claimed session**, which exits when done,
  plus optional warm pods:
  - Cursor `anysphere/k8s-workers` (`agent worker controller --spawn`, no CRD)
    ([self-hosted](https://cursor.com/docs/cloud-agent/self-hosted))
  - the Devin `devin-outpost-k8s` operator
    ([Outposts](https://docs.devin.ai/cloud/outposts/overview.md))
  - the Warp Kubernetes Job backend
    ([self-hosting](https://docs.warp.dev/agent-platform/cloud-agents/self-hosting))
  - Anthropic's runner, which exits after its sessions so Kubernetes restarts it with a
    fresh disk ([self-hosted](https://code.claude.com/docs/en/self-hosted-environments))
  - OpenHands Enterprise, whose `runtime-api` deployment runs sandboxes in the namespace
    `openhands-runtimes`
    ([k8s install](https://docs.openhands.dev/enterprise/k8s-install/installation)).

**What this means for LADO.** LADO's current shape is shape A: the unchanged CLI in a
tmux pane, talking back through hooks and `lado mcp`. That shape carries over to a remote
box unchanged, provided one thing holds. **The hook and MCP callbacks must reach LADO's
state over the network, through a connection the sandbox opens outward.** That means a
small in-sandbox LADO daemon (or `lado mcp` itself) that dials the control plane, holds
a lease and heartbeat in the Anthropic runner's style, and relays hooks, MCP calls and the
PTY stream.

## 1.2 (b) Pluggable runtime / sandbox provider interfaces

The concrete interfaces found, with their methods:

| Interface | Methods | Source |
|---|---|---|
| **OpenHands `BaseWorkspace`** (V1 SDK, MIT) | `execute_command`, `file_upload`, `file_download`, `git_changes`, `git_diff`; optional `pause()`/`resume()`; context manager; cost tracking. Implementations: Local, Remote (HTTP to agent-server: `POST /command`, `POST /file/upload`, `GET /file/download`), Docker, APIRemote (Runtime API), OpenHandsCloud, Apptainer, **AgentSandboxWorkspace** (claim from a warm pool; pause and resume by flipping `operatingMode`) | [base.py](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/workspace/base.py), [workspace.py](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-workspace/openhands/workspace/agent_sandbox/workspace.py) |
| **DevPod provider** (`provider.yaml`, a CLI) | `command` (required: a stdio channel into the machine, DevPod tunnels its agent over it), optional `init`, `create`, `delete`, `start`, `stop`, `status` → Running/Busy/Stopped/NotFound; `options` passed as env vars | [quickstart](https://devpod.sh/docs/developing-providers/quickstart) |
| **agent-sandbox `sandboxd`** wire contract | gRPC `process.v1.ProcessService`: `Start` (server stream: Init/stdout/stderr/Exit), `Execute`, `WriteStdin`, `SendSignal`, `ResizeTTY`; REST `/v1/files`, `/v1/health`, `/v1/metadata` | [USER_GUIDE](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/packages/sandboxd/USER_GUIDE.md) |
| **agent-sandbox Python SDK** | `create_sandbox(warmpool)`, `get_sandbox`, `list_*`, `delete_sandbox`; `commands.run`, `files.read/write/list/exists/delete`, `status`, `terminate` | [quickstart](https://agent-sandbox.sigs.k8s.io/docs/getting_started/python-sdk-quickstart/) |
| **E2B** | `Sandbox.create/connect/list/kill`, `setTimeout`, `commands.run`, `pty.create/sendInput/resize/kill/connect`, filesystem read/write/watch, public port URLs, `pause()` | [persistence](https://docs.e2b.dev/sandbox/persistence.md), [pty](https://docs.e2b.dev/sandbox/pty.md) |
| **Modal `Sandbox`** | `create(timeout, idle_timeout, block_network, pty, ports, cidr allowlists)`, `exec(pty=…)`, `tunnels()`, `snapshot_filesystem`, `_experimental_snapshot`, `filesystem.*`, `terminate` | [reference](https://modal.com/docs/reference/modal.Sandbox) |
| **Vercel `@vercel/sandbox`** | `Sandbox.create({source: git/tarball/snapshot, ports, networkPolicy, persistent})`, `getOrCreate({onCreate,onResume})`, `runCommand(detached)` → `logs()`, `writeStdin`; `writeFiles/readFile`, `domain(port)`, `stop`, `snapshot`, `delete` | [SDK](https://vercel.com/docs/sandbox/sdk-reference) |
| **Daytona** | `create`, `snapshot.create`, `process.code_run`, `start/stop/pause/archive/delete/recover/fork` | [sandboxes](https://www.daytona.io/docs/en/sandboxes.md) |
| **Runloop** | `cmd.exec`/`exec_async`, `suspend/resume`, files, tunnels, SSH, snapshots | [lifecycle](https://docs.runloop.ai/docs/devboxes/lifecycle) |
| **Fly Machines** REST | `POST create`, `/start`, `/stop`, `/suspend`, `/wait?state=`, `DELETE`, leases | [machines API](https://docs.fly.io/machines/api/machines-resource) |
| **Claude Managed Agents self-hosted** | env worker: `poll` → claim session → run tool calls locally → post results | [self-hosted sandboxes](https://platform.claude.com/docs/managed-agents/self-hosted-sandboxes) |
| **Warp worker backends** | Docker / Kubernetes Job / Direct / **Command** (hand the job to your own API) | [self-hosting](https://docs.warp.dev/agent-platform/cloud-agents/self-hosting) |
| **Open-Inspect** | sandbox backend packages for Modal, Daytona, E2B, OpenComputer, Vercel | [repo](https://github.com/ColeMurray/background-agents) |
| **Omnara** | 9 sandbox providers (Daytona, Modal, Blaxel, Freestyle, Unikraft, …) or `omnarad` machines | [repo](https://github.com/omnara-ai/omnara) |

**The common denominator** is a **"Linux box with a PTY, files, ports, and a lifecycle"**:

```
create(template/image, resources, env, network_policy) -> id
exec(cmd, pty?, cwd, env) -> stream(stdout/stderr/exit) + stdin + resize + signal
files.read / write / list (or upload/download tar)
expose_port(port) -> url                (optional)
suspend / resume (disk-only is the portable guarantee)
snapshot -> template_id                 (optional, for warm start)
delete / ttl / idle_timeout
status -> running | suspended | stopped | gone
```

Two cheap ways to make this pluggable:

1. **The DevPod model.** A provider is an external CLI with create, start, stop, status
   and a stdio command channel. It is cloud-agnostic, and third parties can write a
   provider without touching LADO's code.
2. **An in-sandbox daemon with a fixed wire contract.** Today, `sandboxd` is the emerging
   open standard on Kubernetes. Its caveat: the sandbox router cannot yet carry gRPC
   ([USER_GUIDE](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/packages/sandboxd/USER_GUIDE.md)).

The two combine well. A LADO "runtime provider" only needs to start a box and give LADO
one byte stream into it. LADO then runs its own small daemon inside, which provides the
tmux, PTY and hook/MCP relay.

## 1.3 (c) How they keep "any agent CLI" support

There are four strategies, ordered from most to least robust.

1. **Run the unchanged CLI in a real terminal, and get status from the CLI's own hooks or
   plugins.**
   - This is LADO's approach and Claude Squad's (tmux + worktree, any program via `-p`)
     ([repo](https://github.com/smtg-ai/claude-squad)).
   - Cursor's `terminals` run in a tmux session shared by human and agent
     ([setup](https://cursor.com/docs/cloud-agent/setup)), and Amp orbs have a shared tmux
     ([orbs](https://ampcode.com/docs/orbs)).
   - Docker `sbx` ships 11 agents out of the box, Claude Code, Codex, Copilot, OpenCode,
     Gemini and Droid among them ([agents](https://docs.docker.com/ai/sandboxes/agents)).
   - Warp Oz lets each run pick its harness: Warp Agent, Claude Code or Codex
     ([overview](https://docs.warp.dev/agent-platform/cloud-agents/overview)).
2. **A per-CLI adapter behind one interface.** Vibe Kanban's Rust trait
   `StandardCodingAgentExecutor` covers 9 CLIs
   ([mod.rs](https://github.com/BloopAI/vibe-kanban/blob/main/crates/executors/src/executors/mod.rs)):
   - `spawn(dir, prompt, env)` and `spawn_follow_up(dir, prompt, session_id, reset_to_message_id, env)`
   - `spawn_review`, `normalize_logs` (into a common event model)
   - `default_mcp_config_path`, `get_availability_info`, `get_setup_helper_action` (login/install)
   - `use_approvals`, `discover_options`
   - capabilities `SessionFork` and `ContextUsage`, and the error `AuthRequired`.
3. **A protocol: ACP, or each CLI's own server.**
   - OpenHands `ACPAgent` spawns an ACP adapter (`claude-agent-acp`, `codex-acp`,
     `gemini --acp`), reuses the CLI's existing login, and raises an error on SDK features
     the CLI cannot honour ([ACP guide](https://docs.openhands.dev/sdk/guides/agent-acp),
     [issue #590](https://github.com/OpenHands/software-agent-sdk/issues/590)).
   - In 2026 ACP stabilized `session/list`, `session/resume`, `session/close` and usage
     updates, but **its remote transport is still only a draft** (Transports WG, April
     2026) ([updates](https://agentclientprotocol.com/updates)).
   - The CLIs' own servers: `opencode serve` (HTTP + SSE `/event`)
     ([server](https://opencode.ai/docs/server/)) and Codex app-server (JSON-RPC 2.0,
     threads, turns and items; source is mirrors only).
4. **Screen scraping (rejected).**
   - Coder AgentAPI ran the CLI in an emulated 80×1000 vt100 terminal and snapshotted the
     screen every 25 ms. It reported "stable" after 2 s without change, and took a reply to
     be the screen diff with per-agent TUI chrome stripped.
   - It is now **archived and deprecated**, and Coder Tasks was removed in v2.37 in
     favour of a Coder-native agent ([agentapi](https://github.com/coder/agentapi),
     [changelog](https://coder.com/changelog/coder-2-37.md)).
   - This confirms LADO's "events, not screens" principle.

**What this means for LADO.** LADO already uses strategy 1, with provider adapters that
resemble strategy 2. To go remote, the CLI does not need to change. Only the transport of
hook events and MCP calls changes, from a local socket or process to a network relay. That
keeps every CLI LADO supports today, and adding one stays a provider change.

## 1.4 (d) Persistence and suspend/resume

The key distinction is whether memory survives a suspend.

| Keeps memory + processes | Keeps disk only | Neither (ephemeral unless snapshotted) |
|---|---|---|
| E2B `pause()` (≈4 s/GiB to pause, ≈1 s resume, kept until killed) ([persistence](https://docs.e2b.dev/sandbox/persistence.md)) | agent-sandbox `operatingMode: Suspended` (Pod deleted, PVCs kept) ([repo](https://github.com/kubernetes-sigs/agent-sandbox)) | Cloudflare containers (disk lost unless `snapshotContainer()`) ([lifetime](https://developers.cloudflare.com/sandbox/concepts/lifetime/)) |
| Fly Machines suspend (≤2 GB RAM; not guaranteed across deploys) ([suspend](https://docs.fly.io/reference/suspend-resume)) | Runloop suspend (Pro) ([lifecycle](https://docs.runloop.ai/docs/devboxes/lifecycle)) | Copilot (59-min Actions job) ([about](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)) |
| Daytona VM pause/fork ([sandboxes](https://www.daytona.io/docs/en/sandboxes.md)) | Vercel (auto FS snapshot on stop, auto-resume on next call) ([persistent](https://vercel.com/docs/sandbox/concepts/persistent-sandboxes)) | Factory Environments ("push branches yourself") ([run droids](https://docs.factory.com/environments/run-droids)) |
| Morph pause/branch (Infinibranch) ([SDK](https://github.com/morph-labs/morph-python-sdk)) | Daytona containers stop/archive ([sandboxes](https://www.daytona.io/docs/en/sandboxes.md)) | |
| Modal memory snapshots (experimental, 7 days) ([snapshots](https://modal.com/docs/guide/sandbox-snapshots)) | Docker `sbx` stop/start ([architecture](https://docs.docker.com/ai/sandboxes/architecture/)) | |
| Amp orbs ("wakes with … running services intact") ([orbs](https://ampcode.com/docs/orbs)) | Claude Code cloud (idle VM paused with files; reclaimed later → fresh VM, conversation restored, background work lost) ([cloud environments](https://code.claude.com/docs/en/cloud-environments)) | |
| | Codex Cloud (task state recoverable 7 days) ([cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments.md)) | |

The patterns that follow:

- **The portable guarantee is disk-only.** Every serious product therefore makes the
  *conversation* resumable from disk or the server. Claude Code restores the conversation
  in a fresh VM; ACP has `session/resume`; Vibe Kanban calls `spawn_follow_up(session_id)`;
  Codex has `thread/resume`; Coder Tasks had full resume only for Claude Code and Codex
  ([compat](https://coder.com/docs/@v2.36.3/ai-coder/agent-compatibility)).
- **Two hooks everywhere: "setup" (before the snapshot) and "start/resume" (every
  boot)**, because processes never survive a filesystem snapshot:
  - Claude: setup script + SessionStart hook
  - Codex: Install script + Start skill
  - Cursor: `install` + `start`/`terminals`
  - Amp: `.agents/setup` + `.agents/resume`
  - Devin: blueprint `initialize`/`maintenance`
  - devcontainers: `onCreate`/`postCreate` vs `postStart`
    ([spec](https://containers.dev/implementors/spec/)).
- **The event log lives outside the sandbox**, so a lost box loses no history. Examples
  are Managed Agents' server-side history
  ([overview](https://platform.claude.com/docs/managed-agents)) and Omnara's Postgres
  event log.
- **Risk:** credentials cached on disk end up in snapshots. Open-Inspect warns about this
  ([repo](https://github.com/ColeMurray/background-agents)), and Devin strips secrets
  before saving a snapshot
  ([blueprints](https://docs.devin.ai/onboard-devin/environment/blueprints.md)).

**What this means for LADO.** A remote agent should keep its worktree and the CLI's
session files (`~/.claude`, `~/.codex`, …) on the persistent volume. On resume, LADO
restarts the tmux pane with the CLI's own resume flag. LADO's SQLite state (messages,
artifacts, runs) is already outside the agent, which matches the "event log outside the
sandbox" pattern.

## 1.5 (e) Cost tricks

1. **A filesystem snapshot after the setup script** is universal. It is ~5 min / ~7 days
   at Claude, 12 h (legacy) or on publish at Codex, on each Build at Cursor (expires after
   30 days idle), via "Run and Snapshot" at Jules, rebuilt ~24 h at Devin, and 24 h at Amp
   (Part 2 §1–§12).
2. **Warm pools.** Examples:
   - agent-sandbox `SandboxWarmPool` with `replicas` and an `OnReplenish` update strategy;
     HPA and KEDA scale to zero ([sandbox docs](https://agent-sandbox.sigs.k8s.io/docs/sandbox/))
   - Cursor's warm pods ([self-hosted](https://cursor.com/docs/cloud-agent/self-hosted))
   - OpenHands claims from a warm pool in under a second.
3. **Idle shutdown with free or cheap suspended state.**
   - Daytona auto-stops after 15 min idle by default and auto-archives to object storage
     after 7 days ([sandboxes](https://www.daytona.io/docs/en/sandboxes.md)).
   - Modal has `idle_timeout` ([guide](https://modal.com/docs/guide/sandboxes)).
   - Paused Amp orbs are free ([sizes](https://ampcode.com/docs/orbs/sizes-and-costs)).
   - Stopped or suspended Fly machines pay only for the rootfs, $0.15/GB-mo
     ([pricing](https://docs.fly.io/about/pricing)).
   - Kilo containers spin down when idle
     ([docs](https://kilo.ai/docs/code-with-ai/platforms/cloud-agent)).
   - Claude cloud VMs pause when idle.
4. **Active-CPU billing.** Vercel ($0.128 per active CPU-hour) and Cloudflare bill CPU
   only while it is used, which suits agents that mostly wait on the LLM
   ([Vercel pricing](https://vercel.com/docs/sandbox/pricing),
   [CF pricing](https://developers.cloudflare.com/containers/platform/pricing/)).
5. **Snapshot restore instead of boot**, and copy-on-write branching. E2B restores
   Firecracker snapshots with lazy `userfaultfd` paging
   ([infra](https://github.com/e2b-dev/infra)). Morph branches a running VM into N copies
   (vendor claim: <250 ms) ([developers](https://cloud.morph.so/developers)).
6. **Several sessions per box.**
   - Kilo runs one container per user, with a worktree per session.
   - Claude's runner has `--capacity`.
   - The Agent SDK hosting guide lists a "long-running container with many sessions"
     pattern and sizes a session at about 1 CPU / 1 GiB / 5 GiB
     ([hosting](https://code.claude.com/docs/en/agent-sdk/hosting)).

   This matters for LADO, whose sessions are *teams*: one box per session with a
   worktree per agent is far cheaper than one box per agent.
7. **Session caps:** Copilot 59 min, E2B 1 h (Hobby) or 24 h (Pro), Modal 24 h max,
   Vercel 45 min (Hobby) or 24 h (Pro), reset on resume.

Reference prices for compute:

| Provider | Price | Source |
|---|---|---|
| E2B | ≈$0.05/vCPU-h + $0.016/GiB-h (Pro plan $150/mo) | [pricing](https://e2b.dev/pricing) |
| Daytona | $0.0504/vCPU-h + $0.0162/GiB-h | [pricing](https://www.daytona.io/pricing) |
| Modal | ≈$0.071/vCPU-h | [pricing](https://modal.com/pricing) |
| Runloop | $0.108/CPU-h | [pricing](https://www.runloop.ai/pricing) |
| Amp orbs | $0.08–$1.32/h | [sizes](https://ampcode.com/docs/orbs/sizes-and-costs) |
| Kilo | $0.60–$1.20/h | [docs](https://kilo.ai/docs/code-with-ai/platforms/cloud-agent) |
| Claude Managed Agents | $0.08/session-hour + tokens (secondary) | [verdent](https://verdent.ai/guides/claude-managed-agents-pricing) |

## 1.6 Code in and out, and how the human watches

**Code in:**

- A git clone from the forge is the norm: GitHub only for Copilot, Codex and Jules;
  GitHub, GitLab, Azure DevOps and Bitbucket for Cursor.
- Alternatives:
  - Claude uploads a **git bundle** when there is no GitHub remote; it cannot push back in
    that case ([cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)).
  - Docker `sbx` mounts the host repo by filesystem passthrough, or as a read-only source
    plus a private clone ([architecture](https://docs.docker.com/ai/sandboxes/architecture/)).
  - Vercel accepts git, a tarball or a snapshot as source.

**Code out:**

- Usually a pushed branch and then a (draft) PR.
- Copilot may only push `copilot/*` branches
  ([risks](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)).
- Kilo commits and pushes after *every message*.
- Cursor signs its commits with an HSM-held key.

**Handoff to local** is always git-based:

| Tool | Command | Source |
|---|---|---|
| Claude | `--teleport` (one-way) | [cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web) |
| Devin | `/handoff`, both ways | [handoff](https://docs.devin.ai/cli/handoff.md) |
| Jules | `remote pull` | [CLI reference](https://jules.google/docs/cli/reference/) |
| Codex | `apply` | (secondary) |
| Amp | `amp sync`: continuous mirroring while the agent works | [orbs](https://ampcode.com/docs/orbs) |
| Sculptor | Pairing Mode: two-way file sync | [pairing](https://docs.imbue.com/features/pairing-mode) |
| container-use | `checkout`/`merge`/`apply` | [workflow](https://container-use.com/environment-workflow) |

**Watching and steering:**

- **Structured event streams** are the main UI channel: Managed Agents SSE, `opencode
  serve` SSE, OpenHands WebSocket, Codex app-server notifications, `kilo cloud --stream`
  JSONL, Cursor's Cloud MCP of transcripts and events.
- **A terminal** sits beside it as a secondary channel:
  - Cursor and Amp share tmux; Devin has `devin ssh`; Factory runs SSH over a WebSocket
    relay.
  - Cloudflare provides a WebSocket terminal and E2B reconnectable PTY handles.
  - Cursor has remote-desktop takeover.
- **Steering** happens through follow-up messages (queued while the agent is busy) or an
  interrupt.

For LADO, which already has a web UI over the tmux terminals and an event feed, the remote
version is a **WebSocket PTY bridge plus the existing event feed**, both relayed through
the outbound connection.

## 1.7 Isolation technology

| Technology | Who uses it |
|---|---|
| **Firecracker microVM** | E2B, Vercel, Fly; Docker `sbx` and Cloudflare say "microVM" without naming the hypervisor |
| **gVisor** | Modal by default (a VM option exists); agent-sandbox via RuntimeClass |
| **Kata Containers** | agent-sandbox via RuntimeClass; Northflank (vendor claim) |
| **"VM", hypervisor unnamed** | Claude Code cloud, new Codex Cloud, Cursor, Jules, Devin ("does not run in containers"), Runloop |
| **Containers** | Managed Agents cloud, legacy Codex, Warp, Kilo, Daytona default, OpenHands Docker |

No vendor documents its hypervisor. For self-hosted Kubernetes the realistic choice is
**a RuntimeClass with gVisor or Kata, chosen by the cluster operator**, which is exactly
what agent-sandbox delegates.

**Network policy is always default-restricted with an allowlist:**

- Claude None/Trusted/Full/Custom ([cloud environments](https://code.claude.com/docs/en/cloud-environments))
- Codex off by default, with presets ([cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments.md))
- Copilot's firewall, which covers only the agent's Bash tool ([firewall](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-firewall))
- agent-sandbox's managed NetworkPolicy: ingress only from the router; RFC1918 and the
  metadata server blocked.

## 1.8 Credentials and subscriptions: the decisive constraint

**The pattern is an egress proxy that injects credentials, so real secrets never enter the
sandbox:**

- **Claude cloud:** a GitHub proxy swaps a scoped credential for the real token
  (`GH_TOKEN=proxy-injected`). "Network secrets" are attached after a request leaves the
  VM ([cloud environments](https://code.claude.com/docs/en/cloud-environments)).
- **Codex Cloud:** network secrets by placeholder substitution, a personal vault, OIDC,
  and Tailscale ([cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments.md)).
- **Codex GitHub Action:** a Responses API proxy, so the key is not handed to the agent
  ([action](https://learn.chatgpt.com/docs/github-action.md)).
- **Kilo:** short-lived capability tokens bound to one container, checked at the egress
  proxy and swapped for the real token per request ([blog](https://blog.kilo.ai/p/keys)).
- **Docker `sbx`:** a host proxy swaps a sentinel value for the real key
  ([architecture](https://docs.docker.com/ai/sandboxes/architecture/)).
- **Others:** Cloudflare (the Worker attaches the token), Runloop Agent Gateways, and the
  Coder AI Gateway (users authenticate with Coder tokens)
  ([AI Gateway](https://coder.com/docs/ai-coder/ai-gateway)).
- The **Agent SDK hosting guide** recommends exactly this proxy
  ([hosting](https://code.claude.com/docs/en/agent-sdk/hosting)).

**Model auth and terms.**

**Anthropic** ([legal](https://code.claude.com/docs/en/legal-and-compliance),
[auth](https://code.claude.com/docs/en/authentication)):

- **Hosting Claude Code requires the Commercial Terms**, and the binary must stay
  unmodified.
- The platform **may not pay for, resell or intermediate** Claude usage.
- It **may not collect, store or intermediate Claude.ai credentials**; sign-in goes
  through Anthropic's own flow.
- It explicitly **allows an end user to sign in to the unmodified binary with their own
  subscription on a hosted platform**.
- `claude setup-token` gives a one-year token that can only make model requests, and
  cannot be used for Remote Control.
- From 2026-06-15, programmatic use (`-p`, the Agent SDK, Actions) reportedly draws from a
  separate monthly Agent SDK credit (secondary:
  [aicatchup](https://aicatchup.com/news/claude-agent-sdk-monthly-credit-paid-plans)).
- Claude's own cloud sessions require a claude.ai login (no API key, Bedrock or Vertex)
  ([cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)). Its Actions
  integration accepts `CLAUDE_CODE_OAUTH_TOKEN`
  ([GH Actions](https://code.claude.com/docs/en/github-actions)).

**OpenAI** ([Codex auth](https://learn.chatgpt.com/docs/auth),
[New Stack](https://thenewstack.io/sign-in-with-chatgpt/)):

- `~/.codex/auth.json` can be copied to the headless machine, or you log in with
  `codex login --device-auth`.
- API keys or Enterprise access tokens are recommended for automation.
- "Sign in with ChatGPT" lets plan usage flow into 16 partner tools.

**Vendors' own billing:**

- Cursor bills cloud agents at model API rates.
- Copilot charges one premium request plus Actions minutes.
- Warp does not allow personal BYOK keys for cloud runs.
- Devin can bill GPT usage to a ChatGPT plan.

**The cautionary timeline:**

- Anthropic blocked subscription OAuth outside Claude Code on 2026-01-09.
- The open-source snapshot of Terragon, which let users plug in their subscriptions, is
  dated 2026-01-16. This is correlation only; no stated cause was found
  ([falcao.org](https://falcao.org/posts/anthropic-claude-access-crackdown-ecosystem-fallout/),
  [terragon-oss](https://github.com/terragon-labs/terragon-oss)).

**What this means for LADO:**

- **Self-hosted / BYO-cluster mode is clean.** The user's own secret store holds the
  user's own credentials, and the unmodified CLIs run in the user's infrastructure.
- **A hosted LADO cloud must:**
  - sign Anthropic's Commercial Terms
  - never pay for or resell Claude usage
  - never store users' Claude.ai tokens itself. Users would complete Anthropic's own login
    inside their sandbox (a device or browser flow through the terminal bridge), or bring
    an API key or Bedrock/Vertex credentials.
- **API keys can go through an egress proxy** using `ANTHROPIC_BASE_URL` / the Codex
  proxy pattern. Subscription OAuth cannot be proxied without "intermediating" it.

## 1.9 Market shifts of 2026 that matter for the decision

- **Coder:** AgentAPI was archived and Tasks removed (v2.37); Coder now runs its own
  agent in the control plane ([changelog](https://coder.com/changelog/coder-2-37.md)).
- **Daytona:** the open-source repo was archived (Oct 2026) and development is now
  private ([repo](https://github.com/daytonaio/daytona)). Part 4 §11 still calls Daytona
  "AGPL, self-hostable"; that came from older comparison pages and is out of date.
- **E2B:** the runtime is Apache-2.0 and self-hostable on a single node ("Embed"); BYOC
  is Enterprise only ([byoc](https://docs.e2b.dev/byoc.md)). Part 4 §11's "no self-host"
  is out of date.
- **Ona:** OpenAI announced the acquisition of Ona (ex-Gitpod) in June 2026 (secondary)
  ([techtimes](https://www.techtimes.com/articles/318338/20260613/openai-acquires-ona-run-codex-coding-agents-hours-without-your-computer.htm)).
- **Codex Cloud:** relaunched on 2026-09-29; the old one is now "Legacy"
  ([SiliconANGLE](https://siliconangle.com/2026/09/29/openais-codex-gets-reusable-cloud-environments-that-follow-developers-across-devices/)).
- **agent-sandbox:** reached v1.0.x with `sandboxd`, and OpenHands has adopted it
  ([repo](https://github.com/kubernetes-sigs/agent-sandbox)).
- **Shutdowns and pivots:** Bloop (Vibe Kanban) shut down on 2026-04-10, Terragon
  shut down, Crystal was deprecated, and Omnara pivoted; Catnip's repo returns 404
  ([vibekanban](https://vibekanban.com/shutdown)).
- **New hosted entrants:** Conductor Cloud (Jul 2026), Kilo Cloud Agents, Docker `sbx`
  cloud, Warp Oz, Factory Droid Computers, Claude Managed Agents.
- **DevPod:** upstream has been stale since 2025; there is an active fork
  (skevetter/devpod).

## 1.10 Implications for LADO (my reading, not a decision)

1. **Keep shape A.** Keep the unchanged CLI in tmux with hooks and MCP, and add a
   **remote runtime** whose only new piece is an in-sandbox LADO daemon. The daemon dials
   out to the LADO server and carries:
   - hooks, MCP calls and message delivery
   - the PTY stream for the UI
   - a lease and heartbeat.

   This keeps every supported CLI and the "events, not screens" principle.
2. **Make the runtime pluggable with a small interface:** create, exec/stream, files,
   suspend/resume, delete and status, plus snapshot as an option. Ship it with:
   - **local** (today's behaviour)
   - **docker**
   - **kubernetes via agent-sandbox** (Sandbox + PVC per LADO session, SandboxWarmPool,
     `operatingMode: Suspended` for idle, RuntimeClass chosen by the operator)
   - a **generic external-provider CLI** in the DevPod style, so that E2B, Modal, Daytona,
     Fly and others are adapters, not core code.
3. **Make one box hold one LADO session**, not one per agent, with a worktree per agent
   inside it (Kilo, Claude `--capacity`, the Agent SDK "many sessions" pattern). This
   keeps worktrees and git local to the team and cuts cost.
4. **Make disk-only persistence the contract.** Put the worktrees and the CLIs' session
   directories on the volume, and resume panes with each CLI's resume flag. Add a setup
   and a start hook, ideally read from `devcontainer.json`.
5. **Credentials:**
   - Self-hosted: the user's own secrets in the user's own store.
   - Hosted: an egress proxy for API keys and git tokens.
   - Claude subscription login: only through Anthropic's own flow, inside the user's
     sandbox, and never stored by LADO.
   - The legal terms decide whether a paid hosted tier can offer Claude subscriptions at
     all.
6. **For a hosted offering, sell what survives:** a control plane plus self-hosted
   runners (the vendor-standard shape) or a VPC/enterprise deployment. Avoid being a thin
   reseller of third-party CLI usage, which is how Terragon and Bloop ended.

---

# Part 2. Vendor-hosted coding agents (detailed evidence)


Research notes for LADO's optional remote execution. Every claim carries a source URL.
"Official" = vendor docs; "(secondary)" marks third-party sources that I could not confirm
against vendor docs. Fetched 2026-10-18.

---

### 0. The pattern in one paragraph

By late 2026 almost every vendor has converged on the same split: a **vendor-hosted
control plane** (agent loop or session orchestration, event stream, web/mobile UI, transcript
storage) plus an **execution plane** that is either a vendor-managed per-task VM or a
**customer-run worker that polls a queue over outbound HTTPS only** ("we never connect
into your network"). Anthropic (Claude Code self-hosted environments, Managed Agents
self-hosted sandboxes), Cursor (self-hosted workers), Devin (Outposts), Warp (Oz workers)
and Factory (Remote Control) all ship this worker model, most with a Kubernetes recipe.
Code moves in by **git clone from GitHub** (occasionally an uploaded bundle), out as a
**pushed branch / PR**, and environment warm-start is a **filesystem snapshot taken after a
setup script**. Credentials are increasingly kept *outside* the sandbox via an egress proxy
that injects them ("network secrets"). GitHub Copilot is the outlier: it runs on GitHub
Actions runners.

---

### 1. Claude Code cloud sessions (claude.ai/code, "Claude Code on the web")

**Architecture.** A cloud session runs on Anthropic-managed infrastructure, or on the org's
self-hosted environment when routed there; it keeps running after the laptop closes and
counts against plan usage with "no separate charge for the cloud VM"
([cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)). Available on Pro,
Max, Team and Enterprise premium/Chat+Code seats (same page). Each session runs "in an
isolated, Anthropic-managed VM" (same page, *Security and isolation*): Ubuntu 24.04 x86_64,
4 vCPU / 16 GB RAM / 30 GB disk
([cloud environments](https://code.claude.com/docs/en/cloud-environments)). Docker is
available inside the VM for `docker compose` (same page). The hypervisor technology is not
named in the docs.

**Code in/out.** The VM clones the GitHub remote at your current branch, not your local
checkout ("push first") ([cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)).
Without a GitHub remote or GitHub App install, the CLI **uploads a git bundle** (all branches
plus uncommitted tracked changes, <100 MB, falls back to current branch, then a squashed
snapshot; untracked files excluded; credential-like files left out); `CCR_FORCE_BUNDLE=1`
forces it, but non-GitHub remotes cannot be pushed back to (same page). Results come back as
a pushed branch / PR created from claude.ai/code, or via teleport (same page). GitHub access is
via the Claude GitHub App or `/web-setup` (sends local `gh` token) (same page).

**Watching / steering / handoff.** Start from browser, mobile, Desktop, terminal
(`claude --cloud "task"`), or routines; steer from any device; follow-ups from any machine with
`claude -p "msg" --cloud <session-id>` (queued, CLI exits); diff view with inline comments;
**teleport**: `claude --teleport [id]` fetches the session's branch and loads the full
conversation into the local terminal — one-way, the local copy diverges from the cloud one
(same page). Auto-fix subscribes to PR webhooks (CI failures, review comments) and pushes fixes
(same page). Idle VMs **pause with files saved**, are restored on the next message, and may be
reclaimed later; reopening provisions a fresh VM with conversation restored but background
work lost ([cloud environments](https://code.claude.com/docs/en/cloud-environments);
[cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)).

**Network.** Access levels None / Trusted (default: package registries, GitHub, cloud SDKs)
/ Full / Custom; GitHub goes through a separate proxy; the Anthropic API is reachable even at
None; all outbound traffic passes through an HTTP/HTTPS security proxy
([cloud environments](https://code.claude.com/docs/en/cloud-environments)).

**Credentials.** GitHub credentials "never enter a session's VM": the git client uses a scoped
credential that the **GitHub proxy** swaps for the real token; the proxy rejects branch
deletion and tag pushes, scopes API calls to attached repos, and blocks GraphQL;
`GH_TOKEN` reads as the placeholder `proxy-injected`. **Network secrets** are API keys the
agent proxy attaches to requests for listed hosts after the request leaves the VM, so the key
never appears in env or files. Plain env vars are readable by anyone using the environment
([cloud environments](https://code.claude.com/docs/en/cloud-environments)). Model auth
requires a claude.ai login; not available with Bedrock/Vertex or API-key auth
([cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)).

**Setup / warm start.** Setup script runs before Claude Code launches; if it finishes in
~5 minutes Anthropic **snapshots the filesystem** and reuses it; rebuild on script/allowlist
change or after ~7 days; snapshot keeps files (incl. pulled Docker images), not processes;
SessionStart hooks are for per-session, cloud-and-local setup; replacing the base image is
not supported ([cloud environments](https://code.claude.com/docs/en/cloud-environments)).

**Self-hosted environments (public beta, Team/Enterprise).** Anthropic's control plane puts
the session on the environment's queue; a **runner** you operate claims it, clones the repo,
and spawns a child Claude Code process; everything is outbound HTTPS to `api.anthropic.com`
("Anthropic never connects into your network"); polling doubles as heartbeat with a ~60 s
lease; a runner locks to one owner, runs up to `--capacity` sessions, and by default exits
when its sessions end so Kubernetes can restart it with a fresh disk; an autoscaling
orchestrator can start runners on demand; Kubernetes and Compose recipes exist; git
credentials come from your deployment (or opt-in to Anthropic's git proxy); inference can be
redirected to Bedrock / Vertex but the transcript still goes to Anthropic; isolation is the
customer's responsibility ([self-hosted](https://code.claude.com/docs/en/self-hosted-environments);
[cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)).

### 2. Claude Code GitHub Actions

`anthropics/claude-code-action@v1` runs Claude Code inside a workflow on GitHub-hosted (or any)
runners; interactive mode reacts to `@claude` in issues/PRs and updates a comment as it works;
automation mode runs a `prompt` on any event incl. cron
([GH Actions docs](https://code.claude.com/docs/en/github-actions)). Code gets in via
`actions/checkout`; results are commits/PRs authenticated as the Claude GitHub App (or a
custom app / `github_token`). Auth: `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` (a
**subscription** token from `claude setup-token`), OIDC workload identity federation to a
Console service account, or Bedrock / Vertex / Foundry via OIDC (same page). Only users with
write access trigger it; bots blocked unless allow-listed (same page). Cost = Actions minutes
+ API tokens (or subscription) (same page). Isolation and network are whatever the runner
gives you.

### 3. Claude Agent SDK hosting guidance and Claude Managed Agents

**Agent SDK (self-host).** The SDK spawns a `claude` CLI subprocess per session, which owns a
shell, cwd and JSONL transcripts on local disk; patterns: ephemeral container per task,
long-running container with many sessions, hybrid (ephemeral containers hydrated from a
`SessionStore`), multi-agent container; starting point 1 GiB RAM / 5 GiB disk / 1 CPU per
agent; recommends an egress proxy that enforces allowlists and injects credentials; points to
Docker, gVisor, Firecracker for isolation; cookbook has Docker, Modal and Kubernetes manifests
([hosting](https://code.claude.com/docs/en/agent-sdk/hosting)). Multi-tenant isolation:
`settingSources: []`, per-tenant `CLAUDE_CONFIG_DIR`, per-tenant cwd (same page).

**Managed Agents (beta, `managed-agents-2026-04-01`).** Anthropic hosts the agent loop;
concepts Agent / Environment / Session / Events; events stream over SSE, history persisted
server-side; steer by sending more user events or interrupt
([overview](https://platform.claude.com/docs/managed-agents)). Cloud environments give each
session "a fresh Linux container"; `packages` (apt, cargo, gem, go, npm, pip) cached across
sessions of the environment; networking `limited` (allowed_hosts, allow_package_managers,
allow_mcp_servers) or `unrestricted` (API default if omitted!); sessions don't share
filesystem state ([environments](https://platform.claude.com/docs/managed-agents/environments)).
**Self-hosted sandboxes:** a `self_hosted` environment is a work queue; your **environment
worker** (`ant beta:worker poll`, or SDK workers) claims sessions, runs each tool call locally
and posts results back; only outbound HTTPS needed; model stays at Anthropic; `file` /
`github_repository` resources are rejected for self-hosted (you stage files yourself);
partner guides: AWS Lambda MicroVMs, Cloudflare, Daytona, E2B, Fly.io Sprites, GKE Agent
Sandbox, Modal, Namespace, Vercel and others
([self-hosted sandboxes](https://platform.claude.com/docs/managed-agents/self-hosted-sandboxes)).
Pricing: tokens at API rates plus a session-runtime fee reported as $0.08 per session-hour,
running time only (secondary: [verdent](https://verdent.ai/guides/claude-managed-agents-pricing),
[truefoundry](https://www.truefoundry.com/fr/blog/claude-managed-agents-pricing)). Not ZDR /
HIPAA eligible ([overview](https://platform.claude.com/docs/managed-agents)).

### 4. OpenAI Codex Cloud (new, Sept 2026) and Codex Cloud (Legacy)

**Status.** OpenAI relaunched Codex Cloud at DevDay (2026-09-29); the old one is now
"Codex Cloud (Legacy)", still running code review, `@codex` GitHub review and Linear
integrations during transition
([SiliconANGLE](https://siliconangle.com/2026/09/29/openais-codex-gets-reusable-cloud-environments-that-follow-developers-across-devices/);
[legacy guide](https://learn.chatgpt.com/docs/environments/cloud-environment)).

**New Codex Cloud.** "Each cloud task runs in a VM"; Plus: 2 vCPU / 8 GiB / 8 GiB disk; Pro,
Business, Enterprise: 4 vCPU / 16 GiB / 32 GiB; larger via Enterprise account team. Codex
infers runtimes and drafts an **Install script** plus a **Start skill** (start services,
readiness checks); **publishing captures the prepared filesystem** for new tasks; existing
tasks keep their own saved state, incl. uncommitted changes; background repo refreshes keep
dependency caches; saved VM state recoverable for **7 days** after last use. Internet off by
default, presets Package managers / Custom / All; **network secrets** via proxy placeholder
substitution (HTTPS 443, setup and task phases); **personal vault** for per-user values in
shared environments; **Tailscale VPN** (only supported provider) for private subnets;
**OIDC** short-lived AWS/Azure credentials (Enterprise by request); agent egress IP feed
published. GitHub only (no GitLab / GHES); no computer or browser use yet; tasks can start
from Slack / Teams in Enterprise
([cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments.md)).
Tasks start from web, mobile, desktop app or the CLI; results reviewed as changed files, then
commit or open a PR; steering = follow-up requests ([Codex Cloud](https://learn.chatgpt.com/docs/cloud)).

**Legacy Codex Cloud.** Container from the `codex-universal` image, repo checked out at a
branch or SHA; setup script (separate bash session) and maintenance script on cache resume;
container state **cached up to 12 h**, shared across users in Business/Enterprise; env vars
for the whole task; **secrets only for setup scripts, removed before the agent phase**;
internet on during setup, off by default for the agent, all egress through an HTTP/HTTPS
proxy; output is a diff → PR
([legacy guide](https://learn.chatgpt.com/docs/environments/cloud-environment)). CLI
`codex cloud exec`, `codex cloud diff`, `codex apply` pull diffs locally (secondary:
[danielvaughan](https://codex.danielvaughan.com/2026/05/19/codex-cli-cloud-delegation-workflows-plan-locally-execute-remotely-apply-diffs/)).
Not covered by OpenAI's BAA (secondary search summary). **No self-hosting** of Codex Cloud
is documented.

### 5. Codex GitHub Action / `codex exec`

`openai/codex-action@v1` installs the CLI, starts a **Responses API proxy** when given an API
key (so the key is not handed to the agent process), and runs `codex exec`; inputs `sandbox`
(`read-only`/`workspace-write`/`danger-full-access`), `safety-strategy` (default `drop-sudo`,
irreversibly removes sudo; `unprivileged-user`; `read-only`; `unsafe` required on Windows);
`allow-users`/`allow-bots` default to write-access users; output via `final-message` /
`output-file`; Linux or macOS runners
([action docs](https://learn.chatgpt.com/docs/github-action.md)). `codex exec` defaults to a
read-only OS sandbox; network off by default (secondary search summary of
[non-interactive mode](https://developers.openai.com/es-419/docs/non-interactive-mode)).

### 6. Cursor Cloud Agents (formerly Background Agents)

**Architecture.** Each agent runs "in an isolated VM" with a full dev environment; Cursor
manages provisioning, snapshots, capacity ([cloud agent](https://cursor.com/docs/cloud-agent)).
VMs are isolated Ubuntu machines ([setup](https://cursor.com/docs/cloud-agent/setup)) in
Cursor's AWS infrastructure ([security](https://cursor.com/docs/cloud-agent/security-network)).
Clones from GitHub, GitLab, Azure DevOps, Bitbucket Cloud; works on a separate branch; pushes;
multi-repo with a PR per repo ([cloud agent](https://cursor.com/docs/cloud-agent)). Every
commit signed with an HSM-backed Ed25519 key ([security](https://cursor.com/docs/cloud-agent/security-network)).

**Environment.** `.cursor/environment.json`: `build` (Dockerfile + context), `install`
(idempotent, runs when a Build is created, background), `snapshot` (ID), `start`, `terminals`
(processes in a **tmux session shared by you and the agent**). A successful Build captures disk
state; new agents start from it; processes and env exports don't survive; Dockerfile layer
cache ([setup](https://cursor.com/docs/cloud-agent/setup)). Snapshots are encrypted VM-disk
copies that expire after 30 days of inactivity ([security](https://cursor.com/docs/cloud-agent/security-network)).

**Watching / steering.** Start from iOS, cursor.com/agents, Desktop, Slack, GitHub / Bitbucket
comments, Linear, API; artifacts (screenshots, videos, logs); **remote desktop takeover** and
hand back; read-only share links; built-in Cloud MCP exposes transcripts and events
([cloud agent](https://cursor.com/docs/cloud-agent)).

**Network / secrets.** Internet on by default; modes Allow all / Default + allowlist /
Allowlist only; Tailscale (userspace) or Cloudflare Tunnel for private nets; PrivateLink for
Enterprise; Runtime Secrets redacted from transcripts and commits; Build Secrets only for
Docker build; OIDC recommended; commands auto-run (exfiltration warning); Privacy Mode
required ([security](https://cursor.com/docs/cloud-agent/security-network)). AWS role assume
via `CURSOR_AWS_ASSUME_IAM_ROLE_ARN` ([setup](https://cursor.com/docs/cloud-agent/setup)).

**Self-hosted.** Cursor keeps agent loop and inference; your **worker** (`agent worker start`)
does file edits, terminal, MCP, checkout; long-lived outbound HTTPS, no inbound; Kubernetes
template `anysphere/k8s-workers` runs `agent worker controller --spawn` (a Pod per claimed
request, warm pods optional, no CRD); Team Pools need Enterprise; self-hosted machines ignore
`environment.json` ([self-hosted](https://cursor.com/docs/cloud-agent/self-hosted)).
**Pricing:** API pricing of the chosen model, spend limit, paid plan required
([cloud agent](https://cursor.com/docs/cloud-agent)).

### 7. GitHub Copilot cloud agent (formerly coding agent)

**Architecture.** "Its own ephemeral development environment, powered by GitHub Actions"
([customize env](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/customize-the-agent-environment)).
Sessions max 59 minutes; one branch, one PR per task; GitHub-hosted repos only
([about](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)).
Pushes only to a new `copilot/` branch (or the PR branch when mentioned on a PR); cannot run
raw git; draft PRs must be merged by a human; Actions workflows on its PRs need approval from a
write-access user; only write-access users can trigger it
([risks](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)).

**Setup.** `.github/workflows/copilot-setup-steps.yml` with one job `copilot-setup-steps`;
honoured keys: `steps`, `permissions`, `runs-on`, `services`, `snapshot`, `timeout-minutes`
(≤59); must be on default branch; failed step → agent starts anyway. Runners: standard Ubuntu,
**larger runners**, or **self-hosted** (ephemeral via ARC / Runner Scale Set recommended);
Ubuntu x64 and Windows only; self-hosted requires disabling the integrated firewall
([customize env](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment)).
The `snapshot` key exists but its semantics were not documented on the pages I read.

**Firewall.** On by default with a recommended allowlist (OS repos, container registries,
language registries, CAs, Playwright); applies **only to processes started by the agent's Bash
tool**, not MCP servers or setup steps; blocked requests are reported in the PR; org/repo
custom allowlists ([firewall](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-firewall)).

**Watching.** Session logs on github.com; chat to steer during the session
([about](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)).
**Pricing:** one premium request per session plus GitHub Actions minutes
([billing](https://docs.github.com/en/billing/concepts/product-billing/github-copilot-premium-requests)).
Model auth is GitHub's; no BYO key.

### 8. Google Jules

**Architecture.** Each task gets "a secure, short-lived virtual machine" running Ubuntu with
Node, Bun, Python, Go, Java, Rust, Docker, etc.; setup script in repo Configuration;
**"Run and Snapshot"** saves an environment snapshot reused for later tasks
([environment](https://jules.google/docs/environment/)). The VM has internet access; long-running
processes (dev servers) not supported in setup ([FAQ](https://jules.google/docs/faq/)).

**Flow.** Pick repo + base branch, prompt, plan approval, mid-task chat feedback, pause;
activity feed and diffs; "Create branch" pushes changes (you own the branch, Jules is commit
author), then open a PR; GitHub issues labelled `jules` start tasks
([running tasks](https://jules.google/docs/running-tasks/)). **CLI** `jules remote new
[--parallel N]`, `remote list`, `remote pull --session <id>` to bring results local
([CLI reference](https://jules.google/docs/cli/reference/)). **API** v1alpha: sessions,
activities, sources at `jules.googleapis.com`; session outputs include PRs
([API reference](https://developers.google.com/jules/api/reference/rest)). Pricing via Google AI
plans: Free 15 tasks/day, Pro 100/day, Ultra 300/day (secondary:
[kie.ai](https://kie.ai/blog/what-is-jules)). No self-hosting.

### 9. Devin (Cognition)

**Architecture.** A stateless cloud "Brain" plus a **Devbox** VM where code runs; every
session needs a new VM; Devin "does not run in containers" (needs virtualization: AWS i3 bare
metal, Azure Lasv3 in VPC); deployment models Enterprise Cloud (multi-tenant, one machine per
session) and Customer Dedicated single-tenant VPC connected via PrivateLink or IPSec
([deployment](https://docs.devin.ai/enterprise/deployment/overview);
[VPC](https://docs.devin.ai/enterprise/vpc/overview.md)).

**Environment.** YAML **blueprints** (`initialize`, `maintenance`, `knowledge`, `post-build`,
`clone`); builds clone up to 10 repos, run steps, health-check and **save a snapshot**; one
active snapshot per org; rebuild on blueprint/repo/secret change and ~every 24 h; each session
boots a fresh copy and pulls latest code; secrets stripped before snapshot save
([blueprints](https://docs.devin.ai/onboard-devin/environment/blueprints.md)). macOS and
Windows VMs are also offered ([docs index](https://docs.devin.ai/llms.txt)).

**Human interaction.** IDE, browser, shell tools in the web app; `devin ssh` into the session VM
and port forwarding ([docs index](https://docs.devin.ai/llms.txt)). CLI `/handoff` packages
conversation + current branch + uncommitted diff into a cloud session; inside a cloud session
`/handoff` fetches its PR branch locally and continues locally
([handoff](https://docs.devin.ai/cli/handoff.md)).

**Self-hosted: Devin Outposts.** Agent loop stays in Devin Cloud; your **workers**
(`devin worker start --outpost=<name>`) claim queued sessions over outbound HTTPS and run all
commands, edits and repo access; per-session isolation is your orchestrator's job; open-source
`devin-outpost-k8s` operator; partners Namespace, Modal, NVIDIA, Daytona, E2B, Cloudflare;
Pro/Max/Teams, off by default on Dedicated Tenant
([Outposts](https://docs.devin.ai/cloud/outposts/overview.md)). **Pricing:** Free / Pro $20 /
Max $200 / Teams $80 base + $40 per seat; Enterprise in ACUs (secondary:
[automationatlas](https://automationatlas.io/answers/devin-pricing-explained-2026/)).

### 10. Amp (Orbs)

Orbs are remote machines in Amp's cloud; each orb thread gets a fresh isolated environment;
pauses a few minutes after work ends and wakes with conversation, files and running services
intact; shared tmux terminal between human and agent; diff/files view; `amp sync <thread>`
mirrors an orb thread's changes into the local checkout while the agent keeps working;
`amp -ox "task"` starts one; burst of 20 orbs then 1 per 5 min
([orbs](https://ampcode.com/docs/orbs)). Debian 12 image with authenticated `gh`; repo at
`/home/user/workspace/repo`; `.agents/setup` runs on fresh orbs, then the sandbox is
**snapshotted and reused for up to 24 h**; `.agents/resume` runs on every wake
([blog](https://ampcode.com/notes/putting-an-agent-in-an-orb)). Per-minute billing:
a1.tiny $0.08/h … a1.large $0.66/h (8 CPU, 16 GB) … a1.xxlarge $1.32/h; 60 GB disk; paused
orbs free ([sizes](https://ampcode.com/docs/orbs/sizes-and-costs)). Isolation technology and
self-hosting are not documented.

### 11. Factory (Droids)

**Environments** (replacing deprecated Cloud Templates) are built into a snapshot; each cloud
session / automation / mission worker gets a fresh instance from it; instance changes are not
written back ("push branches yourself")
([run droids](https://docs.factory.com/environments/run-droids);
[cloud templates](https://docs.factory.com/droid-computers/cloud-templates)). **Droid Computers**
are persistent Factory-managed machines (auto-pause / auto-resume), creatable from an
Environment snapshot; SSH and TCP port-forward over a WebSocket relay; relay mode blocks all
public traffic; git credentials injected from the personal GitHub integration
([Droid Computers](https://docs.factory.com/droid-computers/overview.md)). **Remote Control /
BYOM**: `droid daemon --remote-control` on your own Linux/macOS/Windows box, outbound to
`relay.factory.ai`, uses that machine's own git credentials
([remote control](https://docs.factory.com/remote-control)). Pricing and isolation technology
not documented on these pages.

### 12. Warp (Oz cloud agents)

Cloud agents run on Warp-hosted compute or your own; triggers: Slack, Linear, CI failures,
schedules, API, `oz` CLI; harness choice per run: Warp Agent, **Claude Code or Codex**;
transcripts, shareable session links, **Agent Session Sharing** to attach and steer; billing =
platform agent time + inference + Warp compute; no personal BYOK for cloud runs
([overview](https://docs.warp.dev/agent-platform/cloud-agents/overview)). An **environment** is
a Docker image + repos + setup commands, fresh workspace per run, non-root user
([environments](https://docs.warp.dev/agent-platform/cloud-agents/environments)).
**Self-hosting (Enterprise):** `oz-agent-worker` connects outbound only; backends Docker
(container per task), Kubernetes (Job per task), Direct (host process), Command (hand to your
own job API); unmanaged mode = run `oz agent run` in your CI and Warp only records it; agent
context and model requests still pass through Warp
([self-hosting](https://docs.warp.dev/agent-platform/cloud-agents/self-hosting)).

---

### 13. Comparison table

| Vendor | Execution unit (hosted) | Self-host / BYO compute | Code in → out | Warm start | Secrets model | Human view |
|---|---|---|---|---|---|---|
| Claude Code cloud | VM per session, Ubuntu 24.04, 4c/16G | Runner polls queue (beta, Team/Ent), K8s | GitHub clone or bundle upload → branch/PR, teleport | FS snapshot after ≤5 min setup, ~7 d | GitHub proxy + network secrets outside VM | web/mobile/CLI stream, `--cloud` follow-ups, teleport |
| Claude Managed Agents | container per session | worker executes tool calls (many partners) | API resources (files, GitHub repo) | package cache per env | vaults / limited egress | SSE events, steer/interrupt |
| Codex Cloud (new) | VM per task, 2–4c | none documented | GitHub → commit/PR | published FS + 7 d task state | proxy network secrets, vault, OIDC, Tailscale | web/mobile/desktop/CLI |
| Codex Cloud legacy | container (`codex-universal`) | none | GitHub → diff/PR, `codex apply` | 12 h container cache | secrets only in setup | web, CLI |
| Cursor | Ubuntu VM on AWS | worker, K8s controller (Ent pools) | GitHub/GitLab/ADO/BB → branch/PR (signed) | Build disk snapshot, 30 d | runtime secrets redacted, OIDC | web, remote desktop, shared tmux |
| Copilot | GitHub Actions runner | self-hosted / larger runners (ARC) | checkout → `copilot/` branch, draft PR | `snapshot` key (undoc.) | Actions `copilot` env secrets | session logs, PR comments |
| Jules | Ubuntu VM per task | none | GitHub → "Create branch" → PR, `remote pull` | "Run and Snapshot" | not documented | web feed, CLI |
| Devin | VM per session (no containers) | Outposts workers, K8s operator; VPC tenant | blueprint clone → PR; `/handoff` both ways | org snapshot, rebuilt ~24 h | secrets stripped before snapshot | IDE/browser/shell, `devin ssh` |
| Amp | orb (isolated, pausable) | none documented | repo in orb → `amp sync` / push | `.agents/setup` snapshot 24 h | n/d | shared tmux, diff, sync |
| Factory | instance from Environment snapshot; persistent Droid Computers | BYOM via relay | clone → push yourself | Environment snapshot | GitHub integration creds | app, SSH/port-forward via relay |
| Warp Oz | container per run | worker: Docker/K8s Job/Direct/Command (Ent) | Docker image + repos | n/d | Agent Secrets injected | session sharing, steer |

### 14. Takeaways relevant to LADO (my reading)

1. The **outbound-only, queue-claiming worker** is the industry-standard self-host shape
   (Anthropic, Cursor, Devin, Warp, Factory). Lease + heartbeat-by-poll + one-owner-per-runner
   (Anthropic) is a well-specified reference design.
2. Kubernetes support is always "one Pod/Job per claimed session, exit when done" plus an
   optional warm pool (Cursor `--warm-idle`, Anthropic `--drain-grace-sec=0`).
3. **Credential injection at an egress proxy** (Claude GitHub proxy + network secrets, Codex
   network secrets, Agent SDK guidance) is becoming the norm; LADO's remote mode could adopt
   the same so agent containers never hold git or API tokens.
4. **Filesystem snapshot after a setup script** is universal (Claude ~5 min / 7 d, Codex 12 h
   legacy / publish, Cursor Builds, Jules, Devin 24 h, Amp 24 h); processes never survive the
   snapshot, so a separate start/resume hook exists everywhere (SessionStart, Start skill,
   `start`/`terminals`, `.agents/resume`).
5. **Shared tmux between human and agent** is used by Cursor (`terminals`) and Amp — close to
   LADO's local model, so a remote tmux-in-pod design has precedent.
6. Handoff is git-based everywhere: push branch / fetch branch (teleport, Devin `/handoff`,
   Jules `remote pull`, Codex `apply`, Amp `sync`). Claude's bundle upload covers the
   "no GitHub remote" case.
7. Subscription auth in remote/CI is possible only for some: Claude (`CLAUDE_CODE_OAUTH_TOKEN`
   for Actions; cloud sessions need claude.ai login), Devin can bill GPT usage to a ChatGPT plan
   ([docs index](https://docs.devin.ai/llms.txt)); Warp disallows personal BYOK for cloud runs.
8. No vendor documents its hypervisor; only Devin states "VM, not containers"; Managed Agents
   uses containers; Agent SDK docs point to gVisor / Firecracker for self-hosters.

---

# Part 3. Sandbox and runtime providers (detailed evidence)


Research notes for LADO's optional remote execution. Every claim carries a source URL;
"(src: …)" refers to official docs or GitHub unless marked as vendor marketing or
secondary. Where a docs page did not state something, the notes say so instead of guessing.

### 0. Headline changes in 2026 that affect our plans

- **Coder AgentAPI is archived and deprecated.** README: "AgentAPI is deprecated and no
  longer maintained"; repo `archived: true`, MIT
  (src: https://github.com/coder/agentapi, GitHub API repo metadata). **Coder Tasks**
  (which was built on AgentAPI) is disabled and deprecated from Coder v2.37; Coder Agents
  (a native Go agent whose loop runs in the control plane) is its replacement
  (src: https://coder.com/changelog/coder-2-37.md, https://coder.com/docs/ai-coder/tasks).
- **Daytona's open-source repo is archived.** "As of June 2026, Daytona's core development
  has moved to a private codebase"; archived Oct 3, 2026; last open release v0.190.0
  (src: https://github.com/daytonaio/daytona). A community fork "Nightona" claims to
  continue it under AGPL-3.0 (secondary, self-interested:
  https://cdn.jsdelivr.net/gh/nightona-co/nightona@main/README.md).
- **OpenAI announced the acquisition of Ona (ex-Gitpod)** on June 11, 2026 to give Codex a
  cloud execution layer (secondary coverage:
  https://www.techtimes.com/articles/318338/20260613/openai-acquires-ona-run-codex-coding-agents-hours-without-your-computer.htm,
  https://andrew.ooo/answers/openai-acquires-ona-gitpod-codex-explained-june-2026/). Ona's
  runner docs now describe a "Codex Agent" (src: https://www.ona.com/docs/ona/runners/overview).
- **kubernetes-sigs/agent-sandbox reached v1.x** (v1.0.7 on 2026-10-15, API
  `agents.x-k8s.io/v1beta1`, Apache-2.0, ~4.3k stars) and now ships a standard in-sandbox
  runtime daemon `sandboxd` (gRPC process service + REST files)
  (src: https://github.com/kubernetes-sigs/agent-sandbox, GitHub releases API).
- **Docker Sandboxes moved to an `sbx` CLI**, microVM per sandbox, local (free) and cloud
  (paid) modes (src: https://docs.docker.com/ai/sandboxes/).
- **E2B's runtime is Apache-2.0 and self-hostable** ("E2B Embed", single node, Docker
  Compose; Terraform for GCP/AWS/Azure; a Kubernetes manifest)
  (src: https://github.com/e2b-dev/infra — now redirects to e2b-dev/runtime).
- **DevPod upstream is stale** (last release v0.7.0-alpha.34, 2025-06-23; last push
  2025-11-14); an active fork exists at skevetter/devpod (GitHub API for
  loft-sh/devpod and skevetter/devpod).

---

### 1. E2B

**Architecture.** One Firecracker microVM per sandbox, in its own cgroup and network
namespace, with a per-sandbox nftables egress firewall. Components: API (control plane:
lifecycle, placement, auth, quotas), Orchestrator (runs Firecracker VMs on each node;
also the template builder), client-proxy (edge router mapping sandbox URLs to nodes),
`envd` (daemon inside every VM exposing process, filesystem and port APIs). Creating a
sandbox = restoring a snapshot, not booting a kernel; memory pages load lazily via
`userfaultfd`, rootfs is a copy-on-write overlay (src: https://github.com/e2b-dev/infra).
Marketing: "hardware-isolated Firecracker microVM rather than a shared-kernel container",
boots from a snapshot, no ms figure given (src: https://e2b.dev/).

**API surface** (JS / Python):
- Create/connect/list/kill: `Sandbox.create()`, `Sandbox.connect(id)`,
  `Sandbox.list({query:{state:['paused']}})`, `sandbox.kill()` / `Sandbox.kill(id)`,
  `setTimeout()` / `set_timeout()` (src: https://docs.e2b.dev/sandbox/persistence.md).
- Exec: `sandbox.commands.run(...)` (src: https://docs.e2b.dev/).
- PTY: `sandbox.pty.create({cols, rows, onData, envs, cwd, user})`,
  `pty.sendInput(pid, bytes)` (Py `send_stdin`), `pty.resize(pid, size)`,
  `pty.kill(pid)`, `pty.connect(pid)` to reattach; `TERM=xterm-256color`; keepalive ping
  every 50 s, clients must reconnect on drop (src: https://docs.e2b.dev/sandbox/pty.md).
  The page does not name the wire transport (envd is gRPC/Connect-based per the repo, not
  confirmed in docs).
- Files: read/write, info, metadata, watch, upload, download pages
  (src: https://docs.e2b.dev/llms.txt → /filesystem/*). Public URL per port:
  https://docs.e2b.dev/network/public-url.md. Volumes (beta): /volumes/*. The `sandbox.git`
  module is deprecated; use `commands.run()` (src: https://docs.e2b.dev/sandbox/git-integration.md).
- Lifecycle events API and webhooks exist (src: https://docs.e2b.dev/llms.txt).

**Persistence.** `pause()` saves filesystem + memory (or `mode: 'filesystem'` = reboot on
resume). Pause ≈ 4 s per GiB RAM, resume ≈ 1 s. Paused sandboxes are kept indefinitely
until killed. Auto-pause via `lifecycle.onTimeout: 'pause'` (default `kill`),
`autoResume` default false. Services are unreachable and clients disconnect while
paused (src: https://docs.e2b.dev/sandbox/persistence.md).

**Templates.** Template = environment definition, built from a base image with
start/ready commands, caching, tags, private registries
(src: https://docs.e2b.dev/template/quickstart.md and siblings listed in https://docs.e2b.dev/llms.txt).

**Self-host / BYOC.** BYOC on AWS, GCP, Azure, Enterprise only, operated by E2B; data path
(sandbox traffic, templates, snapshots, logs) stays in the customer VPC; E2B Cloud gets
anonymized metrics (src: https://docs.e2b.dev/byoc.md). E2B Embed: Apache-2.0
single-machine runtime you operate yourself, does not scale across machines
(src: https://docs.e2b.dev/byoc.md, https://github.com/e2b-dev/infra).

**Pricing.** Hobby $0 + one-time $100 credit, 1 h max continuous runtime, 20 concurrent;
Pro $150/month, 24 h runtime, 100 concurrent (+500 slots for $500/mo); pausing resets the
runtime limit (src: https://docs.e2b.dev/billing.md). $0.000014/vCPU-s,
$0.0000045/GiB-s; storage included (10 GiB Hobby / 20 GiB Pro); default 2 vCPU / 4 GiB
(src: https://e2b.dev/pricing).

### 2. Daytona

**Architecture.** Interface plane / control plane / compute plane; sandboxes have a
dedicated kernel, filesystem, network stack (src: https://github.com/daytonaio/daytona).
Default sandboxes are containers; Linux/Windows VM, GPU and macOS sandboxes also exist;
"<90ms" container startup (vendor claim) (src: https://www.daytona.io/docs/en/sandboxes).
Default 1 vCPU / 1 GiB / 3 GiB disk; org max 4 vCPU / 8 GiB / 10 GiB (same src).

**API surface.** `daytona.create()`, `daytona.snapshot.create()`,
`sandbox.process.code_run()` (src: https://www.daytona.io/docs/en/sandboxes);
lifecycle `sandbox.start()`, `stop()`, `pause()` (VM only), `archive()`, `delete()`,
`recover()`, `fork(name=…)` (VM only); resume = `start()`
(src: https://www.daytona.io/docs/en/sandboxes.md). Agent tools: process/code exec,
filesystem, Git operations, snapshots; human tools: dashboard, web terminal, SSH, VNC;
system: webhooks, network limits, audit logs, MCP server (src: https://github.com/daytonaio/daytona).

**States and persistence.** 22 states (Started, Stopped, Paused, Archived, Forking, …).
Auto-stop default 15 min idle (0 disables); auto-archive default 7 days (max 30); auto-delete
off by default (0 = delete on stop = ephemeral); VM auto-pause 60 min. Stop keeps the
filesystem, loses memory; archive moves the stopped filesystem to object storage
(containers only); pause keeps memory + filesystem (VM/Windows only); fork copies memory +
filesystem into a fork tree (src: https://www.daytona.io/docs/en/sandboxes.md).

**Self-host / license.** Open-source repo archived; last open release v0.190.0; LICENSE
not shown by GitHub API (null); development is now private
(src: https://github.com/daytonaio/daytona). BYOC listed under Enterprise
(src: https://www.daytona.io/pricing).

**Pricing.** $0.0504/vCPU-h, $0.0162/GiB-h, storage $0.000108/GiB-h (first 5 GiB free);
$200 free compute; per-second billing (src: https://www.daytona.io/pricing).

### 3. Modal Sandboxes

**Isolation.** gVisor runtime by default (required for GPU); optional `runtime="vm"` with
its own kernel for Docker, FUSE, nested cgroups (src: https://modal.com/docs/guide/sandboxes).

**API surface** (`modal.Sandbox`): `create(…, timeout=300, idle_timeout, block_network,
pty=False, encrypted_ports, h2_ports, unencrypted_ports, outbound_cidr_allowlist,
inbound_cidr_allowlist)`, `from_id`, `from_name`, `list`, `exec(*args, pty=False, text,
workdir, env, secrets, timeout)` → `ContainerProcess`, `stdin/stdout/stderr`, `wait`,
`wait_until_ready`, `poll`, `terminate`, `detach`, `tunnels()`, `create_connect_token`,
`snapshot_filesystem`, `snapshot_directory`, `mount_image`, `unmount_image`,
`reload_volumes`, `set_tags`, `logs.tail`; `sandbox.filesystem.{list_files,
make_directory, remove, read_text, read_bytes, write_text, write_bytes, copy_from_local,
copy_to_local, stat, watch}` (src: https://modal.com/docs/reference/modal.Sandbox).
Output streams are iterable line-by-line; stdin is a `StreamWriter` with `write`,
`write_eof`, `drain`; output readable for 10 min after exit
(src: https://modal.com/docs/guide/sandbox-spawn).

**Ports.** Tunnels: encrypted (TLS terminated, random `*.modal.host` URL) or unencrypted
raw TCP; URLs are random but public; no extra charge (src: https://modal.com/docs/guide/tunnels).

**Persistence.** Default lifetime 5 min, max 24 h; `idle_timeout` counts exec, stdin and
open tunnel connections as activity (src: https://modal.com/docs/guide/sandboxes).
Filesystem snapshots → Image (default TTL 30 days); directory snapshots; experimental
memory snapshots (`_experimental_enable_snapshot=True`, `sb._experimental_snapshot()`,
`Sandbox._experimental_from_snapshot`), expire after 7 days, terminate the sandbox,
close TCP connections, cannot be taken during an exec
(src: https://modal.com/docs/guide/sandbox-snapshots).

**Self-host.** None (hosted only). **Pricing.** Sandbox CPU $0.00003942/physical core-s
(= 2 vCPU), memory $0.00000667/GiB-s (≈3× Functions rates, my arithmetic); Starter $30/mo
credits, Team $100/mo (src: https://modal.com/pricing).

### 4. Runloop

**Architecture.** Devboxes are VMs ("virtual machine technology to provide isolation");
first command runs within a few seconds; blueprints = team-shared images; network
policies, Agent Gateways (LLM credentials not exposed to the devbox), MCP Hub
(src: https://docs.runloop.ai/docs/devboxes/overview).

**API surface.** `devbox.cmd.exec`; `exec` / `exec_async` (returns handle with `kill()`),
streaming via `output` or `stdout`/`stderr` callbacks, stateful shells via `shell_name`;
transport not documented (src: https://docs.runloop.ai/docs/devboxes/execute-commands).
Suspend/resume: `devbox.suspend()`, `await_suspended()`, `resume()`, `await_running()`
(src: https://docs.runloop.ai/docs/devboxes/lifecycle). Files, tunnels, SSH, snapshots,
TTL/idle policies have dedicated pages: /docs/devboxes/files, /tunnels, /ssh, /snapshots,
/start-stop (src: https://docs.runloop.ai/llms.txt).

**Persistence.** States Provisioning → Initializing → Running → Suspending/Suspended →
Resuming → Shutdown/Failure; suspend keeps disk only, not memory; ID and SSH keys
preserved; processes must be restarted (src: https://docs.runloop.ai/docs/devboxes/lifecycle).

**Pricing / self-host.** $0.108/CPU-h, $0.0252/GB-h, storage $0.00034236/GB-h; Basic free +
usage, Pro $250/mo (suspend/resume is a Pro feature), Enterprise adds Deploy to VPC; $50
trial credits (src: https://www.runloop.ai/pricing). SDK MIT (GitHub runloopai/api-client-python).

### 5. Morph Cloud (Infinibranch)

**Concept.** VM snapshots that can be started as instances, branched into N copies, and
re-snapshotted; vendor claims snapshot/branch/restore of whole environments in <250 ms
(src: https://cloud.morph.so/developers, vendor marketing). Docs cover instances
start/stop, pause/resume, branching, SSH, remote commands, upload/download, FUSE mounts,
exposing HTTP services, plus "Devboxes" for humans and CLI agents with tmux automation
(src: https://cloud.morph.so/docs/documentation/overview).

**API surface** (Python SDK): `MorphCloudClient()`, `client.snapshots.create(image_id,
vcpus, memory, disk_size, ttl_seconds)`, `snapshot.exec(...)` (returns a new cached
snapshot), `snapshot.upload(...)`, `snapshot.set_ttl`, `client.instances.start(snapshot_id)`,
`instance.wait_until_ready()`, `instance.ssh().run/copy_to/copy_from/tunnel`,
`instance.expose_http_service(name, port)`, `instance.stop()`; CLI: `instance exec`,
`pause`, `resume`, `branch`, `snapshot` (src: https://github.com/morph-labs/morph-python-sdk).

**Pricing.** Metered in MCU: 1 MCU = 1 vCPU-h + 4 GB RAM-h + 16 GB disk-h or 5 TB snapshot-h;
example rate $0.05/MCU; Developer tier 300 free MCU (src: https://cloud.morph.so/web/subscribe,
https://cloud.morph.so/docs/documentation/setup/plans). Hosted only; isolation tech not
stated in docs fetched.

### 6. Vercel Sandbox

**Isolation.** Firecracker microVM per sandbox, own filesystem and network; can run
privileged workloads (Docker, VPN, FUSE); default image `vercel/sandbox/universal`
includes Node LTS, Python 3.14 and coding agents; custom OCI images via Vercel Container
Registry; "multi-agent isolation" via a Linux user per agent
(src: https://vercel.com/docs/vercel-sandbox).

**API surface** (`@vercel/sandbox`): `Sandbox.create({source: git|tarball|snapshot,
resources:{vcpus}, ports (≤15), timeout, name, image, region, networkPolicy, env, tags,
persistent})`, `Sandbox.get({name})`, `Sandbox.getOrCreate({onCreate,onResume})`,
`Sandbox.list`, `sandbox.runCommand(cmd,args | {cmd,args,cwd,env,detached})` →
`Command` with `logs()` (async iterator of `{stream,data}`), `wait()`, `kill()`,
`output()`, `stdout()`, `writeStdin()`, `closeStdin()`; `mkDir`, `writeFiles`, `readFile`
(stream), `readFileToBuffer`; `domain(port)`; `extendTimeout`; `stop()`; `snapshot()`
(shuts the sandbox down); `update({...})`; `delete()`
(src: https://vercel.com/docs/sandbox/sdk-reference,
https://vercel.com/docs/sandbox/concepts/persistent-sandboxes).

**Persistence.** Persistent by default: on stop the filesystem is auto-snapshotted; any SDK
call on a stopped sandbox auto-resumes a new session from that snapshot (filesystem only;
`onResume` exists to restart services). Snapshots expire 30 days after last use (configurable,
`keepLastSnapshots`). Max session 45 min Hobby / 24 h Pro, reset on each resume
(src: https://vercel.com/docs/sandbox/concepts/persistent-sandboxes, https://vercel.com/docs/sandbox/pricing).

**Pricing.** Active-CPU billing: $0.128/CPU-h only while CPU is actually used; memory
$0.0212/GB-h provisioned; $0.60 per 1M creations; snapshots $0.08/GB-month; 10,000
concurrent on Pro; 2 GB RAM per vCPU, max 8 vCPU on Pro (src: https://vercel.com/docs/sandbox/pricing).
Notable for agents: CPU is not billed while the agent waits on the LLM
(src: https://vercel.com/docs/vercel-sandbox). SDK and CLI code is public on GitHub (github.com/vercel/sandbox, linked from the docs; license not checked);
the service is hosted only.

### 7. Cloudflare Sandboxes / Containers

**Architecture.** Two environments: Containers (your image, each instance a microVM with own
kernel and network, started and driven by a Durable Object in your Worker; inbound HTTP only
through your Worker) and Dynamic Workers (isolates). Requires Workers Paid
(src: https://developers.cloudflare.com/sandbox/). For coding agents the Worker holds the
credentials and attaches the API token per request so the sandbox never sees it
(src: https://developers.cloudflare.com/sandbox/coding-agents/).

**API surface.** Sandbox SDK 1.0 is "a different library that works with a container you
start from a Durable Object" (src: https://developers.cloudflare.com/sandbox/sdk/). 0.12 APIs
`getSandbox`, `exec`, `execStream`, `createSession`, `readFile`, `writeFile`, `startProcess`,
`exposePort`, `terminal`, `gitCheckout`, `createBackup`/`restoreBackup` map to Durable
Object container calls (`start()`, `exec()`, `setInactivityTimeout()`, `snapshotContainer()`,
`destroy()`) plus helper classes `Files`, `S3Mount`, `DirectoryBackup`
(src: https://developers.cloudflare.com/sandbox/sdk/migrate/,
https://developers.cloudflare.com/sandbox/reference/,
https://developers.cloudflare.com/sandbox/concepts/lifetime/). Output: streaming via
server-sent events; browser terminal over a WebSocket
(src: https://developers.cloudflare.com/sandbox/commands/).

**Persistence.** Instance stops shortly after the DO goes inactive unless
`setInactivityTimeout()` (≤6 h); disk and memory are lost on stop;
`snapshotContainer()` saves the writable root FS (not memory), expires 30 days
(src: https://developers.cloudflare.com/sandbox/concepts/lifetime/).

**Pricing.** $0.000020/vCPU-s (active only), $0.0000025/GiB-s, disk $0.00000007/GB-s; billed per
10 ms; instance types lite (1/16 vCPU) to standard-4 (4 vCPU / 12 GiB / 20 GB)
(src: https://developers.cloudflare.com/containers/platform/pricing/). Hosted only.

### 8. Fly Machines (and Sprites)

**Machines.** Firecracker VMs. REST under `/v1/apps/{app}/machines`: `POST` create,
`POST /{id}/start`, `/stop`, `/suspend`, `GET /{id}/wait?state=…`, `DELETE /{id}`, leases,
metadata (src: https://docs.fly.io/machines/api/machines-resource). Suspend snapshots CPU
registers, memory and file handles via Firecracker; resume in a few hundred ms vs ~2 s cold
start; ≤2 GB RAM, no swap; snapshots not guaranteed (deploys, host migrations force cold
start); `auto_stop_machines = "suspend"` in fly.toml (src: https://docs.fly.io/reference/suspend-resume).
Pricing: shared-cpu-1x 256 MB $2.19/mo, 1 GB $6.70/mo; stopped/suspended only pay rootfs
$0.15/GB-mo (src: https://docs.fly.io/about/pricing).

**Sprites.** Persistent "disposable" Linux computers, ~1–2 s creation, 100 GB, first-class
checkpoints (`sprite-env checkpoints create`, `sprite checkpoint restore v1` ≈ 1 s), stop
metering when idle; API at sprites.dev (src: https://fly.io/blog/code-and-let-live/).

### 9. Northflank (notable)

Vendor blog posts claim Kata Containers (Cloud Hypervisor/Firecracker) and gVisor per
workload, self-serve BYOC on AWS/GCP/Azure/Oracle/on-prem, $0.01667/vCPU-h and
$0.00833/GB-h, no session time limits (vendor marketing:
https://northflank.com/blog/best-byoc-sandbox-platforms, https://northflank.com/blog/ai-sandbox-pricing).
Not verified against official docs.

### 10. kubernetes-sigs/agent-sandbox (special attention)

**Status.** SIG Apps project, Apache-2.0, API group `agents.x-k8s.io/v1beta1` (core) and
`extensions.agents.x-k8s.io` (extensions), releases v1.0.3–v1.0.7 in Sep–Oct 2026
(src: https://github.com/kubernetes-sigs/agent-sandbox, GitHub releases API). Install
`sandbox-with-extensions.yaml` or `sandbox.yaml` + `extensions.yaml` (same src).
Isolation is delegated to a RuntimeClass (gVisor or Kata Containers); the project is a
"sandbox orchestrator" (same src; guides
https://agent-sandbox.sigs.k8s.io/docs/use-cases/gvisor-isolation/,
https://agent-sandbox.sigs.k8s.io/docs/use-cases/kata-containers-isolation/).

**CRDs** (from `api/v1beta1/sandbox_types.go` and `extensions/api/v1beta1/*_types.go` in the repo):
- **Sandbox** — a single stateful pod with stable identity. `spec.podTemplate` (PodSpec +
  metadata, required), `spec.volumeClaimTemplates` (PVCs, immutable), `spec.service`
  (create a headless Service), `spec.operatingMode`: `Running` (default) or `Suspended`
  (controller deletes the Pod but keeps the Sandbox object and its volumes — this is the
  pause/resume primitive: disk survives, memory does not), `spec.shutdownTime` (absolute
  expiry), `spec.shutdownPolicy` `Retain` (default) | `Delete`. Status: `serviceFQDN`,
  `service`, `conditions` (Ready, Suspended), `selector`, `podIPs`, `nodeName`.
- **SandboxTemplate** — shares the "SandboxBlueprint" (podTemplate, volumeClaimTemplates,
  service) plus `networkPolicy` (ingress/egress subset) with `networkPolicyManagement`
  `Managed` (default: ingress only from the Sandbox Router, egress to public internet only,
  RFC1918 and metadata server blocked) | `Unmanaged`; `envVarsInjectionPolicy`,
  `volumeClaimTemplatesPolicy` (what a claim may override). Pods from templates default
  `automountServiceAccountToken=false`.
- **SandboxClaim** — `warmPoolRef` (required), `lifecycle` (shutdownTime,
  `ttlSecondsAfterFinished`, shutdownPolicy), `additionalPodMetadata`, `env` (per
  container), `volumeClaimTemplates`. Status embeds the sandbox's name, podIPs, serviceFQDN.
  A claim adopts a ready Sandbox from the pool.
- **SandboxWarmPool** — `replicas`, `sandboxTemplateRef`, `updateStrategy`
  `Recreate` | `OnReplenish` (stale unclaimed sandboxes replaced only when deleted/claimed);
  status `replicas`, `readyReplicas`, `selector` (HPA/KEDA scale-to-zero examples exist:
  https://agent-sandbox.sigs.k8s.io/docs/sandbox/).
- Docs also list Shutdown Time, Snapshots, Status Conditions, volumes, FUSE CSI
  (src: https://agent-sandbox.sigs.k8s.io/docs/sandbox/). GKE-specific pod snapshots appear
  in the Python client (`gke_extensions/snapshots`) (repo tree).

**Runtime daemon `sandboxd`** (KEP-539.2 "runtime standardization"): runs inside the sandbox
pod; gRPC `:9090` `process.v1.ProcessService` with `Start` (server-streaming: InitEvent,
stdout/stderr events, ExitEvent), `Execute`, `WriteStdin`, `SendSignal`, `ResizeTTY`
(PTY supported); HTTP `:8080` REST `/v1/files`, `/v1/health`, `/v1/metadata` with raw-byte
payloads. Any runtime implementing these wire contracts is compatible. Caveat: the
current `sandbox-router` disables HTTP/2 upstream so it cannot carry the gRPC process
service (src: https://github.com/kubernetes-sigs/agent-sandbox/blob/main/packages/sandboxd/USER_GUIDE.md,
`packages/sandboxd/spec/process/v1/process.proto`).

**Python SDK** (`pip install k8s-agent-sandbox`): `SandboxClient(connection_config)`,
`create_sandbox(warmpool, namespace)`, `get_sandbox`, `list_active_sandboxes`,
`list_all_sandboxes`, `delete_sandbox(claim_name)`, `delete_all`; `sandbox.commands.run(cmd)`
(`.stdout`), `sandbox.files.write/read/read_to/list/exists/delete`, `sandbox.status()`,
`get_pod_ip()`, `get_service_fqdn()`, `terminate()`
(src: repo `clients/python/agentic-sandbox-client/k8s_agent_sandbox/*.py`,
https://agent-sandbox.sigs.k8s.io/docs/getting_started/python-sdk-quickstart/).
Connection modes: `SandboxLocalTunnelConnectionConfig` (default; `kubectl port-forward` to
the router), `SandboxGatewayConnectionConfig` (public Gateway), `SandboxDirectConnectionConfig`,
`SandboxInClusterConnectionConfig` (same quickstart). Go SDK: `sandbox.NewClient`,
`CreateSandbox`, `sb.Run`, `DeleteAll`; a TypeScript client also exists
(src: https://agent-sandbox.sigs.k8s.io/, repo tree).

Goals still listed as "desired": deep hibernation, automatic resume on network connection
(src: https://github.com/kubernetes-sigs/agent-sandbox).

### 11. Docker Sandboxes (`sbx`) and Docker MCP Gateway

**Sandboxes.** Each sandbox is a microVM (hypervisor not named) with its own Docker daemon
and image cache. A host workspace is mounted via filesystem passthrough at the same
absolute path, changes visible instantly both ways; or "clone mode" mounts the repo
read-only at `/run/sandbox/source` and the agent works in a private clone. All outbound TCP
goes through a host proxy enforcing network policy; credentials are injected by the proxy
(agent sees a sentinel value, real key never enters the VM). State persists across
stop/start until `sbx rm` (src: https://docs.docker.com/ai/sandboxes/architecture/).
Agents supported: Claude Code, Codex, Copilot, Cursor, Devin, Docker Agent, Droid, Gemini,
Kiro, OpenCode, Shell (src: https://docs.docker.com/ai/sandboxes/agents). Local compute and
CLI free (incl. commercial); cloud sandboxes pay-as-you-go; REST API + TypeScript SDK for
cloud sandboxes (create, run commands, transfer files, images, snapshots, volumes,
secrets); SSH integrations for VS Code/Cursor
(src: https://docs.docker.com/ai/sandboxes/, https://docs.docker.com/ai/sandboxes-api/).
Older `docker sandbox run claude` naming is superseded by `sbx` (inferred from docs using `sbx`).

**MCP Gateway.** Single MCP endpoint proxying to MCP servers each run in an isolated
container started on demand, with credential injection, `--profile` selection,
logging/call tracing (src: https://docs.docker.com/ai/mcp-catalog-and-toolkit/mcp-gateway/).
Repo docker/mcp-gateway is MIT (GitHub API).

### 12. container-use (Dagger)

MCP server (`container-use stdio`) giving each agent a fresh container on its own git
branch; Apache-2.0; "experimental" (src: https://github.com/dagger/container-use). Latest
release v0.4.2 (2025-08-19), last push 2026-09-21 (GitHub API). MCP tools:
`environment_create`, `environment_open`, `environment_list`, `environment_config`,
`environment_run_cmd`, `environment_add_service`, `environment_file_read/write/edit/delete/list`,
`environment_checkpoint`, `environment_diff`, `environment_log`, `environment_source`,
`environment_update_metadata`, `environment_id` (src: repo `mcpserver/tools.go`). CLI:
`list`, `watch`, `log`, `diff`, `terminal`, `checkout`, `merge` (keep agent commits),
`apply` (stage changes), `delete`, `config` (src: https://container-use.com/environment-workflow).
Relevance: same "branch per agent" idea as LADO's worktrees, but the agent's tools are
replaced by MCP tools, so the agent CLI itself stays on the host.

### 13. Dev Containers spec and DevPod

**Spec.** `devcontainer.json` (image / Dockerfile / Compose), Features, lifecycle hooks
`onCreateCommand` → `updateContentCommand` → `postCreateCommand`, then `postStartCommand`,
`postAttachCommand`; `waitFor`; `workspaceMount`/`workspaceFolder`; `remoteUser`;
reference implementation devcontainers/cli (`devcontainer exec`)
(src: https://containers.dev/implementors/spec/). Spec CC-BY-4.0, CLI MIT (GitHub API).
Ona environments are VMs built from the Dev Container config
(src: https://www.ona.com/docs/ona/runners/overview), so the spec is the de-facto
portable environment format.

**DevPod providers.** A provider is a CLI described by `provider.yaml` with `exec`,
`options` (passed as env vars), `binaries`, `agent`. Exec commands: `command` (required;
DevPod injects its agent and tunnels over the command's stdio, e.g.
`sh -c "${COMMAND}"`), optional `init`, `create`/`delete`/`start`/`stop` (machine
providers), `status` printing Running|Busy|Stopped|NotFound. The injected agent handles
inactivity auto-shutdown and git/docker credential injection
(src: https://devpod.sh/docs/developing-providers/quickstart). Providers exist for local
Docker, Kubernetes, SSH and cloud VMs (src: https://pkg.go.dev/github.com/skevetter/devpod@v0.11.2).
MPL-2.0; upstream stale since 2025, fork skevetter/devpod active (GitHub API).
Relevance: the "provider = small CLI with create/start/stop/status + a stdio command
channel" pattern is a cheap, cloud-agnostic plug-in interface worth copying in spirit.

### 14. Coder (workspaces, Tasks, AgentAPI, AI Gateway) — special attention

**Workspaces.** `coderd` control plane (Postgres, API, dashboard, proxies), `provisionerd`
running Terraform (only provider), workspaces = any Terraform resources (VMs, k8s pods),
a workspace agent inside providing SSH, port-forwarding, liveness, startup scripts
(src: https://coder.com/docs/admin/infrastructure/architecture). Networking built on
Tailscale's open source: direct WireGuard over UDP with STUN, else DERP relay (built into
the control plane or custom) (src: https://coder.com/docs/admin/networking).
coder/coder is AGPL-3.0 (GitHub API).

**Tasks → Coder Agents.** Tasks are deprecated: 12-month ESR for Premium from June 2, 2026,
removed starting v2.37 (Sept 1, 2026) (secondary mirror of docs:
https://git.dragonfruit.dev/mirror/coder/src/branch/main/docs/ai-coder/tasks.md; confirmed by
https://coder.com/changelog/coder-2-37.md). Agent compatibility for Tasks resume: full for
Claude Code and Codex, partial for Copilot and OpenCode; AgentAPI's state file streams chat
to the Tasks UI (src: https://coder.com/docs/@v2.36.3/ai-coder/agent-compatibility).
Coder Agents: a chat interface + API; self-hosted standalone Go agent (not a wrapper around
Claude Code/Codex); loop runs in the control plane and executes tool calls in a workspace
over the existing workspace connection; workspaces provisioned on demand from templates
(src: https://coder.com/docs/ai-coder/tasks — page now describes Coder Agents). Community
edition available; enterprise scale needs Coder AI Premium (src: https://coder.com/changelog/coder-2-37.md).

**AI Gateway (ex-AI Bridge).** Proxy between agents/IDEs and OpenAI/Anthropic; records
prompts, token usage, tool invocations; users authenticate with Coder tokens so no
per-user provider keys; admin-approved MCP servers/tools; Premium license
(src: https://coder.com/docs/ai-coder/ai-gateway). Renamed from AI Bridge; old names kept as
deprecated aliases (src: https://coder.com/docs/ai-coder/ai-gateway/rebranding-migration).
"Agent Boundaries" renamed "Agent Firewall" (secondary mirror commit, see search above).

**AgentAPI — how it wraps any agent CLI** (MIT, archived; v0.12.2 OpenAPI):
- Run as `agentapi server --type=<claude|codex|opencode|…> -- <agent command>`; default
  port 3284; localhost-only host/CORS by default (src: https://github.com/coder/agentapi).
- **Terminal emulation:** starts the agent in an in-memory PTY via `xpty` (vt10x emulator,
  `TERM=vt100`), default 80 columns × 1000 rows (`--term-width`, `--term-height`)
  (src: repo `lib/termexec/termexec.go`, `cmd/server/server.go`).
- **Endpoints:** `GET /messages` (id, role user|agent, content, time), `POST /message`
  `{content, type: "user"|"raw"}` (`user` requires status stable and is recorded; `raw`
  writes keystrokes, e.g. escape sequences), `GET /status` (`status` running|stable,
  `agent_type`, `transport` pty|acp), `GET /events` SSE with `message_update`,
  `status_change`, `agent_error` (replays current state on connect), `POST /upload`
  (multipart file into the workspace); plus `/openapi.json`, `/docs`, `/chat` UI
  (src: https://raw.githubusercontent.com/coder/agentapi/main/openapi.json, https://github.com/coder/agentapi).
- **Status detection = screen stability:** a snapshot of the emulated screen every 25 ms;
  "stable" when the screen has not changed for 2 s (ring buffer of
  ceil(2000/25)+1 snapshots all equal) (src: repo `lib/httpapi/server.go`,
  `lib/screentracker/pty_conversation.go`).
- **Sending a message:** snapshot screen, type the text (bracketed paste), wait up to 2 s for
  echo + 1 s stability (non-fatal), then send `\r` and wait up to 15 s for the screen to
  change, re-sending `\r` every 3 s; 200 means "processing started" (same file).
- **Message parsing:** the agent's reply = diff of the screen against the snapshot taken
  before the user message; echoed input and TUI chrome (input box, `>` / `------`
  markers) stripped with per-agent rules (`msgfmt`: Claude, Codex, OpenCode, Amp, …);
  readiness for the initial prompt = input box detected; this breaks when an agent changes
  its TUI (src: https://github.com/coder/agentapi, repo `lib/msgfmt/agent_readiness.go`).
- **State persistence:** `--state-file` with `--load-state`/`--save-state` (not in ACP mode)
  (src: repo `cmd/server/server.go`). **Experimental ACP transport**
  (`--experimental-acp`) talks Agent Client Protocol instead of scraping a PTY (same src).
- Lesson for LADO: AgentAPI is exactly the "read the screen" approach LADO's design
  principles reject; even its authors moved to ACP and then abandoned it.

### 15. Ona (ex-Gitpod)

Management plane hosted by Ona (auth, org settings, guardrails); runners execute
environments: Ona Cloud (Frankfurt, N. Virginia), AWS runner (ECS services in your VPC,
environments on EC2), GCP runner (Compute Engine) — the latter two Enterprise only. Source
code and SCM credentials stay on the runner. Environments are isolated VMs from the Dev
Container config; runners inject secrets, run prebuilds, tasks, services; the "Codex Agent"
runs tasks in the same environments (src: https://www.ona.com/docs/ona/runners/overview).
Acquisition by OpenAI announced June 2026 (secondary, see §0).

---

### 16. Comparison at a glance

| Provider | Isolation | Startup | Suspend keeps memory? | Snapshot / branch | Self-host | Price (compute) |
|---|---|---|---|---|---|---|
| E2B | Firecracker | snapshot restore, resume ~1 s | yes (pause) | pause snapshots; templates | Apache-2.0 Embed (1 node); BYOC Ent. | $0.050/vCPU-h + $0.016/GiB-h |
| Daytona | container default; VM option | "<90 ms" (vendor) | VM only | snapshots, archive; fork (VM) | OSS archived; BYOC Ent. | $0.0504/vCPU-h + $0.0162/GiB-h |
| Modal | gVisor; VM option | n/a in docs | experimental memory snapshot (7 d) | FS/dir snapshots | no | ~$0.071/vCPU-h + $0.024/GiB-h |
| Runloop | VM | few seconds | no (disk only) | disk snapshots, blueprints | VPC Ent. | $0.108/CPU-h + $0.0252/GB-h |
| Morph | VM (not stated) | <250 ms (vendor) | pause/resume | Infinibranch branch N | no | MCU ≈ $0.05 |
| Vercel | Firecracker | "milliseconds" | no (FS auto-snapshot) | snapshots | no (SDK public) | $0.128/active CPU-h + $0.0212/GB-h |
| Cloudflare | microVM via DO | n/a | no; disk lost unless snapshot | root-FS snapshot | no | $0.072/active vCPU-h + $0.009/GiB-h |
| Fly Machines | Firecracker | cold ~2 s, resume 100s of ms | yes (≤2 GB) | — | no | from $2.19/mo |
| agent-sandbox | gVisor/Kata via RuntimeClass | warm pool | no (Suspended = pod deleted, PVC kept) | GKE pod snapshots ext. | Apache-2.0, any k8s | your cluster |
| Docker sbx | microVM | n/a | stop/start keeps disk | snapshots (cloud API) | local free | cloud PAYG |
| Coder | whatever Terraform makes | template-dependent | — | — | AGPL-3.0 | self-hosted |

(Hourly figures for E2B, Modal and Cloudflare are my conversions of the per-second rates
cited above.)

### 17. Takeaways for LADO

1. **The cloud-agnostic target is "a Linux box with a PTY, files and a port"** — every
   provider exposes the same five verbs (create, exec/PTY, files, expose port, stop/delete)
   with different names. A thin LADO `Runtime` interface over these is feasible; DevPod's
   `provider.yaml` (create/start/stop/status + a stdio `command` channel) is the cheapest
   generic plug-in model, and agent-sandbox's `sandboxd` wire contract (gRPC process stream
   with PTY resize + REST files) is the emerging open standard for Kubernetes.
2. **Self-hosted k8s path = agent-sandbox**: Sandbox per agent (PVC holds the git worktree,
   `operatingMode: Suspended` for idle agents, `shutdownTime` for cleanup), SandboxWarmPool
   for fast starts, gVisor/Kata RuntimeClass, managed NetworkPolicy defaults. Memory is not
   kept on suspend, so the agent CLI must be resumable from disk (Claude Code / Codex
   session resume).
3. **Memory-preserving suspend** (agent keeps running context, tmux session survives) exists
   on E2B, Fly, Daytona VMs, Morph, Modal (experimental); elsewhere only the filesystem
   survives. LADO should not rely on memory persistence.
4. **Don't wrap TUIs by screen scraping.** AgentAPI shows the cost (25 ms polling, 2 s
   stability, per-agent chrome regexes, fragile on TUI changes) and is now archived. LADO's
   hooks + MCP approach carries over to remote boxes unchanged as long as the `lado mcp`
   / hook callbacks can reach LADO (reverse tunnel or an in-sandbox relay).
5. **Credential brokering is table stakes**: Docker sbx (proxy swaps a sentinel key),
   Cloudflare (Worker attaches the token), Runloop Agent Gateways, Coder AI Gateway — all keep
   provider API keys out of the sandbox. A hosted LADO should do the same.
6. **Terminal streaming** for the UI: E2B PTY handles with reconnect, Modal `pty=True`,
   Cloudflare WebSocket terminal, sandboxd `Start` stream + `ResizeTTY`, Coder reconnecting
   terminals over its tailnet — a WebSocket PTY bridge in LADO's server is the common
   denominator.

---

# Part 4. Orchestrators and multi-agent tools (detailed evidence)


Research notes for LADO's remote-execution design. Every claim carries a source URL. "Unverified"
marks claims that rest only on third-party aggregators or that the sources contradict.
Claims I checked against source code are marked "(code)".

---

### 0. The landscape at a glance

| Tool | Where the agent runs | Code in / out | Human watches via | Isolation | Multi-CLI | Self-host | Status |
|---|---|---|---|---|---|---|---|
| OpenHands (SDK + agent-server) | agent-server in local process / Docker / remote runtime API / k8s pod (agent-sandbox) / Apptainer / OpenHands Cloud | git clone inside sandbox; file upload/download API; git_diff API | REST + WebSocket event stream; web GUI | Docker, gVisor/Kata via k8s runtimeClass | Own agent; plus `ACPAgent` drives Claude Code / Codex / Gemini via ACP | Yes (MIT SDK); Enterprise k8s Helm is licensed | Active |
| Sculptor (Imbue) | Docker container per agent (local) | clone into container; Pairing Mode two-way sync to local checkout | Desktop app | Containers (devcontainer) | Claude Code; Codex added later | No (proprietary, free) | Active (beta) |
| Vibe Kanban (Bloop) | Local processes in git worktrees; server can run on remote host | worktree + branch, PR | Web UI (Rust backend) | Worktree only | 9 CLIs behind one Rust trait | Apache-2.0 | Company shut down Apr 2026; community-maintained |
| Conductor (Melty) | Local Mac worktrees; Conductor Cloud microVMs | worktree / cloud repo | Mac app; API | microVM (cloud) | Claude Code, Codex, Cursor, OpenCode | No | Active, Cloud launched Jul 2026 |
| Terragon | Cloud sandbox per task | branch, checkpoint push to GitHub, PR; `terry` CLI pulls locally | Web + WebSocket broadcast | Sandbox containers | Claude Code, Codex, Amp, Gemini | Apache-2.0 snapshot | Shut down Jan 2026 |
| Omnara | Pivoted: own agent loop on stateless workers; tools run on `omnarad` machines or 9 sandbox providers | — | API event stream, web/mobile | Pluggable sandboxes | No longer wraps CLIs | Apache-2.0, docker compose | Active |
| Happy | User's machine; wraps CLI | stays local | E2E-encrypted relay to mobile/web | none | Claude Code, Codex | MIT, server Dockerfile | Active |
| Claude Squad / Uzi | Local tmux + worktrees | worktree | tmux TUI | worktree | Any CLI via command/profile | AGPL / MIT | Active / early |
| Crystal → Nimbalyst | Local worktrees | worktree | Desktop, iOS | worktree | Claude Code, Codex | Crystal deprecated Feb 2026 | — |
| Superset | Local worktrees; remote workspaces on another machine | worktree | Desktop app, CLI, SDK, MCP | worktree | Any CLI | ELv2 (source-available) | Active |
| Catnip (W&B) | Container (Docker / Apple container / Codespaces) | worktrees inside container | Web + mobile | container | Claude Code | — | Repo now 404 |
| Kilo Cloud Agents | Per-user Linux container (Kilo infra) | clone, branch, commit+push after every message | Web, mobile, `kilo cloud --stream` JSONL | Container; egress proxy swaps capability tokens | Kilo only | No | Active, beta |
| Open-Inspect (ColeMurray/background-agents) | Pluggable sandbox: Modal/Daytona/E2B/OpenComputer/Vercel | clone up to 10 repos, PR per repo, FS snapshots | Web, Slack, GitHub, Linear bots | Provider sandbox | OpenCode or Claude Agent SDK harness | MIT, Cloudflare Workers control plane | Active |
| Tembo | Cloud sandboxes; VPC for Enterprise | PRs | Integrations (Sentry, Linear, GitHub) | — | Claude Code, Codex, Cursor… | Enterprise VPC | Active |

---

### 1. OpenHands

#### 1.1 V0 runtime (legacy)

- Client-server: the backend sends *actions* to an **action execution server** inside the sandbox and gets
  *observations* back over a REST API; at startup the server creates an `ActionExecutor` with a bash shell
  and requested plugins ([runtime architecture](https://docs.openhands.dev/usage/architecture/runtime)).
- Implementations named in the docs: `impl/docker/docker_runtime.py`, `impl/local/local_runtime.py`,
  `impl/remote/remote_runtime.py` ([same page](https://docs.openhands.dev/usage/architecture/runtime)).
- Image building: user supplies a base image; OpenHands builds an "OH runtime image" on top with three
  tags (versioned, lock = dependency hash, source = source hash) and reuses the most specific existing tag
  ([same page](https://docs.openhands.dev/usage/architecture/runtime)).
- Third-party runtimes (E2B, Modal, Runloop, Daytona) are installed via a `third_party_runtimes` extra and
  supported by their vendors, not the OpenHands team ([V0 runtimes overview](https://docs.openhands.dev/openhands/usage/v0/runtimes/V0_overview));
  Daytona is configured with `DAYTONA_API_KEY` ([Daytona runtime](https://docs.all-hands.dev/modules/usage/runtimes/daytona)),
  Modal with a token id/secret ([Modal runtime](https://docs.openhands.dev/openhands/usage/v0/runtimes/V0_modal)).
- I found **no** official `KubernetesRuntime` class in V0 docs; K8s arrives in V1 as a workspace type
  (below) and in the Enterprise Helm install.

#### 1.2 V1: Software Agent SDK + agent-server

- Repo `OpenHands/software-agent-sdk`, MIT, four Python packages: `openhands-sdk`, `openhands-tools`,
  `openhands-agent-server`, `openhands-workspace`, plus a TypeScript client generated from the server's
  OpenAPI contract ([repo](https://github.com/OpenHands/software-agent-sdk)).
- V1 "sandboxes" in the product: **Docker** (default, runs `ghcr.io/openhands/agent-server` image),
  **Process** (agent-server as a local process, no isolation), **Remote** (managed deployments)
  ([sandboxes overview](https://docs.openhands.dev/openhands/usage/sandboxes/overview.md),
  [custom sandbox guide](https://docs.openhands.dev/openhands/usage/advanced/custom-sandbox-guide)).
  Some deployments still select via legacy `RUNTIME=docker|process|remote` (same overview).
- **Workspace abstraction** ([workspace arch doc](https://docs.openhands.dev/sdk/arch/workspace)):
  - `BaseWorkspace` abstract methods (code: [base.py](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-sdk/openhands/sdk/workspace/base.py)):
    `execute_command`, `file_upload`, `file_download`, `git_changes`, `git_diff`; optional `pause()` /
    `resume()`; context manager `__enter__/__exit__`; cost tracking (`register_cost`).
  - `LocalWorkspace`: subprocess + `shutil`, no isolation.
  - `RemoteWorkspace`: HTTP to an agent-server (`POST /command`, `POST /file/upload` multipart,
    `GET /file/download` streamed).
  - In `openhands-workspace` (code: [package tree](https://github.com/OpenHands/software-agent-sdk/tree/main/openhands-workspace/openhands/workspace)):
    `DockerWorkspace` (+ `DockerDevWorkspace`), `APIRemoteWorkspace` (talks to the OpenHands **Runtime API**,
    `runtime_api_url` + `X-API-Key`, fields `runtime_class`, `keep_alive`, env forwarding),
    `OpenHandsCloudWorkspace` (Cloud API), `ApptainerWorkspace` (HPC), and
    **`AgentSandboxWorkspace`** — a pod managed by the `kubernetes-sigs/agent-sandbox` controller, claimed
    from a `SandboxWarmPool` (sub-second claim), native pause/resume by flipping `spec.operatingMode`
    Suspended/Running with a persistent volume, gVisor/Kata via `runtimeClass`, connects through
    port-forward (code: [agent_sandbox/workspace.py](https://github.com/OpenHands/software-agent-sdk/blob/main/openhands-workspace/openhands/workspace/agent_sandbox/workspace.py)).
  - The workspace type picks `LocalConversation` vs `RemoteConversation`
    ([workspace arch doc](https://docs.openhands.dev/sdk/arch/workspace)).
- **agent-server** ([agent-server doc](https://docs.openhands.dev/sdk/arch/agent-server)): HTTP + WebSocket;
  `/health`, `/ready`, `/server_info`, `/docs` (OpenAPI), `/api/*` for conversations, workspace, files,
  commands, settings; auth off by default, enabled with `OH_SESSION_API_KEYS_0..N` → header
  `X-Session-API-Key`; `OH_SECRET_KEY` encrypts stored LLM keys; CORS via `OH_ALLOW_CORS_ORIGINS_*`;
  data under `workspace/` (bash events, conversations, project). Start with
  `python -m openhands.agent_server --host --port`.
- **Running other CLIs**: `ACPAgent(acp_command=[...])` spawns an ACP server subprocess and talks JSON-RPC;
  documented commands `npx -y @agentclientprotocol/claude-agent-acp`, `npx -y @zed-industries/codex-acp`,
  `npx -y @google/gemini-cli --acp`; reuses an existing CLI login on the machine, which beats an API key
  ([ACP agent guide](https://docs.openhands.dev/sdk/guides/agent-acp),
  [Agent Canvas ACP agents](https://docs.openhands.dev/openhands/usage/agent-canvas/acp-agents),
  [blog](https://openhands.dev/blog/use-any-coding-agent-in-openhands-with-acp)). The original issue
  accepted "throw errors when user tries to set" unsupported SDK features
  ([issue #590](https://github.com/OpenHands/software-agent-sdk/issues/590)) — same "no silent drops" stance as LADO.

#### 1.3 Cloud, self-hosted, pricing

- Pricing ([pricing](https://openhands.dev/pricing)): Local OSS free (BYOK); Individual SaaS free (BYOK
  or OpenHands models at cost, 10 conversations/day); Enterprise custom — SaaS or self-hosted in your VPC,
  SAML/SSO, RBAC, unlimited users. A hub page shows Enterprise at $40/user/month (unverified;
  [hub pricing](https://hub.openhands.dev/pricing)).
- Self-hosted Enterprise on Kubernetes: Helm chart via the **Replicated** registry, license required;
  needs default storage class, ingress controller, Helm v4+; sandboxes in a separate namespace
  `openhands-runtimes`; a **runtime-api** deployment provisions/scales/cleans sandboxes; available to
  select customers on request ([k8s install](https://docs.openhands.dev/enterprise/k8s-install/installation)).
  The chart is source-available with a 30-day trial under a Polyform Free Trial license
  ([blog](https://www.openhands.dev/blog/openhands-cloud-self-hosted-secure-convenient-deployment-of-ai-software-development-agents)).

**Takeaway for LADO**: the cleanest public precedent for "one in-sandbox server + many interchangeable
workspace backends". The workspace interface is tiny (exec, upload, download, git diff, pause/resume).
Its k8s backend leans on `kubernetes-sigs/agent-sandbox` (warm pools, suspend) rather than raw pods.

---

### 2. Sculptor (Imbue)

- Each agent gets its own container with a cloned repo at a specific commit and a Sculptor-created branch;
  dependencies come from your devcontainer config; local repo untouched until you Pull
  ([containers doc](https://docs.imbue.com/features/containers) — 404 when re-fetched; content via search
  snippet; [blog on containers](https://imbue.com/blog/containers)).
- **Pairing Mode**: checks out the agent's branch locally, stashes your uncommitted changes, syncs files
  both ways between container and local dir, restores your branch when turned off
  ([pairing mode](https://docs.imbue.com/features/pairing-mode); [product page](https://imbue.com/sculptor)).
  The sync mechanism (mutagen or own) is not documented publicly.
- Prebuilt devcontainer image caching cuts agent setup from minutes to seconds (company-reported,
  [blog](https://imbue.com/blog/containers)).
- Agents: Claude Code; Codex added via OpenAI API key; sessions (plans, chats, tool calls, diffs) saved and
  reopenable; Mac (Apple Silicon) and Linux ([product page](https://imbue.com/sculptor)).
- Proprietary, free ([AlternativeTo](https://www.alternativeto.net/software/sculptor/about/)); team says
  goal is "for the whole thing to be open" ([HN](https://hn.svelte.dev/item/45427697)).
- Containers appear to run locally (Docker); no cloud runner documented.

---

### 3. Vibe Kanban (BloopAI)

- Apache-2.0; Rust crates + web app; each workspace gives an agent a branch, terminal, dev server; supports
  remote server deployment (systemctl/Docker) reached through Cloudflare Tunnel/ngrok, and opening
  projects in a local editor via VS Code Remote-SSH; a self-hostable "Vibe Kanban Cloud" (Docker); MCP
  server on `MCP_HOST/MCP_PORT` ([repo](https://github.com/BloopAI/vibe-kanban)).
- **Shutdown**: Bloop announced 2026-04-10 it was shutting down; remote services kept 30 days, then a
  fully local architecture; project continues as community-maintained open source
  ([shutdown page](https://vibekanban.com/shutdown); [Nimbalyst write-up](https://nimbalyst.com/blog/vibe-kanban-after-bloop-whats-next/)).
  Stated reason: mostly free users, no business model they liked (same).
- **Executor interface** (code: [executors/mod.rs](https://github.com/BloopAI/vibe-kanban/blob/main/crates/executors/src/executors/mod.rs)):
  `enum CodingAgent { ClaudeCode, Amp, Gemini, Codex, Opencode, CursorAgent, QwenCode, Copilot, Droid }`
  dispatched to trait `StandardCodingAgentExecutor`:
  - `spawn(current_dir, prompt, env) -> SpawnedChild`
  - `spawn_follow_up(current_dir, prompt, session_id, reset_to_message_id, env)`
  - `spawn_review(...)` (defaults to follow-up or spawn)
  - `normalize_logs(raw_logs_store, worktree_path)` — converts each CLI's output into a common log/event model
  - `default_mcp_config_path()`, `get_availability_info()`, `get_setup_helper_action()` (login/install),
    `discover_options()` (stream of JSON patches), `apply_overrides()`, `use_approvals(service)`,
    `get_preset_options()`; capabilities `SessionFork`, `SetupHelper`, `ContextUsage`; error `AuthRequired`.
  - Agents are child processes via `command-group`, output normalized per agent
    ([DeepWiki](https://deepwiki.com/BloopAI/vibe-kanban)).

**Takeaway**: a well-factored adapter shape (spawn / follow-up with session id / normalize logs / MCP
config path / availability / approvals) — and a cautionary tale that the hosted business failed.

---

### 4. Conductor (Melty Labs)

- Local: Mac app, each agent in its own git worktree ([compare page](https://www.conductor.build/compare);
  [codepick guide](https://codepick.dev/en/guides/conductor-build-intro/)).
- **Conductor Cloud** launched 2026-07-30: isolated microVMs with repos and dependencies pre-installed,
  multiplayer (share workspace link, prompt together), an API to create workspaces, send prompts and read
  transcripts ([release note](https://releases.sh/release/rel_tvDCOCilKUe_ap-pKaWNP-conductor-cloud-workspaces-launch-api-for-programmatic-control);
  [runtimewire](https://runtimewire.com/ja/article/conductor-launches-multiplayer-cloud-workspaces-coding-agents)).
  A review says paid workspaces run in Vercel sandboxes (8 vCPU/16 GB) — conflicts with "microVM"
  only if Vercel isn't microVM-based; unverified ([vibecoding review](https://vibecoding.app/blog/conductor-review)).
- Bring your own Claude/OpenAI/Cursor subscription or keys; Pro ~$50/month reported (unverified, same review).
- $22M Series A reported (unverified, [aiagentstore](https://aiagentstore.ai/ai-agent/conductor-melty-labs)).
- Not self-hostable; no k8s story.

---

### 5. Terragon (terragon-labs)

- Shut down; open-source snapshot `terragon-oss` dated 2026-01-16, Apache-2.0, "as-is"
  ([repo](https://github.com/terragon-labs/terragon-oss)).
- Each task in an isolated sandbox container with its own repo copy and branch; work checkpointed and
  pushed to GitHub, PRs auto-created; GitHub App auth; `terry` CLI for local handoff/takeover plus an MCP
  server; agents Claude Code, Codex, Amp, Gemini; users could power agents with **existing Claude or
  ChatGPT subscriptions** or API keys (same repo).
- Components: Next app (`apps/www`), `apps/broadcast` WebSocket service, Postgres, Redis, Cloudflare R2,
  Stripe, Slack app; sandbox provider is a pluggable credential (E2B/Daytona not named on the README)
  (same repo).
- Timing: the shutdown snapshot (Jan 16) coincides with Anthropic's server-side block of subscription
  OAuth outside Claude Code (Jan 9) ([falcao.org timeline](https://falcao.org/posts/anthropic-claude-access-crackdown-ecosystem-fallout/)) —
  correlation only, no stated cause found.

---

### 6. Remote-control / mobile layers

#### Omnara
- Launched as "run Claude Code and Codex from anywhere" (YC S25) ([Launch HN mirror](https://mewayz.com/cs/blog/launch-hn-omnara-yc-s25-run-claude-code-and-codex-from-anywhere)).
- **Pivoted** (per current README): its own agent loop "works with any model"; API (launch agents, send
  input, stream events, approvals); Postgres event log so any stateless worker resumes after a crash;
  machines run `omnarad`, which **connects out** (no inbound ports); sandboxes from a managed pool or 9
  providers (Arker, Blaxel, boxd, CreateOS, Daytona, Freestyle, Modal, Tenki, Unikraft); self-host with
  `docker compose --profile app`; Apache-2.0 ([repo](https://github.com/omnara-ai/omnara)).

#### Happy (slopus)
- `happy-cli` wraps Claude Code and Codex in your terminal; `happy-server` relays end-to-end encrypted
  sync; Expo app for iOS/Android/web; MIT; `Dockerfile.server` in repo ([repo](https://github.com/slopus/happy)).
  Server stores only ciphertext; keys from public-key signatures ([SourcePulse](https://www.sourcepulse.org/projects/12376471)).
  Fork "Happier" adds OpenCode ([App Store](https://apps.apple.com/gb/app/id6758554297)).

#### Anthropic's own Remote Control (first-party competitor to these)
- Session stays on your machine; local Claude Code makes **outbound HTTPS only**, registers with the
  Anthropic API and polls for work; web/mobile messages routed over a streaming connection; requires a
  claude.ai subscription, API keys not supported; server mode for many concurrent sessions per process
  ([Remote Control docs](https://code.claude.com/docs/en/remote-control)).
- A `setup-token` OAuth token "can't establish Remote Control sessions"
  ([auth docs](https://code.claude.com/docs/en/authentication)).

**Pattern**: everyone uses an *outbound* connection from the agent host to a relay/control plane
(Remote Control, `omnarad`, Happy server). That is the NAT-friendly shape LADO would need for agents in
someone's cluster or laptop reporting to a hosted UI.

---

### 7. Local worktree orchestrators (LADO's closest peers)

- **Claude Squad**: tmux session per agent + git worktree per session; TUI; Claude Code default, Codex,
  Gemini, Aider, OpenCode, Amp, any program via `-p` or config profiles; AGPL-3.0; no remote support
  ([repo](https://github.com/smtg-ai/claude-squad)).
- **Uzi**: tmux session + worktree per agent under `~/.local/share/uzi/worktrees/`; `uzi prompt --agents
  claude:3,codex:2`; per-agent dev-server port range; early (0.0.x), MIT per pkg.go.dev
  ([architecture](https://www.mintlify.com/devflowinc/uzi/concepts/architecture);
  [pkg.go.dev](https://pkg.go.dev/www.uzi.sh)).
- **Crystal → Nimbalyst**: Crystal deprecated, last release v0.3.5 on 2026-02-26 pointing to Nimbalyst
  ([repo](https://github.com/stravu/crystal)); Nimbalyst adds kanban, iOS app; reported MIT since
  2026-04-30 (unverified, [rywalker](https://rywalker.com/research/nimbalyst)).
- **Superset**: worktree per task, any CLI agent, diff viewer, scheduled automations, **remote access to
  workspaces hosted on another machine**, CLI + TypeScript SDK + MCP server
  ([docs](https://docs.superset.sh/)); YC P26 ([Launch HN](https://hn.svelte.dev/item/48236770));
  source-available under ELv2 per its own comparison pages
  ([superset vs openhands](https://superset.sh/compare/superset-vs-openhands)); Pro $20/seat reported (unverified).
- **Catnip (W&B)**: Go binary with embedded Vite SPA, runs in a container (Docker or Apple container SDK)
  so Claude Code can run with permission checks off; worktrees inside; usable in GitHub Codespaces;
  web + mobile ([README via search](https://raw.githubusercontent.com/wandb/catnip/main/README.md);
  [skillsllm](https://skillsllm.com/skill/catnip)). The repo URL now returns 404 (checked 2026-10-18) —
  likely removed/privated.
- **Container Use (Dagger)**: MCP server giving each agent a container + branch `container-use/<env>`;
  review with `git checkout` ([Dagger blog](https://dagger.io/blog/agent-container-use)). Interesting
  inversion: isolation is offered *to* the agent as MCP tools rather than imposed around it.

---

### 8. Hosted background-agent platforms

#### Kilo Cloud Agents
- One isolated Linux container per user (Node, git, gh, glab; apt installs); all of a user's chats share
  the container, each session its own worktree/dir; repo cloned, unique branch, startup commands, env
  vars injected; **after every message the agent commits and pushes** to the session branch; containers
  spin down when idle; sessions deleted after 7 days in beta but reachable via CLI
  ([cloud agent docs](https://kilo.ai/docs/code-with-ai/platforms/cloud-agent);
  [older doc](https://kilo.ai/docs/advanced-usage/cloud-agent)).
- Watch: web/mobile; `kilo cloud start --stream` prints events as JSONL; follow-ups queue while running
  (same docs). Vercel sandboxes are mentioned for GitHub repos (same).
- Pricing: per-second compute while awake, $0.60/h (Docker, Small), $1.20/h (Standard), separate from
  inference; $5 minimum balance; BYOK still pays compute (same).
- **Credentials**: real GitHub/Kilo tokens never enter the sandbox; it gets short-lived, container-bound,
  encrypted capability tokens; egress is intercepted (a Cloudflare feature), checked for issuance,
  allowed destination and container binding, then the real token is swapped in per request
  ([Kilo blog "keys"](https://blog.kilo.ai/p/keys)). Best-in-class pattern found in this survey.

#### Open-Inspect (ColeMurray/background-agents, inspired by Ramp Inspect)
- Control plane on Cloudflare Workers + one Durable Object per session (SQLite, WebSocket hub, event
  stream); D1 for encrypted repo-scoped secrets; **pluggable sandbox backend** with packages for Modal,
  Daytona, E2B, OpenComputer, Vercel; inside each sandbox a Supervisor + Bridge connect to a harness
  (OpenCode or Claude Agent SDK); Claude via API key or subscription, Codex via ChatGPT subscription;
  web, Slack, GitHub, Linear bots, cron/Sentry/webhook automations; up to 10 repos/session, PR per repo,
  filesystem snapshot after each prompt; single-tenant only; MIT
  ([repo](https://github.com/ColeMurray/background-agents)).
- Ramp Inspect itself: Modal Sandbox per session with full stack (Postgres, Redis, Temporal, RabbitMQ),
  OpenCode as the agent, snapshot-based fast start; >50% of merged PRs at Ramp
  ([Modal case study](https://modal.com/blog/how-ramp-built-a-full-context-background-coding-agent-on-modal);
  [ZenML summary](https://www.zenml.io/llmops-database/building-a-full-context-background-coding-agent-with-sandboxed-development-environments)).

#### Tembo
- Orchestration layer dispatching Claude Code, Codex, Cursor and others into isolated cloud environments,
  triggered by Sentry/Linear/GitHub; Enterprise in customer VPC; Free 10 credits/week, Pro $60/mo,
  Max $200/mo, credit ≈ $1 inference (mostly vendor/aggregator sources, unverified)
  ([Tembo blog](https://www.tembo.io/blog/top-coding-agent-tools); [PricingSaaS](https://pricingsaas.com/companies/tembo)).

#### Charlie (Charlie Labs)
- Hosted TypeScript-focused agent working through GitHub, Linear, Slack; "daemons" that work
  continuously; runs on GPT-5; SOC 2 Type II ([V2 post](https://charlielabs.ai/blog/charlie-v2-introducing-the-coding-agent-operating-system-caos/);
  [changelog](https://www.charlielabs.ai/changelog)). Own agent, not a CLI orchestrator; no sandbox details public.

#### Sweep
- Now a JetBrains IDE plugin; last plugin release v1.29.3 on 2026-02-05 (unverified,
  [rywalker](https://rywalker.com/research/sweep)). Not relevant to remote CLI orchestration.

---

### 9. Agent servers and protocols LADO could drive remotely

#### OpenCode server
- `opencode serve` = headless HTTP server, OpenAPI 3.1 at `/doc`; default `127.0.0.1:4096`; `--mdns`,
  `--cors`; basic auth via `OPENCODE_SERVER_PASSWORD`; SSE at `/event` and `/global/event`; sessions
  CRUD, `/session/:id/message`, `prompt_async`, `abort`, `fork`, `diff`, `/permissions/:id`; file/find
  endpoints; the TUI is itself a client; `/tui/*` drives a TUI remotely
  ([server docs](https://opencode.ai/docs/server/)). `opencode attach <url>` connects a TUI to a remote
  server ([attach (mirror)](https://www.mintlify.com/anomalyco/opencode/cli/attach)).

#### Codex app-server
- JSON-RPC 2.0 over stdio (WebSocket experimental), `initialize` handshake, threads → turns → items;
  `thread/start|resume|fork|list`, `turn/start`; notifications `item/started`, `item/completed`,
  `item/agentMessage/delta`, `turn/completed` with token usage; error -32001 = overloaded, retry with
  backoff; schema version-specific (`codex app-server generate-ts`), pin the version
  ([app-server README mirror](https://forge.lthn.ai/core/core-agent-ide/src/commit/361d43b969f0b0c4e08f3ab53ede22bbdee06c71/codex-rs/app-server/README.md);
  [Mintlify API overview](https://www.mintlify.com/openai/codex/api/overview)) — mirrors, verify against openai/codex.

#### Agent Client Protocol (ACP)
- Agents launched as subprocesses over stdio; registry launched (Zed blog 2026-01-28, protocol updates
  2026-03-09) listing Claude Code, Codex CLI, Copilot CLI, OpenCode, Gemini CLI
  ([Zed blog](https://zed.dev/blog/acp-registry); [updates](https://agentclientprotocol.com/updates)).
- 2026 stabilizations relevant to remote use: `session/list` and `session_info_update` (Mar 9),
  `session/resume` without history replay — "proxies and adapters can build `session/load` on top"
  (Apr 22), `session/close` (Apr 23), `session/delete`, `usage_update`, message IDs (Jun 5), Rust/TS SDKs
  1.0 (Jun 25), `$/cancel_request` (Jun 29), ACP v2 draft (Jul 20), elicitation (Jul 22), tool call names
  (Sep 17) ([updates](https://agentclientprotocol.com/updates)).
- **Remote transport is not standardized yet**: a Transports Working Group was formed 2026-04-22 with a
  draft RFD ([updates](https://agentclientprotocol.com/updates)); a later guide still lists remote
  transport as a proposal ([noqta](https://www.noqta.tn/en/blog/agent-client-protocol-acp-universal-ai-coding-editor-standard-2026), secondary).
- Claude Code speaks ACP through an adapter (`@agentclientprotocol/claude-agent-acp`), Codex through
  `@zed-industries/codex-acp` ([OpenHands ACP guide](https://docs.openhands.dev/sdk/guides/agent-acp)).
  Note: the Claude adapter is built on the Agent SDK, so under Anthropic's rules its subscription usage
  is "programmatic" (see §10).

---

### 10. Credentials and terms of service for hosting third-party agent CLIs

#### Anthropic / Claude Code (the strict one)
- **Precedence** (official): cloud provider flags → `ANTHROPIC_AUTH_TOKEN` → `ANTHROPIC_API_KEY` →
  `apiKeyHelper` → `CLAUDE_CODE_OAUTH_TOKEN` → Anthropic profile/WIF → `/login` OAuth
  ([auth docs](https://code.claude.com/docs/en/authentication)).
- `claude setup-token` mints a **one-year** subscription OAuth token (Pro/Max/Team/Enterprise), printed
  not stored, used as `CLAUDE_CODE_OAUTH_TOKEN`; it can only make model requests (no Remote Control, no
  claude.ai connectors); `--bare` mode ignores it (same page). Linux credentials live in
  `~/.claude/.credentials.json` (0600); `CLAUDE_CONFIG_DIR` gives per-account dirs (same page).
- **Legal and compliance page** ([link](https://code.claude.com/docs/en/legal-and-compliance)):
  - Preinstalling or running Claude Code "in hosted sandboxes or other agent infrastructure" requires the
    **Commercial Terms** and: binary unmodified, no removing auth methods; the platform **may not pay
    for, resell, or intermediate** Claude usage — each end user authenticates with *their own* API key,
    subscription credentials, or Bedrock/Vertex/Foundry credential.
  - OAuth is for subscription purchasers and "ordinary use of Claude Code and other native Anthropic
    applications"; developers of products, including Agent SDK ones, should use API keys; third parties
    may not offer Claude.ai login in their apps or route requests through Free/Pro/Max credentials on
    behalf of users, and **may not collect, store, or intermediate Claude.ai credentials or session
    tokens** — sign-in must complete through Anthropic's own flow.
  - But it explicitly does **not** prevent "an end user from signing in to the unmodified Claude Code
    binary with their own Claude subscription, including where a platform hosts Claude Code."
  - Advertised Pro/Max limits assume "ordinary, individual usage".
- Timeline: 2026-01-09 server-side block of subscription OAuth outside Claude Code (error "This
  credential is only authorized for use with Claude Code"); Feb 17–20 Consumer Terms update; Mar 19
  OpenCode removed Anthropic OAuth after legal demands; Apr 4 subscriptions no longer cover third-party
  tools ([falcao.org](https://falcao.org/posts/anthropic-claude-access-crackdown-ecosystem-fallout/);
  [AlternativeTo](https://alternativeto.net/news/2026/4/anthropic-ends-free-claude-access-for-third-party-tools-like-openclaw);
  [Gigazine](https://gigazine.net/gsc_news/en/20260220-anthropic-third-party-block)).
- From 2026-06-15 programmatic usage (Agent SDK, `claude -p`, GitHub Actions, SDK-based third-party apps)
  draws from a separate monthly **Agent SDK credit** (Pro $20, Max 5x $100, Max 20x $200); interactive
  Claude Code stays on subscription limits; hard stop when exhausted unless extra usage is on
  (secondary sources: [aicatchup](https://aicatchup.com/news/claude-agent-sdk-monthly-credit-paid-plans),
  [betterstack](https://betterstack.com/community/guides/ai/claude-credits/); Anthropic's support article not fetched).

**Implication for LADO**: running the unmodified `claude` binary interactively in tmux, logged in by the
user through Anthropic's own flow, is the explicitly allowed case — even on a hosted platform. A paid
LADO cloud must (a) sign the Commercial Terms, (b) never pay for/resell Claude usage, (c) never store or
proxy users' Claude.ai credentials itself — so "paste your setup-token into our cloud" is at best grey
(the user's own token, but LADO stores it). A self-hosted/BYO-cluster mode where the user's own secret
store holds the token is much cleaner. Headless `-p` use burns Agent SDK credit, not plan limits.

#### OpenAI / Codex
- ChatGPT login cached in `~/.codex/auth.json` (plaintext, "treat like a password") or OS keyring via
  `cli_auth_credentials_store`; tokens auto-refresh; headless: `codex login --device-auth` (beta, must be
  enabled in ChatGPT security/workspace settings), or copy `auth.json` (docs show `scp`, `docker cp`), or
  SSH-forward port 1455 ([Codex auth](https://learn.chatgpt.com/docs/auth)).
- Automation: API keys are "the recommended default"; Enterprise **access tokens**
  (`codex login --with-access-token`, `CODEX_ACCESS_TOKEN`) for trusted scripts/CI; "Don't expose Codex
  execution in untrusted or public environments"; admins can force login method/workspace (same page).
- OpenAI went the other way from Anthropic: "Sign in with ChatGPT" lets plan usage flow into third-party
  tools with 16 launch partners incl. OpenCode, OpenClaw, Amp, Devin, Warp, Vercel; per-app weekly caps,
  no automatic overflow billing ([The New Stack](https://thenewstack.io/sign-in-with-chatgpt/);
  [yage.ai summary](https://yage.ai/share/chatgpt-subscription-oauth-en-20261013.html), secondary).

#### How products actually handle it
- **Terragon**: let users plug in Claude/ChatGPT subscriptions or API keys — and shut down a week after
  Anthropic's OAuth block ([repo](https://github.com/terragon-labs/terragon-oss); timeline above).
- **Conductor Cloud / Tembo / Open-Inspect**: bring-your-own subscription or key
  ([vibecoding](https://vibecoding.app/blog/conductor-review); [Open-Inspect](https://github.com/ColeMurray/background-agents)).
- **OpenHands ACPAgent**: reuses whatever CLI login exists on the sandbox machine
  ([ACP guide](https://docs.openhands.dev/sdk/guides/agent-acp)).
- **Kilo**: keeps tokens in the control plane; sandbox only sees container-bound capability tokens
  swapped at an egress proxy ([blog](https://blog.kilo.ai/p/keys)). Could apply to `ANTHROPIC_API_KEY`
  too (proxy via `ANTHROPIC_BASE_URL`), but not to subscription OAuth without "intermediating" it.
- **Open-Inspect** warns that credentials cached on disk end up in snapshots and that revocation is not
  immediate ([repo](https://github.com/ColeMurray/background-agents)) — relevant if LADO ever snapshots
  or suspends workspaces with `~/.claude` inside.

---

### 11. Isolation / sandbox providers seen in the wild

- Docker (OpenHands default, Sculptor, Catnip), Apple container SDK (Catnip), microVMs (Conductor Cloud),
  Modal (gVisor), E2B (Firecracker, no self-host), Daytona (AGPL, self-hostable; sysbox vs Firecracker
  claims conflict) ([Modal comparison](https://modal.com/resources/best-code-execution-sandboxes-coding-agents);
  [Novita](https://blogs.novita.ai/what-are-the-best-ai-sandbox-solutions/)), Vercel Sandbox (Kilo,
  Open-Inspect, maybe Conductor), Kubernetes `agent-sandbox` CRDs with gVisor/Kata runtimeClass and warm
  pools (OpenHands), Apptainer (OpenHands, HPC).

---

### 12. Lessons for LADO

1. **Two proven shapes for remote**: (a) "agent-server inside the sandbox" with a small API (OpenHands:
   exec, files, git diff, events over WS; OpenCode serve; Codex app-server) and (b) "unchanged CLI in a
   terminal, controlled from outside" (tmux/PTY — Claude Squad, Uzi, Superset, LADO today). LADO's
   hooks+MCP model fits (b) and can run unchanged inside a container if the MCP/hook channel back to
   LADO's control plane works over the network.
2. **Outbound-only daemons** (Remote Control, `omnarad`, Happy) are the norm for reaching agents behind
   NAT or in a customer cluster.
3. **Kubernetes**: OpenHands builds on `kubernetes-sigs/agent-sandbox` (SandboxTemplate, SandboxClaim,
   SandboxWarmPool, Suspended/Running) — a ready-made CRD set rather than custom pod management.
4. **Code in/out**: almost everyone uses git (clone in, branch + push/PR out); Kilo pushes after every
   message; Sculptor adds live two-way sync for "pairing"; Open-Inspect snapshots the FS per prompt.
5. **Adapters**: Vibe Kanban's trait (spawn, follow-up with session id, normalize logs, MCP config path,
   availability, approvals) and OpenHands' `ACPAgent` are the two reference adapter designs. ACP covers
   Claude/Codex/Gemini/OpenCode but its remote transport is still a draft.
6. **Credentials** decide the business model: Anthropic forbids a platform paying for, reselling, or
   intermediating Claude usage and storing Claude.ai credentials; it allows hosting the unmodified binary
   where the user signs in themselves. OpenAI actively allows subscription use in partner tools.
7. **Hosted businesses here are fragile**: Terragon (Jan 2026) and Vibe Kanban/Bloop (Apr 2026) shut
   down; Omnara pivoted away from wrapping CLIs; Catnip's repo vanished; Crystal deprecated. Survivors
   either own the agent (OpenHands, Kilo, Charlie) or sell enterprise VPC/self-hosted (OpenHands, Tembo).
