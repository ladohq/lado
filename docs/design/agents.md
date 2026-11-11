# How agents talk

How LADO starts agents and moves messages, statuses and turns between them and the human,
with each agent CLI's facts checked by hand. Moved from AGENTS.md (LAD-82).

- An agent's environment (PATH, keys, variables) is the user's login shell's, as a new
  terminal sees it, the same whichever process starts the agent (`lado start`, the UI
  server, an agent's `spawn_worker`) and whoever started LADO's tmux server
  (`agent_env.layers`). For each launch (start, resume, spawn) LADO runs
  `$SHELL -ilc` with a dump of the environment, started from a terminal's few variables
  (`HOME`, `USER`, `LOGNAME`, `SHELL`, `TMPDIR`, `LANG`, `SSH_AUTH_SOCK`, and the `PATH` a
  login gives before the shell runs, `agent_env.base_path`) in a new session, no cache. That
  `PATH`: on macOS a fixed system one, which `/etc/profile`'s `path_helper` rebuilds; on
  Linux the `PATH` of `/etc/environment` (pam_env's simple form; one with a `$` is taken as
  a mistake, LADO's choice), else the login default
  `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`; on WSL (`agent_env.is_wsl`:
  its interop file or `/proc/version`) the same, plus `/usr/lib/wsl/lib`, never the Windows
  PATH (the human's decision; a folder the startup files add stays). `lado doctor` names
  where it came from, why the default, and on WSL that the Windows PATH is left out. The
  dump is JSON between markers, so what the startup files print does not matter; LADO waits for the end marker and the shell's exit, not for its output to
  close (a program the startup files leave in the background may hold it). No `$SHELL`, a
  failing shell or one slower than `agent_env.TIMEOUT` (10 s) stops the launch before
  anything starts, with the command and the end of its stderr; so does an agent CLI that is
  not on the resolved `PATH`.
  `LADO_AGENT_ENV=inherit` takes the environment of the process that starts the agent instead
  (the tests set it). From either, `TMUX`, `TMUX_PANE`, the shell's own `PWD`, `OLDPWD`,
  `SHLVL` and `_`, and a parent Claude Code's variables are dropped; the variables of the
  outside folder go over them, then LADO's secrets (the agent CLIs' login variables the
  human sets in Settings, `<LADO_HOME>/secrets/`, read as a project's secrets folder is:
  `agent_env.lado_secrets`), then the variables of the session's project, then LADO's
  variables, then the provider's (`agent_env.layers(project)`, merged by
  `agent_env.merge`, one function for every provider). A login comes whole from one layer:
  of the agent's provider's login variables (`Provider.login_variables`, given to `merge` as
  names), the highest of the first four layers that sets any gives those it sets, and none
  comes from a lower one, so a login shell's `ANTHROPIC_API_KEY` never beats a token saved
  in LADO's secrets by Claude Code's own order; each agent merges with its own provider's
  names (`runtime.agents_env`), so a worker of another CLI keeps a variable that is no login
  of its own. LADO's own git calls (`for_git`) do not get LADO's secrets. The project's
  variables (`lado project set`, docs/design/projects.md), its
  plain ones from lado.db and its secrets from their folder
  (`<LADO_HOME>/projects/<id>/secrets/`, `project_secrets.read`, the outside folder's reader
  with no link and no loose mode), are read anew at each start, resume and spawn by the
  process that launches
  (`runtime.agent_layers(project)`: the CLI, the UI server, or a supervisor's `lado mcp` for its
  `spawn_worker`, flow runs' workers and `start_session`), so an agent launched after a
  change gets it and a running one keeps its own; a session without a project gets none.
  Being in the base, they reach the kits' checks and `mcp_exec` as the outside folder's do.
  A stored project variable named as one LADO or the provider sets keeps LADO's value and is
  named in that launch's warnings (`project variable <name> of <id> not used: LADO sets
  <name> for <provider>`; `runtime._layer_warnings`); a secret cannot be one, as every such
  name is reserved. A file of the project's secrets folder not given, or the folder, is
  named in a start's and resume's warnings (`project secret <name> of <id> not used:
  <reason>`, `project secrets folder of <id> not used: <reason>`). Under
  `LADO_AGENT_ENV=inherit` an agent's `lado mcp` resolves from its own environment, which
  holds its project's values of its start: a variable or a secret unset since still reaches
  the workers it spawns (the outside folder has the same limit); the default `shell` is
  exact. A secret's value, like every variable's, goes only into the launch file `env.json`
  (600), never into a process's arguments or the tmux server's environment. The outside
  folder (`agent_env.outside`) is the one `LADO_ENV_DIR` names, an absolute path (LADO's
  image: `/run/secrets`), read anew at each launch, so the kits' checks (`${NAME}` of an MCP
  server, `_check_commands`) see it too: each regular file directly in it is a variable,
  its name the file's, its value the content with one trailing `\n` or `\r\n` dropped. A
  dotfile is passed over; a file in a subfolder, not regular, not a variable name, reserved
  (`agent_env.RESERVED`: the shell's identity, `PATH`, tmux's, and every `LADO_*`),
  unreadable, over `MAX_VALUE` (64 KiB) or not UTF-8 text without NUL is not applied and
  named with why, never with its content (`variable file <name> in <folder> not used:
  <reason>`), in a start's and resume's warnings (`runtime._layer_warnings`) and by `lado
  doctor` (`Variables from outside`: the names, never a value; the bug report has none). A
  name LADO or the provider sets for the launch keeps their value and is named in that
  launch's warnings, `spawn_worker`'s too (`LADO sets <name> for <provider>`). Unset,
  empty, missing or the null device (`agent_env.null_device`: a character device with
  `os.devnull`'s `st_rdev`, so compose's `/dev/null` bound at `/run/secrets` is one), there
  is no layer and no line; any other path that is no folder is named `not a folder`. In a
  container doctor's `[info]` for no secrets names how to give them. A launching process with `LADO_ENV_DIR` set gives
  it to the agent and its `lado mcp` among LADO's variables (`providers.agent_env`), so a
  supervisor's `spawn_worker` and `start_session` read the same folder, also when the login
  shell does not name it. `LADO_REPOS`, when set, goes the same way: a supervisor's
  `start_session` finds its project's repository and refuses a session inside `projects/`
  by LADO's workspace, not by one its login shell names or lacks (LAD-125). A tmux window starts with its server's environment, so the
  window runs `lado.agent_env <file> <argv>` (`interpreter.run_module`): it reads that environment from a file
  in the agent's config folder (`env.json`, mode 600 also when it was there before, removed
  once read; the one file under `LADO_HOME/agents/` that holds the values of a kit's MCP
  `env`, see `mcp_exec.py`; a Codex agent's `config.toml`, mode 600 too, holds what LADO
  carried of the user's Codex config, whose model providers may hold keys), keeps tmux's own `TERM`,
  `TERM_PROGRAM(_VERSION)`, `TMUX` and `TMUX_PANE`, and execs the agent's CLI, found on the
  resolved `PATH`. `lado doctor` shows the source and how long the shell takes (a warning
  above 2 s).
- Each agent has a temporary folder of its own (LAD-247): all agents of a machine run as one
  user with one `/tmp`, where two agents' files of one name (a draft `pr.md`) met. At each
  launch `providers.base.make_temp_dir` makes `<parent>/lado-<uid>/<session>/<agent>`, each
  level 0700; `<parent>` is the `TMPDIR` of the agent's merged layers (login shell, outside
  folder, project), else `/tmp`, so a user's own `TMPDIR` is the parent and is named in no
  warning. A `lado-<uid>` that is a link, not a folder, or another user's refuses the launch
  before its window opens (`<path> is a link`, `<path> belongs to uid <n>`). LADO gives the
  folder as `TMPDIR` among its own variables (`runtime._ours`), so it is in
  `LADO_LAUNCH_VARS` and a worker an agent spawns gets its own, not one inside its
  spawner's: `without_launch` drops it under `LADO_AGENT_ENV=inherit`, and the login shell
  starts from the caller's `SHELL_BASE` without it (`agent_env.from_shell`). That worker's
  parent is then the `TMPDIR` its shell's startup files export, else `/tmp` (or the tests'
  `LADO_TEMP_PARENT`, docs/testing.md). Each CLI
  honours `TMPDIR` for its commands' files; Claude Code keeps its own temporary root, where
  its scratchpad is, by `CLAUDE_CODE_TMPDIR` (else `/tmp/claude-<uid>`, one for all its
  agents), which `providers/claude.py` sets to the same folder (`AgentSpec.temp_dir`). The
  folder stays over a stop and a resume and goes with the agent's state
  (`remove_agent_state`: `finish_worker`, a spawn undone; `remove_session_state`: `lado
  forget`, the session's folder with it), found by a link `temp-dir` in its state folder.
  Every agent's instructions end with `runtime.TEMP_FILES`: temporary files in `$TMPDIR`,
  never at a fixed path in `/tmp`. It keeps agents from colliding by name; it is no security
  boundary, as every agent is the same user.
- An agent's status (busy / idle / background / waiting) comes from its hooks, never from
  screen scraping. Only the end of its process marks it `stopped`. A CLI command that leaves
  the conversation for another one in the same process (Claude Code's `/clear` and
  `/resume`) shows it as `starting` until the CLI is ready again; messages to it wait in the
  queue meanwhile and are typed in when it is `idle` again.
- `background`: the agent's turn ended while work it started still runs. A provider says so
  on its `TURN_END` (`Event.background`), and only there `hooks._idle` sets `background`
  instead of `idle`. It takes input exactly as `idle`: every check that decides a hand-over,
  a planned resume, a requeue or a failure's wait asks `state.ACCEPTS_INPUT` (`(idle,
  background)`), through `state.accepts_input` or its SQL form `state.ACCEPTS_INPUT_SQL`,
  never `idle` alone (a guard test in `tests/test_state.py`; `web/src/status.test.ts` for
  the UI, which reloads a worker's git state when it leaves busy). Where this section says
  an idle agent gets its queue or its resume, a `background` one does too. `state.working_agents`
  counts it as working, with busy and starting; it is no "needs you" and has no
  `status_reason`. After a wait that began in `background` (its latest `status` event
  before the wait, with no `spawned` event after it), the awaited `RESUMED` returns it to
  `background`, else to `busy` (`state.resume`, read from the events, no column). Claude
  Code: its `Stop` and `StopFailure` list the session's background tasks,
  `background_tasks`; a `running` or `pending` one is background work (seen live with
  2.1.295, `pending` only read in the binary; `providers/claude.py`). The list can be
  stale: a task killed in `/tasks` stays `running` with no hook after it, so the agent
  stays `background` until its next turn's end, which any message to it brings; no timer
  ends it (it would end an honest long `make check` too). Kilo and OpenCode never set it:
  OpenCode's task tool waits for its subagent (background subagents are its experimental
  `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`), Kilo is not checked (BACKLOG.md). Codex
  CLI never sets it either: its `Stop` (0.162) says nothing of work still running, though
  it can move a shell command to a background terminal, and LADO switches its subagents off
  (BACKLOG.md): both of Codex's versions of them, `features.multi_agent = false` the first,
  `agents.enabled = false` the second, which newer OpenAI models turn on through their
  metadata over the features (its `wait_agent`, "Waiting for agents", held a turn open, so
  the agent got no messages, LAD-167), and `features.multi_agent_v2 = false`, which Codex
  checks before `agents.enabled`.
- A turn that ends on an error is a turn's end: the provider's `TURN_END` carries
  `Event.error` (one short line), the agent is `idle` (or `background`) and gets its queue
  as after any turn, a `turn_error` event keeps the error (`lado log`), and
  `runtime.turn_failed` tells the supervisor in one line from `lado` (`turn of <agent>
  ended on an error: <error>; it is idle`, or `it is background: work it started still
  runs, and it takes messages`), or the human when it is the supervisor's turn. An error the provider says passes
  by itself (`Event.transient`) is told to no one at first: LADO resumes the agent.
  `state.schedule_resume` plans the n-th resume in a row `RESUME_DELAYS[n-1]` seconds
  later (30, 120, 480; `LADO_RESUME_DELAYS` replaces them, and their count is the number of
  resumes) in `agents.resume_at`; when it is due and the agent is idle, `runtime.sweep`
  (hooks or the session loop) queues one message from `lado`, `your turn ended on a
  temporary API error (<error>); continue where you left off (resume <n> of <N>)`, and
  drops the plan in the same transaction (`state.take_resume`); the message goes through
  the queue as any other. Any other status drops a planned resume (`state._set_status`):
  busy, the agent goes on anyway (a message, the human's input, its queue at the turn's
  end); waiting or starting (a dialog, failed messages, `/clear`), the human acts on it
  already, so dropping it is no silent drop, and it was told to no one, so it leaves the count of
  `agents.resumes`; an error while a resume is planned leaves the plan (`schedule_resume`): `after
  <N> resumes` follows N told ones. A transient error after the last resume goes
  to the lead as above, with `after <N> resumes`. Every turn's end that plans no resume (as
  usual, a permanent error, the resumes spent) sets the count back to 0. Claude Code's
  transient types are `overloaded`, `server_error` and `unknown` (also the machine's
  sleep; `claude.TRANSIENT`); Kilo and OpenCode mark no error transient: which errors reach
  `session.error` is not checked (BACKLOG.md). Claude Code runs `StopFailure`
  instead of `Stop` then (API errors: rate_limit, overloaded, authentication_failed,
  billing_error, server_error, also the machine's sleep, max_output_tokens, unknown) and
  ignores its output (`Event.output_ignored`: the queue is typed in, not printed); read in
  the binary of 2.1.291, not triggered by hand. Kilo 7.8.3 and OpenCode 1.18.34 publish
  `session.error`, then `session.idle` of the same session (read in their bundles); the
  plugin passes the error's name (and an `APIError`'s message and status) with that idle, drops it at
  `session.compacted` (a context overflow the CLI compacts its way out of ends no turn),
  and `MessageAbortedError` (the human's Esc) is no error. A request larger than the context
  never reaches `session.idle` on OpenCode 1.18.35: it compacts and resends without end, the
  compaction's own small request succeeding each round. So the plugin counts
  `ContextOverflowError`s in a row per session, a new prompt or a step of the turn (not of a
  compaction, whose message has `summary: true`) starting the count again, and at the third
  marks that error `stopped` with the count, the server's text as it came,
  and calls `client.session.abort`, whose
  `MessageAbortedError` does not replace it. Any turn that ends on an error gives two
  `session.idle` 20 ms apart (a server's 500 and an abort alike, on both CLIs): the first ends
  the turn on that error, and any more before the next prompt end no turn, or the second would
  pass as a clean end and decide the reply check. LADO's words of such a turn live in
  `opencode_family.turn_error` alone, before the server's, as an error is cut to one short line:
  a stopped turn's, with the server's text alone in `Event.details`, and a server's own refusal
  (`exceed_context_size_error`, LM Studio's HTTP 400, which both CLIs report as `UnknownError`
  and no overflow count sees: that turn ends at once), with the CLI's whole text there. Any other
  error past `base.ERROR_LIMIT` keeps its
  whole text in `Event.details`, which `turn_failed` puts in the message's body; checked in the TUI of OpenCode 1.18.35 and Kilo
  7.8.8 on a server of a small context, 6 and 7 requests to the idle. A model provider's refusal,
  any 4xx but a 408 (`base.is_refusal`), reads in LADO's words with the status and the
  server's first line (`base.refusal_line`: `base.REFUSALS` for 401, 402, 403, 429, a 400 that
  names an API key as a refused key, as cloud.ru answers a wrong key, else `refused the request`),
  its whole text in `Event.details`, and is never transient; LADO's words of a context too small
  come first (`base.context_line`, on all three CLIs): a turn of OpenCode or Kilo by the plugin's `status`, a Claude agent on a server by
  `last_assistant_message` of `StopFailure` (`claude.REFUSED`, as 2.1.295 calls a 402 `unknown`; the
  hook sees `LADO_MODEL_SERVER`, checked by smoke). Of the 4xx from 400 to 451 two differ there: a
  413 has `error_details`, `request_too_large: 413 <body>`, and a 404 the kind `model_not_found` with
  Claude Code's own words, no field holding the server's text, which stand in the line. A Claude agent
  on a built-in model keeps its words. `rate_limit` stays permanent: a short limit and a spent
  quota cannot be told apart, so no resume follows a 429 and the lead or the human decides. The
  words stand before the first colon, what `lado stats` counts as the error's kind. `base.without_keys`
  takes each `LADO_MODEL_KEY_*` of the hook's environment out of an error before any cut, as half a
  key would pass a later replacement. Measured on a fake server, requests of a turn (Claude Code
  with its own default of 10 repeats by `claude -p`; OpenCode 1.18.35, Kilo 7.8.8, about 70 s on a
  429 with no `Retry-After`): on a 401 OpenCode 2, Kilo 1, Claude Code 11 in 179 s; on a 429
  OpenCode 9, Kilo 6, Claude Code 11. `Retry-After` stretches these: OpenCode and Kilo wait what it
  names, 100 and 101 s at 20 s; at 600 s both were still `busy` after 150 s with nothing in the chat
  (by that proportion about 50 minutes, not measured), and LADO does not see the wait. A Claude
  agent on a server has `CLAUDE_CODE_MAX_RETRIES` 7: its TUI then sends 8 requests of the turn on a
  429, in 72 s with no `Retry-After`, 160 s at 20 s, and one at 600 s, where it gives up at once; 10
  on a 401, in 149 s; and as many again for the session's title, a
  request with no tools, that goes on a few seconds past the turn's end. Claude Code runs no hook when
  the human interrupts a turn with Esc, while text streams, while a tool runs or on a
  permission dialog (checked by hand with 2.1.292): the agent stays `busy`, or `waiting`
  after a `PermissionRequest`, until the human's next prompt in its window, whose `Stop`
  ends the turn and hands over the queue (BACKLOG.md). Codex CLI 0.162 runs no hook at all
  for a turn that ends on a model or API error. An agent on a built-in model stays `busy`
  (BACKLOG.md). For one on a server each pass of the session loop asks
  `Provider.failed_turn` (`runtime.check_turns`, busy agents only): Codex's reads what is new in
  the agent's newest `sessions/**/rollout-*.jsonl`, whole lines from the offset in
  `<home>/journal-offset`, kept there so that a restarted loop tells nothing twice. A
  `task_complete` with an `error` and no later `task_started` is a `TURN_END` through
  `hooks.handle`, the one path of a hook's, with `output_ignored`, as no hook prints it. A 4xx but
  408 reads in LADO's words (`base.refusal_line`), any 5xx and `server_overloaded` are temporary,
  anything else its message. A 400 whose body is no JSON object has no status in the journal
  (`other`, which is more than a 400): `Codex CLI's turn ended on an error`, then the text. The loop has no variable of the key: it gives
  the kept one (`base.without_keys(text, keys)`) before everything from `, url: ` or `, cf-ray: `
  on is cut. This reverses the decision of 2026-10-09 for these agents alone; the smoke holds the
  journal's format. The
  human's Esc, and a refused approval, run `Interrupt` and no `Stop`: a turn's end whose
  output Codex ignores (`output_ignored`, read in its source), so the queue is typed in, and
  a refused approval ends the wait at once.
- An agent's model and effort (`agents.model`, `effort`, schema 36) each have a source and
  a detail: `cli`, the CLI's own choice (its default or its own settings), `cli-config`,
  the user's config of the CLI that LADO carries into the agent, with the detail
  `profile <name>` when a profile gave it, `session`, the session's model ("chosen for
  the session"), `default`, its CLI's default of Settings → Agent CLIs ("default in Settings"), or
  `cli-changed`, another model its CLI named after the launch ("changed in the agent CLI").
  Later ways of choosing a model add tokens, not
  columns; `state.source_words` holds the words the API and the UI show for each, and an
  unknown token is shown as itself. A launch says what it set up (`Launch.model`, `effort`),
  which `runtime` records before the window opens (`state.set_model`): Codex's carried
  `model` and `model_reasoning_effort`, the chosen profile's before the top level's, as
  Codex reads them, and the session's model. In a trusted folder the repository's
  `.codex/config.toml` wins over a Codex agent's config.toml, and `-m` over both (Codex CLI
  0.162.0): so a Codex agent whose config names a model, LADO's or the carried one, also gets
  it as `-m`, and one with none runs on the repository's, which its launch records from the
  nearest `.codex/config.toml` up to the project root (a worktree's own) as `cli` with the
  detail `the repository's .codex/config.toml`. A session keeps its model as a power table
  (`sessions.power`, schema 37: rows `light`, `normal` and `heavy`, all the same for now, each a
  CLI and a model: built-in, external by a saved model's id with copies for the words after its
  removal, or `""` for the CLI's own settings; a stored text that is no table reads as
  `PowerTable.unreadable()`, which lists as any session and refuses a resume that keeps it).
  `model_settings.start_model`, read at each launch, says what an agent starts on: its CLI's row,
  else its CLI's default of Settings → Agent CLIs (`cli_defaults`), else nothing; a session that chose
  nothing keeps nothing, so a default changed later reaches the next resume and worker. Its name
  goes in `AgentSpec.model`, with `model_source`, which the provider applies its own way (Claude
  Code `--model`, Codex `model` at the top level and in the carried profile of its
  config.toml and `-m`, the OpenCode family `model` in its config content and `--model`, the only one that
  beats Kilo's remembered `/model` pick, the fake agent
  `FAKE_AGENT_MODEL`) and returns as `Launch.model` with that source, so a Kilo
  agent shows it also while its plugin names none. Both family CLIs remember the last `/model`
  pick in `<state>/<cli>/model.json`, read by every run: each of their agents has its own
  `XDG_STATE_HOME`, `LADO_HOME/agent-state/<session>/<agent>` (`OpenCodeFamily.own_state`), so an
  agent's pick of a server, a provider only its config has, stays out of the user's file, which
  LADO only reads. A new folder starts from a copy of that file without LADO's servers, and of
  the user's TUI settings, `kv.json`, as they are, each file when the folder lacks it. The
  variable moves `state` alone, logins stay; the agent's tools see it, and its prompt history and
  `locks` live there too. It is apart from the config folder: it outlasts a stop and a resume, and
  goes with the worker or the session. A CLI whose models on a server sit beside its
  own (`Provider.external_whole_process` false, the OpenCode family) gets every model ticked for it in
  `AgentSpec.servers` (`model_settings.agent_servers`), whatever it starts on: one OpenAI-compatible
  provider per server, `lado-<server id>`, so a rename changes nothing, labelled `LADO · <server>`,
  its key named as `{env:LADO_MODEL_KEY_<ID>}` and given only in `Launch.env`; a name or id that
  holds `{env:` or `{file:` is left out with a warning, as the CLI would expand it. Each server of
  the config is asked for its models' context at each start, resume and spawn, all at once within
  `model_servers.LIMIT_TIMEOUT` (`ServerEntry.limits`): nothing is stored, so a reloaded model is
  read anew, and a silent server only leaves its models with no limit. A known context goes in
  as `limit: {context, output}`, both always, as OpenCode refuses one without `output`; `output`
  is at most a quarter of the context, when none is reported 8192, or 32000 on a context of 131072
  or more: the CLIs' own default, so reading a cloud provider's context cuts no long answer. Below
  `Provider.min_context` the start warns, and goes on; so does an unknown context on a server
  outside the human's machine and network (`model_servers.in_network`: the hosts of the rule of a
  key over plain http, and a name with no dot or ending in `.local`, `.lan`, `.internal` or
  `.home.arpa`), where a late compaction costs money. An OpenCode agent on a server's model also gets npm's
  `fetch_retries=0` and `fetch_timeout=5000` (`OpenCodeProvider.server_env`) while
  `@opencode-ai/plugin` is not in OpenCode's config folder: any `plugin` entry makes it wait for
  that install, 72 s with outside traffic refused, 2 s with these or with the package there. LADO's
  plugin imports nothing from it. They reach what the agent runs in its shell too. Claude Code and
  Codex hold one model per process and get none of it: the server of their start model alone,
  with that model. A Codex agent on one gets in its own `config.toml`, over what was carried, a
  provider `lado-<server id>` with `wire_api = "responses"` and `env_key` (none for a server with
  no key, and then no `Authorization` goes out, also with `OPENAI_API_KEY` set), `model_provider`
  and `model` at the top level and in a carried profile, `web_search = "disabled"`, no carried
  effort, `model_context_window` and `model_auto_compact_token_limit` (the context less
  `Limit.output_room`) for a known context, and `model_catalog_json`: a `models.json` of its one
  model, made at launch from the last entry of `codex debug models --bundled` with no `tool_mode`,
  everything that adds a tool or a parameter off. A list that cannot be made warns, and `/model`
  then shows OpenAI's models. No `auth.json` is linked or written (`first_hook_blocker`), and
  `launched_on` reads the provider back. A server of a type the CLI refuses
  (`Provider.refuses_server`, `model_servers.suiting`: Codex on LM Studio, whose Responses API drops
  the type `namespace` of its MCP tools) is refused with no request
  (`model_settings.check_launch`). A start or resume checks the supervisor's model
  (`check_start`, by the probe of saving a model, within its timeout), and `spawn_worker` its
  worker's in the same way (`runtime._worker_start`), before anything of the worker exists; a
  worker with no model asks nothing. A worker takes a model by name (`spawn_worker(model=…)`, from
  `list_models`, which asks no server): the name picks its CLI (`model_settings.worker_start`),
  the source is `supervisor`, the session's table does not change, and nothing keeps the choice
  past that spawn. `""` is the CLI's own settings. An agent of another CLI (a worker
  spawned with another provider and no `model`) takes its own CLI's default; with none it gets no
  model: its
  record has no name, the source `cli`
  and the detail `the session's model <model> is for <CLI>`, and its launch warns, as
  `spawn_worker` returns and loop.log keeps its launch warnings. The agents' rows go at a stop, so
  an event `start_model`, written when the model changed, holds what the supervisor last started
  on: a resume compares it to say a default moved the model. In inherit mode
  (`LADO_AGENT_ENV=inherit`) a worker starts from its spawner's `lado mcp`, whose environment holds
  the spawner's launch: every launch names in `LADO_LAUNCH_VARS` what it set and what its CLI gives
  the processes it starts (`Launch.cli_env`: Claude Code hands the `env` of its settings to `lado
  mcp` too, 2.1.295), and `agent_env.without_launch` drops those, so neither a config, a key nor a
  server's address reaches a worker. A blanked variable goes with them: in this mode a worker of a
  supervisor on a server has no `ANTHROPIC_API_KEY` of the human's, and a built-in one that needs it
  is refused for its login. Then the events name it
  (`Event.model`, `effort`), recorded by `hooks.handle` first (`state.report_model`): every
  Codex hook's input has `model` and none the effort (0.162.0, its hook input schemas);
  Claude Code's SessionStart has `model` in the interactive mode LADO runs, at a start,
  compaction, `/clear` and resume, not in `claude -p`, and no hook gave the effort (2.1.295,
  checked by hand), so a `/model` typed in its terminal shows at the next SessionStart; the
  OpenCode family's plugin sends with `chat.message` the user message's model
  (`providerID/modelID`) and its `variant` as the effort, none when the model runs its
  default variant, so the effort goes back to the CLI's default (OpenCode 1.18.35, read in its
  bundle; Kilo runs the same plugin interface, its bundle not read: without a model in its
  message a Kilo agent shows the CLI's default with no name). A name equal to the one the
  agent has writes nothing, so a hook in every turn adds nothing to the change journal; a
  different one replaces it, and a source other than `cli` becomes `cli` with no detail:
  the CLI runs another model than the one chosen. Two names keep the source and the
  detail: the first one an agent with none gets (so the other CLI's note stays), and one
  the provider's `same_model` says is the chosen one's (Claude Code names the full model of
  an alias: `opus` → `claude-opus-5-5`; `best` and `opusplan` any of Claude's). LADO never reads the terminal for it and
  asks no model API.
- An agent whose process ends by itself goes through one transition, `runtime.agent_ended`
  (`state.agent_ended`, one conditional transaction): its session-end hook (`SESSION_END`,
  "its CLI exited") and the session loop's window check ("its window closed without a
  session-end hook") call it, nothing else marks an agent stopped by its end. It changes
  nothing and tells no one for an agent that is gone or stopped already; else the agent is
  `stopped` with an `ended` event for why (`runtime.status_reason` reads it: `lado ls`,
  `list_agents`, the UI's `AgentInfo.status_reason`), its `pending` and `sent` messages
  are `dropped` with one line from `lado` to each sender (`message #<id> to <agent> not
  delivered: <agent> stopped (<why>): <summary>`; LADO's own to the supervisor), its open
  questions are `closed`, and new messages to it are refused. The supervisor gets the way
  out for a worker: `finish_worker(name=...)` (with `discard=true` when the finish would be
  refused), then `spawn_worker(run=...)` for a run's worker; the human, for the
  supervisor: `lado stop <s>`, then `lado start <repo> --name <s>` (in the body). Its
  window is gone, as before (keeping a crashed agent's output: BACKLOG.md). LADO ending an
  agent itself writes that first and kills second, so the dying agent's session-end hook
  finds it gone or stopped and tells no one: `close_worker` (finish, a run's end or cancel)
  forgets the worker before it kills its window, `stop_session` (`lado stop`, `--all`,
  `lado update`) marks the session stopped before it kills its tmux session (only the
  migration path of an older lado.db kills first: its agents' hooks cannot write to it).
- On macOS an agent runs in the audit session of LADO's tmux server, its parent (not of
  the client, and its environment does not change it), and only the graphical audit
  session opens the login keychain, where Claude Code keeps its login. The server is born
  in the audit session of the process whose `new-session` finds no server on the socket.
  So before each attempt of `runtime.start_session`'s `new-session` (start and resume, the
  hook `gui_session.ensure_server`), a process outside the graphical session (`lado start`
  or `lado ui` over ssh, `lado update` resuming from ssh) with someone logged in to it and
  no server on the socket has launchd start the server in `gui/<uid>`; its agents can read
  the keychain. Linux and the graphical session start it as before; a launchd failure is
  a warning and the server starts here. A server that runs already is never restarted
  (the human's decision): once an agent's window is there (start, resume, spawn), an agent
  whose provider needs the keychain (`Provider.keychain_login`: Claude Code on a Mac
  without `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
  `CLAUDE_CODE_USE_BEDROCK` or `CLAUDE_CODE_USE_VERTEX` in its environment; the others
  never) gets a warning when the server runs outside the graphical session (`OUTSIDE_GUI`:
  `lado stop --all`, then start again) or nobody is logged in (`NO_GUI`), told whoever
  starts it as a blocker's reason is (`Started.warnings`, `spawn_worker`'s warnings,
  `loop.log`); the agent runs anyway. `lado doctor` (Graphical session), the system panel
  (`SystemInfo.gui_session`) and the update's plan (`agents_note`) say the same.
- Claude Code's "trust this folder?" in a repo it does not trust is answered by LADO ahead:
  `first_hook_blocker` records the trust of the repo's main root in Claude Code's global
  config (`claude.edit_config`) and returns a `note`, written to `loop.log` once and told
  nobody (LAD-163: LADO's own write is no problem), and nothing holds the agent. Only when
  that fails does the agent wait for the
  question, the reason saying why LADO could not record it. For an agent whose environment
  logs Claude Code in, or whose login it cannot read (`login_status` not `no`: an unknown
  login holds no agent), it also records Claude Code's first run
  (`hasCompletedOnboarding`, else the theme screen holds it) and approves the
  `ANTHROPIC_API_KEY` LADO gives it (its last 20 characters in
  `customApiKeyResponses.approved`, else "Detected a custom API key" holds it): one write
  and one note each, never any part of the key; a key the human rejected there is left,
  and the agent waits with a reason saying so.
- Two more Claude Code screens before the first hook (all seven `--permission-mode`s
  checked on a clean config with 2.1.295, LAD-163) are answered by the agent's own
  `--settings` file, with no write to a shared one: `enableAllProjectMcpServers: true`
  always ("New MCP server found in this project" for a repository's `.mcp.json`: its servers
  are taken, as for a human who trusts the folder) and `skipDangerousModePermissionPrompt:
  true` in `bypassPermissions` only (its warning screen). Auto mode's notice holds nothing.
- An agent of any provider still `starting` with no hook since its launch (`seen_at` 0)
  `Provider.start_silence` after it (30 s; 45 s for OpenCode and Kilo, past the 30 s their
  server plugin counts from its own init, 3 to 5 s after the launch; its window mark,
  `window_at`; a waiting window marks it anew when it starts the CLI) is held by a screen LADO
  does not know: the session
  loop's pass (`runtime.check_starts`) makes it `waiting` with a `blocked` event, `Waiting
  for an answer in its terminal: no sign from it <limit> s after its start. Open its terminal.`,
  in the same transaction as the look (`state.block_unheard`: a hook that came meanwhile
  wins), logged once. Its first hook ends the wait: its session start as for any start
  blocker, any other first hook (`state.seen` says it is the first) by
  `runtime.heard_at_start`, which puts it back to `starting`. A slow CLI past its limit is
  `waiting` for a moment and clears by itself.
- A Claude agent on a model server (`claude.py`, checked by hand on 2.1.295 against a fake server
  with every other way out refused) has that server in its own `--settings`, not in its
  environment: flag settings beat the environment and the user's and the repository's settings, and
  `ANTHROPIC_BASE_URL` alone sent the human's login, sent `ANTHROPIC_API_KEY` beside the server's
  token, and lost to a base URL in `~/.claude/settings.json`. So the settings hold the server's root
  (`ServerEntry.root`: Claude Code adds `/v1/messages`, the `/v1` of `base_url` would double),
  `availableModels` and `ANTHROPIC_DEFAULT_MODEL` and `ANTHROPIC_SMALL_FAST_MODEL` with the model,
  so that `/model` shows Default and the model and a subagent's `model: haiku` falls back to it;
  `SERVER_BLANKS` as empty values (`ANTHROPIC_UNIX_SOCKET`, on which an empty value in the settings
  does nothing, goes empty in the launch's environment); `SERVER_SWITCHES`; for a known context `CLAUDE_CODE_MAX_CONTEXT_TOKENS` and
  `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (`Limit.output_room`, at most `claude.SERVER_OUTPUT`, 16384: it asks
  for 32000 by itself, over a 64K context with a prompt of 45K, and retries for hours what the server
  ends, and on a context of 131072 its request at a compaction passed the context with 32000) and,
  where that cuts the output, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, the context less the output, read by
  2.1.319 and not by 2.1.295; `CLAUDE_CODE_EFFORT_LEVEL` `auto` of
  `SERVER_SWITCHES` names no effort, where `effortLevel` in `--settings` loses to the user's; `permissions.allow` with
  `mcp__lado__*`, as auto mode's classifier, in a `defaultMode` of the user's settings too, asks the
  same model, and one of no usable answer has LADO's tools blocked at every try; `apiKeyHelper: printenv LADO_MODEL_KEY_<ID>`, whose output goes out in both `x-api-key`
  and `Authorization`, or `echo no-key`, as with no credential at all the login goes out. The file
  holds no secret and is rewritten at each launch. The launch's `LADO_MODEL_SERVER` tells the
  provider it needs no login, as `claude auth status` reads no `--settings`: `needs_login`,
  `keychain_login` and `first_hook_blocker` go by it; `runtime.check_login`, which runs before the
  launch, goes by a `start.server` on a CLI of one model per process, and so does the launch
  window's `login_missing` (`server/launch.py`), on the CLI's default model. The model's id says
  no server, and may be a built-in model's too, so `Provider.launched_on` reads the agent's server
  from its settings for its card, `lado ls` and `list_agents`: while it runs, as they go with it.
  The first run is recorded as for any agent. A `system` message ends `messages`, and `thinking` and `output_config` stay in the
  body: only a real server tells whether it takes them.
- A Codex agent's own Codex home (its config folder, `CODEX_HOME`) is settled so that no
  screen holds it: its config.toml trusts the repository's main root (`trust_level =
  "trusted"` for its real path, which covers a worker's worktree) unless the user's Codex
  config has an entry Codex goes by for the folder, carried as it is (`untrusted` too);
  trusts the repository's own hooks (`.codex/hooks.json` and `.codex/config.toml`'s, from
  the project root down) by Codex's hashes, as a human who trusts the folder takes them, a
  hook the user disabled staying disabled; switches plugins off (`features.plugins =
  false`: Codex would clone its catalogue into each new home at its start); and keeps the
  login in the file (`cli_auth_credentials_store = "file"`). Its login is settled by
  `first_hook_blocker` (`codex._settle_login`), before its status is read in that home:
  `auth.json` becomes a symbolic link to the user's (`$CODEX_HOME/auth.json` of the agent's
  environment, else `~/.codex/auth.json`, kept by `launch_command` in the agent's folder as
  `user-codex-home` for the waiting window, whose `CODEX_HOME` is the agent's), also before
  that file exists; Codex writes it in place and re-reads it before a refresh, so one
  refresh serves every agent and the user's own Codex (0.162.0, checked on a ChatGPT login:
  three agents refreshing at once). With `OPENAI_API_KEY` in the agent's environment and no
  `CODEX_ACCESS_TOKEN` (which Codex reads itself, before its file) it is a file of the
  agent's own instead, mode 600, holding the key as `codex login --with-api-key` writes it:
  Codex's TUI does not read the variable. Each write is a `note`; one LADO cannot make is a
  `warning`, which says that an agent whose model needs a login then waits for one (its
  status, read in its own home, finds none) until it starts again with its folder
  writable. Nothing is written into the user's Codex home.
- A Codex agent on Linux in any mode but `bypassPermissions` would otherwise stand in
  Needs you at its first shell command where Codex's sandbox cannot start: it runs
  commands through bubblewrap, which needs an unprivileged user namespace, and Docker's
  seccomp refuses one in a container (LAD-151; Codex 0.162's way without bubblewrap
  refuses too), so Codex asks "retry without sandbox?". Before each launch (start, resume,
  worker) LADO asks Codex itself, `codex sandbox -- true` in the agent's home, folder and
  environment (`codex._sandbox_error`). When it fails, in LADO's container the agent runs
  with `--sandbox danger-full-access` and no permission profile, its mode's approvals kept,
  the container being its boundary as for every other CLI there; on a host it keeps the
  sandbox. Either way the launch warns (`lado start`, the UI's start notice, loop.log for a
  worker). macOS's sandbox is not bubblewrap: no probe there.
- A new session or worker whose CLI needs a login (`Provider.needs_login`, asked with the
  environment the agent would start from: Claude Code always; Codex when the model
  provider of the user's config, the chosen profile's, else the top level's, is OpenAI's,
  its default, or has `requires_openai_auth`) and has none is refused before anything of it is stored or made
  (`runtime.check_login`, `lado.logins.refusal`): `start_session` checks a new session and
  a resume by hand (`lado start` of a stopped session, the UI's Resume: `logins.RESUME`,
  "… so the session was not resumed: …", LAD-163) by the supervisor's provider, the one
  agent a resume starts, never LADO's own resume (`reason` `AT_START`, or `wait_for_login`:
  `lado update`'s `lado start --wait-for-login`, a hidden flag), and `spawn_worker` each
  worker by its own provider, both in
  `runtime.agents_env` over `runtime.agent_layers(project)`, the environment the agent would start from, so a project's
  secret that logs the CLI in counts; `lado start <git-url>`, `--new` and the UI's From
  scratch check before the clone or the folder (`runtime.check_start_login`). Only `no`
  refuses; an unreadable login goes on as below.
- An agent LADO resumes by itself whose CLI needs a login waits for it before anything else, as does a new
  one whose login went between the check and its launch: before its window starts, once
  `first_hook_blocker` has settled what it can (`runtime._before_window`, at every launch:
  it may give the agent its login, Codex's link), LADO asks the provider (`needs_login`,
  `login_status`) with the agent's launch environment (`runtime._held_for_login`); at `no`
  the agent is `waiting` with `logins.wait_reason` (`<CLI> is not
  logged in: log in in Settings → Agent CLIs, or set <variable>; the agent
  starts by itself once you do`), told and logged as a blocker's reason is; what needs no
  login is settled at once (`first_hook_blocker`: Claude Code's trust, its note in
  `loop.log` only; a question it would still ask waits for the window), and its window
  runs `lado login-wait` (`lado.login_wait`) instead of `lado.agent_env`: it reads and
  removes the launch file, and every `logins.POLL` seconds lays the file layers read anew
  (the outside folder, LADO's secrets, the session's project) over the environment it
  holds, never over LADO's and the provider's own variables, its provider's login taken
  whole from one layer (the launch file keeps the login shell's own login variables,
  `shell_login`, the lowest such layer), and asks again. Once logged
  in it runs `first_hook_blocker` there (the first run above: its note in loop.log only, a
  reason or warning also printed in the agent's terminal), marks the CLI's launch
  (`state.window_opened`, from which the limit above counts), puts the agent
  back to `starting` (or waits with that blocker's reason) and execs the CLI: the agent
  reaches its first hook with no restart. A login shell's change needs a new agent. A
  login LADO cannot read (`unknown`: a failure, a timeout, odd output) never holds an
  agent: the launch goes on with a warning. The UI shows the wait by `AgentInfo.login_wait`.
- An agent whose CLI asks the human before any hook (Claude Code's "trust this folder?"
  when LADO could not record it, Codex's; `Provider.first_hook_blocker`) waits from its
  start: after `launch_command` and before its window starts (`runtime._before_window`, for start,
  resume and spawn), `state.block` sets it `waiting` with a `blocked` event, whose detail
  is why and what to answer. That reason holds while no `status` or `spawned` event came
  after it (`state.block_reasons`, read by `_Reasons`: `lado ls`, `list_agents`,
  `AgentInfo.status_reason`, Needs you), before the reason of failed messages. Its first
  `SESSION_START` ends that wait (also only that one: a compaction's session start leaves
  any other wait), and its queue is handed over as after any start; an answer that ends
  the CLI ("No, exit") is an end like any other (`agent_ended`, the window check). Who
  starts it is told the reason, or the provider's `warning` when it cannot tell: `lado
  start` on stderr, the UI's start in `Started.warnings`, `spawn_worker` in its result's
  `warnings`, and each once in `loop.log` (start, resume and spawn); a `note` goes to
  `loop.log` alone (`runtime._log_notes`).
- An agent `waiting` for the human (a dialog in its terminal) is `busy` again as soon as the
  human answers there: the neutral `WAITING` and `RESUMED` come in pairs with the same key
  (`Event.key`, the provider's id of the request), and only `RESUMED` with the key it waits
  for ends the wait (`state.wait`, `state.resume`: one conditional update, kept in
  `agents.waiting_for`). One open request at a time: a new one replaces the key, so of two
  open dialogs only the answer to the latest ends the wait (the agent shows `waiting`
  longer, never shorter). A wait without a key (failed messages, `runtime.sweep`) keeps the
  key of a wait already open, and any `RESUMED` ends it. A `RESUMED` of an agent not
  `waiting` (a late async hook after its turn's end, a stopped agent) changes nothing; any
  other status drops the key. `RESUMED` leaves the queue alone: a busy agent gets it when
  its turn ends.
  Claude Code (checked by hand with 2.1.289): `PermissionRequest` runs just before a dialog
  shows (with `bypassPermissions` only for an `AskUserQuestion` question, never for a call
  `dontAsk` refuses; mode `auto` not checked, BACKLOG.md), and `Elicitation` before an MCP server's
  form; the tool call's `PostToolUse` or `PostToolUseFailure` (async: they run after every
  tool) and `ElicitationResult` are the answer. `PermissionRequest` has no `tool_use_id`,
  so the key is the tool and its input (an `AskUserQuestion`'s questions only: its answer
  adds to the input), or the MCP server of an elicitation. When the human refuses a
  permission or dismisses a question, no hook runs: the agent stays `waiting` until the
  human types (BACKLOG.md); a refusal with a comment ends the wait at the turn's end.
  `Notification` is not used. Kilo and OpenCode: the plugin reports `permission.asked`,
  `question.asked` (WAITING) and `permission.replied` (also a refusal),
  `question.replied`, `question.rejected` (RESUMED) with the request's id, also for
  subagents' sessions; with `--auto` the permission events are not reported. Codex CLI
  (0.162, checked by hand): `PermissionRequest` runs before an approval dialog (a shell
  command that leaves the sandbox, an MCP tool call), its tool call's `PostToolUse` is the
  answer, keyed by the tool and its input; a cancelled MCP call runs no `PostToolUse`, so
  the wait ends with the turn's `Stop`.
- A message is a one-line `summary` (at most 200 characters; a longer or multi-line one is
  refused) and an optional `body` with the details. Only one short line per message reaches
  the recipient: `[from <sender>] <summary>`, plus ` (#<id>, <n> lines: call read_messages)`
  when there is a body, ` (#<id>, <n> lines, <k> artifacts: call read_messages)` with
  artifacts attached too, ` (#<id>, <k> artifacts: call read_messages)` with only those. A
  message with a body or an attachment is one to read (`state.TO_READ`): `read_messages`
  returns the caller's handed-over (`sent` or `delivered`), unread ones (with each
  attachment's full name, title, media type, size and whether it `changed` since) and
  marks them `read`; reading a `sent` one confirms it, as the agent has it in the tool's
  result (any channel); a `pending` one it first takes with the whole queue, in order, as
  every tool call does (`tool_result`, below), so a message that waited is returned at
  once, and its result's lines are those of the taken messages without anything to read.
  A stop or finish drops such a message unread.
- A `send_message` to agent X is refused, with nothing queued, while a message from X waits
  for the caller unreceived (`state.waiting_from`: `pending`, or handed over with
  something to read and not read): `X's message #<id> waits for you, so nothing was
  sent: ...` (`runtime._refuse_while_waiting`), carrying the caller's queue as any tool's
  error does. It compares sender and recipient only, so the "send your report" to a
  worker whose report is on its way never goes out; once the caller got the message (its
  line in that very error, its body by `read_messages`), the same send goes through. A
  message to or from `human` is never refused so: messages to the human stay
  `delivered`, never read. The supervisor stays quiet with the human: it does not relay reports,
  and the details are in `lado log`.
- The human is a participant of messages, `human` (design in
  [docs/design/ui.md](ui.md), The human in the session): agents write to it with
  `send_message(to="human")` and ask with `ask_human` (a question, up to 6 choices, a free
  answer by default); such a message is `delivered` at once into no window, and the UI's
  Activity chat shows it. The human writes from the UI's composer (`runtime.write_as_human`,
  only through the server's API; to the supervisor by default) through the same queue,
  confirmation and retries, and the agent gets `[from human] ...`. A message may carry the
  files the human uploaded (`artifacts.upload`, the session's scope; at most
  `MAX_HUMAN_FILES`, attached as `send_message` attaches; with files the text may be empty,
  the summary then `<n> file(s): <names>`); a run's worker reads such a file as `/<name>`.
  When the human writes to another agent, the supervisor gets a one-line copy from `lado`,
  `human wrote to <agent>: <summary> (#<id>[, <k> files])`, without the attachments, queued
  in the same transaction (answers and dismissals get none), and
  only while the supervisor runs: a stopped one would never get it, so there is none. An answer
  (`Answer to #<id>: ...`) or dismissal (`Dismissed #<id>`, with the human's comment as its
  body when they wrote one) comes to the agent the same way. The answers to several open
  questions of one agent come together (`runtime.answer_questions`: each checked first, all
  queued and their questions closed in one transaction, `state.reply_to_questions`, then
  the agent's queue taken once), so an idle agent gets them in one hand-over and starts one
  turn; one the core refuses refuses them all, with nothing changed (`answer_question` and
  `dismiss_question` are one-reply calls of it).
  No agent may be named `human` or `lado` (`state.RESERVED`). Messages to `human` are never
  dropped (stop, finish). The open questions of an agent that ended or was finished in a
  running session are `closed`; every stop of a session (`state._stop_session`) makes the
  session's open questions `stopped`, as no agent is left to get an answer and a resume
  starts a new conversation. A resume (`runs.resume`, the one way back) then queues for the
  new supervisor, after its `session resumed`, one message from LADO listing the `stopped`
  questions no supervisor was told of, with their artifacts, to ask again what is still
  needed. `answered_by` of a `stopped` question holds that message's id: it is told once,
  and again only when the message was `dropped` (a failed resume, or a stop before the
  supervisor read it). A reply to a `stopped` question is refused, also while the session
  is stopped (`question #<id> is stopped`). LADO's
  instructions tell the supervisor to answer where the human asked: a `[from human]`
  message with `send_message(to="human")` or `ask_human`, text typed into its window in the
  window. At each turn's end, before the queue is handed over, the human's messages the
  agent got (not answers or dismissals) are checked once: `replied` if it wrote to `human`
  after it got them (by `sent_at`, when each was handed over, not by id), else `missing`,
  which the chat shows as "replied only in its terminal". A turn that ended on an error
  checks nothing: the next clean turn decides, as the agent has seen the message by then.
- The lead recommends on each question to the human, a core mechanism of every kit and
  provider: when a flow gate opens (approval, choice, loop limit) or an agent other than
  the lead asks the human (`ask_human`), LADO asks the lead with one message from `lado`,
  `recommend on gate #<id>: <run> at <state>` or `recommend on question #<id> of <agent>`
  (`runs.recommendation_request`, `runtime.ask_recommendation`; its body the question,
  the options or choices, the note or the details, the artifacts the gate reads and
  `runtime.RECOMMEND_REQUEST`; the note's or the question's attachments attached), queued
  and marked `asked` in one transaction (`state.ask_recommendation`) and handed over as
  any message; when the lead's own `flow_advance` (or `flow_start`) opened the gate, the
  request is a notice in the tool's result. A lead that does not run is not asked: the gate
  or question opens all the same. The lead answers with its MCP tool `recommend(text, gate
  | question, choice, disagrees)` (`runtime.recommend`: one of `gate` or `question`, a
  text of at most `MAX_MESSAGE`, a gate's option as `lado answer` takes it, one of a
  question's choices, never its own question; a later call replaces it until the human
  answers), stored on the gate's or the question's row (schema 26) and shown in its card
  and in `lado answer`; the human answers whenever they want. A request still `pending`
  goes with its gate or question in the transaction that closes it (answer, dismissal,
  override, cancel, the asker's end). At the lead's turn's end (`hooks.handle`'s
  `TURN_END`, after `turn_failed` and before the queue is handed over, so a request in
  this hook's output is not counted) each open `asked` one whose request the lead got (a
  notice, or a message `delivered` or `read`) becomes `missing`, unless a resume is
  planned (`agents.resume_at`); the lead's end and a stop mark every `asked` one
  `missing`. Codex CLI runs no hook for a turn that ends on an API error: there it stays
  `asked` until the lead's next turn's end. LADO's lead instructions say to answer only
  with `recommend`, never with a separate message to the human, with a short view of its
  own and `disagrees` when it disagrees. Kit sdlc's supervisor paragraph "A gate opens…"
  still asks for a message to the human until the kit's own change.
- No prompt and no message text on an agent's command line, which `ps` shows to every user
  of the machine: the role and LADO's instructions go in a file (Claude Code
  `--append-system-prompt-file`, Kilo and OpenCode `instructions`), and an agent's first
  input (a worker's task or step, a resumed supervisor's messages from `lado`) is a pending
  message from `lado` in its queue, with the text as its body (`your task` or `flow <run>:
  step <state>` for a worker; `agents.task` keeps the full text). Its session-start hook
  makes it idle, which hands the queue over as any other (below): the agent gets one line
  and reads the text with `read_messages`. A spawn or resume that fails drops it with the
  rest of the queue; the next resume writes LADO's messages anew. A supervisor's queue may
  also hold the human's first message (`start_session(prompt=)`, checked by
  `runtime.check_prompt`: `lado start --prompt`, the New session window), a message from
  `human` queued after LADO's own (a resume's `session resumed`, a brief), whose summary is
  the fixed `runtime.FIRST_MESSAGE` and whose body is the whole text, also for one line, so
  the text never goes on a command line below; a failed start drops it with the queue.
  Kilo and OpenCode lose text typed into their TUI before its prompt has focus, which comes
  1.5 to 3 s after the server plugin's init, later under load (Kilo 7.8.8, OpenCode 1.18.35).
  So their session start is the TUI's: `opencode_tui_plugin.js`, which LADO gives the agent
  alone in `tui.json` of its config folder (`OPENCODE_TUI_CONFIG`, `KILO_TUI_CONFIG`), runs
  `lado hook tui.ready` on the first frame with a focused renderable, and the server plugin's
  init reports nothing. A message sent before that waits `pending` with no attempt counted,
  while the TUI takes its time; a report ends that: `tui.ready`, or with a live server plugin
  `tui.silent`, its timer counting from the plugin's init and not from the launch, so before
  the start's limit of 45 s (`Provider.start_silence`), past which the agent shows the reason
  of a silent start. A renderer without that API
  reports at once: a paste may be lost then and the sweep types it again. A TUI plugin that
  does not report (a CLI's change, or a TUI merely slow, which nothing tells apart) must not
  leave the agent `starting`: the server plugin, alive, runs `lado hook tui.silent` 30 s after
  its init (`tuiWait`, dropped at `dispose`), a `SESSION_START` with `Event.note`. When that
  start makes the agent ready, the note goes to its lead (`runtime.start_note`) and its queue
  is typed in as for any idle agent, so a TUI still blank loses it; once the agent is ready that
  hook is dropped before `state.seen`, as it would pass for a sign after a paste (`_plan`).
  `tui.ready` carries `Event.ready`, for what was typed in before it. A paste not confirmed
  starts over from that hook as a first attempt (`state.restart_typed`), and an agent busy
  for it alone is idle: no turn ran, so no hook would end that. The paste goes back to the
  queue after `RETRY_DELAYS[0]`, not at once, so a CLI that held it confirms it by
  `chat.message` and it is not typed twice. A real turn stays `busy` by itself; it can leave the
  second line of a paste of two unconfirmed, and the agent is then `idle` until that goes in.
  `hooks.handle` also ends a wait with no key, the one failed messages left, which
  `state.seen` has just put back in the queue; a dialog's wait, with its key, stays. Claude
  Code and Codex set neither field. Their queue's lines at launch
  (`Capabilities.notice_on_argv`), never a body, go on `--prompt` (`runtime._launch_command`),
  handed over then as `typed` with its first attempt and confirmed by `chat.message` as
  typed text, before or after `tui.ready`; the agent stays `starting` until its session
  start or that `chat.message`, whichever comes first. Codex CLI takes them as
  its own `[PROMPT]` argument, and starts its session (SessionStart) only when its first
  input is submitted (`Capabilities.session_start_on_first_input`): an agent of it with an
  empty queue (a new supervisor) first gets `runtime.FIRST_INPUT` from `lado`, a message
  like any other, so a Codex supervisor's start costs one short model turn. The line asks
  the agent to end that turn and never to wait: a model with a tool to wait takes "wait"
  literally, and the turn that does not end gets no messages. Codex's
  `SessionEnd` is not used: after `/resume` it runs for the conversation left, once the
  next one has started; an agent whose Codex exits is ended by the window check.
- A queue is handed over by one of two channels at a turn's end (and a third, mid-turn,
  below), kept with each message
  (`messages.channel`), and stays `sent` until the agent confirms it (then `delivered`):
  - `typed`: pasted into the agent's window, confirmed when its prompt-submit hook sees
    the message's line. A paste that ends in a backslash gets a space after it
    (`tmux.send_text`): Claude Code reads `\` + Enter as a line break and would not submit
    it; Kilo and OpenCode submit either.
  - `hook_output`: at a turn's end, where the provider can (`deliver_on_turn_end`) and the
    CLI does not ignore the output (`Event.output_ignored`), carried on in the turn-end
    hook's output. Kilo and OpenCode: the plugin sends it with `promptAsync` as the next
    user message, for which `chat.message` runs, so it is confirmed by its line as typed
    text is (Kilo 7.8.3, OpenCode 1.18.34, read in their bundles; the live test checks it);
    a `promptAsync` that fails is reported by the plugin as `plugin.error` (the neutral
    `HOOK_ERROR`), one line in `hooks.log`, and is no sign of life. Claude Code runs no
    UserPromptSubmit for a Stop hook's `block` reason; the Stop that ends the turn it went
    on to has `stop_hook_active` true (`Event.continued`; checked by hand with 2.1.291,
    also after two blocks in a row), which confirms the agent's `hook_output` messages, and
    only those: another Stop hook of the user's may have made the turn go on too. The turn
    that goes on from the output reads the batch's bodies at once (`read_messages` takes
    `sent` ones); what is left of the batch waits for that Stop. Claude Code and Codex
    take what a Stop hook that ended by itself printed
    (`Capabilities.output_taken_when_printed`): `hooks.main` marks its batch printed right
    after the print (`state.output_printed`, `messages.printed_at`; a failing mark is
    logged and leaves it unmarked, never `typed`), and their turn-end hooks get LADO's
    limit, `base.TURN_END_HOOK_TIMEOUT` (60 s: Claude Code's `Stop` and `StopFailure`,
    Codex's `Stop`; both kill a hook that runs longer and go on, checked by hand with
    2.1.296 and 0.162.0).
  Every path takes the queue the same way, `runtime.hand_over`: only from an idle agent
  with no batch sent and unconfirmed (checked as the queue is taken), which is then busy;
  so an agent has at most one sent batch at a time, and a new message waits while one
  handed over before is unconfirmed. A busy, waiting or starting agent's queue is handed
  over on every switch to idle (`hooks._idle`: its session start without a task, a
  conversation start, a turn's end), and by `runtime.sweep` when the agent is idle, so the
  session loop types in within one pass what every hook missed. At a turn's end the order
  is: confirm the `hook_output` batch the turn went on from, check the replies to the
  human, set idle and hand over, sweep; so a chain of turns that go on from the hook's
  output gets each new batch at once. A sender queues first and takes the queue of an idle
  agent second, a hook sets idle and takes the queue in one transaction
  (`state.take_pending`'s `become`), so the session loop never sees the agent idle with
  the queue the hook takes: exactly one of them hands a message over, and the sender's reply says `sent` also when a hook or the loop handed its
  message over in between (and refuses, as for an agent not running, when the agent was
  finished or stopped in between). A session's end refuses in one sentence of its own
  (`runtime.CUT_OFF`, a 400 at the server), however far the delivery got: the session is
  stopped by the database, which a stop marks before it kills tmux, or typing failed and
  its tmux session is gone (`loop.tmux_gone`, whatever tmux's words). A session the
  database does not know has no Resume: `no running agent` where a message is stored,
  `unknown session` when it was forgotten during the typing. Any other failure of tmux
  stays an error, and the message stays as the stop or the sweep leaves it. tmux calls name a session and a window with `=`: tmux matches any other target by
  prefix, so text for a stopped `lad` would land in a running `lad-1`. A queue is taken
  only so, also an agent's first input, but for the third channel:
  - `tool_result`: in the middle of a turn, the result of any call of a `lado` MCP tool
    carries the caller's whole queue (`mcp_server._Server.call_tool`,
    `runtime.take_mid_turn`), after the tool's own content, under `runtime.MID_TURN`
    ("Messages that came during your turn:"); a tool that fails carries it in its error
    text, and `read_messages` takes it before it reads. The lines are `delivered` at once
    (`sent_at` set): the agent has them as it has `read_messages`' result, so no hook
    confirms them, no turn's end hands them over again and the sweep never retypes them.
    Without a queue the result is unchanged. Before 0.45.0 a message to a busy agent
    waited for its turn's end, and a supervisor that waited for a worker inside its turn
    asked again for a report it had (LAD-172). The lines go twice: a text block after the
    tool's content and `lado_messages` in its structured content, when there is one,
    since the CLIs show the model different parts: OpenCode the content when there is any
    (its structured content only for a result without content; read in its 1.18 bundle,
    errors as their text blocks), Claude Code the structured content (seen in a session:
    `{"result": ...}`), Codex the structured content when there is one (its
    `FunctionCallOutputPayload` from a `CallToolResult`, open source, not re-read for
    this change); Kilo's binary has no readable bundle, as OpenCode's fork it is taken to
    behave as OpenCode. Either way the model gets the lines once.
  What was handed
  over and is unconfirmed is typed again only by the sweep's rule (below), also into a
  busy agent whose window shows no sign of having taken it; never into one that is
  waiting, starting or stopped.
- What happens to an unconfirmed message is one rule, `runtime.sweep` (`_plan`), run by
  `send_message` to the agent, by each of its hooks that makes it idle, and every
  `loop.INTERVAL` seconds by the session loop (below). Each hand-over is an attempt; after
  the n-th, the message is left alone for `RETRY_DELAYS[n-1]` seconds (15, 30, 60). A
  message the agent read (`read_messages`) is confirmed and out of this rule: never typed
  again, never failed, nor failed with its batch. Then, by its channel:
  - `hook_output` (its first attempt): for a provider whose CLI takes what the hook
    printed (`output_taken_when_printed`: Claude Code, Codex), the delay is not
    `RETRY_DELAYS[0]` but the fact of the print: a batch marked printed waits for the
    end of the turn that goes on from it, however long its model steps run without a
    hook, up to `runtime.HOOK_OUTPUT_BACKSTOP` (600 s, the CLIs' own default hook limit:
    only a CLI that broke its promise to take it gets there); one never marked printed
    (the hook was killed or failed before the print) waits `runtime.HOOK_OUTPUT_WAIT`,
    the hook's limit and 15 s, after which no print can come. Kilo and OpenCode (more
    can fail after the plugin's print) wait `RETRY_DELAYS[0]`. Then, if no hook of the
    agent ran since (the CLI did not take the output, the hook failed after the
    hand-over, or the turn goes on that long without a hook), it is typed in, once, with
    the queue, and is `typed` from then on: a turn that did take it gets it twice, which
    is better than never (the human's decision); if a hook ran and the agent takes input,
    it goes back to the queue; if a hook ran and the agent is busy, it is left to the
    turn's end. It never fails by this channel. A batch the CLI did not take stops waiting
    for a turn that goes on from it, so a later turn another Stop hook makes go on never
    confirms it: a turn's end without `Event.continued`, or a hook that fails after the
    hand-over (`hooks.main`, its own batch only), makes it `typed`
    (`state.output_not_taken`), and the rule below takes it on: with the agent idle, it
    goes back to the queue after the delay and is typed in by the same sweep.
  - `typed`: if no hook of the agent ran since the paste (`agents.seen_at`; a dialog took
    the text) and the agent is busy, it is pasted again with the queue; if hooks ran but no
    prompt held its line and the agent is idle, it goes back to the queue and is delivered
    as usual. After `1 + len(RETRY_DELAYS)` attempts and the last
  delay it is `failed` (`lado log`): the agent is set `waiting`, `lado ls` and
  `list_agents` (`status_reason`) say why and what the human can do (until the agent's next
  hook), and nothing more is typed into it in that sweep; the messages typed together with
  it that are not back in the queue fail with it, attempts left or not; the sender of each
  (the supervisor for LADO's own messages) gets one line from `lado`; a failed notice is not
  reported. The agent's first hook after that puts the messages no hook ran after back in
  the queue with their attempts from 0; the ones it saw and never confirmed stay failed.
  `LADO_RETRY_DELAYS` (`2,0.5,0.5`) replaces the delays in the processes started with it:
  only tests set it, the integration tests for each test (`tests/integration/conftest.py`,
  also `runtime.RETRY_DELAYS` in the test's own process); a test that moves time itself
  takes the `production_retry_delays` fixture. `LADO_HOOK_OUTPUT_WAIT` and
  `LADO_HOOK_OUTPUT_BACKSTOP` (seconds) replace those two waits likewise; only tests set
  them, each test itself, never the integration conftest. A test whose agent is the fake
  provider with that flag (`fake-printed`) takes the `fakes_known_to_lado` fixture, so
  its session loop, whose sweep asks the agent's provider, knows the fake providers.
- The session loop is a hidden `lado loop <session>` (`loop.py`), a process of its own
  outside tmux that `lado start` (also a resume) starts once the tmux session exists. It
  sweeps the session every `loop.INTERVAL` seconds (2; `LADO_LOOP_INTERVAL`, a positive
  number of seconds, replaces it in the processes started with it, and a value that is none
  stops them with an error at once; only tests set it, the integration tests to 0.25 s in
  `tests/integration/conftest.py`, with `loop.INTERVAL` in the test's own process; it is
  also how long `loop.wait_stopped` waits, three of them; `loop.log` names it at the
  loop's start), so an unconfirmed message is typed again or failed on time with no send
  and no hook. Before each sweep it looks at the session's windows
  (`runtime.check_windows`, one `tmux list-windows`, no screen; the pass's only tmux call):
  an agent not stopped whose window opened and is missing in two passes in a row has ended
  (`agent_ended`), so a CLI that crashed before its first hook or in a turn is `stopped`
  within a few seconds. The agent's row is written before the slow part of its spawn (its
  task queued, the launch command, the first-hook blocker, the tmux call), so the spawn
  marks its window opened (`agents.window_at`, `state.window_opened`) right after
  `tmux new-window` (a worker) or `new-session` (the supervisor) returns, and the check
  leaves an agent without the mark alone however many passes miss its window, up to
  `runtime.SPAWN_DEADLINE` (60 s) from its row: past it the spawning process died, and the
  agent ends at once with "its start ended before its window opened" (`SPAWN_DIED`).
  After it the pass looks for agents a screen holds before any hook
  (`runtime.check_starts`, the safety net above).
  A failing list changes nothing: only then
  a `tmux has-session` tells a gone tmux session (the loop ends) from another failure (an
  error of the pass; a tmux that cannot run is one too; `loop.tmux_gone`). The supervisor's
  window, when it was the last, takes the tmux session with
  it: that stays "tmux session is gone". One per session: it holds an exclusive
  `flock` on `LADO_HOME/loop/<session>.lock` (gone with the process, no pid file); a second
  one exits when it cannot take the lock within `loop.LOCK_WAIT` (0.1 s, so a moment's lock
  check by `lado ls` does not make a starting loop exit). It ends, writing
  why to `LADO_HOME/loop.log`, when the
  session is stopped or gone (before each pass), its tmux session is gone (as above), or `lado.db` has another schema
  version than its own (`state.SchemaError` of any connection of a pass, so it never
  migrates). It ends writing nothing when `LADO_HOME/lado.db` is gone (`loop.home_gone`,
  before taking its lock, before each pass, after a pass that failed and before the statistics
  kick), so a home deleted by hand or under a stop that timed out is not made again. While it
  runs, `state.home_not_made` keeps its process from making LADO_HOME or `lado.db` again: a
  home deleted in the middle of a pass fails the rest of it, and the loop ends silently. A hook
  likewise exits 0 writing nothing when `lado.db` is gone (`hooks.main`: the session-end hook
  of an agent killed by a stop may come after the home was deleted). `lado stop`, `--all` and the UI's Stop
  return only after the loop has ended (`runtime.stop_session`, `loop.wait_stopped`'s three
  intervals; a loop that does not end fails the stop, the session staying stopped); `lado
  update` and `lado uninstall` stop with `wait=False` and wait themselves, with their own
  errors. An error in a pass is
  written there too with its traceback (and once to `errors.jsonl`, `telemetry.record`;
  a locked `lado.db`, `loop.is_locked`, only once it has failed the passes for
  `loop.LOCK_GRACE` seconds, 60), and the loop goes on. While the same error
  repeats, it writes one short line at most every `loop.REPEAT_NOTE` seconds (60) and the
  count when another error comes or passes work again. After a pass it kicks the
  statistics sender at most every `telemetry.KICK_EVERY` (`telemetry.kick`). `lado ls` marks a running session
  whose loop does not run (its lock is free) and says to run `lado attach <session>`:
  `lado attach`, and `lado start` on a running session (which still refuses), start the
  loop again when its lock is free. `lado forget` removes the lock file.
- Read-only roles: a role's `read_only: true` (`kits.AGENT_KEYS`, a bool, `AgentDef.read_only`;
  `lado kits show` prints `read-only: yes`, `lado kits check` the read-only roles; a kit
  supervisor that does not lead keeps none, said in `Environment.warnings`) makes its agent
  change nothing in the repository, for its whole life, in three layers; an agent without
  it runs exactly as before. 1. Its CLI's edit tools are taken away in the agent's own
  config (`AgentSpec.read_only`), only on a CLI with `Capabilities.deny_edit_tools`, set
  after a check by hand: Claude Code adds `EDIT_TOOLS` (Edit, Write, NotebookEdit) to
  `permissions.deny`, which takes them out of the tool list also with bypassPermissions,
  its Task subagents' too (checked with 2.1.296 on haiku);
  OpenCode and Kilo set `permission.edit: deny`, globally and in each of their
  `BUILT_IN_AGENTS` (a repo's or the user's `agent.<name>.permission.edit: allow` would
  beat the global rule; checked with OpenCode 1.18.35 and Kilo 7.8.8 under `--auto`: edit,
  write and patch gone, also for their subagents). Not covered there: an agent of the
  repo's or the user's own config with its own edit rule (a custom subagent,
  `default_agent`). Codex CLI sets `features.worktrees = false` (its `create_worktree`
  changes the repository); with that, a model Codex has no metadata for (all local ones)
  gets no tool that writes files but the shell (0.162 on LM Studio's qwen3.5-35b-a3b, the
  request's tools read in a bridge, under `default` and bypassPermissions;
  `providers/codex.py`). Not covered there: a model Codex has metadata for (OpenAI's) may
  get an apply_patch tool, which no config key takes away (unchecked: paid), so each
  read-only Codex agent's launch warns about it; a shell `apply_patch <<EOF` runs as
  Codex's own apply_patch, as any shell command may change a file (layer 3 reports it).
  `runtime._spec` refuses a read-only agent on a CLI without the capability before
  anything is stored or made (a lead before the session is added, a worker before its
  worktree), naming the providers that can. These claims hold for each provider's `TESTED_VERSION`; another
  version is `lado doctor`'s usual warning. LADO's instructions get a paragraph
  (`runtime.READ_ONLY_INSTRUCTIONS`): no changes through the shell either. 2. A read-only
  supervisor's `lado mcp` has no `COMMAND_TOOLS` (`mcp_server.py`). 3. Its hooks take a
  git fingerprint (`fingerprint.py`) at each turn's start (PROMPT_SUBMIT) and end
  (TURN_END, before it is idle, so before any queue goes), kept in its config folder as
  `hooks.BASELINE` (`open` from a turn's start to its end, then `closed` with the end's
  fingerprint; when the queue goes in the turn-end hook's output it is `continued`: that
  end starts the turn that goes on from it, which Claude Code and Codex run with no
  prompt-submit hook, and whose prompt-submit hook in OpenCode and Kilo, `chat.message`
  for `promptAsync`, replaces it without comparing; one still `open` at a turn's start, a
  turn whose end ran no hook, is compared then, worded `since <agent>'s turn started (its
  end was not seen)`). A difference is a `repo_changed` event and one line from `lado` to its lead
  (`runtime.repo_changed`, the human for a read-only supervisor), `while <agent>'s turn
  the repository changed: ...` (another agent may share the worktree), the whole list in
  the body when the line cannot hold it; nothing is blocked. The fingerprint's git runs
  within what the CLI gives the hook: `hooks.deadline` from the hook's start, the
  provider's `hook_limit`, the timeout of the handler LADO writes (Claude Code: 600 s when
  it sets none, read in its binary, and `base.TURN_END_HOOK_TIMEOUT` for its turn-end hooks;
  Codex: shared with `hook_hash`; OpenCode and Kilo none) less `STARTUP_RESERVE` and
  `QUEUE_RESERVE`, at most `fingerprint.BUDGET` (2 s); under `MIN_BUDGET`, or on a git
  error or timeout, it is `repo_check_failed`, told to the lead once per launch
  (`state.has_kind`), and the hook goes on.
- In LADO's container (`update.in_container`) every agent's instructions, on every
  provider and a read-only role's too, get a paragraph after the read-only one and before
  `MESSAGING` (`runtime.CONTAINER_INSTRUCTIONS`): a tool the repository needs and lacks is
  installed with mise into the home volume, by the repository's version files or as
  `<tool>@<version>` run through `mise exec`; no file is added to the repository unless the
  human asks; Node is the image's 22; apt packages and databases cannot be installed; a
  version mise refuses is reported, its checks never switched off. Then one sentence by
  role (`agent.name == SUPERVISOR`): the supervisor alone sets a container-wide default
  (`mise use -g`, `CONTAINER_SUPERVISOR`), a worker, a flow run's too, asks it
  (`CONTAINER_WORKER`). It is a rule of the instructions only: every agent has the shell.
  Outside a container the paragraph is absent. The image's side: docs/design/modules.md,
  `docker/`.
- Agents talk only through LADO's MCP tools. A CLI's own agent messaging is switched off
  (Claude Code: `SendMessage` and `ListAgents` are denied in the agent's settings, and the
  `lado` MCP server has `alwaysLoad`, so its tools are not hidden behind tool search), and so
  is self-updating (Kilo and OpenCode: `autoupdate: false`, and `KILO_DISABLE_AUTOUPDATE=1`
  or `OPENCODE_DISABLE_AUTOUPDATE=1`). Their snapshots (their undo; git keeps the history)
  are off too (`snapshot: false`): on a slow repo their setup stops the agent on a question
  for the human.
- Claude Code starts an agent's first turn after its SessionStart hooks, not after its MCP
  servers, and defers the tools of a server that connects later, `alwaysLoad` or not. So
  the `lado` MCP server records `mcp_ready` (with the launch's instance) when the CLI lists
  its tools, and the session-start hook of a provider with `hold_first_turn` waits for it
  (looking every `hooks.MCP_READY_POLL`, 0.02 s, at most `hooks.MCP_READY_TIMEOUT`; giving
  up is written to `hooks.log`). Verified by hand with Claude Code 2.1.289; the tested
  version is `providers/claude.py`'s `TESTED_VERSION` (`lado doctor` warns about others);
  the live test checks w1's transcript. Codex CLI needs no hold: its first turn waits for a
  `required` MCP server, which `lado` is in its config, and one that fails to start makes
  Codex exit (0.162, checked by hand; the window check ends the agent).
