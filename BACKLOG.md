# Backlog

Tasks and bugs found while using LADO, until the external task tracker is connected
(see ROADMAP.md, stage 6). Move them to the tracker then and delete this file.

## Stop a single agent

There is no way to stop one agent: `lado stop` kills the whole session. A worker that has
finished (e.g. a research task with nothing to merge) keeps its tmux window and stays idle.

Wanted: `lado stop <session> <agent>` and an MCP tool for the supervisor to stop a worker.
It closes the agent's window and marks it stopped. Its worktree and branch stay on disk.
Found: 2026-10-01, after the `kilo-research` worker finished.

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

## `lado log`: show messages between agents

There is no way to see who sent what to whom in a session; today it means reading the
`messages` table in `~/.lado/lado.db` by hand.
Wanted: `lado log <session>` prints the session's messages in order (time, sender ->
recipient, state, text), with `--follow` to keep printing new ones and a filter by agent.
Found: 2026-10-01, checking whether two workers talked to each other.

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
says to run `lado kits update` or `remove`. Decide: keep failing everywhere, or fail only
when the wanted kit (or the lookup path to it) depends on the broken source and warn
otherwise.
Found: 2026-10-01, kit sources review.
