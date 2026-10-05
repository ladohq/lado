# Backlog

Tasks and bugs found while using LADO, until the external task tracker is connected
(see ROADMAP.md, stage 9). Move them to the tracker then and delete this file.

## Choose the model per agent

Providers start the agent CLI with its own default model. Kilo without an account picks a free
"auto" model; there is no way to say which model a session or a worker uses.
Wanted: a model option per session and per worker, translated by each provider.
Postponed (2026-10-01): model names differ per provider and change with every release, so
first decide how a kit names a model without tying it to one provider (aliases such as
fast / strong mapped per provider? a per-provider map?). Draft design: `model:` in a role,
`spawn_worker(model=...)` so the supervisor can pick a cheaper model per task, `lado start
--model`; no hand-kept model lists; the model shown in `lado ls` and the `spawned` event.
Found: 2026-10-01, Kilo provider smoke test.

## Permission modes are Claude-shaped

`--permission-mode` takes Claude Code values. Each provider declares the ones it honours
and LADO refuses the others (Kilo: default, acceptEdits, bypassPermissions, plan), but the
vocabulary is still Claude Code's, and a session has one mode for all its agents.
Wanted: a neutral LADO permission setting that each provider translates.
Found: 2026-10-01, Kilo provider review.

## Kit MCP secrets are written to disk

`${ENV_VAR}` values in a kit's MCP env are resolved by LADO and written into the per-agent
config under `~/.lado/agents/`. Secrets should stay in the process environment: pass them
to the agent's env and let each CLI expand them (Claude `${VAR}` in mcp.json, Kilo
`{env:VAR}`), or start the MCP server through a LADO wrapper that reads them.
Found: 2026-10-01, kits review.

## Claude Code's "trust this folder?" dialog blocks a new session

In a repo Claude Code has not seen before, it asks whether to trust the folder, and no flag
skips the question. Checked on Claude Code 2.1.287 (2026-10-02): until the human answers,
no hook runs, so the agent stays `starting` and LADO types nothing into it (messages wait in
the queue). The dialog's default answer is "No, exit": an Enter there ends Claude Code, its
tmux window closes, and no SessionEnd hook runs, so `lado ls` keeps showing it `starting`
(with "tmux session is gone" for a supervisor). `lado start` (or `lado doctor <repo>`)
should detect an untrusted repo and tell the user, and the agent's status could show that it
waits for the human.
Found: 2026-10-01, live e2e tests.

## No way to reach a busy agent urgently

A message to a busy agent waits until its turn ends. A hint from the supervisor that would
save a worker many minutes (e.g. the known cause of a failure it is debugging) arrives only
after the worker has finished that long turn. Wanted: an "urgent" flag on send_message that
types the message into the busy agent's window at once (Claude Code and Kilo accept input
while working and handle it at the next step), with the same confirmation via prompt-submit.
Found: 2026-10-01, provider fixes task.

## A delivered message can carry the human's unsent draft

The supervisor's window is both the human's chat and the agents' inbox. When a message is
pasted into an idle supervisor (paste + Enter) while the human is typing there, the half-written
text is submitted together with it. Decided (2026-10-01): live with it for now. It goes away
when the human writes through LADO's own input (UI composer, stage 7: messages from the human
and from agents are queued and delivered one at a time) or with the ACP runtime (stage 8: LADO
drives the agent's input itself). Make sure the UI has a composer that goes through LADO.
Update (2026-10-03, chat task): the UI's composer in Activity writes through LADO's queue, so
a human who writes from the UI is not affected. Typing in the supervisor's window (tmux or
"Take control" in the UI) still is, until ACP.
Found: 2026-10-01, dogfooding.

## A step that needs a new worker is a relay through the supervisor

LADO asks the supervisor to start a step's worker, and the supervisor calls spawn_worker with
exactly the arguments LADO named; no decision is made.
Wanted: a flow (or kit) can say that LADO spawns the step's worker itself.
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## "idle" while a background command runs

A reviewer's turn ended while its `make check` ran in the background; LADO showed it idle for
80 s (and could have pasted a message into it) until the command finished and woke it. The end
of a turn is not the end of the agent's work.
Wanted: find out whether Claude Code and Kilo signal a running or finished background task;
use it for the status, or document the limit.
Postponed (2026-10-02): low impact. Flows move on flow_advance, not on idle; a message
pasted meanwhile most likely starts a normal turn (not verified); typing into waiting agents is
already blocked. The reference orchestrator does not handle it either (screen-based idle).
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## Delivery at turn end reads "Stop hook error"

Claude Code shows a message delivered by the turn-end hook as a "Stop hook error" line.
Wanted: check whether another form of the hook's answer (e.g. JSON `decision: block`) shows a
neutral label. Cosmetic.
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## Flows cannot work on another repository

A run's worktree and branch are always made in the session's repo, so a change to another
repo (e.g. the lado-kits kit repo while the session runs on LADO) cannot go through a flow:
it is done by a worker outside a run, with no design gate, review step or merge gate.
Wanted: `flow_start` can name the repo a run works on (a registered kit source or a path),
and the run's worktree, `make check` and merge happen there.
Found: 2026-10-02, task lado-dev architecture (kit changes in lado-kits).

## A failed rollback hides why a start or spawn failed

When `start_session` or `spawn_worker` fails, its `except` undoes what it stored
(`state.fail_resume`, `state.delete_session`, `close_worker`, git cleanup) and re-raises. If
that undo raises too (e.g. the database is locked), the user sees the undo's error instead of
the cause, and the session or worker is left half undone.
Wanted: an undo that never replaces the original error (report its own failure apart, e.g.
in `hooks.log` or as a note on the error) and leaves no half state.
Found: 2026-10-02, review of run fix/resume-settings.

## Two starts of a session whose tmux server died can stop each other

`start_session` stops a session whose tmux server is gone (`stopped_at` unset, no tmux
session) before it takes it over. Two `lado start` of that name at once both see it so: the
first stops it, resumes it and launches its supervisor; the second then stops that running
session again, forgetting its agents, and takes it over in turn. The window is small.
Wanted: stopping a left-over session and taking it over as one step that only one start wins.
Found: 2026-10-02, run fix/resume-settings.
## Live-test evidence lacks the CLIs' own transcripts and logs

A failed live test keeps LADO's log, hooks.log, agent configs and window screens, but not
Claude Code's transcript (~/.claude/projects/<cwd>/*.jsonl) or Kilo's session and log from its
data folder. For a flake such as a weak model calling a tool with a wrong argument, the
transcript (tool calls and their answers) matters most.
Wanted: the evidence also copies each agent's CLI transcript and logs, picked by the agent's
cwd and the test's start time; the test layer asks the provider for their location, so nothing
above providers/ learns a provider's paths.
Found: 2026-10-02, review of run fix/live-test-keeps-logs.

## Stopping one of several running sessions migrates the database under the others

A newer CLI refuses to migrate `lado.db` while a session runs and asks for `lado stop`
first, but lets `lado stop` itself through: with sessions A and B running, `lado stop A`
migrates the database while B still runs, so B's older agents break until B is stopped
too. Also, a LADO upgraded in place (`pip install -U`) while a session runs migrates from
that session's own hooks, which run the new code, under its older MCP servers. Wanted: a
stop that kills the session before it opens the database, or one `lado stop --all`.
Found: 2026-10-02, migration guard (fix/migration-guard).

## The running-session check sees one tmux socket

`runtime.check_migration` asks `tmux.has_session` on the current process's `LADO_TMUX_SOCKET`.
A session started in the same LADO_HOME with another socket counts as not running, so the
database is migrated under it.
Wanted: store the socket with the session and check that one (or say in the refusal and the
docs that the check sees one socket). An edge case.
Found: 2026-10-02, review of run fix/migration-guard.

## A missing tmux binary crashes the CLI with a traceback

Without tmux installed, `tmux.run` raises FileNotFoundError, not TmuxError, so the CLI shows a
traceback (now also from `check_migration` when an old database has unstopped sessions).
Wanted: `tmux.run` turns a missing binary into TmuxError with a clear text.
Found: 2026-10-02, review of run fix/migration-guard.

## Migration-guard leftovers (two Minor review findings)

`state.pending_migration`'s docstring says it creates and changes nothing, but opening a WAL
database read-only leaves `lado.db-wal` and `lado.db-shm` behind (the data is unchanged).
`tests/test_state.py` `_database()` and `tests/integration/test_agents.py` `database()` are the
same helper twice. Wanted: say "changes nothing in the database"; move the helper to
`tests/agent_helpers.py` next to `previous_schema()`.
Found: 2026-10-02, review of run fix/migration-guard.

## `lado forget` can leave two loops for one session name

`lado forget` deletes the lock file while the stopped session's loop may still sleep (up to
INTERVAL). A new session of the same name started within that time locks a new file (another
inode); the old loop wakes, sees a running session and goes on: two loops. Wanted: each pass
checks that the held file is still the one at the path (os.fstat vs os.stat) and exits if not.
Found: 2026-10-02, review of run fix/session-loop.

## A running session loop keeps the old code after an upgrade

After upgrading LADO without a schema change, a running loop goes on with the old code until
`lado stop`; `lado doctor` and `lado ls` do not show it. Low priority.
Found: 2026-10-02, review of run fix/session-loop.

## A gate shows a needed note twice when it is the note before the gate

A gate with `needs: [design]` reached right from `design` shows design's report twice in
`lado answer` and on the gate's card in the UI's chat (`GateCard.tsx`): as `Note from
design` and as the note that led to the gate. The step text
prints such a note once (compared by note id), the gate view does not: the gate record
keeps a copy of the note's text, not the note's id.
Wanted: the gate keeps the id of the note that led to it (or the view finds it as the run's
note just before the gate opened), and the view prints a needed note that is the same
record once, as the step text does.
The same happens after the gate: the answer's note copies the note before the gate into its
body ("Note before the gate: ..."), so a next step that needs that state gets it twice (the
answer is its own notes record, so the id comparison does not catch it). Wanted as well: the
answer keeps a reference to the note before the gate instead of a copy. Also flows.py's
docstring example (`design_ok: needs: [design]` right after design) shows exactly this
duplicating pattern; pick an example where the gate needs an earlier state. lado-dev is not
affected (its design_ok follows architecture).
Found: 2026-10-02, run fix/gate-needs and its review.
## Flaky: integration test of a swallowed message typed again after a hook

`test_a_swallowed_message_is_typed_again_after_a_hook_of_its_agent` failed about 1 run in 5
of the full parallel integration suite (never alone): "timed out after 30s waiting for
delivery; ... w1 → supervisor [sent] 'report'". The screen shows the human's `sleep 0` and
the re-pasted `[from w1] report` in one input line, so the fake agent saw only `sleep 0`
and no prompt held the message line.
Wanted: the retry never types into an input the human has just typed into (or the test
waits for the human's line to be submitted first); the test passes under load.
Found: 2026-10-02, `make check` in fix/live-loop-reason (change touched only tests and
loop.py constants).

## Flaky: integration test of the migration refusal under a running session

`test_cli_refuses_to_migrate_the_database_under_a_running_session` failed once in nine
parallel integration runs: `lado ls` exited 0 (`assert 0 == 1`) because the database was
already migrated back. Likely a session-loop pass that passed `why_stop` before
`previous_schema()` and then opened the database through `runtime.sweep`, which migrates.
Wanted: a loop pass never migrates (the schema checked on the connection the pass uses),
so the refusal holds while the loop runs.
Found: 2026-10-02, repeated `make test-integration` in fix/live-loop-reason.

## A repo's own Kilo config may override what LADO switches off

LADO passes its Kilo settings (`autoupdate`, `snapshot`, permissions) in the file named by
`KILO_CONFIG`. In the opencode family a project's own config (`kilo.json` in the repo, or the
one Kilo's "Disable for this project" writes) is merged after that file, so a repo with
`"snapshot": true` would bring the snapshot dialog back. Not verified for Kilo 7.8.1.
Wanted: check the merge order; if the project wins, pass LADO's must-have settings where
they win (e.g. `KILO_CONFIG_CONTENT`, which 7.8.1 reads) and test it.
Found: 2026-10-02, run fix/kilo-no-snapshots.

## Claude agents load the user's global Claude Code plugins

A Claude Code agent started by LADO still loads the plugins enabled in the user's own
`~/.claude` (seen: the global superpowers plugin's SessionStart hook runs in the supervisor,
next to the kit's superpowers skills from its skill packs). So what an agent can do depends on
the human's machine, Claude agents get skills and hooks Kilo agents do not, and a kit cannot
switch them off (`--without` does not see them).
Wanted: an agent runs only what its kit gives it: find Claude Code's switch for user plugins
(e.g. a settings source or flag for the agent's own settings) and use it per agent, without
touching the user's global config; `lado doctor` says what it found. Low priority
(environment isolation), but it makes runs reproducible.
Found: 2026-10-03, choosing UI skills for the lado-dev kit.

## Skill packs written for Claude Code plugins break under LADO

`ui-ux-pro-max` (nextlevelbuilder/ui-ux-pro-max-skill) calls its scripts as
`python "${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max/scripts/search.py"`. Outside a
Claude Code plugin `CLAUDE_PLUGIN_ROOT` is unset, so the skill cannot find its scripts and
data when LADO links it from a source, for Claude and Kilo agents alike. Other plugin-born
packs may do the same. Wanted: decide whether LADO supports such packs (e.g. set
`CLAUDE_PLUGIN_ROOT`-like variables per skill, or a source option that maps them to the
source folder) or `lado kits check` warns about unknown `${...}` variables in a skill.
Found: 2026-10-03, choosing UI skills for the lado-dev kit.

## `lado kits check` warns about skills no role uses

Every `lado kits check lado-dev` prints four hardcoded-path warnings from superpowers skills
that no lado-dev role lists (diagnosing-superpowers, subagent-driven-development,
writing-skills). The kit cannot act on them, so the warnings are noise that hides real ones.
Wanted: lint only the skills the kit's roles use, or mark the others "(not used by any role)".
Found: 2026-10-03, review of lado-dev 0.5.0.

## `lado ui` fails while another server is just starting

`server/run.py` `wait_ready` treats any early exit of the server it started as a failure.
When two `lado ui` run at once, or `lado ui` right after `lado server`, the lock is held but
server.json not yet written; `lado ui` starts its own server, which exits at once ("a LADO
server already runs"), and `lado ui` reports "the LADO server ended as it started" although
the first server is ready a moment later. Wanted: on an early exit of its own process, check
whether the lock is held and, if so, keep waiting until the timeout.
Found: 2026-10-03, review of run feature/ui-skeleton (M-3).

## `make check` hides an integration test's need for the web bundle

`make check` builds the web UI (`make web`) before it runs the unit and integration tests,
while CI's `check` job runs them without the bundle. An integration test that reaches the
page behind `/` passes locally and fails in CI with 503 "the web UI's bundle is missing"
(test_server_log_is_the_owners_only_and_never_holds_the_token, CI run 37066847184).
Wanted: unit and integration tests run without the bundle in `make check` too (e.g. a
static dir from the test or the bundle hidden for them), so `make check` matches CI.
Found: 2026-10-03, run fix/ci-red-after-ui.

## The supervisor draws the UI mockups itself

In UI design steps the supervisor makes the mockups: it has no UI skills (frontend-design and
the visual critique skills belong to the developer and reviewer), nobody reviews a mockup
before the human sees it, the supervisor stops coordinating other runs meanwhile, and it
publishes them with a Claude-only feature. Fine for low-fidelity structure wireframes, which
are part of the talk with the human.
Wanted (lado-dev kit): a `designer` role (frontend-design plus visual critique; writes only
static HTML mockups in `.lado/mockups/<run>/`, never the UI source) that the supervisor starts
inside a design step for detailed section mockups; the supervisor shows them to the human
(opening the local file works for any provider; publishing a page is optional) and writes the
human's decisions into the design. Do it before the first task with detailed mockups.
Found: 2026-10-03, design of feature/ui-main-screen.

## state.connect() creates and migrates lado.db; readers have no read-only connection

`state.connect()` creates the schema when there is no `lado.db` and migrates an older one.
The UI server must never migrate, so each endpoint first checks the schema version
(`feed.schema_problem`) and only then calls `state.py`; a future endpoint that forgets the
check, or a race between the check and the call, can migrate the database under a running
session. `loop.why_stop` relies on the same discipline.
Wanted: a read-only connection in `state.py` for readers (the server, `loop.why_stop`) that
refuses another schema itself. Related: "Flaky: integration test of the migration refusal
under a running session".
Found: 2026-10-03, architect's review of the live updates design (feature/ui-live-updates).

## A terminal viewer outlives a UI server that is killed

A viewer tmux session (lado/terminal.py) cannot be made with `destroy-unattached on`: tmux
destroys an unattached session at once, before its client attaches. So when the UI server is
killed (SIGKILL, a crash), its viewers stay and keep the agents' windows linked, until the
next server start or `lado stop` removes them by their labels. Meanwhile `lado ls` and tmux
show extra `lado-view-*` sessions.
Wanted: viewers go with their server: set `destroy-unattached` once the client is attached,
or have `lado ls` and the session loop remove viewers whose server is not running.
Found: 2026-10-03, implement of feature/ui-agent-terminal.

## Agents read the human's own Claude Code settings, which change how they behave

LADO gives Claude Code its settings with `--settings`, but Claude Code still reads the
human's `~/.claude/settings.json`. With `"tui": "fullscreen"` there, every LADO agent runs
full screen (alternate screen, mouse tracking): its output is not in tmux's history, and the
UI's history layer can only say so. Hooks and permissions set there apply to agents as well.
Wanted: decide which of the human's settings an agent should get, and say so in
`lado doctor` (e.g. warn that agents run full screen), or pin what LADO depends on (the
renderer) in the agent's own settings.
Found: 2026-10-03, prototype of the history in implement of feature/ui-agent-terminal.

## Workers get ask_human and send_message(to="human") with no LADO-level hint

LADO 0.12 gives every agent `ask_human`, and `send_message`'s docstring offers `to="human"` to
workers too. By the human's decision (2026-10-03) the core does not restrict who writes to
the human; kit roles do (lado-dev 0.6.0 tells its workers to route questions through the
supervisor). A kit that forgets it lets a worker's question reach the human past the
supervisor. Wanted: revisit with more kits in use: a worker-specific hint in LADO's own
worker instructions, or tools only for the supervisor unless a role asks for them.
Found: 2026-10-03, review of lado-dev 0.6.0.

## Activity loads every message and run event of a session at once

The Activity feed (Layout task) loads `GET …/messages` (now without `with`: all of the
session's messages, agent-to-agent too) and `GET …/events` whole on each reset, and the store
keeps them all. A long session (hundreds of worker reports, dozens of runs) makes every
reconnect load and re-render all of it, while the human looks at the last screen.
Wanted: the latest N with "load earlier" (`?before=<id>&limit=`), or a window the feed asks
for as it scrolls; the store's lists keep only what was loaded.
Found: 2026-10-03, implement of feature/ui-layout.

## UI e2e screenshots of parallel runs overwrite each other

Every `make test-ui` / `make check` writes to the same `<temp dir>/lado-ui-shots/<test>.png`,
whatever worktree it runs in. When a developer and a reviewer (or two runs) test at once,
the folder holds a mix: a screenshot of the old rail showed up after the new code had passed
the same test. The reviewer can look at the wrong build's screens.
Wanted: a folder per worktree or per run (e.g. named after the branch or a hash of the
repo path), printed by the tests, so each report names its own screenshots.
Found: 2026-10-03, implement of feature/ui-layout (the rail change).
## Claude Code 2.1.288 is installed but TESTED_VERSION is 2.1.287

`lado doctor` warns: the installed Claude Code is 2.1.288, `providers/claude.py`
`TESTED_VERSION` is 2.1.287.
Wanted: run `make test-live PROVIDER=claude` on 2.1.288 and raise `TESTED_VERSION` if it
is green.
Found: 2026-10-03, design of feature/ui-polish.

## A terminal closed for good shows its reason twice

A terminal whose socket closes for good (e.g. a stopped session) shows the reason in its
status ("closed: session "x" is stopped") and again as the error notice beside it: the
server sends an error frame and then closes with the same reason. Now that the
supervisor's tab is always shown, every stopped session's page shows it twice.
Wanted: one line with the reason (the notice left out when it repeats the close reason).
Found: 2026-10-03, UI e2e screenshots of feature/ui-polish.

## A tooltip can miss its keyboard focus after a click

`web/src/Tooltip.tsx` sets `pressed` on pointer down and clears it only on focus. A click
on a button that already has focus (or in Safari, where a click does not focus a button)
leaves `pressed` set, so the next keyboard focus shows no tooltip once.
Wanted: clear `pressed` on pointer up / click, or test `:focus-visible` on the target.
Found: 2026-10-03, review of feature/ui-polish (Minor).

## Terminals.tsx and Team.tsx import each other

Terminals imports `SUPERVISOR`, `StatusDot` and `AgentTip` from Team, and Team imports
`useOpenTerminal` / `useShownTerminal` from Terminals. It works while each is used only
inside functions; a module-level use breaks on load order.
Wanted: move the shared agent pieces (`SUPERVISOR`, `StatusDot`, `AgentTip`) into a module
of their own (e.g. `agents.tsx`).
Found: 2026-10-03, review of feature/ui-polish (Minor).
## An open run's task cannot be amended

A small addition the human asks for while a run is in `implement` (feature/ui-polish:
AC-13..15) can only go to the developer as a message. The design note that the reviewer and
the merge gate get does not have it, and `lado log` does not tie it to the run. The only
other way, `lado flow-set` back to `design`, repeats the architect's review and the design
gate for a few lines.
Wanted: an addendum to an open run (from the supervisor, approved by the human), kept in
`notes` and shown to every later step and gate after the design note.
Found: 2026-10-03, feature/ui-polish.

## The version banner gives a stale tab the wrong advice

A tab opened before an upgrade keeps its old bundle. Once `lado ui` restarts the server,
that tab sees the new server's version and says to run `lado server stop` and `lado ui`,
though reloading the page is enough. Stopping the server is needless there.
Wanted: the banner first offers to reload the page, and names `lado server stop` and
`lado ui` only when the versions still differ after a reload.
Found: 2026-10-03, review of fix/stale-ui-server.

## The session list has its own copy of "not stopped"

web/src/Sessions.tsx (`grouped`) splits the sessions with its own `status === "stopped"`,
while the rail's count and the live store's reloads of what waits use `live.isLive`. Both
say the same now, but a change to one rule leaves the session list's groups apart from
the count.
Wanted: `grouped` (and `about`, `waits`) take the rule from `isLive`.
Found: 2026-10-03, review of feature/needs-you.

## `lado stop` kills agents without a graceful exit

`lado stop` (and Stop in the UI) kills the session's tmux windows at once. An agent CLI
gets no chance to end its turn or save its state.
Wanted: send each provider's own exit command first, wait a bounded time, then kill what
is left, and say which agents had to be killed. Seen in another orchestrator, where slow
agents were killed too early until a delay was added.
Found: 2026-10-04, design of feature/launch.

## A message to a new agent that is still starting waits until its first turn ends

A message sent to a supervisor (or a worker without a task) while it is `starting` stays
`pending`: its session-start hook sets it `idle`, but nothing hands over the queue then
(only turn-end and conversation-start do, and `sweep` only deals with typed messages). In
the fake-agent test it stayed pending for 30 s, until something else made the agent work.
Wanted: the session-start hook delivers the queue when it sets the agent `idle`, as
CONVERSATION_START does.
Found: 2026-10-04, fix/agent-env (integration test of the login-shell environment).

## `lado doctor` looks for the agent CLIs on its own PATH, not the agents'

`lado doctor` checks `claude`, `kilo` and `tmux` with `shutil.which` in its caller's
environment, while agents now run with their login shell's PATH (`agent_env.resolve`); a
CLI found by one may be missing for the other. The UI's New session window shows the same
check (`GET /api/providers`, `doctor.provider_status` with the server's PATH), so it can
offer a provider whose start then fails with "not on the agents' PATH", or the other way.
Wanted: doctor looks the agent CLIs up on the resolved environment's PATH too and says
where they differ.
Found: 2026-10-04, fix/agent-env; the UI's case in feature/launch.

## No tmux on an agent's PATH breaks its LADO calls with a raw error and a ghost worker

When the agent's environment has no `tmux` on PATH, its `lado mcp` fails `spawn_worker`
with a FileNotFoundError ("Error executing tool spawn_worker"), and the cleanup in
`runtime.spawn_worker` fails the same way on `kill_window`, so the worker stays `starting`
in `lado ls`.
Wanted: tmux calls raise TmuxError with "tmux not found on PATH", and the spawn cleanup
cannot be stopped by its own tmux call failing.
Found: 2026-10-04, fix/agent-env (fake login shell without the Homebrew PATH).

## An agent whose process dies before its first hook stays `starting` for good

When an agent's window closes before any hook ran (its CLI crashed at once, a bad flag),
nothing notices: the agent stays `starting` in `lado ls` and the UI, and a session whose
supervisor window closed vanishes from tmux although `lado start` reported success.
Wanted: notice the window's end (tmux `remain-on-exit` with a `pane-died` hook, or a check
in the session loop) and mark the agent `stopped` with the reason, shown in `lado ls`/UI.
Found: 2026-10-04, review of fix/agent-env.

## A login shell that starts tmux from its startup files breaks the agents' environment

Startup files that start or attach tmux when `$TMUX` is unset (`[ -z "$TMUX" ] && exec tmux`,
oh-my-zsh's tmux plugin with autostart) make `$SHELL -ilc` fail without a terminal, so every
`lado start` and spawn stops with the shell's error. The error is loud and names
`LADO_AGENT_ENV=inherit`, but does not say why.
Wanted: the docs and `lado doctor`'s hint name this case and how to guard it in the rc file
(for example, skip the autostart when the shell is not interactive on a terminal).
Found: 2026-10-04, review of fix/agent-env.

## A snapshot's problem of several lines shows as one line in the UI

When the validator refuses a run's flow snapshot, `problem` (`RunInfo`, `GateInfo`) holds
one error per line (`flows.from_snapshot` joins them with "\n"). The run page
(`web/src/Flows.tsx`, `.problem`) and the gate card (`web/src/GateCard.tsx`,
`.gate-problem`) put it in a `<p>`, so the lines run together without a break.
Wanted: `white-space: pre-wrap` on both (or one line per error).
Found: 2026-10-04, review of fix/unreadable-snapshot (Minor).

## `lado answer` without a gate stops at a gate whose run's flow cannot be read

`lado answer` (no arguments, or a session) and the gate popup show each open gate with the
notes it needs (`cli._choose` → `runs.gate_notes` → `runs.flow_of`). A gate of a run whose
flow snapshot cannot be read raises `runs.SnapshotError`: the command ends with that error,
and the other open gates are not asked about.
Wanted: such a gate is shown with its problem (it can only be left open; the run is
cancelled with `flow_cancel`) and `lado answer` goes on with the other gates.
Found: 2026-10-04, fix/snapshot-core (implement).

## Finishing a worker in a stopped session says "no worker"

`lado finish <stopped session> w1` (and the UI's `POST …/agents/w1/finish`) answers
`no worker "w1"; workers: none`: `runtime.finish_worker` does not ask
`runtime.running_session`, and `lado stop` has forgotten the agents already.
Wanted: the same refusal as the other commands in a stopped session (`session "s" is
stopped; …`), which says what to do.
Found: 2026-10-04, feature/agents-tab (implement).

## Flaky UI test: a gate answered with `lado answer` loses the rail's "Needs you" count

`tests/ui/test_needs_you.py::test_a_gate_answered_with_lado_answer_goes_without_a_reload`
failed once in `make check` (review of feature/flows-list, commit d80765d): after the gate's
answer the rail's Needs you link had no count, so the supervisor the test set `waiting`
with `state.set_status` was no longer waiting; run alone it passed 3 of 3. Likely a hook or
status change of the fake agent under load overwrites the status the test set.
Wanted: the test does not rely on nobody else changing the agent's status (or waits for it).
Found: 2026-10-04, feature/flows-list (review).

## Flows.tsx and Agents.tsx import each other

`Flows.tsx` imports `AgentName` from `Agents.tsx` and `Agents.tsx` imports `isOpen` from
`Flows.tsx`. It works (both are used only while rendering), but each new tab with a list
of runs or agents would join the cycle.
Wanted: the helpers about runs and agents shared by the tabs in a module of their own.
Found: 2026-10-04, feature/flows-list (review).

## Flaky integration test: the UI's start says at once that its server exited

`tests/integration/test_server_process.py::test_ui_says_at_once_when_the_server_it_started_exits`
failed once in `make check` on feature/flows-list (`assert 10.22 < 15.0 / 2`, the time
`lado ui` took to report the exit, against `server_run.READY_TIMEOUT / 2`); run alone it
passed 3 of 3 (0.7–5.2 s). Under the full parallel run the machine is slow enough to cross
the bound.
Wanted: a bound that tells "at once" from "waited for the timeout" under load too (e.g.
compare with the full READY_TIMEOUT, or measure the wait the code does, not wall time).
Found: 2026-10-04, feature/flows-list (implement, make check).
## The git cache is never cleaned

`LADO_HOME/cache` keeps a clone of every (address, tag or commit) a pack or `lado kits add`
ever fetched; `lado kits update` and `remove` leave the old clones there, since running
agents may still read them. The folder only grows.
Wanted: a `lado kits clean` (or a step of `update`/`remove`) that removes the clones no
installed kit, project kit and running session uses, and says what it removed.
Found: 2026-10-04, design of feature/kit-manifest-v2.

## The API's `core` helper turns only LadoError into a 400

`server/app.py` `core()` and the session endpoints caught `runtime.LadoError` only, so a
`kits.KitError` from the core (a kit not found or invalid at `POST /api/sessions`) was a 500
without its reason. Fixed for `POST /api/sessions` and resume in feature/kit-manifest-v2;
`core()` still lets any other core error type through as a 500.
Wanted: one error type for what the core refuses (or `core()` and the endpoints map each
known one to 400), so no refusal reaches the UI as a 500.
Found: 2026-10-04, feature/kit-manifest-v2 (implement).

## Flaky: integration test of the UI server's early exit

`tests/integration/test_server_process.py::test_ui_says_at_once_when_the_server_it_started_exits`
failed once in `make check` (pytest -n auto) with `assert 9.038402291946113 < (15.0 / 2)`;
alone it passes in 0.79 s. Its bound is half of `READY_TIMEOUT` in wall time, which a
loaded machine can exceed.
Wanted: a bound that holds under parallel load, or a check without absolute time (the
answer came before `READY_TIMEOUT`, not within half of it).
Found: 2026-10-04, review of feature/kit-manifest-v2.

## README says there is nothing to run yet

`README.md`, Install, still ends with "There is nothing else to run yet" and the status
note says "Nothing is ready to use yet", while sessions, kits, flows and the web UI work
(the README now has a section on the web UI).
Wanted: a README that says what runs today (start a session, the UI, kits) and links the
docs.
Found: 2026-10-04, feature/server-host (implement).

## The New session window does not say who will lead the session

`lado start` and `lado kits show` print `lead: ...` and warn about each kit supervisor that
is not used; the New session window shows neither before Start, so the human learns only
after the start (or not at all) that LADO's built-in supervisor leads.
Wanted: the window shows the lead line and the warnings for the chosen kits and Switch off
items (an endpoint over `kits.resolve`), before Start.
Found: 2026-10-04, design of feature/without-at-kit.

## lado-dev in lado-kits still uses the old kit format

LADO 0.19.0 reads the lead from `supervisor:` in kit.yaml; `supervisor: true` in an agent
and `default_agent` in kit.yaml are unknown keys now. lado-dev on the lado-0.19 branch of
the lado-kits repo still has both, so it fails to load with 0.19.0.
Wanted: lado-dev with `supervisor: supervisor` in kit.yaml, without `default_agent` and
`supervisor: true`, before the 0.19.0 release (the supervisor does it after the merge).
Found: 2026-10-04, design of feature/without-at-kit.

## Flaky: vitest "the tab without an agent opens the supervisor"

`make web` failed once in `src/Agents.test.tsx` > "the tab without an agent opens the
supervisor, and an unknown one is not found" with `Unable to find role="region" and name
"Agent supervisor"`; the file alone and the next `make web` passed. Probably a wait shorter
than the render under the full run's load.
Wanted: the test waits for what it checks (findBy with a timeout that holds under load).
Found: 2026-10-04, feature/without-at-kit (implement).
## A refused permission leaves the Claude agent waiting until the human types

When the human refuses a Claude Code permission dialog (or dismisses an AskUserQuestion
question) without a comment, Claude Code interrupts the turn and runs no hook: no
PostToolUse, PermissionDenied or Stop (checked with 2.1.289). The agent stays `waiting`,
LADO types nothing into it and its queue waits, until the human types a line.
Wanted: the agent idle once the turn is interrupted, its queue handed over; needs a sign
of the interruption from Claude Code (none found in its hooks).
Found: 2026-10-04, feature/waiting-ends (implement, manual check).

## One key per waiting agent, though Kilo can have several requests open

Kilo keeps a list of open permission and question requests per session and shows the
lists of the agent and its subagents together, so several can be open at once. LADO keeps
one key (`agents.waiting_for`, the latest request's): when an earlier request is answered
last, the agent is busy while one is still open, or waiting after the latest is answered.
Wanted: a set of open request keys per agent; the wait ends when it is empty.
Found: 2026-10-04, feature/waiting-ends (implement, Kilo 7.8.3 source).

## Claude's waiting hooks unchecked in permission mode auto

feature/waiting-ends checked PermissionRequest and PostToolUse by hand with Claude Code
2.1.289 in the modes default, bypassPermissions and dontAsk, not in auto: Claude Code says
"auto mode unavailable for this model" for Haiku. If auto's classifier refuses a call after
PermissionRequest, no hook comes and the agent shows waiting until its turn ends.
Wanted: the check in auto on a model that has it (the human's OK: it is paid); if
PermissionRequest runs there without a dialog, a hook that ends the wait (PermissionDenied).
Found: 2026-10-04, review of feature/waiting-ends.

## Claude's TESTED_VERSION is older than the hooks LADO now relies on

`providers/claude.py` has `TESTED_VERSION = "2.1.287"`, but the waiting hooks
(PermissionRequest without tool_use_id, its tool_input equal to PostToolUse's, async
PostToolUse) were checked with 2.1.289 only; `lado doctor` warns about 2.1.289 and not
about 2.1.287.
Wanted: before the release, `make test-live PROVIDER=claude` on 2.1.289 (with the human's
OK) and TESTED_VERSION raised to it.
Found: 2026-10-04, review of feature/waiting-ends.

## The Flows tab loads every note of the session

`GET /api/sessions/{name}/notes` returns all notes of all runs of the session with their
bodies: 1.7 MB for session `lado` on 0.18.0, and it only grows, as messages did before
feature/chat-paging.
Wanted: notes in windows with a cursor, as the chat's messages (`live.ts`
`watchMessages`), loaded per run or by pages.
Found: 2026-10-05, feature/chat-paging (design).
## Agents may be asked to read kit files outside their allowed folders

Two ways a Claude agent may meet a permission dialog in the modes default and acceptEdits
when it only reads a kit's files: `${KIT_DIR}` in an agent's prompt (a role, a kit's leading
supervisor, a lead skill's text) becomes the kit's absolute folder, which for a linked local
kit is outside LADO_HOME and outside every `--add-dir`; and the skills LADO links into
`.claude/skills` (`base.link_skills`) point to their folders in the kit or the git cache, so
reading a skill's other files (not loading it) goes to a path outside `--add-dir`. Kilo
allows reads under LADO_HOME only, so a linked local kit is outside there too.
Wanted: a live check of both in mode default; if a dialog shows, give the agent its kits'
folders to read (`AgentSpec.read`) or copy what it reads, as the lead's lead-files are.
Found: 2026-10-04, design and architect's review of feature/lead-skills.

## Flaky: vitest "the runs come in groups" times out under load

`make check` failed twice in a row in `web/src/Flows.test.tsx` > "the runs come in groups,
the ended ones folded and remembered, the tab counts the open ones" with `Error: Test timed
out in 5000ms` (5572 ms, 5823 ms) while the machine's load average was 180-220; the file
alone passed (19 passed) and the next `make check` was green. The test takes about 5 s even
when it passes, so vitest's default 5 s timeout leaves no margin.
Wanted: the test made shorter (fewer steps or fake timers) or given its own timeout.
Found: 2026-10-05, feature/lead-skills (implement, review fixes).

## The Stop popover does not give focus back to its icon

Esc, Cancel or a click outside closes the session's Stop popover (`SessionControl.tsx`,
`onClose={close}`) and the focus goes to the page's body; the list row's menu gives it back
to its button (`back()` in `SessionRowMenu`). It was so on main before the icons too.
Wanted: closing the popover without a stop puts the focus back on the Stop icon.
Found: 2026-10-05, feature/session-controls (review).

## An open menu or popover stays where it opened when the page scrolls

`useBelow` (`web/src/Menu.tsx`) places a row's menu or the Stop popover once, when it opens;
scrolling the session list or the session's page, or resizing the window, leaves it at its
old place, away from its button. The row's menu did so on main before.
Wanted: the place computed again on scroll and resize, or the menu closed on scroll.
Found: 2026-10-05, feature/session-controls (review).
