# LADO single-machine couplings and seams for remote execution (R1)

Research of the repository at `main` 033705e (2026-10-18), read-only. Paths are relative to
the repository root. "Remote" below means: the agent CLI process (and its worktree)
runs on a machine other than the one holding `LADO_HOME/lado.db`, the tmux server and the
UI server: a Kubernetes pod, a remote Docker host, a VM or a sandbox service.

## 0. TL;DR

LADO today is a **set of cooperating local processes that share three things directly:
one SQLite file, one tmux server and one filesystem (LADO_HOME + the repository with its
worktrees)**. There is no daemon that owns state; every process (CLI, UI server, session
loop, each agent's `lado mcp`, each hook invocation) opens `lado.db` itself, calls `tmux -L
lado` itself and runs `git` on absolute paths itself. Control-plane logic (spawning workers,
creating worktrees, delivering messages by typing into tmux) runs **inside processes that are
children of the agent CLI** (`lado mcp`, `lado hook`). That is the deepest coupling: to move
an agent off the machine, those children must stop being "LADO" and become thin clients of
a LADO that stays put.

The good news: the coupling is concentrated. The tmux surface the core uses is ~8
functions (`tmux.py`), the hook/MCP entry points are two commands (`lado hook`, `lado mcp`),
the provider interface already separates "what to launch" from "how", and the design docs
already reserve seams for exactly this (feed `Source`, artifact `Store`, auth layer,
`NoTerminal` for agents without a tmux window, UI principle "the server's address is
configured, not assumed").

## 1. Process map today

```
 human ── browser ──HTTP/SSE/WS──> lado server (uvicorn, FastAPI)          [LADO host]
                                     │ reads lado.db (journal), runs runtime.* in-process,
                                     │ opens pty + `tmux attach` for terminals, runs git
 human ── terminal ── lado CLI ──────┤ (start/stop/answer/attach) same
                                     ▼
                        LADO_HOME/lado.db (SQLite, WAL)   LADO_HOME/{agents,cache,artifacts,loop,...}
                                     ▲
 lado loop <session> (detached, flock) ── sweep every 2 s, tmux list-windows, send-keys
                                     ▲
 tmux -L lado server ── session <name> ── window per agent:
     python -m lado.agent_env env.json <cli argv>  →  claude | codex | kilo | opencode
           │ cwd = repo (supervisor) or repo/.lado/worktrees/<session>/<worker>
           ├── stdio child: python -m lado.cli mcp   (LADO_SESSION/LADO_AGENT env) → lado.db, tmux, git
           ├── hook children: python -m lado.cli hook <event> --session --agent --instance → lado.db, tmux, git
           └── kit MCP servers via python -m lado.mcp_exec (secrets from env)
```

All arrows into `lado.db` are direct file opens; all arrows into tmux are `tmux -L <socket>`
subprocesses; all git is `git -C <absolute path>`.

## 2. Couplings, one by one

### C1. Process launch and lifecycle: tmux

- **Where**: `src/lado/tmux.py` (whole module; `socket()` :69, `_run_once` :125,
  `new_session` :165, `new_window` :186, `has_session` :190, `kill_session` :200,
  `kill_window` :215, `list_windows` :232, `send_text` :239, `popup` :258, viewers :341-385).
  Callers: `runtime.start_session` :750 (`tmux.new_session(... before_attempt=gui_session.ensure_server)`),
  `runtime.spawn_worker` :870 (`tmux.new_window(session, worker, worktree, cmd)`),
  `runtime.close_worker` :1238, `runtime.stop_session` :2368-2402, `stop_for_container` :2437-2458,
  `_kill_for_migration` :2519, `_mark_stopped` :2538-2555, `runtime.session_status` :1020-1028,
  `runtime.check_windows` :2205-2223, `runs._popup` :834-842, `cli.py` :958, :969, :1252-1256
  (`lado attach`), `uninstall.py` :416-429, `gui_session.py` :138-205.
- **How it works**: one private tmux server per user (socket `lado` or `LADO_TMUX_SOCKET`);
  a LADO session == a tmux session; an agent == a window named after it. A window's command
  is `python -c <loader> lado.agent_env <config>/env.json <argv>` (`runtime._command`
  :2809, `agent_env.command` :375), which replaces the tmux server's environment with the
  resolved one and execs the CLI. Liveness: "the window exists" (`check_windows`, the loop's
  only tmux call per pass) and "the tmux session exists" (`session_status`). Kill = kill
  the window or session. The supervisor's window being the last one takes the tmux session
  with it (agents.md, session loop).
- **Remote breaks**: every one of these is a local subprocess against a local socket. A
  pod/VM has no window on this tmux server; `has_session`/`list_windows` say "gone" and
  the loop would mark the agent `stopped` within two passes (`agent_ended`, :2174).
- **Candidate abstraction**: an `ExecutionBackend` / "placement" interface with exactly the
  verbs the core uses: `start_session_host(session)`, `launch(agent, cwd, argv, env_file)`,
  `alive(session) -> set[agent]`, `kill(agent)`, `kill_session(session)`,
  `type_text(agent, text)`, `open_terminal(agent, mode)`. The local backend is today's
  `tmux.py` calls verbatim. A remote backend runs **tmux on the remote node** (keeps
  everything the providers rely on: TUI, typed delivery, `/resume`, the human's terminal)
  and drives it through a node agent (or `ssh host tmux ...`, `kubectl exec`, Docker
  `exec`). Keeping tmux on the far side is the cheapest way to preserve the provider
  contracts that were checked by hand (bracketed paste, Enter timing, copy-mode cancel).

### C2. Message delivery: typed into a window, confirmed by hooks

- **Where**: `runtime.hand_over` :1902-1920 (`tmux.send_text` :1919), `runtime._sweep_sent`
  :1949-1960 (`tmux.send_text` :1958), `runtime.sweep` :1923, `runtime._deliver` :1874,
  `runtime._plan` :1973, `tmux.send_text` :239-255 (display-message pane_in_mode,
  load-buffer, paste-buffer -p, 50 ms sleep, send-keys Enter). Retry delays
  `RETRY_DELAYS` :53-58, `HOOK_OUTPUT_WAIT/BACKSTOP` :71-74. Protocol: docs/design/agents.md
  lines 295-384.
- **How it works**: the queue is rows in `messages` (`pending -> sent -> delivered/read`,
  or `failed/dropped`). Two channels: `typed` (pasted into the window, confirmed when the
  prompt-submit hook sees the line, `state.confirm_sent`) and `hook_output` (returned as the
  turn-end hook's stdout, confirmed by `Event.continued` or by Kilo/OpenCode's
  `chat.message`). Whoever makes the agent idle takes the queue in the same transaction
  (`state.take_pending(..., become=)`), so senders (`lado mcp` of another agent, the UI
  server, the CLI), hooks and the loop all may type into the window. The typing therefore
  happens **in whatever process noticed** — often another agent's `lado mcp` or this
  agent's own hook.
- **Remote breaks**: (a) the `typed` channel needs a local tmux pane; (b) the race-free
  design depends on a single transactional store reachable from the sender, the hook and the
  loop; (c) `agents.seen_at` (sweep's "did any hook run since the paste") compares wall
  clocks of different processes — fine on one machine, needs a single clock (the control
  plane's receipt time) across machines.
- **Candidate abstraction**: keep the queue and `_plan` exactly where they are (control
  plane); replace only the last mile `tmux.send_text(session, name, text)` with
  `backend.type_text(agent, text)`. The `hook_output` channel already works with no
  tmux at all as long as the hook can reach the control plane synchronously (C3).

### C3. Hooks: how status reaches LADO

- **Where**: `providers/base.py` `hook_argv` :277-288 (`python -m lado.cli hook <native>
  --session --agent --instance`), `hook_command` :291; Claude Code writes them into
  `settings.json` (`providers/claude.py` :159-172), Codex into `config.toml` `[hooks]`
  (`providers/codex.py` :180, `_handler` :409, `_hooks` :450), Kilo/OpenCode through the JS
  plugin that `spawn`s the argv (`providers/opencode_plugin.js` :10-16).
  `src/lado/hooks.py`: `main` :266-297 reads stdin, `state.get_agent`, `provider.parse_event`,
  `handle` :141-223, prints the output; `_wait_for_mcp` :51 polls `lado.db` every 20 ms
  up to 20 s; `_fingerprint` :89 runs git on `me.cwd` and the session's repo for read-only
  agents; logs to `LADO_HOME/hooks.log` :65; `telemetry.record` to `errors.jsonl`.
- **How it works**: a hook is **a fresh Python process per event, which writes SQLite
  directly** and may also type into tmux (`_idle` -> `runtime.hand_over` -> `send_text`)
  and run `runtime.sweep`, `runtime.turn_failed`, `runtime.agent_ended`, i.e. full
  control-plane logic. Its stdout is the hook output (the Stop hook's `block` reason with
  the queued messages). It runs under the CLI's time limit (`TURN_END_HOOK_TIMEOUT` 60 s,
  base.py :274; `hooks.deadline` :37). The `instance` argument fences off hooks of earlier
  launches (`main` :276).
- **Remote breaks**: no `lado.db` (or only an unsafe network copy; see C7), no tmux, no
  LADO_HOME for logs, and `sys.executable` of the LADO host in the argv (`interpreter.run_module`)
  does not exist on the node.
- **Candidate abstraction**: the hook command becomes a **thin forwarder**: `lado-agent hook
  <native>` (or a stdlib-only script) that POSTs `{session, agent, instance, native,
  payload}` to the control plane and prints the response body. Server side, the existing
  `hooks.main`/`handle` run unchanged (parse_event is pure). Two subtleties: `hold_first_turn`
  waits for `MCP_READY` (polling inside the hook — becomes a long-poll/wait on the server);
  the read-only fingerprint (`fingerprint.take(me.cwd, repo, budget)`) needs the worktree
  and must be taken **on the node** and sent along with the event (split `_turn_start`/
  `_turn_end` into "node computes fingerprint, server compares"). Latency budget: the turn
  end hook must answer well inside 60 s; an HTTP round trip is fine. Claude Code may also
  support HTTP-type hooks natively (unverified against `TESTED_VERSION`, check by hand);
  Codex and the OpenCode plugin need the command shim anyway, so the shim is the neutral
  choice.

### C4. MCP server transport and where it runs

- **Where**: `src/lado/mcp_server.py` (docstring :1-5 "Each agent's CLI starts one over
  stdio"; `main` :437-441 `build(...).run("stdio")` from `LADO_SESSION`/`LADO_AGENT`/
  `LADO_INSTANCE` env); `providers/base.py` `mcp_server` :296-299 and `agent_env` :224-237
  (`LADO_HOME`, `LADO_SESSION`, `LADO_AGENT`, `LADO_TMUX_SOCKET`, `LADO_ENV_DIR`);
  `_Server.list_tools` :45-53 records `MCP_READY`. Claude config `mcp.json`
  (`providers/claude.py` :142-157), Codex `_mcp_servers` (codex.py :464), Kilo/OpenCode
  config content (opencode_family.py).
- **How it works**: one stdio subprocess per agent, child of the CLI, importing all of
  LADO. Its tools call `runtime.*`, `runs.*`, `artifacts.*` in-process: `spawn_worker`
  (git worktree add, provider config files, `tmux new-window`), `send_message` (queue +
  type), `flow_*`, `start_session` (spawns a whole new session and its loop,
  `runtime.start_approved_session` :1759), `write_artifact` with `file=` reading a path
  from the agent's working folder. Identity = environment variables, trusted as is.
- **Remote breaks**: the same as hooks, plus `write_artifact(file=...)` and
  `read_artifact` must read/write the node's files, not the control plane's. Identity by
  env var is not authentication once the process is on another host.
- **Candidate abstraction**: two options, both keep the tool code server-side:
  1. **Remote MCP over HTTP** (streamable HTTP) hosted by the control plane at
     `/mcp`, with a per-agent bearer token derived from `(session, agent, instance)`.
     Claude Code (`type: http`), Codex (`url =` streamable HTTP) and OpenCode/Kilo
     (`type: remote`) all have a remote MCP form (verify each on its tested version);
     `McpServer` (base.py :97) needs a `url`/`headers` variant. Tools that touch the node's
     filesystem (`write_artifact(file=)`) need a small node-side helper or the agent sends
     `content` instead.
  2. **stdio proxy**: keep `lado mcp` as a stdio process on the node that forwards
     JSON-RPC to the control plane. Simplest for the providers (nothing changes in their
     configs) and lets the proxy read local files for `file=` arguments.
  Either way `MCP_READY` becomes "the CLI listed tools" as seen by the server.

### C5. The session loop

- **Where**: `src/lado/loop.py` (`start` :119-129 `Popen(lado loop <session>,
  start_new_session=True)`, `take_lock` :82-93 `fcntl.flock` on `LADO_HOME/loop/<session>.lock`,
  `running` :96, `run` :143, `tmux_gone` :70); `runtime.check_windows` :2205;
  `runtime.session_status` :1020 (`loop.running`).
- **How it works**: a detached local process per session; liveness by flock; each pass:
  `tmux list-windows`, `runtime.sweep` (retype/fail messages, due resumes), telemetry kick.
- **Remote breaks**: the loop itself can stay on the control plane; what breaks is its
  window check (C1) and its typing (C2). The flock-based "one loop per session" works only
  where the loop runs (control plane), which is fine.
- **Candidate abstraction**: none needed for the loop itself; it calls `backend.alive()`
  and `backend.type_text()`. For remote nodes, liveness should be a **heartbeat/lease**
  (node agent reports its windows every N s) instead of polling, with "missing in two
  passes" kept as the rule.

### C6. Git: repository, worktrees, branches, merge

- **Where**: `runtime._run_git/git` :367-385 (`git -C <repo>`), `spawn_worker` :827
  (list branches), :841 worktree path `repo/.lado/worktrees/<session>/<worker>`, :860
  `git worktree add -b`, undo :884-887; `runs.start` :84 and :89 (run worktree),
  `runs._restore_worktree` :431-443, `runs._close`/`_unfinished` :892-955 (merge-base
  `--is-ancestor`); `runtime.gone/tip/remove_work/work_of` :1152-1338 (`git status
  --porcelain`, `rev-list --left-right --count HEAD...<tip>`);
  `exclude_worktrees` :2864 (writes `.git/info/exclude`); `session_worktrees` :2601;
  `fingerprint.py` (read-only check). UI: `server/models.py` :1297 calls
  `runtime.work_state` synchronously for agent details. Clone: `clone.py` (`DEFAULT_PARENT`
  `~/lado` :30, `LADO_REPOS` :31, `clone` :436); scratch repos `scratch.py`.
- **How it works**: the supervisor runs **in the human's checkout itself** (`agent.cwd =
  repo`, runtime.py :692-694); workers and runs get linked worktrees inside it. Because linked
  worktrees share one object store and ref namespace, **a worker's commit is instantly
  visible to the supervisor**, which merges with a plain `git merge lado/<s>/<w>` in its
  own shell (LADO's instructions; `runs.py` :907-908). `finish_worker` refuses until
  `merge-base --is-ancestor` says merged. Docker research 5.3 notes absolute paths in
  `.git` files (git < 2.48), hence the same-path mount in the image.
- **Remote breaks**: completely. A worker on another machine has no linked worktree of
  the human's repo; its commits are invisible to the supervisor and to `work_of`; the
  control plane cannot `git status` its worktree; `finish_worker` cannot check or remove
  it; the UI's work state cannot be computed. Absolute paths stored in `agents.cwd`,
  `runs.worktree`, `sessions.repo` are host paths.
- **Candidate abstraction**: a `Workspace` interface: `create(session, agent|run, base_ref)
  -> handle`, `state(handle) -> WorkState`, `remove(handle, force)`, `exists(handle)`,
  plus a **sync** step for the branch. Local implementation = today's linked worktree.
  Remote implementation: the node gets a **clone** (from a git remote the node can reach,
  or a `git bundle`/fetch over the node agent), works on `lado/<s>/<w>`, and the branch is
  brought back by push to a shared remote (origin, or a bare repo the control plane
  exposes) or by LADO fetching from the node into the human's repo (`git fetch
  node:<branch>`), at turn end or on `finish_worker`. `WorkState` queries become node RPCs
  or are computed after the fetch. Merge semantics stay "supervisor merges a branch",
  only now after a fetch. This is the largest functional change for "remote worker only".

### C7. SQLite: one file, many writers

- **Where**: `state.py` docstring :1-5 ("Several processes use it at once ... every call
  opens its own short-lived connection and SQLite does the locking"); `_open` :1147-1152
  (`timeout=10`, `journal_mode = WAL`, `foreign_keys`); `connect` :1155-1190 (schema check,
  never migrates); ~30 `BEGIN IMMEDIATE` transactions (e.g. :1279, :1372, :1457 ...
  :3228); `SCHEMA_VERSION = 31` :22; change journal `changes` written by triggers (feed).
- **Who writes**: the CLI, the UI server (`write_as_human`, answers, start/stop), each
  agent's `lado mcp`, each hook process, the session loop, `mcp_server.list_tools`
  (MCP_READY). Correctness of delivery relies on single-transaction take-and-mark
  (`take_pending(become=)`), conditional updates (`state.wait/resume`, `agent_ended`).
- **Remote breaks**: SQLite WAL needs shared memory (`-shm`) on one host; it is unsafe on
  NFS/SMB and impossible across pods. A remote process cannot be a writer.
- **Candidate abstraction**: do **not** make SQLite remote. Make the control plane the
  only writer and expose the state operations remote processes need as an RPC surface
  (hook event, MCP tool call, heartbeat, fingerprint result). The `state` module API is
  already the de-facto RPC boundary: hooks and MCP call a few dozen `state.*`/`runtime.*`
  functions. A Postgres backend is a separate, much larger question (raw SQL across 3355
  lines of `state.py`, triggers for the journal) and is not needed for remote agents.

### C8. Filesystem: LADO_HOME and per-agent config folders

- **Where**: `state.home/home_path` :1131-1140 (`LADO_HOME` or `~/.lado`);
  `providers/base.py` `configs_root/config_path/config_dir` :240-264
  (`LADO_HOME/agents/<session>/<agent>`), `link_skills` :302-313 (symlinks to skill
  folders); per provider: Claude `mcp.json`, `settings.json`, `prompt.md`,
  `skills/.claude/skills/*` symlinks, `--add-dir` paths (claude.py :140-201); Codex
  `CODEX_HOME = config dir` with `config.toml` (mode 600) and `skills/` (codex.py :193-216);
  Kilo/OpenCode config **as env var content** (`KILO_CONFIG_CONTENT`,
  `OPENCODE_CONFIG_CONTENT`: kilo.py :40-44, opencode.py :55) but `skills.paths` pointing
  at a local folder (opencode_family.py :115-116); `env.json` with the whole resolved
  environment incl. secrets (agents.md :48-52); lead skills/files `runtime._write_lead_skills`
  :2721; read-only baseline `hooks.BASELINE` in the config folder (hooks.py :69-87).
  Kits and packs: `gitcache.root()` = `LADO_HOME/cache` (gitcache.py :50), installed kits in
  `lado.db`; skill folders resolved to paths there (`runtime._spec` ~:2688). Logs:
  `hooks.log`, `loop.log`, `errors.jsonl`, `server.log`, `server.json`, `server-token`.
- **How it works**: `launch_command` *writes files and returns argv with absolute local
  paths* (config files, skills, `sys.executable`). `state.home()` is called from ~30
  sites in 18 modules.
- **Remote breaks**: all those paths are meaningless on the node; the skill symlinks point
  into the control plane's cache; `env.json` would have to be shipped (it holds secrets).
- **Candidate abstraction**: split `Provider.launch_command` into **render** (pure: a
  `LaunchBundle` of `{relative path -> bytes, mode}`, argv with placeholders such as
  `${CONFIG_DIR}`, `${LADO}`, env) and **materialize** (backend: write the bundle under a
  root on the target and substitute placeholders). Skills become bundle content (copied, or
  a content-addressed sync of the kit cache to the node) instead of symlinks. This also
  matches the AGENTS.md rule "no hardcoded paths; `${KIT_DIR}`/`${SKILL_DIR}`".

### C9. Agent environment and credentials

- **Where**: `agent_env.py` (`resolve` :98 runs `$SHELL -ilc` locally per launch,
  `base_path` :212, `outside` :116 reads `LADO_ENV_DIR` files, `command` :375 writes
  `env.json` and the window command, `main` :389 execs); `runtime._base_env` :2769,
  `_check_commands` :2777 (kit `expects.commands` checked on the *local* PATH),
  `_launch_env` :2786, `_outside_warnings` :2794. Provider auth: Claude's macOS keychain
  (`claude.py` `keychain_login` :247, `LOGINS` :93), `gui_session.py` (whole module: tmux
  server born in the GUI audit session via launchd, `ensure_server`), Claude trust file
  `~/.claude.json` read by `_trusted` (claude.py :312-320) for `first_hook_blocker`; Codex
  reads the user's `~/.codex/config.toml` (`_user_config` codex.py :278) and copies
  trust/hooks state; Codex `auth.json` is *not* carried into per-agent `CODEX_HOME` (open
  item, docker-install.md :200-210, plan T15); OpenCode/Kilo logins in
  `~/.local/share/{opencode,kilo}/auth.json`. Kit MCP secrets: `mcp_exec.py` (values only in
  the agent's env, never on disk).
- **How it works**: the environment, PATH and credentials of agents are those of **the
  human's login shell on this machine**; logins live in this user's home (or keychain).
- **Remote breaks**: the node has its own shell, PATH, CLIs and (no) logins. Checks run on
  the wrong host (`_check_commands`, `first_hook_blocker`, `keychain_login`,
  `gui_session`). Credentials must be provisioned to the node explicitly.
- **Candidate abstraction**: env resolution and the pre-launch checks become backend
  methods executed on the target (`backend.resolve_env()`, `backend.check_commands()`,
  `provider.first_hook_blocker` evaluated node-side). Credentials: reuse the **outside
  folder** contract (`LADO_ENV_DIR`, one file per variable) — it maps 1:1 onto a
  Kubernetes Secret mounted as a volume, a Docker secret or a VM's cloud-init file. Token
  logins are required remotely (`CLAUDE_CODE_OAUTH_TOKEN`, API keys); the macOS keychain
  path is irrelevant there.

### C10. Terminals in the UI and `lado attach`

- **Where**: `src/lado/terminal.py` (docstring :1-19; `open` :74-95 makes a viewer tmux
  session with `link-window`, `_attach` :98-120 `pty.openpty()` + `tmux attach` subprocess,
  `Terminal` :132, `ended` :200, `close_viewers` :214); `server/terminals.py` (WebSocket
  protocol: binary output frames, JSON `size`/`error`/`input`/`resize`, close codes 44xx/45xx,
  `serve` :42, reads in a thread); app route `app.py` :1075-1078. `lado attach`:
  `cli.py` :1252-1256 (`tmux attach-session`). Gate popups: `runs._popup` :834 →
  `tmux.popup` (display-popup on attached clients).
- **How it works**: the UI server process itself runs a local `tmux attach` on a pty and
  pumps bytes over the WebSocket. Already designed so that "an agent without a terminal
  (ACP) raises NoTerminal" and "the terminal stream comes from where the agent runs"
  (ui.md principle 4).
- **Remote breaks**: no local tmux window to link/attach.
- **Candidate abstraction**: `backend.open_terminal(agent, mode) -> byte stream + write +
  resize` — exactly the `Terminal` object's surface. Remote: the node agent does the same
  viewer/attach locally and relays bytes over its own WebSocket/gRPC stream to the UI
  server (or `ssh -t host tmux attach` / `kubectl exec -it`). The WebSocket protocol to the
  browser is unchanged. `lado attach` for remote agents would go through the same relay
  (or print the `ssh`/`kubectl exec` command). Popups: tmux-only and optional; for remote
  sessions they simply have no clients (already returns 0).

### C11. The UI server: binding, auth, API

- **Where**: `server/auth.py` (token in `LADO_HOME/server-token`, cookie
  `lado_token_<port>`, Bearer, Origin check `Guard.check` :121, `renew` :98; docstring
  says plain HTTP risk "until a real login and TLS replace this module"); `server/run.py`
  (`serve` :316 uvicorn, `--host` any IPv4, `Listening` ~:180-250, `public_host` :157
  `LADO_PUBLIC_HOST`, container note :41-45, `server.json`); `server/app.py` routes
  :364-1083 (~70 endpoints: sessions, agents, messages, gates, runs, notes, artifacts,
  kits, marketplaces, update, system, telemetry, folders, clones, terminal WS); SSE feed
  `server/feed.py` (`Source` protocol :52-67, `Journal` :86 reads the SQLite `changes`
  journal every 0.25 s, `DERIVED` :239 computes `session_status` via tmux and loop lock).
- **How it works**: the server runs the core **in-process** (calls `runtime.start_session`
  :951/:983, `stop_session` :1017, `write_as_human` :1061, `runs.answer_text` :1051,
  `finish_worker` :786, `work_state` via models :1297) — it is a peer of the CLI, not a
  client of a daemon. It can already be reached remotely (`--host 0.0.0.0`, Docker publishes
  it), with token auth over plain HTTP. Folder picker/clone endpoints browse and write the
  server host's filesystem (`/api/folders`, `/api/clone-target`, `launch.folder_info`).
  OpenAPI is generated and committed (`web/openapi.json`, `web/src/api.gen.ts`), and UI
  principle 1 forbids the UI from assuming the server is local.
- **Remote breaks**: nothing breaks for "UI remote"; it works today (minus TLS and real
  login). For "agents remote", the server's derived status and work state call tmux/git
  locally (C1, C6).
- **Candidate abstraction**: the UI server is the natural **control plane API** host. Add
  agent-facing routes (`/agent/hook`, `/agent/mcp`, `/agent/heartbeat`, `/agent/terminal`)
  behind a different auth scheme (per-agent tokens), and put TLS + a real login in front
  (reverse proxy first, as the docstring anticipates). `feed.Source` is explicitly the
  place where "remote workers' events will come through the same interface later" (feed.py
  :5-6) — though with the control plane as sole writer, remote events land in the same
  journal and no second source is needed.

### C12. Provider interface

- **Where**: `providers/base.py`: `Capabilities` :29-58, `Event` :61-84, `McpServer` :97-105
  (stdio only: `command`, `env`, `env_vars`), `AgentSpec` :108-124 (skills as `dict[str,
  Path]`, `read: list[Path]`, `environ`), `Launch` :127-136 (argv + env + warnings),
  `Provider` :150-216 (`launch_command` writes files, `parse_event` pure,
  `first_hook_blocker(cwd, env)` reads local files, `keychain_login`, `hook_limit`,
  `continue_output` pure), `lado_command` :219 (`sys.executable`), `agent_env` :224,
  `hook_argv` :277, `mcp_server` :296.
- **How it works**: providers are neutral about *what* runs but assume *where*: local paths,
  local `sys.executable`, local tmux socket in env, local user config files.
- **Remote needs**: (a) `launch_command` -> pure render into a bundle (C8); (b) `McpServer`
  gets a remote (URL + headers) form, or the stdio proxy; (c) `hook_argv` takes a
  "LADO entry point on the target" instead of `sys.executable`; (d) `first_hook_blocker`
  and `keychain_login` evaluated on the target; (e) a capability such as
  `remote_mcp: bool` if option 1 of C4 is chosen. `parse_event`, `continue_output`,
  `Capabilities`, `Event` stay as they are — they are the neutral core and already
  location-free. ACP (stage 8) is planned "behind the same provider interface as tmux"
  (ROADMAP stage 8), i.e. a second *runtime* next to tmux — the same seam this work needs.

### C13. Artifacts store

- **Where**: `artifacts.py` `Store` Protocol :170-206, `store()` :209-213 ("the one place
  the store is chosen: there is one backend, the local one"); `artifacts_local.py`
  `LocalStore` (content by hash in `LADO_HOME/artifacts`, metadata in `lado.db` via
  `state.write_artifact`); design `docs/design/artifacts.md` :8-14 (motivated precisely by
  "LADO runs on a remote server"), :93-99, :129-137 (what another backend costs).
- **How it works**: agents know artifacts by name only, via MCP tools; never by path.
- **Remote breaks**: nothing, as long as MCP tools are served by the control plane (C4).
  Only `write_artifact(file=...)` reads a path on the agent's machine.
- **Candidate abstraction**: already present. An object-store backend (S3/GCS) is
  optional and orthogonal; the costed list is in artifacts.md :129-137.

### C14. Docker image

- **Where**: `docker/Dockerfile`, `docker/compose.yaml`, `docker/entrypoint.sh`,
  `docker/profile.sh`, `docker/ssh-agent-*.sh`; code: `update.in_container` (update.py
  :494), `runtime.CONTAINER_INSTRUCTIONS`, `stop_for_container` (runtime.py :2437),
  `run.py` container note :41-45. Research: `docs/research/docker-install.md` (5.3 paths,
  5.6 UI inside, 5.14 isolation levels), `docker-install-plan.md`.
- **What it solves**: one reproducible Linux userland with LADO + tmux + git + the four
  CLIs at pinned versions + Node + mise toolchains; agents isolated from the host's home;
  secrets as files (`LADO_ENV_DIR=/run/secrets`); git identity and ssh agent forwarding;
  `docker stop/start` = `lado stop`/resume; UI bound to 0.0.0.0 inside and published to
  loopback. CI builds amd64/arm64 and publishes to GHCR.
- **What it does not**: it is **"whole LADO in one box"** — control plane and all agents
  in the same container, sharing one `lado.db`, one tmux server, all projects and all
  logins (5.14 level 1). Projects are bind-mounted at the host's path so worktree links
  stay valid (5.3). No per-session or per-agent container; no multi-host; Codex login not
  carried; research 5.14 rates "container per session" as L and notes per-agent
  containers would "cut" hooks/MCP/loop links — exactly the couplings C2-C5.
- **Reuse**: the image is ready to be the **node image** for remote agents (it already has
  the CLIs and LADO itself, so `lado hook`/`lado mcp` shims exist there) and also the
  **whole-session image** for split point B.

### C15. Session start/stop/resume and update

- **Where**: `runtime.start_session` :624-781 (check_repo local, `kits.resolve`,
  `_base_env`, config files, `tmux.new_session`, `loop.start`), `resume_at_start` :2466,
  `stop_session` :2368, `forget_session` :2583; `self_update.py` (stops all sessions,
  installs, resumes; `gui_session` plan); `runs.resume` :445 (re-spawns run workers,
  `_restore_worktree`).
- **Remote breaks**: stop must also stop remote nodes; resume must re-provision them;
  `lado update` would have to update node images too (version skew between control plane
  and node shim).
- **Candidate abstraction**: backend `teardown(session)`/`provision(session)`; a version
  handshake between node shim and control plane (the code already refuses schema skew
  with `SchemaError`; a protocol version does the same over the wire).

### C16. Smaller couplings worth listing

- **Telemetry and logs**: `hooks.log`, `loop.log`, `errors.jsonl` written by whatever
  process hit the error (`telemetry.bounded_append`, `telemetry.record`). Remote shims
  must ship errors to the control plane or log locally and lose them from `lado bug-report`.
- **`interpreter.run_module`** (interpreter.py :21): every LADO subprocess is
  `sys.executable -c <loader> <module>` — the absolute interpreter of the LADO host.
- **Clock**: `agents.seen_at`, `messages.sent_at`, `resume_at` use `time.time()` of the
  writing process; across hosts use the control plane's clock only.
- **Session names**: unique per `LADO_HOME` (artifacts.md :135-136) — fine as long as
  one control plane owns them.
- **Clone/scratch** (`clone.py`, `scratch.py`, `server/clones.py`): create repositories
  on the server host's disk (`~/lado` or `LADO_REPOS`). For remote workers the source of
  truth for the repo becomes "the git URL" rather than "a folder".
- **`exclude_worktrees`** writes the human repo's `.git/info/exclude` (runtime.py :2864);
  irrelevant for remote clones.
- **macOS GUI session** (`gui_session.py`, docs/design/macos-gui-session.md): only local
  Claude-on-Mac; no remote impact except that it must be skipped for remote placement.

## 3. Coupling table

| # | Coupling | Main refs | Today | Breaks if agent is remote | Candidate seam | Size |
|---|---|---|---|---|---|---|
| C1 | Process lifecycle via tmux | tmux.py :165-255; runtime.py :750, :870, :1238, :2205, :2368 | local `tmux -L lado` subprocess; window = agent | no window; loop marks agent stopped | `ExecutionBackend` (launch/alive/kill/type/terminal); tmux kept on the node | M |
| C2 | Typed delivery | runtime.py :1902-1960; tmux.py :239 | paste into pane from any process | no pane | `backend.type_text`; queue stays central | S (after C1) |
| C3 | Hooks write SQLite | base.py :277-293; hooks.py :141-297 | per-event Python process, direct DB + tmux + git | no DB/tmux; wrong interpreter path | hook shim → HTTP → `hooks.handle` server-side; fingerprint node-side | M |
| C4 | MCP over stdio, in-process core | mcp_server.py :1-5, :437; base.py :296 | stdio child of the CLI runs runtime/runs | no DB; env identity not auth | remote MCP (HTTP + per-agent token) or stdio proxy | M |
| C5 | Session loop | loop.py :82-143; runtime.py :2205 | detached local process, flock | its window check & typing | uses backend; heartbeats for liveness | S |
| C6 | Git worktrees share one repo | runtime.py :827-887, :1152-1338; runs.py :84-89, :431, :936 | linked worktrees; supervisor merges locally | commits invisible; work state & finish fail | `Workspace` (create/state/remove/sync); clone + push/fetch | L |
| C7 | SQLite multi-writer | state.py :1-5, :1147-1190 | WAL, many processes | cannot share across hosts | control plane sole writer; RPC for remote | M (falls out of C3/C4) |
| C8 | LADO_HOME paths, config dirs, skill symlinks | base.py :240-313; claude.py :140-201; codex.py :193-216; opencode_family.py :115 | provider writes files & absolute argv | paths/symlinks absent on node | render `LaunchBundle` + backend materialize | M |
| C9 | Env & credentials from local login shell | agent_env.py :98-389; runtime.py :2769-2850; claude.py :247, :312; codex.py :278; gui_session.py | `$SHELL -ilc` + keychain + home files | wrong host; no logins | backend resolves env on node; secrets via `LADO_ENV_DIR` contract | M |
| C10 | Terminal = local pty + tmux attach | terminal.py :74-224; server/terminals.py | UI server attaches locally | nothing to attach | `backend.open_terminal` stream; relay via node agent | M |
| C11 | UI server runs core in-process | server/app.py; auth.py; run.py; feed.py :52 | token over HTTP, `--host` | n/a for UI-remote; derived status uses tmux | control-plane API; TLS/login in front | S (UI) / M (agent API) |
| C12 | Provider assumes local | base.py :97-299 | files + local paths | see C3/C4/C8/C9 | pure render; remote McpServer; node-side checks | M |
| C13 | Artifacts | artifacts.py :170-213; artifacts_local.py | Store protocol, local backend | only `file=` arg | already abstracted | S |
| C14 | Docker image | docker/* | one box for everything | n/a | reuse as node / session image | — |
| C15 | Start/stop/resume/update | runtime.py :624, :2368, :2466; self_update.py; runs.py :445 | local only | nodes not provisioned/stopped; version skew | backend provision/teardown; protocol version | M |
| C16 | Logs, clock, interpreter path, clone | telemetry.py; interpreter.py :21; clone.py | local | lost logs, skew | ship to control plane; server clock | S |

## 4. Candidate split points

### A. "Whole session in a remote box" (control plane + agents together, remote)

Run the existing image (or a VM with LADO installed) on a remote Docker host / VM / pod;
the human uses the UI over the network. **This works today** apart from security
hardening: `lado server --host 0.0.0.0`, token auth, Docker image, `LADO_ENV_DIR` secrets,
`LADO_PUBLIC_HOST` for links.

- **Requires**: TLS and a real login in front of the UI (reverse proxy first; auth.py is
  the one place to change later); repos come from git URLs (clone already exists in the UI)
  instead of bind mounts; a persistent volume for `/home/lado` (state + logins + mise);
  a launcher/IaC recipe (compose on a remote Docker host, a Helm chart/StatefulSet with one
  replica + PVC, or a VM image). Codex login carry (T15) for Codex users. Per-session
  isolation = one box per session/project (research 5.14 level 2), each its own LADO_HOME.
- **Size**: S-M (mostly packaging, docs, TLS/auth). No change to the core.
- **Risks**: the UI token over plain HTTP until TLS; one box = agents share logins and
  repos (fine for single user); state on a PVC means one replica only (SQLite); the human
  cannot open the worktrees in a local IDE (push/pull through git instead); multiple boxes
  = multiple UIs unless a thin "fleet" page lists them.

### B. "UI remote, runtime local" (or local UI on a remote runtime)

Just the presentation split. Already designed in (ui.md principles 1-4, OpenAPI, SSE
feed, token auth, Bearer for non-browser clients).

- **Requires**: TLS/login; making the folder picker and clone endpoints explicit about
  "server host's filesystem" (they are); maybe a tunnel product (SSH tunnel, Tailscale,
  Cloudflare Tunnel) as the documented way. The desktop app (stage 7) is the same split.
- **Size**: S.
- **Risks**: exposure of a server that can run commands as the user; the terminal
  WebSocket's control mode gives a remote browser a shell-equivalent.

### C. "Remote worker only" (supervisor and control plane local, some workers remote)

The supervisor keeps running in the human's checkout; `spawn_worker(..., placement=...)`
places a worker on a pod/VM/Docker host.

- **Requires**: C1 backend with a remote implementation (node agent or ssh/kubectl/docker
  exec driving a tmux on the node); C3 hook shim + server endpoint; C4 remote MCP or stdio
  proxy, per-agent tokens (derive from `agents.instance`); C8 launch bundle (configs,
  prompt, skills copied); C9 env/credentials on the node; C6 `Workspace` with clone +
  branch sync (push to origin or a LADO-hosted bare repo, or fetch from node) and
  `work_of` after fetch; C10 terminal relay; heartbeats in the loop; a `placement` column
  on `agents` (schema bump) and a node registry/config. Read-only fingerprint moved to the
  node. Network path from node to control plane (the human's laptop is usually not
  reachable from a pod: needs an outbound-from-laptop tunnel or a relay).
- **Size**: L (roughly: backend + node agent M, hooks/MCP over HTTP M, workspace/git sync
  L, terminal relay M, provisioning per target M each).
- **Risks**: the laptop as control plane must stay up and reachable; git sync semantics
  (when is the branch visible to the supervisor; conflicts with "merge then finish"); hook
  latency vs the 60 s turn-end limit; secrets shipped per agent; partial failures (node
  lost mid-turn) need new `agent_ended` reasons; provider configs checked by hand per
  version would need re-checking with remote MCP.

### D. "Control plane vs execution plane" (the general architecture)

Control plane = `lado server` + `lado.db` + session loops + kits/cache + artifacts, run
anywhere (laptop, VM, pod). Execution plane = N nodes (local tmux is one of them) running a
`lado node` agent that owns a tmux server, workspaces and the CLIs, and talks to the
control plane over one authenticated channel (outbound WebSocket/gRPC from the node,
so nodes behind NAT/pods work). Supervisor is just another agent on some node.

- **Requires**: everything in C plus: the local mode re-expressed as "the local node"
  through the same interface (or kept as a fast in-process path, with the remote node as a
  second implementation — the safer route given "local mode untouched"); `lado node`
  command; node registration and auth; workspace sync for the supervisor too (it merges in
  its own clone and pushes); session-level placement (all agents of a session on one node
  = cheap git, linked worktrees still work there) vs agent-level placement.
- **Size**: XL in total, but can be delivered as C first, then "session placement"
  (all agents of a session on one remote node — which keeps linked worktrees and avoids
  most of C6, a very attractive middle ground), then general.
- **Risks**: scope; two implementations of every backend verb to test (integration tests
  today assume one machine: real tmux, fake agent); ACP stage 8 will touch the same seam —
  design the backend interface so an ACP runtime is a third implementation rather than a
  rewrite.

**A pragmatic ordering**: B (S, already almost there) → A (S-M, packaging + TLS) →
"session on a remote node" variant of D (M-L: backend + hooks/MCP over network + terminal
relay, but **no git sync** because all of the session's worktrees stay on that node, and
the human pushes/pulls via origin) → C (per-worker placement with git sync).

## 5. Existing assets to reuse

- **Provider neutrality**: `Capabilities`, `Event`, pure `parse_event`/`continue_output`
  (base.py) — the event protocol is already wire-ready (small dataclasses).
- **`instance` per launch** (state.py :934, schema `agents.instance`): hooks of older
  launches already ignored (`hooks.main` :276) — a ready basis for per-agent tokens/fencing.
- **Small tmux surface** used by the core (~8 functions; list in C1) — a backend interface
  is mostly a wrapper of `tmux.py`.
- **`terminal.Terminal` + `NoTerminal`** and the WebSocket protocol (server/terminals.py)
  — the browser side does not change for a relayed terminal.
- **`feed.Source` protocol** (feed.py :52) explicitly reserved for remote workers' events.
- **`artifacts.Store` protocol** (artifacts.py :170) and the "agents know artifacts by name"
  rule — results already location-independent.
- **Auth as one layer** (`server/auth.py`), Bearer tokens for non-browser clients, Origin
  check; OpenAPI-typed API (`web/openapi.json`).
- **Outside folder for secrets** (`agent_env.outside`, `LADO_ENV_DIR`): maps onto
  Kubernetes Secrets/Docker secrets with zero new concepts; `mcp_exec` keeps kit secrets
  off disk.
- **Kilo/OpenCode config as env content** (`*_CONFIG_CONTENT`) — already file-free except
  skills.
- **Docker image** with all four CLIs at pinned versions, LADO itself, mise, git/ssh/gh
  setup, `in_container` handling, `stop_for_container`, CI multi-arch publishing.
- **Clone from URL** (`clone.py`, `server/clones.py`) — the start of "repo as URL".
- **Message protocol designed for unreliable hand-over**: retries, confirmation, `failed`
  with a human-visible reason, `hook_output` channel that needs no tmux — tolerant of a
  network hop.
- **Schema-skew refusal** (`state.SchemaError`, `feed.schema_problem`) — a model for a
  control-plane/node protocol version check.
- **Docs that already anticipate the move**: ui.md principles 1-4 (:13-48), artifacts.md
  :8-14 and :129-137, docker-install.md 5.14 (isolation levels, "a per-agent container
  would cut those links"), ROADMAP stage 8 (ACP runtime "behind the same provider
  interface as tmux").

## 6. To verify by hand before designing

1. Remote (HTTP) MCP server support and config shape in each CLI at its `TESTED_VERSION`
   (Claude Code 2.1.29x `type: http` + headers; Codex 0.162 streamable HTTP `url`;
   OpenCode 1.18 / Kilo 7.8 `type: remote`), including `alwaysLoad` and Codex `required`.
2. Whether Claude Code's hooks support an HTTP type at the tested version (would remove the
   shim for Claude only; the shim is still needed for Codex and the JS plugin).
3. Hook round-trip latency budget under the 60 s turn-end limit and the 20 ms MCP_READY
   poll (becomes a server-side wait).
4. Git sync choice: push to origin vs LADO-hosted bare repo vs fetch from node; how
   `finish_worker`'s "merged" check behaves after a fetch.
5. Node reachability: the control plane on a laptop behind NAT with pods that cannot call
   back — needs node-initiated outbound connections (WebSocket) for everything.
