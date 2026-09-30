# Roadmap

Goal: reach a version of LADO that can be used to develop LADO itself, as fast as possible.
Each stage is done when all its boxes are checked.

## Stage 0: Repository setup

- [x] uv, ruff and pytest configured; `uv.lock` committed
- [x] CI on GitHub Actions: format, lint, tests
- [x] Agent instructions (`AGENTS.md`, `CLAUDE.md`) and this roadmap

## Stage 1: Walking skeleton

- [x] `lado doctor` checks the environment: Python, tmux, Claude Code
- [x] Release to PyPI on a git tag (trusted publishing)
- [x] `uv tool install lado` works on a clean machine

## Stage 2: Dogfood MVP

- [x] `lado start <repo>` launches a supervisor agent (Claude Code) in tmux
- [x] LADO MCP server with `spawn_worker`, `send_message`, `list_agents`
- [x] `lado ls` and `lado attach`
- [x] Agent state stored in `~/.lado/`
- [ ] A supervisor can delegate a real LADO task to a worker end to end

## Stage 2.5: Task trackers

- [ ] Common task-tracker interface; the active tracker is chosen in config
- [ ] YouGile adapter
- [ ] Jira adapter

## Stage 3: Develop LADO inside LADO

- [ ] Work runs through an installed release of LADO; agents edit the working copy
- [ ] Every bug or friction found is filed in the task tracker
- [ ] Claude Code is used directly only when LADO is too broken to fix itself

## Stage 4: Desktop app

The agents still run in tmux; the app is a window onto them.

- [ ] Local web UI (`lado ui`): sessions, agents with their status, messages
- [ ] Agent terminals in the UI (a web terminal attached to the agent's tmux window)
- [ ] Desktop app that bundles the UI and the LADO runtime (macOS first)
- [ ] Notifications when an agent waits for the human

## Stage 5: ACP runtime

Drive agents over the Agent Client Protocol instead of tmux: structured events, permission
requests handled by LADO, any ACP agent as a provider. Starts with research.

- [ ] Research: Claude via ACP adapter (subscription auth, skills, hooks, plugins), other agents
- [ ] Agent runtime interface with tmux and ACP implementations
- [ ] UI renders ACP sessions and permission requests
- [ ] Dogfooding moves to the ACP runtime
