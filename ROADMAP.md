# Roadmap

Goal: reach a version of LADO that can be used to develop LADO itself, as fast as possible.
Each stage is done when all its boxes are checked.

LADO's value over a single agent CLI: a team of agents shaped by kits (which roles, skills and
tools are active), driven by flows (steps and human gates enforced by LADO, not by the model),
and a human who answers gates asynchronously instead of sitting in one chat. LADO treats agent
CLIs equally: Claude Code is the first provider, not the only one.

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
- [x] A supervisor can delegate a real LADO task to a worker end to end

## Stage 3: Providers

Everything above the provider layer (sessions, messages, kits, flows) must not depend on
which agent CLI runs. Agent status comes from events (hooks, plugins, ACP), never from
reading the screen.

- [x] Provider interface with explicit capabilities; Claude Code moved onto it
- [x] Kilo provider (Codex later, when an OpenAI account is available)
- [x] Provider chosen per session and per worker; `lado doctor` checks every installed one

## Stage 4: Kits

A kit is a provider-neutral bundle: roles (agent prompts), skills (`SKILL.md` folders),
MCP servers and flows. Kits can be combined and parts switched on or off.

- [x] Kit format and `lado start --kit`; several kits combine into one environment
- [x] Switch single roles, skills and MCP servers on or off per session and per agent
- [x] Skills placed where each provider looks for them in the agent's worktree
- [x] Kit sources: git repositories and local folders (`lado kits add`), skill packs
- [ ] `lado-dev` kit used to develop LADO

## Stage 5: Flows

A flow is optional and comes with a kit: steps, who does them, allowed outcomes, human gates,
required artifacts. LADO enforces the rules; how to do each step is up to the agent.

- [ ] Flow engine with steps, outcomes, human gates and required artifacts
- [ ] Artifacts stored per session and readable by agents and the human
- [ ] `lado inbox`: answer gates and questions from all agents in one place
- [ ] Notifications when an agent waits for the human

## Stage 6: Develop LADO inside LADO

- [ ] Work runs through an installed release of LADO; agents edit the working copy
- [ ] Task trackers (YouGile, Jira) as kits with skills; the active tracker is chosen in config
- [ ] Every bug or friction found is filed in the task tracker
- [ ] Agent CLIs are used directly only when LADO is too broken to fix itself

## Stage 7: Desktop app

The agents still run in tmux; the app is a window onto them.

- [ ] Local web UI (`lado ui`): sessions, agents with their status, messages, gates
- [ ] Agent terminals in the UI (a web terminal attached to the agent's tmux window)
- [ ] Desktop app that bundles the UI and the LADO runtime (macOS first)

## Stage 8: ACP runtime

Drive agents over the Agent Client Protocol instead of tmux: structured events, permission
requests handled by LADO, any ACP agent as a provider (OpenCode, Kilo, Gemini CLI, Copilot,
Cursor; Claude Code and Codex through adapters).

- [ ] Research: Claude and Codex via ACP adapters (subscription auth, skills, hooks)
- [ ] ACP runtime behind the same provider interface as tmux
- [ ] UI renders ACP sessions and permission requests
- [ ] Dogfooding moves to the ACP runtime
