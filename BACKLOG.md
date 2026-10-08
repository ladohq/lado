# Backlog

Tasks and bugs found while using LADO, until the external task tracker is connected
(see ROADMAP.md, stage 9). Move them to the tracker then and delete this file.
Entries sit in four tiers, by rank within each: P0 fix now, P1 next, P2 when convenient,
P3 maybe never (candidates for removal); a new entry goes into its tier with a `Size:` and
`Why here:` line under its title.

# P0: fix now

No entry is open.

# P1: next

## `make check` fails on timeouts when the machine is under heavy load

Size: M. Why here: a red `make check` with no real error hits every flow run; this entry holds the timeout flakes below as sub-items.

With a load average of 150-420 (other agents of the session running), three full
`make check` runs failed on different timeouts each time, and every failed test passed on
its own: test_event_stream::test_the_server_stops_with_a_stream_open (STOP_TIMEOUT/2),
test_fake_agent::test_the_agent_ends_its_process_on_exit, test_agent_terminal's
test_the_humans_tmux_session_is_left_as_it_was and
test_history_gives_the_windows_past_lines_and_says_when_it_is_full_screen,
test_flow_runs::test_a_worker_gets_a_step_far_longer_than_a_tmux_command, the UI tests
test_chat::test_a_long_chat_opens_with_its_latest_page… and
test_layout::test_a_chip_opens_its_agents_terminal…, and vitest `findBy…` waits.
Wanted: `make check` gives the same verdict under load (time bounds that hold under
parallel load, or `-n` chosen by the machine's load), so a red run means a real failure.
Found: 2026-10-06, review of fix/deliver-on-idle.
Also (2026-10-06, fix/conversation-resume-roadmap, load average ~180):
test_session_loop::test_the_loop_types_in_a_message_every_hook_missed and the UI test
test_terminal_panel::test_dont_ask_again_takes_control_at_once_after_a_reload failed and
passed on their own.
Also (2026-10-06, merge of fix/trailing-backslash, load average ~200): the UI tests
test_agents_tab::test_a_workers_page_shows_its_work_and_finish_discards_it,
test_flows_tab::test_in_a_narrow_column_the_runs_take_it_and_a_run_has_the_way_back,
test_kits_page::test_the_update_window_keeps_its_buttons_on_a_short_screen and
test_agent_terminal::test_a_viewer_has_only_the_agents_window_and_no_tmux_keys failed in
`make check` and passed together on a serial rerun.
Partly done (2026-10-06, fix/check-lock): concurrent runs from separate sessions or
worktrees no longer add up, since `make check`, `make test`, `make test-integration` and
`make test-ui` take one lock per machine (`scripts/check_lock.py`, AGENTS.md). Still open:
one run on a machine other agents keep busy, with `-n` not chosen by the load.
Also (2026-10-07, merge of feature/turn-resume, load average rising to 60-70 during the run
itself, nothing else running): two of four `make check` runs on one commit failed, each on
other timeouts: vitest Launch "the folder is checked by the server and its reason shown…";
then the UI tests test_layout::test_a_chip_opens_its_agents_terminal… and
test_main_screen::test_a_page_loads_without_a_console_error… (the server did not come up
in 15 s; the fake provider's `server --port 0` timed out after 10 s) and
test_agent_liveness::test_the_human_writes_to_a_worker_while_the_supervisor_is_stopped
(w1 busy after 30 s; 3 of 3 green alone). So `-n auto` alone loads the machine enough.
Also (2026-10-07, fix/test-timers, the integration tests now with `LADO_LOOP_INTERVAL=0.25`
and `LADO_RETRY_DELAYS=0.5,0.5,0.5`, load average 54 from other sessions): one parallel
`make test-integration` run (164 s instead of about 80) failed
test_session_loop::test_the_loop_types_a_swallowed_message_again and
test_flow_runs::test_runs_and_gates_survive_stop_and_start; their lines were not kept, and
both passed 5 of 5 alone and in the six parallel runs after it (five `make
test-integration`, one `make check`). A short retry delay is
exceeded by a hook that takes over 0.5 s to start under such load (the message is then
typed once more), so these may be timing-sensitive under load.
Also (2026-10-07, fix/integration-fix1, load average 90-160 from other processes): `make
check` failed in vitest on Launch.test.tsx:197 "the folder is checked by the server…":
`expect(startButton().disabled).toBe(false)` right after `await ready("/src/lado")` got
true (a synchronous check of what a later render sets); `make web` and `make check` passed
right after.

### Vitest tests time out at vitest's default 5 s under load, one entry per test

Size: S: one setting in vite.config.ts; `testTimeout` and `asyncUtilTimeout` are set nowhere.

`cd web && npm test` at a load average of about 60 failed 3 of 365 tests on their 5000 ms
timeout: Agents "the supervisor comes first, then the agents by spawn" (5791 ms), Chat "the
chat shows who wrote each message ..." (5180 ms), Flows "the runs come in two groups"
(5441 ms); `make web` had passed minutes before. The cause is shared:
`web/vite.config.ts` keeps vitest's default `testTimeout` (5 s), and `findBy`'s default
1 s, while `make check` runs vitest on a machine other checks keep busy.
Earlier single failures of the same kind, each passing alone and on the next run:
- `src/Agents.test.tsx` > "the tab without an agent opens the supervisor, and an unknown one
  is not found": `Unable to find role="region" and name "Agent supervisor"` (2026-10-04,
  feature/without-at-kit; 2026-10-05, feature/kit-marketplaces-core, the file took 26 s at
  load average 100); 2026-10-07, merge of fix/esc-docs, with the Flows one below, twice in
  a row at load average 74-129 while another worktree ran `uv run pytest -n auto`, which
  takes no check lock; green when that run had ended.
- `src/Flows.test.tsx` > "the flows tab without a run opens the first waiting run, else the
  first active one" (`… "Run feature/flows-tab"`, `… "Run fix/gate-bubble"`) and "with no
  runs both groups are there and say they are empty; with only ended ones the latest to end
  opens" (`… "Run fix/older"`): 2026-10-05 at load average 80–160 (feature/session-list-groups),
  in feature/kits-page-polish (18 vitest workers beside the build) and in
  feature/opencode-provider after merging main (with the Agents flake; 47 passed alone).
- `src/Flows.test.tsx` > "the runs come in groups, the ended ones folded and remembered, the
  tab counts the open ones": `Test timed out in 5000ms` twice in a row (5572 ms, 5823 ms) at
  load average 180-220 (2026-10-05, feature/lead-skills); it takes about 5 s even when it
  passes, so it may also need to be made shorter (fewer steps or fake timers).
- `src/App.test.tsx` > "the Agents tab follows the agents' changes; a reset loads them
  again": `Unable to find role="navigation" and name "Agents"` at load average 238
  (2026-10-05, review of feature/kit-marketplaces-core).
Wanted: one setting for the whole suite (a `testTimeout` and an `asyncUtilTimeout` that
hold under load), so a test fails only when what it waits for never comes.
Found: 2026-10-04..06, the tests above; this entry 2026-10-06, investigation of why
`make check` is slow (worker check-speed).

### Flaky: integration test "spawned worker reports back to supervisor" times out at `starting` under load

Size: S/M: needs one shared wait helper with a margin.

`tests/integration/test_agents.py::test_spawned_worker_reports_back_to_supervisor` failed in a
full `make check` at load average ~200: "timed out after 30s waiting for the report; agents:
supervisor idle, worker starting". Alone it passed 3 of 3. The same pattern, each once in a
full `make check` and passing alone or on a rerun:
- `tests/integration/test_agent_kits.py::test_a_worker_gets_its_role_from_an_installed_kit`
  (since fix/integration-fix3 a unit test in tests/test_runtime.py):
  `timed out after 30s waiting for dev to be idle; agents: supervisor idle, dev starting`
  at load average near 200 (2026-10-05, after merging main into feature/kits-page-polish).
- `tests/integration/test_agent_kits.py::test_two_kits_get_two_versions_of_one_skill_pack`
  (removed in fix/integration-fix3, its proof is in the unit tests):
  `timed out after 30s waiting for dev1 to be idle; agents: supervisor idle, dev1 busy, dev2
  starting`; the machine may have slept during that run (2026-10-05, review of
  feature/self-update).
- `tests/integration/test_agent_terminal.py::test_stop_ends_open_terminals_and_leaves_no_window_viewer_or_agent`
  (`waiting for w1 idle; agents: supervisor idle, w1 busy`) and
  `tests/integration/test_flow_runs.py::test_the_humans_answer_moves_the_run_on_to_the_next_agent`
  (`waiting for worker to be idle; agents: supervisor idle, worker starting`), both in one
  `make check` of 11.5 min; both passed alone (2026-10-06, fix/trailing-backslash).
Wanted: integration tests that wait for a worker's start share one wait helper with a margin
for parallel runs under load, not 30 s in each test.
Found: 2026-10-05, the kits tests above; 2026-10-06, review of fix/finish-race.

### Flaky integration test: the UI's start says at once that its server exited

Size: S.

`tests/integration/test_server_process.py::test_ui_says_at_once_when_the_server_it_started_exits`
failed once in `make check` on feature/flows-list (`assert 10.22 < 15.0 / 2`, the time
`lado ui` took to report the exit, against `server_run.READY_TIMEOUT / 2`); run alone it
passed 3 of 3 (0.7–5.2 s). Again in the review of feature/kit-manifest-v2 (`assert
9.038402291946113 < (15.0 / 2)`; alone 0.79 s). Under the full parallel run the machine is
slow enough to cross the bound.
Wanted: a bound that tells "at once" from "waited for the timeout" under load too (e.g.
compare with the full READY_TIMEOUT, or measure the wait the code does, not wall time).
Found: 2026-10-04, feature/flows-list (implement, make check); review of
feature/kit-manifest-v2.

### Flaky: UI e2e test of a question card under load

Size: S.

`tests/ui/test_chat.py::test_the_supervisor_asks_and_the_human_answers_in_a_card` failed in
`make check` with `Locator expected to be visible ... get_by_role("article", name="Question
from supervisor").get_by_role("button", name="later")` (timeout 5000ms) at a load average of
about 160; `tests/ui/test_chat.py` passed alone right after with no change.
Wanted: the wait for the fake agent's question allows for a loaded machine (the shared
timeout of the UI tests, or a wait on the message in lado.db first), so it fails only when
the question never comes.
Found: 2026-10-05, merge step of feature/session-list-groups.

### Launch vitest tests fail now and then under the load of a full run

Size: S: check whether there is a race in the product (`touched`).

In a full vitest run (`make check`, `npx vitest run`), about 2 runs in 7,
`Launch.test.tsx > without a kit Start stays off and the window says why` did not find
"a session needs at least one kit" right after the click on Remove default
(`TestingLibraryElementError: Unable to find an element with the text`); the file alone
passes. It was first seen in the review of fix/chat-start-day-tz (2026-10-05), while a
second vitest run loaded the machine, with a synchronous `getByText` after `fireEvent.click`.
Once `with a refused copy Copy link shows the address selected` failed on the
field's focus (`expected <body> to be <input>`), checked before the effect that focuses it.
Both now wait for what they check (`findByText`, `waitFor`). Not shown: why the kits
message is late; the Launch window's `touched` guard should keep a late folder load from
putting the default kit back, so a product race is not ruled out.
Wanted: if the kits test still fails with the wait, look for a load that resets the kits
after the human removed them.
Found: 2026-10-05, run feature/session-head (developer, reviewer).
Seen again 2026-10-07, verify of fix/integration-fix2, load average 75–108: 4 UI tests
failed, all passed on rerun: test_launch::test_stop_from_the_session_head (tooltip 'Stop
session…' not in 5 s), test_chat::test_the_human_writes_and_the_supervisor_gets_it_and_replies
(test_chat.py:35, value ''), test_layout::test_many_tabs_stay_on_one_line… (click 'Open
terminal' 30 s timeout), test_launch::test_a_session_starts_from_the_new_session_window
(provider select disabled: `/api/providers` slower than 30 s, since the CLIs' `--version`
are slow under load; failed twice, passed the third time).

## Test runs leave `lado server` processes behind

Size: S. Why here: each leaked server keeps loading a machine whose load already makes `make check` fail on timeouts, and one ran for 29 hours.

On 2026-10-06 the supervisor found 23 orphaned `tests/integration/fake_provider.py server
--port 0` processes (parent 1, about 35 minutes old, from the feature-mcp-secrets and
session-tabs worktrees) and a `lado.cli server --port 0` from the feature-self-update
worktree that had run for 29 hours. Cause: the `server` fixture in tests/ui/conftest.py:44-60
only calls `server_run.stop()` and `process.wait(timeout=10)` in its `finally`; when
`wait_ready` times out under load (no server.json yet), `stop()` finds no server and nothing
kills the process.
Wanted: every test that starts a server kills its process whatever `stop()` did, and a
check at the end of the test session that no process a test started is still alive.
Found: 2026-10-06, supervisor; recorded in fix/check-lock.
Seen again 2026-10-07: two `lado.cli server --port 0` from the feature-turn-resume (13 h)
and feature-mcp-secrets (16 h) worktrees, and three test tmux servers (`tmux -L
lado-test-*`, sessions `ui-*`, from UI tests of fix-server-stop-streams, 1.5 h old, parent
1) with their fake agents still alive: the tmux servers a UI test starts leak too. All idle
(0% CPU); killed by hand.

## Flaky terminal socket test: input checked before it is written

Size: S. Why here: it has already turned CI red before a release.

`tests/test_terminal_socket.py::test_control_takes_input_and_resize` failed once in CI
(Python 3.13, run 37426821369): `written` was `[b'ls\r']` without the `é`. The test takes
the `done` output frame as proof that all input was handled, but output and input are
separate tasks in the socket, so `done` can arrive before the last input is written.
Passed on rerun and locally. Wanted: wait for the written input itself (poll `written`
with a timeout), not for an unrelated output frame.
Found: 2026-10-06, CI before the 0.23.0 release.

## Flaky: integration test of a swallowed message typed again after a hook

Size: M. Why here: also a product problem: the retry is pasted into a line the human has started typing.

`test_a_swallowed_message_is_typed_again_after_a_hook_of_its_agent` failed about 1 run in 5
of the full parallel integration suite (never alone): "timed out after 30s waiting for
delivery; ... w1 → supervisor [sent] 'report'". The screen shows the human's `sleep 0` and
the re-pasted `[from w1] report` in one input line, so the fake agent saw only `sleep 0`
and no prompt held the message line.
Wanted: the retry never types into an input the human has just typed into (or the test
waits for the human's line to be submitted first); the test passes under load.
Found: 2026-10-02, `make check` in fix/live-loop-reason (change touched only tests and
loop.py constants).
Again 2026-10-07, merge step of feature/turn-resume (load average about 10): the fake
agent's input was `sleep 0` with the bracketed paste `[from w1] report` in the same line;
green on the next `make check`. Again 2026-10-07 in fix/test-timers (a 0.25 s loop interval,
load average 54), which changed the test: the report is due only after the human's
`sleep 0` was submitted and its hooks ran, so no sweep pastes while the human types. The
product side (a retry pasted into a line the human has started) is still open.

## Flaky UI test: a gate answered with `lado answer` loses the rail's "Needs you" count

Size: S. Why here: a flaky test that turns `make check` red.

`tests/ui/test_needs_you.py::test_a_gate_answered_with_lado_answer_goes_without_a_reload`
failed once in `make check` (review of feature/flows-list, commit d80765d): after the gate's
answer the rail's Needs you link had no count, so the supervisor the test set `waiting`
with `state.set_status` was no longer waiting; run alone it passed 3 of 3. Likely a hook or
status change of the fake agent under load overwrites the status the test set.
Wanted: the test does not rely on nobody else changing the agent's status (or waits for it).
Found: 2026-10-04, feature/flows-list (review).

## Local test runs do not catch a commit without a git identity

Size: S. Why here: catches locally what now shows only in CI.

On macOS (and wherever git derives an identity from the host), a test that commits in a
repository without a local user passes locally and fails only in CI ("Author identity
unknown"), as `test_another_folders_session_does_not_count` did before 0.22.0.
Wanted: tests/conftest.py sets `user.useConfigOnly=true` for the test run
(GIT_CONFIG_COUNT/KEY/VALUE, as agent_helpers does for maintenance), so it fails locally too.
Found: 2026-10-06, review of fix/ci-git-identity.

## `make check` hides an integration test's need for the web bundle

Size: S. Why here: green locally, red in CI.

`make check` builds the web UI (`make web`) before it runs the unit and integration tests,
while CI's `check` job runs them without the bundle. An integration test that reaches the
page behind `/` passes locally and fails in CI with 503 "the web UI's bundle is missing"
(test_server_log_is_the_owners_only_and_never_holds_the_token, CI run 37066847184).
Wanted: unit and integration tests run without the bundle in `make check` too (e.g. a
static dir from the test or the bundle hidden for them), so `make check` matches CI.
Found: 2026-10-03, run fix/ci-red-after-ui.

## UI e2e screenshots of parallel runs overwrite each other

Size: S. Why here: the reviewer sees another build's screenshots, which hurts the review.

Every `make test-ui` / `make check` writes to the same `<temp dir>/lado-ui-shots/<test>.png`,
whatever worktree it runs in. When a developer and a reviewer (or two runs) test at once,
the folder holds a mix: a screenshot of the old rail showed up after the new code had passed
the same test. The reviewer can look at the wrong build's screens.
The same on 2026-10-05: a run of feature/flows-tab-redesign showed the old Flows page from
another worktree. The `shot` fixture (`tests/ui/conftest.py`, `SHOTS`) writes there.
Wanted: a folder per worktree or per run (e.g. named after the branch or a hash of the
repo path), printed by the tests, so each report names its own screenshots.
Found: 2026-10-03, implement of feature/ui-layout (the rail change); 2026-10-05,
feature/flows-tab-redesign (developer).

## A refused permission leaves the Claude agent waiting until the human types

Size: M. Why here: a wrong status and a stalled queue; needs research.

When the human refuses a Claude Code permission dialog (or dismisses an AskUserQuestion
question) without a comment, Claude Code interrupts the turn and runs no hook: no
PostToolUse, PermissionDenied or Stop (checked with 2.1.289). The agent stays `waiting`,
LADO types nothing into it and its queue waits, until the human types a line.
Wanted: the agent idle once the turn is interrupted, its queue handed over; needs a sign
of the interruption from Claude Code (none found in its hooks).
An Esc on the dialog runs no hook either (checked with 2.1.292; see the interrupt entry in P3).
Found: 2026-10-04, feature/waiting-ends (implement, manual check).

## One key per waiting agent, though Kilo can have several requests open

Size: M. Why here: a wrong status for Kilo; a question of provider parity.

Kilo keeps a list of open permission and question requests per session and shows the
lists of the agent and its subagents together, so several can be open at once. LADO keeps
one key (`agents.waiting_for`, the latest request's): when an earlier request is answered
last, the agent is busy while one is still open, or waiting after the latest is answered.
Wanted: a set of open request keys per agent; the wait ends when it is empty.
Found: 2026-10-04, feature/waiting-ends (implement, Kilo 7.8.3 source).

## Claude's waiting hooks unchecked in permission mode auto

Size: S. Why here: one manual check, paid, needs the human's OK.

feature/waiting-ends checked PermissionRequest and PostToolUse by hand with Claude Code
2.1.289 in the modes default, bypassPermissions and dontAsk, not in auto: Claude Code says
"auto mode unavailable for this model" for Haiku. If auto's classifier refuses a call after
PermissionRequest, no hook comes and the agent shows waiting until its turn ends.
Wanted: the check in auto on a model that has it (the human's OK: it is paid); if
PermissionRequest runs there without a dialog, a hook that ends the wait (PermissionDenied).
Found: 2026-10-04, review of feature/waiting-ends.

## A parent OpenCode or Kilo agent's variables reach the agents started from its shell

Size: S. Why here: a nested CLI's hooks report as the outer agent; parity with Claude (tmux.py:27-34 knows only Claude's variables).

`tmux._INHERITED_AGENT_VARS` and `_INHERITED_AGENT_PREFIXES` drop only Claude Code's
variables. An OpenCode or Kilo agent's `OPENCODE_CONFIG_CONTENT` / `KILO_CONFIG_CONTENT`
(the whole config, with hooks `--session … --agent …`) and `*_DISABLE_AUTOUPDATE` go on to
an agent started from its shell with `LADO_AGENT_ENV=inherit` (the tests), and to an
`opencode` or `kilo` the agent runs itself: that nested CLI's plugin would report hooks as
the outer agent.
Wanted: drop the OpenCode family's agent variables as Claude Code's are, with a unit test in
test_tmux / agent_env.
Found: 2026-10-05, review of feature/opencode-provider (Found on the way).

## `lado doctor` looks for the agent CLIs on its own PATH, not the agents'

Size: M. Why here: onboarding: the UI suggests a provider whose start then fails.

`lado doctor` checks `claude`, `kilo` and `tmux` with `shutil.which` in its caller's
environment, while agents now run with their login shell's PATH (`agent_env.resolve`); a
CLI found by one may be missing for the other. The UI's New session window shows the same
check (`GET /api/providers`, `doctor.provider_status` with the server's PATH), so it can
offer a provider whose start then fails with "not on the agents' PATH", or the other way.
Since there is no default provider, the window's suggestion (`FolderInfo.provider`,
`runtime.suggested_provider` with the server's `shutil.which`) has the same gap: it may
suggest "the only one installed" that the agents' PATH lacks, or none where `lado start`
(which looks on the agents' PATH) would choose one; the start then refuses loudly.
Wanted: doctor looks the agent CLIs up on the resolved environment's PATH too and says
where they differ.
Found: 2026-10-04, fix/agent-env; the UI's case in feature/launch; the suggestion's in
feature/no-default-provider.

## The Flows tab loads every note of the session

Size: M. Why here: 1.7 MB and growing; the UI is the current stage 7.

`GET /api/sessions/{name}/notes` returns all notes of all runs of the session with their
bodies: 1.7 MB for session `lado` on 0.18.0, and it only grows, as messages did before
feature/chat-paging.
Wanted: notes in windows with a cursor, as the chat's messages (`live.ts`
`watchMessages`), loaded per run or by pages.
Found: 2026-10-05, feature/chat-paging (design).

## Activity loads every run event of a session at once

Size: M. Why here: the same as the notes above, for run events.

The Activity feed (Layout task) loads `GET …/events` whole on each reset, and the store
keeps them all. A long session (dozens of runs) makes every reconnect load and re-render all
of it, while the human looks at the last screen.
Wanted: the latest N with "load earlier" (`?before=<id>&limit=`), or a window the feed asks
for as it scrolls; the store's lists keep only what was loaded.
Update (2026-10-06, backlog revision): messages are paged since feature/chat-paging (86ae3cc:
`MessagePage`, `watchMessages` in `web/src/live.ts`); run events are not (`live.ts` loads
`getRunEvents` whole).
Found: 2026-10-03, implement of feature/ui-layout.

## `lado forget` can leave two loops for one session name

Size: S. Why here: two loops for one session; loop.py has no fstat check.

`lado forget` deletes the lock file while the stopped session's loop may still sleep (up to
INTERVAL). A new session of the same name started within that time locks a new file (another
inode); the old loop wakes, sees a running session and goes on: two loops. Wanted: each pass
checks that the held file is still the one at the path (os.fstat vs os.stat) and exits if not.
Found: 2026-10-02, review of run fix/session-loop.

## Agents may be asked to read kit files outside their allowed folders

Size: S/M (S to check, M to fix). Why here: a permission dialog stops the agent in mode default.

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

## A failed `_add_agent` in spawn_worker leaves the worktree and branch

Size: S. Why here: a spawn that fails after `git worktree add` leaves a worktree, a branch or a `starting` row behind; the rollback added in fix/tmux-missing-rollback does not cover these steps yet.

In `runtime.spawn_worker` the `git worktree add` and `_add_agent` calls stand before the
`try` whose `_undo` rolls back. If `state.add_agent` fails (two spawns of one name racing past
the `taken` check, a locked database), the worktree `lado/<s>/<name>` and its branch stay, and
the next unnamed spawn picks `-2`; if `add_event` fails after `add_agent`, an agent row stays
`starting`.
Wanted: these steps run under the same `_undo`, so the rollback covers everything the spawn did.
Found: 2026-10-06, review of fix/tmux-missing-rollback.

## An agent can stay `starting` with no hook and no reason

Size: M. Why here: a dialog LADO does not foresee holds the agent silently, as the trust dialog did.

LADO foresees only what a provider's `first_hook_blocker` reads (Claude Code's folder
trust). Before its first hook Claude Code may show other dialogs too: its first run and
login, the confirmation of bypassPermissions, the approval of the servers in a project's
`.mcp.json` (not checked on 2.1.291). Then the agent stays `starting` with no
`status_reason`, and messages wait.
Wanted: a neutral check in the core: an agent `starting` longer than N seconds with no hook
at all gets a `status_reason` that says to look at its window (`lado attach`, the UI's
terminal).
Found: 2026-10-06, architect's review of feature/trust-dialog.

## Flaky: a Claude live worker's window closes before its first hook

Size: S. Why here: a live-test flake whose cause is unknown; the evidence has no screen of it.

`make test-live PROVIDER=claude`, `test_worker_does_a_task_reports_and_gets_a_message`: w1
(haiku, bypassPermissions, in a worktree of the trusted live repo) was spawned at 19:51:47
and its window closed by 19:51:51 with no hook at all (`ended: its window closed without a
session-end hook`). The same launch by hand ran, and the rerun passed. The evidence keeps no
screen of a window that is gone, so why the CLI exited is not known.
Wanted: the evidence keeps a closed agent window's last screen (e.g. tmux `remain-on-exit`
in live tests, related to "Keep a crashed agent's last output"), and the cause is found.
Found: 2026-10-06, live tests of run feature/trust-dialog.

## Kilo and OpenCode agents are not resumed after a transient API error

Size: S/M. Why here: a Kilo or OpenCode worker whose turn ends on an overloaded API stays
idle until the supervisor acts, where a Claude agent is resumed by LADO.
The plugin passes only the error's class name and message (`APIError`, `UnknownError`), so
an overloaded server and a refused key look alike, and the opencode_family provider never
sets `Event.transient`. Which errors reach `session.error` at all is not checked: OpenCode
may retry retryable requests itself.
Wanted: check by hand which errors of Kilo and OpenCode end a turn, and mark the ones that
pass by themselves `Event.transient` in the provider (e.g. by the APIError's status code).
Found: 2026-10-07, design of run feature/turn-resume.
Seen again 2026-10-07 in the OpenCode live test (verify of fix/integration-fix2): w1's turn
ended twice on `UnknownError: ... [503] Upstream error from Nvidia: Service temporarily
overloaded`, not resumed; passed the third time. The live test cannot tell a model outage
from a LADO failure.
Again at the release of 0.29.0 (2026-10-08): `test_an_agent_sees_the_image_the_human_attaches[opencode]`
failed twice in a row on `[503] Upstream error from Nvidia: Service temporarily overloaded`
after colour.png; released on the human's decision (no provider change in 0.29.0).

## A message typed again before its hook confirms it runs twice

Size: M. Why here: in the product the retry rule runs a non-idempotent command twice when
only the confirmation is late, not the delivery. It showed as flaky integration tests: 13
failures in 21 parallel runs (1 in 11 on a quiet machine, 7 in 8 under load). Under
`-n auto` the prompt-submit hook took 0.18 s at p50 and 0.6 s at p99, longer than the
layer's first `LADO_RETRY_DELAYS` step then (0.5 s): the sweep typed the message again
before the hook confirmed it, and the fake agent ran it twice (duplicated inputs, a second
`flow_start`, a second advance opening gate #2).
The test half is done (run fix/integration-fix1): the layer's first retry step is 2 s, and
tests keep the fake agent busy with `pause` and a release by the test instead of `sleep 1`.
Wanted (product): a design note on "typed twice beats never" for non-idempotent tools
(flow_start, flow_advance) when only the confirmation is late, e.g. a real agent on a
loaded machine whose hook takes longer than the first 15 s delay.
Found: 2026-10-07, read-only analysis of the integration tests (integ-analysis); outputs
kept in .lado/briefs/integ-analysis/FLAKE-*.out (local, uncommitted).

## Flaky: integration test of a finished worker waits for a hook that never comes

Size: S. Why here: it turned CI red on a release commit.
`tests/integration/test_agent_liveness.py::test_finishing_a_worker_tells_no_one_it_stopped`
failed once in CI on Python 3.10 (`Failed: timed out after 30s waiting for w1's hook`; the
events show w1 `finished merged` before it); 104 passed locally on 3.10.
Wanted: the test waits for what the finish guarantees, not for a hook of a worker that is
being killed.
Found: 2026-10-08, CI of the release commit c165eee (0.28.0).

## Other users of the machine can read LADO_HOME

Size: M. Why here: every message, task, note and artifact of every session is readable by
the machine's other local users; the human decided to do it after the argv fix.
`~/.lado` is made with mode 755, `lado.db` and `lado.db-wal` 644, `artifacts/` 755, and the
agents' config folders (`mcp.json`, `settings.json`, `prompt.md`, `role.md`) 755/644. On
macOS the home folder is 750 with group `staff`, which every local user is in. Only
`server-token`, `server.log` and `env.json` are 600.
Wanted: LADO makes `LADO_HOME` with mode 700 and tightens an existing one by default;
`lado doctor` warns about modes wider than 700, and for a `LADO_HOME` set by hand only
warns.
Found: 2026-10-08, design of feature/argv-prompt.

# P2: when convenient

## The commands of a kit's MCP servers are not checked before a start

Size: S. Why here: a kit whose MCP server runs through `uvx` or `npx` gets an agent without
that server when the command is missing, and nobody hears of it until a tool call.

`expects.commands` (0.30) is checked on the agents' PATH at start, resume and spawn
(`runtime._check_commands`), but an agent's MCP server command (`mcp.command[0]` in its
frontmatter) is not: the agent's CLI only fails to connect it. The command is in the kit
already, so the kit's author should not have to list it again in `expects.commands` (the
README says to, for now).
Wanted: the same check (`kits.missing_commands`, the same error) also takes the first word
of each MCP server's command of the agents a launch starts, not only `expects.commands`.
Found: 2026-10-08, run feature/expects-commands (architect's review).

## No way to start a session whose expected command is missing

Size: S. Why here: no case yet; the human chose no flag in the first version.

A kit's `expects.commands` refuses a start, resume or spawn while a command is not on the
agents' PATH. A command that exists only inside a container the agent enters, or that the
agent installs itself, cannot be declared then.
Wanted: when such a case comes, a flag (e.g. `lado start --skip-commands`) that starts
anyway and says loudly which commands are missing.
Found: 2026-10-08, run feature/expects-commands (design, Q4).

## A message keeps no run: the chat cannot say which run an agent writes for

Size: M. Why here: the chat's rows show only the agent's name; with several runs at once the
human cannot tell which run a message belongs to (the mockup of feature/chat-look had it).

`MessageInfo` has no run, and the run cannot be taken from `AgentInfo.run`: agent names are
used again (a finished worker's name is free for the next one), so today's agent may not be
the one that wrote an old message.
Wanted: the run of the sender stored with each message when it is queued (a column), served
in `MessageInfo`, and shown muted in the row's head (`FeedRow`'s `aside`).
Found: 2026-10-07, run feature/chat-look (design, architect's review).

## The Launch window's `.chip` rule restyles the team's chips

Size: S. Why here: the team's chips do not look as designed (30 px pills); no function is
lost.

`web/src/styles.css` has two global `.chip` rules: the team's (line ~1540: 30 px high,
radius 15 px, gap 7 px, `--panel` ground) and, later in the file, the kit chips of the
Launch and Kits forms (line ~2351: 26 px, radius 6 px, gap 2 px, `--raised` ground, used by
`Kits.tsx`). The later one wins for every property it sets, so the team's chips in Activity
are 26 px, square-cornered, with the dot and name 2 px apart (`w1worker` in the screenshot of
`test_a_runs_worker_is_a_compact_chip_in_the_runs_frame_which_links_to_flows`).
Wanted: each kind of chip its own class or a scoped selector (e.g. `.kits-box .chip`), and
the team's chips as `docs/design/ui.md` (Activity) and the mockups draw them.
Found: 2026-10-07, run feature/activity-team (implement).

## LADO's own processes take the agent's PYTHONPATH and other PYTHON* variables

Size: S. Why here: LADO's hooks, `lado mcp` and the MCP secrets wrapper run with the agent's
environment, the user's login shell; a `PYTHONPATH` there (also a relative one such as `.`,
made absolute against the agent's cwd at startup) or `PYTHONSTARTUP`-like variables reach
LADO's Python, so a module on that path can still replace one LADO imports.

`interpreter.run_module` keeps the cwd off `sys.path` but keeps PYTHONPATH and the user site
on purpose (a LADO installed with `pip install --user` or found by PYTHONPATH must still run).
Wanted: decide whether LADO's processes drop the agent's `PYTHON*` variables and pass only
what LADO's own install needs (e.g. `-E` with the install's paths given explicitly), with a
test.
Found: 2026-10-07, fix/no-cwd-imports.

## One search for every tab of a session

Size: M. Why here: the human's wish (2026-10-07); today only the Flows overview has a search
in the tab bar, and Agents keeps its own search above its list.

The session's tab bar has a magnifier at its right end (`Find` in Sessions.tsx), shown for
the tabs in `FINDS`, now only the Flows overview, writing the address's `?find=`.
Wanted: one search for Flows, Agents, Activity and Artifacts in that same place and
parameter: each tab gets an entry in `FINDS` and reads `?find=`, and Agents' ListPage drops
its own search field.
Found: 2026-10-07, feature/flows-list-states (design).

## Keep a crashed agent's last output

Size: M. Why here: decided with the human (feature/agent-liveness, 2026-10-06): the window of an agent that ended by itself closes as before.

When an agent's CLI crashes, its window closes with it, so what it printed last (the
error, a stack trace) is lost; `lado ls` only says "its window closed without a
session-end hook".
Wanted: keep the last screen of a window whose process ended by itself (e.g. tmux
`remain-on-exit` with a `pane-died` hook that saves it to the agent's config folder, then
closes the window), on top of the session loop's window check, and show it with the reason.
Found: 2026-10-06, design of feature/agent-liveness.

## An OpenCode or Kilo error with no idle after it is taken for the next turn's

Size: S. Why here: a false "turn ended on an error" line, rare.

The plugin keeps a `session.error` until the session's next `session.idle` (or
`session.compacted`). Kilo 7.8.3 and OpenCode 1.18.34 also publish `session.error` without
an idle after it, e.g. when a `promptAsync` fails (the plugin's own hand-over of the queue)
or a subagent tool's agent is not found; the next normal turn end then carries that error.
Wanted: an error only goes with the idle that ends the turn it happened in (e.g. dropped at
the session's next `busy` status), checked on both CLIs.
Found: 2026-10-06, feature/agent-liveness (read in their bundles).

## A spawn's undo kills the worker's window before it forgets the worker

Size: S. Why here: a spawn that fails after its window opened could tell the supervisor "w1 stopped (its CLI exited)" about a worker that never ran.

`runtime.spawn_worker`'s undo closes the window first, then forgets the worker. A CLI that
runs its session-end hook when killed (Claude Code does) then finds the agent still there
and `agent_ended` reports it, unlike `close_worker` and `stop_session`, which now write
their intent first.
Wanted: the undo forgets the worker before it kills the window, as the finish does.
Found: 2026-10-06, feature/agent-liveness.

## A window renamed by hand reads as its agent's end

Size: S. Why here: the session loop finds an agent's window only by its name.

`allow-rename off` keeps programs from renaming an agent's window, but a human's
`tmux rename-window` on LADO's server still does: after two loop passes the agent is
marked stopped ("its window closed without a session-end hook") though it runs, and
messages can no longer be typed into it.
Wanted: find an agent's window by a label of its own (`@lado-agent=<name>`, set atomically
with the window), or refuse a rename.
Found: 2026-10-06, feature/agent-liveness.

## A stopped agent's page offers Write and Open terminal

Size: S. Why here: more agents end up `stopped` now (feature/agent-liveness), and both actions fail for them.

On the Agents tab, an agent in `stopped` (its process ended by itself) still has "Write to
<agent>" with its composer and "Open terminal", though a message to it is refused ("no
running agent") and it has no window.
Wanted: for a stopped agent the composer and Open terminal are off or hidden, with a hint
that Finish… comes next.
Found: 2026-10-06, review of feature/agent-liveness.

## Flaky vitest: Launch's taken name of a running session

Size: S. Why here: it fails `make check` under load.

`web/src/Launch.test.tsx`, "a taken name of a running session of this folder offers to open
it, not to resume it": under heavy load (load average 27) `findByRole("alert")` does not see
the answer within its default timeout and `make check` fails; a rerun with no change passes.
Wanted: the test does not depend on the machine's speed (an explicit timeout, or waiting
for the mocked fetch).
Found: 2026-10-06, review of feature/agent-liveness.
Again 2026-10-07, fix/check-sequential, in `make web` of a `make check`: its sibling "a taken
name is offered to resume when the session is of this folder" (`Unable to find
role="alert"`); the rerun passed.

## `tmux.window_names` splits window names at spaces

Size: S. Why here: the same split `list_windows` had, fixed there in feature/agent-liveness.

`tmux.window_names` (used by `kill_window` and the UI terminal's check) splits tmux's list
on any whitespace, so a window the human named `w1 notes` on LADO's server reads as a window
`w1`: `kill_window` then tries a window that is not there, and the terminal check takes a
gone agent's window for present.
Wanted: split by lines, as `list_windows` does.
Found: 2026-10-06, review fix of feature/agent-liveness.

## A kit's lint problems are seen only by `lado kits check`

Size: S. Why here: the user never learns of an endless loop in a flow.

`kits.lint` (hardcoded paths, and now the flow graph rules: traps, unbounded cycles, needs
that never come before) runs only in `lado kits check`. `lado kits add` / `update` (whose
`Install` already carries `warnings`), `lado start` and the UI's Kits page do not show them,
so the user of an installed kit never learns that one of its flows can loop forever.
Wanted: show `kits.lint` and `kits.warnings` lines at add/update, at start (stderr) and on
the Kits page, from the same two calls.
Found: 2026-10-06, design of the flow graph checks.

## Flaky: Kilo live flow test, the passive supervisor acts on its own

Size: S. Why here: a live-test flake, not in CI.

`make test-live PROVIDER=kilo`, `test_a_flow_run_moves_on_when_its_worker_reports[kilo]`
on `kilo/kilo-auto/free` failed twice in three runs: the supervisor, whose role says to do
nothing, once called `finish_worker(name="w1", discard=true)` after the run ended ("agent w1
is gone"), once spawned its own worker `worker` for the step before the test's w1 (the run's
move was by `worker`). The third run passed. The free model does not keep to the passive
role when LADO's messages ("step needs a worker", "run ended") reach it.
Also on OpenCode: `test_worker_does_a_task_reports_and_gets_a_message[opencode]` on
`opencode/nemotron-3-ultra-free` failed once in two runs (2026-10-06, feature/agent-liveness):
the supervisor merged w1's branch and called `finish_worker(name="w1")` before the test's
check of the human's message ("agent w1 is gone"); the rerun passed.
Again on OpenCode (2026-10-08, release 0.28.0): the same test failed the same way, and
`test_an_agent_sees_the_image_the_human_attaches[opencode]` timed out with w1 busy for 120 s
("waiting for w1 to be idle"); the rerun passed (the image test skipped: the model takes
no images).
Again on Kilo (2026-10-06, feature/trust-dialog): the supervisor spawned `worker` for the
step besides w1, so finishing w1 kept the run's worktree; the rerun passed. The same day on
Claude Code (haiku): the passive supervisor spawned `worker`, which advanced the run instead
of w1; the rerun passed.
Also on Claude Code (2.1.291, haiku; 2026-10-06, feature/delivery):
`test_a_flow_run_moves_on_when_its_worker_reports[claude]`, the supervisor got "step step
needs a worker" at once (it was idle) and spawned `worker` for the run besides the test's
w1, so finishing w1 kept the worktree (`assert not os.path.exists(run.worktree)`); the
rerun passed. In the next round (load average ~135 just before) all three failed at once
and passed on the rerun: Kilo's supervisor spawned `worker` and cancelled the run,
OpenCode's spawned `worker` for the flow and merged and finished w1 during the follow-up.
On 2026-10-07 (run feature/turn-resume) OpenCode's supervisor merged and finished w1 during
the follow-up in two runs in a row ("agent w1 is gone"); the third run passed.
Again on 2026-10-07 (run fix/test-timers): Kilo's supervisor finished w1 before the human's
message (the rerun passed); OpenCode failed three runs in a row, a different way each
time: w1 committed `flow.txt` with "live flow test" instead of "OK"; the supervisor spawned
`worker` besides w1, so finishing w1 kept the run's worktree; the supervisor called
`finish_worker(name="w1", discard=true)` before the human's message.
Again on 2026-10-07 (run fix/integration-fix2): Kilo's supervisor merged w1's branch and
called `finish_worker(name="w1")` before w1 answered the human ("agent w1 is gone").
Again at the 0.25.0 release check (2026-10-07, f2b4c78): OpenCode's supervisor merged w1's
branch and called `finish_worker(name="w1")` after w1 answered the human ("agent w1 is gone");
the rerun passed.
Again at the 0.26.0 release check (2026-10-08, e9ba5fa): OpenCode's passive supervisor
spawned `worker` for the run besides w1 twice in a row (finishing w1 kept the worktree; the
second time `worker`'s turn ended on the model's "tokens to keep ... greater than the
context length" and the supervisor cancelled the run); the second rerun passed.
Again on 2026-10-08 (verify of feature/expects-commands): OpenCode's passive supervisor
spawned `worker` for the run besides w1, so finishing w1 kept the worktree; the rerun
passed. In that rerun `test_an_agent_sees_the_image_the_human_attaches[opencode]` timed out
with w1 busy for 120 s again; the next run skipped it as expected (the model takes no images).
Wanted: a live supervisor that cannot act (e.g. no spawn/finish tools for the test's passive
role, or the test tolerates and names it), so the test checks LADO, not the model.
Found: 2026-10-05, live tests of run feature/opencode-provider.
Seen with Claude too, 2026-10-07 (verify of fix/integration-fix2):
test_a_flow_run_moves_on_when_its_worker_reports[claude] failed on `assert not
os.path.exists(run.worktree)` after finish_worker(w1): the passive supervisor (haiku) called
spawn_worker for the run on its own, and that worker keeps the worktree; passed on rerun.
Wanted also: the test does not depend on the supervisor not spawning (deny it spawn_worker
in the live kit, or tolerate extra workers).
Again on 2026-10-07 (verify of fix/merge-origin-main): OpenCode's supervisor merged w1's
branch and called `finish_worker(name="w1")` while the test waited for w1's reply to the
human ("agent w1 is gone", tests/live/test_live.py:162); the rerun passed.

## Flaky: Kilo live test does not see the resume line on the supervisor's screen

Size: S. Why here: a live-test flake, not in CI.

`make test-live PROVIDER=kilo`, `test_worker_does_a_task_reports_and_gets_a_message[kilo]`
timed out after 120 s "waiting for the supervisor to take the resume message": the
supervisor got `session resumed: 0 open runs`, answered the human and was idle, but the
line `[from lado] session resumed: 0 open runs` was not on its captured screen (Kilo's TUI
had scrolled it away). Passed on the rerun with no change. Again on 2026-10-07 (live tests
of run feature/turn-resume): the message was delivered, the rerun passed. Again on
2026-10-07 (run fix/integration-fix2): delivered, supervisor busy; the next run passed.
Wanted: the test checks that the supervisor took the message by its delivery (state), not
by the screen.
Found: 2026-10-06, `make test-live` on main before the 0.22.0 release.

## UI unit tests depend on the process's locale and nothing guards it

Size: S. Why here: it has already turned CI red.

`day()` and the clock in `web/src/ChatText.tsx` format with `toLocale*([], …)`; CI runs in
en-US, local machines in other locales (en_NZ, ru). A test with a date written in one format
passes locally and fails in CI, as the chat's "Start of session" tests did on 6a5c694 ("2 Oct"
here, "Oct 2" in CI).
Wanted: vitest run in `make web` (or CI) also under a second locale, e.g.
`LC_ALL=ru_RU.UTF-8`, so such a test fails locally.
Found: 2026-10-05, review of fix/chat-start-day-tz.

## A running session loop keeps the old code after an upgrade

Size: S. Why here: the cheap part is that `lado stop` waits for `loop.wait_stopped` (only update does now, cli.py:518).

After upgrading LADO without a schema change, a running loop goes on with the old code until
`lado stop`; `lado doctor` and `lado ls` do not show it. Low priority.
Found: 2026-10-02, review of run fix/session-loop.
Update (2026-10-05, feature/self-update): not after `lado update`, which stops each session
and waits for its loop to end (`loop.wait_stopped`) before installing. An upgrade by hand
still leaves it, and plain `lado stop` does not wait for the loop: a quick `lado start`
after it can meet the old loop for up to `loop.INTERVAL`.

## A terminal viewer outlives a UI server that is killed

Size: S. Why here: leftover viewer sessions until the next server start or stop.

A viewer tmux session (lado/terminal.py) cannot be made with `destroy-unattached on`: tmux
destroys an unattached session at once, before its client attaches. So when the UI server is
killed (SIGKILL, a crash), its viewers stay and keep the agents' windows linked, until the
next server start or `lado stop` removes them by their labels. Meanwhile `lado ls` and tmux
show extra `lado-view-*` sessions.
Wanted: viewers go with their server: set `destroy-unattached` once the client is attached,
or have `lado ls` and the session loop remove viewers whose server is not running.
Found: 2026-10-03, implement of feature/ui-agent-terminal.

## `lado ui` fails while another server is just starting

Size: S. Why here: a narrow race at start (server/run.py:292-300).

`server/run.py` `wait_ready` treats any early exit of the server it started as a failure.
When two `lado ui` run at once, or `lado ui` right after `lado server`, the lock is held but
server.json not yet written; `lado ui` starts its own server, which exits at once ("a LADO
server already runs"), and `lado ui` reports "the LADO server ended as it started" although
the first server is ready a moment later. Wanted: on an early exit of its own process, check
whether the lock is held and, if so, keep waiting until the timeout.
Found: 2026-10-03, review of run feature/ui-skeleton (M-3).

## `lado update` by hand suggests a pip that may not be there

Size: S. Why here: a wrong hint for a manual upgrade (cli.py:491).

For an install it does not upgrade itself, `lado update` prints `<prefix>/bin/pip install
lado==X`. A venv made by uv (also a uv tool install of a working copy) has no pip, and for a
working copy that command would replace it with the PyPI release.
Wanted: the hint follows what was found: a uv tool or pipx install not from an index: update
the working copy yourself (git pull), then restart the sessions; a venv without pip:
`uv pip install --python <prefix>/bin/python lado==X`; only a venv with pip: `<prefix>/bin/pip`.
Found: 2026-10-05, second review of feature/self-update.

## The New session window does not say who will lead the session

Size: M. Why here: the human learns who leads only after the start.

`lado start` and `lado kits show` print `lead: ...` and warn about each kit supervisor that
is not used; the New session window shows neither before Start, so the human learns only
after the start (or not at all) that LADO's built-in supervisor leads.
Wanted: the window shows the lead line and the warnings for the chosen kits and Switch off
items (an endpoint over `kits.resolve`), before Start.
The start's answer (`Started`) carries `lead` and `warnings` since feature/trust-dialog;
the session's page shows the warnings after the start, the lead nowhere yet.
Found: 2026-10-04, design of feature/without-at-kit.

## The human cannot cancel a run whose flow cannot be read

Size: S. Why here: after the upgrade to 0.27 an open run of a flow with `needs` is such a run.

A run whose flow snapshot cannot be read (`runs.SnapshotError`; also an open run of LADO
0.26's `needs` after schema 23) moves only by the supervisor's `flow_cancel`: `lado
flow-set` and `lado answer` refuse, and the UI has no cancel. The human has to ask the
supervisor, which may itself be down.
Wanted: the human cancels a run from the CLI (`lado cancel <session> <run>`) or the run's
page in the UI, through the same core function as `flow_cancel`.
Found: 2026-10-08, feature/flow-inputs (design, Q8).

## Finishing a worker in a stopped session says "no worker"

Size: S. Why here: a misleading text (runtime.py:616-630).

`lado finish <stopped session> w1` (and the UI's `POST …/agents/w1/finish`) answers
`no worker "w1"; workers: none`: `runtime.finish_worker` does not ask
`runtime.running_session`, and `lado stop` has forgotten the agents already.
Wanted: the same refusal as the other commands in a stopped session (`session "s" is
stopped; …`), which says what to do.
Found: 2026-10-04, feature/agents-tab (implement).

## The API's `core` helper turns only LadoError into a 400

Size: S. Why here: a core refusal reaches the UI as a 500 without its reason (server/app.py:93-98).

`server/app.py` `core()` and the session endpoints caught `runtime.LadoError` only, so a
`kits.KitError` from the core (a kit not found or invalid at `POST /api/sessions`) was a 500
without its reason. Fixed for `POST /api/sessions` and resume in feature/kit-manifest-v2;
`core()` still lets any other core error type through as a 500.
Wanted: one error type for what the core refuses (or `core()` and the endpoints map each
known one to 400), so no refusal reaches the UI as a 500.
Found: 2026-10-04, feature/kit-manifest-v2 (implement).

## A gate's answer copies the note before the gate into its own

Size: S. Why here: since `reads` replaced `needs` (feature/flow-inputs) nothing shows it
twice; the copy is only text where a reference would do.

A gate keeps the id of the note that led to it (`gates.note_id`, schema 22). The answer's
note still copies that note into its body ("Note before the gate: ..."), as text: the next
step gets it without the note's attachments.
Wanted: the answer keeps a reference to the note before the gate (the gate's `note_id`)
instead of a copy, and the next step is shown that note with its artifacts.
Found: 2026-10-02, run fix/gate-needs and its review; narrowed 2026-10-08,
feature/flow-inputs.

## Two starts of a session whose tmux server died can stop each other

Size: M. Why here: the race window is small.

`start_session` stops a session whose tmux server is gone (`stopped_at` unset, no tmux
session) before it takes it over. Two `lado start` of that name at once both see it so: the
first stops it, resumes it and launches its supervisor; the second then stops that running
session again, forgetting its agents, and takes it over in turn. The window is small.
Wanted: stopping a left-over session and taking it over as one step that only one start wins.
Found: 2026-10-02, run fix/resume-settings.

## A login shell that starts tmux from its startup files breaks the agents' environment

Size: S. Why here: only docs and a doctor hint; the error is already loud.

Startup files that start or attach tmux when `$TMUX` is unset (`[ -z "$TMUX" ] && exec tmux`,
oh-my-zsh's tmux plugin with autostart) make `$SHELL -ilc` fail without a terminal, so every
`lado start` and spawn stops with the shell's error. The error is loud and names
`LADO_AGENT_ENV=inherit`, but does not say why.
Wanted: the docs and `lado doctor`'s hint name this case and how to guard it in the rc file
(for example, skip the autostart when the shell is not interactive on a terminal).
Found: 2026-10-04, review of fix/agent-env.

## `lado stop` kills agents without a graceful exit

Size: M. Why here: agents lose their turn at a stop, but nothing breaks.

`lado stop` (and Stop in the UI) kills the session's tmux windows at once. An agent CLI
gets no chance to end its turn or save its state.
Wanted: send each provider's own exit command first, wait a bounded time, then kill what
is left, and say which agents had to be killed. Seen in another orchestrator, where slow
agents were killed too early until a delay was added.
Found: 2026-10-04, design of feature/launch.

## Choose the model per agent

Size: M/L. Why here: savings and parity, but postponed until a scheme for model names is decided.

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

Size: M. Why here: stage 8 (ACP, permissions through LADO) redoes this anyway; design it there.

`--permission-mode` takes Claude Code values. Each provider declares the ones it honours
and LADO refuses the others (Kilo: default, acceptEdits, bypassPermissions, plan), but the
vocabulary is still Claude Code's, and a session has one mode for all its agents.
Wanted: a neutral LADO permission setting that each provider translates.
Found: 2026-10-01, Kilo provider review.

## Agents load the human's own global plugins, skills and settings

Size: M. Why here: reproducibility of runs; one environment-isolation topic (with fullscreen set, the UI's history breaks).

### Claude agents load the user's global Claude Code plugins

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

### OpenCode and Kilo agents load the user's global skills

Besides LADO's `skills.paths`, OpenCode 1.18.34 finds skills in `~/.claude/skills`,
`~/.agents/skills` and `~/.config/opencode/skills` (seen with `opencode debug skill`), and
Kilo probably does the same: an agent gets skills its kit never named. The switch
`OPENCODE_DISABLE_EXTERNAL_SKILLS` drops the repo's own `.claude/skills` too. Same kind of
leak as "Claude agents load the user's global Claude Code plugins".
Wanted: decide which outside skills an agent may see, and keep the others away without
touching the user's global config.
Found: 2026-10-05, design of run feature/opencode-provider.

### Agents read the human's own Claude Code settings, which change how they behave

LADO gives Claude Code its settings with `--settings`, but Claude Code still reads the
human's `~/.claude/settings.json`. With `"tui": "fullscreen"` there, every LADO agent runs
full screen (alternate screen, mouse tracking): its output is not in tmux's history, and the
UI's history layer can only say so. Hooks and permissions set there apply to agents as well.
Wanted: decide which of the human's settings an agent should get, and say so in
`lado doctor` (e.g. warn that agents run full screen), or pin what LADO depends on (the
renderer) in the agent's own settings.
Found: 2026-10-03, prototype of the history in implement of feature/ui-agent-terminal.

## A marketplace's clone has no lock: an update from the UI and the CLI at once race

Size: S/M. Why here: a race that needs two updates at once.

`marketplaces._folder` removes a clone whose origin is another address and clones again,
and `update` refreshes it in place, with no lock. The Kits page's Update all and
`lado marketplaces update` (or two UI tabs) at the same time work on the same
`LADO_HOME/marketplaces/<name>/`; one can read a half-made clone or fail on the other's
`rmtree`. The UI makes this more likely.
Wanted: an exclusive lock per marketplace clone (as the session loop's `flock`) around
clone, refresh and read.
Found: 2026-10-05, design of feature/kits-page (Found on the way).

## The git cache is never cleaned, and a moved tag is never fetched again

Size: M. Why here: only the disk grows; one cache task with the moved tags of kits and packs.

### The git cache is never cleaned

`LADO_HOME/cache` keeps a clone of every (address, tag or commit) a pack or `lado kits add`
ever fetched; `lado kits update` and `remove` leave the old clones there, since running
agents may still read them. The folder only grows.
Wanted: a `lado kits clean` (or a step of `update`/`remove`) that removes the clones no
installed kit, project kit and running session uses, and says what it removed.
Found: 2026-10-04, design of feature/kit-manifest-v2.

### A kit whose tag was moved cannot be installed again with the new content

`lado kits outdated`, `update` and `add` warn when a remote tag now points to another commit
than the clone in `LADO_HOME/cache`, but a clone there is never fetched again: the kit
stays at the old commit until someone deletes that clone by hand.
Wanted: a way to take the moved tag's new content (with the warning and a confirmation),
together with the cache cleaning above.
Found: 2026-10-05, design of feature/kit-marketplaces-core.

### A moved tag of a skill pack goes unnoticed

A kit's `dependencies.skills` pins packs by tag too, but nothing compares the cached clone
of a pack with the remote's tag, as `lado kits outdated` does for a kit.
Wanted: the same moved-tag warning for packs (next to the cache cleaning).
Found: 2026-10-05, design of feature/kit-marketplaces-core.

## `lado kits check <folder>` for a marketplace's CI

Size: M. Why here: the official marketplace needs it.

A marketplace's CI (github.com/ladohq/marketplace) has to check each listed kit: its
kit.yaml at the root, `version` equal to its tag, the name equal to the name in
`marketplace.yaml`. LADO has no command that does all of that for a folder or address.
Wanted: `lado kits check` covering those checks, for the marketplace's CI and its index.json.
Found: 2026-10-05, design of feature/kit-marketplaces-core.

## `lado update`'s installer commands are not tried against real uv and pipx

Size: M. Why here: a live test, due before the next release that changes update.

The tests run a fake installer (`LADO_UPDATE_INSTALLER`) and read hand-written receipts. That
`uv tool install lado==X` (with the receipt's `--python` and `--with`) replaces an installed
tool's version and keeps its options, and that `pipx install --force lado==X` keeps
injected packages, comes from their documentation, not from a test.
Wanted: a live test (not in CI) that installs an old LADO with uv tool and with pipx into a
temp tool dir, runs `lado update` against PyPI and checks the version and the options after.
Found: 2026-10-05, feature/self-update (implement).

## Live-test evidence lacks the CLIs' own transcripts and logs

Size: M. Why here: helps debug live flakes; nothing breaks without it.

A failed live test keeps LADO's log, hooks.log, agent configs and window screens, but not
Claude Code's transcript (~/.claude/projects/<cwd>/*.jsonl) or Kilo's session and log from its
data folder. For a flake such as a weak model calling a tool with a wrong argument, the
transcript (tool calls and their answers) matters most.
Wanted: the evidence also copies each agent's CLI transcript and logs, picked by the agent's
cwd and the test's start time; the test layer asks the provider for their location, so nothing
above providers/ learns a provider's paths.
Found: 2026-10-02, review of run fix/live-test-keeps-logs.

## Message delivery is spread over runtime, state and hooks

Size: L. Why here: one architecture task of delivery; before stage 8 (ACP) adds a channel.

The delivery rule (How agents talk) lives in `runtime.py` (post, _deliver, hand_over, sweep,
_plan), `state.py` (take_pending, sweep, seen, confirm_sent, confirm_channel) and
`hooks.py` (at a turn's end: confirm the hook-output batch, idle, hand over, sweep). Since
feature/delivery the channels are named (`messages.channel`: `typed`, `hook_output`), every
path takes the queue through `runtime.hand_over`, and the hook order is in `hooks._idle`'s
docstring; the first input (start, resume) is still taken in `runtime.start_session` with
`take_pending` as delivered. It is correct but hard to read and test as one rule. Wanted:
one module for delivery, with tests through its interface. Low priority: no bug depends on
it.
Found: 2026-10-06, architecture review and its check (session improve-architecture).

## The OpenCode-family plugin swallows the failures of its own hook commands

Size: S. Why here: a hook command that cannot start or fails leaves no trace; the agent's status or queue then waits for the sweep or the human.

`opencode_plugin.js` runs `lado hook <event>` through `run`, which resolves "" on a spawn
error or a failing process: a `session.idle` hook that cannot run hands over nothing, a
`chat.message` one confirms nothing, and nothing says why. Since feature/delivery a failed
`promptAsync` is reported with `plugin.error` (hooks.log). Wanted: `run`'s failures go
through `plugin.error` too (a spawn error, a non-zero exit with the end of its stderr),
without a loop when `plugin.error` itself cannot run.
Found: 2026-10-06, architect's review of feature/delivery.

## An open run's task cannot be amended

Size: M. Why here: a run of its own right after part 4 (Kit) of docs/design/artifacts.md
(the human's decision, 2026-10-08): it builds on artifacts, and part 3 (Flows) left it out
to keep `produces` small.

A small addition the human asks for while a run is in `implement` (feature/ui-polish:
AC-13..15) can only go to the developer as a message. The design note that the reviewer and
the merge gate get does not have it, and `lado log` does not tie it to the run. The only
other way, `lado flow-set` back to `design`, repeats the architect's review and the design
gate for a few lines.
Wanted: an addendum to an open run as an artifact, `<run>/addendum`: the supervisor writes
it, the human approves it, and every later step sees it in its step's text.
Found: 2026-10-03, feature/ui-polish.

## A step that needs a new worker is a relay through the supervisor

Size: M. Why here: works today; it only saves the supervisor a relay.

LADO asks the supervisor to start a step's worker, and the supervisor calls spawn_worker with
exactly the arguments LADO named; no decision is made.
Wanted: a flow (or kit) can say that LADO spawns the step's worker itself.
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## No way to reach a busy agent urgently

Size: M. Why here: saves time, but messages arrive at the turn's end today.

A message to a busy agent waits until its turn ends. A hint from the supervisor that would
save a worker many minutes (e.g. the known cause of a failure it is debugging) arrives only
after the worker has finished that long turn. Wanted: an "urgent" flag on send_message that
types the message into the busy agent's window at once (Claude Code and Kilo accept input
while working and handle it at the next step), with the same confirmation via prompt-submit.
Found: 2026-10-01, provider fixes task.

## Flows cannot work on another repository

Size: L. Why here: part of "Projects" (Later in ROADMAP.md).

A run's worktree and branch are always made in the session's repo, so a change to another
repo (e.g. the lado-kits kit repo while the session runs on LADO) cannot go through a flow:
it is done by a worker outside a run, with no design gate, review step or merge gate.
Wanted: `flow_start` can name the repo a run works on (a registered kit source or a path),
and the run's worktree, `make check` and merge happen there.
Found: 2026-10-02, task lado-dev architecture (kit changes in lado-kits).

## A terminal closed for good shows its reason twice

Size: S. Why here: seen on every stopped session's page.

A terminal whose socket closes for good (e.g. a stopped session) shows the reason in its
status ("closed: session "x" is stopped") and again as the error notice beside it: the
server sends an error frame and then closes with the same reason. Now that the
supervisor's tab is always shown, every stopped session's page shows it twice.
Wanted: one line with the reason (the notice left out when it repeats the close reason).
Found: 2026-10-03, UI e2e screenshots of feature/ui-polish.

## A sent batch of a busy agent that a hook ran after waits without a limit

Size: S. Why here: no loss, but the agent shows busy with an unconfirmed batch until the human types; rare.

`runtime._plan` does nothing with a sent message whose agent ran a hook after it was handed
over (`seen_at >= sent_at`) while the agent is still `busy`: no retype, no requeue, never
failed. It happens when a late async hook of the turn before (Claude Code's PostToolUse)
runs after the hand-over and the CLI did not take the text: the agent stays busy with its
batch unconfirmed until the human types in its window.
Wanted: a limit for that case too (e.g. after the last delay: failed with the notice, or
waiting with a reason), in the one rule of `_plan`.
Found: 2026-10-06, review of feature/delivery.

## The open search field in a narrow tab bar covers tabs that stay focusable

Size: S. Why here: review follow-ups of fix/flows-search-narrow, accepted as Minor.
In a narrow session column (terminals open), the open "Find a run" field lies over the
tabs: the current tab (Flows) is hidden and "Agents · 1" is cut; the covered tabs stay in
the Tab order, so Shift+Tab from the field focuses Artifacts under it with no visible ring
(WCAG 2.4.11); with text in it the field does not close on blur, so a covered tab cannot be
clicked until Esc or ×.
Wanted: while the field is open in a narrow bar, the tabs shrink to their icons (or the
field stays right of the current tab), covered tabs are `inert`, and ui.md (Flows, The
search) states the blur rule.
Found: 2026-10-07, review of fix/flows-search-narrow.

## Session head's about is a 500 for a session whose provider is no longer registered

Size: S. Why here: rare (a provider dropped from LADO, a test home's "fake"), but the head then loses its git and kit versions too.
`GET /api/sessions/{name}/about` calls `providers.get(sess.provider)` in `launch.session_about`; an unknown name raises ValueError, the endpoint answers 500, and the UI falls back to the plain line (AC-10), losing git and kit versions that do not depend on the provider.
Wanted: an unknown provider gives a `ProviderInfo` with `installed: false` and a `detail` saying so (or `provider` optional); the rest of the answer stays.
Found: 2026-10-07, feature/session-head review (Minor).
## `ask_human` asks one question, so a round of several comes to the human as plain text

Size: M. Why here: friction for the human at every design round; nothing is lost.

A design round of six questions (feature/turn-resume) went to the human as one text message,
since `ask_human` holds one question with its choices: six questions would be six cards in
a row, each answered on its own. The human asked why there were no buttons.
Wanted: one question card in the UI's chat with several questions, each with its own choices
and free answer, answered at once (an extension of `ask_human`, one message back to the agent).
Found: 2026-10-06, design of run feature/turn-resume, by the human.

## A session's history grows until `lado forget`, with no way to see or trim it

Size: M. Why here: no failure yet, but lado.db only grows (session `lado` had about 5 MB of messages on 0.18.0) and the human cannot tell how much or clean it up in bulk.

Messages, events and notes of a session stay in lado.db for good: `lado stop` and
`finish_worker` only mark undelivered messages `dropped`, and only `lado forget <session>`
deletes rows, one stopped session at a time, from the CLI. Nothing says how big lado.db or
a session's history is. Agents are not affected: a resumed supervisor gets the open runs
and their notes, never the chat, so this is storage only.
Wanted: an explicit retention the human runs, never a silent age-based delete: `lado forget`
of stopped sessions by age (e.g. `--older-than 30d`, listing what it deletes first), a
`lado doctor` line with lado.db's size and its largest sessions, and Forget for a stopped
session in the UI. Running sessions are never trimmed.
Found: 2026-10-07, the human's question in session chat-history about how the chat grows.

## Follow-ups of fix/test-timers: an empty LADO_RETRY_DELAYS, two weak tests

Size: S. Why here: review's Minor findings, nothing wrong in production.
1. `runtime.retry_delays_from` takes `value or "15,30,60"`, so `LADO_RETRY_DELAYS=""` now
   silently means the production delays (before, it failed at import); `LADO_LOOP_INTERVAL=""`
   is refused. 2. tests/integration/test_agents.py:291-292: the comment says this send's
   sweep or the loop's types the report in, but only the loop's can, so the test no longer
   covers "a send_message sweep types the due report in with the next message".
3. tests/test_loop.py `test_wait_stopped_waits_three_intervals_by_default` checks only an
   upper bound, so a timeout of 0 would pass it.
Wanted: `"15,30,60" if value is None else value` (and "" refused, with a test); the comment
fixed and the send path covered at the unit layer if it is not; a lower bound (>= 3 intervals).
Found: 2026-10-07, review of fix/test-timers.
## A stream that opens while the UI server stops can keep the stop waiting

Size: S. Why here: the stop is only slower, nothing is lost, and the window is narrow.
`feed.Hub.subscribe` checks `_closed` before `await to_thread.run_sync(self.source.last)`;
`Hub.close` does not take the lock, so when it runs during that await, the first stream
starts its `_run` task and joins `_queues` after the None was sent: it never ends, and the
stop waits uvicorn's full grace again, as before fix/server-stop-streams.
Wanted: `subscribe` checks `_closed` again after the await, before it starts the task or
adds the queue; a unit test closes the hub during that await.
Found: 2026-10-07, review of fix/server-stop-streams (Minor finding).

## Two session loops for a moment after a second `lado loop` exits

Size: S. Why here: one loop per session is a rule (`flock`); a second one, even briefly,
could sweep twice.
`tests/integration/test_session_loop.py:59` once saw 2 loop pids right after the test's
second `lado loop` returned 0, under `-n auto` load. Maybe the loop `start_session` started
was still importing (before `take_lock`) while the second took and dropped the lock, or
`pgrep -f` matched a passing process. Not explained.
Wanted: find which with that run's loop.log; if a loop can start after another one gave up
the lock, the test should wait for the lock holder, or the product should say so.
Found: 2026-10-07, read-only analysis of the integration tests (integ-analysis).

## tests/test_loop.py `_stop_after`: its docstring says `passes` holds tmux calls

Size: S. Why here: a misleading test comment (review Minor of fix/integration-fix2).
The docstring says each pass's tmux calls go to `passes`, but `passes` collects the loop's
sleeps; the tmux calls are counted in `tmux_server["calls"]`.
Wanted: the docstring says what each collects.
Found: 2026-10-07, review of fix/integration-fix2.

## Artifact cleanup can remove the content of a write in progress

Size: S. Why here: a narrow race (a `lado forget` of one session while another writes the
same content, older than an hour); the review of feature/artifacts-core rated it Minor.
`LocalStore._collect` (src/lado/artifacts_local.py) lists the orphans with their mtime
first and unlinks them later without looking again. A write of the same content in
between sets the file's mtime, commits its record and finds the file there; then the
unlink takes it, and reading that record says "content ... is missing from the store".
Wanted: `_collect` reads each file's mtime again right before its unlink and skips one
younger than `ORPHAN_AGE`, so the window shrinks to one stat and unlink.
Found: 2026-10-07, review of feature/artifacts-core.

## Flow events wrap in a narrow chat column

Size: S. Why here: the chat's flow event lines are new (feature/chat-message-text) and meant to be one line each.
In a narrow column (520 px or less) `.run-line` has `flex-wrap`, so the event's detail and its time wrap onto lines of their own.
Wanted: the detail cut with an ellipsis on the event's line and the time kept on it, as the chat's other quiet lines do.
Found: 2026-10-07, review of feature/chat-message-text (Minor left open).

## Artifacts UI: three small gaps left by feature/artifacts-ui

Size: S. Why here: Minor findings of the review of feature/artifacts-ui; none misleads in normal use.
- An artifact's page with `?record=` of another artifact (web/src/ArtifactsTable.tsx,
  `useRecord`) shows that record's content under this artifact's head, name and Download.
  Wanted: a record of another artifact says "not a record of this artifact" or redirects
  to its own artifact's page.
- Closing the artifact panel (web/src/ArtifactPanel.tsx, `close`) pushes a history step,
  so Back opens it again, against the comment in `Attachments.useView`. Wanted: close with
  `replace` (or go back when the panel opened this step), so Back after a close leaves it shut.
- The content address's errors (500 for missing content, 404 from `known_record`,
  src/lado/server/app.py) carry `nosniff` but not `Content-Security-Policy: sandbox`.
  Wanted: every response of a content address carries the sandbox header, errors too.
Found: 2026-10-07, review of feature/artifacts-ui.

## An unfinished update's mark outlives the sessions resumed by hand

Size: S. Why here: harmless today, misleading later; no session is lost.
`lado update` to 0.27.0 resumed core-tracker and the UI server but not kit-lado-dev and
kit-builder; the human resumed those with `lado start`, yet `~/.lado/update.json` stays
(only `cmd_update` clears it, on full success). A later deliberate `lado stop` of one of
those sessions makes `lado ls` say "an update did not finish" again. The update's own
output, which would say why it stopped resuming, was not kept.
Wanted: the mark goes once none of its sessions is stopped (e.g. `_unfinished_update` or a
resume drops it), and `lado update` writes why a resume failed to `loop.log` too.
Found: 2026-10-08, checking the 0.27.0 update in session core-tracker.

## The web UI's main bundle is over Vite's 800 kB warning

Size: S. Why here: every `make web` warns, so the warning no longer tells anything.
`make web` prints `(!) Some chunks are larger than 800 kB after minification`: `index-*.js`
is 886.64 kB on main (gzip 251.83 kB) and 924.84 kB with remark-gfm (gzip 262.94 kB).
Wanted: split the bundle with dynamic `import()` (e.g. the Markdown renderer and the
terminal in chunks of their own), or raise `build.chunkSizeWarningLimit` on purpose.
Found: 2026-10-08, verify of feature/markdown-render.

## Images over the limits are named, not resized; more than 20 large images can break an agent

Size: M. Why here: a retina screenshot is often over 2000 px a side, and the API's tighter rule turns a working agent into one whose every turn fails (architecture review of feature/chat-attachments, Minor 6).
`read_artifact` shows an image only up to `artifacts.IMAGE_LIMIT` (3.75 MB) and
`IMAGE_MAX_SIDE` (8000 px); a larger one gives its facts and "not shown". Claude's API also
refuses any image over 2000 px a side once a request holds more than 20 images, and an
agent's whole conversation is sent with each request: after about 20 large screenshots
read, every later turn of that agent may fail.
Wanted: LADO scales an image down (before the upload in the browser, or in
`read_artifact`) to fit the limits, and past 20 images in an agent's conversation to
2000 px a side; or it says so before the agent reads one more.
Found: 2026-10-08, design and architecture review of feature/chat-attachments.

## Files only in the composer: not in gate answers, question answers or the New session window

Size: M. Why here: the upload has no recipient on purpose, so these reuse it (feature/chat-attachments, Out of scope).
The human attaches files only to a message from the composer. Answering a gate or an
agent's question, or starting a session with a task, takes text only.
Wanted: the same chips and upload in a gate's comment, a question's free answer and the New
session window's task; the files attached to the answer's note or message.
Found: 2026-10-08, design of feature/chat-attachments.

## An upload whose message failed stays in the session

Size: S. Why here: Send uploads first, then sends; a message refused after the uploads (the agent stopped meanwhile) leaves artifacts no message refers to (feature/chat-attachments, Out of scope).
They show in the Artifacts tab, attached by nobody, and live until `lado forget`; the next
Send of the same file returns them, so nothing is stored twice.
Wanted: with deleting artifacts (none yet), a way to remove the human's uploads that no
message or note refers to.
Found: 2026-10-08, design of feature/chat-attachments.

## A run's worker cannot list the session's artifacts

Size: S. Why here: it reads them as `/<name>`, but only when it is told the name (feature/chat-attachments).
`list_artifacts()` gives a run's worker its run's scope and `list_artifacts(run=...)` another
run's; there is no way to ask for the session's scope, so a run's worker learns a session
artifact's name only from a message, a step or a note.
Wanted: `list_artifacts` takes the session's scope too (e.g. `run="/"`), when a kit needs
it.
Found: 2026-10-08, implement of feature/chat-attachments.

## OpenCode's live image check never runs on the default model

Size: S. Why here: the image path of OpenCode (and Kilo) has no live proof.
`test_an_agent_sees_the_image_the_human_attaches[opencode]` always skips with `Cannot read
image`: the default free model `opencode/nemotron-3-ultra-free` takes no images. So only
Claude Code proves that an attached image reaches the model.
Wanted: a free OpenCode model with image input for that test (e.g. a separate
`LADO_LIVE_OPENCODE_IMAGE_MODEL`), or the gap named in AGENTS.md (Testing, Live e2e).
Found: 2026-10-08, verify of feature/chat-attachments.

# P3: maybe never

## Code artifacts have no syntax highlighting

Size: S. Why here: the human's decision (2026-10-07, run feature/artifacts-ui): text and
code read well with line numbers; a highlighter is a dependency and a bundle of grammars.

The viewer (`web/src/ArtifactView.tsx`, `Text`) shows text and code (`text/x-python`,
`text/typescript`, `application/json`, ...) as plain lines with their numbers.
Wanted, if it ever matters: highlighting by the media type, loaded only for a code
artifact, in both themes' colours (tokens.css).
Found: 2026-10-07, run feature/artifacts-ui (design).

## The chat's day dividers say "Today" and "Yesterday" as of their last render

Size: S. Why here: only a tab left open across midnight shows it, until its next render.

`dayName()` (`web/src/ChatText.tsx`) names a day by the time it is called. The chat's day
dividers (`Chat.tsx`, `DayDivider`) and the Flows History headings call it while rendering,
so in a tab open across midnight "Today" stays on yesterday's entries until the feed brings
something that renders the chat again.
Wanted: a render at local midnight (a timer, or a clock in the live store), if it ever
matters.
Found: 2026-10-07, run feature/chat-look (design).

## A server endpoint that writes makes lado.db when there is none

Size: S. Why here: only before the first session; the file it makes is a fresh, correct one.

The server never makes lado.db for a read (`database()` says there is none), but an endpoint
whose only guard is `Depends(database)` and that calls the core goes through
`state.connect()`, which makes the file: e.g. `POST /api/kits/plan` (`kits.plan_add` reads
`state.get_kit`). Meant for `POST /api/sessions`; for the others not decided.
Wanted: decide per endpoint whether it may make the database, and test it.
Found: 2026-10-06, design of run feature/readonly-db (confirmed by reading `plan_kit`).

## "idle" while a background command runs

Size: M. Why here: postponed as low impact.

A reviewer's turn ended while its `make check` ran in the background; LADO showed it idle for
80 s (and could have pasted a message into it) until the command finished and woke it. The end
of a turn is not the end of the agent's work.
Wanted: find out whether Claude Code and Kilo signal a running or finished background task;
use it for the status, or document the limit.
Postponed (2026-10-02): low impact. Flows move on flow_advance, not on idle; a message
pasted meanwhile most likely starts a normal turn (not verified); typing into waiting agents is
already blocked. The reference orchestrator does not handle it either (screen-based idle).
Found: 2026-10-02, first flow run `fix/resume-stopped`.

## The running-session check sees one tmux socket

Size: S. Why here: an edge case.

`runtime.migrate_if_safe` asks `tmux.has_session` on the current process's `LADO_TMUX_SOCKET`.
A session started in the same LADO_HOME with another socket counts as not running, so the
database is migrated under it.
Wanted: store the socket with the session and check that one (or say in the refusal and the
docs that the check sees one socket). An edge case.
Found: 2026-10-02, review of run fix/migration-guard.
Update (2026-10-05, feature/self-update): `lado update` sees only the sessions on the current
`LADO_TMUX_SOCKET` too: it does not stop a session on another socket and the new version
migrates the database under it. Its plan says which socket it sees.
Update (2026-10-06, feature/readonly-db): `lado stop --all` has the same limit (it kills only the sessions
on its socket, then migrates) and says which socket it sees.

## Skill packs written for Claude Code plugins break under LADO

Size: M. Why here: needs a decision first.

`ui-ux-pro-max` (nextlevelbuilder/ui-ux-pro-max-skill) calls its scripts as
`python "${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max/scripts/search.py"`. Outside a
Claude Code plugin `CLAUDE_PLUGIN_ROOT` is unset, so the skill cannot find its scripts and
data when LADO links it from a source, for Claude and Kilo agents alike. Other plugin-born
packs may do the same. Wanted: decide whether LADO supports such packs (e.g. set
`CLAUDE_PLUGIN_ROOT`-like variables per skill, or a source option that maps them to the
source folder) or `lado kits check` warns about unknown `${...}` variables in a skill.
Found: 2026-10-03, choosing UI skills for the lado-dev kit.

## Workers get ask_human and send_message(to="human") with no LADO-level hint

Size: S. Why here: the human has decided already; revisit when more kits are in use.

LADO 0.12 gives every agent `ask_human`, and `send_message`'s docstring offers `to="human"` to
workers too. By the human's decision (2026-10-03) the core does not restrict who writes to
the human; kit roles do (lado-dev 0.6.0 tells its workers to route questions through the
supervisor). A kit that forgets it lets a worker's question reach the human past the
supervisor. Wanted: revisit with more kits in use: a worker-specific hint in LADO's own
worker instructions, or tools only for the supervisor unless a role asks for them.
Found: 2026-10-03, review of lado-dev 0.6.0.

## A tooltip can miss its keyboard focus after a click

Size: S. Why here: a minor UI glitch.

`web/src/Tooltip.tsx` sets `pressed` on pointer down and clears it only on focus. A click
on a button that already has focus (or in Safari, where a click does not focus a button)
leaves `pressed` set, so the next keyboard focus shows no tooltip once.
Wanted: clear `pressed` on pointer up / click, or test `:focus-visible` on the target.
Found: 2026-10-03, review of feature/ui-polish (Minor).

## Terminals.tsx and Team.tsx import each other

Size: S. Why here: works today; do it together with the Flows.tsx / Agents.tsx cycle below.

Terminals imports `SUPERVISOR`, `StatusDot` and `AgentTip` from Team, and Team imports
`useOpenTerminal` / `useShownTerminal` from Terminals. It works while each is used only
inside functions; a module-level use breaks on load order.
Wanted: move the shared agent pieces (`SUPERVISOR`, `StatusDot`, `AgentTip`) into a module
of their own (e.g. `agents.tsx`).
Found: 2026-10-03, review of feature/ui-polish (Minor).

## Flows.tsx and Agents.tsx import each other

Size: S. Why here: works today; together with the cycle above.

`Flows.tsx` imports `AgentName` from `Agents.tsx` and `Agents.tsx` imports `isOpen` from
`Flows.tsx`. It works (both are used only while rendering), but each new tab with a list
of runs or agents would join the cycle.
Wanted: the helpers about runs and agents shared by the tabs in a module of their own.
Found: 2026-10-04, feature/flows-list (review).

## The sources.yaml migration hint suggests refs that `lado kits add` now refuses

Size: S. Why here: only users of an old LADO's sources.yaml see it.

`kits.migration_hint` prints `lado kits add <url>@<ref>` with the ref of an older LADO's
sources.yaml, often a commit or `v1`; from 0.20.0 a kit is added only by a tag vX.Y.Z, and
the repository may hold several kits in `kits/<name>/`, which is refused too.
Wanted: the hint says `lado kits add <url>` (the latest release) and names the
one-kit-per-repository rule, or the hint is dropped with sources.yaml support.
Found: 2026-10-05, feature/kit-marketplaces-core (implement).

## The Stop popover does not give focus back to its icon

Size: S. Why here: a minor keyboard-focus glitch.

Esc, Cancel or a click outside closes the session's Stop popover (`SessionControl.tsx`,
`onClose={close}`) and the focus goes to the page's body; the list row's menu gives it back
to its button (`back()` in `SessionRowMenu`). It was so on main before the icons too.
Wanted: closing the popover without a stop puts the focus back on the Stop icon.
Found: 2026-10-05, feature/session-controls (review).

## An open menu or popover stays where it opened when the page scrolls

Size: S. Why here: a minor UI glitch (Menu.tsx:11-28).

`useBelow` (`web/src/Menu.tsx`) places a row's menu or the Stop popover once, when it opens;
scrolling the session list or the session's page, or resizing the window, leaves it at its
old place, away from its button. The row's menu did so on main before.
Wanted: the place computed again on scroll and resize, or the menu closed on scroll.
Found: 2026-10-05, feature/session-controls (review).

## Two texts for one rule: a kit that needs a newer LADO

Size: S. Why here: two wordings of one refusal (kits.py:761 and :1124).

`lado kits add ./folder` and `lado start` (through `kits.load`, `_load_dependencies`) say
`<file>: kit "k" needs LADO >=99.0, this is X; upgrade LADO`; `lado kits add <git>` and
`lado kits check` (through `kits.load_release`) say `k 1.2.0 needs LADO 99.0, this is X;
upgrade LADO`.
Wanted: one text from one function for every path.
Found: 2026-10-05, fix/kits-check-tag (developer's concern, reviewer's Found on the way).

## No test that the wide session strip scrolls with its buttons fixed

Size: S. Why here: works today, checked by hand.

`tests/ui/test_sessions_strip.py` checks the collapsed session list on a wide window with
two sessions only: nothing checks that its column of icons (`.strip-icons`) scrolls while
"Sessions" and "+" stay put (feature/sessions-list-collapse, AC-2). It works now (checked
by hand: 40 icons, `overflow-y: auto`), but a change to `min-height: 0` or the grid would
go unnoticed. Wanted: the e2e test checks `overflow-y` of `.strip-icons`, or fills the strip
and checks that the buttons keep their place.
Found: 2026-10-05, review of feature/sessions-list-collapse (Minor 1).

## The OpenCode family's turn end depends on `session.idle`, which OpenCode calls transitional

Size: S. Why here: watch the releases; nothing to do until the event goes.

The plugin (`opencode_plugin.js`) takes the end of a turn from the bus event `session.idle`.
OpenCode 1.18 marks that event as transitional, next to `session.status` (status `idle`).
If OpenCode, or Kilo after it, drops `session.idle`, agents never go idle and get no
queued messages at turn end.
Wanted: watch the releases; when `session.idle` goes, take the turn end from
`session.status` in the plugin, for both CLIs, with a JS test.
Found: 2026-10-05, design of run feature/opencode-provider.

## The end of a session whose tmux died is recorded only at its next stop or resume

Size: S. Why here: the recorded time is already close enough.

`session_gone` (the run time's end for a session whose tmux died) is written only when
`lado stop` or a resume finds the tmux session gone, at the last sign of life it can find
then (its agents' latest hook, else its latest event). The session loop (`loop.py`) sees
the tmux session go at once, but only exits.
Wanted: the loop records `session_gone` when it sees the tmux session gone, at a closer
time, through the same `state` function (once per session, not after a stop).
Found: 2026-10-05, run feature/session-head (design).

## Events have no index by session

Size: S. Why here: leave it until it gets slow.

`SessionInfo` reads each session's span events (`state.span_events`: `events` by session and
kind) at every build, in REST and in the change feed; `events` has no index on `session`,
so each read walks the whole table.
Wanted: when that becomes noticeable, an index `events(session, kind)` (a schema change, its
own task).
Found: 2026-10-05, run feature/session-head (design).

## A kit's skill count differs between Available and Installed

Size: S. Why here: a cosmetic mismatch.

Available counts a kit's skills from `index.json`, only its own (lado-dev: 1); Installed and
the plans count its packs' skills too (`models._skill_names`: 71). The same kit shows two
numbers.
Wanted: one count everywhere, e.g. "N skills (M from packs)", or index.json gives the total.
Found: 2026-10-05, design of feature/kits-page-polish.

## Update… stays on a kit a check found up to date

Size: S. Why here: a cosmetic label; the window already answers.

After Check for updates says a kit has no newer version, its row still offers Update…; the
window now answers briefly, but the button promises an update.
Wanted: after a check, such a kit's button says what it does (e.g. "Versions…").
Found: 2026-10-05, design of feature/kits-page-polish.

## The UI scrolls sideways on a phone-wide screen

Size: M. Why here: a desktop app; the phone comes second.

At a 420 px wide viewport the Kits page (the rail and the page) is wider than the screen:
a full-page screenshot is 476 px wide, and the Marketplaces block runs past the right edge.
Wanted: no horizontal page scroll at phone width (the rail collapses, the page fits).
Found: 2026-10-05, UI e2e screenshot update-narrow of feature/kits-page-polish.

## The Kits up-to-date window drops the plan's other notes

Size: S. Why here: hypothetical: no such notes exist today.

`UpdateDialog` (`web/src/Kits.tsx`, the `plan.current` branch) rewords `kits.current_line`
as its heading and shows no `plan.notes`. Today a current plan has only that line, but a
note the core adds there later (a moved tag, the sessions that use the kit) would not show.
Wanted: the server gives the current line apart from the other notes, and the window shows
those; or the window shows `plan.notes` under its heading.
Found: 2026-10-05, review of feature/kits-page-polish.

## The database schema still names `claude` as the provider column's default

Size: S. Why here: waits for a migration that touches these tables anyway.

`sessions.provider` and `agents.provider` are `NOT NULL DEFAULT 'claude'` in `state.SCHEMA`
and in the migration that added them. Since there is no default provider in the code
(feature/no-default-provider), every insert gives the provider, so a fresh database never
uses that default; it only filled the rows of sessions made before providers existed, which
did run Claude Code. Wanted: when a migration touches these tables anyway, drop the default
from the schema of new databases (keep the migration's fill for old rows).
Found: 2026-10-05, feature/no-default-provider.

## The popup integration test fails with an empty HOME

Size: S/M. Why here: does not get in the way in CI.

`HOME=<empty dir> uv run pytest -m integration -n0 tests/integration/test_flow_runs.py -k
popup` times out waiting for the popup (the worker's `flow_advance` fails with
`Error executing tool flow_advance`); with the usual HOME it passes. Not the git identity:
with `GIT_CONFIG_GLOBAL=/dev/null` and `user.useConfigOnly=true` it passes too.
Wanted: find what the gate's popup reads from HOME, and either isolate it in the tests or
say so in AGENTS.md.
Found: 2026-10-06, fix/ci-git-identity, checking the tests without a global git identity.

## A start or resume from the UI that tmux fails is a 500 without its cause

Size: S. Why here: the UI hides the real cause (a missing tmux) the CLI now names.

`POST /api/sessions` and `POST /api/sessions/{name}/resume` (server/app.py) turn only
`LadoError` and `KitError` into a 400 with the reason; a `tmux.TmuxError` (`TmuxMissing`:
tmux not on the server's PATH) from `start_session` is a 500 "Internal Server Error", and
the notes of a failed undo (`runtime._undo`, also on a `LadoError`) are not in the 400 either.
Wanted: the API answers 400 with the error and its notes, as the CLI prints them.
Found: 2026-10-06, fix/tmux-missing-rollback.

## Live flow test fails while the passive supervisor has a kit MCP server (Kilo)

Size: S. Why here: a live-test flake, not in CI.

With an MCP server of its own on the passive supervisor (the token server of
`check_mcp_token`), `test_a_flow_run_moves_on_when_its_worker_reports[kilo]` failed 3 times
of 3 (kilo-auto/free): the supervisor spawned `worker` for the run besides w1, so finishing
w1 kept the worktree; without that server it passed at once. Maybe chance (see the passive
supervisors entry above), maybe the server changes what Kilo's model does. The token check
now runs only in `test_worker_does_a_task_reports_and_gets_a_message`.
Wanted: know whether a kit MCP server makes the passive supervisor act; then the check can
go in both scenarios.
Found: 2026-10-06, run feature/mcp-secrets, `make test-live PROVIDER=kilo`.
## Session tabs are cut in a narrow column with no sign they scroll

With the terminal column open (window 1280 px), the session's tab bar overflows: Artifacts
shows half ("A"). `.tab-bar` of the session has `overflow-x: auto`, but no visible scrollbar
(macOS) and no wheel scrolling as the terminal tabs have. It overflowed before
feature/session-tabs too; Mono and the icons made it wider.
Wanted: the session's tabs always whole, or plainly scrollable: a thin bar and the wheel as
for the terminals, or shorter labels / icons only in a narrow column.
Found: 2026-10-06, review of feature/session-tabs (`session-light.png`).

## A Claude agent whose turn the human interrupts stays busy

Size: S. Why here: checked, Claude Code has no hook for it; recheck on a new Claude Code.

Claude Code runs no hook when the human interrupts a turn with Esc (checked by hand with
2.1.292, model haiku, every hook event of the binary registered): while text streams,
nothing after `UserPromptSubmit` (no `Stop`, `StopFailure` or `Notification`); while a tool
runs, no `PostToolUse`, `PostToolUseFailure` or `Stop` (`PostToolUseFailure`'s
`is_interrupt` never reaches a hook: its hooks run under the turn's abort signal, which Esc
aborts); on a permission dialog, nothing after `PermissionRequest` (and `Notification`
permission_prompt), no `PermissionDenied`. So the agent stays `busy`, or `waiting` after a
`PermissionRequest`, and its queue waits until the human's next prompt in its window, whose
`Stop` ends the turn and hands the queue over. Kilo and OpenCode report the Esc
(`MessageAbortedError` with `session.idle`) as a turn's end.
Rejected (the human's decision): reading the transcript's "[Request interrupted by user]"
marker, an undocumented text format that cannot tell whether the human goes on typing.
Wanted: when a Claude Code release adds a hook for an interrupt, close the turn with
`TURN_END` as for any other.
Found: 2026-10-06, architect's review of feature/agent-liveness; checked 2026-10-06.

## An artifact's records cannot be compared

Size: M. Why here: no real need yet; the human sees only an artifact's latest record (docs/design/artifacts.md, Left out).
Every write of an artifact is kept as a record, but neither the UI nor the agents' tools show
the records as versions or what changed between two of them; an attachment only says that
its artifact changed since.
Wanted: the records of an artifact as its versions, and a diff of two text records, in the
UI (from an attachment marked changed, at a gate) and as a tool for agents.
Found: 2026-10-07, design of feature/artifacts (the human's decision: later).

## Artifacts end with their session

Size: L. Why here: comes with projects (ROADMAP, Later); a session's artifacts are enough until then (docs/design/artifacts.md, Left out).
`lado forget` removes a session's artifacts with it, so a design or report cannot outlive
the session that wrote it, nor belong to a project or a tracker task.
Wanted: a project scope for artifacts (one more scope, one migration), kept across sessions.
Found: 2026-10-07, design of feature/artifacts (the human's decision: later).

## Artifacts have no retention policy

Size: M. Why here: no failure yet; content stays until `lado forget` and `lado doctor` shows its size (docs/design/artifacts.md, Lifecycle).
Every record's content is kept as long as its session (up to 25 MB a record), so an agent
that rewrites a large artifact often fills `LADO_HOME/artifacts`.
Wanted: an explicit retention the human runs (e.g. keep the latest N records of an artifact
and the ones attachments refer to), never a silent delete; together with the history entry
"A session's history grows until `lado forget`".
Found: 2026-10-07, design of feature/artifacts (the human's decision: later).

## Image previews only under the human's own messages

Size: S. Why here: the human asked for previews of their own files first (feature/chat-attachments, Out of scope).
An image an agent attaches (a screenshot it took, a mockup's picture) shows in the chat as a
chip only; the human opens it to see it.
Wanted: the same preview (at most 240 × 180) under an agent's message to the human, if it
proves useful.
Found: 2026-10-08, design of feature/chat-attachments.

## Agents read no PDF or other binary

Size: M. Why here: no kit needs it yet; providers differ in what a tool may return (feature/chat-attachments, Out of scope).
`read_artifact` gives text and PNG, JPEG, GIF and WebP images; a PDF, an archive or any
other binary the human attaches is only its name and size to the agent (the composer's
crossed-out eye says so).
Wanted: a PDF's pages as images (or its text), within the image limits; an archive's list
of files.
Found: 2026-10-08, design of feature/chat-attachments.
