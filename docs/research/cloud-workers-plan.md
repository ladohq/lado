# Cloud workers: the staged plan

Based on: [cloud-workers.md](cloud-workers.md), the research of LAD-100, and its reports
in [cloud-workers/](cloud-workers/) (R1-R4). Approved by the human on 2026-10-18. This plan
is living: it is updated after each step (the status of each step, the decisions taken),
as [docker-install-plan.md](docker-install-plan.md) is; the research report stays as
written.

1. [Decisions taken](#1-decisions-taken)
2. [How the work goes](#2-how-the-work-goes)
3. [Step 0 and stages A-E](#3-step-0-and-stages-a-e)
4. [Technical details](#4-technical-details)
5. [Risks and open questions](#5-risks-and-open-questions)

## 1. Decisions taken

| Question | Decision (2026-10-18) |
|---|---|
| Order | Start with stage A ("the whole of LADO in a cloud") as the continuation of the Docker work (LAD-52), not with split C |
| First targets | A Docker host over SSH and Kubernetes |
| Paid service | Only as BYOK: the user brings their own key or cloud account and pays for the models |
| Contacting the model providers (Anthropic, OpenAI) | Left to the later stages of implementation; not now |
| Where the plan lives | In the repository: this file beside the research, as with Docker |
| Tracker | Only the next task goes to the tracker, each on the human's yes |

## 2. How the work goes

- Each step is a working delivery that leaves the local mode unchanged: an existing user
  notices nothing.
- Only the next task goes to the tracker; after each step this plan is revisited (the
  step's status, what it showed, the decisions taken).
- Each item of stages B-D is a task of its own with the full set of tests (AGENTS.md,
  Testing); behaviour that crosses processes gets integration tests with the fake agent.

## 3. Step 0 and stages A-E

Status of every step: not started.

### Step 0. Checks before the design (hands-on research, no product code)

- **MCP over HTTP:** does it work with a Bearer header in each CLI at its tested version
  (4.3; R1 section 6, items 1-2; R4 4.4).
- **Claude Code's HTTP hooks:** how they behave (R4 4.2).
- **Latency:** a hook's round trip over the network against the 60-second limit (4.3).
- **Codex `auth.json` in a container:** what happens to it when the token is refreshed
  (4.6).
- **Running LADO's image on a remote Docker host:** through `DOCKER_HOST=ssh://`, and in
  k3s (a PVC, a pod restart).
- **The git sync for split D:** push to origin, a separate bare repository of LADO's, or
  fetch from the node (4.5).
- **Legal questions** (only if the paid service idea lives): a letter to Anthropic about
  scenario (b), an application to OpenAI for "Sign in with ChatGPT", a lawyer's advice.
  Decided 2026-10-18: left to the later stages (section 1).

### Stage A. "The whole of LADO in a cloud" (split A; the core does not change)

- **A1. A safe remote UI.**
  - TLS: built in or through a reverse proxy, with a documented recipe.
  - A login to the UI instead of one token in the URL.
  - Limits on the terminal WebSocket: it gives the browser a shell's rights.
  - This part is closed first, before anyone is invited to the cloud.
  - Details: R1 C10, C11 (`server/auth.py` is the one place to change; its docstring
    already expects "a real login and TLS").
- **A2. Repositories from a git URL as the main path in the cloud** (cloning already
  exists: `clone.py`, `server/clones.py`). A persistent volume `/home/lado` for the state,
  the logins and mise. Details: R1 C14, C16 (clone), split A.
- **A3. Launch recipes.**
  - compose for a remote Docker host (a VPS);
  - a Helm chart or manifest for Kubernetes (a one-pod StatefulSet plus a PVC: SQLite
    allows one replica only);
  - `devcontainer.json` for DevPod, Coder and Codespaces;
  - documentation "LADO on a VPS" and "LADO in Kubernetes".
- **A4. Logins in the "box".** `CLAUDE_CODE_OAUTH_TOKEN` or API keys through
  `LADO_ENV_DIR` or k8s secrets; Codex: T15 of the Docker plan. Details: 4.6.

**Result of stage A:** a user brings LADO up on any VPS or in any Kubernetes in 10-15
minutes, with all the CLIs, and works from a browser. The local install does not change.
The stage continues the Docker epic LAD-52.

### Stage B. Inner seams (refactoring with no change of behaviour)

- **B1. The "execution backend" interface below `providers/`.**
  - Operations: launch, type text, attach a terminal, is it alive, stop.
  - tmux becomes the first implementation; behaviour does not change.
  - The interface is designed together with the future ACP runtime (ROADMAP stage 8).
  - Details: 4.2.
- **B2. A token for each agent**, based on `agents.instance`. LADO's MCP server is also
  reachable over HTTP; locally it stays stdio. Details: 4.3.
- **B3. Hooks:** events delivered through LADO's API as an alternative to writing SQLite
  directly. For remote agents the control plane is the only writer to the DB. Details:
  4.3.
- **B4. The "launch bundle":** a provider assembles the configs, the prompt and the skills
  into a portable bundle instead of writing paths in `LADO_HOME`. Details: 4.4.

**Result of stage B:** locally everything is as before, but a remote node can now be
connected. Each item is a task of its own with the full set of tests.

### Stage C. A remote node for a session (split C)

- **C1. `lado node`:** a daemon on the node. It holds tmux, the worktrees and the CLIs and
  connects to the control plane over an **outbound** connection, so NAT and pods are no
  obstacle. A protocol version check. Details: 4.3.
- **C2. The "Docker over SSH" backend:** any VPS, with a gVisor or Sysbox option.
- **C3. The Kubernetes backend:** a pod plus a PVC, then the agent-sandbox mode (pause,
  warm pools).
- **C4. The agent's terminal in the UI through the node.** Stopping, resuming and updating
  nodes. Details: 4.2 (`open_terminal`), 4.3 (terminal relay, version check).
- **C5. Choosing the place at session start:** `lado start --on <backend>` and the same
  choice in the UI. The backends' config in `~/.lado`; secrets are kept as references.

**Result of stage C:** the UI and the data stay with the user, the agents' heavy work runs
in a cloud; the cloud is changed by one setting.

### Stage D. Mixed sessions (split D; only if needed)

Single workers are placed remotely (`spawn_worker(..., placement=...)`), branches are
synced through git, with heartbeats and a node registry. The most expensive stage; the
decision is taken after C. Details: 4.5, and R1 split points C and D.

### Stage E. A paid service (an idea only; decided after A-C and the lawyers' answer)

- Multi-tenancy: per session or a "box" per user, VM-level isolation.
- An outbound proxy with BYOK keys, and a GitHub App.
- Metering and billing based on the log of usage events.
- Sign-up and login.
- First test on the market a cheap variant: a "managed box" (stage A, deployed by us for
  the user). A cloud platform of its own is built later.
- Details: 4.6 (terms per CLI, secret handling).

## 4. Technical details

Condensed from the reports; each subsection names its origin. Open the report for the
evidence and the sources. R1 letters its split points differently from the research
report and this plan: R1's C ("remote worker only") is split D here, and the "session on
a remote node" variant of R1's D is split C here.

### 4.1 Couplings to one machine (R1 sections 2-3)

The code references are those of R1, taken at `main` 033705e (2026-10-18); the line
numbers may have moved since. Today LADO is a set of cooperating local processes that
share one SQLite file, one tmux server and one filesystem directly; no daemon owns the
state, and control-plane logic (spawning workers, worktrees, typing messages into tmux)
runs inside `lado mcp` and `lado hook`, children of the agent CLI.

| # | Coupling | Main refs | Today | Breaks if the agent is remote | Seam | Size |
|---|---|---|---|---|---|---|
| C1 | Process lifecycle via tmux | tmux.py :165-255; runtime.py :750, :870, :1238, :2205, :2368 | local `tmux -L lado` subprocess; window = agent | no window; the loop marks the agent stopped | `ExecutionBackend` (launch/alive/kill/type/terminal); tmux kept on the node | M |
| C2 | Typed delivery | runtime.py :1902-1960; tmux.py :239 | paste into the pane from any process | no pane | `backend.type_text`; the queue stays central | S (after C1) |
| C3 | Hooks write SQLite | base.py :277-293; hooks.py :141-297 | a Python process per event, direct DB + tmux + git | no DB/tmux; wrong interpreter path | hook shim → HTTP → `hooks.handle` on the server; fingerprint on the node | M |
| C4 | MCP over stdio, core in-process | mcp_server.py :1-5, :437; base.py :296 | stdio child of the CLI runs runtime/runs | no DB; identity by env is not auth | remote MCP (HTTP + per-agent token) or a stdio proxy | M |
| C5 | Session loop | loop.py :82-143; runtime.py :2205 | detached local process, flock | its window check and typing | uses the backend; heartbeats for liveness | S |
| C6 | Git worktrees share one repo | runtime.py :827-887, :1152-1338; runs.py :84-89, :431, :936 | linked worktrees; the supervisor merges locally | commits invisible; work state and finish fail | `Workspace` (create/state/remove/sync); clone + push/fetch | L |
| C7 | SQLite with many writers | state.py :1-5, :1147-1190 | WAL, many processes | cannot be shared across hosts | the control plane the only writer; RPC for remote | M (falls out of C3/C4) |
| C8 | LADO_HOME paths, config folders, skill symlinks | base.py :240-313; claude.py :140-201; codex.py :193-216; opencode_family.py :115 | the provider writes files and an absolute argv | paths and symlinks absent on the node | render a `LaunchBundle` + the backend materializes it | M |
| C9 | Environment and credentials from the local login shell | agent_env.py :98-389; runtime.py :2769-2850; claude.py :247, :312; codex.py :278; gui_session.py | `$SHELL -ilc` + keychain + home files | wrong host; no logins | the backend resolves the env on the node; secrets through the `LADO_ENV_DIR` contract | M |
| C10 | Terminal = local pty + tmux attach | terminal.py :74-224; server/terminals.py | the UI server attaches locally | nothing to attach | `backend.open_terminal` stream; relay through the node agent | M |
| C11 | The UI server runs the core in-process | server/app.py; auth.py; run.py; feed.py :52 | token over HTTP, `--host` | n/a for a remote UI; derived status uses tmux | control-plane API; TLS and login in front | S (UI) / M (agent API) |
| C12 | Providers assume local | base.py :97-299 | files + local paths | see C3/C4/C8/C9 | pure render; remote `McpServer`; checks on the node | M |
| C13 | Artifacts | artifacts.py :170-213; artifacts_local.py | `Store` protocol, local backend | only the `file=` argument | already abstracted | S |
| C14 | Docker image | docker/* | one box for everything | n/a | reuse as the node or session image | — |
| C15 | Start/stop/resume/update | runtime.py :624, :2368, :2466; self_update.py; runs.py :445 | local only | nodes not provisioned or stopped; version skew | backend provision/teardown; protocol version | M |
| C16 | Logs, clock, interpreter path, clone | telemetry.py; interpreter.py :21; clone.py | local | lost logs, clock skew | ship to the control plane; the server's clock | S |

### 4.2 The execution backend interface (R1 C1, C2, C5, C9, C10, C15)

A sketch for B1, below `providers/`, with exactly the verbs the core uses today:

- `start_session_host(session)`, `launch(agent, cwd, argv, env_file)`, `alive(session) ->
  set[agent]`, `kill(agent)`, `kill_session(session)`, `type_text(agent, text)`,
  `open_terminal(agent, mode)` (a byte stream with write and resize: the surface of
  `terminal.Terminal`);
- for remote targets also `provision(session)` / `teardown(session)`, and the checks run
  on the target: `resolve_env()`, `check_commands()`, the provider's `first_hook_blocker`
  and `keychain_login`;
- the research's principle 2 names the operations as the user sees them: create,
  start/stop/pause, status, exec/attach, port forwarding, delete.

Implementations:

1. **tmux** (first): today's `tmux.py` calls verbatim (about 8 functions); behaviour does
   not change.
2. **A remote node** (next): tmux runs **on the node**, driven by a node agent (or `ssh
   host tmux ...`, `kubectl exec`, Docker `exec`). Keeping tmux on the far side keeps what
   the providers rely on (the TUI, typed delivery with its hand-checked bracketed paste and
   Enter timing, `/resume`, the human's terminal).
3. **An ACP runtime** (ROADMAP stage 8): a third implementation of the same interface, not
   a rewrite; an agent without a terminal raises `NoTerminal`, as the UI already expects.

Each backend says loudly what it cannot do (No silent drops). The message queue and its
planning stay in the control plane; only the last mile (`tmux.send_text`) goes through
`backend.type_text`. The `hook_output` channel needs no tmux at all. The session loop
stays on the control plane and calls `backend.alive()`; for remote nodes liveness is a
heartbeat (the node reports its windows every N seconds), and "missing in two passes" stays
the rule.

### 4.3 The node protocol (R1 C3, C4, C5, C7, C10, C11, C15, C16; R4 4.2, 4.4)

- **One channel, opened by the node.** The node agent (`lado node`) connects to the
  control plane over an outbound, authenticated connection (WebSocket or gRPC), so nodes
  behind NAT and in pods work; the control plane on a laptop is usually unreachable from a
  pod.
- **Hook forwarding.** The hook command becomes a thin forwarder (`lado-agent hook
  <native>`, or a stdlib-only script) that POSTs `{session, agent, instance, native,
  payload}` to the control plane and prints the response body; `hooks.main`/`handle` run
  unchanged on the server (`parse_event` is pure). The read-only fingerprint needs the
  worktree, so the node computes it and sends it with the event; the server compares.
  The wait for `MCP_READY` (polling in the hook today) becomes a wait on the server. The
  turn-end hook must answer well inside its 60 s; an HTTP round trip fits, step 0
  measures it. Claude Code also has native `http` hooks (gated by `allowedHttpHookUrls`),
  but Codex and the OpenCode-family plugin need the command shim anyway, so the shim is
  the neutral choice.
- **MCP over HTTP with a per-agent token.** The control plane serves LADO's MCP tools as
  streamable HTTP at `/mcp`, with a bearer token derived from `(session, agent,
  instance)`: `agents.instance` already fences off older launches. All four CLIs have a
  remote MCP form with headers: Claude Code `type: http` with `headers`, Codex `url` with
  `bearer_token_env_var` / `http_headers`, OpenCode and Kilo `type: remote` with
  `headers`. Bearer headers, not OAuth: headless OAuth is awkward in Claude Code.
  `McpServer` gets a URL-and-headers form. `write_artifact(file=...)` reads a path on the
  node, so it needs a small node-side helper or the agent sends `content`. The
  alternative is a stdio proxy (`lado mcp` stays a stdio process on the node and forwards
  JSON-RPC): nothing changes in the providers' configs, and it reads local files.
- **The control plane is the only writer of `lado.db`.** SQLite WAL needs shared memory
  on one host; a remote process cannot be a writer. The `state.*` / `runtime.*` calls of
  hooks and MCP are the RPC surface (hook event, MCP tool call, heartbeat, fingerprint
  result). No remote DB and no Postgres for this.
- **Heartbeats.** The node reports its live agents every N seconds; the loop's rule
  "missing in two passes" applies to the heartbeat instead of `tmux list-windows`.
- **Terminal relay.** The node agent opens the viewer and `tmux attach` locally and relays
  the bytes over its channel to the UI server; the WebSocket protocol to the browser is
  unchanged. `lado attach` goes through the same relay (or prints the `ssh` / `kubectl
  exec` command). Popups are tmux-only and optional.
- **Protocol version check**, modelled on `SchemaError`: the control plane and the node
  agree on a protocol version and refuse a skew loudly; `lado update` must update the
  node images too.
- **One clock:** `seen_at`, `sent_at` and `resume_at` use the control plane's receipt time
  across machines.
- **Errors and logs:** the node ships them to the control plane, or `lado bug-report`
  loses them.
- **Agent-facing routes** (`/agent/hook`, `/agent/mcp`, `/agent/heartbeat`,
  `/agent/terminal`) sit behind per-agent tokens, apart from the UI's login.

### 4.4 The launch bundle (R1 C8, C12)

`Provider.launch_command` today writes files and returns an argv with absolute local paths
(config files, skill symlinks, `sys.executable`). For B4 it splits in two:

- **render** (pure, in the provider): a `LaunchBundle` of `{relative path -> bytes, mode}`,
  the argv with placeholders such as `${CONFIG_DIR}` and `${LADO}`, and the environment;
- **materialize** (in the backend): writes the bundle under a root on the target and
  substitutes the placeholders. Locally that is today's `LADO_HOME/agents/<session>/<agent>`.

Skills become bundle content (copied, or a content-addressed sync of the kit cache to the
node) instead of symlinks. `hook_argv` takes "LADO's entry point on the target" instead
of `sys.executable`. `env.json` holds secrets, so it is not shipped as is: secrets reach
the node through the `LADO_ENV_DIR` contract (4.6). This also follows AGENTS.md's rule "no
hardcoded paths". Kilo and OpenCode already take their config as environment content
(`*_CONFIG_CONTENT`), file-free except for the skills.

### 4.5 Git for stage D (R1 C6; R1 section 6, item 4)

Today the supervisor works in the human's checkout and workers in linked worktrees of it,
so a worker's commit is visible to the supervisor at once and it merges with a plain `git
merge`; `finish_worker` refuses until `merge-base --is-ancestor` says merged. A remote
worker breaks all of it. The seam is a `Workspace` interface: `create(session, agent|run,
base_ref) -> handle`, `state(handle) -> WorkState`, `remove(handle, force)`,
`exists(handle)`, plus a **sync** step for the branch; the local implementation is today's
linked worktree. The remote one gets a **clone** (from a remote the node can reach, or a
`git bundle` through the node agent), works on `lado/<s>/<w>`, and the branch comes back
by one of:

1. **push to origin**: no new infrastructure; needs write access on the node and
   publishes work-in-progress branches;
2. **a bare repository the control plane exposes**: private to LADO; one more service to
   run and secure;
3. **fetch from the node into the human's repository** (`git fetch node:<branch>`) at turn
   end or on `finish_worker`: no credentials on the node for pushing; needs the node
   reachable through the node agent.

Merge semantics stay "the supervisor merges a branch", only after a fetch; work state is
a node RPC or is computed after the fetch. Step 0 chooses, including how `finish_worker`'s
"merged" check behaves after a fetch. Stage C avoids all of this: with all agents of a
session on one node, linked worktrees still work there and the human pushes and pulls
through origin.

### 4.6 Credentials and terms per CLI (R4 1.1-1.4, 2.6, 3)

Scenarios: (a) own cloud, own subscription; (b) hosted, the user's subscription; (b')
hosted, the user's API key or cloud credentials; (c) hosted, the operator's keys, resold.

| CLI | (a) | (b) | (b') | (c) |
|---|---|---|---|---|
| Claude Code | Yes (setup-token or `/login`; "ordinary individual usage") | Narrow yes: an unmodified binary, the user signs in through Anthropic's flow, the operator never collects or stores tokens; Commercial Terms; get a written OK | Yes | **No** without a separate Anthropic agreement |
| Codex | Yes (one `auth.json` per machine; an API key recommended) | Only through Sign in with ChatGPT approval for paid or hosted apps | Yes | Likely yes through the API (Services Agreement); confirm |
| OpenCode | Yes | Depends on the provider (Anthropic: no; OpenAI: SIWC) | Yes | Not with Zen/Go ("own internal use"); through a provider's API per its terms |
| Kilo | Yes | Unclear (seat rules) | Yes | Kilo's terms allow serving end users through its API |
| Gemini CLI | API key or Vertex only | **No** (explicit ban on reusing its OAuth) | Yes | Through the Gemini API or Vertex terms |
| Copilot CLI | Yes (own PAT) | Seat-sharing risk | n/a | No |

Logins per CLI:

- **Claude Code** (R4 1.1): `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token` is static
  for a year, model requests only, and as a static bearer can be set in many containers
  (R4's reading; all of them count against one plan's limits); a `/login` credential (`~/.claude/.credentials.json`, mode 0600) refreshes and
  rewrites itself, so copying it to several containers risks refresh races; a login in a
  container pastes a code. `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` route through a
  gateway or proxy; `apiKeyHelper` fetches short-lived keys; Workload Identity Federation
  (Kubernetes projected service-account tokens) is the best fit for k8s, API billing only.
- **Codex** (R4 1.2): ChatGPT login, API key, or Enterprise access tokens; headless through
  `codex login --device-auth`. OpenAI says outright not to share `auth.json` across
  concurrent jobs or machines; it is refreshed and written back (about every 8 days in
  CI), so it must persist. One ChatGPT login per container, or an API key for fleets;
  the Docker image's "log in once inside, keep it on the home volume" fits one container,
  not N replicas on one volume.
- **Kilo** (R4 1.3): `kilo auth login` (OAuth for OAuth-capable providers) or API keys
  through the environment (`KILO_API_KEY`, `KILO_PROVIDER`, `KILO_ORG_ID`) and `{env:...}`
  in config; auth in `auth.json` under the data folder.
- **OpenCode** (R4 1.4): `/connect` keys in `~/.local/share/opencode/auth.json`, env vars,
  `{env:...}` / `{file:...}` in `opencode.json`; Bedrock, Vertex, Azure, OpenRouter and any
  OpenAI-compatible endpoint. Claude Pro/Max through OpenCode is prohibited by Anthropic.

Secret handling (R4 3):

- **Injection:** secrets as mounted files rather than env vars, matching `LADO_ENV_DIR`
  (one file per variable) and Kubernetes or Docker secrets; short-lived credentials where
  the vendor supports them; one credential per container for refreshing logins.
- **Out of the agent's reach** (for stage E): an egress proxy holds the real keys and
  injects them into matching requests (TLS terminated by its own CA, default-deny
  allowlist); the agent gets a placeholder. It works for API keys (`ANTHROPIC_BASE_URL`,
  Codex `model_providers` with `env_key`, OpenCode/Kilo `baseURL`); a subscription's OAuth
  token must sit in the container, and a proxy swapping it is the "intermediating"
  Anthropic forbids.
- **Git:** for a hosted LADO a GitHub App with one-hour installation tokens narrowed to
  the repository, served through a credential helper that calls the control plane; deploy
  keys or a forwarded ssh agent for single-repo self-hosting; a fine-grained `GH_TOKEN`
  (today's default) is fine for scenario (a).
- **Egress:** a default-deny network policy plus an allowlisting proxy (model API, git
  host, package registries, MCP hosts, the vendors' token endpoints).

## 5. Risks and open questions

### Risks

- **SQLite with many writers** does not carry across hosts: a single writer (B3), not a
  remote DB.
- **Git** is the largest hole for split D; it stays closed before stage D (4.5).
- **The UI on a network** is HTTP with a token, and the terminal is in effect a shell: A1
  comes before any cloud recommendation.
- **Subscriptions:** Pro/Max limits assume ordinary individual usage; many parallel agents
  on one subscription may hit them or bring sanctions.
- **An unstable sandbox market:** rely on OCI, the Docker API and the k8s API, not on
  vendors.
- **The network from Russia:** Cloudflare Tunnel and Tailscale may be unreachable; the
  base path is an SSH tunnel or Headscale.
- **Hook latency** against the 60 s turn-end limit (step 0).
- **A lost node mid-turn** needs new `agent_ended` reasons; partial failures are new to
  LADO (R1 split C).
- **The laptop as the control plane** must stay up and reachable for splits C and D (R1
  split C).
- **Two implementations of every backend verb** to test: today's integration tests
  assume one machine (R1 split D).
- **Provider configs checked by hand per CLI version** need checking again with remote
  MCP (R1 split C).

### Open questions (all: decide later)

- **An example on a Russian cloud** (Selectel, Yandex) as a checked target next to the
  Docker host and Kubernetes.
- **Running step 0 as a separate session by brief**, as in the Docker epic.
- **The legal questions of stage E:** writing to Anthropic about scenario (b), applying to
  OpenAI for "Sign in with ChatGPT", a lawyer's advice; left to the later stages of
  implementation (section 1).
