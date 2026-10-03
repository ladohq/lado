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

## A broken kit source blocks every kit lookup

If any registered source is broken (folder or clone missing, two kits with one name, bad
layout), every kit lookup fails, even `lado start` with the built-in `default` kit. The error
says to run `lado sources update` or `lado sources remove`.
Wanted (decided 2026-10-02): fail only when the wanted kit (or a kit it includes) depends on
the broken source; otherwise warn and go on.
Found: 2026-10-01, kit sources review.

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

## A kit cannot say which LADO it needs

A kit that uses a newer flow or kit field (e.g. a flow state's `needs`) fails in an older
LADO with a validator error about an unknown field, which does not say that LADO is too old.
So a kit change must wait until every user has upgraded, and the order (release LADO first,
then the kit) lives only in people's heads.
Wanted: `kit.yaml` may say `requires: lado>=0.11`; an older LADO refuses the kit with
"kit <name> needs LADO >= 0.11, this is 0.10.0: upgrade LADO" (`lado start`, `lado kits
check`), and the kit's own validator errors stay for real mistakes.
Found: 2026-10-02, planning the lado-dev update for named notes.

## A gate shows a needed note twice when it is the note before the gate

A gate with `needs: [design]` reached right from `design` shows design's report twice in
`lado answer`: as `Note from design` and as the note that led to the gate. The step text
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
next to the kit's superpowers skills from `lado sources`). So what an agent can do depends on
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

## A human who works only in the browser does not see gates

The gate popup (`tmux.popup`) opens only on the clients of the session's own tmux session;
a browser's terminal is a client of a viewer session, so it never shows the popup, and the
UI has no gates yet. A human who left tmux for the UI misses a waiting gate until they look
at `lado ls`. docs/design/ui.md (Tasks, Gates) says so for now.
Wanted: the Gates task shows gates in the UI (Needs you, the gate page) and notifies the
browser.
Found: 2026-10-03, architect's review of the agent terminal design (feature/ui-agent-terminal).

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
## A gate answered with free text is lost without a word

The human answered the merge gate by typing "reject, стоит исправить minors?" (into the popup or a
window); nothing took it as an answer, the gate stayed open, and nothing told the human that
the answer was not accepted. Only `lado answer` (or the popup's option) answers a gate.
Wanted: the Gates task answers gates with buttons and a comment in the chat; until then, the
popup says plainly when the input is not one of the options, and keeps asking.
Found: 2026-10-03, merge gate #35 of feature/ui-layout.

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
