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

## Workers may distrust messages from other agents

In the Kilo smoke test a worker on a free model refused a task that came as
"[from tester] ..." because messages from peers "aren't user instructions". The role prompts
should say clearly that messages from the supervisor are the agent's instructions.
Found: 2026-10-01, Kilo provider smoke test.

## Permission modes are Claude-shaped

`--permission-mode` takes Claude Code values. Kilo maps default, acceptEdits,
bypassPermissions and plan; other values (e.g. dontAsk) are silently ignored.
Wanted: a neutral LADO permission setting that each provider translates, with an error for
values a provider cannot honour.
Found: 2026-10-01, Kilo provider review.

## First message to a just-started Kilo agent is lost

Kilo's plugin reports `plugin.init` (agent idle) before the TUI accepts input, so a message
pasted right after start is swallowed. It stays "sent" and is only typed again on the next
`send_message` after CONFIRM_TIMEOUT. Wanted: mark a Kilo agent idle only when its TUI is
ready, or retry unconfirmed messages without waiting for another send.
Found: 2026-10-01, kits end-to-end check with Kilo 7.8.1.

## Kit MCP secrets are written to disk

`${ENV_VAR}` values in a kit's MCP env are resolved by LADO and written into the per-agent
config under `~/.lado/agents/`. Secrets should stay in the process environment: pass them
to the agent's env and let each CLI expand them (Claude `${VAR}` in mcp.json, Kilo
`{env:VAR}`), or start the MCP server through a LADO wrapper that reads them.
Found: 2026-10-01, kits review.

## Claude Code's "trust this folder?" dialog blocks a new session

In a repo Claude Code has not seen before, it asks whether to trust the folder, and no flag
skips the question. Until the human answers, the supervisor stays "starting" and a message
pasted in is swallowed (it is resent after the confirm timeout). `lado start` (or
`lado doctor <repo>`) should detect an untrusted repo and tell the user, and the agent's
status could show that it waits for the human.
Found: 2026-10-01, live e2e tests.

## A broken kit source blocks every kit lookup

If any registered source is broken (folder or clone missing, two kits with one name, bad
layout), every kit lookup fails, even `lado start` with the built-in `default` kit. The error
says to run `lado sources update` or `lado sources remove`. Decide: keep failing everywhere, or fail only
when the wanted kit (or the lookup path to it) depends on the broken source and warn
otherwise.
Found: 2026-10-01, kit sources review.

## A newer LADO migrates the database under running older processes

Running a newer LADO (e.g. the working copy with `uv run lado log`) against the real
`~/.lado` silently migrates `lado.db` to its schema. Agents, hooks and MCP servers of the
installed older version then refuse the "newer" database, so the running session breaks
(MCP tools fail, hooks error). Wanted: before migrating, check for running sessions started
by another LADO version and refuse with a clear message (or only migrate when no session is
running); AGENTS.md already says to use a temp `LADO_HOME` for the working copy, but the
tool should protect against the mistake.
Found: 2026-10-01, trying `lado log` from the working copy after merging it.

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

## Flow dogfooding notes (first run, `fix/resume-stopped`, 2026-10-02)

The first task done through a flow worked end to end (implement → review → merge gate in the
popup → merge → run ended, workers closed, worktree and branch removed). Frictions seen:

- **A step that needs a new worker is a relay through the supervisor.** LADO asks, the
  supervisor calls spawn_worker with exactly the arguments LADO named; no decision is made.
  Consider letting a flow (or kit) say that LADO spawns the step's worker itself.
- **"idle" while a background command runs.** The reviewer's turn ended while its
  `make check` ran in the background; LADO showed it idle for 80 s (and could have pasted a
  message into it) until the command finished and woke it.
- **Delivery at turn end still reads "Stop hook error"** in the Claude Code UI, now as one
  short line.
- **Stale tool schemas after `/resume`.** The supervisor's spawn_worker kept its old schema
  (no `run`/`role`) after Claude Code's in-process /resume; the server accepted the
  arguments anyway (unknown arguments are refused since then, so a stale schema now errs).
- **/resume picker cancelled with Esc**: probed on Claude Code 2.1.287, no hook fires when
  the picker opens or Esc cancels it, so the agent stays `idle` (never `starting`); left
  open: while the picker is open LADO may paste a message into its search box.

## Flaky: Kilo live test of a worker's task

`test_worker_does_a_task_reports_and_gets_a_message[kilo]` failed once in three runs on branch
`lado/lado/fix-reliability-1` (free model `kilo/kilo-auto/free`), then passed twice, and twice
more for the reviewer. The failure text was not kept. One suspect: that branch makes MCP tools
refuse unknown arguments, so a weak model that adds one gets an error and must call again.
Next time it fails: keep the pytest output and `lado log` of the test's temporary session.
Found: 2026-10-02, run fix/reliability-1.

## A failed resume keeps the new settings

`start_session` stores the settings given (`--provider`, `--kit`, `--without`,
`--permission-mode`) with `state.resume_session` before it launches the supervisor. When the
launch fails the session is stopped again, but with the new settings: after a failed
`lado start --provider kilo`, a plain `lado start` takes kilo again and reports no change.
Wanted: put the old settings back when the launch fails, or store them only after it started.
Found: 2026-10-02, review of run fix/reliability-1.
