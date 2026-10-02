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
- [x] Kit sources: git repositories and local folders (`lado sources add`), skill packs
- [x] `lado-dev` kit used to develop LADO

## Stage 5: Flows

A flow is optional and comes with a kit: steps, who does them, allowed outcomes, human gates,
and which earlier notes a step needs. LADO enforces the rules; how to do each step is up to the
agent.

- [x] Flow engine with steps, outcomes and human gates
- [x] Gates answered by the human with `lado answer` or in a tmux popup
- [x] A step gets the latest notes of the earlier states it names (`needs`), so roles do not
  copy a design forward; `lado flow-set` keeps them

## Stage 6: Develop LADO inside LADO

- [x] Work runs through an installed release of LADO; agents edit the working copy
- [ ] Agent CLIs are used directly only when LADO is too broken to fix itself

Task trackers moved to stage 9: BACKLOG.md serves until it gets too small.

## Stage 7: Desktop app

The agents still run in tmux; the app is a window onto them.

- [x] Research first (from stage 8), done 2026-10-03: what ACP gives Claude Code, Kilo and
  Codex. Over ACP the human watches and steps in only through the client (prompt, cancel,
  permission answers); no real terminal can attach to a live ACP session (OpenCode may get
  it); the CLI's own dialogs, /resume picker and /clear are lost; a session can move between
  ACP and the TUI one after the other (shared transcript store), not at the same time.
  Claude over ACP runs on the Agent SDK, whose terms want an API key rather than a Pro/Max
  subscription. Decision: the UI is built on tmux first (an agent's terminal plus LADO's
  own structured panels), its data model on LADO's events, so an ACP runtime later adds an
  event view without a rewrite.
- [ ] Local web UI (`lado ui`): sessions, agents with their status, messages, gates, notes;
  built on LADO's events, not on the terminal. Design and tasks: docs/design/ui.md
  (skeleton, live updates, session view, gates, composer)
- [ ] Notifications when an agent waits for the human
- [ ] Artifacts: named, versioned documents of a session (design, plan, review, report) that
  any agent writes and reads, with or without a flow; the human's main way to get results:
  attached to messages and gates and shown in the UI. Flows can require them. Agents know an
  artifact by name only, never by path, and storage sits behind one interface, so it can
  move to a separate service
- [ ] Agent terminals in the UI (a web terminal attached to the agent's tmux window)
- [ ] Desktop app that bundles the UI and the LADO runtime (macOS first)

## Stage 8: ACP runtime

Drive agents over the Agent Client Protocol instead of tmux: structured events, permission
requests handled by LADO, any ACP agent as a provider (OpenCode, Kilo, Gemini CLI, Copilot,
Cursor; Claude Code and Codex through adapters).

- [ ] Start when ACP v2 leaves draft (v1 is stable; v2 changes the turn and state model).
  Try first with agents that speak ACP natively (OpenCode, Kilo), then Codex (codex-acp);
  Claude (claude-agent-acp) only with an API key unless its subscription terms allow it.
  Hands-on check of the open points from the stage 7 research: adapter stability, resume
  between ACP and the TUI, per-session MCP servers, model choice (Kilo)
- [ ] ACP runtime behind the same provider interface as tmux
- [ ] UI renders ACP sessions and permission requests
- [ ] Dogfooding moves to the ACP runtime

## Stage 9: Task trackers

Trackers stay outside LADO: each is a kit (skills and an MCP server), and the core knows
nothing about trackers. Open question: how a flow or role works with "the active tracker"
without depending on one, e.g. one shared skill interface (file a task, update its status)
that each tracker kit implements.

- [ ] Task trackers (YouGile, Jira) as kits with skills; the active tracker is chosen in config
- [ ] Every bug or friction found is filed in the task tracker; BACKLOG.md goes away
