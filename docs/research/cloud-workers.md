# Research: cloud workers (LAD-100)

The question: how can LADO run its agents in a cloud instead of on the human's own machine,
without tying LADO to one cloud, with any agent CLI, as an option next to the local mode
and never a requirement, and with a paid hosted offering kept possible for later. Research
of 2026-10-18, no code changed; the human approved the summary and its staged plan the same
day. Openspec change: `openspec/changes/cloud-workers-research/`. The staged plan, kept up
to date after each step: [cloud-workers-plan.md](cloud-workers-plan.md).

The research went in several directions; the detailed reports (with sources and code
references) are in [cloud-workers/](cloud-workers/):

| Report | What about |
|---|---|
| [R1](cloud-workers/r1-lado-coupling.md) | what in LADO is tied to one machine: 16 places with `file:line`, the seams for remote running |
| [R2](cloud-workers/r2-prior-art.md) | how others do it: about 50 products and projects, about 385 sources |
| [R3](cloud-workers/r3-cloud-survey.md) | a survey of clouds, Kubernetes, sandboxes, isolation and portability layers |
| [R4](cloud-workers/r4-credentials.md) | the agent CLIs' logins in a cloud, terms of use, secrets |

1. [Summary](#1-summary)
2. [Options](#2-options)
3. [Split points A-D](#3-split-points-a-d)
4. [Logins and money](#4-logins-and-money)
5. [Principles](#5-principles)
6. [Risks](#6-risks)
7. [Sources](#7-sources)

## 1. Summary

1. **The industry converged on one scheme.** A "control plane" (UI, task queue, event
   log, accounts) is separate from the "sandbox" where the agent works. The sandbox is a
   container or a micro-VM, one per session. Code gets in through `git clone`, the result
   leaves as a branch or a PR. In self-hosted mode the "runner" connects to the control
   plane itself, over an outbound connection, so NAT is no obstacle. This is how Claude
   Code (self-hosted runners), Cursor, Devin, Warp and Factory work.
2. **LADO has no central owning process.** All its processes work with one SQLite file,
   one tmux and one filesystem: the CLI, the UI server, the session loop, each agent's
   `lado mcp`, each hook. So **moving a whole session to a cloud is cheap**: almost
   everything is already there. **Moving a single worker to a cloud is dear**: it needs
   hooks and MCP over the network, git sync and a terminal relay.
3. **Portability between clouds comes from three standards: the OCI image, the Docker API
   (over SSH too) and the Kubernetes API.** They cover any VPS (Hetzner, DO, Selectel,
   Yandex), any Kubernetes (k3s at home, managed clusters, Russian clouds) and sandboxes;
   the sandboxes are plugged in through adapters, not core code. There is no need to tie
   LADO to the proprietary APIs of sandboxes (E2B, Modal, Daytona); Daytona, moreover,
   closed its source in 2026.
4. **The "any provider" requirement holds if the CLIs stay unchanged inside tmux, as
   today.** An agent of one's own or screen reading lost: Coder's AgentAPI, which read the
   screen, is archived. The market's experience confirms our principle "events, not
   screens".
5. **The main limit of a paid variant is legal, not technical.**
   - **Anthropic** expressly forbids a platform to pay for its users' Claude inference or
     to resell it. Storing their claude.ai tokens is forbidden too. One thing is allowed:
     the user signs in with their own subscription to an unmodified `claude` on the hosted
     platform.
   - **OpenAI**: "Sign in with ChatGPT" for paid hosting needs an application and
     approval.
   - **Gemini CLI**: OAuth from third-party programs is forbidden.
   - The safe model for a paid service is **BYOK**: the user brings their own API key or
     cloud account (Bedrock, Vertex, Azure) and pays for the models themselves.

## 2. Options

### 2.1 Where to run

| Option | Lock-in | Self-hostable | For a long interactive session | Verdict |
|---|---|---|---|---|
| **Docker host over SSH** (any VPS or home server; Podman the same) | none | yes | excellent | **first backend** |
| **Kubernetes** (k3s, EKS/GKE/AKS, DO/Scaleway/OVH, Yandex/Selectel/VK Cloud/Cloud.ru) | none | yes | good: a one-pod StatefulSet plus a PVC | **second backend** |
| `kubernetes-sigs/agent-sandbox` (Sandbox CRD, warm pod pools, pause/resume, gVisor/Kata) | none | yes | made exactly for this task | a mode of the k8s backend, later; OpenHands already runs on it |
| A VM through a cloud's API | weak (each has its own SDK) | — | good | "Docker host plus making the machine": a helper, not a backend of its own |
| Fly Machines and Sprites (Firecracker, suspend/resume) | medium | no | good, cheap when idle | later, as a "zero administration" option |
| SaaS sandboxes: E2B, Modal, Runloop, Morph, Northflank, Daytona | high | partly | some have a 24-hour limit | only through an adapter, on request |
| Serverless: Cloud Run, Fargate, ACI | medium | no | poor: the WebSocket drops after an hour, no suspend | does not fit |
| Nomad | — | yes | — | not needed: BSL licence, few users |

### 2.2 Portability layers

- **The OCI image.** We already have it (the Docker epic LAD-52): one image with four CLIs,
  amd64 and arm64. It is the common unit of all the options.
- **devcontainer.json.** Gives a "free" launch of LADO in DevPod, Coder and Codespaces with
  all their providers and no integration code. It is cheap and worth doing at once.
- **Coder (Terraform templates)**: for organisations that already have it. An example
  template is enough.
- **DevPod.** The best "change the cloud with one flag" model, but its development has
  almost stopped since 2025. We take the idea (a small external "provider CLI"), not the
  dependency.
- **Pulumi Automation API and OpenTofu** are needed only to create machines. Pulumi is
  handier from Python.
- **Crossplane and libcloud** are not needed.

### 2.3 Isolation

- For a single user on their own VPS, a separate VM and an ordinary container are enough.
- A shared host, and a paid service all the more, needs VM-level isolation: gVisor
  (without KVM), Kata or Firecracker. Added to it: outbound traffic limited to an
  allowlist, a non-root user, narrowly scoped tokens and a stop on idle.
- Do not mount the host's Docker socket by default. If agents need Docker inside, use
  Sysbox.

## 3. Split points A-D

What of LADO can run in a cloud: four split points.

| Split | What runs where | What LADO must change | Size |
|---|---|---|---|
| **A. The whole session in a remote "box"** | LADO, the UI and all agents in one container, VM or pod. The human opens the UI in a browser | The core does not change. Needed: TLS and a proper login to the UI, repositories from a git URL instead of a mounted folder, a persistent volume, launch recipes (compose on a remote host, a Helm chart or k8s manifest, devcontainer) | S–M |
| **B. The UI remote, execution local** (or the other way round) | only the presentation | TLS and a login; in effect the same as the desktop app | S |
| **C. All agents of one session on a remote node**, the control plane apart | the UI and the DB in one place, tmux, worktrees and the CLIs on the node | an "execution backend" interface below `providers/`; hooks and MCP over the network with a token per agent; a terminal relay; a node daemon with an outbound connection. Git on the node works as today (worktrees side by side) | M–L |
| **D. Single workers remote** (a mixed session), the full "control / execution" split | the supervisor local, some workers in the cloud | all of C plus branch sync (clone and push/fetch), heartbeats, a node registry. The "control" laptop must be reachable from the node | L–XL |

**The answer to "what exactly to run in the cloud":** the right target architecture is D,
a control plane and an execution plane, where the local launch becomes one of the nodes,
the "local node". The way to it goes through A and C. Each step gives a working result and
leaves the local mode untouched.

### Already in the code, to reuse

- **The provider interface:** `Capabilities` and event parsing in `providers/base.py`.
- **The agent's identity:** the launch id `agents.instance`. A ready basis for an agent's
  token.
- **Event feeds:** `feed.Source`. Its docstring already mentions remote workers' events.
- **The artifact store:** the `artifacts.Store` protocol; it can be moved into a service.
- **Authorization:** `server/auth.py`, the UI's one place of authorization. A token and
  Bearer are already there, OpenAPI too.
- **Secrets:** the `LADO_ENV_DIR` folder maps one to one onto Kubernetes or Docker
  secrets.
- **Versions:** `SchemaError` is a model for a protocol version check between the control
  plane and a node.
- **ACP (ROADMAP stage 8):** planned "behind the same interface". It is the same seam, so
  the backend interface is worth designing at once for three implementations: tmux, a
  remote node and ACP.

## 4. Logins and money

| Scenario | Claude Code | Codex | Kilo / OpenCode | Gemini CLI |
|---|---|---|---|---|
| (a) the user runs LADO in their own cloud with their own subscription | yes: `claude setup-token` or `/login` in the container | yes, but `auth.json` is one per machine and cannot be shared between replicas | yes | only an API key or Vertex |
| (b) our hosting, the user's subscription | only if the user signs in to an unmodified `claude` themselves. Storing or inserting their token is forbidden. Needs Anthropic's written confirmation | only on application and OpenAI's approval | Kilo allows it; OpenCode Zen/Go do not | no |
| (c) our hosting, our keys, we charge money | **forbidden** without a separate agreement with Anthropic | seems allowed under the Services Agreement (to confirm) | Kilo allows it | API key: yes |

Hence:

- **A self-hosted cloud (scenario a) is legally safe** for all CLIs. We start with it.
- **A paid service** is built on BYOK: the user's own key or cloud accounts. An outbound
  proxy holds the keys and puts them into the requests (as Anthropic, Cloudflare and
  Docker Sandboxes do), so the agent never sees the keys themselves. Git access goes
  through a GitHub App with one-hour tokens. Claude subscriptions in a paid service only
  through Anthropic's own sign-in, and only after their written "yes".
- **The market warns.** Hosted wrappers around other vendors' CLIs mostly closed or
  changed course in 2026: Terragon, Bloop, Omnara, Crystal. A paid variant is a hypothesis
  to test cheaply.

Technical limits of the logins:

- Refreshing logins (Codex `auth.json`, Claude `/login`) need a copy of their own in each
  container.
- `CLAUDE_CODE_OAUTH_TOKEN` is static for a year and suits a "box".
- All four CLIs support remote MCP over HTTP with a Bearer header. Splits C and D need it.
- Claude Code has hooks of type `http`.
- All of this must be checked by hand on the CLI versions LADO is tested with.

## 5. Principles

The principles of the solution, held against the task's criteria:

1. **The cloud is an addition.** The local mode stays the default and does not change.
   Each step ships so that an existing user notices nothing.
2. **No cloud lock-in.** The core knows only an "execution backend" with a small set of
   operations: create, start/stop/pause, status, exec/attach, port forwarding, delete.
   Each backend says loudly what it cannot do, by the No silent drops principle. Concrete
   clouds are plugged in as backends (Docker over SSH, Kubernetes) or as external adapters
   in the manner of DevPod's providers, not as core code.
3. **Any provider.** In the cloud: the same unchanged CLIs in tmux, the same image with all
   the CLIs, the same hooks and MCP. Only MCP and the hooks go over the network.
4. **Components.** The UI, the control plane (DB, loop, artifacts) and execution are
   separate components. Each can be put anywhere: all local, all in the cloud, the UI
   local and the agents in the cloud.
5. **Ready for a paid version in advance**, without building it now:
   - the control plane stores no secrets, only references to them;
   - each agent has its own token;
   - usage events (node time, tokens) are written to the log;
   - the data schema has an owner or tenant field;
   - the UI's API is stable, with OpenAPI.

## 6. Risks

- **SQLite with many writers** does not carry across hosts. The cure is a single writer
  (B3 of the plan), not a remote DB.
- **Git** is the largest hole for split D. We do not open it before stage D.
- **The UI's security on a network.** Today it is HTTP with a token, and the terminal in
  effect gives a shell. A1 of the plan is required before any cloud recommendation.
- **Subscriptions.** Pro/Max limits are meant for "ordinary individual usage". Many
  parallel agents in a cloud on one subscription may hit the limits or bring sanctions.
- **An unstable sandbox market.** Daytona closed its code, DevPod has stopped, OpenAI is
  buying Ona. So we rely on standards (OCI, the Docker API, the k8s API), not on vendors.
- **The network from Russia:** Cloudflare Tunnel and Tailscale may be unreachable. A base
  path without them is needed: an SSH tunnel or Headscale.

## 7. Sources

The four intermediate reports, in English, as written on 2026-10-18, each with its
sources:

- [R1, LADO's single-machine couplings](cloud-workers/r1-lado-coupling.md): the process
  map, the couplings C1-C16 with code references at commit 033705e, the split points and
  the assets to reuse.
- [R2, prior art](cloud-workers/r2-prior-art.md): vendor-hosted coding agents, sandbox and
  runtime providers, orchestrators and multi-agent tools, as of 2026-10-18.
- [R3, cloud survey](cloud-workers/r3-cloud-survey.md): execution targets, isolation,
  portability layers, remote access and sync, cost of long idle sessions, the minimal set
  of backends.
- [R4, credentials](cloud-workers/r4-credentials.md): each CLI's logins, the terms of
  service per scenario, secret handling, remote-running capabilities (headless, hooks,
  ACP, remote MCP).
