# Plan: Session isolation, M1 — Agent API groundwork (LAD-321)

## State
Phase: plan · Epic run: epic/epic-isolation-m1 · Branch: base (main)
In work: — · Next: S1 · Open checks: — (S9's draft PR is closed in S11)
OpenRouter budget: $10 for the epic, spent $0 (S2 measures a run's cost; every live run adds its cost here)
Standing rules of the human:
- One step at a time: the next starts only after the previous one merged and passed its manual check (#8915 q1).
- Merge into main only by a pull request with a green `ci-ok` and the human's explicit "merge" (statement).
- Every step leaves LADO working and releasable; no release plan up front; the CHANGELOG line in the step that changes what users see (statement).
- A step that changes how LADO talks to an agent CLI (hooks, `lado mcp`, MCP tools, the agent's environment) gets a live run before its merge: Claude Code on the human's subscription, once per step; the other CLIs on a cheap OpenRouter model; $10 on OpenRouter for the whole epic for now (#8901 q4, #8915 q3, q4).
- A step that changes product code carries a detailed manual checklist, written for an agent on the human's other machine, run on a build of the pull request's branch before the merge, native and Docker installs where the step touches them (#8901, #8915 q5).
- Review findings go into the next steps; a wrong plan is fixed by a separate docs pull request (statement).
- Every code step (S3–S7) has a negative test seen red first: the call that must be refused is made against the code without the change and seen to pass wrongly, then refused with it (statement, dev plan 1.7).
Last review: 2026-11-28, base at 76ebdc6a

## Steps

The source of each M1 task's scope is `docs/research/session-isolation-dev-plan.md`, section
3.1 (its line numbers checked against main on 2026-11-27: each step checks them again).
Steps are numbered in the order they run; the M1 task each implements is in its title.

### S1 — The smoke tests reviewed and made to catch breakage
Status: planned
Check: a review document (what each smoke test proves, where it can pass while the path it
names is broken, what M1's hook and MCP changes need from it) attached to the task; every
fix it lists for this step merged with the smoke green in CI on Linux and macOS for all four
CLIs; each fixed gap shown able to fail (the test seen red against a deliberately broken
path, e.g. a hook that does nothing, a tool that is not called); a new or changed smoke
test's own duration (`--durations` in the cell's log, Linux and macOS) at most 60 s.
No manual check by the human and no live run: the step changes tests only (open question 4).
Touches: tests/smoke/, tests/fake_endpoint.py, tests/real_clis.py, scripts/smoke_ci.py, the smoke part of .github/workflows/ci.yml, tests/test_ci_workflow.py, docs/testing.md
Notes: `tests/fake_endpoint.py` already has scripted turns for the Anthropic API (Claude
Code) and the Responses API (Codex) that call LADO's `mcp__lado__list_agents`
(test_smoke.py: the auto-mode test for Claude Code, the server test for Codex); the chat
completions API (Kilo, OpenCode) has none, so no smoke proves a tool call for them. Two
questions of the step: (a) a scripted turn for chat completions; (b) whether a read-only
`list_agents` is enough for M1, or a call that writes (`send_message`) and changes state the
test can see is needed, since S5 checks the token in `lado mcp` and S7 moves its reads and
writes behind a seam. Fixes past the step's threshold become S1b.

### S2 — Live runs before a merge, cheap and on demand
Status: planned
Check: one command runs the live tests locally (LADO's container) for one CLI or all:
Claude Code on the human's subscription, Codex, Kilo and OpenCode on OpenRouter; its report
names each CLI's result and the OpenRouter cost of the run; a run of all four on main
passes, its cost recorded in the task and in the State's budget line; when the cost of a
run of the three OpenRouter CLIs times the live runs left in the plan (S4, S5, S6a, S6b, S7,
plus one repeat each) exceeds what is left of the budget, the step asks the human: raise the
ceiling, a smaller live set per step, or another model (open question 3); docs/testing.md says when a step runs it and how;
no key or subscription token in any log, config or evidence (a test checks it).
Touches: tests/live/, tests/real_clis.py, scripts/smoke_ci.py, Makefile, docs/testing.md
Notes: CI's `live.yml` gets its key only on main and tags, so a pull request's live run is
local. Today "no live test uses a Claude subscription" (docs/testing.md): how the
subscription reaches the test without touching the human's config is the step's design
(open question 1).

### S3 — LADO's folder closed to other users of the machine (M1-10)
Status: planned
Check: unit tests (a new home is 700, a wide one tightened silently, a home of another
owner left alone and reported by `lado doctor` with the command that fixes it; a file the
server creates under `LADO_HOME` is 600 by its umask), each negative case seen red first; container test (`stat` of `/home/lado` and
`~/.lado/lado.db` in the image); CHANGELOG line under Improved; docs/cli.md (`lado doctor`);
the human's manual check on native macOS and Docker: an existing `~/.lado` at 755 becomes
700 after `lado start`, LADO works as before, `lado doctor` is quiet, a second account
cannot list it.
Touches: state.py, server/run.py, cli.py, docker/entrypoint.sh, doctor.py

### S4 — Artifacts only from the agent's own folders (M1-4)
Status: planned
Check: unit tests in test_artifacts.py (inside, outside, `..`, a symlink out, an absolute
path inside), the outside cases seen red first; integration: the fake agent's `write_artifact` with a path in `LADO_HOME` is
refused with a message that says where files may come from; the spec where
`write_artifact` is specified and docs/design/artifacts.md updated; CHANGELOG under Fixed;
live run (an agent attaches a file of its worktree); the human's manual check: an artifact
from the worktree works, one from `~/.lado/lado.db` is refused with a clear message.
Touches: artifacts.py, mcp_server.py, openspec/specs/, docs/design/artifacts.md

### S5 — A token per agent (M1-1)
Status: planned
Check: unit (mint/verify, tampered token, another instance's token, a retired key, key file
mode 600; the token in the agent's env, never in argv nor tmux's environment), the refusals
seen red first; integration: a fake agent's hook and its `lado mcp` with a wrong token
change no state and the refusal is written to `hooks.log` and the error journal, with the
right one they work, with none (an agent launched by the previous version) they work and
it is logged once per agent; docs/design/agents.md and modules.md; no CHANGELOG; live run
of all four CLIs; the human's manual check in two parts: (1) an in-place update (the new
build installed with `uv tool install`/pip, no `lado update`) under a running session — its
agents, launched without a token, keep working and are logged once; (2) `lado update` from
the previous release — the sessions restart and their agents carry tokens; the way back:
`lado update <previous>` restarts the agents without tokens and they work (whether a schema
change is needed is the step's design; if one is, the rollback by
`LADO_HOME/backups/lado.db.schema-<N>` is part of the check).
Touches: agent_token.py (new), providers/base.py, runtime.py, hooks.py, mcp_stdio.py, login_wait.py

### S6a — The two event classes as data (M1-2, first half)
Status: planned
Check: each neutral event of each provider tagged "needs an answer" or "notification" in
`providers/` (`event_class(provider, native)`); a unit test that every neutral event of every
provider has a class, seen red with one event untagged; no change of the hook's argv nor of
its behaviour (the whole suite unchanged); docs/design/agents.md (the classes). No manual
check and no live run: nothing an agent does changes.
Touches: providers/base.py, providers/ (each provider's events), docs/design/agents.md

### S6b — The hook split in two halves (M1-2, second half)
Status: planned
Check: the whole suite unchanged and green (the dev plan lists the protecting files); new
unit test: the client module imports none of `lado.state`, `lado.runtime`, `lado.tmux`,
seen red first; `make test-js`; compatibility (integration): a hook with the old argv (an
agent launched by the previous version) still works, the server half taking the
fingerprint itself; the smoke of S1 green; live run of all four CLIs; the human's manual
check: a real session per CLI reaches idle, takes a message, a worker reports; an in-place
update under a running session keeps its agents working on the old argv; the way back:
`lado update <previous>` rewrites the agents' hook configs to the old argv and they work.
Touches: hooks.py, agent_api.py (new), agent_client.py (new), providers/ (base hook_argv, claude, codex, opencode_family), docs/design/agents.md

### S7 — The `lado mcp` front as a proxy (M1-3)
Status: planned
Check: test_mcp_stdio.py, test_mcp_server.py, integration test_mcp_start.py and
test_mid_turn_messages.py green; new lazy-import test (the front imports no `lado.state`
after start); the first `tools/list` measured before and after, no slower beyond the
threshold of the step's brief; compatibility (integration): a `lado mcp` started by the
previous version under a running session keeps serving its agent; the new lazy-import test
seen red first; the smoke's probe_mcp and S1's tool-call smoke green in CI; live run of all
four CLIs; the human's manual check as in S6b, with a tool call per CLI and an in-place update
under a running session.
Touches: mcp_stdio.py, mcp_server.py, agent_api.py, docs/design/agents.md

### S8 — The event-class table per CLI (M1-5)
Status: planned (may start right after S6a)
Check: for each of the four CLIs a table (native event → neutral event → class → what the
CLI does with the hook's output and at its deadline → what an empty exit does), every row
from code or a fact checked by hand (a short smoke or live run where docs/design/agents.md
has no fact), agreeing with S6a's "every event has a class" test; written as a section for
the spec of S11.
Touches: docs only

### S9 — The throwaway end-to-end prototype (M1-6)
Status: planned
Check: a draft pull request on ladohq/lado labelled "prototype, do not merge" with a script
that runs end to end: the Agent API over a Unix socket in `lado server`, an agent in a plain
container, the fake agent, a supervisor and a worker exchanging a message, the worker's
commit merged; the human runs the script on their separate Mac; the findings list (hook
latency over the socket, what broke without `LADO_HOME`, how the MCP front maps onto the
server, long operations) as an artifact and attached to the task. Its closing (the PR closed,
its branch deleted) is checked in S11, once the findings are in the spec.
Notes for the brief: timeboxed to three days; what needs no Docker (the socket, the server's
routes, the fake agent on the host) is built and run in LADO's container first; at most
three rounds "the human runs it on the Mac → a fix"; past the timebox or the rounds the
findings are written as they are, the prototype is called partial, and the human decides at
the M1 gate.
Touches: a separate branch, never merged

### S10 — The decision record on the process model (M1-8)
Status: planned
Check: `docs/design/agent-api.md` with a Decisions table: `lado server` mandatory and how it
is kept up, where the Agent API socket lives (macOS's 104-byte limit), the fate of
`lado loop`; for what `lado server stop` does while sessions run (Q-2) the options and the
dev plan's recommendation recorded with the status open, decided in M2a; linked from docs/design/agents.md
and modules.md; S9's findings folded in.
Touches: docs/design/agent-api.md (new), docs/design/agents.md, docs/design/modules.md

### S11 — The Agent API protocol spec (M1-7)
Status: planned
Check: an openspec change archived into `openspec/specs/agent-api/spec.md`:
version and handshake, the token and what it permits, event ids and "processed exactly
once", retries against each CLI's deadline, the two event classes with S8's table, the
on-disk queue, long operations, the socket entry, errors; `openspec validate --specs
--strict` and a trial archive green; S9's draft pull request closed and its branch deleted;
the human approves the protocol (M1 gate item).
Touches: openspec/changes/, openspec/specs/agent-api/

### S12 — The threat model approved (M1-9)
Status: planned
Check: `docs/research/session-isolation-plan.md`, section 4 and the M1 row, updated with
E9, E14, E15, E10, the narrow setuid "become the agent" helper of M3-5b, and an M3 column in
the threat table; the human approves it (M1 gate item).
Touches: docs/research/session-isolation-plan.md

### M1 exit gate
After S12: the readiness check (`delivery`) confirms the four gate items (protocol spec,
decision record, prototype reviewed, threat model approved) and every step's check; the
human closes the epic.

## Open questions

1. **How Claude Code's live run uses the subscription (S2).** Options: a long-lived token
   the human makes once (`claude setup-token`) given to the test as
   `CLAUDE_CODE_OAUTH_TOKEN`, never written to disk; or the container's own login copied
   into the test's home. Recommendation: the token in the environment, as LADO already
   supports `CLAUDE_CODE_OAUTH_TOKEN` and the test then touches no config of the human;
   decided at S2's design. In LADO's container every agent runs as one user, so any agent
   can read what a test can (the same holds for today's `OPENROUTER_API_KEY` in the
   container's environment); closing that is what the isolation epics are for. So the token
   goes only to the live-run command's process, from a file of mode 600 outside any
   repository, never into the container's environment; the human confirms at `plan_ok`.
2. **A schema change in S5.** Whether the token needs a column (the agent's instance is
   already in the state): S5's design decides; if yes, its way back is in its check.
3. **When $10 is not enough (S2).** Recommendation: S2 asks the human with the measured
   numbers; the default proposal is a smaller live set per step (the tests that cross the
   path the step changes) on the cheapest model that held tool calls in the trial; the
   human confirms at `plan_ok`.
4. **No manual check for S1, S2 and S6a.** They change test code or tag data only; their
   check is their own run in CI or locally. Recommendation: the human's rule "a checklist
   for every step that changes code" means product code; the human confirms at `plan_ok`.
5. **Q-2 (`lado server stop` while sessions run)** belongs to M2a; S10 records options and
   the dev plan's recommendation, the human decides when M2a needs it.

## Later

- A scripted model endpoint beyond the smoke (for the integration tests with a real CLI) —
  only if S1 shows the smoke version pays off — no task yet.
- The live run in CI on pull requests (`live.yml`'s key is open only to main and tags) —
  a change of the repository's secrets policy, the human's call — no task yet; local runs
  of S2 cover the epic.
- M2a and later stages — the next epics, after M1's gate — docs/research/session-isolation-dev-plan.md 3.2…
