# Backlog

Tasks and bugs found while using LADO, until the external task tracker is connected
(see ROADMAP.md, stage 6). Move them to the tracker then and delete this file.

## Choose the model per agent

Providers start the agent CLI with its own default model. Kilo without an account picks a free
"auto" model; there is no way to say which model a session or a worker uses.
Wanted: a model option per session and per worker, translated by each provider.
Postponed (2026-10-01): model names differ per provider and change with every release, so
first decide how a kit names a model without tying it to one provider (aliases such as
fast / strong mapped per provider? a per-provider map?). Draft design: `model:` in a role,
`spawn_worker(model=...)` so the supervisor can pick a cheaper model per task, `lado start
--model`; no hand-kept model lists; the model shown in `lado ls` and the `spawned` event.
Found: 2026-10-01, Kilo provider smoke test.

## Permission modes are Claude-shaped

`--permission-mode` takes Claude Code values. Each provider declares the ones it honours
and LADO refuses the others (Kilo: default, acceptEdits, bypassPermissions, plan), but the
vocabulary is still Claude Code's, and a session has one mode for all its agents.
Wanted: a neutral LADO permission setting that each provider translates.
Found: 2026-10-01, Kilo provider review.

## Kit MCP secrets are written to disk

`${ENV_VAR}` values in a kit's MCP env are resolved by LADO and written into the per-agent
config under `~/.lado/agents/`. Secrets should stay in the process environment: pass them
to the agent's env and let each CLI expand them (Claude `${VAR}` in mcp.json, Kilo
`{env:VAR}`), or start the MCP server through a LADO wrapper that reads them.
Found: 2026-10-01, kits review.

## Claude Code's "trust this folder?" dialog blocks a new session

In a repo Claude Code has not seen before, it asks whether to trust the folder, and no flag
skips the question. Checked on Claude Code 2.1.287 (2026-10-02): until the human answers,
no hook runs, so the agent stays `starting` and LADO types nothing into it (messages wait in
the queue). The dialog's default answer is "No, exit": an Enter there ends Claude Code, its
tmux window closes, and no SessionEnd hook runs, so `lado ls` keeps showing it `starting`
(with "tmux session is gone" for a supervisor). `lado start` (or `lado doctor <repo>`)
should detect an untrusted repo and tell the user, and the agent's status could show that it
waits for the human.
Found: 2026-10-01, live e2e tests.

## A broken kit source blocks every kit lookup

If any registered source is broken (folder or clone missing, two kits with one name, bad
layout), every kit lookup fails, even `lado start` with the built-in `default` kit. The error
says to run `lado sources update` or `lado sources remove`.
Wanted (decided 2026-10-02): fail only when the wanted kit (or a kit it includes) depends on
the broken source; otherwise warn and go on.
Found: 2026-10-01, kit sources review.

## No way to reach a busy agent urgently

A message to a busy agent waits until its turn ends. A hint from the supervisor that would
save a worker many minutes (e.g. the known cause of a failure it is debugging) arrives only
after the worker has finished that long turn. Wanted: an "urgent" flag on send_message that
types the message into the busy agent's window at once (Claude Code and Kilo accept input
while working and handle it at the next step), with the same confirmation via prompt-submit.
Found: 2026-10-01, provider fixes task.

## A delivered message can carry the human's unsent draft

The supervisor's window is both the human's chat and the agents' inbox. When a message is
pasted into an idle supervisor (paste + Enter) while the human is typing there, the half-written
text is submitted together with it. Decided (2026-10-01): live with it for now. It goes away
when the human writes through LADO's own input (UI composer, stage 7: messages from the human
and from agents are queued and delivered one at a time) or with the ACP runtime (stage 8: LADO
drives the agent's input itself). Make sure the UI has a composer that goes through LADO.
Found: 2026-10-01, dogfooding.

## A step that needs a new worker is a relay through the supervisor

LADO asks the supervisor to start a step's worker, and the supervisor calls spawn_worker with
exactly the arguments LADO named; no decision is made.
Wanted: a flow (or kit) can say that LADO spawns the step's worker itself.
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## "idle" while a background command runs

A reviewer's turn ended while its `make check` ran in the background; LADO showed it idle for
80 s (and could have pasted a message into it) until the command finished and woke it. The end
of a turn is not the end of the agent's work.
Wanted: find out whether Claude Code and Kilo signal a running or finished background task;
use it for the status, or document the limit.
Postponed (2026-10-02): low impact. Flows move on flow_advance, not on idle; a message
pasted meanwhile most likely starts a normal turn (not verified); typing into waiting agents is
already blocked. The reference orchestrator does not handle it either (screen-based idle).
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## Delivery at turn end reads "Stop hook error"

Claude Code shows a message delivered by the turn-end hook as a "Stop hook error" line.
Wanted: check whether another form of the hook's answer (e.g. JSON `decision: block`) shows a
neutral label. Cosmetic.
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## Flaky: Kilo live test of a worker's task

`test_worker_does_a_task_reports_and_gets_a_message[kilo]` failed once in three runs on branch
`lado/lado/fix-reliability-1` (free model `kilo/kilo-auto/free`), then passed twice, and twice
more for the reviewer. The failure text was not kept. One suspect: that branch makes MCP tools
refuse unknown arguments, so a weak model that adds one gets an error and must call again.
Next time it fails, the failure report names a folder under `<temp dir>/lado-live-evidence/`
with the session's `lado log`, `hooks.log`, the agents' configs and their last screens (run
fix/live-test-keeps-logs); keep the pytest output too.
Found: 2026-10-02, run fix/reliability-1.

## Flows cannot work on another repository

A run's worktree and branch are always made in the session's repo, so a change to another
repo (e.g. the lado-kits kit repo while the session runs on LADO) cannot go through a flow:
it is done by a worker outside a run, with no design gate, review step or merge gate.
Wanted: `flow_start` can name the repo a run works on (a registered kit source or a path),
and the run's worktree, `make check` and merge happen there.
Found: 2026-10-02, task lado-dev architecture (kit changes in lado-kits).

## A failed rollback hides why a start or spawn failed

When `start_session` or `spawn_worker` fails, its `except` undoes what it stored
(`state.fail_resume`, `state.delete_session`, `close_worker`, git cleanup) and re-raises. If
that undo raises too (e.g. the database is locked), the user sees the undo's error instead of
the cause, and the session or worker is left half undone.
Wanted: an undo that never replaces the original error (report its own failure apart, e.g.
in `hooks.log` or as a note on the error) and leaves no half state.
Found: 2026-10-02, review of run fix/resume-settings.

## Two starts of a session whose tmux server died can stop each other

`start_session` stops a session whose tmux server is gone (`stopped_at` unset, no tmux
session) before it takes it over. Two `lado start` of that name at once both see it so: the
first stops it, resumes it and launches its supervisor; the second then stops that running
session again, forgetting its agents, and takes it over in turn. The window is small.
Wanted: stopping a left-over session and taking it over as one step that only one start wins.
Found: 2026-10-02, run fix/resume-settings.
## Live-test evidence lacks the CLIs' own transcripts and logs

A failed live test keeps LADO's log, hooks.log, agent configs and window screens, but not
Claude Code's transcript (~/.claude/projects/<cwd>/*.jsonl) or Kilo's session and log from its
data folder. For a flake such as a weak model calling a tool with a wrong argument, the
transcript (tool calls and their answers) matters most.
Wanted: the evidence also copies each agent's CLI transcript and logs, picked by the agent's
cwd and the test's start time; the test layer asks the provider for their location, so nothing
above providers/ learns a provider's paths.
Found: 2026-10-02, review of run fix/live-test-keeps-logs.

## Stopping one of several running sessions migrates the database under the others

A newer CLI refuses to migrate `lado.db` while a session runs and asks for `lado stop`
first, but lets `lado stop` itself through: with sessions A and B running, `lado stop A`
migrates the database while B still runs, so B's older agents break until B is stopped
too. Also, a LADO upgraded in place (`pip install -U`) while a session runs migrates from
that session's own hooks, which run the new code, under its older MCP servers. Wanted: a
stop that kills the session before it opens the database, or one `lado stop --all`.
Found: 2026-10-02, migration guard (fix/migration-guard).

## The running-session check sees one tmux socket

`runtime.check_migration` asks `tmux.has_session` on the current process's `LADO_TMUX_SOCKET`.
A session started in the same LADO_HOME with another socket counts as not running, so the
database is migrated under it.
Wanted: store the socket with the session and check that one (or say in the refusal and the
docs that the check sees one socket). An edge case.
Found: 2026-10-02, review of run fix/migration-guard.

## A missing tmux binary crashes the CLI with a traceback

Without tmux installed, `tmux.run` raises FileNotFoundError, not TmuxError, so the CLI shows a
traceback (now also from `check_migration` when an old database has unstopped sessions).
Wanted: `tmux.run` turns a missing binary into TmuxError with a clear text.
Found: 2026-10-02, review of run fix/migration-guard.

## Migration-guard leftovers (two Minor review findings)

`state.pending_migration`'s docstring says it creates and changes nothing, but opening a WAL
database read-only leaves `lado.db-wal` and `lado.db-shm` behind (the data is unchanged).
`tests/test_state.py` `_database()` and `tests/integration/test_agents.py` `database()` are the
same helper twice. Wanted: say "changes nothing in the database"; move the helper to
`tests/agent_helpers.py` next to `previous_schema()`.
Found: 2026-10-02, review of run fix/migration-guard.

## The architect cannot put questions to the human

A design review often turns up decisions that are the human's (e.g. what to resurrect after a
failed delivery), but the architect works inside a flow step with no channel to the human: it
can only send the design back as `changes`, and the supervisor finds the questions in its note.
The `grilling` skill (rounds of numbered questions with a recommended answer each) worked well
for the supervisor in the chat. Wanted (lado-dev kit): the architect lists such decisions under
a "Questions for the human" section of its note, and the supervisor asks them in the chat in
the `grilling` format before the next design visit.
Found: 2026-10-02, design of feature/message-retry.

## `lado forget` can leave two loops for one session name

`lado forget` deletes the lock file while the stopped session's loop may still sleep (up to
INTERVAL). A new session of the same name started within that time locks a new file (another
inode); the old loop wakes, sees a running session and goes on: two loops. Wanted: each pass
checks that the held file is still the one at the path (os.fstat vs os.stat) and exits if not.
Found: 2026-10-02, review of run fix/session-loop.

## A running session loop keeps the old code after an upgrade

After upgrading LADO without a schema change, a running loop goes on with the old code until
`lado stop`; `lado doctor` and `lado ls` do not show it. Low priority.
Found: 2026-10-02, review of run fix/session-loop.

## A kit cannot say which LADO it needs

A kit that uses a newer flow or kit field (e.g. a flow state's `needs`) fails in an older
LADO with a validator error about an unknown field, which does not say that LADO is too old.
So a kit change must wait until every user has upgraded, and the order (release LADO first,
then the kit) lives only in people's heads.
Wanted: `kit.yaml` may say `requires: lado>=0.11`; an older LADO refuses the kit with
"kit <name> needs LADO >= 0.11, this is 0.10.0: upgrade LADO" (`lado start`, `lado kits
check`), and the kit's own validator errors stay for real mistakes.
Found: 2026-10-02, planning the lado-dev update for named notes.
