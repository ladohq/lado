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
   terminal's WebSocket, the composer, answers to questions and gates): only a page of the
   server itself, whose Origin's authority (host and port, the scheme aside) is the
   request's own `Host` (a request with an Origin and no Host is refused); no Origin only
   with a Bearer token (a client that is not a browser). The server does not know the names
   it is reached by (`--host 0.0.0.0`, an SSH tunnel to another local port, a TLS proxy that
   keeps the Host), so it compares the two headers instead of a list; a page of another
   name that resolves to it (DNS rebinding) passes this check but has no cookie. Later the
   layer can be replaced by a real login for a remote host without touching the rest.
3. **One change feed: "changes after id N".** The UI learns about changes from one stream,
   never by polling lists. SQLite triggers write every insert, update and delete of the
   tables the UI shows (sessions, agents, messages, runs, gates, notes, kits,
   marketplaces; of events, the flow runs' new ones) to the journal
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
  port is an error naming its address.
- Versions: an upgrade (`uv tool upgrade lado`) leaves a running server on its old Python
  code while it reads the new bundle from disk, so the page would get an API it does not
  know. `lado ui` therefore restarts a server whose version (`server.json`) is not its own:
  it stops it, starts a new one on the same port and says so on stderr (`lado: restarted the
  LADO server: <old> -> <new>`); when the stop fails, it exits with an error naming
  `lado server stop`. The bundle knows the version it was built for (`__LADO_VERSION__`,
  taken from `pyproject.toml` by `web/vite.config.ts` at build time) and compares it with
  `/api/health`'s each time the change feed opens: when they differ, every page shows a
  banner (`role="alert"`) that names both versions and offers to reload the page (a
  Reload button): mostly the tab is the old one, opened before an upgrade. The tab keeps
  the server version it reloaded for (`sessionStorage`); when the versions still differ
  after that reload, the banner says to run `lado server stop`, then `lado ui`. A list a
  page cannot load (e.g. a 404 from an older server) shows the API's error, never an empty
  page.
- A newer LADO: `GET /api/update` (`UpdateInfo`: `current`, `latest`, `available`,
  `checked_at`) gives what the daily update check found (`lado.update.check`, the rule
  `lado ls` and `lado doctor` share; a plain `def`, so its look at PyPI holds up no other
  request). Asked each time the change feed opens; when a newer version is `available`,
  one quiet line under the top bar says `LADO X.Y.Z is available: run lado update`. A
  failed check shows nothing here (`lado doctor` says why). `lado update` restarts the
  server on the new version, on the same host and port.
- Host (decided 2026-10-04): 127.0.0.1 by default; `--host` takes any IPv4 address or name
  (`lado server`, and `lado ui` for a server it starts), e.g. `0.0.0.0` to open the UI of a
  remote host from another machine. An IPv6 address is refused (not supported yet). A
  non-loopback address prints a warning on stderr (so in `server.log` too) that the server
  is open to other machines and the token travels unencrypted: plain HTTP, a risk taken
  knowingly until TLS and a real login come. What the server reports is decided by the
  address it took (`run.Listening`): a loopback one is reached by itself, `0.0.0.0` locally
  on `http://127.0.0.1:<port>` and from others by the hostname, another address by itself.
  Only a busy port (`EADDRINUSE`) moves on to the next one (for `0.0.0.0` also one busy on
  127.0.0.1: macOS would let both take it, and the local link would reach the other); an
  address not on this machine,
  a name that does not resolve or a port it may not take is an error `cannot listen on
  <host>:<port>: <reason>`. `lado ui --host H` while the server listens on another address
  (names resolved: `localhost` is 127.0.0.1) is an error naming its address; without
  `--host` it takes the running server wherever it listens, and for a non-loopback one
  prints the warning and, after the local link, `From another machine: <link>`. The
  restart of a server of another version keeps its host and port.
- Port: 8000, or the next free one up to 8020; `--port N` takes exactly N (busy: an error;
  0: any free port, as the tests use).
- One per `LADO_HOME`: the server holds an exclusive flock on `LADO_HOME/server.lock` and
  writes `LADO_HOME/server.json` (url, host, port, pid, version; `url` reaches it from this
  machine, `host` is the address it listens on, 127.0.0.1 in a file of an older LADO
  without it; the health check, `lado server stop` and `lado ui` use `url`). The file
  counts only while the
  lock is held; with the lock free it is stale and removed, and `lado server stop` kills
  nobody. A second server refuses and names the first one's address.
- Token: `LADO_HOME/server-token` (owner only), made on the first start, replaced with
  `lado server --new-token`. The link `<url>/?token=<token>` (`url` from server.json) sets the
  cookie (HttpOnly, SameSite=Strict, Path=/) and redirects (303) to `/`, so the token leaves
  the address bar. Every page of the UI takes `?token=` the same way (decided in task 2):
  `/sessions/lado/activity?token=…` sets the cookie and redirects to
  `/sessions/lado/activity` with the other query parameters kept, so a link from a
  notification leads straight to its page. The redirect
  is the path as it was sent, still encoded (`%2F` in a run's name stays), and a path on
  this server (leading slashes become one: `//host/x` goes to `/host/x`). A wrong token is
  401. `/api/health` needs no token.
- Pages and files (task 2): the bundle's files are at its top (`/favicon.svg`) or under
  `/assets/`. A path under `/assets/`, or one at the top with a file extension, is a file,
  served as it is or 404, never the page: an open tab that asks for a file an upgrade
  removed must not get HTML instead of JS. Deeper down a dot belongs to a name
  (`/sessions/a.b` is a page). `/api/<unknown>` is a JSON 404. Every other path gets
  `index.html`, and the UI's router shows the page or Not found.
- Endpoints that start or end processes (Launch and session control): `POST /api/sessions`
  (start), `POST /api/sessions/{name}/resume`, `POST /api/sessions/{name}/stop` and
  `DELETE /api/sessions/{name}` (forget) change state like the composer and are guarded
  the same way (`Guard.changes`: the token and the server's own Origin). The lookups the
  New session window makes (`GET /api/folders`, `/api/folders/recent`, `/api/kits`,
  `/api/providers`, the stop and forget previews) need the token; `/api/providers` runs
  each CLI's `--version` on every request.
- Data only through `lado.state` and `lado.runtime`, no SQL in the server but the journal's
  read-only reader (`feed.Journal`, The change feed below). The server never
  migrates `lado.db`: every data endpoint first reads the schema version read-only and
  answers 503 for another one (older or newer), and `state.connect()` refuses another one
  itself (`state.SchemaError`, also a 503), so a change after that check migrates nothing.
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
  exit code and last log line. A stopping server ends every open event stream first (an
  event stream never ends by itself; a stream opened during the shutdown ends at once),
  then waits at most a second for the other open requests: a stop with a tab open is as
  fast as one without, and the browser reconnects as after any end of its stream.

### The change feed

Decided in the live updates task (2026-10-03).

- **The journal**: `changes(id, kind, session, key, op)` in `lado.db` (from schema 12), written
  by triggers on the six tables. `kind` is the table, `key` the row in its session (an
  agent's or run's name, a message's, gate's or note's id, `''` for the session). An update
  of an agent that changes `seen_at` (every hook sets it, alone) is no change. The journal
  keeps the latest `state.CHANGES_KEPT` (100 000) changes: each insert drops the older
  ones, in the writer's transaction; the server only reads. From schema 14 (the Layout
  task) `events` is in it too, key its `id`, but only inserts and only a flow run's events
  (`WHEN NEW.run IS NOT NULL`, `state.RUN_EVENT`): an agent's `status` event would double
  the journal, as its `agents` row is recorded already. A trigger's condition stays in
  `lado.db` as the trigger was made (`state.JOURNAL_WHEN`).
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
  (runs, notes until their tasks) has a null item; an agent's is its
  `AgentInfo`, as `GET /api/sessions/{name}/agents` gives it, a message's its
  `MessageInfo` (any message: each window of the store takes those its filter takes), a
  run event's its `RunEventInfo`, a gate's its `GateInfo` (`models.gate_info`, as
  `GET /api/sessions/{name}/gates` gives it: a closed gate's item replaces the open one's,
  it is never null), an artifact's its `ArtifactInfo` (`artifacts.of_artifact`, with its
  latest record). One table in `feed.py`, `ALSO`, says which change also
  changes another item: a change of `agents`, `gates` or `messages` also sends the
  session's (it counts its agents and what waits for the human in it, `waiting`); another,
  `OWNER`, the one item a row belongs to: a new `artifact_records` row sends its
  artifact's item (its new latest record). Each
  session item asks tmux for its status (`runtime.session_status`); a batch is collapsed
  first, so that is once per session in a batch. A comment line every 15 s keeps a quiet
  stream open. An item that cannot be built in full is sent without what failed, with the
  problem named (`problem` of a run whose flow snapshot cannot be read, `runs.SnapshotError`:
  no `states`; of its open gate: no `reads`), and the error is logged once per message, so
  one bad row never stops the feed or a list endpoint.
- **The start of a stream**: the position is the `Last-Event-ID` header (the browser's own
  reconnect) or else `?after=N`. Without a position, or with one the journal no longer has
  (dropped, or ahead of it), the stream starts with `event: reset` whose `id` is the latest
  position, taken before it is sent; the UI loads its data on reset (the first load and
  the load after a gap are one path) and gets every change after it. With a position the
  journal has, the stream sends what came after it, then the current value of every
  derived field.
- **Message windows** (feature/chat-paging, 2026-10-05): a session's messages grow without
  end (5 MB for session `lado` on 0.18.0), so no page loads them whole. `GET
  /api/sessions/{name}/messages` takes the kind (`with=human`, `agent=<name>`: from and to
  it), id cursors (`before`, `after`), times (`since`: from the start of its second;
  `until`: to the end of its second, so a time with milliseconds keeps a row of the same
  second; ISO 8601, another value 422) and `limit` (the latest n; without it every message
  that matches), all in SQL (`state.MessageFilter`, `state.message_page`; no index: `ORDER
  BY id DESC LIMIT` walks the rowid). It answers `MessagePage {items (oldest first),
  earlier}`: whether messages of the kind and times (cursors aside) come before the first
  item. The store (`live.ts`) keeps windows by session and filter (`watchMessages`): the
  latest page when one opens; `loadEarlier` (the page before its first message, one at a
  time); `loadUpTo` (from a message id or a time up to the window, one request). A
  window's `from` is the time from which it holds every message of its kind (null when it
  holds all). The feed's rule (`matches`, the server's filter in the browser; one case
  table, `web/src/messageFilter.cases.json`, checks both): a change the filter takes is
  added after the last item, put in its place inside the window, and left out before it
  while earlier ones are not loaded; one it does not take, or null, leaves it. While any
  load into a window runs, its changes wait and are applied after the last one, as a whole
  list's are. On `reset` a window loads again from its first message (`after=<first - 1>`),
  so it keeps what the human scrolled back to. Other lists (agents, events, gates, runs,
  notes) stay whole; notes are next (BACKLOG.md).
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
  terminal), shown, no reconnect by itself; 45xx for now (4500 the terminal closed, 4503
  lado.db of another schema), the UI opens a new socket after 2 s.
- **Reconnect** (the UI polish, 2026-10-03): a terminal closed for good shows
  **Reconnect** beside its reason, which opens a new socket in the same tab (the
  supervisor's tab cannot be closed, so it would stay dead otherwise). It also opens again
  by itself when its agent comes back or changes in the session's agents (the panel
  follows them on every tab): a stopped session's supervisor is live again after
  `lado start`, with no reload. The agent as it was at the close is kept, so an agent that
  still has no terminal is not asked again until it changes.
- **Modes**: every terminal opens in view, the supervisor's too (the Layout task: the human
  writes to agents in the chat, and a window is never resized without the human's own
  step); **Take control** asks first in a modal dialog (`<dialog>`, Esc is Cancel) with
  **Don't ask again**, remembered in the browser (`lado.askControl`) for every agent; there
  is no setting for it, and the button's tooltip always has the explanation. Without
  browser storage it asks every time. **Release** goes back. In control tmux
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
- **Tabs** (the human's additions to the UI polish, 2026-10-03): left of its agent's name
  a tab shows the agent's status as the team chip's dot, smaller (`StatusDot`, one
  component, `dot-small`), from the session's agents list, live; an agent not in the list
  shows as stopped; the tab's accessible name has the status too. The collapsed strip shows
  a column of these dots under **Terminals**, one per open tab, each titled with the agent
  and its status. Many tabs stay on one line: a name is cut with an ellipsis down to about
  72 px (a shorter name stays whole), then the row scrolls sideways (the wheel too) under a
  thin bar; the supervisor's tab stays at the left (sticky), the tab selected here or by a
  chip scrolls into view, and Expand and Collapse at the right never move. The whole name
  is in the tab's tooltip (below), not in a `title`. The tabs look as every tab of the UI
  (Look, Tabs).
- **Focus** (2026-10-05, task feature/sessions-list-collapse): after **Collapse
  terminals** the focus is on the strip's **Terminals**, after Terminals on Collapse
  terminals, as for the session list's strip (`Splitter.useStripFocus`). Only those buttons
  move it: a page that opens collapsed, or a chip that opens the panel, leaves it where it
  is.
- **Expand**: the panel's **Expand terminal** shows it over the whole content (the rail
  and the top bar stay; `position: absolute; inset: 0` in the content, so no widths are
  written twice; on a narrow window over the whole window), with the same terminals and
  sockets, the mode kept; **Restore terminal** puts it back, and so does Esc, except in a
  terminal the human controls: there Esc goes to the agent. Not remembered.
- **Needs tmux 3.2** (`attach -f ignore-size`); `lado doctor` warns before it, and
  `terminal.open` refuses with the reason.

## Structure

Decided with the human in task 2 (2026-10-03): a frame for all the sections to come, all of
them visible from the start; a section not built yet is a placeholder. The work is in
Sessions for now. The UI's texts are in English.

- **Rail** on the left, top to bottom: Home, **Launch** (a button that opens the New
  session window: Launch and session control, below), Needs you, Sessions, Projects, Kits
  (one page for the kits and their marketplaces: Kits below); Settings apart at the
  bottom. A button collapses it to icons (each with its
  name as tooltip and accessible name; the button has `aria-expanded`). The browser
  remembers the choice; a window narrower than 900 px starts collapsed.
- **Top bar**: the page's title on the left; on the right the server's address and the
  change feed's link (`live`, or `reconnecting…` with the reason).
- **Sessions** (the Layout task, 2026-10-03): three columns under the top bar, each the
  window's height. The **list** on the left: "+" in its head (it opens the New session
  window, as Launch), the
  search by name, and the sessions in groups: **Needs you** (something waits for the
  human: `SessionInfo.waiting`, counted by the server: open gates, open questions, agents
  in `waiting`), **Running**, and **Stopped** at the bottom. Nothing in a stopped session
  counts as waiting (its waiting is all zeros), though its gates stay open and `lado ls`
  shows them: nothing in it can be answered until it is resumed. The groups (decided
  2026-10-05, task feature/session-list-groups; mockup
  `.lado/mockups/session-list-groups/index.html`, variant C2,
  https://claude.ai/artifact/36B8Z5KWxKWhyMPcyswL5M version 3) look and work alike: each
  is under the one group heading of every list (`GroupHead.tsx`, List and page below), a
  band of its tone, Needs you `human` (`--human` on `--human-ground`), Running `done`
  (`--done` on `--done-ground`), Stopped `neutral` (`--muted` on `--raised`), the name in
  small capitals and the count on the right in the group's colour, a chevron on the left.
  The whole band is a button (`aria-expanded`, `aria-controls` naming the group's list,
  which stays in the page folded or not; Enter and Space as any button) that folds and
  opens its group; a folded group keeps its count, and a group without sessions is not
  drawn, heading and all. Each group's state is remembered in the browser by its id
  (`lado.sessionGroups`: `{"needs-you", "running", "stopped"}`, each `open` or `folded`);
  by default Needs you and Running are open and Stopped folded. The older key of Stopped
  alone (`lado.stoppedSessions`) is only where Stopped starts while `lado.sessionGroups` is
  not stored, and never read after. While the search has text every group with a match is
  shown open, its heading is off (`disabled`: a click would change what is remembered and
  nothing seen), and nothing remembered changes. The open session is always seen: in a folded
  group (the human folded it, or the session moved there, e.g. stopped into Stopped) its
  row alone shows under the heading; going to a session never opens a group nor changes
  what is remembered. The rows look alike in every group (no dimmed stopped ones, no
  orange in Needs you): the open row and the one under the pointer or focus get a stripe
  of their group's colour on the left. Each shows a line under its name: what waits, or
  its agents, the status of a session whose tmux session is gone or whose loop does not
  run, and on hover or keyboard focus of the row ⋯ with the entry's menu, Copy link and
  Open in new tab; the session's own actions are in its head (Launch and session control,
  below). On hover or keyboard focus a row shows the session's card (`SessionTip` in a
  `Tooltip`, the one of the strip's icons, below): a dot of its group's colour, name ·
  status · agents, `Needs you: <the row's line>` in the human's colour, the folder, kits ·
  provider · `mode <permission mode>` when it has one, and for a stopped session `Stopped:
  open it and press Resume`; all from `SessionInfo`, no CLI commands. The **session**
  in the middle: its head in two lines (task feature/session-head, 2026-10-05), then the
  tabs **Activity | Agents | Flows |
  Artifacts** (their look: Look, Tabs; its gates come as cards in the feed): Activity is the
  feed (The human in the session, below), Agents the agents and what each does (Agents
  below), Flows the runs (Flows below), Artifacts the documents the agents write
  (Artifacts below). The head's first line: the name, the status, how long the session ran, then on the
  right Copy link and its actions (Launch and session control, below). The run time is
  the server's (`SessionInfo.ran_seconds`, `running_since`: `runtime.session_time`, stops
  and the time after its tmux died left out); while it runs the UI adds the time since
  `running_since` and counts on each minute ("2 h 14 min"); a stopped session says
  `stopped 5 h ago · ran 3 h 2 min` (from `stopped_at`), one whose tmux is gone `ran …`.
  One formatter (`ChatText.duration`) says every duration: exact to the next unit here,
  roughly (its largest unit) for `since` in Agents and Flows. The second line, small and
  quiet: Copy path (a folder icon, no other copy button), the folder in mono on one line,
  cut with "…" at its start so its end stays in view, whole in its `title`; its git remote
  and branch; the kits; the provider · permission mode (the provider alone without a mode);
  versions in tooltips (Session head, below). In a narrow column the
  icons of the first line and the items of the second go to lines of their own, with no
  sideways scrolling. The Activity chat (its feed and composer) is at most 860 px wide and
  stands in the middle of a wider column (the terminals folded), as much room on each
  side; an agent's composer (Agents) stays at its page's left edge. The **terminal panel** on the
  right, on every tab (Terminal above), is always there, so the page never jumps (the UI
  polish, 2026-10-03): its first tab is the supervisor's, pinned (no ×), shown when the
  page opens; a team chip or Open terminal adds an agent's tab or selects it, and the
  others close with ×, the supervisor's then shown. A tab's socket opens the first time
  it shows in the open panel, then a hidden tab keeps it and a closed tab closes it. The
  price: each session page opened with the panel open makes one viewer (a tmux session) on
  the server, closed with the page. **Collapse terminals** leaves a strip with a
  **Terminals** button that opens it again; collapsed, its terminals keep their sockets
  but are hidden, so nothing is resized (in control too), and a panel collapsed when the
  page opens opens no socket until it is opened. A chip opens a collapsed panel. Collapsed
  is remembered in the browser (`lado.terminals`) and is the default below 900 px.
- **The list collapsed to a strip** (decided 2026-10-05, task
  feature/sessions-list-collapse; mockup `.lado/mockups/sessions-list-collapse/index.html`,
  https://claude.ai/artifact/TTZcaWXnyooRPxyYBqEB3g version 2): **Collapse sessions** in
  the list's head, after "+", with Collapse terminals' icon mirrored, folds the list to a
  strip of 44 px, `nav "Sessions"`, and the session gets the room (no edge to drag; the
  list's width stays remembered for when it opens). On the strip, in order: **Sessions**
  (the Terminals button's look, read from the bottom up; it opens the list), "+" (New
  session), and a column of icons that scrolls while the two buttons stay: one per session
  not stopped (`live.isLive`), Needs you first, then Running, as the open list orders them,
  with a line between the two when both have sessions. An icon is a link to the session at
  the row's address (`aria-current` as the row's): two letters in the mono font in a
  neutral square, the first of the name's first two words (split at `-`, `_`, `.`, `/`,
  space) or else its first two (`crm-api` CA, `lado` LA); two sessions may share them. One
  that needs the human is marked by colour only (`--human` on `--human-ground`, no count),
  and its label says `<name>, needs you`. On hover or focus it shows the session's card,
  the row's (above). While the list loads the column is empty and `aria-busy`; when
  `/api/sessions` fails, an alert icon in `--danger` takes its place with the error in its
  label and tooltip, the open list's text; Sessions and "+" work either way. Collapsed is
  remembered with the width (`lado.sessionsList`, `{ width, collapsed }`) and is the
  default below 900 px, the same rule as the terminals' (`prefs.storedColumn`: nothing
  stored and `(max-width: 900px)` collapsed; a value stored before it could collapse is
  open). Below 900 px, where the columns stack, the strip is a row over the session:
  Sessions, "+", then the icons in a row that scrolls sideways. After Collapse sessions the
  focus is on Sessions, after Sessions on Collapse sessions, only after those buttons (not
  when a page opens collapsed).
- **List and page** (task feature/flows-list, 2026-10-04, boards 14–15 of the canvas; one
  component, `ListPage.tsx`, for every tab with a list: Agents (Artifacts is a table of its
  own, Artifacts below); since task
  feature/flows-list-states, 2026-10-07, Flows has an overview of its own, Flows below,
  which shares the list's group, `ListGroup`, and its search's filter, `filterGroups`):
  the tab's list of items and the page of the one its address names. In a column of 900 px
  or wider the list is on the left (240–300 px) and the page on the right, each scrolling
  by itself; an address without an item goes (replaced) to the tab's default item. In a
  narrower column (the terminals open) the address without an item shows the list over
  the whole column, with no redirect, and an item's address shows its page alone, under a link back to the list (`‹ All runs (2 open, 39 ended)`, `‹ All
  agents`), which comes back with its search and its scroll as they were. Until the
  column is measured neither is drawn. Above the list a search (`Find a run`), any case,
  by the texts each tab names, over every group at once; while it has text each group
  shows every match, a group with an `empty` text and no match says "No match", and with
  none anywhere it says `No run matches “…”`. No group folds (decided 2026-10-05, task
  feature/flows-tab-redesign): each is open under its heading, the one of every list
  (`GroupHead.tsx`, since task feature/session-list-groups): a band of the group's tone
  (`Group.tone`: `human`, `done` or `neutral`, the default), its name in small capitals
  and how many rows it has now, no chevron; the session list's groups and the Flows
  overview's use it with folding (`ListGroup`'s `fold`). A group's rows are list rows or,
  in an overview, cards (`Group.look`: `row`, the default, or `card`). The groups are apart by a
  gap. A group may say why it is empty (`empty`: "No active runs"; without it an empty
  group is not drawn, as Agents' one group without a heading, `heading: false`), show its
  rows under their local day (`days`: Today, Yesterday, a date; a row has the time) and
  its first N (`first`) and then **Show N more**. The selected item is always seen and
  marked (`aria-current`), also past the first N; items are picked by key. The page is a
  size container: its own layout goes by its own width (`@container`), not by the
  column's.
- **Columns**: the list and the panel are resized on their edges with one component
  (`Splitter.tsx`: a `separator`, dragged, the arrow keys, a double click for the default
  width; a wide grip with a `col-resize` cursor and a line on hover and focus), within
  bounds (list 200–480 px, panel 280–1200 px), and remembered in the browser
  (`lado.sessionsList`, `lado.terminals`). The session in the middle keeps at least
  360 px: in a narrower window the list and the panel are drawn narrower, but their chosen
  widths stay remembered for a wider window.
- **The window never scrolls** on a wide window: `html` and `body` do not scroll or bounce
  (`overflow: hidden`, `overscroll-behavior: none`) and the frame is the window's height;
  only regions inside scroll (the session list, the feed, the session's column, a page's
  content, a terminal and its history), each without passing its scroll on. Below 900 px
  the columns stack and the page scrolls, as before.
  `/sessions` with no name says "Select a session" (nothing is selected for the human); a
  name `/api/sessions` does not know says "Session <name> not found" with a link to the
  list, and the address stays as it was.
- **Needs you** (`/needs-you`, the task Needs you and notifications, 2026-10-03): what
  waits for the human in every session not stopped (`sessions.stopped_at IS NULL`, so
  `tmux_gone` and `loop_down` count; the server and the UI apply the one rule), oldest
  first, by session, each session's name a link to its chat: open gates as the chat's
  `GateCard`, open questions as its question card (`Question.tsx`), both answered in
  place; agents in `waiting` with their role, since when, and why (`status_reason`, or
  "waits for you in its terminal" when LADO knows no reason), with **Open terminal**
  (`/sessions/<name>/activity?terminal=<agent>`: the panel opens that agent's tab and
  drops the parameter from the address, replaced, so Back and a reload do not open it
  again; an agent the session does not have is named in a line). Each item links to its
  card in the chat (`#gate-<id>`, `#message-<id>`; the chat scrolls there once loaded,
  after its scroll to the latest). Nothing waiting: "Nothing waits for you". The list is
  `GET /api/waiting` (`WaitingItem`: session, kind, key, since and the gate, question or
  agent in the form of their own endpoints), built from `state.waiting_items`, which is
  also what `SessionInfo.waiting` counts: the count and the list cannot differ. The live
  store keeps it as its list `waiting` (`watch("waiting")`): an item has no row of its
  own in the journal, so the store loads it whole again on `reset`, on every change of
  any session's gates, agents or messages, and when a session stops or comes back; one
  load at a time, one more for all changes that came meanwhile. A count is never the
  trigger: one item in place of another keeps it. Answered here, in the chat or with
  `lado answer`, an item goes without a reload. **The count**: the sum of the
  not-stopped sessions' `waiting`, from the live session list, as a badge on the rail's
  Needs you (also collapsed; its accessible name `Needs you, <n> waiting`), and first in
  the tab's title while above zero: `(<n>) <page> · LADO`. A gate has no page of its
  own: it is a card in its session's chat.
- **Settings**: one page, its sections one under the other: Appearance (theme: system,
  light, dark), Notifications (the switch Browser notifications, below) and Providers and
  environment (what `lado doctor` checks; a task of its
  own). New sections go below.
- **Placeholders**: one component, with the section's name, one sentence on what it will
  hold, and a link to the plan item that builds it. A placeholder is allowed only when its
  section has an item in ROADMAP.md or in Tasks below: Projects is ROADMAP's "Later (after
  stage 7)", the others are Tasks here.
- **Addresses**: `/` Home, `/needs-you`, `/sessions`, `/sessions/<name>/<tab>` (tab:
  activity, agents, flows, artifacts; without one, activity), a flow run's page
  `/sessions/<name>/flows/<run>` (Flows below), an agent's page
  `/sessions/<name>/agents/<agent>` (Agents below; another tab has no pages),
  `/projects`,
  `/kits`, `/kits/<tab>` (installed, available, updates; without one, installed),
  `/settings`; `/marketplace` of earlier versions goes (replaced) to `/kits`. Anything else
  is Not found with a link to Home.
  Opened directly or reloaded, each works (the server's page fallback, Server above).
  Routing: react-router in declarative mode.
- **Encoding rule**: every name in an address is one segment, encoded whole with
  `encodeURIComponent` (session names are free text, run names hold `/`); a run's address
  is `/sessions/<name>/flows/<run, encoded whole>` (`runPath`), an agent's `agentPath`.
  `web/src/paths.ts` makes
  them.
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
  opens them, an agent cannot forget to). Built (Gates task, gates in the chat): the server
  lists a session's gates (`GET /api/sessions/{name}/gates`, `GateInfo`: the question, the
  options, the note that led to the gate with its attachments and, only while it is open,
  the full names of the artifacts its state reads but those the note carries, `reads`) and
  takes the human's answer
  (`POST …/gates/{id}/answer {option, comment}`, guarded like the composer, through
  `runs.answer_text`, the one text `lado answer` prints too; what the core refuses is 400
  with its reason). An **open gate** is a row of the feed where it opened (the flag
  avatar, "Gate #id", muted "run · state", the time; Look of the feed below) with its card,
  which has no head of its own: the question, the note before the gate (its summary in bold, its body
  open, more than 20 lines behind Show more) with its chips, then under a muted "It reads"
  a line per artifact the gate reads (a chip that opens its latest record, and its "title —
  summary"; "<name>: no record yet"; the name alone while the session's artifacts are not
  loaded): the latest record comes from the feed's artifacts, so a write while the gate is
  open shows at once, and the note's chip of an artifact written since says "changed
  since" (docs/design/artifacts.md, Flows), an optional comment for the next
  step, and a button per option (Approve / Reject, a choice gate's own options, Continue /
  Cancel run at a loop limit; the first one primary). The buttons are off while the answer
  is sent and in a stopped session (it says to resume it); a refusal shows on the card.
  The card changes only when the feed brings the closed gate, wherever it was answered
  (the popup, `lado answer`, another tab). A **closed gate** is a quiet line at the text's
  column, as the run events: "Gate #id · run · state: <answer> by <who>" (one title,
  `gateTitle`, also on a run's page in Flows; also `overridden` by `lado flow-set`,
  `cancelled`), its comment and time; a click shows its question and note, read only,
  without the artifacts it read, which are not kept as they were when it was answered. The
  line stays where the gate opened, often far above the bottom; the **human's answer** is
  where it was given as one line, the run's move it made (a `flow` event of `human`), with
  the answer's comment under it (Flow events in Look of the feed; since
  feature/chat-message-text, 2026-10-07: no row of its own besides). On the open page it
  shows at the bottom as soon as the feed brings the event, and the feed scrolls to it as
  to a new message. While a gate is open, a
  hint over the composer (an orange band, "Gate #id waits: answer on its card") scrolls to
  its card: the
  composer does not answer gates.
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

Built in the chat task (2026-10-03):

- **Core**: `human` is a recipient without an agent: a message to it is `delivered` at once
  and typed into no window (`runtime.post`). It is sent only by the server's API
  (`runtime.write_as_human`): an agent's MCP tools always send as the agent, and `human`
  and `lado` are names no agent may take (`state.RESERVED`, checked by `spawn_worker`).
  The human's text: its first line, tabs and control characters made spaces, is the
  summary, cut to 200 characters with "…"; the whole text is the body when it has more
  lines or the line was cut; over 8000 characters it is refused. It goes through the queue,
  confirmation and retries like an agent's; if it fails, `lado` tells the human in one line.
  Messages to `human` are never dropped: stop, finish and `drop_undelivered` leave them as
  they are and do not count them (`state.UNRECEIVED`).
- **Questions**: `ask_human(question, details, choices, free_answer)`, for every agent; at
  most 6 choices of at most 160 characters each, no duplicates; no choices and no free
  answer is refused. A question is a message of kind `question` to `human` with its
  `choices`, `free_answer` and `question_state` (`open`, `answered`, `dismissed`,
  `closed`). The answer (`Answer to #<id>: <choice or the first line>`, the rest in the
  body) or the dismissal (`Dismissed #<id>`) is a message from `human` to the agent with
  `reply_to` and `choice`, queued in the transaction that sets the question's outcome and
  `answered_by`; a question not `open` refuses both. When the agent is forgotten
  (`runtime.close_worker`: finish, a run's end or cancel, a failed spawn; `lado stop`), its
  open questions are `closed` in the same transaction.
- **Where the human asked**: LADO's instructions to the supervisor say to answer
  `[from human] …` with `send_message(to="human")` or `ask_human`, and text typed into its
  window in the window. The forgotten-reply check: at a turn's end, before the queue is
  handed over, each message from `human` to the agent in `delivered` or `read` that is not
  an answer or dismissal and has no `reply_state` yet gets `replied` (the agent wrote to
  `human` after it got it: compared by when each was handed over, `sent_at`, not by id, as
  the human's message is queued before it is handed over) or `missing`; each one is checked
  once.
- **Schema 13**: `messages` gets `kind`, `choices`, `free_answer`, `question_state`,
  `answered_by`, `reply_to`, `choice`, `reply_state`; their changes reach the feed through
  the `messages` triggers.
- **API**: `GET /api/sessions/{name}/messages?with=human` (`MessageInfo`, oldest first);
  `POST /api/sessions/{name}/messages` `{to?, text}` (default to the supervisor);
  `POST /api/sessions/{name}/questions/{id}/answer` `{choice?, text?}` and `…/dismiss`.
  The POSTs need the server's own Origin (`Guard.changes`), answer 503 under another
  schema, 404 for an unknown session and 400 with the core's reason for what it refuses
  (a stopped session, an agent that is not running, a question not open). They return
  `{result}`; the UI shows a message only when the feed brings it.
- **UI**: Activity is the chat: the messages from and to the human (their text as Message
  text in Look of the feed says, Markdown with any HTML left out), "not delivered" on a
  failed one, "<agent> replied only in its terminal" on a `missing` one, and each question
  as a card in its agent's row; the composer under it. Its look is Look of the feed, below.

**Look of the feed** (decided with the human 2026-10-07, task feature/chat-look, mockup
`/Users/kao/Projects/lado/.lado/mockups/chat-look/index.html`, variant B "feed"):

- **A row** (`FeedRow.tsx`, the one place that draws who wrote an entry, in the chat and on
  Needs you): a 32 px avatar column, then the head and the content, the chat's whole width
  (at most 860 px). The head: the name (Inter 600; the human's is "You"), a muted part,
  the time on the right (24 hours, a `<time>`). The muted part: "→ <to>" for the human's
  messages and the agents' messages to each other, also "· answer to #N" (a link to
  `#message-N`) for an answer to a question not in the window; nothing for an agent's message to the human (a message
  keeps no run: BACKLOG). No frame on a message; a row's ground is `--raised` on hover;
  the human's rows lie on `--action-ground`, the whole width, not moved to the right. The
  row's kind (agent, human, gate) is its own prop, so an agent named `gate` is an agent.
  The cards in rows (a question's, a gate's, a waiting agent's on Needs you) have no head
  of their own.
- **Groups**: an entry continues the group above it (no head, no letter; its time in the
  avatar column, seen on hover and focus, always in a column of 520 px or less) when the
  row above is a message or question of the same sender to the same recipient, less than
  5 minutes before it; a day divider, a run's events, a gate or a late reply's line between
  ends a group. The human's reply to a question in the window is no row (Answer in the
  question card, below), so it ends no group; a reply to a question not in the window
  stands alone, never continuing a group nor continued: an answer's head says which
  question it answers, a dismissal is a line. One pure function, `feedRows` in `Chat.tsx`,
  makes the rows: also a **day divider** (a line with the day's name, `dayName`) between
  entries of different local days, and a run's events in groups (Flow events). "Start of
  session …" stays on top.
- **Message text** (decided with the human 2026-10-07, task feature/chat-message-text,
  mockups `/Users/kao/Projects/lado/.lado/mockups/chat-message-text/index.html`, right
  column, and `fonts.html`, column B): each message shows its text once, as in Slack;
  drawn in `MessageText` (`Chat.tsx`) by who wrote it, never by changing the core's
  summary and body.
  - The **human's message** (not a reply to a question): one text, the body when there is
    one (the core's body is the whole text, its summary the first line:
    `runtime._human_text`), else the summary; no heading, nothing folded. Markdown with
    the human's single line breaks kept as breaks (`Body` with `breaks`, a small remark
    plugin of `ChatText.tsx`).
  - **Markdown** (task feature/markdown-render, 2026-10-08): every Markdown text of the UI
    (messages, gate and run notes, answers, an artifact in the viewer) is one `Body`
    (`ChatText.tsx`): react-markdown with `remark-gfm`, GitHub-flavoured Markdown (tables,
    task lists with disabled checkboxes, strikethrough only with `~~`, so `5~10 min` stays
    text, autolinks, footnotes), any raw HTML left out (`skipHtml`), links through
    react-markdown's default URL transform. Each `Body` has its own footnote ids
    (`clobberPrefix` from `useId`), so a footnote link never jumps to another message's.
    Its typography is one set of rules on `.chat-body`, in `em` so a card's 14 px and the
    viewer's 15 px step alike: headings h1–h4 in steps, h1 with a rule under it; lists
    indented, task items without bullets; inline `code` on `--raised` in `--mono`; quotes
    muted with a `--line` bar; `del` muted; links `--action`. A table sits in a
    `.md-table` frame (`--line`, radius 6) that scrolls sideways when the table is wider,
    so neither the chat nor the panel ever does: the table `max-content` wide and at least
    the frame's, the head row on `--raised` in 600 without wrapping, cells 6×10 px whose
    words are never split letter by letter, each column aligned as its `:---:` says.
  - An **agent's message to the human**: the summary in Inter 600, the whole body under
    it (Markdown: agents wrap lines by width, so no `breaks`). The summary is not drawn
    when it only repeats the body (`repeatsSummary`, only for agents' messages): the
    body's first line that is not blank, trimmed, is the summary, or the summary ends in
    "…" and that line starts with the rest of it.
  - **Long text** (`Preview`, `clamp`): a line that is not blank counts for 200
    characters (`CHARS_PER_LINE`). A message's text shows whole up to 30 such lines and
    6000 characters; a longer one shows its first 12 (at most 2400 characters), then
    **Show more** / **Show less** (`aria-expanded`), which opens it in place. Every
    `Preview` says Show more: the note before a gate cuts at 20 lines, an agent's task in
    Agents at 3, each at its own number of lines.
  - The **agents' messages to each other**: one muted line of the summary (14 px, cut with
    an ellipsis), a chevron before it when there is a body, which opens under it on a click
    or the keyboard (a native `<details>`) with a muted rule on its left.
  - Size: a message's summary and text are 15/22 px and at most 720 px wide, only in the
    chat's messages (`.chat-message`); the shared `.chat-body` of a gate's card, Flows and
    an agent's task keeps its size; code 13 px mono.
- **A question**: open, an orange card (a 4 px band on its left) "Question #N · waits for
  you", its choices, field and Dismiss as before; closed, a neutral card "Question #N",
  its choices faded, the chosen one marked "✓" in `--done`, and the human's reply in the
  card (Answer in the question card); "Closed: the agent left" when its agent was
  forgotten. The reply's text comes from the answer's fields, never from parsing the
  core's line (`replyOf`): the `choice` with the body under it as a comment; else a body
  that is not empty (the whole text, `runtime._human_text`); else the summary without
  `Answer to #N: ` (as `runtime.answer_question` writes it). A dismissal is told by its
  question (`dismissed` and `answered_by` this message; with no question in the window, by
  the summary `Dismissed #N` of `runtime.dismiss_question`).
- **Answer in the question card** (decided 2026-10-07, feature/chat-message-text, mockup
  `question-answer.html`): with its question in the window, the reply is drawn in the
  question's card under the choices, on the human's ground: a small "Y", "You ·
  answered" (or "You · dismissed", quieter), its time, and the answer (the choice in
  bold "✓", the comment under it; else the own words) as Markdown with `breaks`. Without
  the reply in the window, the block says only "You · answered" or "You · dismissed".
  When the reply is the row right under its question, it is no row; when other rows came
  between, one quiet line stands where it was given (it ends a group): "Y", "You answered
  question #N ↑" (a link up to the card, `#message-N`) and the answer's start on one line
  cut with an ellipsis, or "You dismissed question #N ↑". A reply whose question is not in
  the window (pages not loaded) is the human's row "answer to #N" as before, a dismissal
  the line "You dismissed question #N". The reply's anchor `#message-<id>` is its late
  line when there is one, else its block in the card.
- **Flow events** (decided 2026-10-07, feature/chat-message-text, mockup
  `flow-events-a.html`): a run's events in a row, with no other row between (whatever the
  time), are one group (`<ol aria-label="Flow run <run>">`): the flow icon and the run's
  name once on top, a link to its page in Flows; no link in the lines. A line (Inter
  13 px, at the text's column): a small avatar of the actor (an agent's colour, "Y" for
  `human`, a grey "L" for `lado`), its name muted ("You" for the human), then by kind: a
  `flow` move as chips, the state it left (mono, muted) → the state it entered (mono) and
  the outcome, green (`--done`) forward and orange (`--human`) back; `flow_start`
  "started", `gate_open` "waits for you" (orange; the gate's card is the row under it),
  `flow_end` "ended" (green), `flow_cancel` "cancelled", `flow_set` "set by you", each with
  the core's `detail` as it is, cut by CSS on one line (the UI parses no detail); a
  `flow` event whose detail is no move shows its detail. The time on the right, always
  seen. `gate_answer` is no line: the human's answer is their move. A move goes back when
  it stays in its state or enters a state its run left earlier **in the loaded window**
  (`goesBack`): when earlier pages load, a move's colour may turn from green to orange;
  its outcome is always written. The **human's answer to a gate** is one line: their
  `flow` move (only the human's answers write a `flow` event as `human`; `lado flow-set`
  writes `flow_set`), with the answer's comment under it (Markdown with `breaks`), from the
  `GateInfo` of its run answered by `human` in the state the run left or entered (a loop
  limit's `continue` enters the gate's state), closed nearest to the event (`gateOf`; the
  answer and the move are one transaction). Without that gate loaded, the move alone. The
  closed gate's line stays where it opened.
- **Quiet lines** (run events, a closed gate, a late reply, a dismissal) start at the
  text's column.
- **The composer** (shared with an agent's page in Agents): one frame, the field without a
  resize handle growing with its text from 1 to 8 lines (by its `scrollHeight`), then
  scrolling; Send inside at the bottom right (`--raised` / `--muted` while off); on focus
  an `--action` frame and an `--action-ground` ring. Under it "to <agent>" and "Enter to
  send · Shift+Enter for a new line". Enter sends, Shift+Enter is a new line; a refusal
  shows at the field and the text stays; a stopped session's composer is off and says so.
- **Narrow** (a column of 520 px or less): 24 px avatars, the continued rows' times shown,
  no sideways scroll.

Built in the layout task (2026-10-03, schema 14):

- **Run events in the journal**: the flow runs' events reach the UI through the `events`
  triggers (The change feed above); `GET /api/sessions/{name}/events` lists them
  (`RunEventInfo {id, run, kind, actor, detail, transition, created_at}`, oldest first);
  the server does not parse `detail`, but for a move: `transition {from_state, outcome,
  to_state}` of a `flow` event, read by `state.transition` next to its one writer
  `state.flow_detail` (since feature/chat-message-text), else null.
- **API**: `GET …/messages` without `with` gives all the session's messages (`with=human`
  stays; pages since feature/chat-paging: The change feed, Message windows); `SessionInfo.waiting {gates, questions, agents}` counts what waits for the human
  (open gates, open questions, agents in `waiting`), computed in `models.session_info` from
  the tables: the one definition of "needs you" for the session list now and the rail's
  count later; `AgentInfo` has `run` and `task` (the first line of its task).
- **Activity**: the team above the feed, a chip per agent, the supervisor first: a status
  dot that differs in colour and shape (busy a full circle, idle a ring, waiting an orange
  diamond, starting a dashed ring, stopped a grey square), its name and role, a tooltip;
  the chip of the terminal the panel shows is marked. The agents are grouped (decided
  2026-10-07, feature/activity-team), from `AgentInfo.run` only: the supervisor and its
  own workers (no run) come first, as the server lists them; then each run that has an
  agent, in the order its first agent is listed, as a dashed frame (`role="group"`,
  `run <name>`) with the run's name, a link to its page in Flows, and its agents as compact
  chips (lower, no role: the role is in the tooltip and the accessible name), all in the
  team's one wrapping row. The frame shows no state of the run (Flows and Agents do).
  A compact chip's accessible name, pressed state, tooltip and click are a chip's. The tooltip (the UI polish, the
  human's decision, 2026-10-03) is the UI's own (`Tooltip.tsx`, one component for the
  chips and the terminal tabs), not the browser's `title`: compact, from `AgentInfo`
  only: `name · role · provider` (the role left out when it is the name), and
  `flow <run>` on a second line when the agent works for a run; no task, no status (the
  status is in the accessible name). It shows 300 ms after the pointer enters, at once on
  the keyboard's focus (not a click's), goes when the pointer leaves, the focus goes or on
  Esc; `role="tooltip"`, the trigger's `aria-describedby` while it shows, no pointer
  events, kept inside the window. A chip opens the agent's terminal in the panel, or selects its tab. The feed
  holds, in time order: the messages with the human and the questions; the flow runs'
  gates as cards or lines (Flow gates above); their events as quiet lines grouped by run
  (Flow events in Look of the feed), the kinds shown as lines named in one list in the UI
  (`Chat.tsx`, `RUN_EVENT_LINES`; `gate_answer` is not in it, the human's move stands for
  it); and behind the switch **Show agent
  messages** (off by default, remembered in the browser) the agents' messages to each
  other. The chat shows a window of messages (Message windows above): the latest 50 with
  the human, with the switch on the latest 50 of all; the switch changes the window.
  A message's text shows as Message text in Look of the feed says. The feed takes the
  page's height and scrolls by itself, the composer under it.
- **Pages of the chat** (feature/chat-paging, the human's choice 2026-10-04: loaded by
  themselves on scroll, not with a button): gates and run events come whole, but while
  earlier messages are not loaded only those from the window's `from` on show. An unseen
  marker at the top of the feed (an `IntersectionObserver`, 200 px ahead) loads the page
  before when it comes into view, observed again after each load so a page that does not
  fill the feed loads the next; meanwhile "Loading earlier messages…" (`role=status`); a
  load that failed says why with **Retry** (`role=alert`); with nothing earlier, "Start of
  session <name> · <day>". The scroll rule: to the bottom when the chat opens or changes
  its window, and when an entry comes at the bottom while the human is there (within
  40 px); entries put in front keep what the human sees in place (the height added is
  added to the scroll; the feed has `overflow-anchor: none`). A link to a card
  (`#message-<id>`, `#gate-<id>`: Needs you, a late reply's line, the hint over the
  composer) scrolls to it; a card before the window is loaded up to in one request (a
  message by its id, a gate by its time), then scrolled to; one that is still not there
  (a message the chat does not show) scrolls nowhere.

### Launch and session control (decided 2026-10-04, task feature/launch)

The human starts, stops, resumes and forgets sessions from the browser. The server calls
the same core functions as the CLI (`runtime.start_session`, `stop_session`,
`forget_session`), so the decisions and their texts are the core's; the UI shows them.

- **New session window** (`Launch.tsx`, a modal `<dialog>`; the rail's Launch and the
  list's "+"): **Where** is a folder only for now (the request's `where` is
  `{kind: "folder", path}`; another kind is refused, so Projects can add theirs). The path
  is typed (`~` allowed, a relative path refused), and checked by `GET /api/folders`:
  under the field "✓ git repository · branch X", or the core's reason from
  `runtime.check_repo` (does not exist, not inside a git repository, no commits yet), and
  Start stays off until it will do. Subfolders are suggested from the folder up to the last
  `/` (the arrow keys and Enter pick one), with chips of the **recent** folders
  (`/api/folders/recent`: the folders of past sessions, latest start first, at most 10).
  **Name** is the folder's default (`default_name`, the core's `slug`) with what the server
  says of it (`name_state`): taken by a running session, by a session of another folder,
  or a stopped session of this folder with **Resume it**, which turns the window to Resume.
  **Kits** (chips, "+ Add kit" from `/api/kits?where=`: the kit of each name the lookup
  takes; one that does not load is listed off with `lado kits check <name>`),
  **Provider** (`/api/providers`: each provider of the registry with
  `doctor.provider_status`; "checking…" while the CLIs answer, one not installed is off,
  a version warning shows under it) and **Permission mode** (the provider's modes; a mode
  the new provider lacks goes back to `default`, and the window says so). Kits and mode
  of a new session come from the folder's last session ("from the last session of this
  folder"), else LADO's defaults; only the UI does this, `lado start` is unchanged. No
  provider is the default (task feature/no-default-provider, 2026-10-05): the provider is
  the folder's suggestion (`FolderInfo.provider`, the core's rule that `lado start` uses
  too: the folder's last session's if installed, else the only one installed) with its
  reason in `lado start`'s words under it ("from the folder's last session", "the only
  one installed"); without a suggestion none is chosen ("choose…", "choose the agent CLI
  for this session") and Start stays off until the human picks one; a suggested one that
  is not installed stays off too, with its install hint. The human's own pick is kept
  when the folder changes. **Advanced** (folded): the `--without` items, `kind:name` or `kind:name@kit`
  (placeholder `agent:reviewer@kit-b, skill:style`). Start shows "Starting…" with
  the fields off; a refusal is shown whole (`role="alert"`) and the window stays; a name
  taken (409, `Taken`: its status and folder) offers Resume it for a session of this
  folder. A start or resume the kits refuse is 400 `Refused` (`message`, `switch_off`):
  for a name in two kits, one button per item ("Switch off reviewer of kit-a", "… of
  kit-b") adds it to the Switch off field and opens Advanced; Start starts again. The
  window does not yet show who will lead the session (BACKLOG). On success the window closes and the session's Activity opens; the `Started`
  answer's `problems` (open runs that cannot go on), its `warnings` (what `lado start`
  prints on stderr: kit supervisors not used, what the supervisor's CLI asks the human
  before its first hook, such as Claude Code's "trust this folder?") and a resume's
  `changes` show under the session's head until closed. No first message, no tmux attach.
- **Resume** is the same window in its Resume mode: Where and Name fixed, kits, provider,
  mode and Advanced filled from the session (`SessionInfo` carries its settings) and
  changeable; it sends only what changed (`POST /api/sessions/{name}/resume`).
- **Actions by status** (`SessionControl.tsx`; task feature/session-controls, 2026-10-05:
  a Stop in the list row was too easy to hit), only in the session's head, as icons with a
  tooltip and the same accessible name (Stop a square filled with the text's colour, dark
  in the light theme and light in the dark one; decided 2026-10-07,
  feature/activity-team): running and `loop_down`: Stop session…; stopped:
  Resume… and Forget… (in the colour of a dangerous action); `tmux_gone`: Resume… and Stop
  session… (which marks it stopped). The head has no ⋯. Before them **Copy link** (a link
  icon) copies the session page's address as the list row's Copy link does, and on the
  head's second line **Copy path** its folder (Structure, above); both say what was copied
  ("Link copied", "Path copied") under the button for 2 s, or show the text selected when
  the copy fails. Copying is one module, `Copy.tsx`, for the head and the row's menu.
- **The list row's menu** (`SessionRowMenu.tsx`, on the shared `Menu.tsx`): ⋯ holds
  actions on the entry only, and only ones that work now; no placeholders for features
  that do not exist (no Rename, Pin or colour until they do). **Copy link** copies the
  session page's address (`location.origin` + its path), says "Link copied" in the row
  (`role="status"`, outside the menu, which closes) and goes after 2 s; without the
  Clipboard API (the page not on localhost or https, e.g. `--host` over http) or when the
  copy is refused, a popover shows the address selected with "Press ⌘C / Ctrl+C to copy".
  **Open in new tab** is a link to the same page (`target="_blank"`, `rel="noopener"`).
  The address has no token: the login is the browser's cookie, so another browser gets
  401 and the Shell's message to open the login link. In a future desktop app (Stage 7) a
  webview may open a new tab in the system browser, without the cookie; the Desktop stage
  decides.
- **Stop** asks in a popover by its button: `Stop session "<name>"?`, what it does from
  `stop-preview` (its agents are closed, the messages they did not get are dropped,
  branches, worktrees, open runs and the history stay, it can be resumed) and the button
  `Stop <name>`; the name is in the request's address. The page stays on the session.
- **Forget** asks in a modal window: the history is deleted for good, the worktrees and
  branches left on disk (`forget-preview`), and with open runs a box to tick
  ("Also forget its N open runs (…)") before `Forget <name>` can be pressed. After it,
  `/sessions`.

### Session head (decided 2026-10-07, feature/session-head)

- The head's second line, left to right: where (the folder, then its git: the origin
  remote short, `github.com/ladohq/lado`, without scheme, user and `.git`, and `· <branch>`),
  the kits, the CLI · permission mode. The git icon is Copy URL (the whole remote, "URL
  copied"), and its tooltip has the whole URL, the branch and the path. Without a remote
  only the branch shows, without either no git fact.
- Versions are in tooltips (the UI's `Tooltip`, never a `title`), on each kit's name:
  `<name> v<version>`, where it is (`Kit.source`, as `lado kits` says it), "installed now:
  the next agent starts with it"; a kit not found or not loading shows why. On the
  provider's name: `<title> <version>`, with an untested version also `tested with
  <tested>` and an orange `!` in the line (`var(--human)`, named "untested version"), as
  `lado doctor` warns; a CLI not installed says so. The versions are the ones installed
  now, which the next agent starts with; a version per agent is not kept.
- They come from `GET /api/sessions/{name}/about` (`SessionAbout`), not from
  `SessionInfo`: git, `<cli> --version` and loading kits are too dear for the change feed,
  and no table of lado.db holds them. It is asked when the head opens, when the feed
  changes the session's `repo`, `kits` or `provider` (a resume), on any change of kind
  `kits` (an install, update or remove) and after a gap in the feed. No event says the
  CLI's version changed: it is read again only when the head opens. Until the about comes,
  or when it fails, the line has the session's settings alone, with no error.
- The remote reaches the API only through `runtime.public_remote`: no userinfo for a URL
  scheme but ssh (a token alone too), a password dropped from `ssh://`, the scp form and a
  local path as they are.
- `repos` is a list, one item now (the session's folder). A project (ROADMAP Later:
  Projects) takes the place of the folder and git: its icon, its name and "N repositories
  ▾", which opens the list, each with path, remote and branch in the same form; kits and
  CLI stay where they are.
- Known limit: the server finds the CLI on its own PATH (`shutil.which`), as
  `/api/providers` and the folder check do; agents get their login shell's PATH, so the
  version shown may differ from theirs.

### Notifications (decided 2026-10-03, task Needs you and notifications)

So the human can work from the browser without watching tmux. The tmux popup stays as it
is; there is no sound and no notification outside the browser.

- **Off by default.** Turned on by **Enable notifications** on Needs you or the switch
  **Browser notifications** in Settings (`lado.notifications` in the browser), each of
  which asks the browser's permission (`Notification.requestPermission()`) and turns them
  on only when it is granted. Turned on but no longer allowed, a browser that blocks them,
  one that has no notifications and a page that is not a secure context are each said in
  words, with what to do.
- **The notifier** lives in the shell, so it works on every page. While notifications are
  on it watches the live store's `waiting` and keeps, for the tab's life, the keys it has
  seen (across the feed's resets): the items of its first list are only remembered; each
  later new key, also one in place of another at the same count and one that came during a
  gap in the feed, gives one notification, only while the tab is not on the screen
  (`document.visibilityState`). An item seen while the tab was shown is not notified later.
- **A notification**: `silent`, `tag` = the item's key (several LADO tabs show one), title
  `LADO · <session>`, body the gate's question, the agent's question, `<agent> waits:
  <reason>` or `<agent> waits for you in its terminal`. A click focuses the tab, goes to the
  item (its card in the chat, or the agent's terminal) and closes it. An item that leaves
  the list (answered anywhere) closes the notification this tab made for it. A notification
  the browser refuses to show is said on Needs you and in Settings.

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
      After it, work moves to the chat (with the release that ships it). Done: The human
      in the session above.
   4. **Layout**: the team chips above the chat, the selected agent's terminal on the right
      instead of the bottom panel (the chat then takes the page's height: now its feed is
      sized to leave room for the panel under it), flow transitions and agent-to-agent
      messages (behind a switch) in the feed (`GET …/messages` without `with`), the session
      list's "+" and its stopped sessions folded. Done: Structure and The human in the
      session above.
   5. **Gates**, in two parts:
      1. **Gates in the chat**: gate cards in the chat, answered from the browser; the popup
         and `lado answer` notice an answer given elsewhere. Done: Flow gates in The human
         in the session above.
      2. **Needs you and notifications**: the Needs you page with its count in the rail,
         browser notifications. Then a release (0.12.0 shipped the chat): the human can
         work from the browser, tmux stays the fallback. Done: Needs you in Structure and
         Notifications above.
   6. **Launch and session control** (decided with the human 2026-10-03, after Needs you):
      start a session from the UI (Launch, the session list's "+": repo, kit, provider,
      permission mode), stop, resume and forget one; guarded like the composer (token and
      Origin). Done: Launch and session control above (a typed path checked by the
      server, with subfolders and recent folders).
   7. **Flows** (decided with the human 2026-10-04, task feature/flows-tab). Done: Flows
      below. Then **Agents** (decided with the human 2026-10-04, task feature/agents-tab).
      Done: Agents below. Then Providers and environment; a pass over the look with a designer role
      (BACKLOG), with it the rework of the rail (later, with the look pass: names under the
      icons when collapsed; Launch moved onto it with Launch and session control); then the
      rest; later the desktop app.

### Providers and environment

Settings: the agent CLIs LADO can run, their versions and logins, and what `lado doctor`
checks.

### Activity

A session's tab: the chat with the human (The human in the session, above), flow
transitions as they happen, agent-to-agent messages behind a switch; the team as chips;
the selected agent's terminal on the right. Built (Layout task); the notes of each step
are in Flows.

### Agents

A session's tab: its agents and what each does (decided with the human 2026-10-04, task
feature/agents-tab; built in `web/src/Agents.tsx`). The human sees each agent and acts on
it here instead of `lado ls`, `list_agents` and `lado finish`.

- **API**: `AgentInfo` (REST and the feed) carries `branch` and `worktree` (a worker's;
  none for the supervisor), `spawned_at` (its latest `spawned` event) and `since` (when it
  got its status: `state.agent_times`, the same rule, `STATUS_EVENTS`, as `lado ls`).
  `GET …/agents/{agent}/details` (`AgentDetails`): the whole task and `work`, where its
  work stands in git now (`runtime.work_state`: branch, base, ahead, behind, uncommitted
  paths, last commit), or `work_problem` when git cannot tell; both none for an agent
  without a branch (the supervisor). Not in the feed: git is asked on each request.
  `GET …/agents/{agent}/finish-preview` (`runtime.finish_preview`: whether the
  worktree goes, why the finish is refused, the work) and `POST …/agents/{agent}/finish
  {discard}` (`runtime.finish_worker`, under `Guard.changes`; a refusal is 400 with the
  core's reason). Finish and the UI's dialog go by the same preview: the UI has no rules
  of its own about runs.
- **The list** (left): the supervisor first, then the live agents by spawn; a
  row: status dot, name, `status · since`, and the run with its state, or the first line
  of the task; an agent in `waiting` is orange with the first line of why, an agent in
  `stopped` whose process ended by itself shows the first line of why it stopped
  (`AgentInfo.status_reason`, `runtime.status_reason`: its `ended` event). Only live
  agents: what an ended worker did is in Flows (step notes and who reported them),
  Activity (messages filtered by agent) and `lado log`. The tab is **Agents · N**, N the
  live agents. A List and page (Structure): the search finds an agent by name, role, task
  and run. On a narrow page
  the facts' names stand above their values and Write takes the page's width.
- **An agent's page**: the head (name, role, provider, status and for how long, when it
  was spawned, for which run and step with the visit, from the run in the store), Open
  terminal, **Write to <agent>** (the Activity composer with `to` fixed; the supervisor
  gets a one-line copy from LADO of what the human writes to another agent, How agents
  talk in AGENTS.md) and **Finish…** (not for the supervisor); why it waits, or why it
  stopped ("Stopped: <reason>", its way out is Finish…); Branch,
  Work (asked when the page opens, when the agent becomes idle and with Refresh; "as of"
  its time; no polling), Worktree, Task (first lines, Show more); its latest 10 messages
  from and to it, only in its lifetime (a name is used again: one request,
  `agent=<name>&since=<spawned_at>&limit=10`; the server and the feed's rule filter, the
  page does not), and
  **All in Activity**, which turns Show agent messages on.
- **Finish…** asks in a dialog with what the preview says: the branch and worktree go,
  or, for a worker of a run that keeps its worktree, only its window closes. A refusal
  shows its reason and **Discard work…**, which asks again with what is lost (commits not
  in the base, uncommitted files) and a red **Discard and finish**.
- An agent that is not live: "Agent <name> not found".
- `/sessions/<name>/agents` opens the supervisor in a wide column, the list in a narrow
  one. A stopped session has no agents (`lado stop` forgets them): its tab says "Session
  stopped: no agents" and nothing else.
- In Flows, who acts in a run's head and who reported a step link to the agent's page
  while the agent lives.
- Not in it (later): spawning a worker from the UI, changing an agent's model or mode,
  polling git.

### Flows

A session's tab: its flow runs, their state, who acts and the notes of each step (decided
with the human 2026-10-04, task feature/flows-tab; built in `web/src/Flows.tsx`). The human
follows a run and answers its gate here instead of `lado ls`, `lado log` and `flow_status`.

- **A step is a note.** Each transition (`flow_advance`, a gate's answer, `lado
  flow-set`) writes exactly one note in its own transaction (`state.update_run`); from
  schema 15 the note also keeps who reported it (`actor`), the `outcome` and the state it
  leads to (`target`): the record of the step, one source of truth, to which artifacts
  can later be attached. A flow-set has no outcome (actor `human`); a loop limit's answer
  is an `override` with the outcome `continue`. When a loop limit kept the run out of
  `target`, the run waits before it at a loop gate, and the next note is that gate's
  answer. Notes from before schema 15 have these fields empty and show their state and
  summary only. A run's start, end and cancel are its events (`flow_start`, `flow_end`,
  `flow_cancel`), shown with their `detail` as the core wrote it.
- **API**: `GET /api/sessions/{name}/runs` (`RunInfo`, newest first: state, status,
  reason, `acting` from `runs.acting`, visits, the open gate's id, worktree, branch,
  language, `since` and, for a closed run, `ended_at`, both its latest event, and `states`,
  the flow's states in the order of the run's snapshot, `FlowStateInfo`) and
  `GET /api/sessions/{name}/notes` (`NoteInfo`, every note of the session, oldest first,
  with run, kind, actor, outcome, target). The feed's `runs` and `notes` changes carry
  these items. Who acts in an open run depends on the session's agents, and the agent
  that was a run's worker may be deleted already: so any change of a session's agents
  also updates every open run of it (`feed.ALSO`).
- **The redesign** (decided with the human 2026-10-05, task feature/flows-tab-redesign;
  mockup https://claude.ai/artifact/5G2wDV6kx6uyWNZTbyHo4S, version 2, variant "Feed"):
  all runs always seen in two groups, and a run's page that shows first where the run is
  and what it waits for, its history behind one line per event.
- **The overview** (decided with the human 2026-10-07, task feature/flows-list-states;
  mockup `.lado/mockups/flows-list-states/overview.html`): the human sees where each
  active run stands without opening it. A flow's states do not fit a 240–300 px list, so
  the tab is no List and page any more: `/sessions/<name>/flows` shows the overview across
  the whole column at any width, never redirected to a run, in a region that scrolls by
  itself (the window does not). Two groups, each folded and opened by its heading
  (`GroupHead` with `fold`), remembered in the browser (`lado.flowsGroups`, `{ active,
  history }`, each `open` or `folded`; `prefs.storedGroups`, the one rule of every list's
  groups: a value not one of the two is the default), Active open and History folded by
  default:
  - **Active** (green, `done`, as the session list's Running), the runs that wait for the
    human first, then the active ones ("No active runs" when there is none), each a card,
    a link to its page: the name (mono), "Waits for you" only when it waits (the card
    orange), on the right flow · kit · `started <time>`; the line of what goes on now
    (state · `→ <who acts>` or `gate #N` or its reason · how long); then its flow's states,
    the run head's chips (the same component, `States`), or "Flow cannot be read: …" for a
    run with a `problem`. No task on the card.
  - **History** (neutral), ended and cancelled runs by when they ended, the latest first,
    under their day, the first 10 and then Show N more ("No ended runs yet"): a compact
    row, the name, its status and time; no states, no task.
  The tab is **Flows · N**, N the open runs (none: Flows).
- **The search** of the overview is in the session's tab bar, not above the list: a
  magnifier at its right end, shown when the tab has an entry in `FINDS` (Sessions.tsx;
  now only Flows, `Find a run`) and the address names no item. A click or `/` (the UI's
  first global key; not while typing in an input, a textarea, a select or an editable
  element, xterm's own textarea too) opens a field there; Esc clears and closes it, left
  empty it closes, with text it stays open. The search is the address's `?find=`: the field
  writes it in place (replaced, so typing adds no step to the browser's history), keeps the
  other parameters and drops it when empty; a click on a run is a usual step, so Back
  comes back to the overview with the same search. It finds a run by name, task, flow and
  state in both groups; while it has text both groups show open, every match, their
  headings off, what is remembered unchanged; a group with no match says "No match", and
  with none anywhere `No run matches “…”`. The open field never makes the bar scroll: it
  lies over the bar at the same right end (`.tab-find.open`, on the band's ground, the
  band's line left uncovered), beside the tabs in a wide bar and over the last ones in a
  narrow one, shrinking to the bar's width; closed, only the magnifier takes room. One
  search for every tab later takes the same place and parameter (BACKLOG.md).
- **A run's page** (`/sessions/<name>/flows/<run>`), keyed by the run, replaces the
  overview at any width, under the link back `‹ All runs (N open, M ended)`, which comes
  back with the overview's last search (the tab keeps it, and its scroll, while the run's
  page is shown; a reload of the run's page forgets it). The page stays a size container
  (`@container`).
  - **The head**: the name (mono) and a pill of its status (Active blue, Waits for you
    orange, Ended green, Cancelled grey); flow · kit, started, branch; the task's first
    line cut to one line with **more** for the whole text; then every state of the flow
    as a chip in the order the flow declares them: its name (◇ at a gate), its visits
    (`2/3` with `max_visits`, else `×2`), in its title who acts ("you" at a gate), then
    `reads <names>` and `writes <names>` of its `reads` and `produces`; the
    current state blue, orange while the run waits for the human, entered ones solid, the
    others dashed. No ways back. A run whose flow cannot be read (its `problem`) shows
    "Flow cannot be read: <problem>" there instead, its lines kept (`.problem` is
    `pre-wrap`, so is the gate card's problem).
  - **Now**, a card: an active run `Now · <how long>`, who acts as the core says it (the
    UI does not parse it; a link to the agent while it lives) · state · `visit 2 of 3`; a
    waiting run, orange, `Waits for you · <how long>` and its open gate, the chat's `Gate`
    in its compact form (title, question, comment, buttons; no note, no reads, which are
    in the history), answered in place through `answerGate` (disabled while the session
    is stopped), or the run's `reason` without a gate; an ended or cancelled run `Ended ·
    <time>` (green) or `Cancelled · <time>`, the end's or cancel's `detail` and how long
    the run took (`created_at` to `ended_at`). The chat's gate card is unchanged.
  - **History · N events**: one feed, the newest first by default; the switch "Newest
    first ↓ / Oldest first ↑" is remembered in the browser (`lado.flowsOrder`); "Open all
    / Close all". The order is the run's start, its steps by time, its end (by kind, then
    time), turned by the switch. A step's line: time, a dot (green; orange for a way back,
    a step whose `target` the flow declares no later than its state, or the human's
    answer; none is a way back without the flow), who (a link while it lives; the human
    is "you"), `<from> [outcome] → <to>` (a way back's outcome orange), "flow-set" or
    "loop limit" for an override, and the summary on one line. It opens to its facts
    (Who, From, Outcome, To, Step took: the time since the run's previous event) and the
    note's whole body as Markdown, as in the chat ("No comment." for the human's answer
    without one). A note from before schema 15 has its state and summary only. The start
    ("started the run", with its detail), the end ("ended the run") and a cancel
    ("cancelled by <actor>") are one line with a blue dot, never opened; the end's or
    cancel's detail is in Now only. What is open lives in the page and starts afresh with
    another run: at first the latest note with a body; a note with a body that the feed
    brings later opens too. All of it follows the feed: an answer anywhere moves the page
    on without a reload.
- `/sessions/<name>/flows` without a run, in a wide column, opens the first run that waits
  for the human, else the first active one, else the latest to end (the address
  replaced); in a narrow one it is the list. With no runs both groups say they are empty
  and the page is empty. An unknown run says "Run <name> not found" and the address
  stays.
- Not in it (later tasks): cancel and flow-set from the UI (they stay in the CLI),
  starting a flow from the UI, editing flows.

### Gates

Gates as cards in the session's chat (built: Flow gates in The human in the session), Needs
you (what waits in all sessions, with a count in the rail and the tab's title) and browser
notifications (built: Needs you in Structure, and Notifications). The popup still opens only
on the clients of the session's own tmux session, never on a browser's viewer; a human who
works only in the browser learns of a gate from Needs you, its count and a notification.

### Artifacts

A session's tab: the documents the agents write (ROADMAP stage 7, Artifacts). The contract
the UI part is built against: [artifacts.md](artifacts.md).

Decided with the human 2026-10-07 (run feature/artifacts-ui; mockups
`.lado/mockups/artifacts-ui/`: `tab-b.html` the tab, `viewer-types.html` the viewer,
`chips.html` in its mode "panel over the chat"):

- **The tab** (`ArtifactsTable.tsx`): a flat table over the whole column, newest first by
  the latest record (`live.ts`, `LISTS.artifacts`, kept by the feed's `artifacts` items: a
  new record moves its artifact to the top). Columns: the name (the full name, its run part
  muted, the title under it, the type's icon before it), the media type, the size, the
  author, how long ago it was updated and the latest record's summary. Above it: a search
  (name, title, summary, author), the scope (All scopes, Session, each run that has
  artifacts) and the type (All types, Documents, Code and text, Images, HTML, Other: one
  per `artifacts.kindOf`). Filters work on the loaded list; a session without artifacts
  says "No artifacts yet", a filter that keeps none "No match". The tab is a size
  container: below 720 px of its own width (the terminals open, a phone) each row is a
  card. A row opens the artifact's page.
- **The page**: `/sessions/<name>/artifacts/<id>` (`paths.artifactPath`), "← Artifacts"
  above the viewer; it shows the latest record, or with `?record=<id>` the record an
  attachment keeps. An unknown id says "No artifact <id> in this session".
- **The viewer** (`ArtifactView.tsx`, one component for the page and the panel): its head
  is the type's icon and the full name, Download (the content with `?download=1`), Copy
  link (the page's address, with `?record=` when it is not the latest), for HTML Open in
  new tab (the content address, under the server's sandbox); the title; the author, how
  long ago, the run's state or "session", the media type and size; the record's summary.
  The body by `artifacts.kindOf`: Markdown (GFM: tables, task lists, strikethrough
  with `~~`, autolinks, footnotes; no raw HTML) as the chat's `Body` (Markdown in Look of
  the feed); text and code in a table with line numbers and Wrap lines (no syntax
  highlighting: BACKLOG.md); an image fitted to the column, a click shows it at its own
  size until Esc or a click; HTML in `<iframe sandbox="allow-scripts">`, never
  `allow-same-origin`, under a bar "Runs sandboxed: its scripts work, it cannot reach
  LADO"; anything else as its facts (media type, size, SHA-256) and Download. Text is read
  through `response.body.getReader()` up to 1 MB, then the read is cancelled and the page
  says "Shown: the first 1.0 MB of …" with a Download. Content the store lost (the
  server's 500) is a red block that says so and points to `lado doctor`; another failure
  is its message. A record that is not the artifact's latest by content says
  "<full name> changed since this record: <its summary>" with Open latest, in
  `--action-ground`.
- **Chips** (`Attachments.tsx`): on a message (also one without a body: its summary and
  its chips), an agent's question, a gate card's note and a note in a run's history.
  A chip is the type's icon, the name and the size; in the chat the full name with its run
  part muted, on a gate and in a run's notes the short name (they are that run's). Its
  name for the ear: "Open artifact <full name>". It opens the record that was attached.
  When the artifact changed since (`artifacts.changed`, the one comparison: the
  attachment's hash against the artifact's latest in the session's list), "changed since ·
  open latest" is joined to it; while that list is not loaded the chip says nothing
  (`unknown`), never "unchanged". The Activity tab (chat and gates), Flows and the panel
  watch the session's artifacts for it, so a new record changes a chip without a reload.
- **The panel** (`ArtifactPanel.tsx`): a chip opens the viewer on the right over the page
  (`?view=<record>`, `paths.VIEW_PARAM`, on any of the session's tabs; from Needs you,
  over the session's Activity tab), min(620 px, 100%) wide, the whole screen on a phone,
  over a scrim; the page stays where it was. Esc, × or a click on the scrim closes it and
  the focus goes back to the chip; Back closes it too (the chip's view is a step of the
  history). "Open in Artifacts tab" leads to the artifact's page with that record. Open
  latest in it shows the latest record in the same panel.
- **A gate's note** (`GateCard.tsx`): its chips under the note before the gate, then the
  artifacts the gate reads; an artifact the note carries is left out of those
  (`runs.gate_reads`), so each shows once.
- Not in it: syntax highlighting, a record's history and a diff, uploads by the human,
  attachments in the composer, deleting an artifact, server-side filters and pages.

### Home

Later: an overview of all sessions, what runs, what is stuck and what waits for the human.

### Kits

Decided with the human (task feature/kits-page, 2026-10-05, mockups v3, layout C1): one
page for what `lado kits` and `lado marketplaces` do, instead of a Kits and a Marketplace
page (LADO has one source of kits, git).

- **Layout**: above, the time of the last check, **Check for updates** and **Add kit…**.
  Under them the tabs **Installed | Available | Updates** (in the address, `/kits/<tab>`;
  their look: Look, Tabs),
  a search by name and description and the source chips (All, each marketplace, git,
  folder, built-in; remembered in the browser, `lado.kitsSource`), which filter every tab;
  then the list. The **Marketplaces** block is on the right on every tab, under the list on
  a page narrower than 900 px.
- **Installed**: the kits of lado.db's `kits` table, then the built-in ones (read only,
  no buttons); not a project's kits (`<repo>/.lado/kits`: Launch shows them for its
  folder). A row: the name, its tag or version, `vX available` after a check, the
  description, its source (the marketplace it was added from, `<name> (removed)` when that
  one is gone, counted by the UI from the two lists; git; folder; built-in), its roles,
  skills and flows, its address or folder, the core's problem when it does not load;
  Update… (a kit from git) and Remove…. A row is a card (below).
- **Available**: each kit the enabled marketplaces list that is not installed, from their
  clones (no network): `marketplace.yaml` for the names and addresses, `index.json` for
  the rest (README, Kits: version 1), only the name and address without an entry; Install….
  An installed kit is in Installed and a new version of it in Updates, never here: the
  list and the tab's count are one set, the offers whose `installed` (the server's) is
  false, before the search and the source chips. When every listed kit is installed, the
  tab says "All kits of your marketplaces are installed", how many kits each marketplace
  lists, and links to Installed. A fresh LADO_HOME says no marketplace is fetched yet, with
  a button to update each; nothing is cloned by itself. (Decided with the human, task
  feature/kits-page-polish, 2026-10-05.)
- **Card** (variant A of that task's mockups, decided 2026-10-05): a list of rows, each a
  mark, a body and the actions on the right (under the body on a page narrower than
  600 px). The mark: the first letters of the name's first two parts (split at `-` and
  `_`; else its first two letters) in mono on `--action-ground` in `--action`, a
  built-in kit's on `--raised` in `--muted`; its colour says nothing. The body: the name,
  the version as a tag (Available: the index's `latest`), the badges (`vX available`,
  `folder missing`); the description cut to two lines by CSS, with **more** only when it
  is cut (measured, again on a resize) and **less**, the whole text on hover, not
  remembered; the source as a dot with its text (the dot by its kind: official `--done`,
  another marketplace, also a removed one, `--action`, git a `--muted` dot, folder a
  `--muted` ring, built-in an empty circle); the counts, number first ("4 roles 71 skills
  2 flows", none of a zero); a git address short (no scheme or user, `host:` as `host/`,
  no `.git`), the whole one on hover, a folder as it is. Update… is the primary button
  only when a check found a newer version.
- **Updates**: only after Check for updates (`kits.outdated`, the network); the time of
  the check is kept in the page, not stored; no check in the background. The kits it did
  not check say why; a moved tag is a warning.
- **Freshness**: the installed kits and the marketplaces are items of the change feed
  (`kits`, `marketplaces`, session `''`), so a change from the CLI shows without a reload;
  Available is asked again whole when either changes. Each item holds only its own row and
  files (`InstalledKitInfo`, `MarketplaceInfo`): who uses a kit is asked when it is
  removed (`GET /api/kits/{name}/remove-preview`, `runtime.kit_users`).
- **Install**: Add kit… asks what (a kit of a marketplace, with the names it lists as
  suggestions; a git address; a folder; a version and pre-releases), then shows the core's
  plan (`POST /api/kits/plan`: `kits.plan_add`, the kit cloned into the cache, nothing
  installed) in the windows' frame (below): the source and `Install <name> <tag>` in the
  head; the description, warnings, three tiles (roles, skills, flows), roles and flows by
  name, the skills behind "Show all N", the MCP servers with their commands, the address
  and commit. When the core says `needs_confirmation` (not the official marketplace, as
  the CLI asks), a warning about its MCP servers and **Install** only after "I checked the
  address and the MCP servers". Install sends the plan's tag and commit (a folder: its MCP
  servers); the server plans again and refuses another one with 409, and the window offers
  the plan again. Install… on an Available row starts at the plan. A refusal of the core
  shows its words with Back.
- **Update**: the core's plan for the latest version or another one chosen from the
  repository's tags (`POST /api/kits/{name}/plan-update`). Decided with the human
  (feature/kits-page-polish, 2026-10-05, the "No update" window and D1):
  - Nothing to update (`current`): a short window, no contents: "<name> is up to date"
    with a check mark (or "<name> is at vX already" when a newer version exists), the
    latest version and the source, the core's warnings, "Install another version" and
    Close. This says what the core's `current_line` says. Choosing another version makes
    it the update window.
  - An update (D1): the head `Update <name> · <source>` and `vOld → vNew` (with `latest`);
    the new MCP servers by name and the core's warnings first; the tiles with `+N`/`−N`;
    roles and flows as chips, the added ones green "+ name", the dropped ones struck red;
    the added and dropped skills, all of them behind "Show all N"; the MCP servers, "new"
    only by the core's `new_mcp` (as the CLI warns), "removed" only from `before`; "Who
    gets it", the core's line; the address and commit. The footer: the version, Cancel and
    "Update to vX".
  - `PlanInfo.before` is the installed version's roles, skills (its own and its packs'),
    flows and MCP servers (`kits.Install.before`), null for an add and when that version's
    clone or one of its packs is not in the cache: a partial list would show its missing
    skills as added. Without it the window marks nothing but the new MCP servers and says
    "The installed version's files are not in the cache: changes are not shown."
- **Windows**: every window of the page has its head and its footer with the buttons in
  place and only its middle scrolling, at most the screen's height less 32 px, so a kit
  with 70 skills never pushes the buttons off the screen. Its styles are only under
  `.kits-dialog`; the other pages' `.question-dialog` stays as it is.
- **Remove**: never blocked: the window names the running sessions that use the kit
  (their new agents and runs fail to start) and the stopped ones (a resume needs it), the
  core's lines, as `lado kits remove` prints them; a kit whose folder is gone is only
  forgotten.
- **Marketplaces**: each with enabled (a checkbox), its address, when it was updated, how
  many kits it lists and its problem (not fetched, a list or `index.json` LADO cannot
  read); Update all (one that fails shows its error and the others go on,
  `marketplaces.update_each`), Remove (never the official one; the window names its
  installed kits, which stay), Add marketplace….
- **Server**: every request that changes something or goes to the network is under
  `Guard.changes` (plan, install, plan-update, update, remove, check-updates, and adding,
  enabling, removing and updating marketplaces); the lists never make lado.db nor clone.
  While a request runs, the window's buttons are disabled and Esc does not close it.

## Look

A first exploration of whole screens (2026-10-03) was not approved as a layout; only its
colours were: a light, calm ground (#F6F7F9, panels #FFFFFF, lines #E3E6EB, ink #16181D,
muted #5B6270), blue for actions and links (#1F5FD6), and orange only for what waits for the
human (#B4530F on #FDF1E6); IBM Plex Sans and IBM Plex Mono. Each section's mockups are made
and approved in its own task; this file keeps what was decided from them.

Fonts (decided with the human 2026-10-07, task feature/chat-message-text, mockups
`/Users/kao/Projects/lado/.lado/mockups/chat-message-text/fonts.html`, column B, and
`ui-font.html`, variant 1): **Inter** for the whole UI (`--sans`; `@fontsource/inter`, 400
and 600, every subset, Cyrillic too) instead of IBM Plex Sans; **IBM Plex Mono** for code
and terminals (`--mono`). Both are bundled, no font from the network; `make dist` checks
that the wheel has Inter's 400.

The dark theme (task 2): ground #111317, panels #181B21, lines #2A2F38, ink #E8EAEE, muted
#9AA1AD, actions #6FA0FF (labels on them #111317), waiting for the human #F0A25A on #3A2A1C.
Both themes add a raised ground for hover and the current item (#EEF0F4 / #20242C), and
(Flows, 2026-10-05) green for work that went well, a run that ended and a step of its
history (#1E7A46 on #E7F4EC / #5CC98A on #18301F); since task feature/session-list-groups
green (`--done`) also means what works now, the session list's Running group, and since
task feature/flows-list-states (2026-10-07) the Flows overview's Active group. (Kits, 2026-10-05) A quiet ground for the action
colour, a kit's mark (#E8EFFC / #1C2840). A kit's source dot: official `--done`, another
marketplace `--action`, always beside the source's text. Every
text colour has a contrast of at least 4.5:1 on its grounds in both themes; a unit test
(`web/src/tokens.test.ts`) checks it.

**Avatars** (task feature/chat-look, 2026-10-07; Look of the feed): six colours,
`--avatar-1` … `--avatar-6` (indigo, green, violet, magenta, teal, olive; light #4F5BD5,
#1F7A5C, #8A4FC7, #B23A78, #0E7490, #6B6B1F with a white letter, dark #9AA6FF, #5CC9A0,
#C49AF0, #F08CC0, #5CC4E0, #C8C56A with a #111317 letter, `--on-avatar`), one chosen from
the agent's name by a hash, so an agent keeps its colour; none is orange or the action's
blue. The human's avatar is "Y" on `--action` (`--on-action`), a gate's a flag in
`--muted` on `--raised`. A known limit: roles with the same first letter (`developer`,
`designer`) differ only by colour, and with six colours that may be the same; the full name
stands beside it. Orange stays only for open questions and gates and the gate hint.

**Artifacts** (feature/artifacts-ui, 2026-10-07): a type's icon is a 28 px tile (20 px on a
chip) on `--raised`, coloured by kind: Markdown `--action` on `--action-ground`, HTML
`--avatar-3`, images `--avatar-2`, text and code `--avatar-5`, anything else `--muted`. A
chip is 30 px high, a `--line` frame on `--panel`, `--action` on hover; "changed since ·
open latest" is joined to its right on `--raised` with a `--action` dot (below 600 px under
it). The panel is `--panel` with a shadow (`--shadow`) over a scrim (`--scrim`); an image
at full size over `--lightbox`; an HTML frame's ground is `--frame-ground` (white, as a
page without a background). Orange is never an artifact's.

**Time**: every time of day in the UI is written in 24 hours (`clock()`, `hourCycle:
"h23"`), whatever the browser's locale.

**Tabs** (decided with the human 2026-10-06, task feature/session-tabs, mockup
`.lado/mockups/session-tabs/index.html`, variant F "folder tabs"): every tab bar of the UI
has one look, the terminal column's type, from one set of rules in `styles.css` (each place
keeps its own markup: links in a `nav`, or the terminals' `tablist` with ×). `.tab-bar` is
the band that holds and scrolls the tabs: `--raised`, from edge to edge of its column (the
session's through `--main-pad`, the same variable as `.session-main`'s padding), a 5 px
ground above the tabs. `.tab-item` is the framed tab: IBM Plex Mono 13 px, `--muted`
(`--ink` on hover), an icon (14 px) or the status dot on its left, a transparent 1 px frame
on three sides rounded 6 px at the top. The selected one, by `aria-current="page"` or
`data-active` (one selector), is `--panel` with a `--line` frame, `--ink` 600, its icon
`--action`, and a 2 px `--action` line along its top drawn by `::before`. The band's line
is an inset shadow (`inset 0 -1px 0 var(--line)`), painted under the tabs, so the selected
tab's ground covers it; no `border-bottom`, no negative margins, no band that scrolls up
and down. A count is `.tab-count` (Mono 11 px on `--panel`), its accessible name kept
(`Agents · 3`, `Installed 3`). Where: the session's sections (with their icons: Activity,
Agents, Flows, Artifacts), the terminal panel (the wrapper of each tab with its × is the
`.tab-item`; the pinned supervisor's tab is opaque and draws the line itself, its divider
a shadow) and Kits (no icons). A new tab bar takes these classes; a UI test
(`tests/ui/test_tabs.py`) compares the three places in both themes.
