# Running LADO in the cloud without lock-in: survey (October 2026)

Scope: where and how to run LADO's existing image (`lado` + Claude Code, Codex, Kilo,
OpenCode; ~615 MB; amd64/arm64) remotely, so that a user can switch providers fast and
can self-host. Possibly a paid hosted LADO later.

Method and confidence: web search in October 2026. Many vendor-comparison pages are
written by competitors, so I cross-checked with vendor docs where possible. Prices and
some 2026 events (Daytona's closed-source move, Hetzner's repricing, E2B Embed) come from
secondary sources and are flagged "(unverified)". Check them before any commitment.

---

## 0. The shape of LADO's workload (why this matters for the choice)

- **Long-lived and mostly idle.** A session runs for hours. Agents wait for an LLM or a
  human most of the time. CPU is low, memory is moderate (four Node/Rust CLIs plus tmux,
  git and Python), and the disk (repo, worktrees, `~/.lado`) must persist.
- **Interactive.** The UI needs terminals (tmux panes over a WebSocket) and a live event
  feed. Request-scoped platforms with timeouts of 60 minutes or less are a bad fit.
- **Stateful.** SQLite in `~/.lado/lado.db`, git worktrees and agent CLIs' login state
  (OAuth tokens for Claude Code and Codex) live on disk. Suspend and resume with the disk
  kept is the key cost lever.
- **Untrusted code.** Agents run arbitrary shell commands, `npm install`s and tests in
  the user's repo. With bypass-permissions modes this is effectively untrusted code with
  the user's credentials (LLM keys, git push token).
- **One container per session is enough.** LADO already isolates agents from each other
  with worktrees inside one box. "One OCI container or VM per LADO session" is the natural
  unit; there is no need for one pod per agent.

So the requirements are: an OCI image, a persistent volume, long or unlimited runtime,
stop/suspend without losing the disk, a way to reach a port or terminal, and, ideally,
VM-grade isolation.

---

## 1. Execution targets

### 1.1 A plain remote Docker host over SSH

- `DOCKER_HOST=ssh://user@host` (or `docker context create --docker host=ssh://...`)
  makes the local Docker CLI and SDK talk to a remote daemon through SSH; no TCP port,
  no TLS certificates. https://docs.docker.com/engine/security/protect-access/ and
  https://docs.docker.com/engine/manage-resources/contexts/
- docker-py supports `ssh://` base URLs (via paramiko or the `ssh` binary with
  `use_ssh_client=True`). https://docker-py.readthedocs.io/en/stable/client.html
- Works with any Linux box: a Hetzner/DO/Selectel VPS, a home server, a corporate VM.
  Docker Compose works over the same context.
- **Lock-in: none.** Self-host: yes by definition. Setup for a user: "a Linux box with
  Docker and an SSH key". Isolation: runc by default; can add gVisor (`--runtime=runsc`),
  Kata or Sysbox on the host.
- Cost: whatever the VM costs (Hetzner CX23/CAX11 roughly €4-6/month after the 2026
  repricing (unverified), hourly billing with a monthly cap). No suspend/resume of
  the container unless the VM itself is stopped.

### 1.2 Podman

- Podman exposes a Docker-compatible REST API socket (`podman system service`), so the
  same Docker client code works; remote through `podman --remote` / `CONTAINER_HOST=ssh://`.
  Rootless by default, which is a security plus. https://docs.podman.io/en/latest/markdown/podman-system-service.1.html
- Podman also has `podman kube play` (run a Kubernetes Pod YAML locally) - one manifest
  for both Podman and k8s. https://docs.podman.io/en/latest/markdown/podman-kube-play.1.html
- Licence Apache-2.0. Lock-in none. Treat it as "the Docker backend with a different
  socket", not a separate backend.

### 1.3 Kubernetes (any distribution)

- The most portable *API* for running containers across clouds: k3s/k0s on one VPS;
  EKS/GKE/AKS; managed k8s at Hetzner (via community/Cluster API, not first-party),
  DigitalOcean DOKS, Linode LKE, Scaleway Kapsule, OVHcloud MKS; Russian market:
  **Yandex Managed Service for Kubernetes** (https://yandex.cloud/en/docs/managed-kubernetes/pricing ;
  masters billed monthly-by-hour, workers per Compute Cloud rules; master pricing changed
  in June 2026 to vCPU/RAM-based), **Selectel Managed Kubernetes**
  (https://docs.selectel.ru/en/managed-kubernetes ; control plane managed by Selectel;
  Selectel raised prices ~2% from 15 Jan 2026: https://files.selectel.ru/docs/ru/New-prices-January-15-2026.pdf),
  **VK Cloud Kubernetes** and **Cloud.ru Evolution Managed Kubernetes** (both exist; I did
  not find their current billing granularity in this search - check their price pages).
- The LADO unit maps cleanly: a StatefulSet of size 1 or a single Pod + PVC + Service;
  terminals via `kubectl exec`/attach or LADO's own WebSocket through a port-forward or
  Ingress.
- Python: the official `kubernetes` client (Apache-2.0) is mature; `kr8s` is a lighter
  alternative. https://github.com/kubernetes-client/python
- **Agent Sandbox (kubernetes-sigs/agent-sandbox)**: a SIG Apps project announced on the
  Kubernetes blog on 20 March 2026 (https://kubernetes.io/blog/2026/03/20/running-agents-on-kubernetes-with-agent-sandbox).
  Core CRD `Sandbox` (`agents.x-k8s.io/v1alpha1`): a singleton, stateful pod with stable
  identity and persistent storage, designed for long-running agent sessions, with
  pause/resume (scale to zero while keeping the PVC). Extensions
  (`extensions.agents.x-k8s.io`): `SandboxTemplate`, `SandboxClaim`, `SandboxWarmPool`
  (pre-warmed sandboxes; HPA-friendly). Runtime-agnostic: gVisor or Kata via
  `runtimeClassName`. Has a Python SDK/client. Still **v1alpha1**; releases in 2026 were
  in the 0.3-0.5 range (sources disagree). Docs: https://agent-sandbox.sigs.k8s.io/docs/ ,
  https://agent-sandbox.sigs.k8s.io/docs/getting_started , install also documented by
  Cloudfleet https://cloudfleet.ai/docs/workload-isolation/agent-sandbox/ .
  This is exactly LADO's shape (one stateful sandbox per session), but alpha: support it
  as an optional mode of a Kubernetes backend, with a plain-StatefulSet fallback.
- Lock-in: low (the API is the same everywhere; storage classes, ingress and
  RuntimeClasses differ). Setup effort for a user: high unless they already have a
  cluster; then low (a kubeconfig).

### 1.4 HashiCorp Nomad

- Schedules Docker/Podman/exec/QEMU workloads; simpler than k8s. But Nomad moved to the
  BSL 1.1 in August 2023 and HashiCorp is now part of IBM; there is no widely adopted
  open fork as with OpenTofu. https://www.hashicorp.com/en/license-faq
- Small user base among LADO's target audience. **Skip**; a Nomad user can use the SSH /
  Docker backend against a Nomad client node.

### 1.5 VMs through cloud APIs (Hetzner, DigitalOcean, AWS EC2, GCP, Yandex, Selectel)

- Each cloud has its own API, but all share the pattern: create VM from image + cloud-init
  → it has Docker → LADO talks to it over SSH (1.1). Stop/start keeps the disk; you pay
  only for the disk while stopped on most clouds (Hetzner is an exception: a stopped
  server is still billed in full; you must snapshot and delete to stop paying -
  https://docs.hetzner.com/cloud/billing/faq/).
- Python: `hcloud` (Hetzner, MIT), `pydo` (DigitalOcean), `boto3`, `google-cloud-compute`,
  `yandexcloud` SDK; or **Apache Libcloud** (one API for 50+ compute providers, Apache-2.0,
  but development is slow and coverage of newer features is thin;
  https://libcloud.apache.org/). Or Terraform/OpenTofu/Pulumi (section 3).
- Lock-in: low if the VM is only "a Docker host reached over SSH"; the provisioning step is
  the only provider-specific part.

### 1.6 Fly.io Machines and Sprites

- **Machines**: Firecracker microVMs from an OCI image, REST API, per-second billing while
  running; stopped/suspended Machines pay only rootfs storage ($0.15/GB-month); volumes
  billed separately; **suspend** saves memory too and resumes in a few hundred ms.
  https://fly.io/docs/about/billing/ , https://fly.io/docs/reference/suspend-resume/ .
  Good fit: hardware isolation, long-running, cheap when idle. Lock-in: medium (Fly-only
  API, but the unit is our OCI image). Not self-hostable.
- **Sprites** (2026): Fly's persistent sandbox VMs for agents; persistent NVMe filesystem
  synced to object storage; ~300 ms checkpoints and restore ("undo button"); billed only
  while active (third-party figures: ~$0.07/CPU-h, ~$0.044/GB-h RAM; one estimate of
  ~$0.44 for a 4-hour Claude Code session - unverified). https://fly.io/sprites ,
  https://fly.io/sprites/checkpoint-restore/ , https://rywalker.com/research/sprites .
  Sprites are base-image Linux machines rather than "run my OCI image", so LADO would be
  installed into them (pip/uv) instead of running our image.

### 1.7 Serverless containers (Cloud Run, ACI, ECS Fargate, Yandex Serverless Containers)

- **Google Cloud Run services**: request timeout max 60 minutes, WebSockets dropped at
  the timeout and on scale-down; session affinity best-effort.
  https://docs.cloud.google.com/run/docs/triggering/websockets . Not a fit for a LADO
  server holding tmux sessions, unless min-instances=max-instances=1 with instance-based
  billing, which turns it into an always-on VM at a higher price. Cloud Run **jobs**
  (up to 7 days) and **worker pools** suit background work, not interactive UI.
- **AWS ECS on Fargate**: tasks can run indefinitely; interactive shell via ECS Exec
  (SSM) - workable but clunky; no suspend; EFS for persistence; per-second billing with a
  1-minute minimum. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-exec.html
- **Azure Container Instances**: long-running container groups, `az container exec`
  is limited (no stdin piping, single command); Azure Files for persistence; no suspend
  except stop/start, which loses the container's local disk.
  https://learn.microsoft.com/en-us/azure/container-instances/container-instances-exec
- **Yandex Serverless Containers**: request-scoped with a per-call timeout (up to 1 h);
  same issue as Cloud Run.
- Verdict: all lock-in heavy and poor fits for "interactive, hours-long, mostly idle,
  stateful". Not first targets.

### 1.8 Sandbox services (agent-oriented)

| Service | Isolation | Persistence / suspend | Max session | Self-host / OSS | Notes |
|---|---|---|---|---|---|
| **E2B** | Firecracker | pause/resume keeps FS + memory (persistence in beta); ~1 s resume | 1 h Hobby, 24 h Pro (window resets on resume) | SDK Apache-2.0; infra repo open; BYOC Enterprise; reported "E2B Embed" single-host self-host (Sept 2026, unverified) | ~$0.05/vCPU-h + $0.016/GiB-h; Pro $150/mo. https://e2b.dev/docs , https://www.beam.cloud/blog/e2b-pricing-explained |
| **Daytona** | containers (Sysbox/Kata options) | stop/archive with FS | long-lived | Was AGPL-3.0/OSS; a community fork (Nightona) and a competitor blog report the core went private in June 2026 (unverified) | https://cdn.jsdelivr.net/gh/nightona-co/nightona@main/README.md , https://helix.ml/blog/self-hosted-agent-sandboxes |
| **Modal Sandboxes** | gVisor | FS/memory snapshots | up to 24 h per sandbox | No (Modal cloud only) | Python-first SDK; strong for GPU. https://modal.com/docs/guide/sandbox |
| **Runloop Devboxes** | microVM | suspend keeps disk (not memory); compute stops; idle auto-suspend/shutdown | long | No | ~$0.108/CPU-h + $0.025/GB-h (third-party); Pro $250/mo. https://docs.runloop.ai/docs/devboxes/lifecycle |
| **Morph Cloud** | microVM ("Infinibranch") | snapshot/branch of running VMs in ms | long | Claims deployable on own infra (vendor) | https://www.morphllm.com/comparisons/e2b-alternatives |
| **Northflank Sandboxes** | Kata / gVisor / Firecracker | persistent volumes | unlimited | BYOC into your AWS/GCP/Azure/on-prem k8s (control plane is theirs) | https://northflank.com/blog/best-platforms-for-long-running-sandbox-environments |
| **CodeSandbox SDK → Together Code Sandbox** | Firecracker microVMs | memory snapshot, hibernate on disconnect, ~2-3 s resume/clone | long | No | per-minute billing; https://docs.together.ai/docs/together-code-sandbox |
| **Fly Sprites** | Firecracker | checkpoints, persistent FS | unlimited | No | see 1.6 |

Common traits: per-second billing, fast resume, VM-grade isolation, proprietary APIs
(each its own SDK), most cloud-only. They are optimized for many short sandboxes driven by
an agent *outside* the sandbox; LADO puts the whole orchestrator *inside* the box, which
any of them can do but with session caps (E2B 24 h, Modal 24 h) to work around.
Self-hostable open-source options in this space: kubernetes-sigs/agent-sandbox, E2B infra
(heavy: Nomad + Firecracker), microsandbox, OpenSandbox, Daytona's last open release /
forks - none as simple as "Docker over SSH".

---

## 2. Isolation

| Runtime | Mechanism | Strength | Cost / requirements | DinD |
|---|---|---|---|---|
| **runc** (default Docker/k8s) | namespaces + cgroups + seccomp, shared host kernel | weakest; kernel bugs = escape | none | only with `--privileged` (bad) or mounting the host socket (worse) |
| **Sysbox** (Nestybox, now Docker) | runc fork with user-ns, procfs/sysfs virtualization | better than runc; still shared kernel | install on host; Apache-2.0 | yes, without `--privileged` (its main purpose) https://github.com/nestybox/sysbox |
| **gVisor** (`runsc`) | user-space kernel intercepts syscalls | strong; small host kernel surface | syscall overhead (I/O-heavy builds slower); no KVM needed; GKE Sandbox built in | partial (Docker-in-gVisor is supported experimentally) https://gvisor.dev/docs/ |
| **Kata Containers** | each pod in a light VM (QEMU / Cloud Hypervisor / Firecracker) | hardware boundary | needs KVM (bare metal or nested virt); slower start | yes, inside the guest VM https://katacontainers.io/ |
| **Firecracker** microVMs | minimal VMM, ~125 ms boot | hardware boundary | KVM; you build the orchestration (or use Fly/E2B/Kata) | yes, inside the guest |
| **A whole VM per session** | cloud VM | hardware boundary, simplest mental model | slower start (30-60 s), per-VM cost | yes, plain Docker |

Comparisons: https://fly.io/learn/firecracker-vs-gvisor/ ,
https://www.softwareseni.com/firecracker-gvisor-containers-and-webassembly-comparing-isolation-technologies-for-ai-agents/

What is needed to run agent code safely:
1. **A boundary stronger than a shared kernel** when the host is shared between users
   (a hosted LADO): gVisor or Kata/Firecracker. For a user's own single-tenant VM, runc
   inside a dedicated VM is acceptable: the VM is the boundary.
2. **Secrets hygiene**: LLM keys and git tokens are inside the box by necessity; scope them
   (fine-grained PAT per repo, provider keys with spend limits); never mount the host's
   `~/.ssh` or Docker socket.
3. **Egress control**: NetworkPolicy (k8s), firewall rules or an egress proxy allowlisting
   LLM endpoints, package registries and the git host. Agent Sandbox templates carry a
   NetworkPolicy per template.
4. **Resource limits** (cgroups) and idle shutdown.
5. **Non-root user** inside the image; rootless Podman or user namespaces outside.

Docker-in-docker: agents often want `docker build`/`docker compose up` for tests
(testcontainers etc.). Options, best first: run in a VM (Kata/Firecracker/whole VM) and
start a real dockerd inside; Sysbox on a Docker host; rootless dockerd/podman inside the
container (needs some capabilities, works under some runtimes). Mounting the host
`/var/run/docker.sock` gives root on the host and must never be the default. LADO's
image could ship an optional rootless Podman for agents and document Sysbox/Kata for full
DinD.

---

## 3. Portability and abstraction layers

| Layer | What it abstracts | Targets | Maturity | Python friendliness | Licence |
|---|---|---|---|---|---|
| **OCI image** | the software unit | every target above | universal | n/a | open standard |
| **SSH** | reach a box: exec, port forwards, file copy | every VM/host/pod with sshd | universal | `asyncssh` (EPL/GPL dual), `paramiko` (LGPL), or the `ssh` binary | n/a |
| **Docker Engine API** (+ Podman compat) | container lifecycle on one host | any Linux host, local or `ssh://` | mature | `docker` (docker-py, Apache-2.0) | Apache-2.0 |
| **devcontainer.json + devcontainer CLI** | "how to build/run a dev container for this repo" (image, features, mounts, postCreate) | Docker/Podman locally or via DOCKER_HOST; used by Codespaces, DevPod, Coder envbuilder, VS Code, JetBrains | mature spec (containers.dev) | CLI is Node (`@devcontainers/cli`); call as subprocess | MIT (spec CC-BY) https://containers.dev/ , https://github.com/devcontainers/cli |
| **DevPod** | "a workspace on any provider": providers are small plugins (YAML + binary) for Docker, SSH, Kubernetes, AWS, GCP, Azure, DigitalOcean, Hetzner, … ; runs devcontainer.json; agent injected; SSH access via its tunnel | ~10 official + community providers | stable but slowed; vendor renamed to vCluster Labs; Pro tier separate | Go CLI; call as subprocess (`devpod up --provider ...`, `devpod ssh`) | MPL-2.0 https://github.com/loft-sh/devpod , https://devpod.sh/docs/managing-providers/what-are-providers |
| **Coder** | self-hosted control plane; templates in Terraform provision any infra (Docker, k8s pods, EC2/GCP VMs…); workspace agent gives SSH, port forwarding, web terminal, idle autostop; 2026 "Coder Agents"/Tasks for AI agents | anything Terraform can create | mature, enterprise | Go; REST API + `coder` CLI | AGPL-3.0 core, enterprise features proprietary https://github.com/coder/coder , https://coder.com/docs |
| **Terraform** | declarative provisioning of any cloud resource | thousands of providers | mature | HCL; Python via CDKTF (deprecated in 2025) or subprocess | BSL 1.1 since 2023 |
| **OpenTofu** | Terraform-compatible fork | same providers | mature, Linux Foundation | subprocess | MPL-2.0 https://opentofu.org/ |
| **Pulumi** | provisioning as code in real languages; Automation API embeds it in a program | same breadth (bridges TF providers) | mature | **excellent**: native Python SDK + Automation API | Apache-2.0 (engine); Pulumi Cloud state optional (can use S3/local backend) https://www.pulumi.com/docs/using-pulumi/automation-api/ |
| **Crossplane** | cloud resources as Kubernetes CRDs, compositions | many cloud providers | CNCF graduated (2025) | via the k8s API | Apache-2.0 https://www.crossplane.io/ |
| **Apache Libcloud** | one Python API for compute/storage/DNS on 50+ providers | many, but shallow | old, slow-moving | native Python | Apache-2.0 https://libcloud.apache.org/ |
| **Kubernetes API** (+ Agent Sandbox CRD) | container scheduling, storage, network everywhere | every cloud + self-hosted | mature (Agent Sandbox alpha) | official client | Apache-2.0 |

Reading of the table:
- **What LADO must abstract is small**: "start my image with a volume and env, give me a
  shell/port, stop/suspend, delete". That is the Docker API on a single host or the k8s API
  on a cluster. Provisioning the *host* (a VM) is a separate, optional, provider-specific
  step that Pulumi/OpenTofu/DevPod/Coder can own.
- **DevPod** is the closest existing "switch providers with one flag" model and is open
  source; its provider protocol is simple enough to borrow as an idea (a provider = a
  manifest of commands: create, start, stop, status, delete, command/exec over a tunnel).
  Using DevPod itself as a dependency would add a Go binary and the devcontainer layer
  for little gain, and its development pace has slowed.
- **Coder** is the right answer for organisations that already run Coder: LADO should run
  *inside* a Coder workspace (a template with our image), not integrate Coder's API.
- **Pulumi Automation API** is the most Python-friendly way to provision VMs on many clouds
  if LADO ever creates VMs itself; OpenTofu is the licence-clean IaC choice for docs and
  templates users run themselves.

---

## 4. Remote access and file/git sync

### Reaching the remote LADO

| Pattern | How | Pros | Cons |
|---|---|---|---|
| **SSH local port-forward** | `ssh -L 8765:localhost:8765 host` then open the UI locally; LADO's existing UI token auth stays | zero extra infra; works with any host; encrypted; Docker-over-SSH uses the same channel | user needs an SSH key; reconnect handling (autossh / a supervisor in LADO) |
| **kubectl port-forward / exec** | `kubectl port-forward pod/lado-x 8765` ; `kubectl exec -it` for a shell | no ingress needed; RBAC | port-forward is fragile over long periods; streams through the API server |
| **LADO's own WebSocket terminal behind HTTPS** | Ingress/LB/Fly proxy + TLS + LADO token auth (already in `server/auth.py`) | browser-only access, phone-friendly | public exposure; needs strong auth, TLS, rate limits |
| **Tailscale / Headscale / WireGuard** | the container or VM joins a tailnet (`tailscaled` userspace mode works in containers); access via MagicDNS; Tailscale SSH | private, NAT traversal, no open ports; Headscale is a self-hosted OSS control plane (BSD-3) | a third-party account (unless Headscale); extra daemon in the image | https://tailscale.com/kb/1112/userspace-networking , https://github.com/juanfont/headscale |
| **Cloudflare Tunnel** | `cloudflared` dials out; Cloudflare Access for auth | no open ports, free tier, auth in front | Cloudflare lock-in; not available/reliable in some regions (notably Russia) | https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/ |
| **Provider proxies** | Fly proxy / `fly proxy`, E2B/Daytona preview URLs, Coder port-forwarding | built in | provider-specific |

Recommendation: SSH port-forward as the baseline (works for SSH hosts and VMs), kubectl
port-forward for k8s, and HTTPS + token for "open in browser" when the user exposes it
themselves; document Tailscale as the comfortable option. Note that Cloudflare and
Tailscale coordination servers may be restricted for Russian users; Headscale/WireGuard
are the self-hosted fallbacks.

### Code and state sync

- **Git as the transport (recommended default).** The remote box clones the repo from the
  git host (`lado start <git-url>` already exists in `clone.py`), agents push branches;
  the user pulls/reviews PRs locally. No file sync daemon; works everywhere; needs a
  scoped token in the box.
- **Git over SSH to the box**: add the remote container/VM as a git remote
  (`git push lado-remote HEAD`), when the repo is private and the user doesn't want to give
  the box a forge token. Works with plain SSH; DevPod and Coder do similar.
- **Mutagen**: real-time bidirectional file sync over SSH, Docker or k8s exec transports;
  open source (MIT/SSPL split; the core is MIT; Docker acquired Mutagen in 2023 and it
  powers Docker Desktop's synchronized file shares). Good for "edit locally, run remotely",
  but LADO's model (agents edit remotely, user reviews via git) does not need it.
  https://mutagen.io/documentation/introduction
- **rsync over SSH / `docker cp` / `kubectl cp`**: for one-off upload of an uncommitted
  working tree at session start.
- **Volumes**: Docker named volume, k8s PVC, Fly volume, cloud disk: hold `~/.lado`,
  repos and CLI login state; snapshot for backup. Agent CLIs' OAuth logins must be done
  once inside the box (device-code flows) or keys passed as env.

---

## 5. Cost for long, mostly idle sessions

Approximate public prices, 2 vCPU / 4 GB class, Oct 2026 (verify before quoting):

| Option | Billing granularity | Idle behaviour | ~cost of an 8 h session | ~cost always-on month |
|---|---|---|---|---|
| Hetzner CX23/CAX11 VPS | hourly, monthly cap | stopped = still billed; snapshot+delete to stop paying | €0.02-0.03 (but realistically kept monthly) | ~€4-6 (after 2026 increases, unverified) https://docs.hetzner.cloud/whats-new |
| DigitalOcean / Linode / Vultr droplet | per second (DO since 2026? historically hourly) | powered-off still billed | ~$0.15-0.20 | ~$24 |
| AWS EC2 / GCP VM (t4g.medium / e2-medium) | per second (1-min min) | stopped = only disk billed | ~$0.25-0.35 | ~$25-30 + disk |
| Yandex Compute (2 vCPU 20 % + 4 GB) / Selectel | per hour/second; burstable "20 % vCPU" tiers are cheap for idle agents | stopped = disk only (Yandex) | low | ~₽1,000-2,000 (check price lists) |
| Fly Machine (shared-cpu-2x, 4 GB) | per second | suspend: memory saved, pay rootfs $0.15/GB-mo + volume | ~$0.2 if running; ~0 when suspended | ~$20-25 always on https://fly.io/docs/about/billing/ |
| Fly Sprites | active time only | idle = storage only; checkpoints | ~$0.4-0.9 (unverified) | depends on activity |
| E2B | per second | pause stops compute; 24 h window | ~$0.5 | n/a (session caps) |
| Runloop | per second | suspend stops compute | ~$1-2 | n/a |
| Managed k8s | nodes per hour/second + control plane (free on DOKS/LKE basic/Scaleway; ~$73/mo EKS/GKE standard) | scale to zero with Agent Sandbox pause / StatefulSet replicas=0 | node cost | node + control plane |
| Cloud Run / Fargate / ACI | per second (100 ms on Run) | must stay on to keep sessions; no suspend | ~$0.5-1 | ~$40-70 |

Takeaways:
- For **one user's own work**, a small always-on VPS (€5-25/month) beats metered sandboxes
  once sessions are daily; idle CPU is nearly free there.
- For **bursty use** and a **hosted multi-tenant LADO**, suspend/resume with the disk kept
  is the lever: Fly Machines (suspend), Fly Sprites, E2B pause, Runloop suspend, Agent
  Sandbox pause on k8s, cloud VM stop. LADO's state is on disk (SQLite, worktrees), and
  agents are CLIs that can be resumed (Claude Code `--resume`, Codex resume), so
  disk-only suspend (no memory snapshot) is acceptable if LADO's own session resume works
  after a restart - it already does for `lado update` (stop, resume).
- LLM tokens dominate cost anyway: an 8-hour multi-agent session easily spends $10-100
  in tokens versus cents to a dollar of compute. Optimise for portability and isolation,
  not compute pennies.

---

## 6. Comparison matrix

Legend: lock-in L/M/H; isolation per default config; effort = for an end user to get a
first session; fit = long interactive mostly-idle sessions.

| Option | Lock-in | Self-host | Isolation | User setup effort | Fit for long interactive | Cost profile |
|---|---|---|---|---|---|---|
| Docker over SSH (any Linux box, incl. Podman) | L | yes | runc (VM = boundary); gVisor/Sysbox optional | low (box + SSH key) | excellent | cheapest flat (€5-25/mo) |
| Cloud VM via API + Docker over SSH | L-M (provision step only) | n/a | VM | low-medium (API token) | excellent | per-hour/second; stop = disk only (not Hetzner) |
| Kubernetes (StatefulSet/Pod+PVC) | L | yes (k3s) | runc, or gVisor/Kata via RuntimeClass | high unless cluster exists | very good | node cost; scale to zero |
| k8s + Agent Sandbox CRD | L | yes | gVisor/Kata by design | high; alpha | excellent (built for it) | warm pools, pause |
| Nomad | M (BSL) | yes | runc / exec / qemu | high | good | node cost |
| Fly Machines | M | no | Firecracker | low (flyctl + token) | very good (suspend) | per-second; cheap idle |
| Fly Sprites | M-H | no | Firecracker | low | very good | active-only billing |
| Cloud Run / ACI / Fargate | H | no | gVisor (Run)/VM (Fargate) | medium | poor (timeouts, no suspend, clumsy exec) | pay to stay on |
| E2B | M-H (BYOC enterprise / Embed) | partial | Firecracker | low | fair (24 h cap, pause) | per-second, pause |
| Daytona | M (OSS status now unclear) | was yes | container/Sysbox | low | good | per-second |
| Modal | H | no | gVisor | low (Python) | fair (24 h cap) | per-second |
| Runloop / Morph / CodeSandbox(Together) | H | no (Morph: claims yes) | microVM | low | good | per-second/minute, suspend |
| Northflank | M (BYOC) | BYOC | Kata/gVisor | medium | good | per-second |
| Coder (user runs LADO inside a workspace) | L (AGPL, self-host) | yes | whatever the template uses | medium-high (Coder install) | excellent | infra cost |
| DevPod (LADO inside a DevPod workspace) | L (MPL) | yes, client-only | per provider | low-medium | good | per provider |

---

## 7. Recommendation: the minimal set of backends

Principle: **the OCI image is the unit, SSH and the Docker API are the lowest common
denominator, Kubernetes is the portable cluster API.** Everything else is either "a way
to get a Docker host" or "a provider adapter added later on demand".

Define one small backend interface in LADO (in the spirit of the neutral `providers/`
layer, and following "Only what is used"): `create(session, image, env, volume) →
handle`, `start/stop/suspend`, `status`, `exec(cmd) / attach`, `forward(port)`,
`delete`, plus `describe()` for loud capability reporting (e.g. "suspend not supported").

Phase 1 (covers the most targets for the least work):

1. **`ssh` / `docker` backend** - talk to any Docker-compatible daemon through a Docker
   context or `DOCKER_HOST=ssh://...` (Podman via its compat socket). Runs our image
   with a named volume; UI reached with an SSH port-forward that LADO manages; sync via
   git (clone from the forge URL). This alone covers: any VPS (Hetzner, DO, Linode,
   Scaleway, OVH, Selectel, Yandex Compute, VK Cloud, Timeweb…), a home server, a
   corporate VM, an EC2/GCP instance. Zero lock-in, fully self-hostable, cheapest.
   Optional `--runtime runsc|sysbox-runc|kata` passthrough for isolation.
2. **`kubernetes` backend** - one Pod (StatefulSet of 1) + PVC + Service from our image,
   using the user's kubeconfig context; `runtimeClassName` option for gVisor/Kata;
   access via port-forward (or an Ingress the user configures). Covers k3s,
   EKS/GKE/AKS, DOKS/LKE/Kapsule/OVH MKS, Yandex Managed k8s, Selectel, VK Cloud,
   Cloud.ru. Add an **Agent Sandbox** mode (create a `Sandbox`/`SandboxClaim` instead of a
   StatefulSet when the CRDs are installed) once it leaves alpha or a user asks - it also
   gives pause/resume and warm pools for a future hosted LADO.

Phase 2 (only on demand):

3. **VM provisioning helper** for the ssh backend: "create a box with Docker on provider X"
   via cloud-init + one provider SDK at a time (Hetzner `hcloud` and Yandex first for the
   Russian-speaking audience, then DO/AWS), or ship OpenTofu/Pulumi templates users run
   themselves. Provisioning stays outside the backend interface, so switching providers
   = pointing the ssh backend at another host.
4. **Fly Machines** backend if a "zero-ops, suspend when idle" hosted option is wanted:
   Firecracker isolation, per-second billing, suspend/resume, runs our image as is. A
   good candidate for a future paid hosted LADO alongside self-hosted k8s + Agent Sandbox.

Not first: Cloud Run/ACI/Fargate (wrong shape), Nomad (BSL, small audience), sandbox
SaaS (E2B/Modal/Runloop/Morph/Together: proprietary APIs, session caps; revisit for the
hosted offering only). For DevPod and Coder: no integration - document how to run LADO
inside a DevPod or Coder workspace using our image (a devcontainer.json in the docs and a
Coder template example), which gives their whole provider catalogue for free.

Security defaults for every backend: non-root user in the image, no host Docker socket,
scoped git token, secrets passed as env/k8s Secrets (never baked into images),
egress allowlist documented, idle stop/suspend timer in LADO, and a loud warning when
the backend runs plain runc on a shared host.

## Sources (main)

- Docker contexts / SSH: https://docs.docker.com/engine/manage-resources/contexts/ , https://docs.docker.com/engine/security/protect-access/
- docker-py: https://docker-py.readthedocs.io/en/stable/client.html
- Podman service: https://docs.podman.io/en/latest/markdown/podman-system-service.1.html
- Agent Sandbox: https://kubernetes.io/blog/2026/03/20/running-agents-on-kubernetes-with-agent-sandbox , https://agent-sandbox.sigs.k8s.io/docs/ , https://cloudfleet.ai/docs/workload-isolation/agent-sandbox/
- Yandex Managed k8s pricing: https://yandex.cloud/en/docs/managed-kubernetes/pricing
- Selectel: https://docs.selectel.ru/en/managed-kubernetes , https://files.selectel.ru/docs/ru/New-prices-January-15-2026.pdf
- Hetzner 2026 pricing: https://docs.hetzner.cloud/whats-new , https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/
- Fly.io: https://fly.io/docs/about/billing/ , https://fly.io/docs/reference/suspend-resume/ , https://fly.io/sprites , https://fly.io/learn/firecracker-vs-gvisor/
- Cloud Run WebSockets: https://docs.cloud.google.com/run/docs/triggering/websockets
- ECS quotas/exec: https://docs.amazonaws.cn/en_us/AmazonECS/latest/userguide/service-quotas.html
- E2B pricing/limits: https://www.beam.cloud/blog/e2b-pricing-explained , https://blaxel.ai/blog/blaxel-vs-e2b
- Daytona status: https://cdn.jsdelivr.net/gh/nightona-co/nightona@main/README.md , https://helix.ml/blog/self-hosted-agent-sandboxes
- Runloop: https://docs.runloop.ai/docs/devboxes/lifecycle , https://rywalker.com/research/runloop
- Together Code Sandbox: https://docs.together.ai/docs/together-code-sandbox
- Northflank: https://northflank.com/blog/best-platforms-for-long-running-sandbox-environments
- Sysbox: https://github.com/nestybox/sysbox , https://www.docker.com/press-release/docker-accelerates-investment-in-container-security-with-acquisition-of-nestybox/
- Isolation comparisons: https://www.softwareseni.com/firecracker-gvisor-containers-and-webassembly-comparing-isolation-technologies-for-ai-agents/
- DevPod: https://github.com/loft-sh/devpod , https://loft.sh/blog/introducing-devpod-codespaces-but-open-source
- Coder: https://coder.com/docs , https://coder.com/blog/using-coder-agents-to-author-templates-in-coder
- Dev containers: https://containers.dev/ , https://github.com/devcontainers/cli
- OpenTofu: https://opentofu.org/ ; Pulumi Automation API: https://www.pulumi.com/docs/using-pulumi/automation-api/ ; Crossplane: https://www.crossplane.io/ ; Libcloud: https://libcloud.apache.org/
- Tailscale userspace: https://tailscale.com/kb/1112/userspace-networking ; Headscale: https://github.com/juanfont/headscale ; Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- Mutagen: https://mutagen.io/documentation/introduction
