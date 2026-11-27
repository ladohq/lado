# Review of the plan "Session isolation as the first step to a cloud" (version 1)

Archived input to the [session isolation plan](../session-isolation-plan.md), 2026-11-27;
translated from Russian, numbering kept (K1-K14 here are the review's points). Plan
version 1 (`isolation-roadmap.md`, a session artifact) is not kept; its stage and step
numbers (stage 1, steps 1.1-1.8 and so on) refer to it.

Date: 2026-11-27. A review to hand to the agent who leads the plan.

**What was reviewed:** `isolation-roadmap.md` (the plan), A1 (code seams), A2 (prior art),
A3 (critical review of the spikes). A few claims were checked against the code of `main`
1e565441.

**What I did not read:** `docs/research/session-isolation.md` and the reports S1-S4. All I
know about the spikes comes from A3's and the plan's retelling.

**How to read:** in section 2 the points are numbered (K1…K14) and ordered by importance.
Each has a "What to change". Section 3 is the proposed sequence. Section 5 lists the
questions the plan must answer before the start.

---

## 1. Verdict

The plan gets the main thing right: the bulk of the work is the seams in the code (the
Agent API), not the sandbox, and they come first. Three decisions I support without
reservation: the runner connects to the panel itself; the ladder "as today → runc →
runsc"; the old mode stays supported.

There are five weak spots:

1. **The path to a cloud goes through the heaviest stage.** The remote runner (stage 5)
   comes after "isolation by default locally" (stage 4), though it does not depend on it.
   The stated goal is a cloud, but the critical path runs through nested gVisor on three
   OSes.
2. **Parts without which a cloud does not work fell out of the plan:** protection of the
   panel (TLS, login, terminal), a backup of `lado.db`, agents' conversations continuing
   after a restart, the launch bundle, delivery semantics on disconnects.
3. **There is no threat model.** Without one it cannot be checked that the "isolation" of
   each stage closes anything. Several steps give a feeling of protection that is not
   there yet (1.1, stage 2, bind mode).
4. **Stage 1 is ordered so that the riskiest step (1.4) comes before the boundary exists
   (1.7),** and the transport of 1.7 is a temporary one, not the one of the target design.
5. **Two steps are infeasible or underestimated as worded:** 2.3 (short-lived per-repository
   tokens with PATs) and 3.1 (one step of size L that hides five).

---

## 2. Points

### K1. The cloud is blocked by local isolation by default (critical)

Stage 4 requires closing E1-E7, a many-hour run and a release cycle of dogfooding. These
are the plan's longest gates. Stage 5 (the remote runner) does not depend on them: it needs
stage 1, 3.1-3.3 and a protected panel.

Besides, nested gVisor is mostly a local problem. In a cloud the sandbox per session comes
from the orchestrator: a pod with a RuntimeClass (gVisor or Kata) or a separate VM. There is
no need there for a privileged runner with `SYS_ADMIN`, an AppArmor profile, or a seccomp
profile maintained for each engine version. So the most expensive engineering part of the
plan (3.5, E3, E6, E7) is hardly needed by the cloud.

**What to change:**
- Split into two tracks after 3.3: "cloud" (the remote runner, then k8s) and "local
  isolation" (runsc, stage 4). They run in parallel and neither waits for the other.
- Introduce a "sandbox provider" interface with two models: nested (the runner starts
  runc/runsc itself) and external (an orchestrator gives a pod or a VM per session).
  Otherwise 5.3 turns into a rewrite of 3.3-3.5.

### K2. There is no threat model (critical)

The plan says "isolates" but not from whom or what. The three analyses yield at least four
attackers: an agent under prompt injection, a malicious dependency or repository, a
neighbouring session, another user (stage 6).

**What to change:** add a "threat × stage" table to the plan: which threat is closed after
stage 1, after runc, after runsc, and which is never closed (for example, a leak through
allowed hosts: a push to `github.com` with someone else's token). Word the stages' done
criteria by this table. Show the session's protection level in the UI.

### K3. The per-agent token of step 1.1 is no boundary before step 1.8, and never between agents of one session

- Before 1.8 the agent reads `LADO_HOME`, and so the HMAC key. It can mint any agent's
  token. A "token forgery" test does not catch this and creates false confidence.
- In the target design all agents of a session live in one sandbox under one uid. A worker
  will read the supervisor's token from its environment or config. The real boundary is the
  session, not the agent.

**What to change:**
- In 1.1 write it plainly: before 1.8 the token is identification, not protection.
- Design permissions from the session: any Agent API call from a session must be safe with
  the supervisor's token in the hands of any of its processes.
- Check all the supervisor's tools by this rule. `start_session` already requires the
  human's answer (`runtime.start_approved_session`, 2312), which is the right model; check
  `spawn_worker` (which secrets the worker gets), `list_models`, `flow_*` the same way.
- Keep the HMAC key where the agent cannot reach it after 1.8, and provide for its rotation.

### K4. The order of stage 1: step 1.4 before boundary 1.7

Step 1.4 moves the tools' heavy work "out of the agent's process into the core". But before
1.7 there is no other process: the call runs inside `lado mcp`. So 1.4 before 1.7 only
rearranges functions, and the real move (secrets, `git worktree`, tmux, starting the loop
leave the agent's tree) happens all at once when the socket is switched on. That is the
riskiest moment of the plan, and it is hidden in a switch.

**What to change:**
- Order: 1.1 → 1.2 → 1.3 → **1.7 (a socket for the simple calls)** → 1.4 one tool per
  release (`list_models` → `finish_worker` → `spawn_worker` → `start_session`) → 1.5 →
  1.6 → 1.8.
- For long operations (`spawn_worker` runs `$SHELL -ilc`, a worktree, tmux) define
  timeouts and an operation id: across the boundary they stop being an ordinary function
  call.

### K5. The Agent API in `lado loop` is a temporary transport with three problems

Checked against the code: `loop.run` (loop.py 151) is a single-threaded polling loop with a
pass every interval.

1. **Concurrency.** The hook waits for MCP_READY up to 20 s, the end of a turn up to 60 s. A
   request server in a single-threaded loop will not serve them. A separate thread or
   process is needed, and that changes the loop's assumptions (flock, `home_not_made`).
2. **A single point of failure.** Today the hook writes the database itself and does not
   depend on the loop. After 1.7 a crashed loop means a lost event. The plan says "the hook
   fails loudly and exits 0"; then a lost end of turn leaves the agent "busy" forever.
3. **The wrong process.** In the target design the Agent API is served by the runner's
   gateway and the panel, not by the session loop. The socket in the loop would have to be
   thrown away.

**What to change:**
- Choose a process that serves the Agent API in both modes. A candidate is a separate
  daemon per machine (A1 calls it `lado agentd`): locally it is the future panel, in the
  runner the gateway.
- Build into the protocol from the first release: a version, an event id, retries without
  duplicates. Version skew happens already locally: `self_update` changes the code under
  running agents.
- On the hook client's side, a short on-disk queue with retries, so that an event survives
  a server restart.
- Write honestly in the plan: 1.7 does not make the panel the only writer of `lado.db`. The
  UI server, the CLI and the loop still write. The single writer appears only with the
  runner.

### K6. Git: "ignore the repository's config" is an unreliable protection

The finding about `.git/config` is right and important. But step 1.6 treats it with a deny
list, and the list is incomplete by construction: `core.fsmonitor`, `core.hooksPath`,
filters through `.gitattributes`, `diff.external`, `core.sshCommand`, `core.pager`, aliases,
`include`/`includeIf`, `credential.helper`, `gpg.program`, `url.*.insteadOf`. Each new git
version may add an item.

**What to change:**
- The rule: the trusted side never opens a repository directory the sandbox has written to.
  It either asks the sandbox to run git and return the result as data, or talks to it over
  the git protocol (`upload-pack` runs inside the sandbox).
- The fingerprint, `merge-base --is-ancestor`, the work state and the merge run inside the
  sandbox through `Workspace`. Their results are untrusted: "merged" is checked on objects
  obtained by fetch.
- Remove `safe.directory '*'` from the panel's image (Dockerfile:148), as the plan says.
- **Separately about bind mode (the plan's question 3):** if the working tree is visible on
  the host, the agent's code will be run by the user's own git or IDE. That is true today
  too. So bind mode protects from neighbouring sessions and closes the network, but does not
  protect the host from the agent. Write exactly that in the UI and the documentation.

### K7. Step 2.3 is infeasible as worded

"Short-lived per-repository tokens" are issued only by a GitHub App. Today Settings → Git
servers holds the user's personal tokens for GitHub, GitLab and GitHub Enterprise (0.48.0).
A personal token cannot be narrowed to a repository and a lifetime. For a self-hosted
install it is unclear who owns the App.

`gh` and `glab` are not covered: agents open PRs and MRs with them, which needs an API
token, not only git. Today it sits in the environment (`GH_TOKEN`).

**What to change:**
- Split 2.3 into two independent steps:
  1. the token does not sit in the sandbox: git goes through a relay of the trusted side,
     which injects the token (works with any server and a personal token);
  2. a GitHub App with one-hour tokens as an option, mostly for stage 6.
- For `gh`/`glab` decide: either an API proxy that injects the token, or "open a PR"
  operations become Agent API tools and the CLI in the sandbox gets no token. Until then,
  write honestly that the API token stays in the sandbox.
- Do the branch checks on push in the relay, not in the CONNECT proxy (A3 2.2).

### K8. Step 3.1 is five steps, and the launch bundle is missing from the plan

3.1 (size L) hides: two images, runner registration, a versioned protocol, a lease and
heartbeat, materializing the agents' configs on the runner, the environment and checks on
the runner's side, placing the repositories. The launch bundle (A1, seam 7, size L across
four providers) is not named in any stage, and without it no session starts in a runner.
Nor is the move from absolute host paths in the database (`agents.cwd`, `runs.worktree`,
`sessions.repo`) to paths relative to the runner (A1 4.1).

**What to change:** split 3.1:
1. the launch bundle: a pure render in the provider and a materialize in the backend,
   locally with no change of behaviour (a step of stage 1);
2. paths as references relative to the place of execution;
3. the runner → panel channel: registration, mutual authentication, protocol version;
4. lease, heartbeat, fencing (see K9);
5. starting a session in the runner without a sandbox.

### K9. The lease and heartbeat are copied from a model that does not fit LADO

At Anthropic a session whose lease expired can be put back in the queue: its state comes
back by a fresh clone. A LADO session is tied to its place: tmux, worktrees, a volume. The
plan does not answer:

- What does the panel do when the lease expires? The session cannot be raised elsewhere
  without the volume.
- What if a "lost" runner comes back after the panel has declared the session stopped or
  raised it again? Two instances of the agents will type and push at once.
- What does the runner do with events while the panel is unreachable (a panel update, a
  network break)?
- How is a message delivered to an agent if the break happens mid-delivery?

**What to change:** add a "failure semantics" section to the plan:
- fencing by epoch: `agents.instance` already cuts off old launches; the same trick is
  needed at the session and runner level;
- "at least once" delivery plus event ids, processing exactly once;
- an event buffer on the runner while the panel is unreachable;
- new reasons for an agent's end (`runner_lost`), visible to the human;
- a panel update does not kill the sessions in runners.

### K10. Cloud prerequisites fell out: panel protection, backup, continuing conversations

- **The panel on a network.** In 5.1 the runner connects to the panel, so the panel is
  reachable over the network. The plan has no TLS, no login instead of a token in the URL,
  no limits on the terminal's WebSocket (`server/auth.py` itself calls the token over HTTP
  "a risk accepted until a real login and TLS"). The wording "the user specifies the
  connection" hides the case "panel on a laptop behind NAT, runner on a VPS": who can dial
  whom?
- **A backup of `lado.db`.** With runners the panel is the only owner of the state of all
  sessions. Losing the panel's disk loses everything.
- **Continuing conversations.** Per the ROADMAP, after `lado stop` + `lado start` agents
  start new conversations. A3 (3.6) notes that an update of the runner's image, `docker
  compose restart` or a Docker Desktop restart kill all sessions at once. With isolation,
  restarts become more frequent (runsc updates), so storing the conversation id and
  continuing with `--resume` is needed before stage 4.
- **Loss of unpushed work.** "WIP push on stop" does not fire on a crash. A periodic
  snapshot is needed. Where to: pushing WIP branches to origin publishes unfinished work, so
  most likely a bare repository on the panel's side is needed.

**What to change:** add these four items as steps with gates: panel protection before 5.1,
continuing conversations and the periodic snapshot before stage 4, the backup before 5.1.

### K11. Stage 0: no decision criteria, and several experiments missing

The plan itself admits that the past conclusions were too optimistic. So that this does not
happen again, the threshold must be written down before the experiment.

**What to change:**
- For each E, a threshold and the decision on either side. An example for E1: "if on a
  volume the read-only role's fingerprint does not fit in 2 s on LADO's repository, the
  fingerprint moves to an asynchronous check, or bind mode does not support runsc".
- For each E, a list of platforms. A volume on macOS is in table 2.2 but tied to no E.
- Add experiments:
  - **a runc step** (A3, section 4.1): the same runner, `runc` instead of `runsc`, the
    isolation table. The ladder rests on it, and there is no check;
  - **cgroups per sandbox** under runsc (`--ignore-cgroups`): without limits one session
    kills the runner and all the others;
  - **hook latency over the network** against the 60 s limit, for a remote runner;
  - **continuing a conversation after a runner restart**, for each CLI;
  - **Docker Sandboxes** as a path for macOS and Windows (A3 4.2: not tried; an hour of
    work).
- Run E1 first and before 1.5: its result affects the shape of the backend interface.

### K12. The interfaces are designed for a single implementation

Steps 1.5 and 1.6 derive the interfaces from today's tmux and git calls. That yields an
interface convenient for the local backend: synchronous, with absolute paths, polling
`alive`. A remote implementation will find this out in stage 3, when changing it is
expensive.

**What to change:**
- After 1.3, build a throwaway end-to-end prototype on a separate branch: the fake agent,
  the Agent API over a socket, a second backend in a separate container without a sandbox.
  The goal is to check the shape of the interfaces of 1.4-1.8 and of the protocol before
  polishing them. It is not merged into main.
- Have a second backend in the tests from the start: out of process, with delays and
  failures. A common contract test for all implementations.

### K13. "The integration tests pass unchanged" does not prove that the boundary holds

It proves there are no regressions. The boundary is proved by negative tests.

**What to change:** a permanent CI cell "boundary" as the acceptance criterion of the whole
of stage 1:
- the agent's process tree runs under a separate uid (or under Landlock) that cannot reach
  `LADO_HOME`, the tmux socket and the secret files; all of the integration suite passes;
- a canary test: the values of another project's secrets and of other git servers are found
  neither in the environment nor in files the agent can reach;
- `write_artifact(file=)` outside the agent's folders is refused (today it takes any path:
  A1, C13).

A separate uid for agents is a cheap, self-standing step of the ladder even before
containers: on Linux and in today's image it gives real protection of the panel's files.

### K14. Estimates and release rhythm

- Sizes are given in "agent work days". The bottleneck is not the agent but the human's
  review and yes on each task. The plan has more than 25 separate releases; the user sees
  nothing of the first eight.
- 3.4 (logins per sandbox, M) is underestimated: a new UI, token refresh races, and for
  Codex a separate login for each session. It is a noticeable step back for subscription
  users, who are probably the majority locally.
- The stage 2 proxy has no designed user flow for a refusal: the agent needs a host outside
  the list; what does the human see, how do they allow it, per session or per project? The
  main technical point is not settled either: without TLS interception the proxy sees only
  host names, so injecting keys is possible only through each CLI's base URL.

**What to change:** group the steps into milestones with visible value and shared gates;
raise 3.4 to L and bring its UI design forward; add a step "the refusal and permission
flow" to stage 2.

---

## 3. Proposed sequence

| Milestone | Content | Gate |
|---|---|---|
| M0 | Experiments with thresholds (K11); the threat model (K2) | the human's decisions on the thresholds |
| M1 | 1.1, 1.2, 1.3; a throwaway end-to-end prototype (K12) | the shape of the Agent API and the backend approved |
| M2 | The Agent API in a persistent process (K5); 1.4 one tool at a time; 1.5; 1.6 with the rule "do not open someone else's repository" (K6); the launch bundle; 1.8 | the CI cell "boundary" green (K13) |
| M3 | Continuing conversations; a periodic snapshot of work; a separate uid for agents as the first step | a restart mid-turn loses neither the conversation nor the work |
| M4 | A runner without a sandbox (K8), failure semantics (K9), the terminal through the runner, runc mode | a LADO session takes a task to merge in a runner |
| M5a, cloud | Panel protection, backup, a remote runner, then k8s with a pod per session | dogfooding on a remote runner |
| M5b, local | A proxy with an allowlist, the git relay (K7), logins per sandbox, runsc, isolation by default | E1-E7 closed, a many-hour run |
| M6 | The cloud service (BYOK) | after M5a and the lawyers |

M5a and M5b run in parallel. The proxy in observe mode (2.1) can be switched on earlier, in
M2-M3: it blocks nothing and collects data for the list.

---

## 4. Answers to the questions of the plan's section 6

1. **Connection direction:** agreed, the runner connects to the panel. Condition: a local
   runner goes the same way, without a separate code path. And see K10 on a panel behind
   NAT.
2. **The ladder of modes:** agreed. Add a lower step "separate uid" (K13) and an experiment
   on runc (K11).
3. **Where repositories live:** agreed with (c), starting with (b). Condition: bind mode is
   honestly labelled as not protecting the host from the agent (K6).
4. **A native macOS install without isolation:** acceptable. Conditions: it is written in
   the documentation; the UI shows the session's protection level; the seams of stage 1
   work there too; the test matrix doubles, and that is accounted for.
5. **Order:** stage 0 and stage 1 in parallel, 1.1 first: agreed. But finish E1 before 1.5,
   and put 1.7 before 1.4 (K4).

---

## 5. Questions the plan must answer before the start

1. Which process serves the Agent API locally and in the runner? (K5)
2. What happens to a session when its lease expires, and when a "lost" runner comes back?
   (K9)
3. How does a remote runner reach the panel if the panel is on a laptop? Or is the panel in
   the cloud mode always in the cloud? (K10)
4. Who runs git over the sandbox's repository for the fingerprint, the merge check and the
   merge? (K6)
5. How do `gh` and `glab` get a token in an isolated session? (K7)
6. Where is the periodic snapshot of unpushed work kept? (K10)
7. Does the cloud need nested gVisor at all, or does the orchestrator always give the
   sandbox there? (K1)
8. Which threats are declared never closed? (K2)
9. How does a Codex subscription user work with three parallel sessions? (K14)

---

## 6. What in the plan is worth keeping

- Seams first and with no change of behaviour; each step a separate release with a
  rollback.
- Switches without a silent fallback to the old behaviour.
- A runc baseline for every sandbox test, and integration tests inside the runner in CI.
- Section 2.3 "what was wrong": the same check is worth repeating after each stage.
- Codex's own login per sandbox, and an honest message in the UI about the subscription
  token inside.
- runsc in the runner's image, updated through `lado update`; cleaning device nodes out of
  the rootfs.
