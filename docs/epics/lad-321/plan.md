# Plan: Session isolation, M1 — Agent API groundwork (LAD-321)

## State
Phase: plan · Epic run: epic/epic-isolation-m1 · Branch: base (main)
In work: — · Next: S1 · Open checks: —
Standing rules of the human:
- One step at a time: the next starts only after the previous one merged and passed its manual check (#8915 q1).
- Merge into main only by a pull request with a green `ci-ok` and the human's explicit "merge" (statement).
- Every step leaves LADO working and releasable; no release plan up front; the CHANGELOG line in the step that changes what users see (statement).
- A step that changes how LADO talks to an agent CLI (hooks, `lado mcp`, MCP tools, the agent's environment) gets a live run before its merge: Claude Code on the human's subscription, once per step; the other CLIs on a cheap OpenRouter model; $10 on OpenRouter for the whole epic for now (#8901 q4, #8915 q3, q4).
- A step that changes product code carries a detailed manual checklist, written for an agent on the human's other machine, run on a build of the pull request's branch before the merge, native and Docker installs where the step touches them (#8901, #8915 q5).
- Review findings go into the next steps; a wrong plan is fixed by a separate docs pull request (statement).
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
path, e.g. a hook that does nothing, a tool list that is empty).
Touches: tests/smoke/, tests/fake_endpoint.py, tests/real_clis.py, scripts/smoke_ci.py, docs/testing.md
Notes: the smoke has no model (a 401 endpoint), so no real CLI ever calls a LADO tool in
it: tool calls are covered by the weekly live run only. The review weighs a scripted model
endpoint (answers one tool call, then ends the turn) that would let the smoke prove a real
CLI → `lado mcp` → tool path for free. Fixes past the step's threshold become S1b.

### S2 — Live runs before a merge, cheap and on demand
Status: planned
Check: one command runs the live tests locally (LADO's container) for one CLI or all:
Claude Code on the human's subscription, Codex, Kilo and OpenCode on OpenRouter; its report
names each CLI's result and the OpenRouter cost of the run; a run of all four on main
passes, its cost recorded in the task; docs/testing.md says when a step runs it and how;
no key or subscription token in any log, config or evidence (a test checks it).
Touches: tests/live/, tests/real_clis.py, scripts/smoke_ci.py, Makefile, docs/testing.md
Notes: CI's `live.yml` gets its key only on main and tags, so a pull request's live run is
local. Today "no live test uses a Claude subscription" (docs/testing.md): how the
subscription reaches the test without touching the human's config is the step's design
(open question 1).

### S3 — LADO's folder closed to other users of the machine (M1-10)
Status: planned
Check: unit tests (a new home is 700, a wide one tightened silently, a home of another
owner left alone and reported by `lado doctor`); container test (`stat` of `/home/lado` and
`~/.lado/lado.db` in the image); CHANGELOG line under Improved; docs/cli.md (`lado doctor`);
the human's manual check on native macOS and Docker: an existing `~/.lado` at 755 becomes
700 after `lado start`, LADO works as before, `lado doctor` is quiet, a second account
cannot list it.
Touches: state.py, server/run.py, cli.py, docker/entrypoint.sh, doctor.py

### S4 — Artifacts only from the agent's own folders (M1-4)
Status: planned
Check: unit tests in test_artifacts.py (inside, outside, `..`, a symlink out, an absolute
path inside); integration: the fake agent's `write_artifact` with a path in `LADO_HOME` is
refused with a message that says where files may come from; the spec where
`write_artifact` is specified and docs/design/artifacts.md updated; CHANGELOG under Fixed;
live run (an agent attaches a file of its worktree); the human's manual check: an artifact
from the worktree works, one from `~/.lado/lado.db` is refused with a clear message.
Touches: artifacts.py, mcp_server.py, openspec/specs/, docs/design/artifacts.md

### S5 — A token per agent (M1-1)
Status: planned
Check: unit (mint/verify, tampered token, another instance's token, a retired key, key file
mode 600; the token in the agent's env, never in argv nor tmux's environment); integration:
a fake agent's hook with a wrong token changes no status, with the right one it does, with
none (an agent of the previous version) it works and is logged once; docs/design/agents.md
and modules.md; no CHANGELOG; live run of all four CLIs; the human's manual check:
`lado update` from the previous release with a session running — its agents keep working,
after a restart they carry tokens; the way back to the previous release (whether a schema
change is needed is the step's design; if one is, the rollback by
`LADO_HOME/backups/lado.db.schema-<N>` is part of the check).
Touches: agent_token.py (new), providers/base.py, runtime.py, hooks.py, mcp_stdio.py, login_wait.py

### S6 — The hook split in two halves, with the two event classes (M1-2)
Status: planned
Check: the whole suite unchanged and green (the dev plan lists the protecting files); new
unit tests: the client module imports none of `lado.state`, `lado.runtime`, `lado.tmux`;
every neutral event of every provider has a class; `make test-js`; agents launched before
the update (the old hook argv) keep working (integration); the smoke of S1 green; live run
of all four CLIs; the human's manual check: a real session per CLI reaches idle, takes a
message, a worker reports.
Touches: hooks.py, agent_api.py (new), agent_client.py (new), providers/ (base, claude, codex, opencode_family), docs/design/agents.md

### S7 — The `lado mcp` front as a proxy (M1-3)
Status: planned
Check: test_mcp_stdio.py, test_mcp_server.py, integration test_mcp_start.py and
test_mid_turn_messages.py green; new lazy-import test (the front imports no `lado.state`
after start); the first `tools/list` measured before and after, no slower beyond the
threshold of the step's brief; the smoke's probe_mcp green in CI; live run of all four CLIs;
the human's manual check as in S6, with a tool call per CLI.
Touches: mcp_stdio.py, mcp_server.py, agent_api.py, docs/design/agents.md

### S8 — The event-class table per CLI (M1-5)
Status: planned
Check: for each of the four CLIs a table (native event → neutral event → class → what the
CLI does with the hook's output and at its deadline → what an empty exit does), every row
from code or a fact checked by hand (a short smoke or live run where docs/design/agents.md
has no fact), agreeing with S6's "every event has a class" test; written as a section for
the spec of S11.
Touches: docs only

### S9 — The throwaway end-to-end prototype (M1-6)
Status: planned
Check: a draft pull request on ladohq/lado labelled "prototype, do not merge" with a script
that runs end to end: the Agent API over a Unix socket in `lado server`, an agent in a plain
container, the fake agent, a supervisor and a worker exchanging a message, the worker's
commit merged; the human runs the script on their separate Mac; the findings list (hook
latency over the socket, what broke without `LADO_HOME`, how the MCP front maps onto the
server, long operations) as an artifact and attached to the task; the PR closed and its
branch deleted once the findings are in S10 and S11. Timeboxed to three days.
Touches: a separate branch, never merged

### S10 — The decision record on the process model (M1-8)
Status: planned
Check: `docs/design/agent-api.md` with a Decisions table: `lado server` mandatory and how it
is kept up, where the Agent API socket lives (macOS's 104-byte limit), the fate of
`lado loop`, what `lado server stop` does while sessions run (Q-2: the human answers, it is
M2a's question, asked here only for the record's option); linked from docs/design/agents.md
and modules.md; S9's findings folded in.
Touches: docs/design/agent-api.md (new), docs/design/agents.md, docs/design/modules.md

### S11 — The Agent API protocol spec (M1-7)
Status: planned
Check: an openspec change archived into `openspec/specs/agent-api/spec.md`:
version and handshake, the token and what it permits, event ids and "processed exactly
once", retries against each CLI's deadline, the two event classes with S8's table, the
on-disk queue, long operations, the socket entry, errors; `openspec validate --specs
--strict` and a trial archive green; the human approves the protocol (M1 gate item).
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
   decided at S2's design.
2. **A schema change in S5.** Whether the token needs a column (the agent's instance is
   already in the state): S5's design decides; if yes, its way back is in its check.
3. **Q-2 (`lado server stop` while sessions run)** belongs to M2a; S10 records options and
   the dev plan's recommendation, the human decides when M2a needs it.

## Later

- A scripted model endpoint beyond the smoke (for the integration tests with a real CLI) —
  only if S1 shows the smoke version pays off — no task yet.
- The live run in CI on pull requests (`live.yml`'s key is open only to main and tags) —
  a change of the repository's secrets policy, the human's call — no task yet; local runs
  of S2 cover the epic.
- M2a and later stages — the next epics, after M1's gate — docs/research/session-isolation-dev-plan.md 3.2…
