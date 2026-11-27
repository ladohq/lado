# Session isolation as the first step to a cloud: the plan

Date: 2026-11-27. **Status: M0 under way: E14, E9, E3, E15, E10 done (2026-11-27/28).** Next
review after the M0 experiments and the M1 prototype. This plan is living: each later
session updates the Status columns, the decisions and this header, as
[cloud-workers-plan.md](cloud-workers-plan.md) does; the research and the archived inputs
stay as written.

The epics and tasks that carry this plan out: [the development plan](session-isolation-dev-plan.md).

This is version 3 of the plan, the last pass before the start, translated from Russian;
versions 1 and 2 were session artifacts and are not kept. It is based on:

- the gVisor spikes, [session-isolation.md](session-isolation.md) (with its corrections of
  2026-11-27) and its reports S1-S4;
- three analyses of 2026-11-27: [A1, code seams](session-isolation/a1-code-seams.md),
  [A2, prior art](session-isolation/a2-prior-art.md),
  [A3, a critical review of the spikes](session-isolation/a3-review.md);
- two independent reviews: [of version 1](session-isolation/review-plan-v1.md) (points
  K1-K14) and [of version 2](session-isolation/review-plan-v2.md) (points P1-P10).

**Names in this file.** D1, D2 are the human's decisions (the Russian draft's R1, R2; renamed
so they do not clash with the cloud workers reports R1-R4 or the runner profiles R and
R+net; E15 adds the candidate R-uid). Q1-Q4 are the questions of plan version 2; Q5 came
with M0's first results. T1-T11 are threats. E1-E15 are the M0 experiments. K1-K14 and
P1-P10 are the reviews' points (P1-P10 are not the spikes' privilege profiles P1-P6). The
analyses are A1-A3.

1. [Summary](#1-summary)
2. [What the spikes proved](#2-what-the-spikes-proved)
3. [What was wrong or unproven](#3-what-was-wrong-or-unproven)
4. [Threat model](#4-threat-model)
5. [The M0 experiments](#5-the-m0-experiments)
6. [Failure semantics and decisions before code](#6-failure-semantics-and-decisions-before-code)
7. [Milestones](#7-milestones)
8. [The steps of M0 and M1](#8-the-steps-of-m0-and-m1)

## Decisions

| Id | Question | Decision | Status |
|---|---|---|---|
| D1 | The first cloud topology | Panel and runner on one server, connected over the Docker network. The hybrid (the panel apart from its runners, including a panel on a laptop with a reverse SSH tunnel) comes last in the cloud track, by a separate decision | decided, 2026-11-27 |
| D2 | `lado server` | Becomes a required, always-running process. For native installs this is a change of the default behaviour, in M2a (section 6.1) | decided, 2026-11-27 |
| Q1 | Connection direction | The runner connects to the panel (outbound from the runner). Decided finally before M4; until M4 it does not matter, as M0-M3 run on one machine. This reverses the direction of 2026-11-26 (the panel connects to the runner) and agrees with the older stage C1 of [cloud-workers-plan.md](cloud-workers-plan.md) | preliminary |
| Q2 | The isolation ladder | See below; amended after E9 | decided, 2026-11-27; amended 2026-11-27 |
| Q3 | Where repositories live locally | See below | decided, 2026-11-27 |
| Q4 | A native macOS install | See below | decided, 2026-11-27 |
| Q5 | The nested runner's profile: R-uid ([E15](session-isolation/m0-e15.md)) or R+net | Not decided. R-uid is the preferred candidate for the nested runner; the final choice after E1, E2, E7 and E8 (speed, density, environments, cgroups), at M5b | open |

**Q2, the isolation ladder.** Step 0, as today → 1, the agent API boundary (M2) → 2, a
separate uid for the agents' processes (M3; E10 passed with conditions: after M2, see
E10's row) → 3, a runc container per
session (M4) → 4, runsc (gVisor) (M5). This is the order of work. The default stays "as
today" until the human decides at M5b's gate; whether steps 2 and 3 exist depends on E10
and E9. The reasons:

- the main threat (a prompt-injected agent reading other sessions or sending data out) is
  mostly closed already at runc, at near-native speed;
- small releases, each reversible;
- others went the same way: OpenHands made sandboxing opt-in, Codex shipped its sandbox
  behind a flag (A2);
- steps 3 and 4 share one runner base.

**Q2 amended, 2026-11-27 (decided).** [E9](session-isolation/m0-e9.md) failed the strict
threshold; on the human's decision the threshold is softened to "access closed; leaks of
information that only identifies the machine are acceptable". So:

- the runc step exists only where session containers are started by Docker on a Linux host
  (an own server): network scheme B with `INPUT`/`ip6tables` REJECT from the session
  bridges, plus `--dns 192.0.2.1 --cap-drop NET_RAW --tmpfs /sys/devices/virtual/dmi:ro`.
  The host's `boot_id` and the overlay2 paths in mountinfo stay visible (identification
  only);
- on Docker Desktop (macOS, Windows) the ladder goes from the agent API boundary straight to
  runsc: runc does not start in the nested runner unless it is widened (`SYS_PTRACE`,
  `SYS_CHROOT`, `keyctl`);
- under runc, `codex sandbox`, bwrap and `unshare -U` do not work. The UI says that in runc
  mode Codex's own sandbox is off and the container takes its place.

**Q3, where repositories live locally.** Both modes, chosen per project.

- **Bind** (the user's folder) comes first, in M4, labelled honestly in the UI and the
  docs: "sessions are isolated from each other, your folder is not". The agent can plant
  git hooks, editor settings or build scripts that later run on the host.
- **Volume plus git** follows: the fastest, it really protects the host, and it works the
  same as in a cloud.
- The default is chosen after E1: if bind is too slow on macOS, the volume becomes the
  default. Measured so far under gVisor, against a plain container: `git status` on a bind
  or volume 7.8× on Linux (ext4 bind) and 11.2× in WSL2 (named volume); the macOS volume
  was not measured, and a macOS bind (VirtioFS) is 21× slower even without gVisor
  ([session-isolation.md](session-isolation.md), 4.3).

**Q4, a native macOS install.** No isolation, but behind the agent API boundary (M2) and, if
E10 passes, a separate macOS user (M3). E10 checked the Docker image only; a separate
macOS user is not checked (and the development plan's Q-5 recommends the image only). Full isolation on a Mac only through Docker
Desktop: one install for macOS, Windows and Linux; the UI and the docs say so. macOS
Seatbelt (`sandbox-exec`) is not in the plan: deprecated, fragile, and it clashes with the
CLIs' own sandboxes. Revisit only on real demand.

## How M0 and M1 run (decided 2026-11-27)

| Question | Decision |
|---|---|
| Machines | The human's Mac (M chip, Docker Desktop), a more powerful machine if needed; Linux created in a cloud with the needed parameters or given by the sysadmins (fewer cores are fine if they are dedicated: what matters is runc against runsc on the same machine); a Windows machine, not a powerful one |
| Who runs the experiments | Yes/no checks on GitHub Actions, in a separate session that writes the workflow: E9, E3, E15, E7 (SELinux on a server or in a container), E5, E10, E8 on Linux, and a first E14. Measurements by a LADO session per machine from a brief, as in rounds 1 and 2: E1, E2, E14's speed, E6, E13. Logins with real subscriptions (E4) by the human by hand. GitHub first: it is cheap and can shorten the plan. The approach may change on the way |
| The M1 prototype | Pushed to ladohq as a draft PR labelled "prototype, do not merge"; closed and its branch deleted once its findings are in the spec; no CHANGELOG line |
| Approvals | The thresholds (section 5) are approved by the human before the experiments start. The threat model (section 4) stays a working version and is approved at M1's gate, together with the protocol spec, after the first results of M0 (E9, E14, E15) and the prototype |

## 1. Summary

1. **gVisor in a container fits as the target for a local machine and an own server.** The
   Dangerzone precedent supports only the idea "runsc inside a container as a portability
   layer between macOS, Windows and Linux". Their profile differs: rootless runsc,
   everything dropped except `SYS_CHROOT`, no network, one single-use sandbox. For our
   profile (a root runner with six capabilities, a netns per sandbox, many long-lived
   sandboxes) the sources have no precedent. So the checks that narrow the runner's
   privileges (E7, E14, E15, mandatory AppArmor) come in the first batch. For k8s and a
   paid service the orchestrator gives the sandbox.
2. **The past conclusions were too optimistic** (section 3; the second review confirmed it
   from the reports).
3. **The main work is the agent API boundary between the agent and LADO.**
4. **Decisions:** the runner calls in itself (Q1, preliminary); the ladder "as today → API
   boundary → (uid) → runc → runsc" (Q2; runc only on a Linux host, after E9); the old mode
   stays supported; the security boundary is the session; `lado server` is mandatory (D2).
5. **Milestones:** M0-M4, then the shared milestone M4b. After it two parallel tracks: the
   cloud (M5a) and local isolation (M5b).

## 2. What the spikes proved

runsc works in a container with six capabilities and Docker's seccomp plus `pivot_root`
and `chroot`. Checked on Docker Desktop under macOS, Engine under Linux x86 and arm64, and
Engine in WSL2. Besides:

- sandboxes do not see each other;
- the "proxy only" rules hold against root, over IPv4;
- the sentry runs in its own user namespace;
- rootless with a shared uid is out because of ptrace;
- CPU is not lost; `kvm` does not help on nested virtualization;
- bwrap and `codex sandbox` work inside;
- `C:\` is unusable; CRLF is a real trap.

## 3. What was wrong or unproven

**Wrong or overstated** (corrected in [session-isolation.md](session-isolation.md)):

- the speed headline (worse on a volume; the macOS volume was not measured);
- "the runner's services are out of reach" (true only for IPv4, and with the proxy outside
  the runner);
- "AppArmor is optional";
- "the code through git" as a detail (it changes today's main workflow);
- the subscription caveat applied too broadly (a hosted-service legal constraint read as a
  technical rule for self-hosting, A3 2.3);
- "the same as Dangerzone".

**Unproven:** the real speed of a session, density, the safety of a proxy inside the runner,
keys and git through the proxy, logins, surviving Docker updates, stability, statistics.
All of it is checked in section 5.

## 4. Threat model

**Attackers:** an agent under prompt injection; a malicious dependency or repository; a
neighbouring session; another user (only in M6).

**Columns:** M2b, the API boundary; M4, the runner in runc mode; M4b, plus the allowlist,
keys and the relay; M5a, the cloud, on an own server runsc as the host's Docker runtime
(E14); M5b, runsc locally.

| Threat | Today | M2b | M4 | M4b | M5a | M5b | Never closed |
|---|---|---|---|---|---|---|---|
| T1. Reading other sessions' and the panel's files and secrets | open | partly (same uid) | closed with secrets per session (M2b) | closed | closed | closed | — |
| T2. Driving other agents (tmux, `lado.db`) | open | closed for the API, not for the same uid | closed | closed | closed | closed | — |
| T3. Sending data out over the network | open | open | open (the proxy observes, but is never an open proxy: E3) | closed outside the allowlist (the strict proxy of E3) | closed outside the allowlist | the same | through the allowed hosts |
| T4. The agent's code run by a trusted party | open | closed for the core (6.3) | the same | the same | the same | the same | bind mode: the human's IDE and git |
| T5. An escape through the kernel | — | — | open | open | closed with runsc; under the host's runtime AppArmor does not apply to runsc's processes, the protection is gVisor itself (E14) | mostly closed; under R-uid the network goes through the host kernel's TCP stack (E15) | bugs in gVisor and the runner |
| T6. Neighbours exhausting resources | open | open | closed (cgroups; Docker's limits work under runc and the host's runsc, E9, E14) | closed, with per-sandbox connection limits on the shared proxy (E3) | closed | closed if E8 passes | — |
| T7. Theft of the own session's subscription token | open | open | open | open | open | open | always, for subscriptions |
| T8. An agent acting in its supervisor's name | open | open | open | open | open | open | the boundary is the session; dangerous tools need the human's answer |
| T9. A compromised runner (the sessions' keys in the proxy, PTYs, the channel to the panel) | — | — | all its sessions | all its sessions; the panel checks epochs and event ids and does not trust git state from the runner (6.3) | the same; a runner per owner. On an own server the launching component holds the Docker socket, root on the host: a narrow API (E14) | the same | all the runner holds in memory |
| T10. The agent's configuration in the repository (`.claude/settings.json` with hooks, `.mcp.json`) overrides LADO's hooks | open | open | limited by the sandbox | the same | the same | the same | the decision is an open item of M4b |
| T11. A `gh`/`glab` token with broad rights | open | a narrow token per project plus `lado doctor` (before M5a) | the same | closed: PR/MR through the Agent API | closed | closed | — |

The UI shows each session's protection level. Bind mode is labelled "the host is not
protected from the agent's code".

## 5. The M0 experiments

The thresholds are written down before the experiments. **First batch:** E14, E1, E9, E3,
E15. Status: E14, E9, E3, E15, E10 done (2026-11-27/28), the rest not started.

| # | Experiment | Platforms | Threshold → decision | Status |
|---|---|---|---|---|
| E14 | runsc as Docker's runtime on the host (`--runtime=runsc`, a container per session) against the nested runner | an own Linux server | if the isolation is the same, the install fits in one installer step and the speed is no worse → on an own server the runner uses the host's runtime, and the nested variant is needed only where nothing can be installed on the host (Docker Desktop). Such a runner holds the Docker socket, which on that host equals root, so it is a trusted part of the host, not an isolated container: fine for an own server, never to be handed to an untrusted party | **done, passed**: on an own Linux server the sessions run as containers with `--runtime=runsc`. One installer step (download and sha512, unpack to `/usr/local/bin`, `runsc install`, restart dockerd ≈ 11 s; containers without a restart policy die). Isolation as nested R+net **only with `INPUT`/`ip6tables` REJECT from the session bridges** (else sessions reach the host's services). Speed equal to nested (H/B 0.96–1.01×); compatibility 29/29. The launching component holds `docker.sock`, root on the host (`default-runtime: runsc` does not stop `--runtime=runc`), so a narrow API only. Network scheme B (a bridge per session, the proxy in its own network, `DOCKER-USER` rules over the pool). Docker's DNS does not work under runsc: the proxy is reached by IP. [Report](session-isolation/m0-e14.md) |
| E1 | An end-to-end "supervisor + worker" session on a fake endpoint; `make test-integration` in the sandbox; runc against runsc; volume and bind. Method: 8+ dedicated vCPU, 10 interleaved runs, median and spread; plus a Mac on an M chip | Linux, macOS, WSL2 | the read-only role's fingerprint over 2 s → the fingerprint becomes asynchronous. runsc over 3× slower than runc on the integration tests → runsc only by choice and in M5b | not started |
| E9 | The runc step: the same runner, `runc` instead of `runsc`, the isolation table | Linux, macOS | the rows "processes, files, network, the runner's services" closed as under runsc → the runc step is accepted; any open → no such step, the ladder goes straight to runsc | **done, strict threshold failed; softened** on the human's decision (2026-11-27) to "access closed; leaks of machine-identifying information only are acceptable" (Q2 amended). On the host DNS exfiltration, `NET_RAW` and DMI are closed by `--dns 192.0.2.1 --cap-drop NET_RAW --tmpfs /sys/devices/virtual/dmi:ro`; the host's `boot_id` and overlay2 paths in mountinfo stay (identification only). `codex sandbox`, bwrap and `unshare -U` do not work under runc. Nested runc in R+net does not start (needs `SYS_PTRACE`, `SYS_CHROOT`, `keyctl`), so no runc step on Docker Desktop. A correction: Docker's default capabilities do include `NET_RAW` for runc (E14 said otherwise). [Report](session-isolation/m0-e9.md) |
| E3 | The proxy and the gateway inside the runner; IPv6 link-local; DNS; CONNECT with the check before resolving | Linux, macOS | a hole in the proxy → the proxy goes into a separate container. The Agent API gateway stays reachable from the sandbox anyway: its own port only, strict parsing, a check of its own | **done, passed**: a strict proxy can live inside the runner (CONNECT only, strict head parsing and limits, the allowlist before DNS, all resolved addresses global, the connection to the checked address, no IP literals, a port list); an open proxy is a hole anywhere and inside the runner bridges sandboxes. Second layer: `iptables -m owner` OUTPUT rules on the proxy's uid (no private, loopback, link-local except Docker's DNS `127.0.0.11`). Per-sandbox connection limits are needed (one client took all 256 slots, 503 for the neighbour). The gateway: its own port only open from `veth+`, nothing else on `0.0.0.0`/`[::]`, strict parsing, its own token check, answering only by the sandbox's veth address. `ip6tables` REJECT from `veth+` required (else IPv6 link-local reaches the runner's services even under runsc). Root in R+net has no `CAP_KILL`. [Report](session-isolation/m0-e3.md) |
| E15 | Rootless runsc with a separate uid per sandbox | Linux, macOS | ptrace between sandboxes closed and the network works → a profile without a root runner becomes a candidate instead of R+net | **done, passed**: candidate profile "R-uid": the runner's root with `SETUID`, `SETGID`, `NET_ADMIN` only; seccomp Docker default + `clone`, `clone3`, `unshare`, `setns`, `mount`, `umount2`, `pivot_root`, `chroot`; AppArmor `lado-runner-lite` (with `userns,`; no host sysctl change on Ubuntu 24.04); each sandbox under its own host uid, rootless runsc `--network=host` in a per-sandbox netns held by `unshare -U -r -n`. Signal, ptrace, mem, environ, root, fd between sandboxes closed by the uid separation; 0/54 network holes. Costs: no gVisor netstack (`--network=sandbox` is unsupported rootless), so the host kernel's TCP stack; root inside the sandbox loses bwrap (agents must run as uid 1000; `codex sandbox` as uid 1000 not finished, moved to E10). Not checked: an escape with the sentry's own-userns capabilities, which of the 8 seccomp calls are needed, speed. [Report](session-isolation/m0-e15.md) |
| E2 | Density: 1, 3 and 6 sessions; memory, start, disk; a shared read-only rootfs | macOS, Linux | 3 do not fit with the default settings → a shared rootfs and an installer warning | not started |
| E4 | Logins: Codex device login per session; Claude `setup-token` and pasting the code; one Claude subscription in two sandboxes over a refresh | any | a shared Claude login breaks → a login per sandbox for Claude too | not started |
| E7 | CI cells: Engine 29, Fedora with SELinux, rootless Docker, userns-remap | Linux | does not work → `lado doctor` says so, and runsc is not offered there | not started |
| E8 | cgroups per sandbox under runsc | Linux, macOS | the limits do not work → limits at the level of a container per session | not started |
| E10 | A separate uid for the agent's process tree in today's image | the Docker image | bind and the CLIs work → the uid step in M3 | **done, passed with conditions**: as a second uid tmux, git in a bind-mounted repository, the four CLIs and `uv run` work. Conditions: (1) **after M2**: hooks and `lado mcp` open `lado.db` themselves and fail from another uid ("attempt to write a readonly database"), so the uid step needs the Agent API through `lado server`; (2) **`LADO_HOME` and LADO's home with mode `700`**: today `~/.lado` is `755` and `lado.db` `644`, and the agent copies and reads the database (everything LADO writes with `700`/`600`, the secrets, tokens and `server-token`, stays closed); (3) **the agent's own HOME** (`700`) with the CLIs' configs, `CLAUDE_CONFIG_DIR` and `NPM_CONFIG_PREFIX` overridden, the logins moved to the agent or passed as variables. Writing to a bind-mounted repository needs ACLs on the host (layout A: LADO stays the human's uid, the agents get their own; a shared group fails for the host's later files; the reverse layout B breaks LADO's own `git worktree add`). Starting as the agent: a narrow setuid helper or a sudo rule inside today's image (neither works under `no-new-privileges` or gVisor); in the runner the runtime sets the uid. tmux: the agent's server, LADO joins with `server-access -a lado` (tmux ≥ 3.3). `codex sandbox` as the second user needs user namespaces (not under runc's default seccomp; works under runsc) and, with a system bwrap, a writable HOME. LADO's image under runsc exits at the entrypoint's sudo step. Not checked: Docker Desktop's bind mounts (ACLs over virtiofs), real logins. [Report](session-isolation/m0-e10.md) |
| E11 | Hook and MCP latency over a network against the 20 s and 60 s limits | a network | does not fit → asynchronous hooks before the hybrid | not started |
| E12 | Each CLI continuing its conversation after a runner restart | 4 CLIs | Claude and Codex can → isolation by default may be switched on; a CLI that cannot is labelled loudly in the UI ("the conversation starts over"). Claude or Codex cannot → that blocks M5b | not started |
| E13 | Docker Sandboxes as the path for macOS and Windows | macOS, Windows | VM isolation with nothing installed beyond Docker Desktop, our CLIs and network control work → a candidate "external provider" for M5b; otherwise the question is closed | not started |
| E5 | Confirm from the changelog that the poll fixes (PR #12851) and the PTY fixes are in release-20261123.0; a short regression: tmux idle, resize, `stty -isig`, SIGHUP | Linux | a regression → pin to a release with the fix | not started |
| E6 | Round 3: Docker Desktop under Windows ([brief](session-isolation/gvisor-spike-3-brief.md)) | Windows | the path from PowerShell does not work → fix the installer before M5b | not started |

The briefs of the experiments run on GitHub are archived in
[m0-experiments-brief.md](session-isolation/m0-experiments-brief.md). After the first four
results the briefs of E10, E8 and E7 were updated: E10 now includes making `codex sandbox`
work as a second user; E8 focuses on the nested runner in both profiles, R+net and R-uid;
E7 covers R+net, R-uid and the host's runtime.

## 6. Failure semantics and decisions before code

### 6.1 The Agent API and a mandatory `lado server` (D2)

- **A persistent process serves it.** Locally that is `lado server`; in the runner, the
  gateway with a buffer. The client (`lado mcp`, the hook) is one.
- **A separate entry.** The Agent API listens on its own socket: locally a Unix socket
  outside the agents' folders, in the runner the gateway's port on the veth. It has its own
  token check. The UI's routes are not reachable on this entry. In the runner (E3): only
  the gateway's and the proxy's ports are open from `veth+`, nothing else listens on
  `0.0.0.0`/`[::]`, the parsing is strict, and the gateway answers each sandbox only by its
  own veth address.
- **Two classes of hook events.** A table mapping each CLI's events to these classes is part
  of M1's spec.
  - **"Needs an answer":** the end of a turn (hand over the unread, "go on"), readiness to
    start, the events whose answer is printed to the agent (`hooks.py:350-356`). If the
    server is unreachable, the client retries until that CLI's hook deadline
    (`hooks.deadline`), then exits empty and writes the event to an on-disk queue. The agent
    stops as if there were no messages. When the server comes up, it processes the queue
    (the agent becomes idle), and the messages are delivered by the usual pass
    (`runtime.sweep`), typed into the window. Nothing is lost, but there is a delay. The UI
    shows "the server was unreachable".
  - **"Notification"** (tool status and the rest): an on-disk queue with retries, without
    duplicates by event id.
- **The protocol:** a version, an event id, retries without duplicates, an id and a timeout
  for long operations (`spawn_worker`, `start_session`).
- **Automatic start and restart.** `lado start`, any CLI command and the hook client start
  the server if it is not running, the way the loop is started today. In Docker the
  entrypoint keeps it up. `lado doctor` checks it. A server crash stops the hooks of all
  sessions, so the failure is loud and goes to the error journal.
- **`lado loop`.** The recommendation: the sessions' passes move into the server (a thread
  or task per session, with the same per-session lock), and the separate process goes away.
  Decided in M1 (a decision record).
- **Tests.** The integration fixture brings up a server per test. The growth of CI time is
  measured in M2a; its budget is an open item of M2a.
- **When the default behaviour changes.** In **M2a** a native install gets a permanent
  background process. That is a minor release with a CHANGELOG line. The rule "the default
  does not change" applies to isolation; this change is announced explicitly.
- A single writer of `lado.db` appears only with the runner.

### 6.2 Lease, fencing, disconnects

- A session is bound to a runner. When the lease is lost, its agents are marked
  `runner_lost` and wait. The human has a manual operation "raise the session from a
  snapshot on another runner".
- **Two epochs.** The runner's epoch and the session's epoch: the session may have been
  stopped and started again on the same runner while it was away. The higher epoch wins;
  the agents of the lower one are stopped.
- **Reconciliation after the panel is restored from a backup.** The runner is the source of
  truth about live agents; the panel about the human's decisions. Events from the runner's
  buffer for agents the panel does not know are not applied; they are shown to the human.
- Delivery is "at least once", processing exactly once. The runner has a buffer for the time
  the panel is unreachable. A panel update does not kill sessions.
- **Open item of M4:** the reconciliation rules in detail, with a test for each rule.

### 6.3 Git

- **The rule:** the trusted side never opens a repository directory the sandbox has written
  to. The fingerprint, the merge check, the work state and the merge run inside the sandbox
  through `Workspace`. Their results are data and are not trusted. "Merged" is checked on
  objects obtained by fetch.
- `safe.directory '*'` is removed from the panel's image.
- **Push** goes through a git relay that injects the token and checks branches. A GitHub App
  is an option for M6.
- **`gh`/`glab`:** before M5a, a narrow token per project and a check in `lado doctor`. In
  M4b "open a PR/MR" becomes an Agent API tool, and the CLI gets no token.
- **A snapshot of unpushed work.** Inside the sandbox a service commit of the working tree
  (with uncommitted and new files) is made periodically under `refs/lado/wip/<agent>`,
  without touching the agent's index. The panel takes it by fetch through the runner's
  channel, so the sandbox needs no credentials of the panel. It fetches only into a bare
  repository, with `fetch.fsckObjects`, without submodules, without a checkout, with a size
  quota.

### 6.4 Panel and runner

- The runner opens the protocol: registration by a token, mutual authentication, a version
  (Q1).
- **The first cloud topology (D1):** panel and runner on one server, over the Docker
  network.
- A reverse SSH tunnel is one of the hybrid's variants and is decided with it. It would
  revisit the decision of 0.48.0 "no ssh in the container".
- Before the panel is reachable over a network: TLS, a login instead of a token in the URL,
  limits on the terminal's WebSocket.

## 7. Milestones

The rules:

- every release leaves LADO working;
- anything new is switched on by an explicit flag, with no silent fallback;
- the old mode stays supported;
- tests at the lowest layer; what users see goes to the CHANGELOG.

The human's yes is needed at each milestone's gate.

| Milestone | Content | Gate | Status |
|---|---|---|---|
| **M0** | The experiments of section 5, first batch E14, E1, E9, E3, E15 | the thresholds approved before the experiments; the human's decision on each result | under way: E14, E9, E3, E15, E10 done |
| **M1** | A token per agent; the hook split in two halves with the event classes; the `lado mcp` front as a proxy, `write_artifact(file=)` only from the agent's folders; a throwaway end-to-end prototype (not merged) | **the Agent API protocol spec** in `openspec/specs`, **a decision record on the process model** (`lado server`, `lado loop`, the entry), a review of the prototype and the threat model approved | not started |
| **M2a** | The Agent API in `lado server` (a separate entry, automatic start, a test fixture, the sessions' passes in the server); the simple calls; then the tools one per release: `list_models` → `finish_worker` → `spawn_worker` → `start_session` | the integration suite green through the server; a server failure mid-turn checked by a test (6.1); the CI budget kept | not started |
| **M2b** | The execution backend (the local one is tmux); `Workspace` with the rule of 6.3; the launch bundle; paths relative to the place of execution; the agent's environment without `LADO_HOME`, the tmux socket and others' secrets, secrets per session; a narrow `gh`/`glab` token and a check in `lado doctor`; a second backend in the tests and a contract test | **the CI cell "boundary":** the agent cannot reach `LADO_HOME`, the socket or others' secrets, the integration suite is green, no canaries found | not started |
| **M3** | Conversations continue after a restart; work snapshots (6.3); the proxy in observe mode, never an open proxy: from day one under its own uid, with owner rules and the address check before connecting (E3); a separate uid in the Docker image (E10 passed with conditions: after M2, `LADO_HOME` `700`, the agent's own HOME, ACLs on bind-mounted repositories) | a restart mid-turn loses nothing | not started |
| **M4** | The `lado` and `runner` images; the runner → panel channel; lease, epochs, buffer, reconciliation (6.2); a session in the runner without a sandbox; the terminal and `lado attach` through the runner; a "sandbox provider" and runc mode (netns, limits). On an own server runc mode is a container per session of the host's Docker (E9, E14) in network scheme B, with the `INPUT`/`ip6tables` rules installed by the launching component at its start and checked by `lado doctor`; the launching component is a trusted part of the host with a narrow API | a LADO session reaches merge in a runner, also across a runner restart | not started |
| **M4b, shared** | A strict proxy with an allowlist (E3): CONNECT only, strict head parsing and limits, the allowlist before DNS, all resolved addresses global and the connection to the checked address, no IP literals, a port list, owner rules on its uid, per-sandbox connection limits, E3's table kept as the proxy's regression suite; IPv6; the flow "a host outside the list is needed"; API key injection through each CLI's base URL; the git relay; "open a PR/MR" as an Agent API tool; logins per sandbox (size L, the UI designed ahead). **Open item:** what to do with the agent's configuration from the repository (T10) | rows T3 and T11 closed by tests; two Codex sessions in parallel | not started |
| **M5a, cloud** | 1) panel protection (TLS, login, WebSocket) and a backup of `lado.db`; 2) panel and runner on one server (compose, the Docker network), runsc as the host's runtime (E14 passed), scheme B and the host's rules as in M4; 3) k8s with an external provider (a pod with a RuntimeClass per session); 4) the hybrid, by a separate decision | dogfooding LADO on the server, an 8-hour run | not started |
| **M5b, local** | runsc mode: in the image, updated through `lado update`, the nested runner's profile, R-uid or R+net (Q5), a narrow seccomp profile with a loud fallback, AppArmor in the installer, `lado doctor`, cleaning device nodes; the integration suite inside the runner in CI (runc and runsc); then isolation by default | E1-E15 closed, an 8-hour run, a release cycle of dogfooding | not started |
| **M6** | The cloud service (BYOK) | after M5a and the lawyers | not started |

The shared runsc parts (the image, seccomp, AppArmor, doctor) are done by whichever track
reaches them first.

## 8. The steps of M0 and M1

In the order of work.

**M0**

1. E14: runsc as Docker's runtime on an own Linux server against the nested runner
   (isolation, speed, install steps). Done ([report](session-isolation/m0-e14.md)).
2. E1: an end-to-end session and `make test-integration` in runc and runsc, volume and bind,
   8+ vCPU, 10 interleaved runs, plus a Mac.
3. E9: the runc step in the same runner, the isolation table. Done
   ([report](session-isolation/m0-e9.md)).
4. E3: the proxy and the gateway in the runner, IPv6, DNS, CONNECT with the check before
   resolving. Done ([report](session-isolation/m0-e3.md)).
5. E15: rootless runsc with a uid per sandbox, ptrace and the network. Done
   ([report](session-isolation/m0-e15.md)).
6. E7: CI cells Engine 29, Fedora with SELinux, rootless Docker, userns-remap.
7. E2: density of 1/3/6 sessions, memory, start, disk, a shared rootfs.
8. E8: cgroups per sandbox under runsc.
9. E4: Codex and Claude logins in a sandbox, one subscription in two sandboxes.
10. E12: each CLI continuing its conversation after a runner restart.
11. E10: a separate uid for the agents in today's image. Done
    ([report](session-isolation/m0-e10.md)).
12. E11: hook and MCP latency over a network against the limits.
13. E5: runsc's changelog plus a short tmux and PTY regression.
14. E13: Docker Sandboxes on macOS and Windows.
15. E6: round 3, Docker Desktop under Windows (the brief is ready).
16. The human decides on each result by its threshold (the thresholds are approved before step 1; the threat model at M1's gate).

**M1**

1. A token per agent: HMAC over (session, agent, instance); identification; permissions
   from the session; key rotation.
2. The hook split into a client half and a server half inside one process, with the classes
   "needs an answer" and "notification" in the code.
3. The `lado mcp` front as a proxy to the Agent API inside one process;
   `write_artifact(file=)` only from the agent's folders.
4. A throwaway end-to-end prototype on a separate branch: the Agent API over a socket, a
   second backend in a container without a sandbox, the fake agent.
5. The Agent API protocol spec in `openspec/specs`: version, event ids, retries, the event
   classes per CLI, long operations.
6. A decision record on the process model: `lado server` mandatory, the Agent API entry, the
   fate of `lado loop`, automatic start.

## History: how the second review was taken

Plan version 3 took all of the second review's points; there were no disagreements. The code
references were rechecked on `main` 1e565441: `hooks.py:350-356` prints the answer of
`handle`, and what is not handed over waits for the pass (`runtime.sweep`, line 2499); ssh
was removed from the container in 0.48.0. The first review's points K1-K14 were taken into
version 2; which of them still stood is in the second review's section 5.

| # | Point | Verdict | What changed, and where |
|---|---|---|---|
| P1 | The allowlist proxy, keys, the git relay and logins are needed by both tracks | taken | a new shared milestone M4b before the fork; M5b keeps only the local part; the threat table has columns M4b and M5a (sections 4, 7) |
| P2 | The most complex first cloud topology was chosen | taken (D1) | M5a's order: panel protection and backup → panel and runner on one server → k8s → the hybrid by decision. Reverse SSH is only a variant of the hybrid (6.4, 7) |
| P3 | The consequences of a mandatory server are not described | taken | 6.1: two classes of hook events and the behaviour with the server down, automatic start, a separate Agent API entry, the server in tests, the fate of `lado loop`, CHANGELOG; the clash with "the default does not change" resolved explicitly |
| P4 | The runner's epoch is not enough | taken | 6.2: a session epoch, reconciliation after restoring the panel from a backup, manual raising from a snapshot. The details are an open item before M4 |
| P5 | The snapshot's content and direction are not defined | taken | 6.3: a service commit of the working tree under `refs/lado/wip/…` inside the sandbox, fetched by the panel, `fsckObjects`, quotas |
| P6 | Gaps in the thresholds and the method; E5 outdated; E14 needed | taken | section 5: thresholds for E9, E12, E13; the method in E1; E5 cut down; E14 in the first batch; the 8-hour run in both tracks' gates; E3 refined about the gateway |
| P7 | Dangerzone supports less than claimed | taken | section 1 rewritten; E15 added (rootless with a uid per sandbox); the checks that narrow privileges moved up |
| P8 | M2 is too big for one gate | taken | M2a and M2b with their own gates; M1's gate is the protocol spec in `openspec/specs` and the process model's decision record |
| P9 | The threat model lacks a compromised runner and the agent's configuration in the repository | taken | rows T9 and T10. T1 after runc holds only with secrets per session (M2b's step) |
| P10 | The `gh`/`glab` token is the main asset in a cloud | taken | before M5a a narrow token per project plus a check in `lado doctor`; "open a PR/MR" as an Agent API tool in M4b |

One refinement to P6 and E14: "runsc as Docker's runtime on the host" means the runner has
the Docker socket. On that host it equals root, so the runner becomes a trusted part of the
host, not an isolated container. Acceptable for an own server, but such a runner must not be
handed to an untrusted party. Written into E14's threshold.
