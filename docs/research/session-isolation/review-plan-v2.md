# Second review of the plan "Session isolation" (version 2) and a recheck of its grounds

Archived input to the [session isolation plan](../session-isolation-plan.md), 2026-11-27;
translated from Russian, numbering kept (P1-P10 here are the review's points, not the
spikes' privilege profiles P1-P6; K1-K14 are the points of the
[first review](review-plan-v1.md)). Plan version 2 (`isolation-roadmap`, a session
artifact) is not kept; its section numbers refer to it.

Date: 2026-11-27. A document for the agent who leads the plan.

**What was done:**
- version 2 of the plan reviewed (`isolation-roadmap`, milestones M0-M6);
- its grounds rechecked: the spike reports in the repository
  ([session-isolation.md](../session-isolation.md), S1-S4), A1's claims about the code at
  `main` 1e565441, A2's external sources against the originals.

**How to read:** section 2 is the result of the recheck. Section 3 is the points on version
2 (P1…P10) by importance, each with a "What to change". Section 4 is my answers to the
questions of the plan's section 9.

---

## 1. Verdict

Version 2 is much stronger than the first. The threat model, the failure semantics, the git
rule, the experiments' thresholds and the two tracks are done in substance, not as a
formality. I accept both of the agent's objections (K1 on an own VPS and K13 on the cost of
a separate uid).

The recheck confirmed almost all of the plan's grounds. It found one overstated support (the
Dangerzone precedent, P7) and one outdated worry (tmux in gVisor, P6).

M0 and M1 can start. Three things are worth fixing first:

1. **Shared prerequisites landed in the local track.** The proxy with an allowlist, the git
   relay, key injection and logins per sandbox sit in M5b, while the cloud runner (M5a)
   needs them more than the local one does (P1).
2. **The most complex topology was chosen as the first cloud one.** "Panel on a laptop,
   runner on a VPS through a reverse SSH tunnel" comes before "panel and runner on one
   server" (P2).
3. **The consequences of a mandatory `lado server` are not described.** The main one: a
   hook waits for an answer, so a queue with retries saves only some of the events (P3).

---

## 2. Recheck of the grounds

### 2.1 The spike reports (S1-S4, `session-isolation.md`)

| Claim of the plan or of A3 | Status | What the reports say |
|---|---|---|
| The headline speed numbers were taken on the sandbox's disk, not on a volume | confirmed | section 4.2 is titled "on the container's own disk"; mode `--overlay2=root:self` |
| On a volume `git status` is worse: 7.8× (Linux), 11.2× (WSL2) | confirmed | table 4.3: Linux bind ext4 0.68 s → 5.32 s; WSL2 volume 0.83 s → 9.32 s |
| The volume on macOS was not measured | confirmed | the "container disk / volume" row is a single one; S1 has no separate volume measurement |
| The measurements are a median of three runs on 2 vCPU, up to 2× spread between VMs | confirmed | S3: "Azure VMs with 2 vCPU", "Median of three runs"; the same workload gave 5.26× and 2.56× on two VMs |
| LADO's tests in the measurement are three files, not the whole suite | confirmed | row W5: "pytest (3 test files, `-n 4`)" |
| The spikes' proxy was a separate container, with no allowlist | confirmed | S1: `spike-proxy`, a CONNECT proxy of its own |
| IPv6 was not checked | confirmed | the rules are `iptables` only; the reports never mention `ip6tables` |
| There are no cgroup limits per sandbox | confirmed | S1: the per-sandbox network worked only with `--ignore-cgroups` ("cgroup busy" without it) |
| tmux was checked only as "it starts" | confirmed | S1: a session, send-keys, capture; the CLIs' screens for 12 seconds |
| AppArmor is recorded as "optional hardening" | confirmed | section 5 |
| The runner is root with six capabilities, including `SYS_ADMIN` | confirmed | the compose fragment of section 5 |

Conclusion: the plan's section 3 ("what was wrong or unproven") is accurate.

### 2.2 The code (A1), sampled

| Claim | Status | Where |
|---|---|---|
| `write_artifact(file=)` reads any absolute path | confirmed | `artifacts.py` 271-274: "An absolute path stays as it is" |
| The credential helper hands out the token of any stored server | confirmed | `git_credential.py` 49-76: `--home` and `--server` come from the arguments |
| Every agent gets `LADO_HOME` and the tmux socket | confirmed | `providers/base.py` 686-692 |
| The hook prints the server's answer to the agent | confirmed | `hooks.py` 356; matters for P3 |
| The integration tests run without the UI server | confirmed | `tests/integration/conftest.py`: the server is one of the processes LADO starts itself, not a precondition |

### 2.3 External sources (A2), against the originals

| Claim | Status | Note |
|---|---|---|
| Anthropic self-hosted: the runner polls the queue itself, polling extends the lease | confirmed | the self-hosted environments documentation |
| Same: a crashed runner → the session goes to another runner, is cloned again, unpushed work is lost | confirmed | an argument for K9: the model assumes a movable session |
| Same: a lease of about 60 s | **not confirmed** | the part of the page I read has no number; there is 80 s for a stop. Does not affect the plan |
| Same: one owner per runner, `--capacity 1`, a fresh container per session | confirmed | |
| OpenHands: "sandboxing should be opt-in, not universal" | confirmed | the SDK's design document and the arXiv paper 2511.03690 |
| Tencent: tmux in gVisor took 96.6 % CPU; PTY and inotify errors | confirmed, **but fixed** | PR #12851, article of 2026-04-23. See P6 |
| CVE-2026-96812: escape to the host through `/dev/cuse` in the image | confirmed | the first installable release with the fix is 20260831.0. The spikes ran on 20261123.0, which is newer |
| CVE-2026-95702 fixed in 20260831.0 | confirmed | |
| Docker Sandboxes CVE-2026-79994 (a race in the Unix socket relay) | confirmed | the fixed version: 0.42.0 per the CVE record, 0.41.0 per one publication |
| Codex: one `auth.json` cannot be shared between parallel jobs and machines | confirmed | OpenAI's CI/CD guide |
| Anthropic: signing in with one's own subscription to an unmodified Claude Code is allowed also where a platform hosts it; intermediating and storing credentials is not; the limits assume ordinary individual usage | confirmed | the legal and compliance page |
| Dangerzone is "built the same way" | **overstated** | see P7 |
| Anthropic and OpenAI use gVisor | not checked | does not affect the plan |

---

## 3. Points on version 2

### P1. The proxy, the git relay and the logins are needed by both tracks but sit in the local one (critical)

In M5a the remote runner works in runc mode. In M4 its network is "proxy only", but the
allowlist arrives in M5b; until then the proxy only observes. So in M5a someone else's
machine holds git tokens and model keys with open egress. The threat model's row T3
("closed after runc, with the M5b proxy") is wrong for the cloud track.

The same with the git relay and API key injection: without them the tokens stay in the
sandbox on the server. And with logins per sandbox: without them M5a cannot run two Codex
sessions.

**What to change:**
- Move out of M5b into a shared milestone before the fork (say M4b): the proxy with an
  allowlist and a refusal flow, API key injection, the git relay, logins per sandbox.
- Leave in M5b only what concerns the local machine: runsc mode with seccomp and AppArmor,
  the installer, isolation by default.
- Fix the threat table's columns: add a separate column "M5a (runc + allowlist)".

### P2. The first cloud topology is the wrong one (critical)

The plan puts into M5a "a remote runner on an own VPS" with the panel on a laptop and a
reverse SSH tunnel. That is the hybrid, the most complex of the three topologies of
`session-isolation.md` (section 7). Its drawback is written there too: while the laptop
sleeps, sessions on other runners get no answers. Agents' hooks need the panel's answer, so
agents will stall at the end of a turn.

The owner's goal is working from a browser with the executors in a cloud. The "cloud"
topology fits it: panel and runner on one server, connected over the Docker network. It
needs no reverse tunnel, no buffer for long panel outages and no SSH keys.

One more thing: since 0.48.0 LADO's container has no SSH keys and no SSH agent (the client
is kept only for a clear git error). A reverse tunnel from the panel in Docker brings SSH
keys back into the image, that is, it revisits a recent decision.

**What to change:** the order in M5a:
1. panel protection and a backup of `lado.db`;
2. panel and runner on one VPS (compose);
3. k8s with an external sandbox provider;
4. the hybrid (several runners, the panel apart): last, and by a separate decision. A
   reverse SSH tunnel is one of its variants, not the base.

### P3. A mandatory `lado server`: the consequences are not described (critical)

I think the decision itself is right. But it has consequences that section 6.1 lacks.

1. **A hook is a request with an answer.** The hook client prints to the agent what the
   server returned (`hooks.py` 356): reminders of unread messages, an instruction to go on.
   An on-disk queue with retries fits only events that need no answer. For the end of a
   turn, the behaviour when the server is unreachable must be defined: the agent will stop
   without getting its messages.
2. **The failure radius grew.** Today a hook depends only on the database. After M2 the
   crash of one process stops the hooks of all sessions. Automatic restart and a check in
   `lado doctor` are needed.
3. **The Agent API must not hang on the same entry as the UI.** A separate socket and a
   separate token check, otherwise the agent gets network access to the UI's routes.
4. **Tests.** The integration tests run without a server today. After M2 every test needs
   the server: CI time and a new fixture.
5. **A contradiction with the plan's rule.** "Until M5b the default behaviour does not
   change", but a mandatory background process appears for native install users already in
   M2.

**What to change:**
- Split hook events into two classes: "needs an answer" and "notification". For the first,
  describe the behaviour when the server is unreachable and who delivers the messages later
  (today the loop's pass `runtime.sweep` does it).
- Add steps: automatic start and restart of the server, a separate Agent API entry, a server
  fixture in the integration tests, a CHANGELOG line for the native install.
- Decide the fate of `lado loop`: it stays a separate process per session or moves into the
  server.

### P4. Fencing by the runner's epoch is not enough

- An epoch is needed at the session level too: the session may be stopped and started again
  on the same runner while that runner was unreachable.
- The reverse case is not described: the panel is restored from a backup (an older state)
  while the runners are alive. A reconciliation rule is needed: who is the source of truth
  about existing agents, and what to do with events from the runner's buffer the panel does
  not "remember".
- "Marks `runner_lost` and waits": until when? An explicit manual operation "raise the
  session from a snapshot on another runner" is needed, otherwise the snapshots of section
  6.3 have nowhere to be applied.

**What to change:** add these three rules to section 6.2, with a test for each.

### P5. The work snapshot: its content and direction are not defined

- A scheduled push saves only commits. An agent mid-turn holds uncommitted edits and new
  files. The snapshot must include the working tree: a service commit made inside the
  sandbox, under `refs/lado/wip/…`.
- Direction: the panel takes the snapshot by fetch through the runner's channel. Then the
  sandbox needs no credentials of the panel.
- A fetch from an untrusted source: only into a bare repository, with object checks
  (`fetch.fsckObjects`), without submodules, without a checkout on the panel's side. Size
  quotas are needed.

### P6. The experiments: gaps in the thresholds and the method

- **No threshold:** E9 ("the ladder rests on it" is not a threshold), E12 (what if two CLIs
  of four can continue a conversation?), E13.
- **E3:** the decision "the proxy into a separate container" does not close the question
  completely. The Agent API gateway must still be reachable from the sandbox inside the
  runner.
- **The method fell out.** The first version had "8+ dedicated vCPU, 10 interleaved runs
  with the spread" and an 8-hour run. In the second the 8-hour run is left only in M5b's
  gate, though runsc on a VPS is switched on in M5a. Bring the method back into E1, and the
  run into the gates of both tracks.
- **E5 is largely outdated.** The tmux busy loop was fixed in April 2026 (PR #12851). The
  spikes ran on release 20261123.0. It is enough to confirm from the changelog that the poll
  and PTY fixes are in it, and keep a short regression check. The threshold "look for a
  version with the fix" is not needed.
- **Add E14: gVisor as Docker's runtime on a VPS.** On an own Linux server the standard way
  is to install `runsc` on the host and run the sessions' containers with
  `--runtime=runsc`. Then no privileged nested runner is needed, no seccomp profile of its
  own and its upkeep for engine versions. The price: the installer changes the host, and
  someone needs access to the Docker socket. The nested variant is required only where
  nothing can be installed on the host (Docker Desktop). E14's result decides whether the
  cloud track needs nested runsc at all (a refinement of K1).

### P7. The Dangerzone precedent supports less than claimed

The plan (section 1) says: "Dangerzone is built the same way". Per their documentation, not
in the main points:

| | Dangerzone | LADO's runner (profile R+net) |
|---|---|---|
| runsc | rootless | as root |
| Capabilities of the outer container | all dropped except `SYS_CHROOT` (earlier also `SETFCAP`) | `SYS_ADMIN`, `NET_ADMIN`, `NET_RAW`, `SETUID`, `SETGID`, `SETFCAP` |
| The sandbox's network | none | a netns and veth per sandbox, iptables |
| Sandboxes per container | one, single-use | many, long-lived |

The plan rejected the rootless variant Dangerzone uses (ptrace between sentries). So the
precedent supports only the idea "runsc in a container as a portability layer". For LADO's
privilege profile the sources have no precedent.

**What to change:**
- Reword item 1 of section 1.
- Raise the priority of the checks that narrow the runner's privileges: mandatory AppArmor,
  rootless Docker and userns-remap (in E7), E14.
- Check the variant from the open questions of `session-isolation.md`: rootless with a
  separate uid per sandbox. It brings back Dangerzone's profile and closes the ptrace
  problem.

### P8. M2 is too big for one gate

M2 has about ten steps, including the change of the process model (P3). If the owner's yes
is needed only per milestone, there is no checkpoint between the start and the end of M2.

**What to change:**
- Split: M2a, the persistent Agent API process and moving the tools; M2b, the backend,
  `Workspace`, the launch bundle, paths, the agent's environment.
- Make M1's gate documents, not only a prototype: the Agent API protocol spec in
  `openspec/specs` and a decision record on the process model.

### P9. The threat model: what is missing

- **A compromised runner.** It holds the keys of all its sessions in the proxy's memory,
  the terminals' PTYs and the channel to the panel. A row is needed: what the panel takes
  from the runner on trust and what it checks.
- **The agent's configuration in the repository itself** (`.claude/settings.json` with
  hooks, `.mcp.json`). It runs inside the sandbox, so it is limited by it, but it can replace
  or silence LADO's hooks. Anthropic has a separate protection for this
  (`--confine-repo-settings`). A row and a decision are needed.
- **T1 "closed after runc"** is true only with secrets issued per session. Tie the row to
  M2's step on the agent's environment.

### P10. The `gh` and `glab` token in the sandbox is the main asset in a cloud, and the fix is put off "for later"

A personal token in the sandbox plus allowed egress to `github.com` give write access to
every repository the token covers. The threat model honestly counts this as never closed,
but names no date for a fix.

**What to change:**
- Before M5a: a recommendation and a check in `lado doctor`, a separate narrow token per
  project.
- "Open a PR/MR" as an Agent API tool: into the shared milestone before the fork (together
  with P1), not "later".

---

## 4. Answers to the questions of the plan's section 9

1. **The runner calls in itself + a reverse SSH tunnel for a panel on a laptop.** The
   direction: yes. Reverse SSH: not in the first cloud delivery (P2).
2. **The ladder "as today → API boundary → (uid) → runc → runsc".** Yes. Add on a VPS the
   variant "runsc as Docker's runtime", depending on E14 (P6).
3. **Repositories locally: both modes, starting with bind, honestly labelled.** Yes.
4. **A native macOS install without isolation, but with the API boundary.** Yes.
5. **`lado server` as a mandatory persistent process.** Yes, on the conditions of P3.
6. **M0 and M1 in parallel; E1, E9, E3 and step 1.1 first.** Yes. Add E14 to the first
   batch: it is cheap and may shorten the cloud track.

---

## 5. What changed since the first review

- Dropped: K2, K3, K4, K5 (except the consequences, P3), K6, K8, K11 (except P6), K12, K13,
  K14.
- Partly remaining: K1 (P1, P2), K7 (P10), K9 (P4), K10 (P5).
- New after the recheck: P6 (E5 outdated, E14), P7 (Dangerzone).
