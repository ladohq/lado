# Session isolation: the development plan

Date: 2026-11-27, checked against `main` 059e600f. **Status: not started** (M0 under way,
see the plan). This file turns the living plan,
[session-isolation-plan.md](session-isolation-plan.md), into epics and tasks. The plan
stays the source of truth for **what** is done and **in which order**: its decisions
(D1, D2, Q1-Q5), threats (T1-T11), experiments (E1-E15), failure semantics (6.1-6.4) and
milestones (M0-M6). This file says **how**: one epic per milestone, one task per pull
request, each task written so that a fresh coding agent can start it from its text alone.
Where this file had to go beyond the plan or found a gap, it says so in
[section 6](#6-questions-for-the-human); nothing here overrides the plan.

Who reads it: the human, to approve epics and answer the questions of section 6 (each
epic starts with a plain-words summary); the lead of each development session, to cut
tracker tasks; the developer of one task, who reads its epic's section and its own task.

Code references were verified on `main` 059e600f. The line numbers of
[A1, the code seams](session-isolation/a1-code-seams.md) still hold for `runtime.py`,
`hooks.py`, `mcp_stdio.py`, `mcp_server.py`, `loop.py`, `state.py` and
`providers/base.py`; `git_credential.py` moved by a few lines (`read_token` 30, `main` 50)
and `git_servers.py` too (`helper_command` 837, `variables` 884, `gh_variables` 928,
`glab_command` 969). A developer rechecks the lines of their own task before starting:
the code moves.

1. [Principles of the transition](#1-principles-of-the-transition)
2. [Map](#2-map)
3. [Epics](#3-epics)
4. [Compatibility and migration](#4-compatibility-and-migration)
5. [How to run the work](#5-how-to-run-the-work)
6. [Questions for the human](#6-questions-for-the-human)

## 1. Principles of the transition

1. **Every task leaves LADO fully working.** Each task is one pull request that can be
   released on its own: the whole of `make check` is green, nothing is half-wired behind
   a missing piece, and a release cut right after it is a good release. Tasks are not
   released one per version: releases bundle tasks as today (an RC per minor,
   [docs/release.md](../release.md)).
2. **The default does not change for users until the human decides.** Isolation stays
   off ("as today", step 0 of the ladder Q2) until M5b's gate. **The one announced
   exception is D2**: in M2a `lado server` becomes an always-running process for native
   installs, in one minor release with a CHANGELOG line (plan 6.1).
3. **New behaviour sits behind an explicit setting; no silent fallbacks.** A switch is a
   named setting (an environment variable for developers and tests while a path is new; a
   per-project or per-session choice in the UI and the CLI once users may choose). When the
   chosen path cannot work, LADO fails or warns loudly, never quietly takes the old path
   (AGENTS.md, "No silent drops").
4. **Each epic has a rollback.** While a new path is being built, the old one is the
   default and the switch goes back to it. After a default flips, the old path stays for at
   least one minor release, so that `lado update <previous>` or the switch is a way back.
   A schema migration's way back is the one LADO already has: the copy
   `LADO_HOME/backups/lado.db.schema-<N>` that `lado update <older>` restores.
5. **Old and new paths are tested side by side** until the old one is removed: the
   integration suite runs in both modes in CI (as the provider matrix does), and a
   contract test runs the same cases against each implementation of an interface.
6. **What the user sees is said exactly** in each task: usually nothing; otherwise a
   CHANGELOG line (written by the rules of [docs/release.md](../release.md), "CHANGELOG.md"),
   a UI label, a `lado doctor` check, a CLI option. Refactors with no visible change get no
   CHANGELOG line.
7. **Tests at the lowest layer that can catch the bug** (AGENTS.md, "Testing"):
   unit by default; integration with the fake agent for anything that crosses processes
   (hooks, `lado mcp`, the server, tmux); container tests for `docker/` and runners;
   smoke and live for changes in how LADO talks to a real CLI. Every boundary gets a
   **negative test**: the call that must be refused is made and seen refused.
8. **The shared parts are done once.** The runsc pieces shared by M5a and M5b (the image,
   seccomp, AppArmor, doctor) are done by whichever track reaches them first (plan 7).

## 2. Map

### 2.1 Epics in order

| Epic | In plain words | Depends on | Waits for experiments | Default for users changes? |
|---|---|---|---|---|
| **M1** Agent API groundwork | Agents get a personal pass; the code that agents run is cut in two halves; the protocol is written down | — | E9, E14, E15 (done) for the threat model | no |
| **M2a** Agent API in the server | The agents' requests go to `lado server` instead of touching LADO's files themselves | M1 gate | — | **yes, once (D2)**: `lado server` always runs |
| **M2b** The boundary | An agent no longer gets LADO's folder, the tmux socket or other sessions' secrets; the code can run agents elsewhere | M2a's tools on the server | — | no |
| **M3** Survive restarts | Work is snapshotted, conversations continue after a restart; a network proxy that watches; a separate user for agents if possible | M2b | E12 (conversations), E10 (uid) | no (all opt-in) |
| **M4** The runner | Sessions can run in a separate container (the runner); on a Linux server, a container per session (runc) | M3 | E1 (storage default), E8 (limits, see Q-6), E7 (where runc is offered), E2 (warnings) | no (opt-in per project) |
| **M4b** Closing the network and keys | The proxy enforces a list of allowed hosts; keys and git tokens never enter the sandbox; logins per session | M4 | E4 (logins) | no (opt-in with M4) |
| **M5a** Cloud | LADO on an own server: protected panel, runner beside it, gVisor | M4b | E11 (hybrid only), E5 | no (a new install kind) |
| **M5b** Local gVisor | runsc for local machines; then, by the human's decision, isolation by default | M4b | E1, E2, E5, E6, E7, E8, E12, E13; Q5 | **yes, by the human's decision at M5b's gate** |
| **M6** Cloud service | Hosted LADO, bring your own key | M5a, lawyers | — | a new product |

### 2.2 The diagram

```
M0 experiments (running alongside, results feed the gates below)
 │
 ▼
M1 ──► M2a ──► M2b ──► M3 ──► M4 ──► M4b ──┬──► M5a (cloud) ──► M6 (service)
                 ▲      ▲      ▲      ▲     │
                 │     E10    E1,E8   E4    └──► M5b (local runsc) ──► isolation by default
                 │     E12    E7,E2               ▲
                 │                                E5,E6,E12,E13, Q5
       (M2a tools one per release:
        list_models → finish_worker → spawn_worker → start_session)
```

### 2.3 What can run in parallel

- **M0 and M1.** The M0 experiments (E1, E2, E4-E8, E10-E13) run on their own machines and
  in their own sessions (plan, "How M0 and M1 run") while M1 is coded. M1 needs only the
  results already in (E9, E14, E15) for the threat model at its gate.
- **Inside M1.** M1-1 (token), M1-2 (hook split), M1-3 (MCP front) and M1-4 (artifact
  confinement) touch different files and can go in parallel; M1-6 (prototype) starts once
  M1-2 and M1-3 are merged or from their branches; M1-7 (spec) and M1-8 (decision record)
  close the epic.
- **Inside M2a.** After M2a-1 to M2a-4, the session passes (M2a-6) and the simple calls
  (M2a-7) can go in parallel; the four tools (M2a-8 to M2a-11) are one per release, in
  order, as the plan says.
- **Inside M2b.** The execution backend (M2b-1), the git workspace (M2b-2) and the launch
  bundle (M2b-3) are independent; the removal of LADO's variables from the agent's
  environment (M2b-8) waits for every agent-side reader to be moved (M2b-4 to M2b-7).
- **M3's tasks** are independent of each other.
- **M4's images (M4-1)** can start during M3; the runner's channel and backend wait for
  M3's snapshots only for the "across a runner restart" part of M4's gate.
- **After M4b** the two tracks M5a and M5b run in parallel (plan 7).

### 2.4 Experiments and what each one unblocks

| Experiment | Status (plan, section 5) | Unblocks | If it fails |
|---|---|---|---|
| E14 | done, passed | M5a: runsc as the host's runtime on an own server; M4-7 network scheme B | — |
| E9 | done, softened threshold | M4-7: runc mode only on a Linux host with Docker, with its flags | — |
| E3 | done, passed | M3-3 and M4b-1: the strict proxy may live inside the runner | — |
| E15 | done, passed | M5b: R-uid as a candidate (Q5) | — |
| E1 | not started | M4-6: the storage default (bind or volume); M2b-2: whether the read-only fingerprint becomes asynchronous; M5b: runsc only by choice if over 3× slower | the volume becomes the default; runsc stays opt-in |
| E2 | not started | M4: memory warnings; M5b: a shared rootfs and the installer warning | — |
| E4 | not started | M4b-7: logins per sandbox for Claude | a login per sandbox for Claude too |
| E5 | not started | M5a, M5b: the runsc release to pin | pin to a release with the fix |
| E6 | not started | M5b on Windows | fix the installer before M5b |
| E7 | not started | M4-7 and M5: where runc or runsc is offered at all | `lado doctor` says so; not offered there |
| E8 | not started | M5b: limits in the nested runner; see Q-6 for M4 | limits per container |
| E10 | not started | M3-5: the separate uid step | no uid step; the ladder skips step 2 |
| E11 | not started | M5a step 4 (the hybrid) | asynchronous hooks before the hybrid |
| E12 | not started | M3-1 labels; M5b's default | a CLI that cannot is labelled; Claude or Codex failing blocks M5b's default |
| E13 | not started | M5b: Docker Sandboxes as an external provider | the question is closed |

## 3. Epics

Each task block has the same fields. **Size**: S is under a day of a coding agent's work
and a short review, M is one to three days, L must be split before it starts. **Depends
on** names tasks that must be merged first.

### 3.1 M1: Agent API groundwork

**Goal in plain words.** Today every agent's helper programs (`lado hook`, `lado mcp`) open
LADO's database and LADO's tmux server themselves, with no proof of who they are. M1 gives
each agent a personal pass (a token), splits those helpers into a thin "client" half and a
"server" half that still run in one process, writes the protocol between the halves down,
and tries the whole idea once in a throwaway prototype.

**What the user sees.** Nothing, except one fix: an agent can no longer make an artifact out
of a file outside its own folders (M1-4).

**What it protects against.** Nothing closed yet (the plan's threat table has no M1
column). M1-4 closes one concrete path of T1 (an artifact of `~/.lado/lado.db` or of a token
file, A1 C13). M1-1 is the base of T2's closure in M2b.

**Entry conditions.** The thresholds approved (done before M0). Nothing else: M1 is
refactoring with no change of behaviour.

**Exit gate** (plan 7, M1): the Agent API protocol spec merged in `openspec/specs`; the
decision record on the process model merged; the prototype reviewed; the threat model
(plan, section 4) approved by the human, with the first M0 results (E9, E14, E15) in.

#### M1-1. A token per agent

- **Goal.** Each launch of an agent gets `LADO_AGENT_TOKEN`, a value that proves "I am
  agent A of session S, launch I". The in-process halves check it; env identity
  (`LADO_SESSION`, `LADO_AGENT`) becomes a claim the token must match.
- **Scope.** In: a new module `agent_token.py` with `mint(session, agent, instance)` and
  `verify(token) -> (session, agent, instance)`; HMAC-SHA256 over a versioned string
  `v1|<session>|<agent>|<instance>`, the token carries a key id; keys in
  `LADO_HOME/agent-api/keys/<id>` (mode 600, made on first use); rotation: a new key is
  made on demand, a key is kept while any running agent's launch used it, retired after.
  The check in `hooks.main` and `mcp_stdio.main`: a wrong or missing token is handled like
  an earlier instance today (hooks.py 345-346: exit 0, nothing done), logged to `hooks.log`
  and the error journal. Out: any transport (M2a); permissions beyond what exists
  (`COMMAND_TOOLS`, mcp_server.py 37, and the read-only role, line 106, stay where they
  are; M2a moves them to the server).
- **Where in the code.** `providers/base.py` `agent_env` (686) adds the token;
  `runtime._command` (3673) and the window's `env.json` carry it like other variables
  (never in argv, never in tmux's environment: docs/design/agents.md); `agent_env.RESERVED`
  already reserves every `LADO_*` name; `hooks.main` (332), `mcp_stdio.main` (421),
  `login_wait.main` (69).
- **Compatibility.** A hook or `lado mcp` started with **no** token is an agent launched by
  a LADO before this task (section 4.1): accept it as today, logged once per agent, until
  the session's next restart. A token that is present and wrong is refused.
- **Users see.** Nothing.
- **Switch / rollback.** No switch: there is no behaviour change. Rollback is a revert.
- **Tests.** Unit: mint/verify, a tampered token, another instance's token, a retired key,
  key file mode. Unit `test_providers.py`: the token is in the agent's env, not in argv.
  Integration (`tests/integration/test_agents.py`): a fake agent's hook with a wrong token
  changes no status; with the right one it does.
- **Docs/spec.** docs/design/agents.md (the agent's environment); docs/design/modules.md
  (the new module).
- **CHANGELOG.** No: not visible.
- **Size / depends on.** S. —

#### M1-2. The hook split in two halves, with the two event classes

- **Goal.** `lado hook` becomes a client half (read stdin, take the read-only fingerprint
  when due, call the server half, print the answer) and a server half (the instance fence,
  `parse_event`, `handle`, `_mark_printed`), still in one process. Each neutral event is
  tagged with its class, "needs an answer" or "notification" (plan 6.1).
- **Scope.** In: a new module `agent_api.py` with `hook_event(token, native, payload,
  fingerprint) -> output`; `hooks.main` becomes the client and calls it through one
  function of a client module (`agent_client.py`) whose only implementation in M1 is the
  in-process call; the event class as data next to the neutral events in
  `providers/base.py` (26-38: `SESSION_START` … `HOOK_ERROR`), with a function
  `event_class(provider, native) -> NEEDS_ANSWER | NOTIFICATION` that each provider can
  refine. The fingerprint and its baseline file (`hooks._fingerprint` 119,
  `_write_baseline` 110) move to the client; the client learns `read_only` and the hook
  limit from two new hook arguments that `base.hook_argv` (831) writes (A1, seam 1). Out:
  any socket; the on-disk queue (M2a-3).
- **Where in the code.** `hooks.py` (`main` 332, `handle` 182, `_idle` 292,
  `_wait_for_mcp` 81 stays on the server side); `providers/base.py` `hook_argv` 831;
  the providers' hook writers: `claude.py` 364-373 (settings.json), `codex.py`
  (config.toml `[hooks]`), `opencode_family.py` 258 and 380 (the plugins' options);
  `opencode_plugin.js` and `opencode_tui_plugin.js` pass the argv through unchanged.
- **Compatibility.** The server half accepts the old argv shape (no new flags): it then
  takes the fingerprint itself, as today. Agents launched before the update keep working
  until they restart.
- **Users see.** Nothing.
- **Switch / rollback.** None needed; revert.
- **Tests.** The whole suite unchanged (A1 lists the protecting files:
  `test_read_only_hooks.py`, `test_providers.py`, `test_runtime.py`, `test_liveness.py`,
  `test_error_journal.py`, `test_recommendation.py`; integration `test_agents`,
  `test_read_only`, `test_mid_turn_messages`, `test_human_messages`, `test_session_loop`,
  `test_agent_liveness`; `make test-js` for the plugins' argv). New unit test in the style
  of `tests/test_lazy_imports.py`: importing the client module loads none of `lado.state`,
  `lado.runtime`, `lado.tmux`. New unit test: every neutral event of every provider has a
  class.
- **Docs/spec.** docs/design/agents.md (hooks section: the two halves, the classes).
- **CHANGELOG.** No.
- **Size / depends on.** M. M1-1 (the server half takes the token).

#### M1-3. The `lado mcp` front as a proxy

- **Goal.** The MCP front (`mcp_stdio.Front`, 155) talks to "an MCP backend" through an
  interface instead of to the SDK it loads in-thread. The local backend is today's
  in-thread SDK. The front's own reads and writes of `lado.db` go through `agent_api`.
- **Scope.** In: `McpBackend.open(token) -> (send_line, recv_line)` (A1, seam 2);
  `Front._prepare` (257) and `Front._record_ready` (324) call `agent_api.tool_set(token)`
  and `agent_api.record_ready(token)`; the answer cache (`_cache_folder` 68) keeps its
  place for now. Out: a remote backend (M2a); moving the cache (M2b-5).
- **Where in the code.** `mcp_stdio.py` (`Front`, `main` 421, `_load_server` 121);
  `mcp_server.py` (`build` 131, `serve` 514).
- **Users see.** Nothing; the fast start (openspec `mcp-server-start`) must stay as fast:
  measure the first `tools/list` before and after.
- **Switch / rollback.** None; revert.
- **Tests.** `test_mcp_stdio.py` (also guards the SDK's private `_lowlevel_server`),
  `test_mcp_server.py`; integration `test_mcp_start.py`, `test_mid_turn_messages.py`;
  `tests/smoke/probe_mcp.py` in CI (real CLIs list the tools). New: the front module
  imports no `lado.state` after start (lazy-import test).
- **Docs/spec.** docs/design/agents.md (MCP section).
- **CHANGELOG.** No.
- **Size / depends on.** M. M1-1.

#### M1-4. `write_artifact(file=)` only from the agent's folders

- **Goal.** Close the exfiltration path of A1 C13: today `artifacts.write` resolves
  `Path(me.cwd, file)` and an absolute path stays as it is (artifacts.py 271-274), read by
  `_read_file` (666) as the `lado mcp` process, so any file the user can read can become
  an artifact.
- **Scope.** In: a confined read: the resolved real path (symlinks resolved) must be under
  the agent's cwd, its worktree, or its temp folder (`base.make_temp_dir`, 782); else
  `ArtifactError` naming the rule. Out: reading the file on the client side and sending
  bytes (M2a-7, when a transport exists).
- **Where in the code.** `artifacts.py` `write` (246), `_read_file` (666); the tool's
  description in `mcp_server.py` `write_artifact` (271).
- **Users see.** An agent that tries to attach a file from outside its folders gets an
  error saying where files may come from.
- **Switch / rollback.** None (a security fix); revert.
- **Tests.** Unit `test_artifacts.py`: inside, outside, `..`, a symlink pointing out, an
  absolute path inside. Integration: the fake agent's `artifact_write` with a path in
  `LADO_HOME` is refused.
- **Docs/spec.** docs/design/artifacts.md; the artifacts spec under `openspec/specs/`
  (`artifact-panel` or a new requirement where `write_artifact` is specified: check which
  spec holds it).
- **CHANGELOG.** Yes, `### Fixed`: "**Artifacts only from the agent's own folders.** …".
- **Size / depends on.** S. —

#### M1-5. The event-class table per CLI

- **Goal.** For each of the four CLIs, a table: native hook event → neutral event → class
  → what the CLI does with the hook's output and at its deadline (`hooks.deadline`, 67;
  `TURN_END_HOOK_TIMEOUT`, base.py 828) → what happens when the hook exits empty. This is
  the input of the spec (M1-7) and of M2a-3.
- **Scope.** In: read each provider's hook writer and the facts already checked by hand in
  docs/design/agents.md; check by hand what is not written there (a short smoke run per
  CLI if needed). Out: code.
- **Where.** `providers/claude.py`, `codex.py`, `opencode_family.py`, `kilo.py`,
  `opencode.py`; the M1-2 code.
- **Users see.** Nothing.
- **Tests.** M1-2's "every event has a class" test is the code's half of this table.
- **Docs/spec.** A section of the M1-7 spec.
- **CHANGELOG.** No.
- **Size / depends on.** S. M1-2.

#### M1-6. The throwaway end-to-end prototype

- **Goal.** Prove the whole path once, cheaply, before the spec is fixed: the Agent API
  over a Unix socket served by `lado server`, a second execution backend that runs an
  agent in a plain container (no sandbox), the fake agent, one supervisor and one worker
  exchanging a message and the worker's commit reaching merge.
- **Scope.** In: whatever is quickest; findings written as a list for the spec and the
  decision record (latency of a hook over the socket; what broke when LADO_HOME was not
  mounted; how the MCP front's calls map onto the server; how long ops behave). Out:
  quality, tests, reuse. Per the plan: a draft PR on ladohq labelled "prototype, do not
  merge", closed and its branch deleted once its findings are in the spec; no CHANGELOG.
- **Where.** A separate branch from M1-2/M1-3.
- **Users see.** Nothing.
- **Tests.** None required; a script that runs it end to end is the deliverable.
- **Docs/spec.** The findings, as an artifact of the session and attached to the tracker
  task; then folded into M1-7 and M1-8.
- **CHANGELOG.** No.
- **Size / depends on.** M (timeboxed to three days). M1-2, M1-3.

#### M1-7. The Agent API protocol spec

- **Goal.** A capability spec in `openspec/specs/agent-api/` that M2a implements.
- **Scope.** In (plan 6.1 and M1 step 5): the version and its handshake (modelled on
  `state.SchemaError`, which `hooks.main` already swallows); the token and what it
  permits (tool sets per role, `COMMAND_TOOLS`, read-only roles); event ids and "at least
  once, processed exactly once"; retries and their budget against each CLI's deadline;
  the two event classes and the M1-5 table; the on-disk queue (where, size limits, strict
  parsing on replay); long operations (`spawn_worker`, `start_session`: an operation id,
  a timeout, polling for the result); the separate entry (a Unix socket, not the UI's
  routes); errors and what the client prints. As a proposal for the spec to confirm or
  change: HTTP/1.1 over the Unix socket with JSON bodies, headers `Authorization: Bearer
  <token>`, `Lado-Api-Version`, `Lado-Event-Id`; a client of the standard library only
  (A1 4.10: the client must not import the MCP SDK or `state`). Out: the runner channel
  (M4-2).
- **Where.** The repository's OpenSpec flow: a change under `openspec/changes/` with
  `proposal.md`, `design.md`, `tasks.md` and the spec delta, archived on merge into
  `openspec/specs/agent-api/spec.md` (as `openspec/changes/archive/` shows).
- **Users see.** Nothing.
- **Tests.** None (a document). Links checked.
- **CHANGELOG.** No.
- **Size / depends on.** M. M1-5, M1-6.

#### M1-8. The decision record on the process model

- **Goal.** Decide and write down: `lado server` is mandatory (D2) and how it is kept up
  (auto-start by `lado start`, any CLI command and the hook client; the Docker
  entrypoint); where the Agent API entry is (the socket's path; macOS limits a Unix
  socket path to 104 bytes, so a long `LADO_HOME` needs a short path, e.g. under
  `/tmp/lado-<uid>/` as the temp folders are, `base.py` 760-782); the fate of `lado loop`
  (the plan recommends moving the passes into the server, a thread per session with the
  same per-session lock, `loop.take_lock` 84); what `lado server stop` does while sessions
  run (Q-2).
- **Where.** A new design document `docs/design/agent-api.md` with a "Decisions" table in
  the style of `docs/epics/*/decisions.md` (Q-10), linked from docs/design/agents.md.
- **Users see.** Nothing.
- **CHANGELOG.** No.
- **Size / depends on.** S. M1-6.

#### M1-9. The threat model approved

- **Goal.** The human approves plan section 4 with the M0 results in. A docs task: update
  the plan's threat table with what M0 changed, bring it to the gate.
- **Where.** `docs/research/session-isolation-plan.md`, section 4 and the M1 row.
- **CHANGELOG.** No. **Size / depends on.** S. E9, E14, E15 (done).

**Risks of M1 and how it limits them.** The split could slow every hook (an extra layer):
M1-2 keeps one process and the prototype measures the socket. The prototype could grow
into the product: it is timeboxed and never merged. The token could leak into argv or
tmux's environment: a test checks both.

### 3.2 M2a: the Agent API in `lado server`

**Goal in plain words.** The agents' helpers stop doing LADO's work themselves: they send
requests to `lado server`, which does it. For a native install this means `lado server`
always runs in the background (D2). The tools that change the most are moved one per
release: `list_models`, then `finish_worker`, then `spawn_worker`, then `start_session`.

**What the user sees.** Until the flip (M2a-12): nothing. At the flip, in one minor
release: `lado server` runs in the background on a native install whenever a session runs
(it starts by itself); `lado doctor` checks it; when it is unreachable, the session's feed
says "the server was unreachable" and messages arrive late, never lost. Docker users see
nothing: the image already runs the server as its main process.

**What it protects against.** Nothing closed by itself; it makes M2b possible (the plan's
M2b column). After M2a-11 no agent process starts panel processes (A1 4.12: a detached
`lado loop` from the supervisor's `lado mcp`).

**Entry conditions.** M1's gate passed (spec, decision record).

**Exit gate** (plan 7, M2a): the integration suite green through the server; a server
failure mid-turn checked by a test (plan 6.1); the CI budget kept (Q-3).

The switch for the whole epic: `LADO_AGENT_API=inprocess|server`, read by the client.
Default `inprocess` until M2a-12. With `server`, a client that cannot reach the server
never falls back to in-process: it follows the failure rules of plan 6.1.

#### M2a-1. The Agent API entry in `lado server`

- **Goal.** `lado server` listens on its own Unix socket for the Agent API, with its own
  token check, beside the UI's HTTP port. None of the UI's routes are reachable on it.
- **Scope.** In: a listener in the server process (a thread or an asyncio server of its
  own, not a mount on the FastAPI app of `server/app.py`, so no UI route can leak onto
  it); the socket's path from M1-8, mode 600, its folder 700; the version handshake; the
  handlers call `agent_api.*`. Out: the client (M2a-2).
- **Where in the code.** `server/run.py` (`serve` 332, `housekeeping` 111,
  `resume_sessions` 86, `stop` 511); `agent_api.py`.
- **Users see.** Nothing (no client uses it yet).
- **Switch / rollback.** Unused until the client's switch says `server`.
- **Tests.** Unit: handlers with a fake request (version mismatch, bad token, unknown
  route, oversize body, malformed JSON). Integration (`test_server_process.py`): the
  server's socket exists with mode 600; a UI route asked on the socket is 404; a request
  without a token is 401.
- **Docs/spec.** docs/design/agent-api.md; docs/design/ui.md ("Server").
- **CHANGELOG.** No.
- **Size / depends on.** M. M1-7, M1-8.

#### M2a-2. The client transport

- **Goal.** `agent_client.py` gains a socket transport: HTTP over the Unix socket with the
  standard library (`http.client` on an `AF_UNIX` socket), retries with event ids, the
  version header, per-call timeouts within the hook's deadline.
- **Scope.** In: the transport, chosen by `LADO_AGENT_API`; the socket's address passed to
  the agent as `LADO_AGENT_API_ADDRESS` (a new `LADO_*` variable). Out: the queue (M2a-3).
- **Where.** `agent_client.py`; `providers/base.py` `agent_env` 686.
- **Users see.** Nothing.
- **Tests.** Unit: retry until the deadline, no retry after it, duplicate ids. Lazy-import
  test: the client imports no SDK and no `lado.state`.
- **CHANGELOG.** No. **Size / depends on.** S. M2a-1.

#### M2a-3. Hook events through the server, the on-disk queue

- **Goal.** With `server` mode, the hook client sends every event to the server and
  follows plan 6.1 when it cannot: "needs an answer" retries until the CLI's deadline
  minus a reserve (`hooks.QUEUE_RESERVE`, 34), then exits empty and writes the event to an
  on-disk queue; "notification" goes to the queue with retries. The server processes the
  queue when it is up (the agent becomes idle) and delivers waiting messages by the usual
  pass (`runtime.sweep`, 2499).
- **Scope.** In: the queue in the agent's state folder (`base.state_path`, 730; in M2b its
  path comes from a variable, not from `LADO_HOME`); strict parsing and a size cap on
  replay (the server reads files an agent could write); de-duplication by event id in
  `lado.db`, a new table (schema bump: `state.SCHEMA_VERSION` 44 → next, a step in
  `MIGRATIONS`, `tests/agent_helpers.previous_schema` updated); a notice in the session's
  feed "the server was unreachable from <agent> for <n> s"; `_wait_for_mcp`'s 20 ms poll
  of the database (hooks.py 81) becomes a wait inside one request on the server (over a
  socket it must, A1 4.4). Out: the heavy tools (M2a-8 to M2a-11).
- **Where.** `hooks.py`, `agent_api.py`, `state.py`, the feed (`server/feed.py`).
- **Users see.** Only in `server` mode: the notice above.
- **Switch / rollback.** `LADO_AGENT_API=inprocess`.
- **Tests.** Integration with the fake agent, the gate's test: the server is killed in the
  middle of a turn; the turn ends; the agent stops as if it had no messages; a message
  sent meanwhile is delivered after the server comes back; no event is applied twice.
  Unit: the queue's parsing refuses oversize and malformed entries.
- **Docs/spec.** agent-api spec (queue requirement); docs/design/agents.md.
- **CHANGELOG.** No (not default yet).
- **Size / depends on.** M. M2a-2.

#### M2a-4. Automatic start and `lado doctor`

- **Goal.** `lado start`, any CLI command that needs it and the hook client start the
  server if it is not running, the way `loop.ensure` (loop.py 134; cli.py 1081) starts a
  loop today; `lado doctor` checks it is up and its socket answers; a crash goes to the
  error journal.
- **Scope.** In: `server_run.start_background` (425) from the CLI and the hook client
  (the hook client only once per call, without waiting past its deadline); the doctor
  check; the Docker entrypoint needs no change (the server is the container's command),
  checked by a container test. Out: the flip of the default (M2a-12).
- **Where.** `cli.py`, `server/run.py`, `doctor.py`, `hooks.py`.
- **Users see.** In `server` mode only.
- **Tests.** Integration: no server running, `lado start` brings one up; a hook with no
  server running brings one up. Container: the image's server answers on the socket.
- **CHANGELOG.** No. **Size / depends on.** M. M2a-1.

#### M2a-5. The integration fixture with a server per test, and the CI budget

- **Goal.** The integration suite can run with a real `lado server` per test home, and
  CI runs the suite in both modes (as it runs the provider matrix).
- **Scope.** In: a fixture in `tests/integration/conftest.py` that brings up a server per
  test's `LADO_HOME` when the mode is `server` (each test has its own home and tmux
  socket, docs/testing.md); a CI job dimension in `.github/workflows/ci.yml` (job
  `integration`); the measurement of the extra time, written into the tracker task and the
  plan. Out: deciding the budget (Q-3).
- **Users see.** Nothing.
- **Tests.** The suite itself.
- **Docs.** docs/testing.md (the fixture, the second mode).
- **CHANGELOG.** No. **Size / depends on.** M. M2a-4.

#### M2a-6. The sessions' passes in the server

- **Goal.** If M1-8 decided so: the session loop's pass (`loop.run` 151: `check_windows`,
  `check_starts`, `check_turns`, `sweep`) runs in `lado server`, a thread per session,
  under the same per-session lock (`loop.take_lock` 84), so that a running `lado loop` and
  the server never both run one session's pass.
- **Scope.** In: the threads, their start and stop with sessions, the lock; `lado loop`
  stays as a command for the old mode. Out: removing `lado loop` (M2a-13).
- **Where.** `loop.py`, `server/run.py`, `runtime.py` (`start_session` 855,
  `stop_session` 3052, `resume_at_start` 3187).
- **Users see.** Nothing (in `server` mode, one fewer process per session).
- **Switch / rollback.** The mode switch.
- **Tests.** Integration `test_session_loop.py` in both modes; a test that a loop process
  and the server never run one session's pass at once.
- **Docs.** docs/design/agents.md ("the session loop").
- **CHANGELOG.** No. **Size / depends on.** M. M2a-5.

#### M2a-7. The simple calls on the server

- **Goal.** The tools that only read or write LADO's state and type messages
  (`send_message`, `read_messages`, `ask_human`, `recommend`, `list_agents`,
  `list_artifacts`, `read_artifact`, `write_artifact`, `flow_status`, `flow_advance`) run
  in the server in `server` mode.
- **Scope.** In: the front forwards these tool calls; `write_artifact(file=)` is read by
  the front (the client side) from the agent's folders and sent as bytes, which needs a
  new parameter on the server side (base64 content). Check in M1-7 whether
  `flow_advance` is simple (it moves a run and may tell other agents; it starts no
  process): if not, it moves with `spawn_worker`. Out: the four heavy tools.
- **Where.** `mcp_stdio.py`, `mcp_server.py` (131-511), `artifacts.py`.
- **Users see.** Nothing.
- **Tests.** Integration `test_mid_turn_messages.py`, `test_human_messages.py`,
  `test_flow_runs.py` in both modes; unit for the new parameter.
- **CHANGELOG.** No (the MCP tool's parameters agents see do not change). The internal
  parameter is not an agent-facing change. **Size / depends on.** M. M2a-3.

#### M2a-8 to M2a-11. The heavy tools, one per release

Each of these is one task and one release, in this order (plan 7, M2a). In `server` mode
the tool runs in the server; the supervisor's `lado mcp` no longer resolves the login
shell, reads secret layers or starts processes for it.

| Task | Tool | Code | What leaves the agent's process tree | Tests |
|---|---|---|---|---|
| M2a-8 (S) | `list_models` | `runtime.list_models` 1183; `mcp_server.py` 359 | the agents' environment and the model servers' keys (A1 N4) | unit `test_mcp_server.py`; integration `test_worker_model.py`, `test_session_model.py` both modes |
| M2a-9 (M) | `finish_worker` | `runtime.finish_worker` 1629, `close_worker` 1739, `remove_work` 1688; `mcp_server.py` 463 | git on worktrees, `tmux kill-window` | integration `test_agents.py` (finish, discard) both modes |
| M2a-10 (M) | `spawn_worker`, `flow_start`, `flow_cancel` | `runtime.spawn_worker` 1248, `agent_layers` 3508, `_ours` 3569, `github_takeover.run` 157; `runs.spawn_worker` 389, `runs.start` 45; `mcp_server.py` 377, 429 | `$SHELL -ilc`, every secret layer, git and model keys, `env.json`, `git worktree add`, `tmux new-window` (A1 2.2) | integration `test_agents.py`, `test_flow_runs.py`, the canaries `test_project_secrets_canary.py`, `test_model_settings_canary.py` both modes |
| M2a-11 (M) | `start_session` | `runtime.start_approved_session` 2312; `loop.start` 121; `mcp_server.py` 492 | a detached `lado loop` Popen from the agent's tree (A1 N18) | integration `test_session_start.py` both modes; a test that no process of the agent's tree is the parent of a loop |

Each: long operations follow the spec (an operation id, a timeout, the client polls);
users see nothing; no CHANGELOG line; rollback is the mode switch. Each depends on the one
before it and on M2a-7.

#### M2a-12. The flip: `server` mode by default (D2)

- **Goal.** `LADO_AGENT_API` defaults to `server`. A native install runs `lado server` in
  the background whenever a session runs.
- **Scope.** In: the default; `lado server stop` with sessions running behaves as decided
  in Q-2; `lado update`, `lado uninstall` and the session stop paths stop and start the
  server in the right order (`self_update.py`, `uninstall.py`); docs/install.md and
  docs/cli.md say that the server always runs and why. Out: removing the in-process path
  (M2a-13).
- **Users see.** A background process `lado server` on native installs; the doctor line;
  the "server unreachable" notice when it happens.
- **Switch / rollback.** `LADO_AGENT_API=inprocess` for one minor release (documented in
  docs/cli.md as a temporary way back); `lado update <previous>`.
- **Tests.** The CI default flips; the `inprocess` dimension stays until M2a-13.
  Integration `test_update_process.py` and `test_uninstall_process.py`: the server is
  stopped and started around them.
- **Docs.** docs/install.md, docs/cli.md, docs/design/agents.md, docs/design/ui.md.
- **CHANGELOG.** Yes, a minor release, `### Improved` (or `### Upgrade`): "**LADO's server
  now always runs.** On a computer without Docker, LADO keeps its server running in the
  background while any session runs; `lado doctor` checks it." Wording by the human.
- **Size / depends on.** M. M2a-11; the human's yes at the gate.

#### M2a-13. Remove the in-process path

- **Goal.** One minor release after M2a-12 (Q-1): the in-process transport, the `lado
  loop` process for sessions (if M2a-6 moved the passes) and the CI dimension go.
- **Scope.** Remove the switch; `lado loop` either goes or stays as a debugging command
  that refuses while the server runs the session (decide in M1-8). Stale tests rewritten
  or removed in the same PR (docs/testing.md, "When to add, merge or remove a test").
- **Users see.** Nothing (unless they set the switch: the CHANGELOG says it is gone).
- **CHANGELOG.** Yes if the variable was documented: `### Upgrade`.
- **Size / depends on.** M. M2a-12 plus one minor release.

**Risks of M2a and how it limits them.** A server crash now stops every session's hooks:
the queue, the loud notice and the error journal make it visible, and the gate's test
proves nothing is lost. CI time grows: measured in M2a-5 before the flip (Q-3). The
Unix socket path may be too long on macOS: decided in M1-8, tested with a long test home.
Old agents across `lado update`: section 4.1.

### 3.3 M2b: the boundary

**Goal in plain words.** After M2a the agents ask the server for everything; M2b takes away
what they no longer need: LADO's folder path, the tmux socket, other sessions' secrets and
the shared git credential helper. It also puts the places where LADO starts agents and runs
git behind interfaces, so that a later runner can do them somewhere else.

**What the user sees.** Nothing, except: `lado doctor` warns when a project's GitHub or
GitLab token has broader rights than the project needs (M2b-9), with a link to making a
narrow one.

**What it protects against** (plan, section 4, column M2b): T1 partly (same uid, but no
paths and no other sessions' secrets handed to the agent); T2 closed for the API (not for
the same uid, which can still open `~/.lado` by path); T4 closed for the core (the rule
of plan 6.3 applies to the core's git); T11 a narrow token per project plus the doctor's
check.

**Entry conditions.** M2a-11 merged (every tool runs on the server). The flip M2a-12 is
not needed to start M2b's refactors, only for M2b-8.

**Exit gate** (plan 7, M2b): **the CI cell "boundary"**: the agent cannot reach
`LADO_HOME`, the socket or others' secrets; the integration suite is green; no canaries
found (M2b-11).

#### M2b-1. The execution backend, the local one is tmux

- **Goal.** Every start, kill, liveness check, typed delivery and terminal of an agent goes
  through one interface, `ExecutionBackend`, whose local implementation calls today's
  `tmux` functions.
- **Scope.** In (A1, seam 4): the verbs `start_session_host`, `launch`, `alive`, `kill`,
  `kill_session`, `type_text`, `open_terminal`, `close_viewers`, `popup` (optional; a
  backend that has none says so), `attach_command`; a new module `execution.py`. The
  local backend calls `tmux.<fn>` by module attribute so that `tests/conftest.py`
  `fake_tmux` (494) keeps working unchanged. Out: a second backend (M2b-10).
- **Where in the code.** About 25 call sites (A1 C1, C2, C10): `runtime.py` 941, 1054,
  1342, 1440, 1527, 1747, 2495, 2534, 2802, 3065, 3085, 3170, 3248, 3266; `loop.py` 79;
  `cli.py` 2381 (`lado attach`); `terminal.py` (`open` 74, `open_login` 203,
  `close_viewers` 242); `runs.py` `_popup` 860; `logins.py` (`open_window` 345,
  `end_windows` 388); `uninstall.py` (pane pids); `server/feed.py` (the derived status).
  Line numbers are those of A1, rechecked for `runtime.py`; recheck the rest.
- **Users see.** Nothing.
- **Tests.** The whole suite unchanged. New: a grep-style test (like
  `tests/test_lazy_imports.py`) that no module but `execution.py`, `tmux.py` and
  `gui_session.py` imports `lado.tmux`.
- **Docs.** docs/design/modules.md; docs/design/agents.md.
- **CHANGELOG.** No. **Size / depends on.** M (mechanical). —

#### M2b-2. The git workspace, with the rule of plan 6.3

- **Goal.** All git the core runs on a session's repository goes through one interface,
  so that a runner can run it where the repository lives, and so that the rule "the
  trusted side never opens a repository directory the sandbox has written to" has one
  place to hold.
- **Scope.** In (A1, seam 5): the operations `branches`, `add_worktree`,
  `remove_worktree`, `delete_branch`, `restore`, `work_of`, `gone`, `tip`, `remote`,
  `exclude`/`include`, `session_worktrees`, plus the read-only fingerprint and the merge
  check; their results typed as data that is not trusted (no path from them is opened by
  the core). The local implementation is `runtime.git` (503) as today. **Name:** the
  module `git_workspace.py`, class `GitWorkspace`, because `server/models.py` already has
  a `Workspace` (316, the projects folder) and `projects.py` uses "workspace" for
  `LADO_REPOS`. Out: making the fingerprint asynchronous (only if E1 says the read-only
  fingerprint takes over 2 s: then a task of its own).
- **Where in the code.** `runtime.py` (1248-1371, 1629-1864, `session_worktrees` 3323,
  `exclude_worktrees` 3800, `remote` 518); `runs.py` (45-94, `_restore_worktree` 436,
  `_close` 918); `server/models.py` (work state); `fingerprint.py`; `hooks.py`.
- **Users see.** Nothing.
- **Tests.** `test_runtime.py`, `test_runs.py`, `test_closed_refusals.py`; integration
  `test_flow_runs.py`, `test_agents.py`. New: a grep-style test that `runtime.git(` is
  called only in `git_workspace.py`.
- **Docs.** docs/design/modules.md.
- **CHANGELOG.** No. **Size / depends on.** M. —

#### M2b-3. The launch bundle

- **Goal.** A provider's launch becomes `render` (pure: what files, variables and argv an
  agent needs, with `${LADO}` in place of the local interpreter) and `materialize` (write
  it at the place of execution). Locally `materialize` does what the launch does today,
  links included.
- **Scope.** Split by provider, one PR each:
  - **M2b-3a (M):** the types and `providers/base.py` (`launch_command` 513,
    `config_path` 709, `state_path` 730, `make_temp_dir` 782, `link_skills` 858,
    `hook_argv` 831, `mcp_server` 850, `lado_command` 658) and Claude Code
    (`providers/claude.py` 344-426; `edit_config` 747 is done at materialize time in the
    agent's own HOME).
  - **M2b-3b (M):** Codex (`providers/codex.py`, CODEX_HOME, `_settle_login` 672).
  - **M2b-3c (M):** OpenCode and Kilo (`opencode_family.py` 248-259, 372-380, the two JS
    plugins).
  Out: copying skills (only the remote materialize copies: M4-4); `env.json` without keys
  (M4b-3).
- **Users see.** Nothing.
- **Tests.** `test_providers.py`, `test_codex.py`, the per-provider launch tests;
  `make test-js`; smoke in CI (each real CLI parses its config). New: `render` is pure
  (no file written, no process started) for each provider.
- **CHANGELOG.** No. **Size / depends on.** 3 × M. —

#### M2b-4. Paths relative to the place of execution

- **Goal.** The paths the database keeps for agents and runs (`agents.cwd`,
  `runs.worktree`, `sessions.repo`) become handles of a place (a backend and a path in
  it). For the local backend the path is today's absolute path, so nothing changes.
- **Scope.** In: a `sessions.backend` column, default `local` (schema bump, a
  `MIGRATIONS` step, `previous_schema`); the core uses the handle where it crosses the
  backend (M2b-1, M2b-2, M2b-3). Out: any non-local value (M4).
- **Where.** `state.py`; `runtime.spawn_worker` (the worktree path, 1294); `runs.py` 88.
- **Users see.** Nothing.
- **Tests.** `tests/test_state.py` (migrations); the suite.
- **CHANGELOG.** No (a schema bump makes the release minor; the CHANGELOG's `### Upgrade`
  line about restarting sessions is the release's, not this task's).
- **Size / depends on.** S. M2b-1, M2b-2.

#### M2b-5. Agent-side files out of `LADO_HOME`

- **Goal.** Nothing an agent's processes write or read lives under a path they find from
  `LADO_HOME`: `hooks.log` and the error journal go to the server through the API
  (`telemetry.record` from hooks and `lado mcp`); the MCP answer cache
  (`mcp_stdio._cache_folder` 68) and the read-only baseline (`hooks._baseline_path` 99)
  move to the agent's own state folder, whose path the launch gives; the `lado.db`
  existence check in `hooks.main` (341) becomes the server's answer.
- **Where.** `hooks.py`, `mcp_stdio.py`, `telemetry.py`, `agent_api.py`.
- **Users see.** Nothing (`lado log` and the error journal show the same).
- **Tests.** `test_error_journal.py`, `test_mcp_stdio.py`, `test_read_only_hooks.py`;
  integration `test_telemetry_processes.py`.
- **CHANGELOG.** No. **Size / depends on.** M. M2a-12.

#### M2b-6. The git credential helper through the Agent API

- **Goal.** Today the helper command in the agent's git config is LADO's Python with
  `lado.git_credential --home <LADO_HOME> --server <id>`, and it reads
  `<LADO_HOME>/git-servers/<id>/token` (git_credential.py 30, 50; git_servers.py 837,
  844): any agent can run it for any saved server (A1 2.4). After: the helper asks the
  Agent API with the agent's token, and the server answers only for the servers this
  session may use (Q-7).
- **Scope.** In: the helper's new form (no `--home`, no file read); glab's
  `valueFromCommand` (`glab_command` 969) the same; the certificate path
  (`sslCAInfo`, git_servers.py 880) given by the launch, not under `LADO_HOME`. Out:
  `GH_TOKEN` in the environment (stays until M4b-6 replaces PRs by a tool).
- **Users see.** Nothing (agents push and pull as before).
- **Tests.** `test_git_credential.py`; integration `test_git_server_access.py`,
  `test_git_server_certificate.py`, `test_git_server_host_tool.py`; live (the push to a
  saved server, docs/testing.md layer 6) on the next RC. Negative: an agent of session A
  asking for a server not allowed to A gets nothing.
- **CHANGELOG.** No. **Size / depends on.** M. M2a-12.

#### M2b-7. `lado login-wait` through the Agent API

- **Goal.** The agent's own window waiting for a login (login_wait.py `main` 69) stops
  reading secret folders and writing `lado.db`: it asks the server "may I start" and
  blocks.
- **Where.** `login_wait.py` (`layers` 48, `main` 69), `logins.py`, `agent_api.py`.
- **Users see.** Nothing.
- **Tests.** `test_login_wait.py`; integration `test_provider_logins.py`.
- **CHANGELOG.** No. **Size / depends on.** S. M2a-12.

#### M2b-8. The agent's environment without LADO's variables

- **Goal.** `providers.agent_env` (base.py 686) stops giving agents `LADO_HOME`,
  `LADO_TMUX_SOCKET`, `LADO_ENV_DIR`, `LADO_REPOS` (A1 2.7). They get the token, the API
  address, their own state folder's path and the session/agent names.
- **Scope.** In: the variables; every remaining reader found by a test that runs the
  integration suite with them unset. Out: the window's `env.json` (it is this agent's
  own launch file: it stays, read and deleted by `agent_env.main` 640).
- **Users see.** Nothing. An agent's shell no longer finds `$LADO_HOME` (documented in
  docs/design/agents.md).
- **Switch / rollback.** Revert; this task is small and comes last.
- **Tests.** Unit `test_providers.py` (the env's names); the whole integration suite.
- **CHANGELOG.** No. **Size / depends on.** S. M2b-5, M2b-6, M2b-7.

#### M2b-9. Secrets per session and a narrow `gh`/`glab` token

- **Goal.** An agent gets only its session's secrets: its project's secrets, LADO's
  secrets for its CLI's login, and the git servers its session may use (Q-7). `lado
  doctor` checks each project's GitHub/GitLab token for rights broader than needed
  (plan 6.3, T11).
- **Scope.** In: `runtime.agent_layers` (3508) and `_ours` (3569) filtered per session;
  a per-project token on the Git servers page (or the project's settings) used before the
  server's one; the doctor's check where the server reports a token's scopes (GitHub
  classic tokens report scopes in a response header; for fine-grained tokens and GitLab,
  find what the APIs tell before promising a check: not verified here). Out: PRs through
  the API (M4b-6).
- **Users see.** A project can have its own narrow token; `lado doctor` warns about broad
  ones. Docs: docs/git-servers.md.
- **Tests.** Unit; integration canaries (`test_project_secrets_canary.py`): an agent of
  project A finds no secret of project B.
- **CHANGELOG.** Yes, `### New`: "**A narrow token per project.** …"; `### Improved` for
  the doctor's check.
- **Size / depends on.** M (split UI from core if the page changes). M2b-6.

#### M2b-10. A second backend in the tests and a contract test

- **Goal.** A test-only execution backend that runs agents where `LADO_HOME` and the tmux
  socket do not exist: a plain container (the M1 prototype's form) on Linux CI. A contract
  test runs the same cases against the local backend and this one.
- **Scope.** In: the backend under `tests/` (not shipped); the contract test (start, alive,
  type, kill, terminal bytes, git workspace operations). Out: any user-facing runner.
- **Users see.** Nothing.
- **Tests.** The contract test; marker `container` (needs Docker, like layer 7).
- **Docs.** docs/testing.md.
- **CHANGELOG.** No. **Size / depends on.** M. M2b-1, M2b-2, M2b-3.

#### M2b-11. The CI cell "boundary"

- **Goal.** The gate's proof. A CI job runs the integration suite's agents in the second
  backend, with canaries: a unique value in a file in `LADO_HOME`, in another session's
  secret, in another project's secret and in the tmux socket's path; the agents' fake
  steps try to read each, and the job fails if any is found in an agent's output, an
  artifact or a commit.
- **Scope.** In: the job in `.github/workflows/ci.yml`, a member of `ci-ok`; the fake
  agent's probing steps (`tests/integration/fake_agent.py`). Out: a same-uid native
  check, which cannot pass by design (T2's "not for the same uid").
- **Users see.** Nothing.
- **Docs.** docs/testing.md; plan, M2b row status.
- **CHANGELOG.** No. **Size / depends on.** M. M2b-8, M2b-10.

**Risks of M2b and how it limits them.** The refactors touch many call sites: each is
mechanical and protected by the unchanged suite plus a grep test. Something still reads
`LADO_HOME` from the agent's side: M2b-8 runs the suite with the variable unset, M2b-11
proves it in a container. A same-uid agent can still open `~/.lado` by path: the plan
accepts this for M2b; M3's uid and M4's runner close it.

### 3.4 M3: survive restarts, observe the network, a separate uid

**Goal in plain words.** Before sessions run in a separate container that may restart, LADO
must lose nothing when an agent's process dies: the conversation continues, and the work
not yet committed is kept. M3 also adds a network proxy that only watches (it shows which
hosts the agents reach, so that the later allowlist is known) and, if the experiment E10
says it works, runs agents as a separate user in the Docker image.

**What the user sees.** Opt-in features: per project, "send the agents' network through
LADO's proxy and show where they go" (M3-3); in the session's view, which CLI continues its
conversation after a restart and which starts over (M3-1). Nothing changes by default.

**What it protects against.** T3 is observed, not closed (plan, the M4 column says
"open (the proxy observes, but is never an open proxy)"). With the uid step (M3-5): T1 and
T2 for the image, as the agents' user cannot read `~/.lado`.

**Entry conditions.** M2b's gate. E12 for M3-1's labels; E10 for M3-5.

**Exit gate** (plan 7, M3): a restart mid-turn loses nothing.

#### M3-1. Conversations continue after a restart

- **Goal.** When an agent's process is restarted (a crash, `lado stop`/`start`, later a
  runner restart), each CLI continues its conversation where it can; where it cannot, the
  UI says loudly "the conversation starts over" (plan E12).
- **Scope.** In: per provider, the CLI's own way to continue a conversation, kept in the
  agent's state folder; what LADO does today on resume (docs/design/agents.md describes
  the resume of an agent; check what each provider's resume continues before coding);
  the label. Out: a runner restart (M4).
- **Where.** `providers/*`, `runtime.resume_at_start` (3187), the UI's agent card.
- **Users see.** The label, for CLIs that cannot continue.
- **Tests.** Integration with the fake agent (a restart mid-turn); live per provider on
  the next RC.
- **CHANGELOG.** Yes if behaviour changes for some CLI: `### Improved`.
- **Size / depends on.** M per provider group; E12.

#### M3-2. Work snapshots

- **Goal.** Inside the place where the agent works, a service commit of its working tree
  (uncommitted and new files) is made periodically under `refs/lado/wip/<agent>`, without
  touching the agent's index; the panel takes it by fetch into a bare repository (plan
  6.3, P5).
- **Scope.** In: the snapshot with a temporary index (`GIT_INDEX_FILE` to a temp file,
  `git add -A`, `write-tree`, `commit-tree`, `update-ref`), run through the git workspace
  (M2b-2) at the place of execution; the fetch into `LADO_HOME/snapshots/<session>.git`
  with `fetch.fsckObjects`, no submodules, no checkout, a size quota; the period and quota
  as settings; a restore operation for a stopped agent (used by M4-11). Out: the UI for
  restoring (M4-11).
- **Users see.** Nothing until restore exists (a hidden ref in the repository; check it
  is excluded from pushes: refs outside `refs/heads` are not pushed by default).
- **Tests.** Unit: the agent's index is unchanged; a quota breach is refused. Integration:
  an agent killed mid-turn with uncommitted files; the snapshot has them.
- **Docs.** docs/design/agents.md or a new section in docs/design/agent-api.md.
- **CHANGELOG.** No (internal until restore exists). **Size / depends on.** M. M2b-2.

#### M3-3. The proxy in observe mode

- **Goal.** A proxy that agents' HTTPS goes through, opt-in per project, which records the
  hosts reached and never acts as an open proxy (E3).
- **Scope.** In: a new module (e.g. `egress_proxy.py`) implementing E3's strict proxy:
  CONNECT only; strict head parsing (CRLF only, no control bytes, no obs-fold, 4 KiB a
  line, 50 headers, 16 KiB in all, 10 s for the head); the target `name:port`, a DNS name
  only, no IP literals in any notation; a port list; the name resolved, **all** resolved
  addresses global (no private, loopback, link-local, metadata), and the connection made
  to the checked address; per-client connection limits. "Observe" means the allowlist is
  not enforced: every allowed-by-address host passes and is recorded, as "would be
  refused" where it is not on the project's future list. The agents get `HTTPS_PROXY`
  and the CLIs' own proxy settings (check each CLI honours them). E3's probe table
  becomes the proxy's regression suite. Out: enforcing (M4b-1); kernel owner rules (M3-4).
- **Where.** New module; `runtime._command` (env); the project's settings (UI and
  `lado project set`).
- **Users see.** A per-project setting and a list of hosts the agents reached.
- **Switch / rollback.** The setting, off by default.
- **Tests.** Unit: E3's table (each row a case). Integration: a fake agent through the
  proxy to a local fake endpoint is refused (a loopback address) and to a test name that
  resolves to a global address passes (needs a resolver stub). Smoke: each real CLI starts
  with the proxy set.
- **Docs.** docs/design/agents.md; a user doc section in docs/install.md or a new page.
- **CHANGELOG.** Yes, `### New`.
- **Size / depends on.** L → split: M3-3a the proxy and its suite (M), M3-3b the wiring
  and setting (M), M3-3c the UI list (S). M2b-8.

#### M3-4. The proxy under its own uid with owner rules

- **Goal.** The plan asks the proxy to run "from day one under its own uid, with owner
  rules" (`iptables -m owner` OUTPUT rules on the proxy's uid: no private, loopback,
  link-local except Docker's DNS, E3). This needs root or `NET_ADMIN` where the proxy
  runs.
- **Scope.** In: in LADO's Docker image, where the container is given `NET_ADMIN` (an
  opt-in compose line), the entrypoint starts the proxy as its own user and installs the
  rules; `lado doctor` says whether the rules are in place. Out: native installs (no root;
  see Q-4).
- **Where.** `docker/Dockerfile`, `docker/entrypoint.sh`, `docker/compose.yaml`,
  `doctor.py`.
- **Users see.** In the image, with the opt-in: the doctor line.
- **Tests.** Container (layer 7): the proxy's user cannot reach a private address even
  with an open request.
- **CHANGELOG.** Yes, `### Docker image`. **Size / depends on.** M. M3-3a.

#### M3-5. A separate uid for the agents (only if E10 passes)

- **Goal.** In LADO's Docker image, the agents' process tree runs as a second user that
  cannot read `LADO_HOME`, the tmux socket or other sessions' folders; the bind-mounted
  repositories stay writable for it (E10's threshold: "bind and the CLIs work").
- **Scope.** In: the user in the image; the launch through `setpriv` or similar from the
  backend's `launch`; file ownership and group of worktrees; `codex sandbox` as that user
  (E10 includes making it work). Out: native Linux and macOS (Q-5).
- **Where.** `docker/`, `execution.py` (local backend's launch), `providers/codex.py`.
- **Users see.** In the image: nothing, unless something breaks (then the doctor says so).
- **Switch / rollback.** An image setting, default as E10 and the human decide.
- **Tests.** Container: an agent cannot read `~/.lado/lado.db`; the CLIs start; a commit
  in a bind-mounted repository works.
- **CHANGELOG.** Yes, `### Docker image`. **Size / depends on.** M. E10; M2b-8.

**Risks of M3 and how it limits them.** A proxy is a new attack surface: E3's table is its
regression suite, and it is opt-in. A CLI may ignore `HTTPS_PROXY`: the smoke layer checks
each. Snapshots may grow the repository: a quota, a bare repository outside the user's.

### 3.5 M4: the runner

**Goal in plain words.** A session can run in a separate container, the runner, instead of
on the machine where LADO's panel runs. First without a sandbox (the runner itself is the
boundary between the sessions and the host); then, on a Linux machine with Docker, one
container per session (runc mode). The panel keeps the database and the UI; the runner
starts agents, holds their terminals and talks to the panel over one channel.

**What the user sees.** A per-project choice "where sessions run": on this machine (the
default, as today), in a runner, in a runner with a container per session (Linux with
Docker only). The session shows its protection level (plan, section 4: "The UI shows each
session's protection level"). With a bind-mounted folder the label says "sessions are
isolated from each other, your folder is not" (Q3). In runc mode the UI says that Codex's
own sandbox is off and the container takes its place (Q2 amended).

**What it protects against** (column M4): T1 closed with secrets per session; T2 closed;
T6 closed (Docker's limits under runc, E9, E14); T3 still open (the proxy observes); T5
open; T9 appears (a compromised runner has all its sessions).

**Entry conditions.** M3's gate (snapshots and continued conversations are needed for
"across a runner restart"). Q1 decided finally (the runner connects to the panel). E1
for the storage default (M4-6); E7 for where runc mode is offered; E8 for limits (Q-6).
The reconciliation rules written (M4-3a, the plan's open item of M4).

**Exit gate** (plan 7, M4): a LADO session reaches merge in a runner, also across a runner
restart.

#### M4-1. Two images: `lado` (the panel) and `runner`

- **Goal.** The image splits: the panel (UI, server, database) and the runner (agent CLIs,
  tmux, git, the gateway). `safe.directory '*'` is removed from the panel's image
  (Dockerfile 148; plan 6.3).
- **Scope.** In: two Dockerfile targets or files; the release workflow builds and pushes
  both (openspec `image-release`); `make docker` builds both; compose runs the panel
  alone for today's users (the runner is not needed until a project chooses it). Out: the
  runner's program (M4-2).
- **Where.** `docker/`, `.github/workflows/release.yml`, `Makefile`, `scripts/`.
- **Users see.** Nothing for today's compose users (same command, same service); a second
  image on the registry.
- **Tests.** Container tests on both images; `tests/test_docker.py`.
- **Docs.** docs/install.md; docs/release.md (4.5, 8: the images).
- **CHANGELOG.** Yes, `### Docker image`, only when users can see a difference.
- **Size / depends on.** M. —

#### M4-2. The runner program and the runner → panel channel

- **Goal.** `lado runner` runs in the runner image, connects **out** to the panel (Q1),
  registers with a token, authenticates both ways, checks the protocol version, and keeps
  a heartbeat.
- **Scope.** In: the channel (over the Docker network locally, D1; a WebSocket or HTTP
  long-poll from the runner, decided in this task's design note); registration tokens
  made in the panel (a `runners` table: schema bump); the version handshake; a buffer in
  the runner for when the panel is away. Out: TLS and a network-reachable panel (M5a).
- **Where.** New modules (`runner.py` and a panel-side `server/runners.py`); `cli.py`.
- **Users see.** Nothing until a project chooses a runner.
- **Tests.** Unit: the handshake, a wrong token, a wrong version. Integration: a runner
  process against a panel on one machine (no Docker needed for the protocol).
- **Docs.** docs/design/agent-api.md (or a new docs/design/runner.md); openspec spec of
  the channel.
- **CHANGELOG.** No. **Size / depends on.** L → split: M4-2a the protocol and spec (M),
  M4-2b the runner side (M), M4-2c the panel side and the table (M). M2b.

#### M4-3. Lease, two epochs, the buffer, reconciliation (plan 6.2)

- **Goal.** A session is bound to a runner by a lease; when the lease is lost its agents
  are `runner_lost` and wait; the runner's epoch and the session's epoch fence old work;
  after the panel is restored from a backup, the runner is the truth about live agents and
  the panel about the human's decisions.
- **Scope.** **M4-3a (S, docs):** the reconciliation rules in detail, each with its test,
  in the channel's spec: the plan's open item of M4; the human approves it. **M4-3b (M):**
  the lease, the epochs (columns: schema bump), `runner_lost` as an agent status (UI
  label), at-least-once delivery with processing once (event ids from M2a-3).
  **M4-3c (M):** reconciliation, a test per rule; events for agents the panel does not
  know are shown to the human, not applied.
- **Where.** `state.py`, `runtime.py`, `server/runners.py`, the UI's agent status.
- **Users see.** A "runner lost" status when it happens.
- **Tests.** Integration: kill the runner, restart it with a higher epoch, the lower
  epoch's agents are stopped; restore the panel from a copy, the runner's unknown events
  are shown and not applied.
- **CHANGELOG.** No until users can choose a runner (M4-9). **Depends on.** M4-2.

#### M4-4. The runner backend

- **Goal.** The second real implementation of the execution backend (M2b-1), the git
  workspace (M2b-2) and the launch bundle's materialize (M2b-3), driven over the channel.
  In the runner a gateway serves the Agent API to its agents on its own port and forwards
  to the panel with the buffer (plan 6.1, E3: only the gateway's and the proxy's ports
  open from `veth+`, nothing on `0.0.0.0`/`[::]`, the gateway answers each sandbox only by
  its own veth address; that last part applies from M4-7).
- **Scope.** In: the backend; the gateway; skills copied in, not linked; `${LADO}`
  resolved to the runner's client; the contract test of M2b-10 run against it. Out:
  sandboxes (M4-7).
- **Users see.** Nothing until M4-9.
- **Tests.** The contract test; container: a session of the fake agent in a runner
  reaches merge.
- **CHANGELOG.** No. **Size / depends on.** L → split per interface (3 × M). M4-2, M4-3b.

#### M4-5. The terminal and `lado attach` through the runner

- **Goal.** The UI's terminal of an agent in a runner is a byte stream relayed by the
  runner; the browser's protocol does not change (resize, input, end detection, view and
  control modes, the 44xx/45xx close codes; A1 4.7). `lado attach` relays or prints the
  command to use.
- **Where.** `terminal.py`, `server/terminals.py`, `cli.py` (2381), the runner.
- **Users see.** The same terminal.
- **Tests.** Integration `test_agent_terminal*.py` against the runner backend; UI e2e one
  case through a runner.
- **CHANGELOG.** No. **Size / depends on.** M. M4-4.

#### M4-6. Where the repository lives: bind first, then volume plus git

- **Goal.** Q3: per project, **bind** (the user's folder mounted into the runner,
  labelled honestly) first; then **volume plus git** (the runner clones into its volume,
  results leave by push or fetch through the workspace).
- **Scope.** M4-6a (M): bind, with the label. M4-6b (M): the volume, the clone, the way
  results come back, the "merged" check on fetched objects (plan 6.3). The default between
  them after E1 (Q3).
- **Users see.** The per-project choice and its label.
- **Tests.** Container: both modes reach merge; in bind mode the label is shown (UI e2e).
- **CHANGELOG.** Yes with M4-9. **Depends on.** M4-4; E1 for the default.

#### M4-7. The sandbox provider and runc mode on a Linux host

- **Goal.** A "sandbox provider" interface with the first provider: on a Linux host with
  Docker, a container per session of the host's Docker (`--runtime=runc`), in network
  scheme B, with the `INPUT`/`ip6tables` REJECT rules from the session bridges installed
  by the launching component at its start and checked by `lado doctor` (E9, E14).
- **Scope.** In (E9, E14): a bridge network per session, the proxy in its own network,
  `DOCKER-USER` rules over the pool (replies in, new connections in refused, out only to
  the proxy); `--dns 192.0.2.1 --cap-drop NET_RAW --tmpfs /sys/devices/virtual/dmi:ro`;
  Docker's memory and CPU limits per session container; the launching component holds
  `docker.sock` (root on the host), so it exposes a narrow API (start, stop, exec, logs of
  LADO's session containers only) and is a trusted part of the host; offered only where
  E7 says it works (`lado doctor` says why not elsewhere: Docker Desktop, SELinux,
  rootless, as E7 finds). Out: runsc (M5a, M5b); Docker Desktop (no runc step there, Q2
  amended).
- **Where.** New modules (`sandbox.py`, a launcher); `doctor.py`.
- **Users see.** On Linux with Docker: the choice "a container per session"; the label
  that Codex's own sandbox is off in this mode.
- **Tests.** Container (Linux CI): E9's isolation table as a regression suite (processes,
  files, the other session, the host's services, metadata, IPv6, DNS, the internet
  directly); the limits (a memory hog is killed). Negative: a session container reaches
  neither the host's port 22 nor the other session.
- **CHANGELOG.** Yes with M4-9.
- **Size / depends on.** L → split: M4-7a the interface and the launcher's narrow API
  (M), M4-7b the network scheme and rules with doctor (M), M4-7c limits and the
  regression suite (M). M4-4; E7.

#### M4-8. The protection level in the UI

- **Goal.** Each session shows its protection level: "as today", "API boundary",
  "separate user", "runner", "container per session", later "gVisor"; bind mode adds
  "the host is not protected from the agent's code" (plan, section 4).
- **Where.** `web/`, `server/models.py`; docs/design/ui.md first (a mockup if the human
  wants one).
- **Tests.** vitest; one UI e2e.
- **CHANGELOG.** Yes with M4-9. **Size / depends on.** M. M4-6a.

#### M4-9. The per-project choice "where sessions run"

- **Goal.** The explicit setting that exposes M4 to users: per project, in Settings and
  `lado project set`, default "this machine". A choice that cannot work here (no Docker,
  Docker Desktop for runc) is refused loudly with the reason.
- **Users see.** The setting.
- **Tests.** Unit and integration; UI e2e for the setting.
- **CHANGELOG.** Yes, `### New`: "**Run a project's sessions in a separate container.**
  …".
- **Size / depends on.** M. M4-4 to M4-8.

#### M4-10. `lado update` with runners

- **Goal.** `lado update` updates the runner image too; a panel update does not kill the
  sessions in a runner (plan 6.2); the protocol's version check refuses a runner too old
  or too new loudly.
- **Where.** `self_update.py`, `update.py`, the runner.
- **Tests.** Integration `test_update_process.py` with a runner; container.
- **CHANGELOG.** Yes, `### Upgrade` if the user must act. **Size / depends on.** M. M4-2.

#### M4-11. Raise a session from a snapshot on another runner

- **Goal.** The manual operation of plan 6.2: after a runner is lost, the human raises the
  session from its last snapshot (M3-2) on another runner; the session's epoch goes up.
- **Users see.** An action on a session whose runner is lost.
- **Tests.** Integration: a lost runner, the raise, the work of the snapshot is there.
- **CHANGELOG.** Yes with M4-9 or after. **Size / depends on.** M. M3-2, M4-3c.

**Risks of M4 and how it limits them.** The runner is a big new part: everything goes
through interfaces with a contract test, and the setting is off by default. The launching
component is root on the host: a narrow API and the docs say plainly it is trusted. Docker
updates or a dockerd restart kill containers without a restart policy (E14): the runner's
containers get one, and the lease rules handle a lost runner.

### 3.6 M4b: closing the network and the keys (shared by both tracks)

**Goal in plain words.** In a runner the agents can still send data anywhere on the
internet and still hold real keys. M4b closes that: the proxy lets through only the hosts
on the project's list; API keys and git tokens stay outside the sandbox and are added on
the way out; opening a pull request becomes a LADO tool, so the agent holds no GitHub
token; each session logs in to its CLI on its own.

**What the user sees.** With a runner chosen: a project's list of allowed hosts (prefilled
from what M3-3 observed); a question in the session when an agent needs a host not on the
list ("allow api.example.com for this project?"); logins per session instead of one for
all. Nothing for projects that run on this machine.

**What it protects against** (column M4b): T3 closed outside the allowlist (the strict
proxy of E3); T6 with per-sandbox connection limits on the shared proxy; T11 closed (PR/MR
through the Agent API); T10 decided (its open item).

**Entry conditions.** M4's gate; E4 for M4b-7.

**Exit gate** (plan 7, M4b): rows T3 and T11 closed by tests; two Codex sessions in
parallel.

#### M4b-1. The strict proxy enforces the allowlist

- **Goal.** M3-3's proxy in enforce mode inside the runner: outside the list, refused;
  owner rules on its uid; `ip6tables` REJECT from `veth+` (else IPv6 link-local reaches the
  runner's services, E3); per-sandbox connection limits (E3: one client took all 256
  slots).
- **Where.** The proxy module; the runner's start script.
- **Users see.** Refusals, shown in the session (M4b-2).
- **Tests.** Container: E3's full table inside the runner, as uid 1000 and root in the
  sandbox; the runner's rules unchanged after the probes; the T3 row's test.
- **CHANGELOG.** Yes with M4b-2. **Size / depends on.** M. M4, M3-3a.

#### M4b-2. "A host outside the list is needed"

- **Goal.** A refused host becomes a question to the human, not a silent failure: the
  proxy records it, LADO asks the human in the session (as `ask_human` does) with the host
  and the agent, and on yes adds it to the project's list.
- **Scope.** Whether the agent asks through a new MCP tool or LADO asks on the proxy's
  record: decided in the task's design note (a new MCP tool is a minor release).
- **Users see.** The question; the list in the project's settings.
- **Tests.** Integration with the fake agent and the proxy; UI e2e of the question.
- **CHANGELOG.** Yes, `### New`. **Size / depends on.** M. M4b-1.

#### M4b-3. API keys injected through each CLI's base URL

- **Goal.** The sandbox gets a placeholder key and the proxy's base URL; the runner's
  proxy adds the real key on the way to the model provider (A1 N4). `env.json` stops
  carrying keys for runner sessions.
- **Scope.** Per provider (one PR each where the CLI's setting differs): Claude Code's
  base URL setting, Codex's, OpenCode's and Kilo's provider config; model servers of
  `model_settings.py` the same. Subscription logins are not keys: M4b-7.
- **Users see.** Nothing (agents work as before).
- **Tests.** Smoke per CLI against the fake endpoint (it sees the real key, the sandbox's
  environment has only the placeholder); the canary test for keys.
- **CHANGELOG.** No (unless the UI says it). **Size / depends on.** 2-4 × M. M4b-1.

#### M4b-4. The git relay

- **Goal.** Push and fetch from the sandbox go through a relay that injects the token and
  checks branches (only the session's branches may be pushed); the credential helper of
  M2b-6 is no longer needed in the sandbox.
- **Tests.** Container: a push to an allowed branch passes, to `main` or another session's
  branch is refused; live on the next RC (the push to a saved server).
- **CHANGELOG.** No (unless branch rules are visible). **Size / depends on.** M. M4b-1.

#### M4b-5. The agent's configuration from the repository (T10)

- **Goal.** Decide, then do: what LADO does with `.claude/settings.json` hooks, `.mcp.json`
  and the like in the session's repository, which can override LADO's hooks. The plan
  leaves this an open item of M4b; the decision goes to the human first (a design note
  with options: refuse to start, ignore with a loud notice, allow per project).
- **CHANGELOG.** Yes if behaviour changes. **Size / depends on.** S (decision) + M. —

#### M4b-6. "Open a PR/MR" as an Agent API tool

- **Goal.** Agents open pull and merge requests through a LADO tool; the CLI's
  environment gets no `GH_TOKEN`/`GH_ENTERPRISE_TOKEN` (git_servers.py `gh_variables`
  928) and no glab token in runner sessions (T11).
- **Scope.** A new MCP tool (minor release). Kits that run `gh pr create` (e.g. the sdlc
  kit) must switch: Q-8.
- **Tests.** Integration with the fake git server; the T11 row's test (the sandbox has no
  token and `gh` fails).
- **CHANGELOG.** Yes, `### New` and `### For integrators` (`MCP:`). **Size / depends
  on.** M. M4b-4.

#### M4b-7. Logins per sandbox

- **Goal.** Each session in a runner has its own CLI login: the login window runs in the
  session's sandbox (A1 N1, N14), with no shared `auth.json` link (codex.py 672) and no
  shared `~/.claude.json` edits.
- **Scope.** Size L, the UI designed ahead (plan 7, M4b): **M4b-7a (S):** the UI design
  and mockup approved by the human; **M4b-7b (M):** Codex device login per session;
  **M4b-7c (M):** Claude (setup-token or a pasted code; one subscription in two sandboxes
  over a refresh, as E4 finds); **M4b-7d (M):** OpenCode and Kilo (check whether their
  OAuth uses a localhost callback, which the terminal relay cannot carry: A1 4.6).
- **Tests.** Integration `test_provider_logins.py` against the runner backend; the gate's
  "two Codex sessions in parallel" as a live test; the human by hand with real
  subscriptions.
- **CHANGELOG.** Yes, `### New`. **Depends on.** E4; M4.

**Risks of M4b and how it limits them.** The allowlist can break agents that need hosts
nobody listed: M3-3 prefills it from what was observed, M4b-2 asks instead of failing
silently. Kits that use `gh` break when the token goes: Q-8, and a loud refusal from the
kit's checks.

### 3.7 M5a: cloud (epic level)

- **Goal.** LADO runs on an own server: the panel protected for the network, the runner
  beside it over the Docker network (D1), sessions in gVisor as the host's runtime (E14).
- **Scope, in the plan's order.** 1) panel protection: TLS, a login instead of a token in
  the URL, limits on the terminal's WebSocket, a backup of `lado.db`; 2) panel and runner
  on one server with compose, runsc as the host's Docker runtime (E14's one installer step:
  download and check sha512, unpack to `/usr/local/bin`, `runsc install`, restart dockerd;
  containers without a restart policy die), network scheme B and the host's rules as in
  M4-7 (under runsc AppArmor does not apply to its processes: the protection is gVisor);
  Docker's DNS does not work under runsc, so the proxy is reached by IP; 3) k8s with an
  external sandbox provider (a pod with a RuntimeClass per session); 4) the hybrid, by a
  separate decision (E11 first; a reverse SSH tunnel would revisit 0.48.0's "no ssh in the
  container").
- **Dependencies.** M4b; E5 (the runsc release to pin); E11 for step 4.
- **Exit gate.** Dogfooding LADO on the server, an 8-hour run.
- **Open questions.** The login method for the panel; where backups go; the
  server's installer (a new install kind for docs/install.md); one runner per owner (T9).
- **Rough tasks.** TLS and login (2-3 M); WebSocket limits (S); `lado.db` backup and
  restore with the reconciliation of M4-3c (M); the compose bundle for a server (M); the
  runsc installer step and `lado doctor` (M); the runsc sandbox provider (M); k8s provider
  (L, split later); the hybrid (decision first).

### 3.8 M5b: local gVisor (epic level)

- **Goal.** runsc on the user's own machine through the nested runner (Docker Desktop on
  macOS and Windows; Linux), then, by the human's decision at the gate, isolation by
  default.
- **Scope.** runsc in the runner image, updated through `lado update`; the nested
  runner's profile R-uid or R+net (Q5, after E1, E2, E7, E8); a narrow seccomp profile
  with a loud fallback; AppArmor (`lado-runner-lite` with `userns,`, E15) installed by the
  installer; `lado doctor`; cleaning device nodes; the integration suite inside the runner
  in CI (runc and runsc); then isolation by default.
- **Dependencies.** M4b; E1, E2, E5, E6, E7, E8, E12, E13 closed; Q5.
- **Exit gate.** E1-E15 closed, an 8-hour run, a release cycle of dogfooding.
- **Open questions.** Q5; what the default flip looks like for an existing user (a
  migration of running sessions, a one-time notice); E13's Docker Sandboxes as an
  external provider; Windows path from PowerShell (E6).
- **Rough tasks.** the runsc runner image (M); R-uid profile and AppArmor in the
  installer (M each, per platform); seccomp profile (M); doctor checks (S); CI cells (M);
  device-node cleaning (S); the default flip (M, with the human's decision).

### 3.9 M6: cloud service (epic level)

- **Goal.** A hosted LADO, bring your own key.
- **Dependencies.** M5a; the lawyers' answer (subscription terms for a hosted service,
  A3 2.3).
- **Open questions.** Multi-user (the attacker "another user" of the threat model);
  billing; a GitHub App for push (plan 6.3); runner per owner (T9).
- **Rough tasks.** Decided after M5a.

## 4. Compatibility and migration

### 4.1 Running sessions across `lado update` mid-epic

- `lado update` stops every session and the UI, installs, and resumes them
  (`self_update.py`; docs/release.md, "Versions"): after an update every agent is launched
  again by the new version, with its new hook argv, token and environment. In LADO's
  Docker image a new image restarts the container and `runtime.resume_at_start` (3187)
  resumes the sessions.
- **The gap:** an upgrade that does not go through `lado update` (`uv tool upgrade lado`,
  `pip install -U` under running sessions). Old agents then run the new code through
  their old hook argv (the argv names a module and `sys.executable`, `interpreter.run_module`).
  Rule for every task that changes the hook argv, the agent's environment or the
  protocol: **the new code accepts the previous shape** (no token, old argv flags) and
  handles it as today, logged once per agent, until the session restarts. A schema skew is
  already safe: `hooks.main` catches `state.SchemaError` (hooks.py 359).
- After M2a-12, an old agent whose hooks still run in-process keeps working until restart
  by the rule above; after M2a-13 the in-process path is gone, so M2a-13 ships only once
  a minor release has passed (every `lado update` restarts the agents).
- Runners (M4 on): the panel and the runner check the protocol version at registration;
  a mismatch is refused loudly and `lado update` updates both (M4-10).

### 4.2 Schema migrations

Tasks that bump `state.SCHEMA_VERSION` (44 today; each bump a step in
`state.MIGRATIONS`, `tests/agent_helpers.previous_schema` updated, a minor release):

| Task | What | Way back |
|---|---|---|
| M2a-3 | event ids for de-duplication | the migration's copy, `lado update <older>` restores it |
| M2b-4 | `sessions.backend` | the same |
| M4-2c | `runners` | the same |
| M4-3b | lease, epochs, `runner_lost` | the same |
| M4b-2 | a project's allowlist (if kept in `lado.db`) | the same |

Bundle bumps that land in one release into one migration step where they are ready
together. The RC checks the way back on a test home (docs/release.md 4.4).

### 4.3 Install kinds

| Install | M1-M2b | M3 | M4-M4b | M5 |
|---|---|---|---|---|
| Native macOS | the server always runs (M2a-12); boundary as on Linux | proxy observe (no owner rules); no uid step (Q-5) | runner only through Docker Desktop, no runc mode (E9) | M5b through Docker Desktop (Q4) |
| Native Linux | the same | proxy observe; no uid step (Q-5) | runner with Docker; runc mode where E7 allows | M5a on an own server; M5b local |
| WSL2 (Windows) | the same as Linux (native Windows is refused, `console.py`) | the same | runner with Docker Desktop's engine or Docker in WSL2: runc mode only with a Linux Docker engine, to be checked by E7 or E6 | M5b; E6 for the PowerShell path |
| LADO's Docker image | nothing visible (the server is the container's process) | owner rules with an opt-in `NET_ADMIN` (M3-4); uid step (M3-5) | the panel image; the runner image beside it | M5a's compose |

### 4.4 The four providers

| Epic | Claude Code | Codex | Kilo, OpenCode |
|---|---|---|---|
| M1 | hook argv in settings.json (M1-2); event table (M1-5) | hook argv in config.toml; event table | the plugins' options carry the argv; `make test-js` |
| M2a | hooks over the server; smoke | the same | the plugins spawn the same argv |
| M2b | launch bundle M2b-3a; `edit_config` at materialize; credential helper | M2b-3b; CODEX_HOME; credential helper | M2b-3c |
| M3 | conversation continue (E12); `HTTPS_PROXY` honoured? | the same; `codex sandbox` as a second uid (E10) | the same |
| M4 | in a runner; keychain does not exist there (A1 4.5: say so loudly) | runc mode turns off its own sandbox (label) | the same |
| M4b | base URL key injection; login per sandbox (setup-token, E4) | base URL; device login per sandbox; two sessions in parallel (the gate) | base URL; OAuth callback check |

Every task that changes how LADO configures a CLI runs the smoke layer in CI (all four),
and the live layer on the next RC.

## 5. How to run the work

### 5.1 Epics, tasks, sessions, pull requests

- **One epic per milestone in the tracker** (M1, M2a, M2b, M3, M4, M4b; M5a, M5b, M6 when
  they are near). Its description links to its section here. As in LAD-162
  ([decisions](../epics/lad-162/decisions.md)), tasks are created one at a time when
  their step is reached, and findings and leftovers go into the next task; this file's
  task list is the plan, not a promise of tracker items.
- **One task = one development session = one pull request**, reviewable in one sitting.
  An L task is split before it starts (the splits are named above).
- **An epic's records** go to `docs/epics/<key>/` (brief, decisions, plan, report), as
  the earlier epics do.
- **The gate** of each epic is the human's yes on the plan's milestone gate, with the
  checks listed in that epic's "Exit gate".

### 5.2 The task text to paste into a new session

```
Task <id> (<tracker key>): <title>

Goal: <the task's Goal, in one or two sentences>

Context (read first):
- docs/research/session-isolation-dev-plan.md, section <epic>, task <id>
- docs/research/session-isolation-plan.md, sections <the ones the task names>
- AGENTS.md; docs/design/agents.md (for hooks, runtime, loop, mcp, agent_env, providers)
- <the spec or design doc the task changes>

Where in the code: <files and functions from the task; recheck line numbers on main>

Scope: in: <...>. Out: <...> (do not do these here).

Behaviour for users: <none | exactly what changes>. Switch: <name, default>.

Checks before the PR:
- make lint; make test; make test-integration (and both Agent API modes while they exist)
- <make test-js | make test-container | smoke in CI> as the task says
- the new negative test is seen failing without the change
- docs/spec updated in the same PR; CHANGELOG line <yes: group | no>

Do not:
- change the default for users unless this task says so
- add a fallback to the old path when the new one fails: fail or warn loudly
- touch the user's global agent config; copy code from other projects
- merge or push to main; open the PR and report

Report (to the lead, in the session): what was done, the PR, what was left out and
where it should go, the numbers measured (if any), questions for the human.
```

### 5.3 How results flow back

- When a task is merged: its tracker task is closed; nothing changes here.
- When an epic's gate passes: the plan's milestone row gets its Status ("done,
  <date>") and its header's status line is updated; this file's header status says which
  epic is under way.
- When an experiment finishes: the plan's section 5 row gets its result, as the M0
  reports do; the epics it unblocks (section 2.4 here) are named in that update.
- When a task finds that this file is wrong (a seam that does not exist, a test that
  cannot be written): the task's report says so, and the lead fixes this file in a docs
  PR before the next task of the epic starts.

## 6. Questions for the human

Each blocks the epic named; a recommendation for each.

| # | Question | Blocks | Recommendation |
|---|---|---|---|
| Q-1 | After the flip to the server (M2a-12), how long does the in-process path stay as a way back? | M2a-13 | One minor release, then removed; documented as temporary in docs/cli.md |
| Q-2 | Once the server is mandatory, what does `lado server stop` do while sessions run? | M2a-12 | Refuse with the sessions named and the command that stops them (`lado stop --all`), with `--force` that stops anyway; `lado update` and `lado uninstall` already stop sessions first |
| Q-3 | The CI time budget for running the integration suite in two modes (plan 6.1: an open item of M2a) | M2a-5 | Allow up to +50 % on the `integration` job while both modes exist, measured in M2a-5 before the flip; drop the old mode's run at M2a-13 |
| Q-4 | **Gap in the plan.** M3 asks the observe proxy to run "under its own uid with owner rules" from day one, but owner rules need root or `NET_ADMIN`, which native installs and today's image do not have | M3-4 | Address checks in the proxy's code always (never an open proxy); kernel owner rules only where the proxy runs with `NET_ADMIN` (the image with an opt-in, then the runner); `lado doctor` says which; native installs get the proxy without owner rules |
| Q-5 | The separate uid step (M3, Q4): only in the Docker image, or also native Linux and a separate macOS user? Native needs admin rights to create a user | M3-5 | The Docker image only in M3, if E10 passes; native only on real demand |
| Q-6 | **Deviation.** The brief asks for E8 before M4's limits. E8 measures cgroups per sandbox under runsc in the nested runner; for M4's runc mode (a container per session on the host) E9 and E14 already showed Docker's limits work | M4-7c | Let M4-7c go on E9/E14's evidence; keep E8 as the entry condition for limits in the nested runner (M5b) |
| Q-7 | With secrets per session (M2b-9), which saved git servers may a session's agents use: all (today), or only the hosts of its project's remotes plus a per-project list? | M2b-6, M2b-9 | The hosts of the session repository's remotes plus an explicit per-project list; a refusal names the setting |
| Q-8 | When "open a PR/MR" becomes a LADO tool (M4b-6), kits that call `gh pr create` lose the token in runner sessions. How do kits move? | M4b-6 | Only runner sessions lose the token; the kit's tool check refuses loudly there; the sdlc kit gets a release that uses the tool |
| Q-9 | Does a native install get M4's runner mode (it needs Docker on the machine)? | M4-9 | Yes, opt-in per project, offered only when Docker answers; `lado doctor` says why not otherwise |
| Q-10 | Where do the decision records of M1 live (the process model, later the channel)? | M1-8 | A new design document `docs/design/agent-api.md` with a decisions table, linked from docs/design/agents.md and docs/design/modules.md |
| Q-11 | The principle "every task is a release": tasks with an MCP or schema change force a minor release, and each minor needs an RC and a freeze. Release per task, or bundle? | all | Every task is releasable; releases bundle tasks at the human's pace, an RC per minor as today |

Not questions, but points where this file goes beyond the plan, for the human to notice:

- **Names.** The plan's "`Workspace`" is named `GitWorkspace` in `git_workspace.py`
  (M2b-2), because `server/models.py` has a `Workspace` already and "the workspace" is
  `LADO_REPOS` in `projects.py`.
- **The boundary cell (M2b-11)** can only be proved where the agent does not share LADO's
  uid and file system: it runs in the second backend (a container), not on a native
  same-uid setup. The plan's M2b column says the same ("partly, same uid").
- **A Unix socket path limit** (104 bytes on macOS) may force the Agent API's socket out
  of `LADO_HOME` into a short path; M1-8 decides.
- **The on-disk hook queue** lives in the agent's own state folder (M2a-3), so it still
  works once the agent has no `LADO_HOME` (M2b-8); the server reads it with strict
  parsing, as a file an agent could have written.
