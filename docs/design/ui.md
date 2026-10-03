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
2. **Authentication is its own layer** (`lado/server/auth.py`, the only place that checks
   it). Now: a token of the LADO_HOME, kept until `lado server --new-token`, checked on
   every API request (and later every WebSocket): a cookie named after the server's port
   (`lado_token_<port>`, so two LADO servers on one machine do not log each other out) or
   `Authorization: Bearer <token>`. A connection that changes something is also checked
   for its Origin (`Guard.check(conn, changes=True)`, for any HTTP connection: the
   terminal's WebSocket now, gates and the composer later): only the server's own
   `http://127.0.0.1:<port>` and `http://localhost:<port>`, and no Origin only with a Bearer
   token (a client that is not a browser). Later the layer can be replaced by a real login
   for a remote host without touching the rest.
3. **One change feed: "changes after id N".** The UI learns about changes from one stream,
   never by polling lists. SQLite triggers write every insert, update and delete of the
   tables the UI shows (sessions, agents, messages, runs, gates, notes) to the journal
   `changes` in the writer's own transaction, so a write by any process (CLI, hooks, MCP
   server, session loop) reaches the UI, and no code path can forget to report one. What
   the UI shows but no table keeps (a session's `tmux_gone`) is derived: the server
   computes it and sends its changes itself (the table of derived fields, Server below).
   Where the server gets changes from sits behind one interface (`server/feed.py`), so
   remote workers can later send events over the network instead of writing a local
   SQLite.
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
| D4 | Who the human writes to | Revised again 2026-10-03 (D7): the human writes in the session's Activity chat, to the supervisor by default, through LADO's message queue (sender `human`); to another agent only through the same queue | One way to write; nothing typed raw into a working agent |
| D7 | How the human and the agents talk | A chat in Activity, not the supervisor's terminal: the human is a participant of LADO's messages; agents write to `human` with `send_message`, ask with options through `ask_human`; flow gates are cards in the same feed; the terminal stays beside it for watching and stepping in | Works with any provider, over ACP and in the cloud; the human's draft never mixes with agents' messages; gates and questions where the talk is |
| D5 | API layout | Everything under `/api`, the bundle served by the same server | No dev proxy that must mirror every route |
| D6 | Desktop app | Later (task 9); the browser first | A bundled server is heavy; the browser covers the need |

## Server

Decided in task 1 (2026-10-03). One UI server per `LADO_HOME`, the same for the browser, the
later desktop app and a later cloud setup; the UI is its client.

- `lado server` runs it in the foreground; `lado ui` starts it in the background when none
  runs (a process of its own, like the session loop), waits until `/api/health` answers
  (on a timeout it names the log) and opens the browser on the link (`--no-open` prints
  it). `lado server stop` ends it. A `lado ui --port N` while the server runs on another
  port is an error naming its address; a server of another LADO version gets a warning
  that says to restart it.
- Host: only 127.0.0.1 or localhost for now; `--host` with anything else is refused until
  there is a real login.
- Port: 8000, or the next free one up to 8020; `--port N` takes exactly N (busy: an error;
  0: any free port, as the tests use).
- One per `LADO_HOME`: the server holds an exclusive flock on `LADO_HOME/server.lock` and
  writes `LADO_HOME/server.json` (url, port, pid, version). The file counts only while the
  lock is held; with the lock free it is stale and removed, and `lado server stop` kills
  nobody. A second server refuses and names the first one's address.
- Token: `LADO_HOME/server-token` (owner only), made on the first start, replaced with
  `lado server --new-token`. The link `http://127.0.0.1:<port>/?token=<token>` sets the
  cookie (HttpOnly, SameSite=Strict, Path=/) and redirects (303) to `/`, so the token leaves
  the address bar. Every page of the UI takes `?token=` the same way (decided in task 2):
  `/gates/12?token=…` sets the cookie and redirects to `/gates/12` with the other query
  parameters kept, so a link from a notification leads straight to its page. The redirect
  is the path as it was sent, still encoded (`%2F` in a run's name stays), and a path on
  this server (leading slashes become one: `//host/x` goes to `/host/x`). A wrong token is
  401. `/api/health` needs no token.
- Pages and files (task 2): the bundle's files are at its top (`/favicon.svg`) or under
  `/assets/`. A path under `/assets/`, or one at the top with a file extension, is a file,
  served as it is or 404, never the page: an open tab that asks for a file an upgrade
  removed must not get HTML instead of JS. Deeper down a dot belongs to a name
  (`/sessions/a.b` is a page). `/api/<unknown>` is a JSON 404. Every other path gets
  `index.html`, and the UI's router shows the page or Not found.
- Data only through `lado.state` and `lado.runtime`, no SQL in the server but the journal's
  read-only reader (`feed.Journal`, The change feed below). The server never
  migrates `lado.db`: every data endpoint first reads the schema version read-only and
  answers 503 for another one (older or newer).
- The API's OpenAPI schema is the contract: `web/openapi.json` and the UI's TypeScript
  types (`web/src/api.gen.ts`) are made from it by `make web-types` and committed; a unit
  test and `make web` fail when they are stale.
- The bundle (`web/`, built by `make web` into `src/lado/server/static/`, git-ignored)
  ships in the sdist and the wheel; `make dist` checks both, in CI on every PR and before
  a release. Without a bundle the server and `lado ui` warn and name `make web`; the API
  works.
- A server started in the background writes its output and request errors to
  `LADO_HOME/server.log` (owner only; no access log, which would hold the login link's
  token). When it ends while `lado ui` waits for it, `lado ui` says so at once with its
  exit code and last log line. A stopping server waits at most a second for open
  requests: an event stream never ends by itself.

### The change feed

Decided in the live updates task (2026-10-03).

- **The journal**: `changes(id, kind, session, key, op)` in `lado.db` (schema 12), written
  by triggers on the six tables. `kind` is the table, `key` the row in its session (an
  agent's or run's name, a message's, gate's or note's id, `''` for the session). An update
  of an agent that changes `seen_at` (every hook sets it, alone) is no change. The journal
  keeps the latest `state.CHANGES_KEPT` (100 000) changes: each insert drops the older
  ones, in the writer's transaction; the server only reads. `events` is not in it.
- **The source** (`server/feed.py`, `Source`): "the changes after position N", "the latest
  position". Now `Journal`, which reads `lado.db` read only and creates nothing (no
  `lado.db` yet: no changes, the stream waits). One hub per server reads it every 0.25 s
  while a stream is open, off the event loop, and hands each batch to every stream. A
  batch keeps one change per row (kind, session, key) with its latest id. Before each
  batch it checks the schema version; another one ends the open streams, and a new one is
  answered 503. A read that fails is written to the log once with its traceback, then only
  counted (the session loop's rule); after 3 failing reads in a row the open streams end,
  and a new one is answered 503 with the error while the source cannot be read, so the UI
  shows why instead of a stream that stays open with nothing in it.
- **`GET /api/events`** (Server-Sent Events, behind the token; 401 and 503 as the REST
  API): `id: <journal id>`, `event: change`, `data: {kind, session, key, op, item}`.
  **`item` is the row as it is now, in the form of its REST model, or null when the row is
  gone, whatever `op` says**; the UI uses only `item`. A kind without a REST model yet
  (messages, runs, gates, notes until their tasks) has a null item; an agent's is its
  `AgentInfo`, as `GET /api/sessions/{name}/agents` gives it. One table in
  `feed.py`, `ALSO`, says which change also changes another item: a change of `agents`
  also sends the session's (it counts its agents). A comment line every 15 s keeps a quiet
  stream open.
- **The start of a stream**: the position is the `Last-Event-ID` header (the browser's own
  reconnect) or else `?after=N`. Without a position, or with one the journal no longer has
  (dropped, or ahead of it), the stream starts with `event: reset` whose `id` is the latest
  position, taken before it is sent; the UI loads its data on reset (the first load and
  the load after a gap are one path) and gets every change after it. With a position the
  journal has, the stream sends what came after it, then the current value of every
  derived field.
- **Derived fields**: the hub computes them every 3 s and sends a change when one differs
  from its last value. Such a synthetic change has no `id:` line: the browser keeps its
  position, and no journal id is taken or repeated. The snapshots after a resume make sure
  a change while no stream was open is not lost; they are idempotent. Every field the UI
  shows that no table holds belongs in this table (`feed.DERIVED`):

  | Field | Computed by | From |
  |---|---|---|
  | `sessions.status` (`tmux_gone`, `loop_down`; not of a stopped session) | `runtime.session_status` | tmux, the session loop's lock |

- **The UI**: the shell opens one `EventSource` per browser tab and keeps the store
  (`web/src/live.ts`) the sections read; a section opens no stream of its own and never
  polls. A change that comes while a reset's load runs is applied after it. The browser
  reconnects by itself only after a network error; when the server refused the stream
  (401, 503), the shell asks the stream's own address why (`api.ts`, `probeStream`: only the
  answer's head; the rest of the API may work while the feed does not), shows it, and
  opens a new stream after
  3 s from the latest journal id it got (`?after=`); after a 401 it shows how to get in and
  stops. While no stream is open the top bar says "reconnecting…" with the reason.

### Terminal

Decided in the agent terminal task (2026-10-03).

- **The core** (`lado/terminal.py`): `open(session, agent, mode)` gives a `Terminal` (read
  its output, write input, resize, follow the window's size, close; blocking, so the server
  reads it in a thread), `history(session, agent, lines)` the window's last lines and
  whether it shows the alternate screen, and both raise `NoTerminal` with the reason when
  there is none (unknown agent, session stopped, window gone; later an agent over ACP).
  `ended()` tells whether a terminal that ended is gone for good. tmux commands only in
  `tmux.py`; in `server/` only the endpoints (`terminals.py`: the socket's protocol).
- **A viewer per terminal**: a tmux session of its own whose only window is the agent's,
  linked in (`link-window`), and one `tmux attach` client to it on a pty. The order:
  `new-session` together with its labels in one tmux call (`@lado-viewer 1`,
  `@lado-home <LADO_HOME>`, `@lado-session <session>`: it never exists without them), then
  `link-window`, then its own shell window is killed, then its settings: `prefix None`,
  `prefix2 None`, `status off`, `key-table lado-viewer` (a table of its own, only the wheel
  bound; tmux's own tables are not changed), `mouse on` only in control. A viewer cannot
  reach another agent's window. When the agent's window is gone (`lado stop` killed the
  session already) the link fails: `NoTerminal`, and the viewer is removed.
- **Never a read-only client**: with a read-only client attached, tmux takes it for the
  client of LADO's own commands and refuses `send-keys` ("client is read-only"), so no
  message would be delivered. View is enforced by the server (it never writes to a view's
  pty) and the UI (it sends no input in view).
- **Stop and cleanup**: `lado stop` kills the session's tmux session first, marks it
  stopped, then kills its viewers (they hold the agents' windows); a start after the tmux
  session is gone kills them too. A viewer's client then ends, and its socket closes for
  good with `session "<name>" is stopped`. `kill-window` (finishing a worker) closes the
  window in every session, so its viewer ends with it. The server, as it starts, removes
  the viewers of its LADO_HOME a server that died left. Viewers are found only by their
  labels, never by name: a LADO session named `lado-view-x` and another LADO_HOME's
  viewers stay.
- **The socket**: `/api/sessions/{name}/agents/{agent}/terminal?mode=view|control`.
  Another Origin is refused before the upgrade (Principle 2); without the token the socket
  opens only to say why. From the server: the output as binary frames, `{type: "size",
  cols, rows}` (first, and in view when the window's size changes) and `{type: "error",
  reason}`; from the browser `{type: "input", data}` and `{type: "resize", cols, rows}`,
  only in control (in view, and for a frame it does not know, an error frame; the socket
  stays open). Backpressure: the pty is read again only after the last output was sent.
  Close codes: 44xx for good with the reason (4401 no token, 4400 unknown mode, 4404 no
  terminal), shown, no reconnect; 45xx for now (4500 the terminal closed, 4503 lado.db of
  another schema), the UI opens a new socket after 2 s.
- **Modes**: the supervisor's terminal opens in control (the human's chat with it); the
  others in view, and **Take control** asks first, **Release** goes back. In control tmux
  sizes the window by the client active last (`window-size latest`, tmux's default): the
  human's `lado attach` sees the window resized when the browser is the latest, and the
  other way round. In view the client never sizes it: its pty always has the window's size,
  which the server reads from tmux every second (`#{window_width}x#{window_height}`, tmux's
  state, not the screen) and sends as a new `size`; xterm.js takes it, and its font shrinks
  from 13 px until the whole window fits the panel (the fit addon tells how many cells fit);
  below 8 px the panel scrolls, kept at the bottom, where the live lines are. tmux's ignore-size flag also keeps a view out while
  another client is attached.
- **History**: in view the wheel up opens a read-only layer over the terminal (`GET
  /api/sessions/{name}/agents/{agent}/history?lines=N`, tmux's history and the screen,
  wrapped lines joined) with **Back to live ↓**; xterm.js keeps no scrollback. For an agent
  whose CLI shows the alternate screen (`#{alternate_on}`: a full-screen TUI) the layer
  says that its history is inside its CLI and to take control to scroll it. In control the
  wheel goes to tmux: into copy-mode for a CLI that does not read the mouse (visible in the
  human's tmux too; LADO's next delivered message leaves copy-mode, `tmux.send_text`), and
  to the CLI itself when it reads the mouse (its own scrolling). Only shown: statuses still
  come from hooks.
- **What each CLI does** (checked by hand 2026-10-03, tmux 3.7): the fake agent and
  Claude Code (2.1.288) with its default renderer write to the main screen, so their output
  is in tmux's history: the layer shows it, the wheel in control scrolls in copy-mode.
  Claude Code with `"tui": "fullscreen"` in the human's own settings (LADO's agents read
  them too) and Kilo (7.8.1) run full screen and read the mouse: the layer shows the note,
  the wheel in control goes to the CLI.
- **Needs tmux 3.2** (`attach -f ignore-size`); `lado doctor` warns before it, and
  `terminal.open` refuses with the reason.

## Structure

Decided with the human in task 2 (2026-10-03): a frame for all the sections to come, all of
them visible from the start; a section not built yet is a placeholder. The work is in
Sessions for now. The UI's texts are in English.

- **Rail** on the left, top to bottom: Home, Needs you, Sessions, Projects, Kits,
  Marketplace; Settings apart at the bottom. A button collapses it to icons (each with its
  name as tooltip and accessible name; the button has `aria-expanded`). The browser
  remembers the choice; a window narrower than 900 px starts collapsed.
- **Top bar**: the page's title on the left; on the right the server's address and
  **Launch**. Launch only explains for now: starting a session from the UI comes later,
  until then `lado start <repo>`.
- **Sessions**: the list on the left (searched by name in the browser, the current one
  marked, stopped ones dimmed), the selected session on the right: its name and status,
  the place for its gates (a placeholder until the Gates task), and the tabs
  **Activity | Agents | Flows | Artifacts**, each a placeholder naming the task that fills
  it; Agents lists the agents live (name, role, provider, status) with **Open terminal**
  until the Agents task builds the whole section. Under them, on every tab, the
  **terminal panel** (Terminal above): docked at the bottom, collapsible, its height dragged
  (or the arrow keys on its edge) and remembered in the browser; its tabs are Supervisor
  (always, first) and the agents opened from Agents, each closed with ×. A hidden tab keeps
  its socket, a closed one closes it. `/sessions` with no name says "Select a session" (nothing is selected for the
  human); a name `/api/sessions` does not know says "Session <name> not found" with a link
  to the list, and the address stays as it was.
- **Needs you**: the gates of all sessions (Gates task); its count comes with it.
- **Gate**: a page of its own, `/gates/<id>` (`gates.id` is global).
- **Settings**: one page, its sections one under the other: Appearance (theme: system,
  light, dark) and Providers and environment (what `lado doctor` checks; a task of its
  own). New sections go below.
- **Placeholders**: one component, with the section's name, one sentence on what it will
  hold, and a link to the plan item that builds it. A placeholder is allowed only when its
  section has an item in ROADMAP.md or in Tasks below: Projects and Marketplace are
  ROADMAP's "Later (after stage 7)", the others are Tasks here.
- **Addresses**: `/` Home, `/needs-you`, `/sessions`, `/sessions/<name>/<tab>` (tab:
  activity, agents, flows, artifacts; without one, activity), `/gates/<id>`, `/projects`,
  `/kits`, `/marketplace`, `/settings`. Anything else is Not found with a link to Home.
  Opened directly or reloaded, each works (the server's page fallback, Server above).
  Routing: react-router in declarative mode.
- **Encoding rule**: every name in an address is one segment, encoded whole with
  `encodeURIComponent` (session names are free text, run names hold `/`); a run's address
  will be `/sessions/<name>/flows/<run, encoded whole>`. `web/src/paths.ts` makes them.
- **Without the token** the shell, one place, shows the server's own `detail` (open the
  link `lado ui` prints) instead of the page; no section knows about 401.
- **Theme**: system (follows `prefers-color-scheme`), light or dark, chosen in Settings,
  applied at once and remembered in the browser (without browser storage: system). The
  colours are tokens in one file, `web/src/tokens.css` (Look below); components use only
  the tokens, and a unit test fails on a colour written anywhere else.

### The human in the session (decided 2026-10-03, D7)

Settled after reading how another orchestrator does it: its feed shows the human's messages
and cards the orchestrator creates with tools; the orchestrator's own terminal text never
reaches the feed. LADO takes the model and builds it on what it has:

- **The human is a participant of LADO's messages** (`human`): agents write to it with
  `send_message(to="human")` (summary and body, as to any agent); the human writes from the
  composer to the supervisor by default, through the same queue, delivery confirmation and
  retries (no raw paste into a working agent). No second notification system.
- **Questions with options**: an `ask_human` tool (a question, optional choices, an optional
  free answer). The answer, or that the human dismissed it, comes back to the agent as a
  normal message; a dismissal is never silent.
- **Flow gates** are cards in the same feed, answered through `runs.answer` (the flow engine
  opens them, an agent cannot forget to).
- **A forgotten reply is caught, not hoped for**: when the supervisor ends a turn that a
  human message started and wrote nothing to `human`, the feed says "replied only in its
  terminal" (the terminal is beside the feed).
- **Layout**: the session page has the chat in the middle of Activity, the team (agents
  with their status) as chips above it, and the selected agent's terminal on the right
  (taking the place of the terminal panel at the bottom); the tabs stay Activity, Agents,
  Flows (which the other orchestrator lacks), Artifacts. The session list gets "+" (Launch)
  and its stopped sessions folded in a group at the bottom.
- The supervisor's role says to talk to the human only this way (lado-dev and the built-in
  `default` kit).

## Lessons from another orchestrator's UI

Taken: one event stream with replay; localhost by default; sessions that need the human
first; answer cards by gate kind; a web terminal through a tmux session per viewer (here
not a grouped one: its viewer could reach every agent's window and `lado stop` would leave
the windows alive; Terminal above); the server serves the bundle.

Avoided: two dozen polling timers and id-only events followed by full refetches; writes
that bypass the event bus; no token and a terminal WebSocket open to any local page; two
transports with different topics; several competing ways to message an agent; a one-slot
side panel; no entry point for what waits for the human; feature flags and wireframes in
production code; end-to-end tests with a mocked network; a terminal without reconnect or
backpressure; and in its chat: a reply that only a prompt makes the agent send, answers that
can be lost after delivery fails, a dismissed question the agent never hears about, a
"steer" box that pastes raw text into a working agent, and the human's messages signed as
an unknown sender.

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
   and how one moves between them; layout and navigation only, sections empty. Done:
   Structure above.
3. **Sections, one at a time**, each designed with the human and then built. Goal
   (decided with the human 2026-10-03): develop LADO from the UI instead of the terminal.
   The plan, in order (the placeholders link to the items below):
   1. Live updates, the change feed (D3). Done: The change feed above.
   2. The agent terminal in the browser. Done: Terminal above.
   3. **Chat** (D7; decided with the human 2026-10-03 to bring the UI with the core, no
      interim CLI command): `human` as a participant of messages, `ask_human`, the
      forgotten-reply check, the composer and a plain chat in Activity (messages with the
      human, question cards with their answer), LADO's own instructions to the supervisor.
      After it, work moves to the chat (with the release that ships it).
   4. **Layout**: the team chips above the chat, the selected agent's terminal on the right
      instead of the bottom panel, flow transitions and agent-to-agent messages (behind a
      switch) in the feed, the session list's "+" and its stopped sessions folded.
   5. **Gates**: gate cards in the chat, Needs you with its count, browser notifications.
      Then release 0.12.0: the human can work from the browser, tmux stays the fallback.
   6. Agents; Flows; Providers and environment; a pass over the look with a designer role
      (BACKLOG); then the rest; later the desktop app.

### Providers and environment

Settings: the agent CLIs LADO can run, their versions and logins, and what `lado doctor`
checks.

### Activity

A session's tab: the chat with the human (The human in the session, above), flow
transitions and notes as they happen, agent-to-agent messages behind a switch; the team as
chips; the selected agent's terminal on the right.

### Agents

A session's tab: its agents, their roles, status and branches.

### Flows

A session's tab: its flow runs, their state, who acts and the notes of each step.

### Gates

Gates as cards in the session's chat (and the gate page, `/gates/<id>`, for a long note),
Needs you (gates of all sessions and agents waiting for the human, with a count in the
rail) and browser notifications. Until this task gates show only in tmux (the
popup opens on the clients of the session's own tmux session, never on a browser's
viewer) and in `lado ls`: a human who works only in the browser does not see them.

### Artifacts

A session's tab: the documents the agents write (ROADMAP stage 7, Artifacts).

### Home

Later: an overview of all sessions, what runs, what is stuck and what waits for the human.

### Kits

Later: the kits LADO knows and where they come from (`lado sources`), with their roles,
skills, MCP servers and flows.

## Look

A first exploration of whole screens (2026-10-03) was not approved as a layout; only its
colours were: a light, calm ground (#F6F7F9, panels #FFFFFF, lines #E3E6EB, ink #16181D,
muted #5B6270), blue for actions and links (#1F5FD6), and orange only for what waits for the
human (#B4530F on #FDF1E6); IBM Plex Sans and IBM Plex Mono. Each section's mockups are made
and approved in its own task; this file keeps what was decided from them.

The dark theme (task 2): ground #111317, panels #181B21, lines #2A2F38, ink #E8EAEE, muted
#9AA1AD, actions #6FA0FF (labels on them #111317), waiting for the human #F0A25A on #3A2A1C.
Both themes add a raised ground for hover and the current item (#EEF0F4 / #20242C). Every
text colour has a contrast of at least 4.5:1 on its grounds in both themes; a unit test
(`web/src/tokens.test.ts`) checks it.
