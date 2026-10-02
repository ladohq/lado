# LADO web UI: design

Status: draft, agreed with the human on 2026-10-03. ROADMAP stage 7. Each UI task's design
starts from this file and updates it; what is decided here holds for every task.

## Goal

A local web UI (`lado ui`) that shows what a session's agents do and lets the human act:
answer gates, write to any agent, see who waits for them, and later watch an agent's
terminal. The agents keep running in tmux; tmux, `lado answer` and the popup stay. The UI adds
a surface, it takes nothing away.

## Principles (every UI task is reviewed against them)

1. **The UI talks only to LADO's API.** No local paths, no reading files or the database
   from the UI, no "the server is on this machine". The server's address is configured, not
   assumed. This keeps a later remote or cloud setup (LADO on a server, workers in the
   cloud, or both) open.
2. **Authentication is its own layer.** Now: a random token per `lado ui` start, checked on
   every HTTP request and every WebSocket, plus an Origin check. Later it can be replaced by
   a real login for a remote host without touching the rest.
3. **One change feed: "events after id N".** The UI learns about changes from one stream,
   never by polling lists. The server reads it from the database's `events`, `messages` and
   `notes` (ids only grow), so a write by any process (CLI, hooks, MCP server, session loop)
   reaches the UI. Where the server gets events from sits behind one interface, so remote
   workers can later send events over the network instead of writing a local SQLite.
4. **An agent's terminal is the runtime's.** The terminal stream comes from where the agent
   runs (a local tmux window today, another host later); the UI sees one WebSocket. An
   agent without a terminal (ACP) simply has none.
5. **The human's actions go through the core.** Answering a gate calls `runs.answer`, a
   message from the human goes through the same queue and delivery as agents' messages
   (sender `human`). No logic of its own in the UI.
6. **Events, not screens; no silent drops.** As in AGENTS.md: the UI never reads a
   terminal to learn a status, and an action that fails says so.

## Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| D1 | Frontend stack | React + TypeScript + Vite | Agents write it best; xterm.js and a later desktop shell fit; the built bundle ships in the wheel, users need no Node |
| D2 | Server | FastAPI on uvicorn (Starlette, uvicorn and pydantic already come with `mcp`) | Typed requests, an OpenAPI schema from which the UI's TypeScript types are generated: one contract for the UI and later remote clients |
| D3 | Realtime | Server-Sent Events for the change feed (resumable from the last id); a WebSocket only for terminals | One transport per job; no second channel with other topics |
| D4 | Who the human writes to | Any agent, the supervisor by default, from one composer with a recipient | One way to write, not several |
| D5 | API layout | Everything under `/api`, the bundle served by the same server | No dev proxy that must mirror every route |
| D6 | Desktop app | Later (task 9); the browser first | A bundled server is heavy; the browser covers the need |

## Lessons from another orchestrator's UI

Taken: one event stream with replay; localhost by default; sessions that need the human
first; answer cards by gate kind; a web terminal over a grouped tmux session per viewer; the
server serves the bundle.

Avoided: two dozen polling timers and id-only events followed by full refetches; writes
that bypass the event bus; no token and a terminal WebSocket open to any local page; two
transports with different topics; several competing ways to message an agent; a one-slot
side panel; no entry point for what waits for the human; feature flags and wireframes in
production code; end-to-end tests with a mocked network; a terminal without reconnect or
backpressure.

## Tasks

Each task is one `feature` run, useful on its own; the order may change as we learn.

1. **Skeleton**: `lado ui` (localhost, token), the bundle built in CI and shipped in the
   wheel, read only: sessions and agents with their status; an end-to-end test harness
   (browser against a real `lado ui` with the fake agent) that saves a screenshot of each
   screen it checks to a folder outside the worktree or git-ignored, so the reviewer can
   look at them and the tree stays clean.
2. **Live updates**: the change feed (D3) behind its interface; the UI updates without
   polling.
3. **Session view**: the activity feed (messages, flow transitions, notes), runs with
   their states.
4. **Gates**: answer approval, choice and loop-limit gates with the notes the gate needs.
5. **Composer**: the human writes to any agent (D4).
6. **Notifications**: browser notifications and a "needs you" count.
7. **Agent terminal** in the browser.
8. **Artifacts** (own design; ROADMAP stage 7).
9. **Desktop app**.

## Screens (first mockups)

Session view (sessions list with "needs you"; activity feed; agents and runs; composer),
gate (the needed notes, the review, approve or reject with a comment), agent (its messages
and events, details; terminal from task 7). The mockups are shown to the human in the
design step of each task; this file keeps what was decided from them.
