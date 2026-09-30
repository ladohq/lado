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
