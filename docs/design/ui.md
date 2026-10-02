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

From simple to complex (decided with the human 2026-10-03): build the plumbing first and see
it work, then agree on the main screen's structure, then design and build one section at a
time. Each task is one `feature` run, useful on its own.

1. **Skeleton**: plumbing only, no screen design. `lado ui` (localhost, token), FastAPI app
   under `/api`, the React bundle built in CI and shipped in the wheel, one plain page that
   lists the sessions read only (proof that database → API → UI works), an end-to-end test
   harness (browser against a real `lado ui` with the fake agent) that saves a screenshot of
   each screen it checks to a folder outside the worktree or git-ignored, so the reviewer can
   look at them and the tree stays clean.
2. **Main screen structure**: with the human, which sections and items the main screen has
   and how one moves between them; layout and navigation only, sections empty.
3. **Sections, one at a time**, each designed with the human and then built. Candidates,
   order decided in task 2: agents and their status, live updates (the change feed, D3),
   activity (messages, flow transitions, notes), runs, gates, the composer (D4),
   notifications, the agent terminal, artifacts; later the desktop app.

## Look

A first exploration of whole screens (2026-10-03) was not approved as a layout; only its
colours were: a light, calm ground (#F6F7F9, panels #FFFFFF, lines #E3E6EB, ink #16181D,
muted #5B6270), blue for actions and links (#1F5FD6), and orange only for what waits for the
human (#B4530F on #FDF1E6); IBM Plex Sans and IBM Plex Mono. Each section's mockups are made
and approved in its own task; this file keeps what was decided from them.
