# Backlog

Tasks and bugs found while using LADO, until the external task tracker is connected
(see ROADMAP.md, stage 6). Move them to the tracker then and delete this file.

## Stop a single agent

There is no way to stop one agent: `lado stop` kills the whole session. A worker that has
finished (e.g. a research task with nothing to merge) keeps its tmux window and stays idle.

Wanted: `lado stop <session> <agent>` and an MCP tool for the supervisor to stop a worker.
It closes the agent's window and marks it stopped. Its worktree and branch stay on disk.
Found: 2026-10-01, after the `kilo-research` worker finished.
