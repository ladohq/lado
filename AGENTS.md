# LADO: notes for coding agents

LADO (Layered Agent Delegation & Orchestration) runs teams of AI coding agents.
Current stage and next steps: [ROADMAP.md](ROADMAP.md).

## Commands

```bash
uv sync                 # create .venv and install dev tools
uv run lado --version   # run the CLI from the working copy
uv run pytest           # tests
uv run ruff format      # format
uv run ruff check       # lint (add --fix to autofix)
```

The Makefile wraps these (`make help` lists the targets):

```bash
make lint               # ruff format --check + ruff check
make fmt                # ruff format + ruff check --fix
make test               # unit tests (uv run pytest -n auto)
make test-integration   # uv run pytest -m integration -n auto: real tmux, git and processes, no LLM
make test-js            # node --test: the Kilo plugin
make web                # the web UI: npm ci, stale-types check, tsc, vitest, build into src/lado/server/static
make web-types          # web/openapi.json and web/src/api.gen.ts from the server's API (commit both)
make test-ui            # uv run pytest -m ui: Chromium against a real lado server, fake agent
make dist               # uv build, and check that the sdist and the wheel ship the web UI
make check              # lint, the Kilo plugin, the web UI, unit, integration and UI tests in one run
make test-live          # uv run pytest -m live: real agent CLIs and models; PROVIDER=kilo|claude
```

The web UI needs Node (npm) to build; users of the wheel do not. `make browser` (part of
`make check` and `make test-ui`) installs Playwright's Chromium.

Unit and integration tests run in parallel, one pytest-xdist worker per CPU; each test has
its own `LADO_HOME`, tmux server and repos, so tests must not share a fixed path, port or
file. To debug serially, with output in order: `make test PYTEST_ARGS=-n0` (`PYTEST_ARGS`
replaces `-n auto` and takes any pytest options, e.g. `PYTEST_ARGS="-n0 -k gate -x"`), or
`uv run pytest` without `-n`. Live tests always run serially.

Integration tests (`tests/integration/`) run a fake agent (`fake_agent.py`, provider "fake")
instead of a real agent CLI. They use a temp `LADO_HOME` and their own tmux server
(`LADO_TMUX_SOCKET=lado-test-...`), and refuse to run otherwise. Tests never use the default
`lado` tmux socket. `tests/conftest.py` clears `LADO_AGENT`, `LADO_SESSION`, `LADO_HOME`,
`LADO_TMUX_SOCKET` and `TMUX` for the test run, so the tests run in an agent's shell as is,
and sets `LADO_AGENT_ENV=inherit`: agents get the test run's environment, not the user's
login shell (tests of the shell set their own `SHELL`).

Live tests (`tests/live/`) run the real CLIs with the same isolation; a test skips when its CLI
is missing or not logged in. Models: Claude Code on `haiku`, Kilo on `kilo/kilo-auto/free`
(override with `LADO_LIVE_CLAUDE_MODEL` / `LADO_LIVE_KILO_MODEL`). The Claude test uses a fixed
repo path and answers Claude Code's workspace trust dialog, so Claude Code records one trusted
folder for it.

CI runs `ruff format --check`, `ruff check`, the unit and integration tests (in parallel) on
Python 3.10 and 3.13, the Node tests, and in one job on Python 3.13 `make dist` (the web UI
built and in both the sdist and the wheel) and the UI e2e tests.
Live tests are not in CI: run them locally.

Release: `uv version <X.Y.Z>`, commit, then push tag `vX.Y.Z`. The Release workflow checks the
tag against the package version, builds with `make dist` and publishes to PyPI.

Versions (0.x): bump the minor (0.7.0) for new features, an MCP tool or CLI change that older
agents cannot use, or a database schema migration; running sessions must be restarted after
such an upgrade. Bump the patch (0.7.1) for fixes and docs only: no new feature, no API or
schema change.

## Layout

- `src/lado/`: the Python package.
  - `cli.py`: the `lado` command. `doctor.py`: environment checks.
  - `runtime.py`: starts agents in tmux (worker = own git worktree and branch) and delivers
    messages to them.
  - `providers/`: agent CLIs behind one interface (`base.py`: `Provider`, `Capabilities`,
    `Launch`, neutral hook events; `claude.py`: Claude Code; `kilo.py`: Kilo CLI, with
    `kilo_plugin.js`, the Kilo plugin that runs LADO's hooks). A provider writes the agent's
    config, returns its argv and env and translates its hook events. The provider is chosen
    per session (`lado start --provider`) and per worker (`spawn_worker(provider=...)`).
    Each provider lists the `--permission-mode` values it honours (`permission_modes`; the
    CLI help shows them); `lado start` (also a resume) and `spawn_worker` refuse a mode the
    agent's provider does not support, before anything is launched.
  - `tmux.py`: tmux calls, on a private server (`tmux -L lado`; `LADO_TMUX_SOCKET` overrides
    the socket name and is passed on to agents).
  - `agent_env.py`: where an agent's environment comes from (How agents talk): `resolve`,
    and `command`, the window's command that runs the agent with exactly that environment.
  - `terminal.py`: an agent's terminal for the UI (design in
    [docs/design/ui.md](docs/design/ui.md), section Terminal): `open` (a viewer tmux session
    with the agent's window linked in and a `tmux attach` on a pty), `history`, `NoTerminal`,
    and `close_viewers`, which `lado stop` and the UI server's start use; viewers are found
    by their tmux labels (`@lado-viewer`, `@lado-home`, `@lado-session`) only. Never a
    read-only tmux client: tmux would refuse LADO's own `send-keys` while one is attached.
  - `kits.py`: kits (agent roles, skills, MCP servers, flows): lookup, `include`, `--without`,
    validation. A provider gets an `AgentSpec` (prompt, skill folders, MCP servers), never
    the kit itself. `builtin_kits/`: kits shipped with LADO (`default`: supervisor + worker).
    LADO's own instructions to agents stay in `runtime.py` and are appended to the role.
  - `sources.py`: kit sources (`lado sources`): a local folder read in place, or a git
    repository cloned into `LADO_HOME/sources/<name>`; registered in `LADO_HOME/sources.yaml`.
    Only the `Source` classes know a kind; `kits.py` asks a source for its directory.
  - `flows.py`: the flow format (`flows/<name>.yaml` in a kit: work, gate and end states;
    a work or gate state's optional `needs` lists the states whose latest notes its step
    gets or the human sees at the gate)
    and its validator. `runs.py`: flow runs: start (own worktree and branch, shared by the
    run's workers), step messages from `lado`, `flow_advance`, loop limits, gates (the run
    waits for the human), end (finish workers, remove the worktree if merged), cancel and
    `lado flow-set`. A run keeps a snapshot of its flow. A waiting run has one open gate
    record (`state.Gate`); `runs.answer` is the only way to answer it, called from
    `lado answer` and the UI server's API, never from an MCP tool; the answering surface
    (popup, CLI, UI) stays outside that core.
  - `mcp_server.py`: MCP tools for agents (`send_message`, `ask_human`, `read_messages`,
    `list_agents`, `flow_advance`, `flow_status`; the supervisor also gets `spawn_worker`,
    `finish_worker`, `flow_start` and `flow_cancel`). No tool answers a gate or a question.
  - `hooks.py`: neutral hook logic: agent status, handing over queued messages and, at a
    turn's end, the forgotten-reply check (How agents talk).
  - `state.py`: SQLite state in `~/.lado/lado.db` (`LADO_HOME` overrides the directory).
    Schema changes: bump `SCHEMA_VERSION`, add a step to `MIGRATIONS` and update
    `tests/agent_helpers.previous_schema` (it undoes the last step). A CLI command does
    not migrate under a running session (not stopped, tmux session alive): it refuses,
    names the sessions and asks for `lado stop` first (`runtime.check_migration`, called
    by the CLI before each command but `stop`; hooks and `lado mcp` do not check). An
    older LADO refuses a newer database and asks to upgrade. A message counts its pastes
    (`messages.attempts`) and can end `failed` (`messages.failed_at`); an agent keeps when
    its latest hook ran
    (`agents.seen_at`). From schema 13 a message has a `kind` (`message` or `question`),
    a question its `choices`, `free_answer`, `question_state` and `answered_by`, an answer
    or dismissal its `reply_to` and `choice`, and the human's message to an agent its
    `reply_state` (How agents talk). The `events`
    table records what each agent did (`spawned`, `status` changes via `set_status`,
    `mcp_ready`, `finished`) and what happened to each flow run (`flow_start`, `flow` transitions,
    `flow_end`, `flow_cancel`, `flow_set`, `gate_open`, `gate_answer`; their `run` column
    names the run) and the session's `session_stop` and `session_resume`. The `notes`
    table keeps every note a run's step reported (`flow_advance`, a gate's answer,
    `lado flow-set`'s reason) with the state it was reported from and its kind: a
    `report` is a work state's own or the answer at an approval or choice gate; an
    `override` (a flow-set reason, from the state the run was in; an answer at a loop
    limit, from the state it kept the run out of) is kept but never taken for a state's
    report. Events, messages,
    runs, notes and gates go with their session, which `lado stop` only marks stopped
    (`sessions.stopped_at`) and `lado forget` deletes. How long an
    agent has had its status (`lado ls`, `list_agents`) comes from its latest `status` or
    `spawned` event, how long a run has been in its state from its latest event.
    The `changes` table is the UI's change journal: triggers on `sessions`, `agents`,
    `messages`, `runs`, `gates` and `notes` record each insert, update and delete (kind,
    session, key, op) in the writer's transaction, so no code path reports changes by hand;
    an agent update that changes `seen_at` is none (`AGENTS_CHANGED`: only `state.seen`
    writes it, and nothing else with it; keep it so, since the condition names no other
    column and a trigger stays in `lado.db` as it was made; when the agent has messages that
    failed after its previous hook, `state.seen` also writes `status = status` in its own
    statement, a change, since why it waits, `waiting_reason`, changes with `seen_at`), and
    each insert drops changes older than
    the latest `CHANGES_KEPT`. From schema 14 `events` is journaled too, key its id, but
    only inserts (`JOURNALED_OPS`) of a flow run's events (`RUN_EVENT`: `run IS NOT NULL`;
    a status event would double the journal); a trigger's condition is in `JOURNAL_WHEN`.
    A new table the UI shows gets its triggers in `JOURNALED`.
  - `log.py`: `lado log`: a session's messages and events merged into one time-ordered feed.
  - `loop.py`: the session loop, `lado loop <session>` (see How agents talk).
  - `server/`: the UI server, one per `LADO_HOME` (`lado server`, `lado ui`; design and
    rules in [docs/design/ui.md](docs/design/ui.md), section Server). `auth.py`: the token
    and, for a connection that changes something, the Origin (`Guard.check`), the only
    place that checks them; `app.py`: the FastAPI app, the API under `/api` (data only
    through `state.py`/`runtime.py`, never migrates the database), the bundle's files, and `index.html` for every other path
    that is a page of the UI (its router shows it); `feed.py`: the change feed behind
    `GET /api/events` (Server-Sent Events): the `Source` of changes (now the `changes`
    journal, read only), one hub per server, `reset` and resume, the derived fields;
    `models.py`: the API's models, one form for REST and the stream's items;
    `terminals.py`: an agent's terminal WebSocket
    (`/api/sessions/{name}/agents/{agent}/terminal`) around `lado.terminal`: frames,
    backpressure, close codes; the agents, history, messages, run events
    (`/api/sessions/{name}/events`) and gates (with the human's answer) endpoints are in
    `app.py`; a gate's model is built by `models.gate_info` for REST and the feed; what
    waits for the human (open gates, open questions, agents in `waiting`: the one "needs
    you") is `state.waiting_items`, only of sessions not stopped (`stopped_at IS NULL`, in
    its SQL), served as `GET /api/waiting` (`models.WaitingItem`) and counted from that same
    list as a session's `waiting` in `models.session_info` (`state.waiting_for_human`), so
    the list and the count cannot differ; an agent's `waiting_reason` (`AgentInfo`, only
    for an agent in `waiting`) is `runtime.waiting_reason`, which `waiting_reasons` uses
    too;
    `run.py`: the lock, `server.json`, the port, the background start and stop. `static/`:
    the built bundle, git-ignored. A session's status (`lado ls`, the API) comes from
    `runtime.session_status`.
- `web/`: the web UI (React, TypeScript, Vite). `openapi.json` and `src/api.gen.ts` are made
  by `make web-types` and committed.
- `tests/`: pytest tests; `tests/integration/`: integration tests with a fake agent;
  `tests/ui/`: UI end-to-end tests in a browser; `tests/live/`: live tests with real agent
  CLIs; `tests/js/`: Node tests of the Kilo plugin; `web/src/*.test.tsx`: the UI's unit
  tests (vitest).
  `tests/agent_helpers.py`: isolation guard and polling shared by integration and live tests.
- `npm/`: placeholder npm package that only reserves the name. Leave it alone.

## How agents talk

- An agent's environment (PATH, keys, variables) is the user's login shell's, as a new
  terminal sees it, the same whichever process starts the agent (`lado start`, the UI
  server, an agent's `spawn_worker`) and whoever started LADO's tmux server
  (`agent_env.resolve`). For each launch (start, resume, spawn) LADO runs
  `$SHELL -ilc` with a dump of the environment, started from a terminal's few variables
  (`HOME`, `USER`, `LOGNAME`, `SHELL`, `TMPDIR`, `LANG`, `SSH_AUTH_SOCK`, a system `PATH`) in
  a new session, no cache; the dump is JSON between markers, so what the startup files print
  does not matter. No `$SHELL`, a failing shell or one slower than `agent_env.TIMEOUT` (10 s)
  stops the launch before anything starts, with the command and the end of its stderr.
  `LADO_AGENT_ENV=inherit` takes the environment of the process that starts the agent instead
  (the tests set it). From either, `TMUX`, `TMUX_PANE`, the shell's own `PWD`, `OLDPWD`,
  `SHLVL` and `_`, and a parent Claude Code's variables are dropped; LADO's variables, then
  the provider's go on top. A tmux window starts with its server's environment, so the
  window runs `python -m lado.agent_env <file> <argv>`: it reads that environment from a file
  in the agent's config folder (mode 600, removed once read), keeps tmux's own `TERM`,
  `TERM_PROGRAM(_VERSION)`, `TMUX` and `TMUX_PANE`, and execs the agent's CLI, found on the
  resolved `PATH`. `lado doctor` shows the source and how long the shell takes (a warning
  above 2 s).
- An agent's status (busy / idle / waiting) comes from its hooks, never from screen scraping.
  Only the end of its process marks it `stopped`. A CLI command that leaves the conversation
  for another one in the same process (Claude Code's `/clear` and `/resume`) shows it as
  `starting` until the CLI is ready again; messages to it wait in the queue meanwhile and are
  typed in when it is `idle` again.
- A message is a one-line `summary` (at most 200 characters; a longer or multi-line one is
  refused) and an optional `body` with the details. Only one short line per message reaches
  the recipient: `[from <sender>] <summary>`, plus ` (#<id>, <n> lines: call read_messages)`
  when there is a body. `read_messages` returns the caller's delivered, unread bodies and
  marks them `read`. The supervisor stays quiet with the human: it does not relay reports,
  and the details are in `lado log`.
- The human is a participant of messages, `human` (design in
  [docs/design/ui.md](docs/design/ui.md), The human in the session): agents write to it with
  `send_message(to="human")` and ask with `ask_human` (a question, up to 6 choices, a free
  answer by default); such a message is `delivered` at once into no window, and the UI's
  Activity chat shows it. The human writes from the UI's composer (`runtime.write_as_human`,
  only through the server's API; to the supervisor by default) through the same queue,
  confirmation and retries, and the agent gets `[from human] ...`. An answer
  (`Answer to #<id>: ...`) or dismissal (`Dismissed #<id>`) comes to the agent the same way.
  No agent may be named `human` or `lado` (`state.RESERVED`). Messages to `human` are never
  dropped (stop, finish), and a forgotten agent's open questions are `closed`. LADO's
  instructions tell the supervisor to answer where the human asked: a `[from human]`
  message with `send_message(to="human")` or `ask_human`, text typed into its window in the
  window. At each turn's end, before the queue is handed over, the human's messages the
  agent got (not answers or dismissals) are checked once: `replied` if it wrote to `human`
  after it got them (by `sent_at`, when each was handed over, not by id), else `missing`,
  which the chat shows as "replied only in its terminal".
- An agent's first input (a worker's task or step, a resumed supervisor's messages) goes on
  its command line. When it is longer than 2000 characters (tmux refuses commands over about
  16 KB), it comes as a message from `lado` instead, marked delivered: the agent gets its
  one line and reads the text with `read_messages`. The worker's task is still the full text.
- A message to an idle agent is pasted into its window and stays `sent` until the agent's
  prompt-submit hook sees its line (then `delivered`). A busy agent gets its queued messages
  from its turn-end hook when the turn ends. LADO types only into an idle agent, never into
  one that is waiting, starting or stopped, and a new message waits while one typed before
  is unconfirmed.
- What happens to an unconfirmed message is one rule, `runtime.sweep`, run by `send_message`
  to the agent, by its turn-end and conversation-start hooks, and every `loop.INTERVAL`
  seconds by the session loop (below). Each paste is an attempt; after the n-th, the message is left alone for
  `RETRY_DELAYS[n-1]` seconds (15, 30, 60). Then: if no hook of the agent ran since the paste
  (`agents.seen_at`; a dialog took the text) and the agent is busy, it is pasted again with
  the queue; if hooks ran but no prompt held its line and the agent is idle, it goes back to
  the queue and is delivered as usual. After `1 + len(RETRY_DELAYS)` pastes and the last
  delay it is `failed` (`lado log`): the agent is set `waiting`, `lado ls` and
  `list_agents` (`waiting_reason`) say why and what the human can do (until the agent's next
  hook), and nothing more is typed into it in that sweep; the messages typed together with
  it that are not back in the queue fail with it, attempts left or not; the sender of each
  (the supervisor for LADO's own messages) gets one line from `lado`; a failed notice is not
  reported. The agent's first hook after that puts the messages no hook ran after back in
  the queue with their attempts from 0; the ones it saw and never confirmed stay failed.
  `LADO_RETRY_DELAYS` (`0.5,0.5,0.5`) replaces the delays in the processes started with it,
  for the integration tests.
- The session loop is a hidden `lado loop <session>` (`loop.py`), a process of its own
  outside tmux that `lado start` (also a resume) starts once the tmux session exists. It
  sweeps the session every `loop.INTERVAL` seconds, so an unconfirmed message is typed
  again or failed on time with no send and no hook. One per session: it holds an exclusive
  `flock` on `LADO_HOME/loop/<session>.lock` (gone with the process, no pid file); a second
  one exits when it cannot take the lock within `loop.LOCK_WAIT` (0.1 s, so a moment's lock
  check by `lado ls` does not make a starting loop exit). Before each pass it ends, writing
  why to `LADO_HOME/loop.log`, when the
  session is stopped or gone, its tmux session is gone, or `lado.db` has another schema
  version than its own (checked read-only, so it never migrates); an error in a pass is
  written there too with its traceback, and the loop goes on. While the same error
  repeats, it writes one short line at most every `loop.REPEAT_NOTE` seconds (60) and the
  count when another error comes or passes work again. `lado ls` marks a running session
  whose loop does not run (its lock is free) and says to run `lado attach <session>`:
  `lado attach`, and `lado start` on a running session (which still refuses), start the
  loop again when its lock is free. `lado forget` removes the lock file.
- Agents talk only through LADO's MCP tools. A CLI's own agent messaging is switched off
  (Claude Code: `SendMessage` and `ListAgents` are denied in the agent's settings, and the
  `lado` MCP server has `alwaysLoad`, so its tools are not hidden behind tool search), and so
  is self-updating (Kilo: `autoupdate: false` and `KILO_DISABLE_AUTOUPDATE=1`). Kilo's
  snapshots (its undo; git keeps the history) are off too (`snapshot: false`): on a slow
  repo their setup stops the agent on a question for the human.
- Claude Code starts an agent's first turn after its SessionStart hooks, not after its MCP
  servers, and defers the tools of a server that connects later, `alwaysLoad` or not. So
  the `lado` MCP server records `mcp_ready` (with the launch's instance) when the CLI lists
  its tools, and the session-start hook of a provider with `hold_first_turn` waits for it
  (at most `hooks.MCP_READY_TIMEOUT`; giving up is written to `hooks.log`). Verified with
  Claude Code 2.1.287 (`providers/claude.py`: `TESTED_VERSION`; `lado doctor` warns about
  others); the live test checks w1's transcript.

## Try it locally

`uv run lado start <repo>` runs the working copy. Use `LADO_HOME=/tmp/some-dir` and
`LADO_TMUX_SOCKET=lado-dev` to keep test sessions apart from the LADO you work with.

`lado log <session>` shows what happened in a session: messages between agents (one line
with their delivery state and summary, the body indented below) and agent events (spawned,
status changes). `--agent NAME` keeps one agent's
lines, `-n N` the last N entries, `--follow` keeps printing new ones until Ctrl-C.
With `--follow` a message is printed once, with the state it had then; a later delivery
is not printed again.

`lado finish <session> <agent>` ends a worker whose branch is merged into the session repo's
current branch: it closes the window, removes the worktree and branch, and drops the agent
from `lado ls` (its messages and events stay in `lado log`, with a `finished` event).
Messages it never got and bodies it never read are dropped, so a later worker of the same
name starts fresh. It refuses an unmerged branch or uncommitted changes; `--discard` ends
the worker anyway and throws that work away. The supervisor does the same with the MCP
tool `finish_worker`. A worker of a flow run only has its window closed while the run is
open: the worktree and branch belong to the run.

`lado stop <session>` kills the session's tmux windows and marks it stopped, then closes the
UI's terminals of its agents (their viewer sessions); its history,
runs and gates stay, and so do worktrees and branches. Its agents are forgotten (their names
are free again; `lado log` keeps what they did), and messages they never got or whose body
they never read are dropped, with the count in the output: new agents start fresh.
`lado ls` shows the session as `(stopped)` with its open runs and gates; `lado log` works
as before. `lado start` with the same name resumes it (also when
its tmux server died without `lado stop`): the repo must be the same, and `--kit`,
`--without`, `--provider` and `--permission-mode`, when given, replace the stored ones
(the output says what changed). The new supervisor starts with one message from `lado`,
`session resumed: <n> open runs`, whose body says per open run what waits: the human at a
gate (answer with `lado answer`), the supervisor's own step (its step message follows), or a
worker to start with `spawn_worker(run=...)`. Such a worker opens in the run's worktree on
its branch, made again from the branch if the folder is gone. An open run that needs a role
the resumed session lacks is reported on stderr and in that body; `flow_cancel` or
`lado flow-set` move it on. While a session is stopped, nothing starts or moves in it:
`lado answer`, `lado flow-set`, spawning workers and starting, advancing or cancelling runs
are refused (`runtime.running_session`); `lado answer` with no session skips its gates.
A worker started without a name (`spawn_worker`, also for a run) is named after its role,
made valid like a given name (`slug`: `Code Reviewer` gives `code-reviewer`): `developer`,
or `developer-2`, `developer-3`… when that is taken. A name is taken by a running agent of
that name or a branch `lado/<session>/<name>` still there (from a stopped launch or a
worker not finished); `human`, `lado` and `supervisor` are never chosen. A given name wins
and is checked as before.
`lado forget <session>` deletes a stopped session with its history; it refuses a running
one, and one with open runs unless `--force`; worktrees and branches stay on disk and are
listed.

Gates: a run that enters a gate state, or would enter a state more often than its
`max_visits`, waits for the human with an open gate (`lado ls`: `gate #<id> waiting:
<question>`). An approval gate has exactly the outcomes `approved` and `rejected` and is
answered `approve` / `reject`; a choice gate with one of its outcome names; a loop limit with
`continue` (enter the state anyway, the visit counts) or `cancel` (cancel the run). The
supervisor gets one line, `flow <run>: waiting for the human at <state> (gate #<id>)`. The
answer and its comment become the next step's note, after which the note that led to the gate
follows in the body; when a worker gets the next step, the supervisor gets one line
`flow <run>: human answered <option> at <state>`.

A step's text (`runs.step_text`) has the task, the step's `do`, then for each state in its
`needs` the latest report kept from that state (`Note from <state>: ...`, or `no note yet`),
then the previous step's note and the outcomes. The needed notes come from the `notes`
table, so `lado flow-set` keeps them: a run set to `implement` with `needs: [design]` gets
the latest design note, and the flow-set reason is the previous step's note. A needed
state whose latest report is the previous step's note itself (the same `notes` record,
compared by id, not by text) is printed once, as `Note from <state> (also the previous
step's note): ...`, and the separate previous-step note is left out.

`lado answer <session> <gate-id|run> <option> [-m COMMENT]` answers a gate. Without the
option it asks: with no arguments about the open gates of all sessions (a list to pick from
when there are several), and after each answer it goes on with the open gates of that session
until none is left or the human presses Enter on an empty line. It shows the question, the
one-line summary of the note that led to the gate, for a gate state with `needs` one line
per needed state (`Note from <state>: <summary>` of its latest report, or `no note yet`),
and the numbered options; when the note has a body or the gate has `needs`, `v` shows the
whole text in `less -R` (printed when there is no `less`): each needed note, then the note
that led to the gate; then it asks again. The needed notes are read from the `notes` table
when asked, not kept in the gate; a loop limit shows none. When a gate opens, LADO opens a tmux popup (`display-popup -E`, titled
`LADO: waiting for you (session <name>)`, a rounded soft orange border around the
terminal's own colours from tmux 3.3 on, tmux's plain border on 3.2, none before 3.2;
`lado doctor` warns about both) running `lado answer <session> <gate-id>` on each client
attached to the session; with no client attached, nothing opens and the gate waits in
`lado ls`. tmux does not stack popups: a second gate is asked about in the open popup after
the first answer. Closing the popup leaves the gate open. `lado answer` and `lado flow-set`
refuse to run inside an agent (`LADO_AGENT` set).

A gate is answered with `lado answer`, the popup, or the UI server's API (the gate's card in
the session's chat; docs/design/ui.md, Flow gates); all go through `runs.answer`, and
`runs.answer_text` is the one line that says what the answer did. Two answers at once: the
second is refused (`closed already`). While `lado answer` waits for the human on a terminal
(the option, the comment), it checks every second (`cli.POLL`) that the gate is still open;
when it was answered elsewhere, it drops what was typed (`tcflush`), prints `Gate #<id> was
answered elsewhere: <answer> by <who>` and goes on with the session's open gates, or ends
with `No more open gates.`, which closes the popup. Without a terminal (a pipe) it does not
check.

Flow tools return short results: the run, flow, state, status, who acts, outcomes, gate,
visits, the note's summary and the run's language; `flow_status(run=...)` adds the task,
reason, worktree and branch. What the supervisor's own `flow_start` or `flow_advance`
causes (a step that needs a worker, a gate, the run's end) comes back in the result's
`notices` instead of as a message; what others cause (a worker's advance, the human's
answer) still comes as a message. A "step <x> needs a <role>" message still waiting in the
queue is dropped when that worker is spawned for the run. `flow_start(human_language=...)`
stores the human's language with the run (e.g. `ru`), and every step message asks for
`note_summary` and `note_body` in it, since the human reads them at gates; the flow's gate
questions stay as written.

`lado flow-set <session> <run> <state> --reason TEXT` puts a flow run into a state: the
human's override, past a gate or a loop limit; it closes the run's open gate as `overridden`.
`lado ls` shows each open run with its state and who acts next.

## Testing

Five layers; each change gets tests at the lowest layer that can catch its bugs:

1. **Unit** (`make test`): pure logic, tmux replaced by a recorder. Default for everything.
   The server's API is tested in process with FastAPI's test client; the web UI's
   components with vitest (`make web`), `fetch` mocked.
2. **Integration** (`make test-integration`): real tmux, git, hooks, `lado mcp` and SQLite
   with the fake agent instead of an LLM. Required for behaviour that crosses processes,
   also the UI server's (one per home, background start, stop), without a browser.
3. **Plugin tests** (`make test-js`): provider plugins run under Node with a fake client.
4. **UI e2e** (`make test-ui`, marker `ui`): Chromium (pytest-playwright) against a real
   `lado server` on a free port, with sessions of the fake agent, isolated like the
   integration tests; only what needs a browser. Each test saves a screenshot of every
   screen it checks to `<temp dir>/lado-ui-shots/<test>.png` (the `shot` fixture), outside
   the tree, for the reviewer. In `make check` and in CI (one job, with `make dist`).
5. **Live e2e** (`make test-live`, marker `live`): real agent CLIs and real models, one short
   scenario per provider: a worker commits a file, reports to the supervisor and gets a
   message; then the session stops and no process is left. Never in the default run and
   not in CI: run it locally after changing a provider or before a release.
   When a live test fails, its report names a folder
   `<temp dir>/lado-live-evidence/<time>-<test>` that keeps the test session's `lado log`,
   `hooks.log`, each agent's config folder and cwd, and each tmux window's screen, taken
   before teardown. A passing test keeps nothing; the folder is never cleaned by the tests.
   A timed-out wait names what it waited for and the agents' statuses and last messages.

Before a release: `make test-live` passes on main, and CI is green on the release commit (main got its `make check` at each merge).

## Design principles

LADO borrows ideas from other orchestrators but must not repeat their mistakes:

- **Events, not screens.** Agent status comes from hooks, plugins or a protocol, never from
  reading the terminal.
- **Neutral core.** Nothing above `providers/` depends on one agent CLI. A new feature works
  with at least two providers or says clearly where it does not.
- **No silent drops.** If a kit, role or option asks for something a provider cannot do,
  fail or warn loudly. Never ignore it quietly.
- **One source of truth.** Derive what exists from the files themselves; do not keep a
  second list of the same things that can drift.
- **Share, don't copy.** Reuse a skill or role through `include`, never by copying it.
- **No hardcoded paths.** Resources refer to each other by relative paths or `${KIT_DIR}` /
  `${SKILL_DIR}`, never by absolute or home-directory paths.
- **Never touch the user's global agent config.** Configure each agent process on its own.
- **Native over injected.** Use each CLI's own way of loading skills, MCP servers and hooks
  instead of pasting their text into the prompt.
- **Explicit lookup.** No hidden fallbacks to global locations; show where each resolved
  piece came from.
- **Only what is used.** Add a field, option or engine feature when a real kit needs it.
- **Tested end to end.** Behaviour that crosses processes (tmux, hooks, MCP) gets an
  integration test with the fake agent.

## Rules

- **Deliver fast.** Build only what the current roadmap stage needs.
- **Clean-room.** Ideas from other projects are welcome, but never copy their code, tests,
  prompt texts or file layout. Describe the behavior in your own words first, then write
  the implementation from scratch.
- **Tasks and bugs** go to the external task tracker, not to GitHub Issues.
- Python 3.10+. Standard library first; add a dependency only when it clearly saves work.
