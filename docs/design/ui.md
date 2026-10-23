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
  `released`, `checked_at`, `error`; `running`, an update holds `update.lock`;
  `can_update` and `why_not`, from `self_update.refusal`, the CLI's too; `by_hand`, the
  commands without an installer, empty in a container; `container`,
  `update.in_container`; `last`, the latest `update-result.json`) gives what the
  daily update check found (`lado.update.check`, the rule `lado ls` and `lado doctor`
  share; a plain `def`, so its look at PyPI holds up no other request). Asked each time the
  change feed opens; a newer version marks `live` (System panel, below); no line under the
  top bar. `POST /api/update/check` (under `Guard.changes`: it goes to the network) looks
  now, past the day's cache (`check(force=True)`). `GET /api/update/plan` is the plan
  `lado update` prints (`UpdatePlan`, `self_update.plan`; 409 when no version is newer; a
  plain `def`). `POST /api/update {to}` (under `Guard.changes`) starts a detached `lado
  update --yes <to> --id <id>` of the server's own LADO (`self_update.start_detached`,
  its own process group) and answers 202 with that id, the time and update.log's path; 409
  when `refusal` says no (asked first, before PyPI) or `to` is not the plan's version. The
  update stops this server
  within seconds and starts it again, on the same host and port. `GET /api/health` has
  `started_at`, the server's start, kept in its memory only: a restart shows also when the
  version stayed the same (a rollback). `GET /api/system` (`SystemInfo`) is the system
  panel's facts (`doctor.system_info`, from what `lado doctor` checks) and `report`
  (`doctor.report`): Markdown to paste into an issue, with no server address, home path,
  repository path, session name, token or message, only "open to the network",
  "loopback only" or "in a container" and "LADO_HOME set" or "default home".
- Host (decided 2026-10-04): 127.0.0.1 by default; `--host` takes any IPv4 address or name
  (`lado server`, and `lado ui` for a server it starts), e.g. `0.0.0.0` to open the UI of a
  remote host from another machine. An IPv6 address is refused (not supported yet). A
  non-loopback address prints a warning on stderr (so in `server.log` too) that the server
  is open to other machines and the token travels unencrypted: plain HTTP, a risk taken
  knowingly until TLS and a real login come. What the server reports is decided by the
  address it took (`run.Listening`): a loopback one is reached by itself, `0.0.0.0` locally
  on `http://127.0.0.1:<port>`, another address by itself. From other devices (the link
  of Open on another device, below; decided 2026-10-18, LAD-94) one rule, the
  share-access spec's table: `LADO_PUBLIC_HOST` when set (a host name or IPv4 address;
  another value warns at the start, `lado: warning: LADO_PUBLIC_HOST is not a host name or
  address: …`, and counts as unset), else for `0.0.0.0` this machine's address in its
  network (`run.network_address`: the source address of a UDP route, found at each answer;
  without one the hostname), for another address that address, for loopback none. Both
  settings come only from the server's environment, nothing is kept on disk.
  Only a busy port (`EADDRINUSE`) moves on to the next one (for `0.0.0.0` also one busy on
  127.0.0.1: macOS would let both take it, and the local link would reach the other); an
  address not on this machine,
  a name that does not resolve or a port it may not take is an error `cannot listen on
  <host>:<port>: <reason>`. `lado ui --host H` while the server listens on another address
  (names resolved: `localhost` is 127.0.0.1) is an error naming its address; without
  `--host` it takes the running server wherever it listens, and for a non-loopback one
  prints the warning and, after the local link, `From another machine: <link>`, the link
  the server gives (`GET /api/access` with the token, so the server's environment decides,
  not the shell's; an older server without it: no line). The
  restart of a server of another version keeps its host and port. In a container
  (`LADO_CONTAINER`, decided 2026-10-14, LAD-63) the address does not decide who reaches
  the server, the port's publication does, which the container learns only from
  `LADO_LISTEN` (compose publishes the port on it and passes it in, LAD-94): a non-loopback
  one prints the warning naming `LADO_LISTEN:<port>`, a loopback one nothing; unset or not
  an IPv4 address, a note (`lado: note: ...`, `run.CONTAINER_NOTE`, also in `server.log`)
  naming the address inside the container, that the publication decides
  (`127.0.0.1:<port>:<port>`: this computer only), and that a link published to other
  machines carries the token unencrypted. The container cannot learn the host's name:
  `LADO_LISTEN=0.0.0.0` without `LADO_PUBLIC_HOST` has no link (`no-address`). `lado ui`
  there opens no browser: it prints the local link (with `--no-open` that one line only,
  the `From another machine` line then on stderr) and, without `--no-open`, `Open it in
  your browser on the host.`; the issue report's server line says `in a container`.
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
  `lado server --new-token`, or in the running server by `POST /api/access/new-token`
  (`Guard.changes`; LAD-94), swapped in the `Guard` at once (`Guard.renew`). An empty or
  whitespace-only file counts as missing and gets a new token, and the file is written
  atomically (a temporary file in `LADO_HOME`, then a rename: a reader sees the old token
  or the new one), so a failed write (a full disk) leaves the old file and stops the command
  with `cannot write the UI server's token to <path>: <reason>`; an empty token (Bearer,
  `?token=`, cookie) is always 401. After a new token every open event stream ends
  (`Hub.end_streams`) and every terminal socket closes with 4500 (`terminals.close_all`),
  so each reconnects and is checked against the token its browser has (a stream or
  terminal checked before the swap checks again once subscribed or registered, so none
  escapes); the answer sets the asking browser's cookie and is the new `AccessInfo`. Others
  get 401, a terminal 4401. `GET /api/access` (under the token, `no-store`, no CORS) is
  `AccessInfo`: `link` (`http://<address>:<port>/?token=<token>`, or null), `reason`
  (`loopback`, `no-address`, `unknown`), `port`, `container`, `listen` (`LADO_LISTEN` in a
  container) and `note` (the container note for `unknown`); without a link it holds no
  token. The link `<url>/?token=<token>` (`url` from server.json) sets the
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
  New session window makes (`GET /api/folders`, `/api/folders/recent`,
  `/api/repos-folder`, `/api/kits`,
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
  reads it in a thread), which raises `NoTerminal` with the reason when there is none (unknown agent, session stopped, window gone; later an agent over ACP).
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
  still has no terminal is not asked again until it changes. Reconnect always opens in
  view. The reason shows once: the error frame the server sends before such a close is
  not shown again as a notice beside it (a notice with another text still shows).
- **Connection** (task feature/terminal-control-bar, 2026-10-11): the bar names the
  socket's state only while it is not open: `connecting…` and `reconnecting: <reason>`
  with a small turning ring (still under `prefers-reduced-motion: reduce`), `closed:
  <reason>` with Reconnect. While it is open the status (`role="status"`, kept in the page)
  is empty: no `live`, which is the change feed's word in the top bar. `.term` carries
  `data-link` (`connecting`, `open`, `retrying`, `closed`). **Take control** is disabled
  (`No connection to the terminal yet`) while the socket is not open, and gone when it is
  closed for good.
- **Modes**: every terminal opens in view, the supervisor's too (the Layout task: the human
  writes to agents in the chat, and a window is never resized without the human's own
  step); **Take control** asks first in a modal dialog (`<dialog>`, Esc is Cancel) with
  **Don't ask again**, remembered in the browser (`lado.askControl`) for every agent; there
  is no setting for it, and the button's tooltip always has the explanation. Without
  browser storage it asks every time. **Release** goes back. Control is the state to see
  and ends by itself (task feature/terminal-control-bar, 2026-10-11; mockup artifact
  `feature/terminal-control-bar/mockup-terminal.html`, variant C, with the human's text):
  view shows an eye and `Viewing` in muted ink, Take control a keyboard; in control the
  bar is on `--action-ground` and says `You're typing into <agent>` in `--action` (on a
  narrow panel only the name is cut, the whole text in its title), Release is ringed in
  `--action`, the screen has a 2 px inset `--action` frame, and the agent's tab a keyboard
  (`In control`), seen from any tab. Blue, never orange: orange is what waits for the
  human. The panel (`TerminalPanel`) is the one owner of which agents are in control; it
  goes back to view, silently and exactly as Release, when the page is hidden
  (`visibilitychange`), when the panel is folded, when its tab is closed, after 10 minutes
  without input to it (`IDLE_MS`; any data the terminal sends in control, from Take
  control on), and when its socket goes from open to retrying or closed (not while the new
  control socket connects). The Take control dialog closes when the socket leaves open.
  The human's unsent draft in the agent's CLI is not covered (ROADMAP stage 8). In control tmux
  sizes the window by the client active last (`window-size latest`, tmux's default): the
  human's `lado attach` sees the window resized when the browser is the latest, and the
  other way round. In view the client never sizes it: its pty always has the window's size,
  which the server reads from tmux every second (`#{window_width}x#{window_height}`, tmux's
  state, not the screen) and sends as a new `size`; xterm.js takes it, and its font shrinks
  from 13 px until the whole window fits the panel (the fit addon tells how many cells fit);
  below 8 px the panel scrolls, kept at the bottom, where the live lines are. tmux's ignore-size flag also keeps a view out while
  another client is attached.
- **Scrolling in view** (task feature/terminal-scroll-hint, 2026-10-10): xterm.js keeps no
  scrollback, and nothing in view scrolls the agent's CLI. The wheel up first scrolls the
  panel itself while it can (a window too big for it at 8 px); once the panel is at its top
  (or has nothing to scroll), a callout under **Take control** in the bar, its arrow at the
  button, says "Scrolling works after Take control." (`role="status"`), and the button is
  ringed (`.attention`) while it shows. Each wheel up keeps it 4 s more (`HINT_MS`), never
  a second one; it closes on its timer, on pressing Take control, on another mode, or when
  another tab is shown. Esc, a click elsewhere and the mouse leaving do not close it. The
  wheel down does nothing. It replaced a read-only History layer over the terminal (tmux's
  history), which full-screen CLIs never filled. In control the wheel goes to tmux: into
  copy-mode for a CLI that does not read the mouse (visible in the human's tmux too; LADO's
  next delivered message leaves copy-mode, `tmux.send_text`), and to the CLI itself when it
  reads the mouse (its own scrolling). Only shown: statuses still come from hooks.
- **What each CLI does** (tmux 3.7): Claude Code 2.1.296 runs full screen by default
  (checked 2026-10-10: every agent window `#{alternate_on}` 1, `#{history_size}` 0, with no
  `"tui"` setting) and reads the mouse: the wheel in control goes to the CLI. Kilo 7.8.1
  runs full screen and reads the mouse too (checked 2026-10-03). The fake agent writes to
  the main screen: the wheel in control scrolls in copy-mode. Codex CLI and OpenCode: not
  checked.
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
  (one page for the kits and their marketplaces: Kits below); Report a bug (a bug icon:
  Report a bug, below) and Settings apart at the bottom. A button collapses it to icons (each with its
  name as tooltip and accessible name; the button has `aria-expanded`). The browser
  remembers the choice; a window narrower than 900 px starts collapsed. On a phone the rail
  is a drawer that Menu opens (Phone layout, below).
- **Top bar**: the page's title on the left, or on a session's page the session's head
  (Session head, below); on the right the change feed's link (`live`, or `reconnecting…`
  with the reason), with the server's address in its tooltip ("The LADO server this page
  talks to: <host>"). `live` is a button (`aria-haspopup`, `aria-expanded`) that opens the
  system panel (System panel, below); while a newer LADO is out, `↑ X.Y.Z` is beside it
  (mockup M2) and its tooltip says so. A page draws its head there through `Shell.useTopBar`, a slot of the
  top bar it fills with a portal; the Shell draws its own title only while no page claims
  the bar. Sticky at the window's top, z-index 10: over the session's splitter and the
  expanded terminals, so what drops from it (the copy notes, the Stop popover) shows over
  them, and under the narrow window's fixed terminals, the artifact panel and the
  lightbox. Its content sets its height (at least 52 px).
- **Bare pages** outside the Shell: `/view/<session>/<record>`, one record alone
  (Artifacts, The artifact's tab, below); no rail, top bar, feed or Needs-you title. A
  later bare page follows this one.
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
  small capitals and the count on the right in the group's colour, a chevron on the left;
  the Stopped band ends with a bin, Forget stopped sessions… (Launch and session control,
  below), a button of its own. The rest of the band is a button (`aria-expanded`,
  `aria-controls` naming the group's list, which stays in the page folded or not; Enter
  and Space as any button) that folds and
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
  of their group's colour on the left. Each shows a line under its name: what waits, its
  agents and run time (Running, below), its stopped text (Stopped), or its agents, the status of a session whose tmux session is gone or whose loop does not
  run, and on hover or keyboard focus of the row ⋯ with the entry's menu, Copy link and
  Open in new tab; the session's own actions are in its head (Launch and session control,
  below). On hover or keyboard focus a row shows the session's card (`SessionTip` in a
  `Tooltip`, the one of the strip's icons, below): name · status · agents, with no dot
  before the name (the row has its own) and the status word in its group's colour
  (`--done` Running, `--human` Needs you, `--muted` Stopped; tmux gone or loop down in
  `--danger`), which explains the colours of the row and the icon (decided 2026-10-09,
  mockup artifact `fix/session-tip-no-dot/mockup-tip.html`), the run time (below),
  `Needs you: <the row's line>` in the human's colour, the folder, kits · provider · `mode <permission mode>`
  when it has one, and for a stopped session `Stopped: open it and press Resume`; all
  from `SessionInfo`, no CLI commands. A Running row (a session whose status is `running`
  and in which nothing waits) also says whether its agents work now (decided 2026-10-08
  in feature/session-activity; mockup artifact
  `feature/session-activity/mockup-list.html`, variant A without the word "working"): a
  dot before its name, a full `--done` dot with a soft pulse (none under
  `prefers-reduced-motion: reduce`) while some agent works, else a ring in `--muted` (the
  team chips' busy and idle shapes), its accessible name `working` or `idle`. Its line
  says what the human can use (decided 2026-10-11 in feature/session-row-line; mockup
  artifact `feature/session-row-line/mockup-list.html`, the right column): its agents and
  how long the session ran, `<agents> agent(s) · <run time>` (`2 agents · 1 d 8 h`), the
  run time the head's, made by the one function `ranText` (Sessions.tsx; `ChatText.duration`,
  exact) and counted on by the minute on the head's clock (`useNow`, `TICK_MS`); no `of`
  count, which the dot says. A Stopped row's line is its stopped text, as its head says it
  (`stopped 5 h ago · ran 3 h 2 min`). Its card's first line says `name · running · 2 of 3
  agents working` or `name · running · idle · 1 agent`, with no time; under it, for every
  session (the strip's icons have no row line), the run time: `ran ` and `ranText` while
  the session runs (`ran 1 d 8 h`), else `ranText` as it is (`stopped … · ran …` or
  `ran …`). Its icon in the strip has the same dot,
  small, in its corner, with `working` or `idle` in its accessible name. Which mark a
  session has, and its words, is one rule, `sessionMark` (Sessions.tsx; decided
  2026-10-19, LAD-108, mockup artifact `task/lad-108/mockup-head-status.html`): stopped,
  tmux gone or loop down by its status; else needs you when something waits; else working
  or idle. The row, the strip's icon, the card and the session's head all take it. The
  group is not the mark: a session in trouble in which something waits is in Needs you,
  its strip icon `<name>, needs you`, while its head's dot says the trouble. The
  rule of working is the
  core's (`state.working_agents`, a count): the agents in `busy`, `starting` or
  `background` (its turn ended, work it started still runs; the human, 2026-10-09,
  feature/background-status) work. Its known
  limits: a Claude agent the human interrupted with Esc stays `busy` until the human's next prompt
  (BACKLOG.md), so its session shows working; an agent's planned resume after a temporary
  API error shows idle until it fires; a background task Claude Code still lists after it
  ended (killed in `/tasks`) keeps its agent `background`, and the session working, until
  the agent's next turn's end, which any message to it brings (no timer: docs/design/agents.md). The **session**
  in the middle: its head is the top bar's line (task feature/session-head, 2026-10-05; in
  the top bar since feature/session-head-topbar, 2026-10-08), then the
  tabs **Activity | Agents | Flows |
  Artifacts** (their look: Look, Tabs; its gates come as cards in the feed): Activity is the
  feed (The human in the session, below), Agents the agents and what each does (Agents
  below), Flows the runs (Flows below), Artifacts the documents the agents write
  (Artifacts below). The head, one line of the top bar, left to right: the status as a dot,
  the name (`h1`, the browser tab's title too), how long the session ran, a thin line, the
  facts (below); on the right Copy link, its actions (Launch and session control, below),
  a thin line and the feed's link. The dot is the list's mark (`sessionMark`, since
  LAD-108, 2026-10-19), with no word, its name and tooltip the mark's words: needs you
  the orange diamond of a waiting agent (`needs you · 1 question`); working the row's
  full `--done` dot with its pulse (`running · 2 of 3 agents working`); idle the row's
  `--muted` ring (`running · idle · 3 agents`); stopped `--muted`, the run time saying
  "stopped"; tmux gone and loop down `--danger`, their status in words in `--danger`
  after the name. The run time is
  the server's (`SessionInfo.ran_seconds`, `running_since`: `runtime.session_time`, stops
  and the time after its tmux died left out); while it runs the UI adds the time since
  `running_since` and counts on each minute ("2 h 14 min"); a stopped session says
  `stopped 5 h ago · ran 3 h 2 min` (from `stopped_at`), one whose tmux is gone `ran …`.
  One formatter (`ChatText.duration`) says every duration: exact to the next unit here,
  roughly (its largest unit) for `since` in Agents and Flows. The facts, small and
  quiet: Copy path (a folder icon, no other copy button), the folder in mono on one line,
  cut with "…" at its start so its end stays in view, whole in its `title`; its git remote
  and branch; the kits; the provider; versions and the permission mode in tooltips
  (Session head, below). The facts take the room between the run time and the icons, the
  folder at most half of it; facts that do not fit there go to a line of their own in that
  room (a fact wider than all of it wraps its own text), so none lies over the icons, and
  the other items stay on the top line. The name keeps a third of the bar. In a narrow
  window (up to 1100 px) the first line keeps the dot, the name,
  the run time, the icons and the link's dot (its word for the ear only), and the facts go
  to a second line of the top bar, with no sideways scrolling; only the name and the
  folder are cut. The Activity chat (its feed and composer) is at most 860 px wide and
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
  but are hidden, so nothing is resized, and go back to view (folded control is
  forgotten control, Terminal, Modes), and a panel collapsed when the
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
  widths stay remembered for a wider window. A drag captures the pointer, so it goes on
  over an iframe and ends on the release or a cancel. The artifact panel's edge is the
  same component (Artifacts, The panel), and so is the edge above the waiting card in a
  session's chat (The waiting card, Height): `edge="top"`, horizontal, a `row-resize`
  cursor, ↑ / ↓, the pointer's y, its grip's dots in a row (since LAD-54).
- **The window never scrolls** on a wide window: `html` and `body` do not scroll or bounce
  (`overflow: hidden`, `overscroll-behavior: none`) and the frame is the window's height;
  only regions inside scroll (the session list, the feed, the session's column, a page's
  content, a terminal), each without passing its scroll on. Below 900 px
  the columns stack and the page scrolls, as before.
  `/sessions` with no name says "Select a session" (nothing is selected for the human); a
  name `/api/sessions` does not know says "Session <name> not found" with a link to the
  list, and the address stays as it was.
- **Needs you** (`/needs-you`, the task Needs you and notifications, 2026-10-03): what
  waits for the human in every session not stopped (`sessions.stopped_at IS NULL`, so
  `tmux_gone` and `loop_down` count; the server and the UI apply the one rule), oldest
  first, by session, each session's name a link to its chat and beside it "In the chat"
  (also to its chat); then the session's open questions and gates as the chat's waiting
  card (The waiting card, LAD-28; before, a card per item with its own link), answered in
  place; expanded, a card fills the page's content area under its session's name line,
  the other sessions and the agents' rows hidden until it folds (LAD-48). A chip in a
  card opens the artifact panel over Needs you (`?view=<record>&session=<name>`,
  `paths.VIEW_SESSION_PARAM`; Artifacts, The panel), so the cards, their picks and an
  expanded card stay as they were (LAD-48; before, it went to the session's Activity tab
  and the picks not sent were lost); then the agents in `waiting` with their role, since when, and why (`status_reason`, or
  "waits for you in its terminal" when LADO knows no reason), with **Open terminal**
  (`/sessions/<name>/activity?terminal=<agent>`: the panel opens that agent's tab and
  drops the parameter from the address, replaced, so Back and a reload do not open it
  again; an agent the session does not have is named in a line). A notification links to
  its item in the chat (`#gate-<id>`, `#message-<id>`, `waiting.ts`): the chat shows its
  tab of the waiting card. Nothing waiting: "Nothing waits for you". The list is
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
  own: it is a tab of its session's waiting card.
- **Settings**: one page, its sections one under the other: Appearance (theme: system,
  light, dark), Notifications (the switch Browser notifications, below), Providers and
  environment (what `lado doctor` checks; a task of its
  own) and Usage statistics (below). New sections go below.
- **Placeholders**: one component, with the section's name, one sentence on what it will
  hold, and a link to the plan item that builds it. A placeholder is allowed only when its
  section has an item in ROADMAP.md or in Tasks below: they are Tasks here. Projects was
  one until step S6a (Projects, below).
- **Addresses**: `/` Home, `/needs-you`, `/sessions`, `/sessions/<name>/<tab>` (tab:
  activity, agents, flows, artifacts; without one, activity), a flow run's page
  `/sessions/<name>/flows/<run>` (Flows below), an agent's page
  `/sessions/<name>/agents/<agent>` (Agents below; another tab has no pages),
  `/projects`, a project's page `/projects/<id>` (Projects below),
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
  normal message; a dismissal is never silent, and carries what the human typed as its
  comment.
- **Flow gates** are cards in the same feed, answered through `runs.answer` (the flow engine
  opens them, an agent cannot forget to). Built (Gates task, gates in the chat): the server
  lists a session's gates (`GET /api/sessions/{name}/gates`, `GateInfo`: the question, the
  options, the note that led to the gate with its attachments and, only while it is open,
  the full names of the artifacts its state reads but those the note carries, `reads`;
  closed, `closed_by_event`, the id of the run's event its closing wrote, a `flow` move, a
  `flow_set` or a `flow_cancel`, which the core stores in the closing's transaction,
  `gates.closed_event`, since LAD-85; and `answer_attachments`, the files the human's
  answer gave the next step, the attachments of the note it kept, `gates.answer_note`,
  schema 31, LAD-86) and takes the human's answer
  (`POST …/gates/{id}/answer {option, comment, artifacts?}`, guarded like the composer,
  through `runs.answer_text`, the one text `lado answer` prints too; `artifacts` are the
  full names of the files uploaded for it, attached to the next step's note, which its
  agent reads as `Artifacts: /<name>`; at a loop limit Cancel run, which has no next step,
  sends them with LADO's message about the cancel to the supervisor; what the core refuses
  is 400 with its reason). An **open gate** is a quiet line of the feed where it opened (the flag
  avatar, "Gate #id run · state waits: <question> ↓", the time) and a tab of the waiting
  card above the composer (The waiting card, below; since LAD-28, 2026-10-13: before, a row
  of the feed with its card). The tab shows its panel (`GatePanel`, also the compact card of
  a run's page in Flows), which has no head of its own: the question, the note before the gate (its summary in bold, its body
  open, more than 20 lines behind Show more) with its chips, then under a muted "It reads"
  a line per artifact the gate reads (a chip that opens its latest record, and its "title —
  summary"; "<name>: no record yet"; the name alone while the session's artifacts are not
  loaded): the latest record comes from the feed's artifacts, so a write while the gate is
  open shows at once, and the note's chip of an artifact written since says "changed
  since" (docs/design/artifacts.md, Flows), the supervisor's recommendation (below), an
  optional comment for the next step, which takes files as the composer does (LAD-86,
  mockup `task/lad-86/mockup-gate-files.html`: the composer's frame with the paperclip at
  its left, the chips above the text, paste and a drop on the field; The waiting card,
  Fields), and a button per option (Approve / Reject, a choice gate's own options,
  Continue / Cancel run at a loop limit; the recommended one primary, else the first; on
  the tab, in its Send row), then "<n> file(s), <size>" while files are attached. A button
  uploads the files not uploaded yet, then answers with the comment and their names; a
  failed upload stops the answer, its chip red with the reason, and says "Remove it, or
  answer again to try it again"; a comment of files only is an answer too. The buttons are
  off while the answer is sent and in a stopped session (it says to resume it); a refusal
  shows on the panel. The
  tab goes only when the feed brings the closed gate, wherever it was answered
  (the popup, `lado answer`, another tab). A **closed gate** (LAD-85, 2026-10-16, mockups
  `task/lad-85/mockup-gate-comment.html` A, `mockup-gate-expanded.html` 2 and
  `mockup-gate-line.html` 2) is a folded card, 8 px left of the text's column, whose head
  is one button the card's width (`GateLine`, `.gate-head`: the panel's ground and a
  frame, `--raised` on hover): a chevron that turns up while it is open, the flag avatar,
  "Gate #id" in 600, "run · state" muted, the answer's chip (by the move that closed it:
  its direction's colour and icon, as on the move's line; without that move, `overridden`
  by `lado flow-set`, `cancelled`, or an older gate, the word on the neutral ground), "by
  you" or "by <agent>" and the time, last (LAD-136: the chevron first, as an agents'
  folded message has it; the frame reaches past the feed's edge by the head's padding and
  border, so the time ends on that edge). Its accessible name is the title sentence
  "Gate #id · run · state: <answer> by <who>" (`gateTitle`, also the title on a run's page
  in Flows), with `aria-expanded`; Enter and Space open and fold it. No comment under it,
  whoever closed it: the comment stands once, under the move it made, and an override's
  or a cancel's reason is on its event's line (before LAD-85 the comment showed under both).
  A click opens it down in the same frame (`.gate-closed-card`), read only, without the
  artifacts it read, which are not kept as they were when it was answered: the question;
  the answer in the look of the human's reply in a question's card (`.question-answer` on
  the human's ground; a gate closed by an agent `.dismissed`, on `--raised`): the small
  avatar, "You" or the agent, the chip, "→ <state>" when the move is in the feed, the time
  and the comment in full (`breaks`), then the answer's files as chips only, no previews
  (LAD-86: the card is compact, the move's line shows them); then a folded line each (`<details>`, its label in
  small capitals in a fixed column, its head cut on one line), none opened with the card:
  **Note** (the note's summary in bold, "· N artifacts"; opened, its body's first 6 lines,
  `CLOSED_NOTE_LINES`, with Show more, and its chips) and **Supervisor** ("recommended
  <option>", named as the buttons, "· you agreed" or "· you answered otherwise", the lead's
  "· disagreed with <agent>" in orange; opened, its text; without an option "Supervisor's
  recommendation"). The card stays where the gate opened, often far above the bottom; the **human's answer** is
  where it was given as one line, the run's move it made (a `flow` event of `human`), with
  the answer's comment under it and then its files, the images previewed and every file a
  chip, as the human's own message shows them (LAD-86, mockup
  `task/lad-86/mockup-feed-files.html`; files only, the files alone) (Flow events in Look of the feed; since
  feature/chat-message-text, 2026-10-07: no row of its own besides). On the open page it
  shows at the bottom as soon as the feed brings the event, and the feed scrolls to it as
  to a new message. The composer does not answer gates; no hint over it names them (the
  hint "Gate #id waits: answer on its card" went with LAD-28: the waiting card stands
  there).
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
  The human's text: its first line, cleaned of hidden characters (`lado.text`: control
  characters, tabs and line or paragraph separators made spaces, format characters such
  as bidi controls and zero-width spaces removed, but the zero width joiner), is the
  summary, cut to 200 characters with "…"; the whole text is the body when the summary is
  not exactly it (more lines, cleaned or cut); over 8000 characters it is refused. It goes
  through the queue, confirmation and retries like an agent's; if it fails, `lado` tells
  the human in one line.
  Messages to `human` are never dropped: stop, finish and `drop_undelivered` leave them as
  they are and do not count them (`state.UNRECEIVED`).
- **Questions**: `ask_human(question, details, choices, free_answer)`, for every agent; at
  most 6 choices of at most 160 characters each, no duplicates; no choices and no free
  answer is refused. A question is a message of kind `question` to `human` with its
  `choices`, `free_answer` and `question_state` (`open`, `answered`, `dismissed`,
  `closed`). The answer (`Answer to #<id>: <choice or the first line>`, the rest in the
  body) or the dismissal (`Dismissed #<id>`, the human's comment as its body when they
  wrote one; feature/question-answer, 2026-10-10) is a message from `human` to the agent with
  `reply_to` and `choice`, queued in the transaction that sets the question's outcome and
  `answered_by`; a question not `open` refuses both. The replies to several open questions
  of one agent are taken together (`runtime.answer_questions`, LAD-28): each checked first,
  all queued and closed in one transaction, the agent's queue taken once, so an idle agent
  gets them in one hand-over and starts one turn; one wrong reply refuses the whole call
  with nothing changed. A reply may carry the files the human uploaded for it (LAD-86):
  attached to its message, checked first (at most 10, every name found, else the call is
  refused whole); an own answer of files only is an answer, its summary
  `Answer to #<id>: <n> file(s): <names>`. `lado answer` and the popup attach none. When the agent is forgotten
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
  `POST /api/sessions/{name}/answers` `{answers: [{question, choice?, text?, skip,
  artifacts?}]}`, the replies of a tab of the waiting card, all to one agent (`skip`: a
  dismissal, `text` its comment; LAD-28, replacing `…/questions/{id}/answer` and
  `…/dismiss`; `artifacts`, the full names of the files uploaded for a reply, LAD-86).
  The POSTs need the server's own Origin (`Guard.changes`), answer 503 under another
  schema, 404 for an unknown session and 400 with the core's reason for what it refuses
  (a stopped session, an agent that is not running, a question not open). They return
  `{result}`; the UI shows a message only when the feed brings it.
- **UI**: Activity is the chat: the messages from and to the human (their text as Message
  text in Look of the feed says, Markdown with any HTML left out), "not delivered" on a
  failed one, "<agent> replied only in its terminal" on a `missing` one, each open question
  as a line and each closed one as a card in its agent's row; under the feed the waiting
  card, then the composer. Its look is Look of the feed, below.

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
  The cards in rows (a closed question's, a waiting agent's on Needs you) have no head of
  their own.
- **Groups**: an entry continues the group above it (no head, no letter; its time in the
  avatar column, seen on hover and focus, always in a column of 520 px or less) when the
  row above is a message or question of the same sender to the same recipient, less than
  5 minutes before it; a day divider, a run's events, a gate, an open question's line or a
  late reply's line between ends a group. The human's reply to a question in the window is no row (Answer in the
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
    `.md-table` frame (`--line`, radius 6) and fills its width (task fix/md-tables-wrap,
    2026-10-10: a short table spans the frame too, so its border and the frame's meet):
    its cells, the head row too, wrap by words, and a token with no place to break (a
    path, a URL, a hash) breaks anywhere (`overflow-wrap: anywhere`), so a table of a
    few columns of prose fits the column. Each column keeps a minimum, 7em with its
    padding but at most a third of the frame (`min(7em, 33cqi)`, the frame a size
    container), so three columns fit also in a phone's chat; a table whose columns cannot
    fit at that minimum scrolls sideways in its frame, so neither the chat nor the panel
    ever does. The head row on `--raised` in 600, cells 6×10 px, each column aligned as
    its `:---:` says.
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
- **A question**: open, a quiet line where it was asked, "<agent> asked: <summary> ↓"
  (a mini avatar, the text cut at the line's end, the arrow beside it, the time; it ends a
  group), answered in the waiting card (LAD-28; before, an orange card in its row);
  closed, a neutral card "Question #N",
  its choices faded, the chosen one marked "✓" in `--done` (the only place the choice
  shows), the supervisor's recommendation's quiet line, if one was given (The
  supervisor's recommendation, below), and the human's reply in the card (Answer in the
  question card); "Closed: the agent left" when its agent was
  forgotten. The reply's text comes from the answer's fields, never from parsing the
  core's line (`replyOf`): the `choice` with the body under it as a comment; else a body
  that is not empty (the whole text, `runtime._human_text`); else the summary without
  `Answer to #N: ` (as `runtime.answer_question` writes it). A dismissal is told by its
  question (`dismissed` and `answered_by` this message; with no question in the window, by
  the summary `Dismissed #N` of `runtime.dismiss_question` and no `choice`), its body is
  its comment.
- **The waiting card** (decided 2026-10-13, LAD-28, mockup
  `task/lad-28/mockup-question-card-final.html`; it replaces the open question's card of
  feature/question-answer, whose field beside the composer's read as a second place to
  write, and the hint over the composer). `WaitingCard.tsx`, between the feed and the
  composer while anything waits in the session, and nowhere else in the chat does the human
  answer it. Its open questions come from what waits for the human (the list `waiting`,
  `state.waiting_items`, Needs you's), its gates from the session's gates (also in a
  stopped session); no second list. **Tabs**: one per agent with open questions (all of
  them, by id) and one per open gate, in the order their first item was asked (then by its
  id); a tab shows the agent's avatar letter in its colour (`avatar`), or a gate's the
  Flows icon in its run's colour (`runColours`, grey until the runs load), the name (the
  run's for a gate) and the number of its items in a muted badge; its 3 px top in that
  colour, dashed for a gate. Many tabs stay on one line, as the terminals' (Terminals,
  Tabs): a name is cut with an ellipsis down to about 72 px (a shorter one whole), then the
  row scrolls sideways (the wheel too), with no bar, which would lie between the shown tab
  and the panel; the shown tab scrolls into view, and the expand button at the right never
  moves (review of LAD-28, F2). The shown tab is the human's: it stays while items come or go
  on other tabs, and when it empties the first one shows. **An agent's tab**: its
  questions, numbered when more than one, each with its text in bold, its details
  (Markdown, muted) and chips, its choices as 32 px buttons (one picked, `--action` on
  `--action-ground`; a second click unpicks), **Other…** (only for a question with a free
  answer: a field "Your own answer") and **Skip** (a field "Why you skip it (optional)");
  the three exclude each other, and a pick is kept per question across tab switches.
  **Fields** (decided 2026-10-15, LAD-70, mockup `task/lad-70/mockup-answer-field.html`,
  option A; before, one row for an own answer and a skip's comment, two for a gate's
  comment, with a resize handle that grew the field under the Send row and off the
  screen): those two and a gate's comment for the next step, as wide as their question,
  open 3 lines high, grow with their text to 8 (the composer's rule, `fieldHeight.ts`),
  then scroll inside, with no resize handle, in every view of the card and on the Flows
  tab's gate card alike; while the human types and the field grows, its lower edge comes
  into view (`scrollIntoView({block: "nearest"})`: the card's list scrolls, else the
  page). A ring around an item of the card shows whole (decided 2026-10-16, LAD-78,
  mockup `task/lad-78/mockup-focus-ring.html`; before, the list kept room only below and
  on the right, and cut the left side of a field's focus ring and the top of a question
  marked at its top): the list keeps `--ring-room` (4 px, the largest ring: the
  `:focus-visible` outline of a gate's comment; the 3 px ring of a focused own answer or
  skip's comment and of a marked question) on every side and pulls itself back by as much
  at the top and the left, so the items and the Send row stand where they would without
  it, and a field scrolled into view keeps that room at whichever edge (`scroll-margin`;
  also the Flows tab's gate card, whose run page scrolls it into view).
  **Files in the fields** (decided 2026-10-18, LAD-86, mockup
  `task/lad-86/mockup-answer-files.html`, option A): Other…'s field, Skip's and a gate's
  comment take files as the composer does (Files in the composer, below; one module,
  `attachFiles.tsx`, `AnswerBox`): the composer's frame, the paperclip at its left, the
  chips above the text, a paste of a file or of a text longer than a message, and a drop
  on the field, whose frame is its own drop zone. The frame draws the field's focus ring
  (3 px, `.composer-box:focus-within`) and is what comes into view as the field grows. A
  picked choice has no field and takes no files. The card keeps the files per question
  (Other… and Skip share them, so a switch keeps them) and per gate, as it keeps the
  comments, and drops those of an item closed elsewhere, revoking their thumbnails; the
  server's limits (`GET /api/limits`) load with the card. A file dropped on the card but
  not on a field goes nowhere (the browser does not open it); the composer leaves the card
  to its fields, and takes what is dropped anywhere else in the chat. The
  Send row, always shown: **Send answer to <agent>** / **Send <n> answers to <agent>**, on
  once each question has a choice, own words that are not blank or files, or Skip, with
  "<k> of <n> answered" beside it until then; it uploads the files of the tab's fields not
  uploaded yet, then posts the tab in one request (`POST …/answers`, each reply with its
  files' names), and the agent gets the replies in one hand-over. A failed upload stops it,
  its chip red with the reason. A refusal shows in the Send row with the
  core's reason and the picks stay (as a gate's comment does: the card keeps the picks and
  the comments across its tabs and its expanded view); the tab goes only when `waiting` brings its questions
  closed. Each question shows the supervisor's recommendation (below) under its details,
  and its recommended choice is picked ahead (decided 2026-10-13, LAD-28, mockup
  `task/lad-28/mockup-recommendation-in-tab.html`, option B): the counter counts it and Send
  sends it as any pick; the human's own pick, also an unpick, wins, and a recommendation
  given later picks its choice then only in a question the human has not touched. A comment with a choice is not offered (the API keeps `text` with `choice`).
  **A gate's tab**: the gate's panel (Flow gates, above), its buttons in the Send row,
  which answer at once. **Look**: the panel on `--human-ground` in a 1 px `--human` frame,
  radius `0 10px 10px 10px`; the shown tab lies on it, tinted with 10 % of its colour, its
  text `--ink` 600; the others `--raised` and `--muted`. **Height**: at most half the
  chat's; the list scrolls inside, the tabs and the Send row stay in view. In a session's
  chat on a window wider than 900 px, the edge above the card is a splitter (decided
  2026-10-14, LAD-54, mockup `task/lad-54/mockup-gate-card.html`, screen D; before, the
  card could not be made smaller, and the human talking a gate over with the supervisor
  read the replies in the other half): dragged, or ↑ / ↓ on it by 40 px, it gives the
  card a height from its least one (`WAITING_MIN`, 166 px: its head, two lines of its list
  and its Send row) to the room it shares with the feed less the feed's 160 px
  (`FEED_MIN`); a double click forgets it, back to the stylesheet's half. The height is one
  value for every session, as the columns' widths are (`lado.waitingHeight`); a chat too
  short for it shows the card lower and keeps the chosen height. Dragged down past the
  least height, the card stays at it and minimizes (below) when the edge is let go, while
  the edge still holds the pointer, so the release lands on no line or tab of the
  minimized card (`Splitter`'s `onEnd`); ↓ past it minimizes at once. The card keeps its
  height for the restore. No edge
  while the card is minimized or expanded, on Needs you, or on a narrow window, whose page
  scrolls. **Minimize** (LAD-54, screens 2 and 2a: the pair of icons): in a session's chat
  only, an icon button left of the expand one, in its style, "Minimize the card" (a line,
  `MinimizeIcon`). Minimized, the card is its tabs, none shown, and one button-line on the
  "waits for you" ground with the shown tab's first item's question (a gate's question, an
  agent's first question), muted, cut with an ellipsis: no answer buttons, choices or
  fields; the icon is "Restore the card" (a window, `RestoreIcon`; `aria-expanded`). That
  icon or the line restores it, the focus then on Minimize; a tab restores it and shows
  itself. The browser keeps, per session, the keys of the tabs the card had when it was
  minimized (`lado.waitingMinimized.<session>`): it stays minimized, also across a reload,
  while each tab it shows is one of them, so a new tab (a new gate, an agent with no tab
  asking) restores it with no event to watch and the shown tab the human's, and a question
  added to a tab that is there leaves it minimized (the tab's count says so). A restore
  forgets the keys. Once the chat has both its open questions and its gates loaded, the
  keys narrow to the tabs there are and go with the last one (never earlier: the gates may
  load after the questions), so an agent whose tab went away has a new tab when it asks
  again (review of LAD-54, F1). Expanding a minimized card shows it whole, and folding it brings it
  back minimized. Minimizing changes nothing of what waits: Needs you's count and the
  notifications are as before, and Needs you shows the card whole, with neither control.
  An icon button
  at the right of the tabs (`ExpandIcon`, no text; "Expand the card", the UI's Tooltip;
  `aria-expanded`) shows it in its place over its page's area, never over the whole
  window, nothing dimmed, no modal (decided 2026-10-13, LAD-48, mockup
  `task/lad-48/mockup-expanded-card.html`, option A; before, a dialog over the window and
  a scrim, under which an artifact panel opened from it stayed hidden): in the chat over
  the chat's whole area, the feed and the composer hidden, the session's head, tabs and
  team row seen and usable (but on a phone, which hides the tabs and the team row too:
  Phone layout, The chat); on Needs you over the page's content area (Needs you, above).
  Its host hides the rest by CSS (`:has(.waiting-card.expanded)`), so the artifact panel
  and its scrim, fixed over the page, are over the card too. On a window of 900 px or
  less, which scrolls, it is the window's height under the top bar and expanding scrolls
  it there. Its other icon ("Collapse the card") or Esc brings it back, the focus
  returning to the expand button, and it comes back by itself when nothing waits. While
  an artifact panel is open (`?view=`), Esc closes the panel only; the next Esc folds the
  card. **Lines lead to tabs**: an open question's or gate's line in the feed
  has an arrow ("Answer question #N", "Answer gate #N") that shows its tab and marks the
  item for 1.5 s; a link to an open item (`#message-<id>`, `#gate-<id>`: Needs you's
  targets, a notification) does the same once what waits is loaded, and scrolls the feed
  nowhere.
- **The supervisor's recommendation** (decided 2026-10-12, LAD-27, mockup
  `task/lad-27/mockup-recommendation.html` v3; `Recommendation.tsx`): LADO asks the
  supervisor for its view on each gate and each other agent's question (docs/design/agents.md), and it is part of that card, never an entry of its own: `recommendation`
  of `GateInfo` and of a question's `MessageInfo` (`RecommendationInfo`: state, text,
  choice, disagrees, by, at; none when never asked), brought by the feed with the item.
  Open, a block between the question's text (the gate's note and what it reads) and the
  answer, also in Needs you and on a run's page in Flows: the supervisor's small avatar,
  "Supervisor's recommendation", "disagrees with <agent>" as an orange chip when the
  supervisor disagrees with the agent whose report led to the gate or who asks, the time
  on the right, then the whole text as Markdown (no length limit or Show more: the
  supervisor is told to keep it short). Its left band is the supervisor's avatar colour,
  orange when it disagrees. On a gate the recommended option's button is the panel's only
  primary one, the others quiet, with no other label, whether the supervisor agrees or not;
  the option is not named in the block's head (the blue button says it). Without a
  recommended option the first button stays primary. On a question, whose choices in its
  tab are picks and whose primary button is Send, the recommended choice is picked ahead
  (The waiting card, above). While it is asked, one muted
  italic line "Supervisor is preparing a recommendation…"; when the supervisor's turn
  ended without it, "The supervisor gave no recommendation"; never asked, nothing. The
  human answers in every state; a recommendation given later replaces the line and moves
  the primary button (or picks its choice). Closed (a gate opened by a click, a closed question under its
  choices), one quiet line with the small avatar, "Supervisor recommended: <option>" (the
  button's label) or "Supervisor's recommendation" without one, " · disagreed with
  <agent>" in orange, the text on a click (`details`); the human's choice stays marked only
  in the list.
- **Answer in the question card** (decided 2026-10-07, feature/chat-message-text, mockup
  `question-answer.html`): with its question in the window, the reply is drawn in the
  question's card under the choices, on the human's ground: a small "Y", "You ·
  answered" (or "You · skipped", quieter: the UI's word for a dismissal since LAD-28), its time, and the comment that came with a
  choice (else the own words; a dismissal's comment) as Markdown with `breaks`. The choice
  itself is not repeated there: it is marked "✓" only in the list above (decided
  2026-10-12, LAD-25, mockup `mockup-closed-question.html`, option A; before, the block
  repeated it in bold "✓", which read as if the human had typed it). Without
  the reply in the window, the block says only "You · answered" or "You · skipped".
  When the reply is the row right under its question, it is no row; when other rows came
  between, one quiet line stands where it was given (it ends a group): "Y", "You answered
  question #N ↑" (a link up to the card, `#message-N`) and the answer's start on one line
  cut with an ellipsis, or "You skipped question #N ↑" (with ` · ` and its comment's
  start, cut the same way, when it has one). A reply whose question is not in
  the window (pages not loaded) is the human's row "answer to #N" as before, a dismissal
  the line "You skipped question #N", its comment under it. The reply's anchor `#message-<id>` is its late
  line when there is one, else its block in the card. The reply's files (LAD-86, mockup
  `task/lad-86/mockup-feed-files.html`) show as the human's own message shows them: in the
  card's block and in the row "answer to #N", the images previewed (at most 240 × 180),
  then every file a chip; under a skip's line, the chips; an own answer of files only shows
  the files alone, not the core's summary that names them (`replyOf`: a summary
  `Answer to #N: <n> file(s): …` with as many attachments). The late line ends
  "· <n> file(s)".
- **Flow events** (decided 2026-10-07, feature/chat-message-text, mockup
  `flow-events-a.html`): a run's events in a row, with no other row between (whatever the
  time), are one group (`<ol aria-label="Flow run <run>">`): the flow icon and the run's
  name once on top, a link to its page in Flows; no link in the lines. A line (Inter
  13 px, at the text's column): a small avatar of the actor (an agent's colour, "Y" for
  `human`, a grey "L" for `lado`), its name muted ("You" for the human), then by kind: a
  `flow` move as chips, the state it left (mono, muted) → the state it entered (mono) and
  the outcome, green (`--done`) forward and orange (`--human`) with a return icon back
  (below); `flow_start` "started", `flow_end` "ended" (green), `flow_cancel` "cancelled",
  `flow_set` "set by you", each with the core's `detail` as it is, cut by CSS on one line (the UI parses no detail); a
  `flow` event whose detail is no move shows its detail. The time on the right, always
  seen. `gate_answer` is no line: the human's answer is their move. `gate_open` is no line
  either (LAD-135): the gate's own row, open or folded, shows it, right under the run's
  group that ends with the move that led to it. A **move's direction**
  (LAD-62, 2026-10-14, mockup `mockup-outcome-colour.html`) is one rule for the chat and
  Flows (`flowSteps.direction`), by the run's flow alone (`RunInfo.states`, of the
  session's runs the chat watches), never by which other events are loaded: a move goes
  back when it leads to a state the flow declares no later than the state it left (a stay
  in its state too), else forward. A step back's outcome has a return icon before its
  word; a screen reader hears `<outcome>, a step back` / `a step forward`, from hidden
  text (`.visually-hidden`) right after the chip, as the icon is decorative and the chips
  are no tab stops (an `aria-label` on a plain span is not allowed, and Chromium drops
  it); the chip's own text stays its outcome. Hovering a forward or back
  outcome shows the UI's tooltip (`Tooltip.tsx`; `OutcomeChip` and its text are shared
  with Flows): `Forward in the flow, to <to>`, or `Back: the work returns to <to>` and,
  muted in the mono face, `Runs again: <to> › … › <from>`, the shortest way through the
  flow's outcomes from the state returned to to the state left (`flowSteps.runsAgain`,
  breadth-first, ties by the declared order; no way, no line). Never the whole flow: a
  branched flow does not fit one line. Without the flow (the runs not loaded, the run's
  `problem`, a state not in it) the outcome is neutral: the `--raised` ground, no icon, no
  tooltip. Kit authors: declare a flow's states in the order its work goes, branches
  before the state they join, as the UI reads that order as forward. Its outcome is
  always written. The **human's answer to a gate** is one line: their
  `flow` move (only the human's answers write a `flow` event as `human`; `lado flow-set`
  writes `flow_set`), with the answer's comment under it (Markdown with `breaks`) and its
  files after it, previews and chips (`answer_attachments`, LAD-86), from the
  `GateInfo` whose `closed_by_event` is the move's id (`gateOf`; the closed gate's card
  finds its move the same way, `moveOf`; before LAD-85 a guess by run, state and time).
  Without that gate loaded, the move alone. The closed gate's card stays where it opened.
  The human's own lines of a group (an answer's move with its comment, a `flow_set`)
  stand on the human's ground (`.run-event.mine`, `--action-ground`, 8 px past the line on
  both sides, so the time stays on the feed's edge, LAD-136), as their messages do; the
  agents' lines have none (LAD-85).
- **Quiet lines** (run events, an open question or gate, a closed gate, a late reply, a
  dismissal) start at the text's column.
- **One edge for the times** (LAD-136): every time on the right of a chat row (a head's,
  a run line's, a closed gate's, a quiet line's) ends on the right edge of the text
  column; no button or chevron stands after it, and showing Copy message moves none. A
  continued row's time (in the avatar's column) and the times inside a card (a question's
  reply block, an opened gate's answer) are not on that edge.
- **The composer** (shared with an agent's page in Agents): one frame, the field without a
  resize handle growing with its text from 1 to 8 lines (by its `scrollHeight`), then
  scrolling; Send inside at the bottom right (`--raised` / `--muted` while off); on focus
  an `--action` frame and an `--action-ground` ring. Under it "to <agent>" and "Enter to
  send · Shift+Enter for a new line" (with no files, "· paste or drop files to attach").
  Enter sends, Shift+Enter is a new line; a refusal shows at the field and the text stays;
  a stopped session's composer is off and says so, its paperclip too.
- **Files in the composer** (`Composer.tsx`; run feature/chat-attachments, mockup
  `mockup-composer.html` of the run): the human attaches files to a message to any agent.
  The handling below is one module (`attachFiles.tsx`, LAD-86) that the waiting card's
  fields share (The waiting card, Files in the fields); the composer's drop leaves the
  waiting card to them.
  - Three ways in: the paperclip left of the field (the file picker, several files);
    paste while the focus is in the composer (files in the clipboard; an image the browser
    names `image.png` becomes `screenshot-<HHMMSS>.png`; a text longer than `MAX_MESSAGE`
    becomes a chip `pasted-<HHMMSS>.txt` instead of text, a shorter one stays text); drop:
    files dragged over the chat column or an agent's page make the composer's frame the
    drop zone ("Drop to attach · up to <n> files, <size> each", dashed `--action`), and a
    drop there lands in that composer.
  - Chips above the field, 44 px: an image's thumbnail (the object URL made for every file
    when it is attached and shown for an image; revoked when the chip is removed, after
    Send and when the composer unmounts), else the type's icon;
    the name and size; × removes it (a button, reachable by keyboard). A file an agent
    cannot read (by the server's types; an image over `IMAGE_LIMIT` too) has a small
    crossed-out eye on its tile, a button whose hint (the UI's Tooltip: the light card,
    `--panel` with a `--line` frame and a soft shadow) shows on hover and on keyboard
    focus: "The agent sees only this file's name and size. Agents read text and PNG, JPEG,
    GIF and WebP images." No orange: orange is only what waits for the human.
  - Under the composer "to <agent> · <n> files, <size>" while there are files.
  - Limits from the server (`GET /api/limits`, read when the composer mounts; `web/src`
    keeps no copy of the extension table, the readable types or the limits): more than
    `max_files` files or one over `max_size` is refused at the field before any upload,
    naming each file refused; the rest stay. A media type is the server's, by the
    extension, never the browser's, and a chip takes it each time it shows, never at
    attach: a file attached before the limits load shows the generic file icon and no eye
    until they load, then its thumbnail or icon and eye by the server's table (LAD-102).
  - Send (on with text or files) locks the field and the chips, uploads each file not
    uploaded yet (`POST …/artifacts?file_name=`, the bytes as the body; a moving bar on its
    chip, as fetch tells no progress), then sends the message with the uploaded full names
    (`POST …/messages {to, text, artifacts}`). A file that fails stays as a red chip
    (`--danger`) with its reason, the text stays and nothing is sent: Send again uploads
    only what was not uploaded, also after the recipient changed (the files are the
    session's, not the recipient's). A file dropped while Send is under way is not part of
    that message: it stays as a chip for the next one (only the files sent go).
- **The human's images in the chat**: under the human's own message, each image it carries
  shows as a preview (at most 240 × 180 px, `ImagePreviews` in `Attachments.tsx`) that
  opens the panel as its chip does; its chips follow as on any message. An agent's
  message shows chips only.
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
  count later; `SessionInfo.busy` says whether something moves in it
  (`state.working_agents`; 0 unless its status is `running`, since a dead
  session's agents may keep their last statuses; feature/session-activity); `AgentInfo`
  has `run` and `task` (the first line of its task).
- **Activity**: the team above the feed, a chip per agent, the supervisor first: a status
  dot that differs in colour and shape (busy a full `--done` circle; background, its turn
  ended while work it started still runs, a `--done` circle filled on its left half with a
  1.5 px `--done` border; both pulse as a working session's dot, by its one keyframes rule
  `activity-pulse`, none under `prefers-reduced-motion: reduce`; idle a `--muted` ring;
  waiting an orange diamond, starting a dashed ring, stopped a grey square; decided
  2026-10-09 in feature/background-status, mockup artifact
  `feature/background-status/mockup-dot.html`, version 3; no count of background tasks
  anywhere), its name, a tooltip; every chip alike and compact (24 px high, a pill), with
  no role on any: the role is in the tooltip and the accessible name (decided 2026-10-10,
  fix/team-chip, mockup `fix/team-chip/mockup-team-chip.html`, variant B; its classes
  are the team's own, `team-chip`, as each component's chips have theirs);
  the chip of the terminal the panel shows is marked. The agents are grouped (decided
  2026-10-07, feature/activity-team), from `AgentInfo.run` only: the supervisor and its
  own workers (no run) come first, as the server lists them; then each run that has an
  agent, in the order its first agent is listed, as a dashed frame (`role="group"`,
  `run <name>`) with its agents' chips, all in the team's one wrapping row. The frame
  shows no name and no state of the run (Flows and Agents show the state; decided
  2026-10-11, feature/team-run-frames, mockup `feature/team-run-frames/mockup-team.html`,
  version 4, variant C): its dashes (1.5 px, no fill) are in the run's colour, and before
  the chips a small Flows icon (the Flows tab's own) in that colour is the link to the
  run's page in Flows (`run <name> in Flows`; the UI's tooltip `flow <name>` on hover and
  on the keyboard's focus). The colour is `--run-1` … `--run-4` by the run's place among
  all the session's runs, ended ones too, as the server lists them (by start), counted
  oldest first, mod 4 (`runColours` in Team.tsx, no sort of its own): a run keeps its
  colour while others start and end, and four runs started one after another never share
  one. Until the runs are loaded the dashes are `--line`. The tooltip (the UI polish, the
  human's decision, 2026-10-03) is the UI's own (`Tooltip.tsx`, one component for the
  chips and the terminal tabs), not the browser's `title`: compact, from `AgentInfo`
  only: `name · role · provider` (the role left out when it is the name), and
  `flow <run>` on a second line when the agent works for a run; no task, no status (the
  status is in the accessible name). It shows 300 ms after the pointer enters, at once on
  the keyboard's focus (not a click's), goes when the pointer leaves, the focus goes or on
  Esc; `role="tooltip"`, the trigger's `aria-describedby` while it shows, no pointer
  events, kept inside the window; under its trigger, or over it when there is no room
  below, with an arrow on the edge facing the trigger that points at the trigger's centre
  (Look: Tooltips). A chip opens the agent's terminal in the panel, or selects its tab. The feed
  holds, in time order: the messages with the human and the questions; the flow runs'
  gates as cards or lines (Flow gates above); their events as quiet lines grouped by run
  (Flow events in Look of the feed), the kinds shown as lines named in one list in the UI
  (`Chat.tsx`, `RUN_EVENT_LINES`; `gate_answer` is not in it, the human's move stands for
  it, nor `gate_open`, the gate's row stands for it); and behind the toggle **Messages
  between agents** (not pressed by default, remembered in the browser) the agents'
  messages to each other. The toggle is an icon
  button at the end of the team's row (two speech bubbles, `BetweenIcon`; 26 px, quiet and
  muted unpressed, the pressed team chip's border with the icon in the action colour when
  `aria-pressed`), its name the same in both states; the UI's tooltip says the state and
  what a click does: "Messages between agents: hidden" / "Click to also show what agents
  write to each other.", pressed "Messages between agents: shown" / "Click to show only
  your conversation with the agents." (decided 2026-10-15, LAD-77: the checkbox "Show
  agent messages" did not say what it adds and its label made the chips wrap in a narrow
  column; mockups `task/lad-77/mockup-placement.html` variant Б and
  `task/lad-77/mockup-agent-messages.html` for the texts). The chat shows a window of
  messages (Message windows above): the latest 50 with the human, with the toggle pressed
  the latest 50 of all; the toggle changes the window.
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
  added to the scroll; the feed has `overflow-anchor: none`). While the feed is hidden (an
  expanded waiting card), the rule waits and applies when it shows again (a
  `ResizeObserver`), so what came meanwhile is at the bottom for a human who was there,
  and one reading above stays there (LAD-48). A link to an open question or
  gate shows its tab of the waiting card (The waiting card); a link to another card
  (`#message-<id>`, `#gate-<id>`: a notification, a late reply's line) scrolls to it; a card before the window is loaded up to in one request (a
  message by its id, a gate by its time), then scrolled to; one that is still not there
  (a message the chat does not show) scrolls nowhere.

### Launch and session control (decided 2026-10-04, task feature/launch)

The human starts, stops, resumes and forgets sessions from the browser. The server calls
the same core functions as the CLI (`runtime.start_session`, `stop_session`,
`forget_session`), so the decisions and their texts are the core's; the UI shows them.

- **New session window** (`Launch.tsx`, a modal `<dialog>`; the rail's Launch and the
  list's "+"): **Where** is a new folder made from scratch, a folder, a clone of a git
  URL made first, or a project's repository (the switch **From scratch | Folder | Clone
  from URL | Project** beside its label, below; on a screen of at most 760 px its four
  buttons are a grid of two rows); the start's request is the same for a folder and a
  clone (its `where` is `{kind: "folder", path}`), from scratch it is `{kind: "scratch",
  path}`, in a project `{kind: "project", project, repo}`; another kind, or a field the
  kind does not take, is refused (400). The path
  is typed (`~` allowed, a relative path refused), and checked by `GET /api/folders`:
  under the field "✓ git repository · branch X", or the core's reason from
  `runtime.check_repo` (`FolderInfo.problem_kind`: does not exist, a file, git not
  installed, git does not run, not inside a git repository, git cannot read it, no commits
  yet), and Start stays off until it will do. When the human can fix it (`FolderInfo.hint`:
  no git, a git that does not run, no repository, no commits) the core's sentence follows
  in muted text and its one command in a code field with **Copy** (`useCopy`; "Command
  copied", or, when no copy works, the command selected with "Press ⌘C / Ctrl+C to copy";
  LAD-5's mockup `mockup-folder-check.html`, variant 2). The window makes no repository of
  a folder that holds files: the human runs the command. A new or empty folder outside git
  (`FolderInfo.scratch`) shows instead `The folder is empty: LADO can start it from
  scratch.` (for one that does not exist, under its text: `LADO can make this folder and
  start it from scratch.`) and the button **Start from scratch here**, which switches to
  From scratch with that folder in Create in and its last segment in Name (below).
  Subfolders are suggested from the folder up to the last
  `/` (the arrow keys and Enter pick one), with chips of the **recent** folders
  (`/api/folders/recent`: the folders of past sessions, latest start first, at most 10).
  The workspace (`projects.workspace`: `LADO_REPOS`, which LADO's image sets to the
  workspace mounted at the host's path, else `~/workspace`; [projects.md](projects.md);
  `GET /api/repos-folder`, `Workspace{path, made}`, read once per window; decided
  2026-10-14, LAD-63, mockup `task/lad-63/mockup-where-start.html` variant 2; renamed
  LAD-117; the default and `made` LAD-123, mockup `task/lad-123/mockup-workspace-where.html`)
  gives the empty field's placeholder `<folder>/…`. Once the folder exists (`made`), the
  field's focus while empty lists its subfolders (a pick sets `<folder>/<name>`; never
  LADO's `projects/`, nor a folder inside it, which has none: LAD-125), and a row
  **Workspace:** with the folder as a chip, before Recent and hidden in Resume as Recent is, sets
  `<folder>/`, gives the field the focus (its keys and its blur work the list) and opens
  the list. The folder is the parent with one `/` at its end (`/` stays `/`). The folder
  check runs only on what is typed or picked, never on the empty field nor on the
  workspace itself (with or without its last `/`): it holds the repositories, and its
  "not inside a git repository" would offer a `git init` over them all.
  In LADO's container only (`LADO_CONTAINER`), a folder whose real path is outside the
  workspace gets a warning after the check mark, `⚠ Outside the workspace (<folder>):
  this folder is only in the container, your computer does not see it
  or the agents' work in it` (a `field-note warn` line; `FolderInfo.warning`, the core's
  `runtime.outside_workspace`, which a start also gives among its warnings); the check mark and
  Start stay. **Clone into** shows the same under the target's note (`CloneTarget.warning`).
  Decided 2026-10-16, LAD-83, mockup `task/lad-83/mockup-outside-repos.html` variant 2;
  renamed LAD-117.
  **Name** is the folder's default (`default_name`, the core's `slug`) with what the server
  says of it (`name_state`): taken by a running session, by a session of another folder,
  or a stopped session of this folder with **Resume it**, which turns the window to Resume.
  **Kits** (chips, "+ Add kit" from `/api/kits`: the kit of each name the lookup takes,
  the installed and the built-in kits, the same for every folder; the window still sends
  its folder as `where`, which the server ignores; one that does not load is listed off
  with `lado kits check <name>`),
  **Provider** (`/api/providers`: each provider of the registry with
  `doctor.provider_status`; "checking…" while the CLIs answer, one not installed is off,
  a version warning shows under it; a chosen name the list lacks, a resumed session's, is
  an option of its own, `<name> · unknown`, off, so the select shows it: LAD-122) and **Permission mode** (the provider's modes; a mode
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
  `changes` show above the session's tabs until closed (`.started-notice`: 12 px under
  the top bar, 10 px above the tabs, which move down while it is open; LAD-42,
  2026-10-14). No tmux attach.
- **The window's notes in three levels** (decided 2026-10-21, LAD-120, mockup
  `task/lad-120/mockup-launch-notes.html` variant A): each note under a field is one of
  three by its class. A hint (`field-note`) and a success (`field-note ok`) are quiet 12 px
  text, muted or in the action's blue, without a ground. A warning (`field-note warn`) is
  an amber panel: `--warn-ground` with a 3 px `--warn` stripe on its left, text 13 px in
  `--ink`, its icon the `⚠` its text starts with. A refusal (`field-note bad`) is the same
  panel on `--danger-ground` with a `--danger` stripe and a round `!` drawn by CSS before
  its first line (not part of its text); its hint, command and Copy stay inside it. A
  folder inside LADO's `projects/` is such a refusal (LAD-125), before git is asked: the
  core's text naming the project, `Start a session in the project:` and `lado start
  --project <id> --repo <name>` with Copy; above the hint, Folder's box has a button from
  `FolderInfo.project` (`ProjectPlace{id, title, repo}`, the core's `projects.place`):
  **Start in the project <title>** for a folder in a project's repository, which switches
  the window to Project with that project and repository, else **Open the project
  <title>**, which closes the window and opens the project's page (LAD-137). A clone's
  target (Clone into) and a fresh start's (Create in) there show the same box with the same
  hint and no button: the window adds no repository to a project. The box shows also for a folder
  there that already has a session, a session in the project too: the window starts no
  session there and offers no Resume it; such a session is resumed from its own page
  (Resume…), as its resume is never refused. Recent folders leave out folders inside
  `projects/` for the same reason. Start
  (Clone and start, Create and start, and Resume session in the Resume mode: LAD-122,
  2026-10-21) is off while a refusal shows, and a note that does
  not keep the session from starting is not a refusal: the kits list that does not load
  (`/api/kits` failed) is a warning, since the start itself refuses a kit that does not
  load. Notes outside this window (`.field-problem`, the start's own `.problem`) are other
  classes.
- **First message** (decided 2026-10-12, LAD-19; mockup `task/lad-19/mockup-first-message.html`
  v2, variant C): a row **First message to the supervisor (optional)** just above
  Advanced, in the New and the Resume mode, for a folder and a clone alike, folded each
  time the window opens (a `<details>` styled as Advanced; the two rows share one line).
  Opened: a text field (`aria-label` "First message", 4 lines, dragged taller; Enter is a
  new line, never a submit) and the note "sent to the supervisor as your message once it
  starts; its answer comes in the chat". Folded with text, the row reads `First message to
  the supervisor: <the text's first line>`, cut to one line. Over `Limits.max_message`
  (the composer's `GET /api/limits`, `runtime.MAX_MESSAGE`) the note is `<n> characters,
  the limit is <limit>` and Start (Clone and start, Resume) stays off, also folded. The
  trimmed text goes as `prompt` of `POST /api/sessions` (also the start after a clone) or
  `POST /api/sessions/{name}/resume`; a field of white space sends none. The core queues it
  as the human's message to the supervisor (`runtime.start_session(prompt=)`), after LADO's
  `session resumed` on a resume, and the Activity chat shows it as the human's.
- **From scratch** (decided 2026-10-18, LAD-98; mockup `task/lad-98/mockup-from-scratch.html`):
  for a human with no repository yet. The window opens in From scratch while LADO has no
  sessions (`/api/folders/recent` answers none), else in Folder as before; a source the
  human picks, or a folder or URL typed, before that answer is kept. The first field is
  **Name**, in the human's words, with the note `folder and session: <name>` and, when the
  text is not the name itself, ` · title: <text>` (Cyrillic transliterated, Latin letters
  without accents: `lado.scratch.names`), or the name's refusal; a name a session has
  shows under it as in Folder. **Create in** is the name's folder in where clones go
  (`<workspace>/<name>`, its placeholder too) until the human edits it, with its state:
  `✓ a new folder`, `✓ an empty folder` (nothing but `.DS_Store`), or the core's refusal
  (a folder with files, a file, a folder inside a git repository). Both come from `GET
  /api/scratch-target` (`ScratchTarget`, 200 ms after typing; only the latest answer).
  When git has no `user.name` or `user.email` (`ScratchTarget.author`), its text and hint
  show under Name with Copy: in LADO's container `Set LADO_GIT_NAME and LADO_GIT_EMAIL in
  the .env file next to compose.yaml, then restart LADO there:` `docker compose up -d`,
  else `Tell git who you are, once for this computer:` and the `git config --global`
  command; the window has no fields for them and LADO sets no author of its own. There is
  no separate session Name; Kits, Provider (`ScratchTarget.provider`), Permission mode, the
  first message and Advanced are as for a clone's folder. **Create and start** is on with
  a name, a folder new or empty, the author known and the name free; it sends `where:
  {kind: "scratch", path}` with the name and the title (`Launch.title`): the server makes
  the folder a repository with one empty commit (`scratch.make`), then starts as for a
  folder. A start refused after the repository was made switches the window to Folder
  with it and keeps the refusal shown, as after a clone.
- **Clone from URL** (decided 2026-10-12, LAD-6; mockup `task/lad-6/mockup-clone.html`
  v3): the Where field takes a git URL (`lado.clone.is_url`: `https://`, `http://`,
  `ssh://`, `git://`, `file://`, or `user@host:path`). **Clone into** is the default folder
  (`<workspace>/<repo>`: the server's `CloneTarget.path`; its placeholder names the same
  parent) until the human edits it, with the
  folder's state from `GET /api/clone-target` (200 ms after typing, like the folder): "✓ a
  new folder", "✓ an empty folder", or the core's text for a folder that holds something.
  **Branch** lists the remote's branches by itself, from `POST /api/remote-branches` (one
  `git ls-remote`, half a second after the URL stops changing, each URL asked once in the
  window's life; "fetching branches…" meanwhile, "✓ repository found · N branches" under
  the URL once listed); the remote's default branch is chosen and marked `(default)`
  (with no default said, main, else master, else the first); above 30 branches it is a
  field that lists the branches holding what is typed (Enter takes a branch typed in full
  or highlighted; other text is never sent). A listing that fails shows under
  the URL with the core's text (`CloneRefused`: `message`, `kind`, `hint`) and, where the
  human can act (an ssh key refused, an unknown host key, a GitHub login, a GitHub
  repository not shown), the hint's sentence and command with Copy, before anything is
  pressed. Name, Kits, Provider (the server's suggestion for a folder with no sessions,
  `CloneTarget.provider`) and Permission mode are the folder's. The one button **Clone and
  start** is on once the branches are listed and the folder is new or empty. A folder
  that holds a clone of the same repository (same host and path; scheme, user and port
  aside) shows "✓ <the core's text>. LADO will use it as it is: no clone, no pull, no
  branch switch." and the button **Use this clone**, which switches the window to Folder
  with that folder and changes nothing on disk; a clone of another repository shows its
  origin and a free folder beside it (`<parent>/<owner>-<repo>`), and the button stays off.
  LADO never clones over, fetches into or switches the branch of a folder that exists.
  The clone is a job of the server (`server/clones.py`): `POST /api/clones` (`{url, path,
  branch}`, or `{url, project, name, branch}` for a repository added to a project, which no
  screen sends yet (steps S6b, S7; docs/design/projects.md); 400 `CloneRefused`, 404 for an
  unknown project, 409 while another job clones into that folder) starts it,
  and the window asks `GET /api/clones/{id}` every 500 ms: a progress block with git's
  phase, its percent with a bar (`role="progressbar"`), the rest of git's line and the
  time it runs; a poll that fails is asked again (the clone goes on), and one the server
  answers 404 ends the clone: when the folder now holds the clone (it ended while the
  window did not ask, and the server dropped it after `clone.KEPT`), the window switches
  to Folder with it ("the clone ended while this window was away; it is in <folder>"),
  else it shows the server's text (it restarted). Meanwhile the fields are off,
  Resume it too, and ×, Esc and Cancel do not close the window;
  **Cancel clone** sends `DELETE /api/clones/{id}`: git's process group ends, its
  temporary folder goes, the folder is not made, and the window says "the clone was
  cancelled" (a Cancel clone that came after git ended starts no session: the window
  switches to Folder with the clone). A page that goes away during the clone (`pagehide`: its tab
  closed or reloaded) cancels it at once with `navigator.sendBeacon` to `POST
  /api/clones/{id}/cancel` (a beacon can only POST, with the cookie and the page's Origin,
  so `Guard.changes` takes it); a job no request asked about for `clone.ABANDONED` seconds
  (150: Chrome runs the timers of a tab in the background for five minutes once a minute;
  a lost connection, a sleeping laptop) is cancelled the same way, a finished one is kept `clone.KEPT`
  seconds (60), and a server that stops cancels its running clones; jobs live in the
  server's memory only. A failed clone shows its text and hint, and the form stays. A
  finished clone starts the session as Start does for a folder; a start refused then
  switches the window to Folder with the cloned folder and shows the refusal there (the
  clone stays). The server's git runs with no terminal and no prompt, with the access the
  server's machine has (ssh keys, `gh auth`, a credential helper): a server started where
  the human's ssh-agent is not reachable cannot use its keys, and the hints point at the
  command to check that.
- **Project** (decided 2026-10-23, LAD-137, step S6b of [projects.md](projects.md); mockup
  `task/lad-137/mockup-project-way.html` v2; `LaunchProject.tsx`): a session in a
  project's repository, as `lado start --project <id> --repo <name>` starts it. The window
  only chooses: it adds, clones or makes no repository (the human's answer #1282); a
  project's repositories are added on its page (step S7). Its fields come from `GET
  /api/project-launch?project=&repo=` (`ProjectLaunch`, asked again on each choice; it makes
  nothing): **Project**, a select of the projects by title (the id without one, case
  aside), each `<title> · <id>`, one whose folder is not found off and marked `folder not
  found`, with the chosen one's line `<N> repositories · <N> sessions running · folder
  <folder>`; then **Repository**, the project's repositories as a list always shown, even
  with one (`.repo-pick`, a `radiogroup`: name, branch, remote; the arrow keys move the
  choice), and `✓ git repository · branch X` under it. While a new choice is asked, the
  field shows the last answer with the choice in it (`aria-busy` on the list), so the select
  and the list keep their focus, and the start stays off until the answer to what is asked
  now has come (LAD-137, review X1). The server chooses what the window
  opens on: the project asked, else that of the latest started session in a project whose
  folder is found, else the first found; the repository asked, else that of the project's
  latest started session still there, else the first. **Name** is `<project>-<repo>`
  (`runtime.project_session_name`) until edited, with the folder check's notes
  (`name_state`, where a session of the name in another project or in none is
  `taken_elsewhere`); Kits and Permission mode come from the repository's last session in
  the project (`ProjectLaunch.last`), Provider from `ProjectLaunch.provider`, as Folder
  takes them. The start button reads **Start in <title>** (the id without one): the window
  opens on the last project used, and a quick click in another project would give the
  session another client's keys (the supervisor's condition at gate #107). It sends
  `where: {kind: "project", project, repo}`; the
  server calls `runtime.start_session(None, …, resume=False, project=, repo_name=)`, the
  CLI's call: an unknown project or repository is 404 with the core's text, a taken name
  409 `Taken` with Resume it or Open it as in Folder, only for a session of this project
  (the feed's `SessionInfo.project`: the core resumes none of another project or none;
  its folder compared with
  `ProjectLaunch.root`, the repository's git root with links resolved, as a session's folder
  is kept, not the listed path, which may go through a link), any other refusal 400. A project
  without repositories shows in the list's place `No repositories yet. Add one on the
  project's page:` with **Open <title>**, and Start stays off; without projects the field
  says `No projects yet. A project keeps its repositories and the variables its sessions
  get.` with **Make one in Projects**; each link closes the window. The window still opens
  in Folder (#1283); `useLaunch()({kind: "new", project})` opens it in Project with that
  project (the project's page).
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
  icon) copies the session page's address as the list row's Copy link does, and among the
  head's facts **Copy path** its folder (Structure, above); both say what was copied
  ("Link copied", "Path copied") under the button for 2 s, or show the text selected when
  the copy fails. Copying is one module, `Copy.tsx`, for the head, the row's menu (and a kit
  card's), and the artifact panel's Copy link, in one order: the Clipboard API; without it (the page not on
  localhost or https, e.g. `--host` over http) or when it refuses, the legacy copy (a
  hidden read-only field selected, `document.execCommand("copy")`, removed, the focus back
  where it was); only when both fail the text shown selected.
- **The list row's menu** (`SessionRowMenu.tsx`, a caller of `RowMenu.tsx`, the ⋯ that the
  Kits page's cards use too; on the shared `Menu.tsx`; decided 2026-10-09,
  feature/kits-cards): ⋯ shows on its row's hover and focus, while open or while its note
  shows, and always on a device without hover (`@media (hover: none)`), one CSS rule for
  every `RowMenu`. It holds
  actions on the entry only, and only ones that work now; no placeholders for features
  that do not exist (no Pin or colour until they do). **Rename…** comes first: it edits
  the session's title in the row (Session title, below). **Copy link** copies the
  session page's address (`location.origin` + its path), says "Link copied" in the row
  (`role="status"`, outside the menu, which closes; the focus goes back to ⋯) and goes
  after 2 s; only when neither the Clipboard API nor the legacy copy works (above) a
  popover shows the address selected with "Press ⌘C / Ctrl+C to copy".
  **Open in new tab** is a link to the same page (`target="_blank"`, `rel="noopener"`).
  The address has no token: the login is the browser's cookie, so another browser gets
  401 and the Shell's message to open the login link. In a future desktop app (Stage 7) a
  webview may open a new tab in the system browser, without the cookie; the Desktop stage
  decides.
- **Stop** asks in a popover by its button: `Stop session "<name>"?`, what it does from
  `stop-preview` (its agents are closed, the messages they did not get are dropped,
  branches, worktrees, open runs and the history stay, it can be resumed) and the buttons
  `Stop and forget` and `Stop <name>`; the name is in the request's address. The page
  stays on the session. **Stop and forget** (decided 2026-10-18, LAD-92; mockup
  `task/lad-92/mockup-bulk-forget.html`), in the colour of a dangerous action with the
  tooltip "Stops it, then deletes its history for good", stops the session, then forgets
  it without force (`Stopping…`, then `Forgetting…`), then goes to `/sessions`. It is off
  while `stop-preview` names open runs, the popover saying "It has open runs: stop it,
  then forget it from the Stopped list."; a refused forget leaves the session stopped and
  the popover shows the core's reason.
- **A menu or popover below its button** (the row's menu, the selected text of a copy that
  failed, Stop's popover; `useBelow` in `Menu.tsx`) is fixed 6px under the button, so a
  scrolling box around it does not cut it: from the button's left edge, Stop's from its
  right edge, and moved along, measured with its own width, so it stays 8px inside both of
  the window's edges (a Copy link near the window's right edge, e.g. a session's head).
- **Forget** asks in a modal window: the history is deleted for good, the worktrees and
  branches left on disk (`forget-preview`), and with open runs a box to tick
  ("Also forget its N open runs (…)") before `Forget <name>` can be pressed. After it,
  `/sessions`.
- **Forget stopped sessions** (`ForgetMany.tsx`; decided 2026-10-18, LAD-92; mockup
  `task/lad-92/mockup-bulk-forget.html`, variant 1; ticks in the list itself were turned
  down): a bin at the right end of the session list's Stopped band (`GroupHead`'s
  `action`), in the colour of a dangerous action, named and tipped "Forget stopped
  sessions…", whenever the band is drawn, folded or open; pressing it never folds the
  group. It opens a modal window "Forget stopped sessions?" with the stopped sessions the
  list shows at that moment (with text in the search, the matching ones), fixed while it
  is open: each with a tick, all ticked, its title or name and when it stopped; "All N"
  ticks or clears them all. The window loads each one's `forget-preview` (in parallel): a
  session with open runs says "N open run(s)", one whose preview is refused shows the
  core's reason and cannot be ticked. The worktrees the ticked sessions leave on disk are
  under a folded "Left on disk: N worktrees of M sessions (…)". With open runs among the
  ticked, the switch "Also forget their N open runs (…)", off; while off those sessions
  stay ("While this is off, … stay.") and are not counted. `Forget N sessions` (off while
  the previews load or at 0) forgets the counted ones one at a time, in the list's order,
  with the single Forget's `DELETE` (force only for those with runs, switch on): the rest
  of the window is off, Esc does nothing, `Forgetting K of N…`, and each row ends as
  "forgotten" or with the core's reason, a refusal never stopping the others. All
  forgotten: the window closes; any refused: it stays with the reasons and Close. When the
  open session is among the forgotten, the page goes to `/sessions`. No API of its own:
  the core decides each session.

### Projects (decided 2026-10-23, LAD-134)

The Projects section (`Projects.tsx`, `ProjectVariables.tsx`; step S6a of
[projects.md](projects.md); the mockup `task/lad-134/mockup-projects.html`, the human's
answers #1151, #1153 and #1158) lists the projects and shows one with its variables and
secrets. A project's repositories, sessions, rename and delete are its page's step S7; the
Project way of New session (S6b, LAD-137) is in Launch and session control.

- **Layout**, as Sessions: the list at the left (260 px), the project at the right at
  `/projects/<id>`; on a phone the list fills the screen and a project opens in its place
  with `← All projects` above it. Not cards.
- **The list** (`GET /api/projects`): a row is the title (the id without one), the mark
  `folder not found` when its folder is missing, then `<id> · <N> repositories · <N>
  running` (`no sessions running` when none runs). A search by title and id, and a `+`
  labelled `New project`. With no project the section is the empty state `No projects
  yet`, a sentence on what a project is, and `New project…`. An unknown id shows `No
  project <id>`.
- **No feed**: projects are not journaled and secrets are files, so the list and the page
  are read anew (`GET /api/projects`, `GET /api/projects/{id}`) when they open, after a
  change (the change's answer carries the project), when a session of the feed appears,
  starts, stops or goes, and when the window gets the focus. A change in another browser
  shows on the next of these.
- **The page**: the title and the id; `<N> repositories · <N> sessions running · folder
  <folder>` (`folder not found` after it); the line `New session in this project… Not built
  yet: the repositories on this page (adding, removing), renaming and deleting the project.
  Plan: Projects, step S7. Meanwhile: lado project show <id>, lado project repo add <id>
  <git-url>.`, where **New session in this project…** (a `link-button`, LAD-137) opens the
  New session window in Project with this project; always the warning `⚠ Projects of one
  LADO are not isolated from each other: …`; and the line on who gets a change: `New values
  reach the agents started after a change; running agents keep the environment they
  started with. Running now: <sessions> — restart a session to give it the change.`, each
  session by its title as a link (with none: `… No session of this project is running.`).
- **Variables** and **Secrets**, two blocks of rows. A variable: its name and value,
  **Edit** in place (Save, Cancel), **Remove**, and `+ Add variable`. A secret: its name
  and `set · hidden`, **Replace** (an empty field, `New value (the old one is not shown)`),
  **Remove**, and `+ Add secret`. Remove turns the row into `Remove <NAME>? Remove ·
  Cancel`; only the second Remove sends the `DELETE`. The core's refusal shows verbatim
  under the row or the form (`field-note bad`), the fields kept; the variable's `… looks
  like a secret …` offers `Add <NAME> as a secret instead`, which moves the name, never the
  value, to the secret's form. A name in `overrides` carries the mark `overrides outside
  value`, its tooltip naming `LADO_ENV_DIR`; an outside value is never shown. A secret in
  `unused` shows `⚠ Agents do not get it: <reason>` in place of `set · hidden`, Replace
  (which writes the file 600) and Remove kept; an `unused` entry that is no secret's row
  shows under the block (`⚠ <name>: agents do not get it: …`, `⚠ The secrets folder is not
  used: …`).
- **A secret's value** is typed into an uncontrolled `<input type="password"
  autocomplete="off">` outside any `<form>` (form history and "save password" follow a
  submission), read from it when the human sends it, and sent as `{value}` in the body of
  one `PUT /api/projects/{id}/secrets/{name}`; the field is emptied after a save, on
  Cancel and when it goes. After a refusal it stays in the open field so the name can be
  fixed. It is never put in React's state, an address, the browser's storage, the console
  or an error the page keeps; the server logs no request (`access_log=False`).
- **New project**, a dialog: Title (optional), Id, the short warning, Cancel and **Create
  project**. Until the human types in Id, Id follows the title (`GET
  /api/project-id?title=`, one request per pause in typing, the fresh start's names:
  Cyrillic transliterated, `_` made `-`); a typed Id is checked by `?id=`. Under Id: `Its
  folder: <folder>. The id never changes.`, or the core's refusal, which disables Create.
  Create sends `POST /api/projects`; a refusal shows under Id, success opens the project.

### Session head (decided 2026-10-07, feature/session-head)

On a phone the head is one line and its facts are in a sheet its title opens (Phone
layout, below).

- The head is the top bar's line (decided with the human 2026-10-08, run
  feature/session-head-topbar: its mockup `feature/session-head-topbar/mockup-topbar.html`,
  variant A with "A, status as an icon"; a head under the top bar, or two lines in it, or
  the facts behind an ⓘ were turned down): the tabs and the chat start about 90 px
  higher. The Shell knows nothing of sessions: `SessionHead` draws itself into the top
  bar's slot (`useTopBar`); while the sessions load or a session is not found nothing
  claims the bar and it keeps the title "Sessions".
- The head's first items: the status dot (the session list's mark, its words in its
  tooltip; LAD-108), the title (or the name), the name when there is a title, the pencil
  **Rename session**, the run time (Session title, below).
- A session in a project (LAD-125, the human's answer #810, mockup
  `task/lad-125/mockup-session-project.html` variant A) has the project as the head's first
  fact, before the folder: the muted word `project` and the project's title (its id
  without one) in `--ink`, the tooltip `Project <id>` (a `title`, as the name's), no icon
  (the folder's icon is the Projects section's). It wraps with the other facts. The title
  comes with `SessionAbout.project`, read when the head opens, so a rename shows on the
  next look; the feed's `SessionInfo.project` carries the id only. On a phone the details
  sheet has a line **Project** `<title>` above **Folder**. A session without a project
  shows nothing new. The title, in the head and in the sheet, is a link to the project's
  page `/projects/<id>` (LAD-134), the tooltip kept.
- The head's facts, left to right: where (the folder, then its git: the origin
  remote short, `github.com/ladohq/lado`, without scheme, user and `.git`, and `· <branch>`),
  the kits, the CLI (its permission mode is in its tooltip, below; decided 2026-10-08,
  fix/head-mode-tooltip). The git icon is Copy URL (the whole remote, "URL
  copied"), and its tooltip has the whole URL, the branch and the path. Without a remote
  only the branch shows, without either no git fact.
- Versions are in tooltips (the UI's `Tooltip`, never a `title`), on each kit's name:
  `<name> v<version>`, where it is (`Kit.source`, as `lado kits` says it), "installed now:
  the next agent starts with it"; a kit not found or not loading shows why. On the
  provider's name: `<title> <version>`, with an untested version also `tested with
  <tested>` and an orange `!` in the line (`var(--human)`, named "untested version"), as
  `lado doctor` warns; a CLI not installed says so; then, when the session has one,
  `mode <permission mode>`. Until the about comes there is no tooltip, so no mode in the
  head either. The versions are the ones installed
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
- `repos` is a list of one item: the session's repository. A session in a project (step S3
  of [projects.md](projects.md), not built yet) shows its project there too; how it looks
  is decided with a mockup at S3. More than one item comes only with sessions over several
  repositories, which the projects model leaves for later (projects.md, Not now).
- Known limit: the server finds the CLI on its own PATH (`shutil.which`), as
  `/api/providers` and the folder check do; agents get their login shell's PATH, so the
  version shown may differ from theirs.

### Session title (decided 2026-10-15, LAD-66)

A session's name is its identifier (the address, the CLI, its tmux session, its branches
and worktrees), so "renaming" a session gives it a **title**, a label over the name
(mockup `task/lad-66/mockup-rename.html`, variant A, both entry points; renaming the
identifier itself was turned down for its cost). The title is `SessionInfo.title`, set by
`PUT /api/sessions/{name}/title` or `lado title`, through the core's one rule
(`runtime.set_title`: one line of visible text, `lado.text`, at most `Limits.max_title`,
80, characters after the trim; empty or equal to the name is no title; a bad one is
refused, never cut). It comes through the change feed, so a title set anywhere shows
without a reload. The UI names a session through one function (`sessionLabel.ts`: the
title, else the name).

Where it shows:

| Place | With a title | Without |
|---|---|---|
| list row | the title in bold; the grey line starts with the name, `lado-2 · 3 agents · 1h 12m` (every kind of grey line) | as before |
| collapsed list's icon | its letters from the title, its accessible name the title | as before |
| row's and icon's card | first line `<b>title</b> · lado-2 · <status> · …` | as before |
| session head | `<h1>` the title, then the name small and grey (`.session-name-id`), then the pencil | `<h1>` the name, then the pencil |
| browser tab | `<title> · LADO` (`(n)` before it when something waits) | the name |
| Needs you | the session's line: the title, then the name in grey | the name |
| notification | `LADO · <title>` | `LADO · <name>` |

The list's search keeps a session whose title or name holds the text (case ignored). The
session region's accessible name (`Session <name>`), the address and Copy link keep the
name.

Where it is set (`TitleEdit.tsx`, one field for both):

- **Head**: the pencil **Rename session** after the title (and the name), shown on the
  title's hover, its own focus, and always on a device without hover; a double click on
  the title does the same. The title becomes a field of its room (a third of the bar),
  holding the title (empty without one, the name as placeholder), selected; under it
  `Enter to save · Esc to cancel · empty shows the name`.
- **List**: **Rename…**, first in the row's ⋯, turns the row into the same field (no link
  while it edits), with `lado-2 · Enter to save · Esc to cancel` under it.
- Enter or leaving the field saves, Esc cancels and sends nothing (nor does the blur after
  it); the same text as stored sends nothing. While it saves the field is read-only. Over
  the limit (counted in characters, as the server does): `<n> characters, the limit is 80`
  under the field, nothing sent. A refusal: the server's text under the field
  (`role="alert"`), the field kept open with the text. The answer, the session as stored,
  is shown at once, before the feed's item. After it closes the focus goes back to the
  pencil or the ⋯.
- **Tab takes the name** (decided 2026-10-16, LAD-84; mockup
  `task/lad-84/mockup-title-tab.html`, variant A): the name is the field's one suggestion
  while its text is a proper start of the name (case and all, the empty text included),
  the caret at the end with nothing selected, nothing saving and no input method
  composing. Empty, it is the placeholder; a start typed (`la` of `lad-84`) shows the
  rest of the name grey after it (`.title-edit-rest`, a layer over the input in
  `--muted`, hidden while the input is scrolled). Tab or → without modifiers then make the
  name the text, the caret at its end, the focus in the field, nothing sent; the human
  types on and saves with Enter. The hint meanwhile reads `Tab takes the name · Enter to
  save · Esc to cancel` in the head, `lado-2 · Tab takes the name · Enter to save · Esc to
  cancel` in a row. With other text, the name whole or a title opened selected, Tab,
  Shift+Tab and → do what they do in any field (Tab leaves it, which saves it).

### System panel (decided 2026-10-09, feature/system-panel)

What LADO, the server and the machine are, and updating LADO without a terminal
(`SystemPanel.tsx`; the mockup `feature/system-panel/mockup-panel.html`, approved variants
M2, P1–P3 of round 3, F3 and U1–U3).

- **The panel** (P1), a popover under `live`: the header `LADO X.Y.Z` with three icons:
  the QR code (Open on another device, below), the clipboard (copies `SystemInfo.report`
  and one line the page adds, its browser and OS from the user agent; "System info
  copied") and the GitHub mark (`LADO on GitHub`, the repository in a new tab; it replaced
  the text link `GitHub ↗` in LAD-94). Then Server (the page's origin), Running
  (how long only; the start in its tooltip, F3), Home (shortened with `~`; the folder icon
  on its left copies the full path, the session head's `CopyButton`), tmux (version ·
  socket), git (`SystemInfo.git`: its version, `not installed` or `does not run`, by the
  folder check's own `runtime.git_version`; never its path), on a Mac Graphical session (`process remote · server gui`, or `no tmux
  server`: `SystemInfo.gui_session`, where the server's process and LADO's tmux server run,
  lado.gui_session), the providers (a dot: ok, an untested version, not installed; the version, and
  the tested one when it differs), and last the update check: `Up to date · checked 09:12`,
  `checked yesterday`, `Checking…`, `Check failed · 09:12` with the reason in its tooltip,
  each with ↻ (`POST /api/update/check`). Esc or a press outside closes it. It ends 8 px
  above the window's bottom and scrolls what does not fit (the window does not scroll).
- **A newer LADO** (P2): an Update block on top, `0.33.0 is out · 12 Oct`, What's new (the
  GitHub release of its tag) and **Update…**. Without an installer (P3) the block says
  why (`why_not`) and shows the commands by hand with Copy, and no button; with
  `can_update` false for another reason (an update runs) it says that reason. In a
  container (LAD-59, mockup `task/lad-59/mockup-container.html`, option A) it says why
  (a new image updates LADO) and shows no command and no button (LAD-73, mockup
  `task/lad-73/mockup-container-update.html`, option 1): how to update a container is the
  documentation's.
- **In a container** (`UpdateInfo.container`, `LADO_CONTAINER`): a grey `container` pill
  beside `LADO X.Y.Z` in the header, its tooltip saying a new image updates it; from
  `UpdateInfo`, which the header has first, not the slower `/api/system`.
- **A pre-release** (LAD-31, mockup `task/lad-31/mockup-prerelease.html`): a LADO on a
  release candidate has a grey `pre-release` pill beside `LADO X.Y.ZrcN` in the header
  (`UpdateInfo.prerelease`; its tooltip says that newer release candidates and the release
  are offered), and the Update block a pill after the date when the offered version is a
  release candidate too (`available_prerelease`). A final release is never offered one, so
  it shows no pill anywhere; the top bar's `↑ X` mark is the same for both.
- **Update…** (U1) opens a modal with the plan from `GET /api/update/plan`, the same data
  `lado update` prints: from → to, each session to restart with its agents' statuses and
  open runs, this UI server, "Busy agents lose their current turn…", on a Mac outside the
  graphical session the core's line on where the agents resume (`UpdatePlan.agents_note`,
  as `lado update` prints it), Cancel and **Restart
  and update**, which asks `/api/health` for the server's `started_at`, then `POST
  /api/update`.
- **The wait** (U2), under the top bar: "Updating to X · The server is restarting · m:ss".
  The page polls `/api/health` and `/api/update` every 2 s and ends on both: a server whose
  `started_at` is newer than the one before, and `UpdateInfo.last` with the id the 202
  answered and an outcome other than `running`, and in either case `running` false: the
  result is written while the update still holds its lock, and the `UpdateInfo` that ends
  the wait is the one the System panel keeps (LAD-57: before, it could say an update runs,
  without Update…). So it ends after a rollback too, where the version is the same; when
  the version changed, the version banner offers the reload. An update that ended before
  it started (a failed result of that id with no log) ends the wait on the same server. After 5 minutes it says "The server did not come back. See <update.log>; start it with
  `lado ui`" and goes on polling. The page cannot learn the steps while the server is gone.
- **The result** (U3), under the top bar, from `UpdateInfo.last`, also after a reload:
  ok; partial with the sessions that did not resume and their `lado start`; failed, rolled
  back or rollback failed with the reason, the database line and the log's tail. Each
  result shows until dismissed (the browser keeps its id, `localStorage`), and none older
  than a day.
- **Statistics**, a row after git: `sending · last today 09:12` (`yesterday 09:12`, `12
  Oct`, `not sent yet`), `off`, `not chosen`, `off: DO_NOT_TRACK=1`, `off: no endpoint`
  (`SystemInfo.telemetry`, `statisticsLine`); it links to Settings and closes the panel.
  The copied report has `- Statistics: on|off|not chosen|off by <VAR>`.

### Open on another device (decided 2026-10-18, LAD-94)

A link and its QR code that open LADO on a phone or another computer (`Share.tsx`; the
mockup `task/lad-94/mockup-share-access.html`, section 1 option И3 and sections 2a–2d).

- **The icon**: the QR code, first of the system panel's header icons (tooltip and label
  `Open on another device`). It opens the dialog `Open LADO on another device` (a
  `question-dialog`); the panel stays behind it, and the dialog stays while the page's
  feed reconnects after a new link (its state is `LinkState`'s, in `Shell.tsx`, which
  outlives `live`).
- **With a link** (`GET /api/access`, read at each opening): the warning (`.share-warning`:
  the link gives **full access** and travels unencrypted, for a trusted network only); the
  QR code of the full link, drawn in the page (`qrcode-generator`, error correction M; 180
  px, black on white with a 4-module quiet zone in both themes, `role="img"`); `Scan it with
  the phone's camera, or send the link.`; the link with its token cut to its first and last
  four characters (`cutToken`); **Copy link** (the full link; `Link copied`; when the
  browser cannot copy, the link in a field to copy by hand); `Anyone who opened LADO with
  this link stays in until you make a new one.`
- **Without one**: `loopback` outside a container, the command `lado server stop && lado
  ui --host 0.0.0.0` (**Copy command**); `loopback` in a container, the `.env` lines
  `LADO_LISTEN=0.0.0.0` and `LADO_PUBLIC_HOST=<this computer's name>` (**Copy lines**);
  `no-address`, `LADO_PUBLIC_HOST` in `.env` or one address in `LADO_LISTEN`; `unknown`,
  the container's note as the server prints it. No field to type an address: the address
  is the environment's.
- **New link…** in every state asks first (`Make a new link?`: everyone who opened LADO with
  the current link is logged out at once, this browser stays in; the same as `lado server
  --new-token`, without a restart; **Cancel**, **Make a new link** in `danger`), then
  `POST /api/access/new-token` and shows the new link; a refusal shows the API's message.

### Usage statistics (decided 2026-10-13, LAD-32)

Whether LADO sends anonymous usage statistics and its errors to its maintainers
(`Telemetry.tsx`; the mockup `task/lad-32/mockup-consent.html`, screens 1A, 2, 3 and 4
approved, 1B rejected; what is sent: docs/telemetry.md). The choice is the server's
(`LADO_HOME`), the same as `lado telemetry on|off`: `GET /api/telemetry` (`TelemetryInfo`),
`POST /api/telemetry {choice}` (under `Guard.changes`; 409 while the server's environment
switches it off), `GET /api/telemetry/preview` (`TelemetryPreview`, what `lado telemetry
show` prints). It is read once per page and after the page's own choice, never from the
change feed: a choice made in the CLI shows after a reload.

- **The banner** (1A), under the top bar on every page, after the update's, once the event
  stream is open, while `ask` (not chosen, also a yes to an older list of fields, whose new
  ones it names; nothing switches it off; an endpoint): "Help improve LADO?", what is sent
  and never sent, "Nothing is sent until you choose…", **What is sent** (a disclosure that
  loads the preview once), **Send statistics**, **Don't send** and What LADO collects ↗.
  A choice hides it.
- **Settings → Usage statistics** (2), the last section: Send / Don't send under the legend
  "Send anonymous statistics and errors to LADO's maintainers", and one state: chosen (on
  or off) with the paragraph on what is anonymous and the variables that switch it off, and
  for on `Last sent today at 09:12` (or `Not sent yet`) · What LADO collects ↗, `Last try
  failed: <reason>` when the last try failed, and What the next report sends; not chosen:
  the heading's `— not chosen yet` and "Not chosen yet: nothing is sent."; off by the
  environment: the heading's `— switched off by the environment`, the switch disabled on
  Don't send, "Off: `DO_NOT_TRACK=1` is set in the LADO server's environment."; no
  endpoint: disabled, "This LADO has no statistics endpoint: nothing is sent."

### Report a bug (decided 2026-10-14, LAD-33)

A bug report the human sends as a new GitHub issue (`ReportBug.tsx`; the mockup
`task/lad-33/mockup-bug-report.html`, variant A approved, B and C and the first version, a
button in the system panel, rejected: it must always be in sight). **Report a bug** is on
the rail above Settings on every page, its icon alone with its name as tooltip when the
rail is collapsed, and opens the page `/report` (title "Report a bug"), a page like
Settings. The page loads `GET /api/bug-report?browser=<browserLine>` on each visit (never
from the change feed; the server checks the line's shape, 422 else) and shows: the warning
(a public issue on github.com/ladohq/lado, nothing is sent until the human submits it
there, where they can edit it, no paths, session or repository names nor message texts,
and **private reporting** ↗ for a vulnerability), the whole report in `pre.log` (the same
as `lado bug-report` prints, with the page's `- Browser:` line), **Open a new issue on
GitHub ↗** (the report's link to GitHub's new issue form, in a new tab; the oldest kinds of
errors may be left out of it, counted in its last line, never on the page) and **Copy
text** ("Report copied"). Loading shows "Loading…", a failed load its reason. Nothing goes
to GitHub before the human's click. The system panel keeps its own copy button.

### Selected text and copy buttons (decided 2026-10-15, LAD-67)

What the human can do with text they read (the mockup `task/lad-67/mockup-selection.html`,
the quote icon of variant 1; openspec change `selection-actions`).

- **Readable areas.** A component that renders text to read marks its root as an area
  (`quoteArea` in `quote.ts`: `data-quote` `text`, `markdown` or `code`, the session, and
  for an artifact its full name and whether the record is older than the latest; a text
  artifact's rows carry `data-line`): each message of the chat (`.feed-main`), its run
  events, closed gates and skipped questions; the waiting card's questions and a gate's
  question, note and recommendation; the agent page's task and messages; an open note of
  the Flows tab; the cards of Needs you; a Markdown artifact's body and a text artifact's
  table, in the panel and in the Artifacts tab. Not areas: inputs, the composer, terminals,
  HTML artifacts (their frame), images, and the UI's chrome (rail, tabs, heads, buttons).
- **The selection bar** (`SelectionBar.tsx`, mounted once in the shell): when a selection
  that is not blank lies in one area (none that takes text of two, nor in a field, an
  editable element or a terminal; one that ends at the next block's start without taking
  its text, as a triple click on an area's last line does, is still that area's), a small
  bar of two icon buttons, their names in the
  UI's tooltips: **Copy** (two sheets) and **Quote in reply** (a speech bubble with quote
  marks). It stands over the selection's middle, 8 px above it; below it on a touch screen
  (`(hover: none)`, where the system's own menu stands above) or with no room above; never
  past the window's edge. Esc, a press outside it, a scroll or an empty selection hide it;
  a resize places it again. Its buttons never take the selection away.
- **Copy** copies the live selection as Ctrl+C does (`execCommand("copy")`), else the
  selection's text by the Clipboard API, and says "Copied" in the bar's place for 2 s; the
  selection stays. When both fail, it says "Press ⌘C / Ctrl+C to copy".
- **Quote in reply** builds a Markdown quote (`quote.ts`): each line `> `, an empty one
  `>`; from a Markdown artifact under `In <full name>:`; from a text artifact its selected
  lines, cut at the selection's ends and without their numbers, as a fenced block (a fence
  longer than any backticks in them) under `In <full name> (lines a–b):` or `(line a)`; a
  record older than the latest says `, an earlier record`. The quote goes to the page's
  composer (the chat's, to the supervisor, or an agent page's, to that agent; also under
  an artifact panel), after one blank line when it holds text, then a new line with the
  cursor, focused; the recipient never changes. On a page with no composer (Artifacts,
  Flows, Needs you) the session's chat opens with the quote in its composer
  (`quotes.ts`). An expanded waiting card of the session folds.
- **Copy code and Copy message.** Each fenced code block of Markdown the UI renders has an
  icon button **Copy code** at its top right (its code exactly); each message of the chat
  has **Copy message** right before its head's time (6 px from its icon to the digits, its
  24 px hit area kept, the two wrapping to the next line together; LAD-136), or at a continued row's top right, and so has each
  message on an agent's page: the human's text, an agent's summary (unless its body's
  first line says it) and body after a blank line, by the chat's own rule. A closed
  question and the human's answer have none: a question is short and never folded, an
  answer is the human's own text. Copy message is there because the selection copies the
  rendered text without its Markdown and cannot reach the part of a long message folded
  under Show more. Both say "Copied" for 2 s, and fall back to the text to copy by hand as
  Copy link does. With a pointer that can hover they show only over their block or
  message, or with the focus. On a touch screen (`hover: none`) Copy code always shows and
  Copy message never does: the selection copies there, and the head's time takes its
  place on the edge.

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

### Phone layout (decided 2026-10-18, LAD-95)

From a phone's browser the human follows a session and answers it: the feed and the runs,
gates and questions, a message to the supervisor, artifacts, Stop. The computer's design
does not change (the human's condition). Mockup: run artifact `task/lad-95/mockup-phone.html`
(navigation A, the menu; B, a bottom bar, was turned down: 56 px of height always, 15% of a
phone held sideways). Change: `openspec/changes/phone-layout/`.

| Screen | Pointer | Layout |
|---|---|---|
| ≤ 600 px wide | coarse | phone, `data-phone="tall"` (`short` when also ≤ 500 px high) |
| ≤ 500 px high | coarse | phone, `data-phone="short"` |
| any | fine (a mouse, a trackpad) | as before |
| a tablet (820×1180, 1180×820) | coarse | as before |

- **One query**, in `web/src/phone.ts` (`PHONE_QUERY`, `SHORT_QUERY`, `usePhone()`), which
  follows the screen as it turns or resizes. The Shell mirrors it to `<html data-phone>`;
  every phone rule of `styles.css` is in its last section, "Phone layout", under
  `:root[data-phone]`. A mouse never matches, so a computer's window of any size never gets
  a phone rule; components branch on `usePhone()` only where the structure changes. No
  setting or switch.
- **The app's window**: as a wide window's, the window does not scroll and each page's
  content does. The app is as high as the part of the window the human sees (LAD-109,
  `openspec/changes/phone-visible-height/`): fixed in place, at `window.visualViewport`'s
  height and its offset from the page's top, which `phone.ts`'s `usePhoneViewport()` puts
  on `<html>` as `--phone-height` and `--phone-top` (not `100dvh`, which on iOS 26 Safari
  is taller than the visible part, so Safari's bottom bar cut the composer off). Without a
  visual viewport (an old browser; no phone browser of today) the app is the viewport's
  height, and `body` does not clip it, the app being fixed. With the on-screen keyboard open the app shrinks to
  the part above it, the top bar kept at the screen's top: Safari ignores the viewport's
  `interactive-widget=resizes-content` (Android follows it) and pans the page instead.
  None of it on a computer: no variable, the app in the page's flow.
- **Menu**: the rail is hidden; Menu (☰, "Menu" or "Menu, N waiting", the Needs you count
  as a badge) starts the top bar and opens the rail from the left as a drawer, 260 px,
  with its names, over a dimmed page. An item, the dimmed page or Esc closes it, the focus
  back on Menu. The computer's collapsed rail (`lado.rail`) is neither read nor written.
- **Top bar**: one line, 52 px upright, 44 px sideways. On a session's page: Menu, the
  status dot, the title (or name) as a button cut with "…", the change feed's mark (a dot
  while live, "reconnecting…" otherwise; it opens the system panel), Stop.
- **The session's details**: the title opens a sheet over the page's bottom
  (`SessionDetails.tsx`, a modal `<dialog>` named by the session): the words of the
  status dot's mark (`needs you · 1 question`; LAD-108) and the run time,
  the whole folder, git, the kits with their versions, the CLI with its version and
  permission mode, and Rename (the title edited in place), Copy path, Copy link, All
  sessions. Close, Esc or a tap beside it closes it. It reuses the head's pieces (`GitFact`,
  `KitTip`, `CliTip`), so the two never say different things.
- **Sessions**: no strip; `/sessions` is the list across the screen, a session's page the
  session alone. `lado.sessionsList` is neither read nor written.
- **Tabs**: a session's four tabs without their icons fit 360 px; the Kits page's three too.
- **The chat**: the feed scrolls by itself, the waiting card (at most half the chat, no
  edge, no height of its own) and the composer stay at the bottom; the composer's text is
  16 px (Safari zooms into a smaller field) and its keys hint is not shown; so is the text
  of the card's fields that take files (an own answer, a skip's or a gate's comment; LAD-86). A flow event's
  line starts at the feed's left edge, its actor, chips and time on the first line, its
  text wrapped under them, whole. With the keyboard open the chat has no room for the
  card above the composer (LAD-126), so a field of the card (a gate's comment, an own
  answer, a skip's comment) taking the focus expands it, the focus kept in the field, and
  the field scrolls into the card's view, again whenever the card is laid out anew (the
  keyboard opening). An expanded card, by its button, a field or sideways, also hides the
  session's tabs and the Team row: it fills the page under the top bar. It stays expanded
  when the keyboard closes, until its fold button, Esc, or nothing waits. Needs you, which
  scrolls as a page, keeps the card as it is.
- **Sideways** (`short`): the chat's card is minimized by the layout (its tabs and one
  line), not by the human: `lado.waitingMinimized.<session>` is not written. A tab or the
  line shows it expanded over the chat; Esc or its fold button minimizes it again; turned
  upright, it shows whole. The Team row and the composer's "to" line are not shown.
- **Terminals**: no panel or strip. A team chip or Open terminal shows the terminal over
  the whole screen, its tabs and bar as when expanded, with **Close terminal** in place of
  Restore terminal; Close terminal or Esc (but in a terminal the human controls) puts it
  away and ends control, as a folded panel does. `lado.terminals` is neither read nor
  written. Typing into a terminal from a phone is a task of its own.
- **Tooltips on a tap** (any touch screen, `Tooltip.tsx`): a tap on a hint (a trigger that
  is no button or link: a kit, the CLI, git, the status dot) shows its tooltip at once, and
  the next touch elsewhere hides it. A button's or link's tooltip only names it: a tap
  never shows it, nor does the mouse the browser emulates for the tap.
- **Unchanged on a phone**: Needs you, Flows, Agents, Artifacts (the artifact panel over
  the whole screen below 464 px, as before), New session, Settings, Projects, Home, Report
  a bug: they fit and only lose the rail.

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
transitions as they happen, agent-to-agent messages behind the toggle Messages between
agents; the team as chips;
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
  gets a one-line copy from LADO of what the human writes to another agent, docs/design/agents.md) and **Finish…** (not for the supervisor); why it waits, or why it
  stopped ("Stopped: <reason>", its way out is Finish…); Branch,
  Work (asked when the page opens, when the agent leaves busy, to any status, the moment a
  turn's commits exist, and with Refresh; no comparison with `idle` alone, which would miss
  `background`, `web/src/status.test.ts`; feature/background-status; "as of"
  its time; no polling), Worktree, Task (first lines, Show more); its latest 10 messages
  from and to it, only in its lifetime (a name is used again: one request,
  `agent=<name>&since=<spawned_at>&limit=10`; the server and the feed's rule filter, the
  page does not), and
  **All in Activity**, which presses Messages between agents.
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
    is "you"), `<from> [outcome] → <to>` (a way back's outcome orange with the return
    icon, and the outcome's tooltip and the direction read out, by the chat's one rule: Flow
    events in Look of the feed), "flow-set" or
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
  card. A plain click on a row, or Enter on its name's link, opens its latest record in
  the panel over the list (The panel, below), which keeps its filters, search and scroll;
  closing it brings the focus back to the row's link. The link's address is the
  artifact's page, so Cmd/Ctrl-click or the middle button opens the page in a new tab.
  The tab is **Artifacts · N**, N the session's artifacts of all scopes (that live list;
  none: Artifacts); the session's view watches the list for it.
- **The page**: `/sessions/<name>/artifacts/<id>` (`paths.artifactPath`), "← Artifacts"
  above the viewer; it shows the latest record, or with `?record=<id>` the record an
  attachment keeps (for links: Copy link, a deep link, the row's link in a new tab, the
  panel's "Open in Artifacts tab"); its Open latest shows the latest record in the panel
  over it. An unknown id says "No artifact <id> in this session".
- **The viewer** (`ArtifactView.tsx`, one component for the page and the panel): its head
  is the type's icon and the full name, its actions (`ArtifactActions`: in the name line on
  the artifact's page, in the panel's top bar in the panel, The panel below), Download (the
  content with `?download=1`), Copy link (the page's address, with `?record=` when it is not the latest), Open in new tab
  (`target="_blank"`, `rel="noopener noreferrer"`) for every kind but other: for Markdown,
  text and an image the artifact's tab of the record shown (`paths.viewPath`, below), never
  the latest, so the link never changes; for HTML the content address, under the server's
  sandbox; for other none, as Download does what a tab would; the title; the author, how
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
  `--action-ground`. The body is `ArtifactBody`, the one renderer of the viewer and of the
  artifact's tab.
- **The artifact's tab** (`ArtifactTab.tsx`; decided with the human 2026-10-10, run
  feature/artifact-new-tab, mockup artifact `feature/artifact-new-tab/mockup-artifact-tab.html`):
  `/view/<session>/<record>`, a bare page outside the Shell (Structure) that shows only the
  record's body by `ArtifactBody`: no rail, top bar, name line, author, summary or
  buttons. It reads `GET …/records/{record}` once (a record never changes: no feed, no
  polling), says "Loading…" meanwhile, and its `document.title` is the artifact's full
  name. A refusal (an unknown record's 404, a 401, any other) shows the server's message
  in `<p class="problem" role="alert">`; it registers no `onDenied`, the Shell stays the one
  listener for a 401. Markdown in a reading column (at most 760 px, centred, padding
  32 px 24 px, 16 px at a phone's width); text and code with their line numbers and Wrap
  lines over the tab's width; an image centred and fitted to the tab, never upscaled, a
  click shows it at full size; HTML: the page goes on with `location.replace` to the
  content address, under the server's sandbox headers, with no frame inside a frame (the
  viewer links HTML there directly: only an address typed by hand comes this way); other:
  its facts and Download. The page is a region that scrolls itself, the window's height (a
  wide window never scrolls, as the Shell's), so a long record scrolls to its end and the
  text's code bar stays at its top. Its theme is the UI's (`main.tsx` applies the stored one first),
  on the UI's ground and ink. Its login is the browser's cookie, as for the session row's
  Open in new tab; the Desktop stage decides for both (Session list, the row's menu).
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
- **The panel** (`ArtifactPanel.tsx`): a chip or a row of the tab opens the viewer on the right over the page
  (`?view=<record>`, `paths.VIEW_PARAM`, on any of the session's tabs; on Needs you over
  Needs you, with its session, `?view=<record>&session=<name>`, `paths.VIEW_SESSION_PARAM`,
  LAD-48; elsewhere over the session's Activity tab), over a scrim; its close takes both
  parameters out; the page stays where it was. Esc, × or a
  click on the scrim closes it and the focus goes back to the chip (a row's link); Back
  closes it too (the view is a step of the history). Its top bar holds every button in one
  row, never wrapped (decided 2026-10-13, LAD-43, mockup artifact
  `task/lad-43/mockup-panel-buttons.html`, option 1): on the left "Open in Artifacts tab"
  (the Artifacts tab's icon; the artifact's page with that record) and the viewer's
  actions, Open in new tab, Download and Copy link; on the right Expand and ×; the
  viewer's name line under it holds no button. A panel narrower than 560 px (its width, or
  the window's when it takes the whole screen) shows the actions as 28 px icon buttons, the
  label as their name and the UI's tooltip; wider, as icon and label with no tooltip (Copy
  link is an icon button either way). While the record loads or fails, the bar holds Expand
  and × only. Open latest in it shows the latest record in the same
  panel. Its width is the human's (decided 2026-10-11, feature/artifact-panel-width,
  mockup artifact `feature/artifact-panel-width/mockup-panel.html`, version 4): its left
  edge is the shared `Splitter` (drag, ←/→, a double-click for 620 px; a drag captures the
  pointer, so it goes on over an HTML artifact's frame), with a grip in its middle (a
  10×34 px pill with three dots, `--action` on hover, focus and drag; it takes no pointer
  events), from 400 px to the room, the window's width less 64 px (a strip of the page stays
  on the left, and a click there closes the panel), 620 px at first. Expand, before ×,
  fills the room and becomes Restore width, back to the width chosen before; a drag or a
  key while expanded ends expanded. Unlike the expanded terminal, Esc closes the panel, so
  Expand's title has no "(Esc)". The width and expanded are remembered per browser under
  `lado.artifactPanel`, one value for every session; when the window narrows the panel
  narrows with it and gets its width back when it widens. A window with less room than
  400 px (under 464 px wide, a phone) shows it on the whole screen, with no edge, grip or
  Expand; the page's other splitters hide at ≤ 900 px, this edge does not.
- **A gate's note** (`GateCard.tsx`): its chips under the note before the gate, then the
  artifacts the gate reads; an artifact the note carries is left out of those
  (`runs.gate_reads`), so each shows once.
- Not in it: syntax highlighting, a record's history and a diff, uploads in this tab (the
  human attaches files in the composer: Files in the composer), deleting an artifact,
  server-side filters and pages.

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
  then the kits as a grid of cards (Card, below). The **Marketplaces** block is on the
  right on every tab, under the grid on a page narrower than 900 px.
- **Installed**: the kits of lado.db's `kits` table, then the built-in ones (read only,
  no buttons, no ⋯). A card: the name, its tag or version, `→ vX` and ↑ after a check found vX, the
  description, its source (the marketplace it was added from, `<name> (removed)` when that
  one is gone, counted by the UI from the two lists; git; folder; built-in), its roles,
  skills and flows, its address or folder in the name's title, the core's problem when it
  does not load; in ⋯ Update… (a kit from git) and Remove….
- **Available**: each kit the enabled marketplaces list that is not installed, from their
  clones (no network): `marketplace.yaml` for the names and addresses, `index.json` for
  the rest (docs/marketplaces.md, index.json: version 1), only the name and address without an entry
  ("No description in the index"); + by the version and Install… in ⋯.
  An installed kit is in Installed and a new version of it in Updates, never here: the
  list and the tab's count are one set, the offers whose `installed` (the server's) is
  false, before the search and the source chips. When every listed kit is installed, the
  tab says "All kits of your marketplaces are installed", how many kits each marketplace
  lists, and links to Installed. A fresh LADO_HOME says no marketplace is fetched yet, with
  a button to update each; nothing is cloned by itself. (Decided with the human, task
  feature/kits-page-polish, 2026-10-05.)
- **Card** (decided with the human 2026-10-09, task feature/kits-cards, in place of the
  list of rows of feature/kits-page: variant B of the run's `mockup-cards.html`, the update
  as U2 of `mockup-update.html`, Install as AV1 of `mockup-available.html`): every tab
  shows its kits as cards in a CSS grid, `repeat(auto-fill, minmax(min(220px, 100%),
  1fr))` with a 10 px gap, one column on a narrow page by itself; the cards of a row take
  the same height, the footer at the bottom. A card (`KitCard.tsx`, one component for
  every tab): `--panel`, a `--line` border, radius 10 px.
  - Top: the mark: the first letters of the name's first two parts (split at `-` and `_`;
    else its first two letters) in mono on `--action-ground` in `--action`, a built-in
    kit's on `--raised` in `--muted`; its colour says nothing. Right of it the name, mono,
    one line cut with "…", the whole name and the git address or folder in its title;
    under it the **version line**: the version as a tag (Available: the index's `latest`,
    none without an entry), the card's action, then the badges (`folder missing`). The
    line wraps: what does not fit goes to a next line, inside the card at its narrowest.
  - The card's action, one at most, by the version (`KitCard`'s one `action` prop draws
    both): **U2**, only when Check for updates found a newer version vX of a git kit:
    `→`, vX as a tag in `--action` on `--action-ground` and a 22 px square button ↑ in
    `--action`, named and titled `Update <name> to <vX>…`; it opens the Update window
    planned for vX (`plan-update` with that tag), not for the latest at that time. **AV1**,
    on every Available card: the same button with +, named and titled `Install <name>
    <vX>…` (`Install <name>…` without a version), which opens the Install window at the
    plan. The `vX available` badge is gone.
  - The description cut to two lines by CSS, with **more** only when it is cut (measured,
    again on a resize) and **less**, which makes that card and its row taller; the whole
    text on hover, not remembered. An offer without a description: "No description in the
    index" in muted italics. The core's problem, red-edged, under it.
  - Footer: the source as a dot with its text (the dot by its kind: official `--done`,
    another marketplace, also a removed one, `--action`, git a `--muted` dot, folder a
    `--muted` ring, built-in an empty circle) and the counts, number first ("4 roles 71
    skills 2 flows", none of a zero). The address is not on the card's face.
  - ⋯ (`RowMenu.tsx`, the session row's too: Launch and session control), `Actions for
    <name>`, in the top-right corner: a git kit Update… (Update to vX… when a check found
    vX), Remove…, Copy address; a folder kit Remove…, Copy folder; Available Install…,
    Copy address; a built-in kit has none. Copy says "Address copied" or "Folder copied"
    in the card, through `Copy.tsx` (the text shown selected when copying fails).
- **Updates**: only after Check for updates (`kits.outdated`, the network); the time of
  the check is kept in the page, not stored; no check in the background. The kits with a
  newer version, as the same cards with U2; above the grid, the kits it did not check say
  why and a moved tag is a warning.
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
  the plan again. An Available card's + and its Install… start at the plan. A refusal of the core
  shows its words with Back.
- **Update**: the core's plan for the latest version (Update…), the one a card's ↑ or
  Update to vX… names, or another one chosen from the repository's tags (`POST
  /api/kits/{name}/plan-update`; the list of versions is the first plan's). Decided with the human
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
green (`--done`) also means what works now, the session list's Running group, since
task feature/flows-list-states (2026-10-07) the Flows overview's Active group, and since
feature/session-head-topbar (2026-10-08) the dot of a session's head (since LAD-108 the
list's working dot), where
`--danger` marks a session that needs an action (tmux gone, loop down). (Kits, 2026-10-05) A quiet ground for the action
colour, a kit's mark (#E8EFFC / #1C2840). A kit's source dot: official `--done`, another
marketplace `--action`, always beside the source's text. Every
text colour has a contrast of at least 4.5:1 on its grounds in both themes; a unit test
(`web/src/tokens.test.ts`) checks it.

**Notes of the New session window** (LAD-120, 2026-10-21): a warning's panel is amber,
`--warn` on `--warn-ground` (#8A5A00 on #FDF5DC / #E0B04A on #2F2814), apart from the orange
of what waits for the human by hue and by place; a refusal's panel is `--danger` on
`--danger-ground` (#FDECEB / #3A1D1B). The panels' text is `--ink`, a refusal's hint
`--muted`; the test checks each of them on both grounds.

**Avatars** (task feature/chat-look, 2026-10-07; Look of the feed): six colours,
`--avatar-1` … `--avatar-6` (indigo, green, violet, magenta, teal, olive; light #4F5BD5,
#1F7A5C, #8A4FC7, #B23A78, #0E7490, #6B6B1F with a white letter, dark #9AA6FF, #5CC9A0,
#C49AF0, #F08CC0, #5CC4E0, #C8C56A with a #111317 letter, `--on-avatar`), one chosen from
the agent's name by a hash, so an agent keeps its colour; none is orange or the action's
blue. The human's avatar is "Y" on `--action` (`--on-action`), a gate's a flag in
`--muted` on `--raised`. A known limit: roles with the same first letter (`developer`,
`designer`) differ only by colour, and with six colours that may be the same; the full name
stands beside it. Orange stays only for open questions and gates and the gate hint.

**Run colours** (feature/team-run-frames, 2026-10-11; Team's run frames): four colours,
`--run-1` … `--run-4`, on purpose four of the avatars' hues (`--avatar-3`, `-5`, `-4`,
`-6`: violet, teal, magenta, olive), written as their own literal pairs so the contrast
test checks them on `--panel` and `--ground`. They keep out orange and the action's blue,
as the avatars do, and leave out the avatars' green, which is close to busy. A run
coloured in the chat one day would sit next to avatars of the same hues.

**Artifacts** (feature/artifacts-ui, 2026-10-07): a type's icon is a 28 px tile (20 px on a
chip) on `--raised`, coloured by kind: Markdown `--action` on `--action-ground`, HTML
`--avatar-3`, images `--avatar-2`, text and code `--avatar-5`, anything else `--muted`. A
chip is 30 px high, a `--line` frame on `--panel`, `--action` on hover; "changed since ·
open latest" is joined to its right on `--raised` with a `--action` dot (below 600 px under
it). The panel is `--panel` with a shadow (`--shadow`) over a scrim (`--scrim`); an image
at full size over `--lightbox`; an HTML frame's ground is `--frame-ground` (white, as a
page without a background). Orange is never an artifact's.

**Files in the composer** (feature/chat-attachments, 2026-10-08): a file's chip is 44 px
high, a `--line` frame on `--panel`, a 36 px thumbnail or type tile; a failed upload's chip
has a `--danger` frame on a light `--danger` wash and its reason in `--danger`. The
crossed-out eye is a 17 px `--panel` circle with a `--line` frame on the tile's lower right
corner, the icon in `--muted`; its hint is the UI's tooltip, the light card (`--panel`,
`--line` frame, `--shadow`, its arrow at the eye; Tooltips below). The drop zone is the composer's frame dashed in `--action` on
`--action-ground`. A preview of the human's image is at most 240 × 180, a `--line` frame
on `--raised`. No orange.

**Tooltips** (fix/tooltip-arrow, the human's decision 2026-10-08): every tooltip of the
UI (`Tooltip.tsx`) is the light card, `--panel` with a `--line` frame and a soft
`--shadow`, and an arrow to its trigger: an 8 px square turned 45° in the card's fill and
frame, on the top edge under the trigger and on the bottom edge over it (`data-side`),
painted over the card's border so the frame runs on with no seam. It points at the
trigger's horizontal centre (`--arrow-x`), also when the window's edge pushes the card,
and stays 16 px from the card's ends, off its rounded corners; for a narrow trigger the
card starts left of it so the arrow still reaches its centre. The card is 11 px from its
trigger, so the arrow never touches it.

**The cards' buttons** (feature/question-answer, 2026-10-10, mockup B v3; the waiting
card, LAD-28): in the form of a gate's panel (`form.answer`) and in the waiting card (its
options `.waiting-option` and its Send row `.waiting-send`) every button is 32 px high,
14 px, radius 8, by one rule each (`.answer .primary, .answer .quiet`; `.waiting-send
.primary, .waiting-send .quiet`), and the fields take radius 8 with them; the global
`.primary` (32 px, radius 6) and `.quiet` (28 px, 13 px) stay as they are elsewhere (one
UI-wide scale: BACKLOG.md). The main action is `.primary`, the others `.quiet`; a
question's options are neutral until picked, Other… and Skip in `--muted`.

**Time**: every time of day in the UI is written in 24 hours (`clock()`, `hourCycle:
"h23"`), whatever the browser's locale.

**Tabs** (decided with the human 2026-10-06, task feature/session-tabs, mockup
`.lado/mockups/session-tabs/index.html`, variant F "folder tabs"): every tab bar of the UI
has one look, the terminal column's type, from one set of rules in `styles.css` (each place
keeps its own markup: links in a `nav`, or the terminals' `tablist` with ×). `.tab-bar` is
the band that holds and scrolls the tabs: `--raised`, from edge to edge of its column (the
session's through `--main-pad`, the same variable as `.session-main`'s side padding), a 5 px
ground above the tabs. The session's band starts right under the top bar (or, in a narrow
window, right under the session list stacked over the session), level with the terminal
panel's band, and so do their selected tabs: `.session-main` has no top padding (LAD-42,
2026-10-14). Only two things stand above the band, each 12 px under the top bar and 10 px
above the tabs: the start notice (Launch and session control) and the alert of a
`?terminal=` agent not in the session (`<agent> is not in this session`). `.tab-item` is the framed tab: IBM Plex Mono 13 px, `--muted`
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
