# Backlog

Tasks and bugs found while using LADO, until the external task tracker is connected
(see ROADMAP.md, stage 6). Move them to the tracker then and delete this file.

## Choose the model per agent

Providers start the agent CLI with its own default model. Kilo without an account picks a free
"auto" model; there is no way to say which model a session or a worker uses.
Wanted: a model option per session and per worker, translated by each provider.
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
