# A1. Code seams for per-session sandboxes (re-verification of R1 at main 1e565441)

Archived input to the [session isolation plan](../session-isolation-plan.md), 2026-11-27; kept as written.

Read-only analysis, 2026-11-27, of `main` 1e565441 (2026-11-26). R1 was taken at 033705e
(2026-10-18). Line numbers below are current. "Agent side" = any process in the agent CLI's
process tree (the CLI's window command, `lado hook`, `lado mcp`, `lado login-wait`, the git
credential helper, `lado.mcp_exec`, the OpenCode/Kilo JS plugins). "Target" = the runner
with one gVisor sandbox per session, the panel outside as the single writer of lado.db
(session-isolation.md section 7; cloud-workers-plan.md stages B-C).

## 0. Summary

1. **All 16 of R1's couplings still hold.** Not one has been reduced. Several got bigger:
   `runtime.py` grew from about 2,900 to 3,824 lines, `state.py` went to SCHEMA_VERSION 44
   with 37 `BEGIN IMMEDIATE` transactions, and 30 modules call `state.home()`/`home_path()`.
   There is still no execution-backend, workspace or agent-API interface. The only
   Protocols are still `artifacts.Store` (artifacts.py:170) and `feed.Source` (feed.py:52).
2. **What is new since R1 is mostly secrets.** Agent-side processes now read more of
   LADO_HOME directly:
   - git server tokens: `git_credential.read_token` reads `LADO_HOME/git-servers/<id>/token`;
   - model server keys: `LADO_HOME/model-servers/<id>/key`, handed to agents as `LADO_MODEL_KEY_<ID>`;
   - LADO's own secrets: `LADO_HOME/secrets`;
   - project secrets: `LADO_HOME/projects/<id>`;
   - logins: Codex's shared `auth.json` is linked into every agent, and Claude's `~/.claude.json` is edited.
   Any agent process can read any of these today, because it runs as the same uid.
3. **There are three new agent-side writers of lado.db:**
   - `lado login-wait`, which runs in the agent's own window;
   - the `lado mcp` front, which records MCP_READY itself;
   - `github_takeover`, which runs inside `lado mcp` on every spawn.
   There are also new tmux users: login windows (logins.py) and UI viewers (terminal.py).
4. **The supervisor's `lado mcp` is a full control plane in the agent's tree.** Through
   `spawn_worker`, `start_session`, `flow_*`, `finish_worker` and `list_models` it:
   - resolves the login shell (`$SHELL -ilc`);
   - reads every secret layer and all git and model keys;
   - writes config folders and `env.json` with secrets;
   - runs `git worktree add`;
   - opens tmux windows;
   - starts a detached `lado loop` process.
   This is the first thing that has to go behind an API.
5. **The smallest seams with no behaviour change** (section 3):
   1. split `hooks.main` and `mcp` into a client half and a server half, called in-process;
   2. put an `ExecutionBackend` in front of the roughly 15 tmux verbs, keeping the
      `fake_tmux` fixture working;
   3. add a `Workspace` for the git calls;
   4. issue a per-agent token;
   5. carry both halves over a local socket;
   6. add a launch bundle.
   Seams 1-2 are S-M each and are protected by the existing unit and integration suites.

## 1. R1's couplings re-verified, plus the new ones

Legend for "crosses": F = file in LADO_HOME/home, D = lado.db, T = tmux socket, P = process
spawn/exec, G = git on host paths, E = env var, S = secret, N = network, Y = pty.

### 1.1 R1's C1-C16

| # | Coupling | Still true? Where now | Crosses | Becomes in the target |
|---|---|---|---|---|
| C1 | Lifecycle via tmux | Yes. tmux.py: `socket` 69, `new_session` 165, `new_window` 209, `has_session` 213, `kill_session` 223, `kill_server` 227, `kill_window` 238, `list_windows` 255, `pane_pids` 262. Callers: runtime.py 941, 1054 (start_session), 1342 (spawn_worker), 1747 (close_worker), 1440/1527 (`session_status` 1523), 2802 (`check_windows` 2792), 3065/3085 (stop_session 3052), 3170 (stop_for_container 3158), 3248 (`_kill_for_migration` 3240), 3266 (`_mark_stopped` 3259); loop.py 79; cli.py 1080, 2377-2382 (`lado attach`); uninstall.py 373, 477-490 | T, P | `ExecutionBackend` verbs run by the runner agent inside the session's sandbox (tmux stays in the sandbox). The panel's loop asks `backend.alive(session)`, which is a heartbeat or a list over the runner channel |
| C2 | Typed delivery | Yes. `hand_over` 2478 → `tmux.send_text` 2495; `_sweep_sent` 2525 → 2534; `_deliver` 2438; tmux.send_text 274. It runs in whichever process noticed (another agent's `lado mcp`, this agent's hook, the loop, the UI server) | T | `backend.type_text(session, agent, text)`. The queue, `take_pending` and `_plan` stay in the panel |
| C3 | Hooks write SQLite | Yes, and more so. base.py `hook_argv` 831 = `lado_command` 658 = `interpreter.run_module` (sys.executable). Written by claude.py 364-373 (settings.json), codex.py (config.toml [hooks]) and opencode_family.py 258, 380 (plugin options). hooks.py: `main` 332 checks that `lado.db` exists (343), `handle` 182 (about 20 state/runtime calls), `_idle` 292 → `runtime.hand_over` + `runtime.sweep` (tmux typing), `_wait_for_mcp` 81 polls the DB every 20 ms for up to 20 s, `_fingerprint` 119 runs git on `me.cwd` and the session repo, `_write_baseline` 110 writes `LADO_HOME/agents/<s>/<a>/read-only-baseline.json`, `_log` 95 writes hooks.log, `telemetry.record` writes errors.jsonl | D, T, G, F, P | A thin forwarder in the sandbox POSTs `{instance, native, payload, fingerprint?}` with the agent's token. `hooks.handle` runs in the panel. The fingerprint and its baseline are computed in the sandbox. The MCP_READY wait becomes a server-side wait |
| C4 | MCP over stdio, core in-process | Yes. mcp_stdio.py: `main` 421 takes identity from `LADO_SESSION`/`LADO_AGENT`/`LADO_INSTANCE` env (trusted as is), `Front` 155, `_prepare` 257 reads the DB, `_record_ready` 324 writes MCP_READY, cache in `LADO_HOME/mcp-cache` 68-101. mcp_server.py: `build` 131, tools call runtime/runs/artifacts in-process (spawn_worker 376-426, flow_start 428, finish_worker 462, start_session 491, list_models 358) | D, T, G, F, P, S | A stdio proxy in the sandbox (the existing `Front` is the natural place) forwards JSON-RPC to the panel's per-agent MCP endpoint. Identity comes from the token, not from env |
| C5 | Session loop | Yes. loop.py: `lock_path` 56 (flock in LADO_HOME/loop), `take_lock` 84, `start` 121-129 (Popen, also from `lado mcp` via `start_approved_session` runtime.py 2312), `run` 151 → check_windows/check_starts/check_turns/sweep 186-189, `tmux_gone` 72 | T, F, P | Stays in the panel and calls the backend. Liveness becomes a runner heartbeat |
| C6 | Git worktrees share one repo | Yes. spawn_worker 1248: `git branch --list` (1276), worktree path 1294 (`repo/.lado/worktrees/<s>/<w>`), `worktree add` 1329, undo 1356-1363. runs.py 88, 93-94 (run worktree), `_restore_worktree` 436-447, `_close` 918. runtime `gone`/`tip`/`remove_work` 1661-1704, `work_of` 1825, `work_state` 1808 (UI models.py 2241), `exclude_worktrees` 3800 (writes `.git/info/exclude`), `session_worktrees` 3323, `remote()` 518 (called by `_ours` 3590 and `_repo_tool` 3602) | G | `Workspace` ops executed by the runner on its volume. A whole session lives in one sandbox, so linked worktrees keep working and no sync is needed (stage C). The result goes out through git push or fetch |
| C7 | SQLite with many writers | Yes, and wider. state.py docstring 1-5, `home` 1482, `home_path` 1490, `_open` 1500, `connect` 1589, SCHEMA_VERSION 44 (26), 37 `BEGIN IMMEDIATE` | D | The panel is the only writer. Hook, MCP and heartbeat calls become RPCs |
| C8 | LADO_HOME paths, config folders, skill symlinks | Yes. base.py `configs_root` 703, `config_path` 709, `state_path` 730 (`agent-state/`), `temp_path`/`make_temp_dir` 775-806 (`/tmp/lado-<uid>/<s>/<a>`), `link_skills` 858 (symlinks into `LADO_HOME/cache`). claude.py 344-426 (mcp.json, settings.json, `--add-dir`), codex.py 497 (CODEX_HOME/skills), opencode_family.py 248-259, 372. `_write_lead_skills` runtime.py 3460. `env.json` with all secrets: `_command` 3673 → agent_env.command 615 / `write_private` 631 | F, S | Render a `LaunchBundle` in the panel and materialize it in the sandbox. Skills are copied in, not linked. `${LADO}` stands for the in-sandbox forwarder |
| C9 | Env and credentials from the local login shell | Yes, and larger (section 1.2). agent_env: `layers` 159, `from_shell` 510 (`$SHELL -ilc`), `outside` 244 (LADO_ENV_DIR), `lado_secrets` 345. runtime `agent_layers` 3508 (+ project_secrets.layer + github_takeover.run), `_check_commands` 3529 (local PATH, git version), `_ours` 3569 (git tokens, gh/glab), `_before_window` 3732 (`first_hook_blocker`, login status), `_keychain_warnings` 3771 (gui_session) | E, S, P, F | The environment and its checks are resolved in the runner, for its PATH and CLIs. Secrets come from the panel per session. API keys sit behind the runner's proxy (placeholders in the sandbox). Subscription logins stay inside the sandbox |
| C10 | Terminal = local pty + tmux attach | Yes, and wider: login windows too. terminal.py: `open` 74 (viewer, `link-window`), `_attach` 98 (`pty.openpty` + `tmux attach`), `open_login` 203, `close_viewers` 242. tmux.py 389-414. server/terminals.py `serve` 58, `serve_login` 75. app.py 1259 (login WS), 1816 (agent WS) | T, Y, P | `backend.open_terminal(agent, mode)`: a byte stream relayed by the runner agent. The browser protocol does not change |
| C11 | The UI server runs the core in-process | Yes. About 140 routes in app.py (440-1824). feed.py `DERIVED` 239 → `runtime.session_status` (tmux + flock). models.py 2241 (work_state → git), 2402. Folder browsing and clones on the server's own file system: app.py 609-711 | D, T, G, F | The panel API stays as it is. Derived status and work state come from runner RPCs. Folder, clone and scratch routes become runner (volume) operations |
| C12 | Providers assume a local machine | Yes. `McpServer` 193 is stdio only. `agent_env` 686 puts `LADO_HOME` and `LADO_TMUX_SOCKET` into every agent. `first_hook_blocker` (claude 622, codex 610) edits the user's `~/.claude.json` (claude.py 747-860) and `~/.codex` (codex.py 672-695) | F, E, S | `render` is pure. `McpServer` gains a remote (url + headers) form, or stays the stdio proxy. Blockers are settled in the sandbox |
| C13 | Artifacts | The Store still abstracts them (artifacts.py 170, 209; artifacts_local.py LADO_HOME/artifacts). **New finding:** `write(file=)` (artifacts.py 246-275, `_read_file` 666) accepts any absolute path and reads it as the `lado mcp` process. An agent can make an artifact of `~/.lado/lado.db` or of a token file today | F, S | The forwarder in the sandbox reads `file=` and sends the bytes. The panel never resolves agent paths |
| C14 | Docker image | Yes. docker/compose.yaml: one `lado` service, home volume, workspace bind at the same path, `/run/secrets` read-only, `host.docker.internal` | — | Split into a panel image and a runner image. Repositories move to a volume (S-isolation finding 2) |
| C15 | Start/stop/resume/update | Yes. start_session 855, `resume_at_start` 3187, stop_session 3052, stop_for_container 3158, `migrate_if_safe` 1443 (cli.py 3117), self_update.py (flock `update.lock`, stops and resumes everything, gui_session plan), runs.resume 450 | P, T, F | Runner provision and teardown per session, plus a protocol version check. `lado update` has to update the runner image as well |
| C16 | Logs, clock, interpreter, clone | Yes. `telemetry.bounded_append` 245 / `record` 334 are written by hooks and mcp. `interpreter.run_module` 21 is the absolute `sys.executable`. `state.seen` and `time.time()` are taken in the writer process. clone.py and scratch.py write to `LADO_REPOS` | F, P | Logs are shipped to the panel. Time is the panel's receipt time. Repositories come from a git URL into the runner's volume |

### 1.2 New since R1

| # | Coupling | Where | Crosses | Target |
|---|---|---|---|---|
| N1 | **Login windows**: a tmux session per provider, `lado-login-<p>`, runs the CLI's login with the agents' environment, in the user's HOME, streamed into the UI | logins.py `open_window` 346-378 (`tmux.new_labelled_session`, env.json under `LADO_HOME/logins`), `windows` 269, `look` 316, `end_windows` 395, `main` 404; terminal.open_login 203; app.py 1239-1259 | T, Y, F, S | Subscription logins must be inside the sandbox (S-isolation finding 5), so a login window must run in the session's sandbox or in a per-runner login sandbox whose credential file is copied or mounted per session. This is an open design question: refresh races on Claude `.credentials.json` and Codex `auth.json` (R4) |
| N2 | **`lado login-wait`**: the agent's own window waits for a login, then execs the CLI | login_wait.py `command` 26, `main` 66-104. It reads `outside`, `lado_secrets`, `project_secrets.layer` (52-63), writes `state.window_opened` / `block` / `set_status` and loop.log, and settles `first_hook_blocker` | D, F, S | The wait moves to the panel or runner. The window starts only once the panel says a login is available |
| N3 | **Git servers and the credential helper**: `credential.<url>.helper` = LADO's Python + `lado.git_credential --home H --server ID`. The helper reads `H/git-servers/ID/token`. GH_TOKEN, GH_ENTERPRISE_TOKEN and glab header commands go into the agent env | git_credential.py 27-46, 49-76; git_servers.py 838-921 (`helper_command`, `variables`, sslCAInfo 880), 925-960 (`gh_variables`: tokens in env), 969-995 (glab); runtime `_ours` 3569-3599 | F, S, E, P | The runner's git proxy injects the credential, or the helper calls the agent API with the agent's token (scoped to the session's origin). No token file and no `--home` in the sandbox. GH_TOKEN becomes a placeholder or comes through the proxy |
| N4 | **Model servers and keys**: `LADO_HOME/model-servers/<id>/key` reaches the agent env as `LADO_MODEL_KEY_<ID>`. `list_models` (MCP) asks servers and CLIs with the agents' environment | model_settings.py 11, 39, 124, 1124; base.py 21-22, `ServerEntry` 229; runtime `list_models` 1183 (from `lado mcp`), `_worker_start` 1145 | S, E, N | The key lives in the runner's proxy memory and the sandbox gets a placeholder plus the proxy's base URL. `list_models` runs in the panel or runner |
| N5 | **Project secrets and LADO's secrets** as layers of every agent's env | agent_env.py 336-347 (`LADO_HOME/secrets`), project_secrets.py 30, 49, 86 (`LADO_HOME/projects/<id>`), runtime `agent_layers` 3508 | F, S, E | The panel assembles the environment for the session only. The sandbox never sees another project's folder |
| N6 | **github_takeover** runs at every launch inside `agent_layers`, including in the supervisor's `lado mcp`. It may run `gh auth token`, probe GitHub and write lado.db and a token | github_takeover.py 1-18, `run` 157-175; runtime.py 3513-3519 | D, S, N, P | Panel only. The sandbox never takes logins over |
| N7 | Commit authors: author files in the agent's config folder, `includeIf` entries | git_servers.py docstring 23-28; runtime `_ours` 3584 (`author_files`) | F, E | Part of the launch bundle |
| N8 | Per-agent temp folder `/tmp/lado-<uid>/<s>/<a>` with a link in `agent-state` | base.py 755-829 | F | Becomes natural (a sandbox's own /tmp). Nothing to ship |
| N9 | The MCP answer cache in `LADO_HOME/mcp-cache`, written by every agent's front | mcp_stdio.py 30-101 | F | The front's cache can live in the sandbox (it is the SDK's answers, not secret), or the panel answers |
| N10 | Telemetry error journal and usage stats | telemetry.py 136-140 (telemetry/, errors.jsonl), `record` 334 (called from hooks 362 and mcp), loop `telemetry.kick` 208 | F, N | Errors are forwarded to the panel over the agent API. Stats stay in the panel |
| N11 | **self_update** stops every session and the UI, runs the installer, resumes, and rolls back. It holds a flock and reads pids | self_update.py 1-60, 509; server/run.py 373, 505-517 (pid in `server.json`, `os.kill`) | P, F | The panel updates itself. Runners are versioned images with a protocol handshake. Sessions in a runner must survive a panel update, or be stopped through the runner |
| N12 | Clones, scratch folders, projects and the workspace on the server's disk | clone.py, scratch.py, setup.py, projects.py (`LADO_REPOS`); app.py 609-711; compose bind at the same path | G, F | Runner-side: a clone into the runner's volume. Folder browsing of the host disappears, or becomes git-URL only (S-isolation finding 2) |
| N13 | macOS GUI session for the keychain | gui_session.py 138-205 (tmux server born through launchd), runtime 1059, 3771-3785, logins.py 371, doctor.py 343 | T, P | Local native mode only. Absent in the runner; the backend says loudly that it does not apply |
| N14 | Codex's login is one shared `~/.codex/auth.json`, linked into each agent's CODEX_HOME | codex.py 672-708 (`_settle_login`, "every agent and the user's own Codex share") | F, S | One credential per sandbox, or an API key through the proxy. A shared link across sandboxes is impossible |
| N15 | Claude's `~/.claude.json` is edited for trust, onboarding and key approval | claude.py 713-860 (`edit_config`) | F | Done inside the sandbox's own HOME at materialize time |
| N16 | Gate popups: `tmux display-popup` running `lado` with LADO_HOME | runs.py 860-868; tmux.py 293 | T, F | Optional and tmux-only. Dropped for runner sessions (it returns 0 when no clients are attached) |
| N17 | uninstall: pids of panes, `os.kill(pid,0)`, kills the tmux server | uninstall.py 373, 403, 477-490 | T, P | Runner teardown |
| N18 | `start_session` from MCP spawns a **detached loop process from the agent's tree** (`loop.start` with `tmux.clean_env()`) | runtime 2312; loop.py 121-129 | P | Panel-side start through the API |
| N19 | guide.py, doctor.py, provider_check: UI facts and local CLI checks | doctor.py 208, 554-571; server/provider_check.py | P | Doctor splits into a panel check and a runner check. The guide stays panel-only (no coupling) |

## 2. Every agent-side access that must go through an API

This is the list of what must become an API (or move out of the sandbox) before an agent
can run in a sandbox. "Kind": DB-R/W = lado.db, HOME = LADO_HOME files, WT = other
worktrees or the session repo, TMUX, SEC = secrets, PROC = starting processes.

### 2.1 `lado hook` (hooks.py; cli.py 3088-3091)

| Access | Where | Kind |
|---|---|---|
| `lado.db` existence check | hooks.py 343 | HOME |
| `state.get_agent` (instance fence) | 344-346 | DB-R |
| handle: `state.seen`, `report_model`, `set_status`, `confirm_sent`, `wait`, `resume`, `confirm_channel`, `output_not_taken`, `check_replies`, `check_unread`, `queue_message`, `reset_resumes`, `recommendations_missed`; `runtime.heard_at_start`, `start_note`, `turn_failed`, `agent_ended`, `repo_changed`, `repo_check_failed` | 182-289 | DB-W |
| MCP_READY poll | 81-92 | DB-R (polling) |
| `_idle` → `runtime.hand_over` (`take_pending` + **tmux send_text**) and `runtime.sweep(session, agent)` (retypes this agent's unconfirmed messages) | 292-329 | DB-W, TMUX |
| `state.output_printed` / `output_not_taken` | 359-369, 371 | DB-W |
| Fingerprint: git on `me.cwd` and `sess.repo` | 119-132; fingerprint.py | WT (own repo: allowed in the sandbox) |
| Baseline file in `LADO_HOME/agents/<s>/<a>/` | 99-116 | HOME |
| hooks.log, errors.jsonl | 95-96, 362 | HOME |

### 2.2 `lado mcp` (mcp_stdio.py + mcp_server.py)

| Access | Where | Kind |
|---|---|---|
| Identity from env, no authentication | mcp_stdio.py 421-428 | — (needs a token) |
| `state.get_agent` (tool set), MCP_READY write | mcp_stdio.py 257-270, 324-331; mcp_server.py 52-58 | DB-R/W |
| mcp-cache read/write | mcp_stdio.py 68-101 | HOME |
| Every tool: state/runtime/runs/artifacts in-process | mcp_server.py 131-511 | DB-R/W |
| `send_message`/`ask_human`/`recommend` → `_deliver` → **tmux send_text into other agents' windows** | runtime 1887, 2438-2495 | TMUX (cross-agent) |
| `spawn_worker` and `runs.spawn_worker`: `agent_layers` (`$SHELL -ilc`, LADO secrets, project secrets, github_takeover), git/model keys, config files + `env.json` with secrets, `git worktree add`, `tmux new-window`, loop.log | runtime 1248-1371, 3508-3600 | SEC, HOME, WT, TMUX, PROC, DB-W |
| `finish_worker`: git status/rev-list/worktree remove/branch -D, `tmux kill-window`, removal of config/state folders | runtime 1629-1770 | WT, TMUX, HOME |
| `flow_start`/`flow_advance`/`flow_cancel`: run worktrees, gate popups | runs.py 45-94, 860-868, 918 | WT, TMUX |
| `start_session`: a whole new session (kits, tmux new-session, `loop.start` Popen) | runtime 2312; loop.py 121 | PROC, TMUX, SEC |
| `list_models`: the agents' env + model server keys + CLI subprocesses | runtime 1183 | SEC, PROC, N |
| `write_artifact(file=)`: reads **any** path; `LocalStore` writes LADO_HOME/artifacts | artifacts.py 270-275, 666; artifacts_local.py | HOME (write), arbitrary read |
| `telemetry.record` on errors | mcp_server / mcp_stdio `_journal` 398 | HOME |

### 2.3 The window command and `lado login-wait`

| Access | Where | Kind |
|---|---|---|
| `agent_env.main` reads and deletes `env.json` (all secrets) from LADO_HOME/agents | agent_env.py 640-646 | HOME, SEC |
| login-wait: re-reads LADO_ENV_DIR, `LADO_HOME/secrets`, project secrets every 3 s | login_wait.py 46-63, 80-82 | SEC |
| login-wait: `state.window_opened`, `block`, `set_status`, loop.log | login_wait.py 85-101 | DB-W, HOME |
| `first_hook_blocker` from the window: edits `~/.claude.json` / CODEX_HOME | login_wait.py 87 | F (home of the agent) |

### 2.4 The git credential helper and the gh/glab helpers

| Access | Where | Kind |
|---|---|---|
| `git_credential --home H --server ID get` reads `H/git-servers/ID/token`. **Any agent can run it for any saved server**: the command line is in its env (`GIT_CONFIG_*`) | git_credential.py 27-76; git_servers.py 838-875 | SEC, HOME |
| glab `valueFromCommand` = the same helper (`token`) | git_servers.py 969-995 | SEC |
| `GH_TOKEN` / `GH_ENTERPRISE_TOKEN` in plain env | git_servers.py 925-960 | SEC (env) |
| sslCAInfo path in LADO_HOME | git_servers.py 880 | HOME |

### 2.5 The OpenCode/Kilo plugins (opencode_plugin.js, opencode_tui_plugin.js)

They `spawn` the hook argv (opencode_plugin.js 11-17, tui 10-15) and touch nothing else.
They inherit everything of 2.1 through the argv, which contains `sys.executable`. Nothing of
their own needs an API, only the argv (a `${LADO}` placeholder in the bundle).

### 2.6 `lado.mcp_exec`

It reads only `os.environ` (mcp_exec.py 55-67) and touches no LADO_HOME. Its weakness is
upstream: the values it fills are in the agent's whole environment. In the target, kit MCP
secrets are still env values in the sandbox (acceptable: they are that session's), or
placeholders through the proxy.

### 2.7 What every agent process gets in its env today

`LADO_HOME`, `LADO_SESSION`, `LADO_AGENT`, `LADO_TMUX_SOCKET`, `LADO_ENV_DIR`,
`LADO_REPOS` (base.py 686-700). An agent's shell can therefore `sqlite3 $LADO_HOME/lado.db`
or `tmux -L $LADO_TMUX_SOCKET send-keys -t other:agent`. In the sandbox these become
`LADO_AGENT_TOKEN` plus the API address, and nothing else.

## 3. Smallest seams, one at a time, with no local behaviour change

Each step is a refactor whose local path is today's code. Order matters: 1 → 2 → 3 make the
agent side a client; 4-6 make the panel-to-runner side explicit.

### Seam 1. A server half and a client half for hooks (in-process)

- **What changes:**
  - `hooks.main` splits into `hook_client(native, session, agent, instance)`, which reads
    stdin, takes the fingerprint where one is due, calls `agent_api.hook_event(...)` and
    prints;
  - and `agent_api.hook_event(session, agent, instance, native, payload, fingerprint)`,
    which holds today's fence, `parse_event`, `handle` and `_mark_printed`.
  - Fingerprint and baseline move to the client. The client needs `read_only` and the
    provider's `hook_limit`: carry them in the hook argv (`--read-only`, provider name),
    which the provider writes anyway.
  - `_wait_for_mcp` stays on the server side.
- **Modules:** hooks.py, a new `agent_api.py` (thin), providers/base.py `hook_argv` (two
  flags). The client half imports `fingerprint`, which already uses only git and the
  standard library.
- **Size:** S-M.
- **Tests that protect it:**
  - test_read_only_hooks.py (fingerprint and baseline), test_providers.py,
    test_runtime.py, test_liveness.py, test_error_journal.py and test_recommendation.py,
    all of which call `hooks.handle` or `hooks.main`;
  - in integration, every test with the fake agent (fake_provider.py 39, 83-87 builds
    `lado hook` argv itself): test_agents, test_read_only, test_mid_turn_messages,
    test_human_messages, test_session_loop, test_agent_liveness;
  - tests/js for the plugin's argv.
- **Proof:** the whole suite is green unchanged. Add a unit test that the client half
  imports nothing of state, runtime or tmux (in the style of `test_lazy_imports.py`).

### Seam 2. The MCP front as a proxy (in-process)

- **What changes:**
  - `mcp_stdio.Front` already passes lines to an SDK it loads. Make the SDK side
    addressable through an interface `McpBackend.open(session, agent, instance) ->
    (send_line, recv_line)`. The local one is today's in-thread SDK.
  - `_record_ready` and `_prepare` go through `agent_api` (record_ready,
    tool_set_of).
  - `write_artifact(file=)` is read by the front and turned into content: base64 for
    binary data, which needs a `data` or `content_b64` parameter on the server side. The
    alternative keeps `file` server-side locally and confines it to `me.cwd` plus
    worktrees, which fixes the exfiltration finding in C13 regardless.
- **Modules:** mcp_stdio.py, mcp_server.py (the `serve` entry), artifacts.py (a confined
  read).
- **Size:** M.
- **Tests:** test_mcp_stdio.py (also guards the SDK's private `_lowlevel_server`),
  test_mcp_server.py, test_artifacts.py; integration test_mcp_start.py,
  test_mid_turn_messages.py, artifact_write in fake_agent; smoke/probe_mcp.py (real CLIs
  list the tools).
- **Proof:** the suites are green. A new test shows the front never imports state after
  the split, and `write_artifact(file="/abs/outside")` is refused or read client-side.

### Seam 3. Per-agent token (still local)

- **What changes:**
  - At launch, mint `LADO_AGENT_TOKEN`, for example an HMAC over (session, agent,
    instance) with a panel key in LADO_HOME. That needs no schema change, and
    `agents.instance` already fences off older launches.
  - `agent_api.*` checks it; env identity becomes a claim only.
  - Every `agent_api` function takes `(token, ...)` and resolves the agent from it, so
    the supervisor-only tools (`COMMAND_TOOLS`) are enforced by the panel, not by which
    tools are listed.
- **Modules:** agent_api.py, base.py `agent_env` 686 / `mcp_server` 850 / `hook_argv` 831,
  runtime `_ours` 3569.
- **Size:** S.
- **Tests:** test_providers.py (env contents), test_project_variables_core.py (reserved
  names: add the token's name to `CLI_VARIABLES` or LADO's own), integration test_agents.
- **Proof:** a hook or tool call with a wrong token or instance is refused. An old launch's
  hook still returns 0, as today (hooks.py 346).

### Seam 4. `ExecutionBackend` (B1) with a `local` backend = today's tmux

- **Verbs, taken from the current callers:**
  - `start_session_host(session, first_agent, cwd, cmd)` (runtime 1054, logins 366);
  - `launch(session, agent, cwd, cmd)` (1342);
  - `alive(session) -> set[str] | None` (`has_session` + `list_windows`: 941, 1440,
    1527, 2802, 3065, 3085, loop 79);
  - `kill(session, agent)` (1747), `kill_session(session)` (3170, 3248, 3266);
  - `type_text(session, agent, text)` (2495, 2534);
  - `open_terminal(session, agent, mode)` (terminal.open 74, open_login 203);
  - `close_viewers(session)` (terminal 242);
  - optional `popup` (runs 868);
  - `attach_command(session)` (cli 2381).
- **Gotcha:** `tests/conftest.py::fake_tmux` 494-537 monkeypatches `tmux.new_session`,
  `new_window`, `send_text`, `has_session`, `list_windows`, `kill_*`, `popup`,
  `terminal.close_viewers` and `logins.end_windows`. The local backend must call them as
  `tmux.<fn>` by module attribute, so that hundreds of unit tests stay untouched.
- **Modules:** a new `backend.py` (or `execution/`); runtime.py, loop.py, terminal.py,
  runs.py, cli.py, logins.py, server/feed.py (session_status).
- **Size:** M (mechanical, about 25 call sites).
- **Tests:** test_tmux.py, test_runtime.py, test_loop.py, test_terminal.py,
  test_terminal_socket.py; integration test_session_loop, test_agent_terminal,
  test_agent_terminal_socket, test_leftover_processes, test_tmux_in_gui_session,
  test_container_sessions; container test_sessions.py.
- **Proof:** a grep test that no module but `backend.py` and `tmux.py` imports `tmux`.
  This is "One source of truth", enforced as test_lazy_imports does.

### Seam 5. `Workspace` for the session repository's git

- **Ops:** `branches(prefix)`, `add_worktree(branch, path, base)`,
  `remove_worktree`/`delete_branch`, `restore(run)`, `work_of(worktree, branch)`, `gone`,
  `tip`, `remote()`, `exclude()`/`include()`, `session_worktrees`.
- **Local:** runtime.git as today. **Runner:** an RPC to the runner agent, which runs the
  same git in the sandbox's volume.
- **Modules:** runtime.py (1248-1371, 1629-1864, 3323, 3800-3824), runs.py (88-94, 436-447,
  918-955), server/models.py 2241.
- **Size:** M.
- **Tests:** test_runtime.py, test_runs.py, test_closed_refusals.py; integration
  test_flow_runs, test_agents (finish, discard); test_server_agents (finish preview).
- **Proof:** the suites are green, and a grep test shows `runtime.git(` is only called
  inside the workspace.

### Seam 6. The agent API over a local socket (the first real boundary)

- **What changes:**
  - The client halves of seams 1 and 2 talk HTTP or JSON-RPC over a Unix socket, with
    the token from seam 3.
  - Who serves it: the hook must work without `lado server`, which is optional today. So
    each session's `lado loop` (one per session, detached, already the session's
    long-lived process) is the natural local server: `LADO_HOME/loop/<s>.sock` beside its
    lock.
  - The alternative is a per-machine `lado agentd`.
- **The switch:** `LADO_AGENT_API=inprocess|socket`, default in-process until the socket
  is proven. Never a silent fallback ("No silent drops"): a socket that fails fails the
  hook loudly, logged, and the hook still exits 0.
- **Latency budget:** a hook has to answer inside its 60 s
  (`TURN_END_HOOK_TIMEOUT`, base.py 829). The 20 s MCP_READY wait becomes a server-side
  wait inside one request.
- **Modules:** loop.py, agent_api.py, hooks.py, mcp_stdio.py.
- **Size:** M.
- **Tests:** all integration tests with the env switch set to `socket`. Run the
  integration suite twice in CI, the same as the provider matrix.
- **Proof:** the integration suite is green in socket mode. Then, as a Landlock-style
  check, run an agent's tree with LADO_HOME unreadable: a hook and MCP must still work.

### Later, larger seams (not part of "no behaviour change" in one step)

- **Seam 7: the launch bundle (B4).** `Provider.launch_command` → `render` (pure) plus
  `materialize`. Skills are copied, `${LADO}` replaces `sys.executable`, and `env.json`
  stops carrying keys (placeholders plus the proxy). Size L across 4 providers. Tests:
  test_providers, test_codex, the per-provider launch tests, smoke (each real CLI parses
  its config), live.
- **Seam 8: secrets out of the agent tree.**
  - Once seams 1-6 exist, `spawn_worker`, `start_session` and `list_models` run in the
    panel, so `agent_layers`, keys and `github_takeover` leave the agent tree with no
    further change.
  - Remaining, each S: the git credential helper becomes an API call or proxy injection;
    login-wait becomes a panel-side wait with a window that blocks on the API;
    `telemetry.record` and hooks.log go through the API.
  - Tests: test_git_credential.py, integration test_git_server_access,
    test_project_secrets_canary, test_model_settings_canary, test_login_wait.py,
    integration test_provider_logins.
- **Seam 9: the runner backend.** A second implementation of seams 4 and 5, plus the
  materialize of seam 7, driven over the panel-to-runner channel. Container tests
  (test_two_lados, test_secrets, test_sessions) are the base for a "two sandboxes cannot
  see each other" test.

## 4. Same-machine assumptions (risks)

1. **Identical paths inside and outside.**
   - `agents.cwd`, `runs.worktree` and `sessions.repo` are absolute host paths stored in
     the DB (runtime 1294, runs 88).
   - compose binds the workspace at the same path because `.git` files of worktrees hold
     absolute paths (git < 2.48).
   - `write_artifact(file=)` resolves `Path(me.cwd, file)` in the server process
     (artifacts.py 273).
   - Claude's `--add-dir` and Codex's `CODEX_HOME` are absolute paths under LADO_HOME.
   - In the target the panel must treat these as runner-relative handles.
2. **pids and process checks.**
   - server/run.py 505-517 (`os.kill` on the pid in `server.json`);
   - uninstall.py 373, 403 (pane pids);
   - self_update's flock plus pid;
   - loop liveness by `flock` (loop.py 84-107), which only works where the lock file is.
3. **The tmux socket is shared by everything.** Agents get `LADO_TMUX_SOCKET` (base.py
   692), so any agent can drive any window. Login windows and UI viewers live on the same
   server (logins 366, terminal 84). In the target each sandbox has its own tmux, and
   viewers and logins must be per sandbox.
4. **Polling and file watching.**
   - The feed polls lado.db's journal every 0.25 s (feed.py 35). That is fine in the
     panel.
   - `_wait_for_mcp` polls the DB every 20 ms (hooks.py 21); over a network it must be a
     server-side wait.
   - login-wait polls every 3 s and reads secret folders anew (login_wait.py 80-82). In a
     sandbox it cannot read them.
   - `agent_env.outside` reads `/run/secrets` at each launch: the panel's folder, not the
     runner's.
5. **macOS keychain and gui_session.** The tmux server is born through launchd in the GUI
   audit session (gui_session.py 138-205), and a Claude login lives in the keychain
   (claude.py 609). This is meaningless in a Linux runner, but the native local mode keeps
   it. The backend must say loudly that a runner has no keychain, and doctor and the
   warnings must not claim it.
6. **Login flows.**
   - The login windows run the CLI's login in the user's HOME (logins.py 346-378).
   - Codex uses `--device-auth` (codex.py 327-335), which needs no local browser.
   - OpenCode and Kilo `auth login` may offer OAuth with a localhost callback inside
     their own menus. That is a CLI choice; not verified here.
   - Claude `/login` pastes a code.
   - In a sandbox with proxy-only egress, the login hosts must be on the allowlist. A
     localhost callback must land inside the sandbox, which the UI's terminal relay does
     not carry.
   - Shared credentials (Codex `auth.json` linked into all agents, codex.py 672-708) are
     impossible across sandboxes: one login per sandbox means refresh races or N logins
     (R4).
7. **Terminal streaming.** The UI server forks `tmux attach` on a local pty (terminal.py
   98-120) and reads it in a thread. A relay needs resize, input, end detection
   (`ended` 228), the view/control modes and the 44xx/45xx close codes kept the same.
8. **self_update.** It stops all sessions, replaces the wheel under them and resumes
   (self_update.py docstring). With runners, the panel's update must not kill sandboxes
   (or must stop them through the runner), and the runner's forwarder and panel API need a
   version handshake, modelled on `state.SchemaError` (hooks.py 357 already swallows a
   schema skew).
9. **`lado attach`** execs `tmux -L <socket> attach` locally (cli.py 2376-2383). For a
   runner it needs a relay or a printed `docker exec`/`ssh` command.
10. **Interpreter path.** Every hook, MCP server, mcp_exec, login-wait and window command is
    `sys.executable -c LOADER module` (interpreter.py 21). The sandbox needs its own LADO
    client (stdlib-only is preferable: the client halves must not import the MCP SDK or
    state).
11. **Clock.** `state.seen`, `sent_at` and `resume_at` use the writer's `time.time()`. Once
    the panel is the only writer this resolves itself, but `_sweep_sent`'s "a hook ran
    since the paste" relies on it (runtime 2525).
12. **The control plane runs inside the agent's tree.**
    - `start_approved_session` starts a detached loop from the supervisor's `lado mcp`
      (loop.py 121-129, `tmux.clean_env()`).
    - In the target, a sandbox process must never start panel processes. Seam 6 has to land
      before any sandbox, or a sandboxed `start_session` silently has no loop.
13. **Secret leakage that exists already locally.**
    - `write_artifact(file=<abs>)` (artifacts.py 273);
    - `git_credential --server <any id>` (git_credential.py 49-76);
    - `env.json` in a predictable path until the window reads it (agent_env.py 631-646);
    - the `LADO_HOME` env var given to every agent (base.py 688).
    None of these is a bug under today's documented boundary (the whole container), but
    each must be closed by the seams above, not worked around.
