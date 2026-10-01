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
