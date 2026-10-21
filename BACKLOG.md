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
test_the_humans_tmux_session_is_left_as_it_was (and a history test removed since),
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
`make test-ui` take one lock per machine (`scripts/check_lock.py`, docs/testing.md). Still open:
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
- `src/Launch.test.tsx` > "a refused start shows the core's whole reason and keeps the
  window": `Unable to find role="alert"` (1257 ms) in one `make web` at load average about
  8 (2026-10-10, fix/md-tables-wrap, a CSS-only change); 561 of 561 passed on the next run.
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

### UI e2e test of the status marks reads the Team buttons before they render

Size: S.

`tests/ui/test_status_marks.py::test_busy_and_background_are_green_and_pulse_and_background_is_half_filled`
failed in 3 of 3 full `make test-ui` runs (2 on feature/session-start-tool, 1 on main at
f9d3739) with `ValueError: not enough values to unpack (expected 2, got 0)` at
`supervisor, w1 = team.get_by_role("button").all()`, and passed alone: Playwright's `.all()`
does not wait, so the list is empty while the Team group has not rendered its buttons.
Wanted: wait for the two buttons first (`expect(team.get_by_role("button")).to_have_count(2)`).
Found: 2026-10-10, implement step of feature/session-start-tool.
Again on 2026-10-11 (verify of feature/live-cloud-matrix, c8aca85): the same `ValueError` in
`make check`; passed on both reruns.
Again on 2026-10-11 (verify of feature/artifact-panel-width, 211f4c8): the same `ValueError`
in `make test-ui`; passed on its first rerun alone.
Again on 2026-10-11 (verify of feature/team-run-frames, 5f0841e): the same `ValueError` in
`make check`; passed on its first rerun. Third time today: worth fixing soon.

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

## Two first opens of lado.db at once can leave it half made

Size: S. Why here: a fresh LADO_HOME refused for good, with "stop all LADO sessions and
delete it" as the only way out.

`state.connect` makes a missing lado.db with `executescript(SCHEMA)` and then sets
`user_version`, with no lock around it: a second connection in that moment sees tables
with version 0 and raises "incompatible schema (version 0)", and a second maker fails on
a table that exists, so the file stays at version 0 with tables. Seen in CI (run
38770622361, container amd64, `test_recreated_with_another_owner_keeps_the_home`): the
container start resume thread of LAD-74 opened lado.db while the server made it; LAD-74
now keeps that thread from opening a missing one, but any two processes that first open
a new LADO_HOME at once (a hook and the CLI, two CLIs) can still do it.
Wanted: make the schema in one `BEGIN IMMEDIATE` transaction, the version checked again
inside it, so the second maker waits and finds it made.
Found: 2026-10-15, feature/lad-74-container-session-restart.

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
the outer agent. Under `LADO_AGENT_ENV=inherit` they also reach the agents of a session an
OpenCode or Kilo supervisor starts with `start_session` (its `lado mcp` has them; LADO's
own identity variables are dropped since feature/session-start-tool).
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

## Integration flake: `test_unmerged_worker_is_finished_only_with_discard` reads w1 busy

Size: S. Why here: a red CI on a release commit with no real error.
CI on e7c8773 (Python 3.13, `-n auto`) failed at tests/integration/test_agents.py:598,
`assert state.get_agent(SESSION, "w1").status == state.IDLE` -> `'busy' == 'idle'`; the
rerun of the failed jobs passed with no change. The test reads w1's status once, right after
the supervisor's refused finish, while w1 may still be in a turn.
Wanted: the test waits for w1 to be idle (as the other status checks do) instead of reading
it once.
Found: 2026-10-09, CI of the 0.31.0 release (run 37887140737).

## A Codex agent whose turn ends on a model or API error stays busy

Size: M. Why here: a Codex worker whose model fails (a 400, a 500, a server that is down)
looks busy forever; neither the supervisor nor the human is told.
Codex CLI 0.162 runs no hook at all for such a turn (400 and 500 tried; a refused connection
it retries forever). Only the rollout at the hooks' `transcript_path` has it: a
`task_complete` with an `error`. The human's decision for v1: a working model is the user's
responsibility, and LADO reads no transcript.
Wanted: a later event source for Codex turn errors (the rollout, or app-server events over
ACP, stage 8), mapped to a turn's end with `Event.error`.
Found: 2026-10-09, design of run feature/codex-provider.
Seen live (2026-10-09, verify of feature/codex-provider): in the image test, w1 on
`qwen3-coder:30b`, a model with no image input, stayed busy for 3 min after the human's
PNG. The test now skips Codex models whose `ollama show` lists no `vision`.
Since feature/hook-output-retry (2026-10-11) a batch a Codex Stop hook printed waits for its
turn's end, up to `runtime.HOOK_OUTPUT_BACKSTOP` (600 s): a turn that goes on from it and
ends on such an error is typed into after 10 minutes, no longer after 15 s, which used to
wake it by chance. The human accepted that (decision Р3 of that run); this entry is the fix.

## Codex agents cannot log in: the user's Codex login is not carried

Size: S/M. Why here: a Codex user with an account (ChatGPT login or an API key stored by
`codex login`) gets the login screen in every agent; only a model that needs no login works.
Each Codex agent has its own CODEX_HOME, and LADO carries only the model settings from the
user's config.toml, not `auth.json` or the keyring setting.
Wanted: carry the login next to the carried settings (read only; a link or a copy with mode
600, or the keyring's setting), checked by hand with an account.
Found: 2026-10-09, design of run feature/codex-provider.

## A Claude turn that goes on from the hook's output and ends on Esc is not fingerprinted

Size: S. Why here: a read-only agent's change in that turn goes unreported (R3 of feature/read-only-roles).
`hooks.py` (the read-only fingerprint, about lines 116-127 and 209): after a `hook_output`
hand-over the baseline is reopened for the turn that goes on; Claude Code runs no hook when
the human interrupts it with Esc, so the next UserPromptSubmit replaces that baseline
without comparing it, and a change made in the interrupted turn is never reported.
Wanted: an open `continued` baseline is compared before it is replaced, only for CLIs whose
hook-output turn runs no prompt-submit hook (Claude Code, Codex; on OpenCode and Kilo it
would bring back the false "its end was not seen" line); a unit test of it.
Found: 2026-10-11, review of feature/read-only-roles (Minor 3, visits 2 and 3).

## The needs-you notification UI test can hang `make test-ui` for good

Size: S. Why here: a hang holds the machine-wide check lock until someone kills pytest.
`tests/ui/test_needs_you.py::test_a_new_question_notifies_a_hidden_tab_and_its_click_leads_to_it`
(its `notifying` fixture launches full Chromium, `channel="chromium"`) stopped the ui group of
one `make check` at 91 of 92 tests for about 14 minutes; killing that Chromium did not help,
only SIGINT to pytest ended it (`91 passed in 902.73s`). It passed in the next `make test-ui`.
Wanted: a hang becomes a failure with a traceback (timeouts on the launch and the fixture's
steps, or a pytest timeout for the ui group), and find where it hangs (launch,
`grant_permissions`, `browser.close()`).
Found: 2026-10-11, verify of feature/artifact-panel-width.

## Expanding the artifact panel on a window over 2464 px, then dragging, jumps it narrower

Size: S. Why here: a small fix in the code just merged; harmless but visible on ultrawide screens.
Expand shows the panel at the room (window − 64 px), while the edge's `bounds.max` stays 2400:
on a wider room `aria-valuenow` exceeds `aria-valuemax`, and the first pixel of a drag clamps
the start width to 2400, so the panel jumps narrower by `room − 2400` px under the pointer
(`web/src/ArtifactPanel.tsx`).
Wanted: a drag from the expanded panel starts where it is (start from `min(width, max)` or let
the expanded case's max be the room), with a vitest case.
Found: 2026-10-11, review of feature/artifact-panel-width (Minor).

## 0.34.0 went out without live tests: run them for every provider

Size: S. Why here: a released version no live test has checked.
The human decided to release 0.34.0 with no `make test-live` at all: no local model made the
Codex live tests pass (session lado-windows), and the release was blocking that work.
Wanted: `make test-live` on v0.34.0 for every provider (Claude Code with the human's yes); a
failure goes through `fix` and a patch release.
Found: 2026-10-11, release of 0.34.0 (the human's decision).

# P2: when convenient

## On a phone the expanded terminal and the menu's drawer ignore the visible part of the window

Size: S. Why here: LAD-109 sized the app by `window.visualViewport`, but the overlays
fixed to the layout viewport still reach under Safari's bottom bar or the keyboard; not a
regression, they did so before.
The expanded terminal (`.terminals.expanded`) and the drawer (`.rail[data-open]`) are
`position: fixed` against the layout viewport, so with the on-screen keyboard open or
under Safari's bottom bar their bottom can be hidden. Wanted: they take their height and
top from `--phone-height`/`--phone-top` as the app does, with a UI test on a fake
`visualViewport` (`tests/ui/test_phone.py`'s `FAKE_VIEWPORT`).
Found: 2026-10-19, review of hotfix/lad-109-phone-bottom-cut.

## On Python 3.14 and later a clone target LADO may not look into is taken for a new folder

Size: S. Why here: LADO supports any Python from 3.10 and CI tests only 3.10 and 3.13, so
the break is unseen; the clone would then fail late, inside git, with a worse message.
From Python 3.14 `Path.exists()` returns False on any `OSError`, a permission error too,
where 3.13 raised it. `clone._check_target` relies on that error for its `no_access`
refusal, so a path under a folder LADO may not enter is "a new folder". Two unit tests
fail on 3.15 (and on 3.14 by the same rule), passing on 3.13:
`tests/test_clone.py::test_a_folder_that_cannot_be_read_is_refused_not_raised` and
`tests/test_server_clones.py::test_a_folder_that_cannot_be_read_is_400_not_500`. Wanted:
the check looks with `os.stat` (or `Path.stat`) so the error stays, and CI tests the
newest Python LADO allows.
Found: 2026-10-19, fix/lad-107-agent-base-tools (a local `uv sync` took Python 3.15).

## `lado kits check` calls `${KIT_DIR}` in an MCP server's command a hardcoded path

Size: S. Why here: a kit that follows the documented form (README before 0.36, the Kits
guide) fails its own CI.
`kits.lint` checks each MCP server's `command` and `env` as `_load_mcp` stored them, with
`${KIT_DIR}` already replaced by the kit's absolute folder, so `HARDCODED_PATH` matches it:
`command: ["${KIT_DIR}/bin/db-mcp"]` gives `hardcoded path "/.../my-team/bin/db-mcp"` and
exit 1. The role's prompt is checked from the raw file and does not have the problem.
Wanted: lint the MCP servers from the raw frontmatter, as the prompt, so only a path
written into the kit is reported.
Found: 2026-10-12, build of fix/lad-16-kits-guide (checking the guide's examples).

## Kilo and OpenCode: a failed `promptAsync` waits the first retry delay

Size: S. Why here: a message LADO knows at once was not delivered waits 15 s more.
When the plugin's `promptAsync` of the turn-end output fails, it reports `plugin.error`
(`HOOK_ERROR`) at once, but the batch stays `hook_output` and is typed in only after
`RETRY_DELAYS[0]` (`runtime._plan`).
Wanted: on that `HOOK_ERROR`, make the agent's `hook_output` batch `typed` at once
(`state.output_not_taken`), so the sweep's typed rule takes it on.
Found: 2026-10-11, design of run feature/hook-output-retry.

## Claude Code's first-run screens block an agent before any hook, unseen

Size: S. Why here: on a user's fresh machine the first Claude agent looks stuck in
`starting` with no reason given.

`Provider.first_hook_blocker` (providers/claude.py) detects only the folder trust dialog.
Three more screens of Claude Code 2.1.296 come before its first hook, each seen in the smoke
test (tests/smoke/, a fresh `CLAUDE_CONFIG_DIR`) with the agent left `starting` and no
reason in `lado ls`:
- the first-run screens (theme first), while `.claude.json` has no `hasCompletedOnboarding`;
- the bypass permissions mode's disclaimer ("No, exit" / "Yes, I accept"), with
  `--permission-mode bypassPermissions` while `.claude.json` has no
  `bypassPermissionsModeAccepted` (nor `skipDangerousModePermissionPrompt` in the user's
  settings);
- "Detected a custom API key in your environment", for an `ANTHROPIC_API_KEY` whose last 20
  characters are in neither list of `customApiKeyResponses`.
The smoke answers all three ahead in its own config.
Wanted: `first_hook_blocker` names each wait, with what to do in the agent's window, as it
does for the trust dialog, with unit tests on configs without the keys.
Found: 2026-10-10, design review of feature/live-cloud-matrix (architect, Found on the way);
the three screens confirmed by the smoke test on 2026-10-11.

## A fake model server for the smoke tests

Size: M. Why here: the smoke stops at the model; a full turn (a tool call, a reply) would
cover the rest of the CLI's plumbing in CI with no model (the human's decision 5 of
feature/live-cloud-matrix).
The smoke's `fake_endpoint` (tests/smoke/conftest.py) answers every request with 401. A
server that answers with canned replies in each API's shape (Anthropic's Messages, OpenAI's
Responses for Codex, Chat Completions for OpenCode and Kilo), streaming and with tool calls,
would let the smoke run a whole turn: call `send_message` or `flow_advance`, end the turn,
take the queue at the turn's end (`hook_output`). It grows from the same fixture and the same
per-provider endpoint config.
Found: 2026-10-10, design of feature/live-cloud-matrix (decision 5).

## styles.css writes 20 selectors twice; some may style two components

Size: S. Why here: the team chips' bug came from exactly this, a later rule of one
component overriding an earlier one of another; no reported symptom yet.

`web/src/styles.css` is one global file. fix/team-chip gave each component's chips their
own classes, and `web/src/chips.test.ts` fails when a selector with `chip` in it is written
twice at the top level. Other selectors are still written twice, some far apart, e.g.
`.needs-you` (l. ~1413, ~2193), `.link-button` (~2536, ~3790), `.feed-who` (~2303, ~4740),
`.feed-label` (~4750, ~5521), `.composer` (~2150, ~3088), `.kit-problem`; some are a rule
and its later refinement on purpose, others may be two components sharing a name.
Wanted: look at each pair; give a component its own class where two share one, merge the
rest, then widen the guard in `chips.test.ts` to every top-level selector.
Found: 2026-10-10, implement of fix/team-chip (developer).

## Integration tests take a new worker's first idle as its task done

Size: S. Why here: latent flakes; one of them failed 2 of 3 Windows probe runs.
A spawned agent's session-start hook sets it idle and then hands over its queue (its task),
so `wait_status("w1", state.IDLE)` right after `spawn_worker` can return before w1 has its
task. `test_supervisor_finishes_a_merged_worker` failed on it (it dropped the task at the
finish) and now waits with `agent_helpers.unreceived` (`worker_commits`). The same wait
stays in test_agents.py (the artifact test, `test_stop_kills_agents_and_keeps_worktrees`),
test_agent_liveness.py (the human writes to a worker, finishing tells no one) and
test_flow_runs.py (`test_the_supervisor_hears_when_a_worker_ends_the_run`); none asserts on
a drop today, so they pass, but each acts on a worker that may still be about to start.
Wanted: one helper, "spawned and its task done" (nothing unreceived, then idle), used by
each.
Found: 2026-10-10, fix/flaky-finish-merged-worker.
## UI: buttons have two unrelated sizes

Size: M. Why here: looks only; every place that mixes the two classes shows two heights.
`.primary` is 32 px, radius 6; `.quiet` is 28 px, 13 px font (`web/src/styles.css`). Only
the question and gate cards share one scale, by a rule scoped to `form.answer`
(feature/question-answer); dialogs, toolbars and rows elsewhere still mix them.
Wanted: one button scale for the whole UI (docs/design/ui.md, Look), applied in one pass,
and the scoped `.answer .primary, .answer .quiet` rule dropped.
Found: 2026-10-10, design of feature/question-answer.

## Mockups: a dark sample in a light page is unreadable when `color` is inherited

Size: S. Why here: only mockup authors meet it; it cost one round of review.
In LADO's HTML viewer the frame follows the system theme; a mockup that forces
`color-scheme: dark` on a block without setting `color` there keeps the light page's ink.
Wanted: one line in the design guidance for mockups (docs/design/ui.md or the lado-dev
kit): set `color` together with `color-scheme`.
Found: 2026-10-10, design of feature/question-answer.

## `lado answer` and the popup answer only flow gates, not an agent's question

Size: M. Why here: friction; the UI answers questions, but a human in the terminal expects
`lado answer` to, e.g. for the supervisor's `Start session <name>` proposal.
An agent's `ask_human` question (`runtime.answer_question`, `dismiss_question`) can be
answered only in the UI's chat; `lado answer` lists and answers gates only, and no popup
opens for a question.
Wanted: `lado answer` lists the open questions beside the gates and answers one by a choice
or a text, through `runtime.answer_question`; maybe a popup as for a gate.
Found: 2026-10-09, design of feature/session-start-tool (the human, the architect).

## macOS: Codex with `cli_auth_credentials_store = "keyring"` is not warned about

Size: S. Why here: only a Codex user who keeps its login in the macOS keychain meets it, and
only with agents started outside the graphical session.
Codex's `keychain_login` is None: LADO does not read whether the user's Codex config keeps
the login in the keyring, so a Codex agent of a tmux server outside the graphical session
may fail to log in without LADO's warning (lado.gui_session; Claude Code is warned about).
Wanted: Codex's `keychain_login` from the carried config's `cli_auth_credentials_store`
(`keyring`, `auto`), checked by hand on a Mac over ssh; together with carrying the Codex
login (P1 above).
Found: 2026-10-10, design of run feature/macos-gui-session.

## macOS: agents after a reboot with nobody logged in to the graphical session

Size: M. Why here: a headless Mac (a build host reached by ssh) after a reboot has no
graphical domain until someone logs in; LADO only warns there (`NO_GUI`), and Claude Code's
agents work only with a token (`CLAUDE_CODE_OAUTH_TOKEN`).
Wanted: decide whether LADO should help more: e.g. say how to turn on automatic login, or
read the token from somewhere the human chooses; checked on a host after a reboot.
Found: 2026-10-10, design of run feature/macos-gui-session.

## Every Codex agent asks whether to trust a repo the user's Codex does not trust

Size: S. Why here: in such a repo each Codex agent, worker or resumed supervisor, waits for
the human at its start (`lado ls` says why), since its home is new at each launch.
LADO carries the user's own trust entry and never trusts a folder on the human's behalf; the
answer in an agent's window is lost with its home. Trusting the repo once in the user's own
Codex (`codex` in it) ends the questions.
Wanted: the human's decision whether LADO may pre-trust the session's repo for its agents
(e.g. after the first agent's answer), and how that is shown.
Found: 2026-10-09, design of run feature/codex-provider.

## A Codex approval of a command moved to a background terminal may wait until the turn ends

Size: S. Why here: such an agent shows `waiting` after the human approved.
A shell command Codex 0.162 moves to a background terminal gets PreToolUse and never
PostToolUse, which is what ends a wait (RESUMED); the turn's Stop ends it at last.
Wanted: check whether such a command can ask for approval, and if so find the event that
says it was answered.
Found: 2026-10-09, design of run feature/codex-provider.

## The live tests run every provider only under bypassPermissions

Size: S/M. Why here: a provider's default sandbox or permission mode can keep a worker from
committing (Codex's sandbox does, LADO's permission profile lifts it), and no live scenario
would see it.
Wanted: one live check per provider that a worker commits on its branch under the
provider's `default` mode (Kilo and OpenCode are untested there too).
Found: 2026-10-09, architecture review of run feature/codex-provider.

## The artifact panel's "Link copied" is cut by the window's right edge

Size: S. Why here: the human clicks Copy link and barely sees that it worked; seen with and
without the Clipboard API.

Copy link sits at the artifact panel's right edge; its note (`CopyButton`'s
`role="status"`, under the button) runs past the window's edge, where only "co" shows, and
the button's tooltip covers the rest (screenshot of
test_artifacts_tab::test_copy_link_copies_without_the_clipboard_api).
Wanted: the note stays inside the window, as the CopyField popover does (`useBelow`, 8px
from the edge), and is not hidden by the tooltip.
Found: 2026-10-09, run fix/copy-without-popover.

## The commands of a kit's MCP servers are not checked before a start

Size: S. Why here: a kit whose MCP server runs through `uvx` or `npx` gets an agent without
that server when the command is missing, and nobody hears of it until a tool call.

`expects.commands` (0.30) is checked on the agents' PATH at start, resume and spawn
(`runtime._check_commands`), but an agent's MCP server command (`mcp.command[0]` in its
frontmatter) is not: the agent's CLI only fails to connect it. The command is in the kit
already, so the kit's author should not have to list it again in `expects.commands` (the
Kits guide, docs/kits.md, says to, for now).
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

## The human cannot start a worker or cancel a run

Size: M. Why here: a run led by a read-only lead, or whose lead is gone, moves only by `lado flow-set` or waits.
`spawn_worker` and `flow_cancel` are only the supervisor's MCP tools: no `lado` command and no
UI endpoint (cli.py, app.py). A read-only lead has neither (`mcp_server.COMMAND_TOOLS`), so
LADO's messages to it can name only `lado flow-set` and `lado stop` for a step that needs a
worker (runs.py, `_waits_for_human`). The entry above is the cancel of an unreadable run.
Wanted: the human starts a run's worker and cancels a run from the CLI and the UI, through the
same core as the tools; the read-only lead's texts then name them, in one place.
Found: 2026-10-11, architecture review of feature/stable-local-live.

## Codex agents have Codex's own worktree tools

Size: S. Why here: a worker can make a git worktree LADO does not know of.
Codex 0.162's `worktrees` feature (on by default) gives the TUI an MCP namespace
`codex_worktrees` with `create_worktree`, which makes a managed git worktree of the repository
(seen in the request's tools, feature/stable-local-live). LADO switches it off only for a
read-only agent; a worker may still make one besides its LADO worktree.
Wanted: `features.worktrees = false` for every Codex agent, as `multi_agent`, if no agent needs it.
Found: 2026-10-11, implement of feature/stable-local-live (hand check of Codex's tools).

## Live: qwen3.5 answers a tool call as text now and then

Size: S. Why here: one of seven OpenCode image runs failed on it.
In `test_an_agent_sees_the_image_the_human_attaches[opencode]` on LM Studio's
qwen/qwen3.5-35b-a3b, w1's two turns ended at once with the tool's name as plain text
(`read_messages`, 3 tokens; then `read_artifact(name="colour-….png")`, finish `stop`) where it
should have called it; the request had LADO's tools (14,360 input tokens, as in the passing
runs, whose same requests got real tool calls, 5 of 5 recorded through a proxy). The model's,
not LADO's (feature/stable-local-live, implement, item 9c).
Wanted: know how often it hits the live suite (verify's 3 runs per provider), and whether a
model setting (LM Studio's tool-call parsing, thinking on) avoids it.
Found: 2026-10-11, implement of feature/stable-local-live.
Verify of that run (d15a64f) on LM Studio: OpenCode red in 3 of 3 runs (image 3 times, worker
once, flow once), Codex 1 of 3 (flow), each the same: `read_messages`, `[call read_messages]`,
`call send_message(...)` or `ACK` written as text, finish `stop`; OpenCode's session store
shows each failed turn's input as large as the turns of the same session that did call the
tools (14,354-14,560 tokens). Hence the human's switch of verify to a gateway with
qwen3.6-35b-a3b (`LADO_LIVE_ENDPOINT`, design v5); LM Studio stays the default setup.

## The lead answers the human's message to a worker

Size: S. Why here: a lead that does a worker's job answers the human twice, and loads the model twice.
When the human writes to an agent, the lead gets the one-line copy `human wrote to <agent>: ...`
"for your information". The live tests' read-only passive supervisor on qwen3.5 takes it as
its task: it reads the attached image with read_artifact and sends `red` to the human itself
(6 of 6 recorded OpenCode image runs in implement, once in verify), while w1 answers too.
Wanted: the copy says plainly that the agent answers and the lead must not, or the live test
fails on a lead's message to the human that answers the human's message to w1.
Found: 2026-10-11, implement and verify of feature/stable-local-live.

## A read-only lead is told the run waits while the test starts its worker

Size: S. Why here: the lead tells the human something false in the live flow test.
At `runs.start` the read-only lead gets "step step needs a worker. Your role is read-only:
you cannot start a worker. The run waits at step until the human moves it on with `lado
flow-set ...`", and in the same second the live test starts w1 itself with `runs.spawn_worker`,
a path no human has (BACKLOG "The human cannot start a worker or cancel a run"). The message
is dropped only if still pending; once handed over, the lead told the human `Flow requires
human action - cannot spawn workers in read-only mode` (Codex, verify run 3).
Wanted: once the human can start a worker, the text names that way and the live test uses it;
until then the test could start the run's worker before the lead's turn, or tolerate it.
Found: 2026-10-11, verify of feature/stable-local-live.

## Test tmux servers leave their socket files behind

Size: S. Why here: about 100 stale sockets pile up in the tmux folder.
`/private/tmp/tmux-501/` holds ~100 `lado-test-*` socket files of earlier runs with no server
behind them: `kill_tmux_server` ends the server but leaves its socket.
Wanted: a test's teardown removes its socket file after the server is gone.
Found: 2026-10-11, verify of feature/stable-local-live.

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

Size: M. Why here: reproducibility of runs; one environment-isolation topic.

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

### OpenCode, Kilo and Codex agents load the user's global skills

Besides LADO's `skills.paths`, OpenCode 1.18.34 finds skills in `~/.claude/skills`,
`~/.agents/skills` and `~/.config/opencode/skills` (seen with `opencode debug skill`), and
Kilo probably does the same: an agent gets skills its kit never named. The switch
`OPENCODE_DISABLE_EXTERNAL_SKILLS` drops the repo's own `.claude/skills` too. Same kind of
leak as "Claude agents load the user's global Claude Code plugins".
Codex CLI 0.162 reads `$HOME/.agents/skills` whatever its CODEX_HOME is (checked by hand,
2026-10-09, design of run feature/codex-provider): its agents get the user's skills too.
Wanted: decide which outside skills an agent may see, and keep the others away without
touching the user's global config.
Found: 2026-10-05, design of run feature/opencode-provider.

### Agents read the human's own Claude Code settings, which change how they behave

LADO gives Claude Code its settings with `--settings`, but Claude Code still reads the
human's `~/.claude/settings.json`: its `"tui"` picks the renderer (Claude Code 2.1.296 runs
full screen by default anyway, docs/design/ui.md, What each CLI does), and hooks and
permissions set there apply to agents as well.
Wanted: decide which of the human's settings an agent should get, and say so in
`lado doctor`, or pin what LADO depends on in the agent's own settings.
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

The delivery rule (docs/design/agents.md) lives in `runtime.py` (post, _deliver, hand_over, sweep,
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

Size: L. Why here: comes with sessions over several repositories of a project, which the projects model leaves for after the projects epic (docs/design/projects.md, Not now).

A run's worktree and branch are always made in the session's repo, so a change to another
repo (e.g. the lado-kits kit repo while the session runs on LADO) cannot go through a flow:
it is done by a worker outside a run, with no design gate, review step or merge gate.
Wanted: `flow_start` can name the repo a run works on (a registered kit source or a path),
and the run's worktree, `make check` and merge happen there.
Found: 2026-10-02, task lado-dev architecture (kit changes in lado-kits).

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

## A traceback in hooks.log when the tmux server is gone at an agent's end

Size: S. Why here: noise in hooks.log, no lost work.
When a live test kills the tmux server, OpenCode's dispose hook runs `agent_ended` →
`_tell_lead` → `hand_over` → `tmux.send_text`, which fails with `TmuxError: error
connecting to /private/tmp/tmux-501/lado-test-… (No such file or directory)`, and the hook
writes the whole traceback to hooks.log.
Wanted: a tmux server that is gone during the hand-over at an agent's end is no error with
a traceback; the message just stays queued.
Found: 2026-10-08, verify of feature/argv-prompt (OpenCode flow live test's hooks.log).

## CHANGELOG.md conflicts when parallel branches add a line

Size: S. Why here: each such merge goes back to implement for a one-line fix.
Branches append lines under the same `## X.Y.Z (unreleased)` heading, so merging main into a
run's branch conflicts there (feature/argv-prompt and main both added one to 0.30.1).
`.gitattributes` has `merge=union` for BACKLOG.md only.
Wanted: CHANGELOG.md merges such additions without a conflict (e.g. `merge=union` too,
checking that a release's dated heading still merges right).
Found: 2026-10-08, merge of main into feature/argv-prompt.

## The supervisor is told twice when a worker crashes before its first hook

Size: S. Why here: a duplicate notice, no lost state; left open by the review of feature/argv-prompt.
A worker whose CLI ends before its first hook, with its first input as a message from `lado`,
gets two lines to the supervisor: the `agent_ended` notice and a `_report_failure` "not
delivered" line for that input (`runtime.py`, `agent_ended` / `_report_failure`).
Wanted: one line per crash, saying why the worker stopped.
Found: 2026-10-08, review of feature/argv-prompt (Minor, not fixed on the branch).

## Docs disagree on who takes an agent's queue

Size: S. Why here: docs only; left open by the review of feature/argv-prompt.
docs/design/agents.md ("A queue is taken only so, also an agent's first input", and the
paragraph on the first input) and the docstring of `state.take_pending` say different things
about whether the first input is taken through `runtime.hand_over`.
Wanted: one wording, matching the code, in both places.
Found: 2026-10-08, review of feature/argv-prompt (Minor, not fixed on the branch).

## A turn's end clears an open dialog's wait

Size: M. Why here: pre-existing, but background subagents make it common.

A background subagent can open a permission dialog (`PermissionRequest`, the agent
`waiting`) while the main turn still runs. That turn's `Stop` then sets the agent idle (now
`background`) and drops `waiting_for`, though the dialog is still on screen, and
`hand_over` types the queue into it: the dialog takes the text, and the retries follow.
Wanted: tell a subagent's `PermissionRequest` from the main agent's (does the payload carry
`agent_id`? check by hand), and keep the wait across the turn's end.
Found: 2026-10-09, architecture review of feature/background-status.

## Background subagents' hooks keep `seen_at` fresh

Size: S. Why here: pre-existing; a swallowed message still fails loudly.

Every hook calls `state.seen`, a background subagent's async `PostToolUse` too, so
`runtime._plan`'s "no hook since the paste: type it again" rarely holds for an agent whose
subagents work. A typed message a dialog swallowed then goes to `failed` after its delays
instead of being typed again.
Wanted: count only the main agent's hooks as a sign that it took input (the payload's
`agent_id`, if it has one), or another sign of a swallowed paste.
Found: 2026-10-09, architecture review of feature/background-status.

## A worker can move any branch of the repo, main too

Size: M. Why here: the human accepted the risk for now (2026-10-09); no agent has done it.
A worker's worktree shares the repo's git common dir, and its sandbox lets it write there:
Codex's `default` profile opens the git folders but their hooks and config (else it cannot
commit), and Claude Code, Kilo and OpenCode do not restrict git at all. So a worker can
`git update-ref`, reset or push any branch, `main` included, not only `lado/<session>/<name>`.
Wanted: a worker's writes to refs other than its own branch refused or at least seen (e.g. a
check of main's tip before a run's merge, or a hook on ref updates).
Found: 2026-10-09, review of feature/codex-provider (the reviewer's open question).

## Codex agents call `read_mcp_resource` instead of LADO's tools

Size: S. Why here: a live-test flake with a cause in what Codex offers the model.
At the release of 0.33.0 (f9d3739) `test_worker_does_a_task_reports_and_gets_a_message[codex]`
on `qwen3-coder:30b` failed once (`timed out after 60s waiting for w1 to be idle`): the
supervisor called Codex's `read_mcp_resource` (`unknown MCP server 'default'`, then
`resources/read failed for lado (artifact://…, message://…)`) instead of `read_messages` and
`read_artifact`; the rerun passed.
Wanted: find whether LADO's MCP server lists resources Codex then offers, and either serve
them or list none, so the model takes LADO's tools.
Found: 2026-10-10, release of 0.33.0.

## `lado ui` says "Opening" when no browser opened

Size: S. Why here: a small silent drop, seen in the WSL audit.
`cli.py` ignores `webbrowser.open`'s False result (WSL, a server without a browser) and prints
`Opening <url>` anyway.
Wanted: on False, say no browser opened and to open the link by hand.
Found: 2026-10-10, read-only Windows/WSL audit (session lado-windows).

## `make browser` installs Chromium without its system libraries

Size: S. Why here: a fresh Ubuntu (or WSL) cannot run `make test-ui`/`make check`.
`make browser` runs `playwright install chromium` without `--with-deps`, which CI adds; on a
fresh machine Chromium does not launch (libnss3 and others missing).
Wanted: say so in AGENTS.md's Commands, or a target that adds `--with-deps` on Linux.
Found: 2026-10-10, read-only Windows/WSL audit (session lado-windows).

## LADO does not install on Windows ARM64: cryptography builds from source

Size: S. Why here: seen in the first Windows probe run; native Windows is not supported yet.
On `windows-11-arm` (run 38003385714, `native.log`) `uv tool install .` fails: uv picks no
wheel of `cryptography` 50.0.2 (from `mcp[crypto]` → `pyjwt[crypto]`) and builds it, which
stops at `openssl-sys` (`failed to run custom build command`, no OpenSSL there).
Wanted: when native Windows is taken on, whether LADO needs `mcp[crypto]`, or a version with a
win_arm64 wheel.
Found: 2026-10-10, run fix/windows-probe (session lado-windows).

## A worktree folder git no longer knows reads as the session repo's

Size: S. Why here: a corner of finishing a worker whose worktree is half gone.
`runtime.gone` takes a worktree as there when its folder exists. A folder left after git
dropped it as a worktree (`git worktree prune` with the folder unreadable, or its `.git` file
deleted) sits inside the session repo (`.lado/worktrees/...`), so `git -C <folder> status` reads
the session repo's own changes as the worker's, and `worktree remove` fails with "is not a
working tree".
Wanted: take a worktree as there only when `git worktree list --porcelain` names it, or when its
`rev-parse --show-toplevel` is the folder itself.
Found: 2026-10-11, implement of fix/run-end-pushed-branch.

## The terminal keeps its colours when the theme changes while it is open

Size: S. Why here: a visible glitch in the UI, no lost work.
`web/src/Terminals.tsx` reads xterm's `theme.background/foreground` once, when the terminal
is made (`getComputedStyle`), while `--term-ground` is `light-dark(...)`: after the OS theme
changes, the xterm canvas keeps the old shade and the rest of `.term-screen` takes the new one.
Wanted: update `term.options.theme` when `prefers-color-scheme` or `data-theme` changes.
Found: 2026-10-10, review of feature/terminal-scroll-hint.

## ask_human's doc calls a multi-line answer's body a comment

Size: S. Why here: agents read the tool's doc as the contract.
`src/lado/mcp_server.py` (`ask_human`) says `"Answer to #<id>: ..." or "Dismissed #<id>",
either with the human's comment as its body when they wrote one`; for an own answer of
several lines the body is the rest of the answer (`runtime._human_text`), not a comment.
Wanted: e.g. `"Answer to #<id>: ..." (the rest, or the comment on a choice, in the body) or
"Dismissed #<id>" (the human's comment, if any, in the body)`.
Found: 2026-10-10, review of feature/question-answer (Minor 1).

## The artifact tab's image fit is not tested

Size: S. Why here: a layout claim of the bare tab with no test.
`tests/ui/test_artifacts_tab.py` opens an image in `/view/<session>/<record>` with a 1×1 PNG,
so nothing checks that a large image is fitted to the tab (`object-fit: contain`, never upscaled).
Wanted: a large image whose box stays within the viewport, and a small one not upscaled.
Found: 2026-10-10, review of feature/artifact-new-tab (Minor 1).

## Smoke test: two of its endpoint checks are looser than they read

Size: S. Why here: the review of feature/live-cloud-matrix left two Minor findings open.
`tests/smoke/test_smoke.py`: for Codex, the supervisor's first request to the fake endpoint
is asserted at once, without a wait (lines 85-86); and "w1 reached the endpoint" is checked
as more requests in total (line 94), not as a request by w1.
Wanted: wait for the first request, and tell each agent's requests apart (e.g. by a header
or the config's provider name) so the check is per agent.
Found: 2026-10-11, review of feature/live-cloud-matrix.

## The lado-dev kit's checker still runs live tests at verify

Size: S. Why here: the human decided live tests run only locally at release; the supervisor overrides the kit each time.
The kit-lado-dev checker role (section 3) has `verify` run `make test-live` when a change touches
providers, hooks, mcp_server, runtime or agent_env, and its lado-checks skill ("Live tests", "Releasing
LADO") says the same; docs/testing.md "Test layers" still says "run it locally after changing a provider".
Wanted: in the kit repository, no live tests in `verify`; the release order is CI green (smoke on
Linux and macOS), the Windows probe green, `make test-live` for every provider locally (Claude with
the human's yes), then the tag. docs/testing.md to match.
Found: 2026-10-11, verify of fix/run-end-pushed-branch (checker-3).

## LADO's messages to the lead read as orders

Size: M. Why here: weak models follow them against their role; the root of the passive live supervisor's breakage.
LADO's lines and instructions to the lead say "Start one with spawn_worker", "Merge the
branch", and SUPERVISOR_INSTRUCTIONS lists spawn_worker, finish_worker and the flow tools
also to a read-only supervisor, which has none of them (read-only roles only make the
orders harmless). A passive supervisor on qwen3-coder followed them in 6 of 10 runs.
Wanted: LADO's messages to the lead state facts ("step x needs a developer"), and the
lead's instructions name only the tools it has.
Found: 2026-10-11, design of feature/read-only-roles.
Done in feature/stable-local-live: LADO's run messages to a read-only lead (a step that needs
a worker, a run's end that kept its branch, a resume, a worker that stopped) name what waits
and the human's ways only. Left: the texts to a lead that is not read-only, and
SUPERVISOR_INSTRUCTIONS and FLOW_INSTRUCTIONS, which still list the command tools to a
read-only lead before READ_ONLY_INSTRUCTIONS switches them off. Also seen there: the live
tests' read-only passive supervisor, on qwen3.5-35b-a3b, takes the one-line copy "human wrote
to w1: ..." as its own task: it reads the attached image with read_artifact and answers the
human itself (OpenCode, 6 of 6 recorded image runs), while w1 does the same.

## A read-only Codex agent on an OpenAI model may keep apply_patch

Size: M. Why here: read-only Codex agents are checked only on a model Codex has no metadata for.
Codex 0.162 gives apply_patch by the model's metadata (`apply_patch_tool_type`); a local
model gets the fallback metadata, which has none (checked on qwen3.5-35b-a3b, run
feature/stable-local-live), but an OpenAI model may get it, and no config key takes it
away. LADO warns at each read-only Codex agent's launch and reports a change of the
repository after the turn. Not tried: a `model_catalog_json` that gives the model no
apply_patch; a PreToolUse hook that denies the apply_patch tool (it does not see a shell
`apply_patch <<EOF`, which reaches the hook as `Bash`).
Wanted: checked on an OpenAI model (paid, the human's yes), and a way to take it away.
Found: 2026-10-11, implement of feature/read-only-roles; narrowed in feature/stable-local-live.

## Live: the passive supervisor explores instead of waiting

Size: S. Why here: makes the Codex live image test flaky on the gateway (qwen3.6).
On its first input ("session started; wait…") the read-only passive supervisor read files
in its config folder and in `LADO_HOME` for more than 60 s instead of ending its turn; the
Codex image test failed once on it (verify of feature/stable-local-live, visit 2) and passed
on rerun.
Wanted: a passive role or first message that makes the model end its turn at once, or a
longer idle wait in the test with the reason written down.
Found: 2026-10-11, verify of feature/stable-local-live.

## Flaky: Kilo live tests time out on slow gateway turns

Size: S. Why here: AC 12 of feature/stable-local-live (3 green runs in a row) not met for Kilo.
On the gateway (qwen3.6) a trivial first turn of w1 took the model 2-2.5 minutes, so the
human's message started near the end of the image test's 180 s wait (2 runs of 3); in the
flow test w1 hung in a model call after its commit, past the 240 s wait. LADO's delivery
and hooks were correct.
Wanted: live waits that allow for a slow endpoint (e.g. scaled by a variable), or a failure
message that says the model's turn was still running; or a documented model or endpoint
that answers in seconds.
Found: 2026-10-11, verify of feature/stable-local-live.

## Live evidence may keep the gateway key when its copy fails half way

Size: S. Why here: the design asks that evidence never hold the key; local `/tmp` only.
`tests/agent_helpers.keep_evidence` redacts only after `_copy_evidence` returns; if the copy
raises part way (e.g. after `agents/` with an unread `env.json` was copied), the files
already copied keep the key and `real_clis.keep_evidence` leaves the folder as it is.
Wanted: redact in a `finally` around `_copy_evidence`.
Found: 2026-10-11, review of feature/stable-local-live (Minor, left open).

## Two misleading texts: a resume problem's "you" and `deny_edit_tools`

Size: S. Why here: wording only, left open by the review of feature/stable-local-live.
`runs.py:421` says "neither you (read-only) nor lado flow-set can move it", which reaches
the human's stderr through `cli.py:57`, where "you" reads as the human. The comment on
`Capabilities.deny_edit_tools` (`providers/base.py:53`) reads as unconditional, though for
Codex the claim depends on the model.
Wanted: the resume text names who it means; the comment says where the claim depends on the model.
Found: 2026-10-11, review of feature/stable-local-live (Minor, left open).

## A long text record's horizontal scrollbar sits after its last line in the artifact's tab

Size: S. Why here: Wrap lines and shift+wheel work around it.
`.artifact-tab-text .code-scroll` has `max-height: none` and `overflow: auto`, so a record
with long lines shows its sideways scrollbar only at the end: to scroll sideways at the top
one scrolls to the end first.
Wanted: decide whether that is acceptable, or make the sideways scroll reachable where the
reader is.
Found: 2026-10-11, review of fix/artifact-tab-scroll.

## Flaky: the Codex live image test's w1 stays busy on its task on LM Studio

Size: S. Why here: one red live run at the 0.35.0 release, green on the first rerun.
`test_an_agent_sees_the_image_the_human_attaches[codex]` on LM Studio's qwen3.5-35b-a3b
(through the bridge): `timed out after 120s waiting for w1 to be idle; agents: supervisor
idle, w1 busy`, its task read. Evidence:
`$TMPDIR/lado-live-evidence/20261011-210906-test_an_agent_sees_the_image_the_human_attaches_codex_`.
Wanted: find out from the evidence what w1's turn did that long (a slow model turn, or a
turn's end Codex ran no hook for), then a fix or a longer wait with the reason written down.
Found: 2026-10-11, live tests of release 0.35.0.

## The chat does not stay at the bottom when its last entry grows in place

Size: S. Why here: no CI failure shows it, but a reader at the bottom loses the end of a
growing entry.
The chat's scroll rule (`web/src/Chat.tsx`) follows the feed to its end only when a new last
entry comes (a new key). When the last entry grows where it is (a run group that gets its
next move, a gate's line that gets its answer and comment), the feed does not scroll, and
the new lines sit below the fold.
Wanted: a reader at the bottom stays at the bottom when the last entry grows too.
Found: 2026-10-14, feature/lad-44-flake-races (design).

## Codex clones its plugins repository at every start

Size: S. Why here: it slows each Codex agent's start and fills a failed smoke's evidence.
Codex CLI clones its plugins repository into `<CODEX_HOME>/.tmp/plugins-clone-*` at every
start; LADO gives each agent its own `CODEX_HOME`, so each start clones again, about 300 MB
in each failed smoke's evidence folder. It did not cause the smoke failures of 0.37.0.
Wanted: switch it off in the agent's config.toml, once a config key for it is checked by
hand on the tested Codex version.
Found: 2026-10-14, feature/lad-44-flake-races (design, from the smoke's evidence).

## The expanded waiting card sometimes stays expanded after the second Esc

Size: S. Why here: a UI flake seen once; 100 of 100 green in a focused CI run.
`tests/ui/test_chat.py::test_an_artifact_from_the_expanded_card_shows_over_it_and_esc_closes_the_topmost`
failed once in CI (run 39150756993, job ui (2)): the artifact panel closed with the first
Esc and the focus was back on the chip, but after the second Esc the card stayed expanded.
LAD-99 did not find the cause. Ruled out in Chromium: the gap between the router
transition that removes the panel and its passive effects, where the card's Esc listener
is not yet back (a `MutationObserver` Esc right after the commit, and React's scheduler
tasks delayed by 1 s, both passed on the code before any fix: CI runs 39246518194 and
39250165796); the test passed 100 of 100 in CI run 39250945744. The test now records every
keydown, the card's class and the address's changes, and prints the record and the card's
HTML on a failure (`record_esc`, `printed_on_failure`). A candidate fix, not pushed and
unproven: the card's and the panel's Esc listeners in `useLayoutEffect` instead of
`useEffect` (local branch `lad-99-backup`, commit 99b32ad of LAD-99).
Wanted: when the test fails again, read its record in the ui job's log and file a task
with it.
Found: 2026-10-18, CI of e859751.

# P3: maybe never

## A field that grows with its text keeps its height when its width changes

Size: S. Why here: the composer has done so since it grew; the height is right again at
the next key, and a field only gets narrower when the window does or the card folds.

`useGrow` (`web/src/fieldHeight.ts`), shared by the composer, the waiting card's fields and
a gate's comment, sizes a field on each change of its text only. A field made narrower
(the window, the waiting card folded back from expanded) wraps into more lines but keeps
its height. While it is under its most lines it does not scroll (`overflow-y: hidden`),
so its last lines are hidden until the human types again.
Wanted: the height sized again when the field's width changes (a `ResizeObserver` on the
field).
Found: 2026-10-15, review of fix/lad-70-answer-field-height (E2).

## A worktree git has forgotten while its folder stays makes finish fail

Size: S. Why here: only a `git worktree prune` or a `git gc` that prunes, or a hand
removal of `.git/worktrees/<name>`, makes it. A container whose paths the host does not
have makes it ordinary: the host's git sees such a worktree as `prunable`
(docs/research/docker-install.md, H6).

`runtime.gone` judges a worktree by its folder only. A folder git no longer knows is not
gone to it, so `remove_work` calls `git worktree remove`, and git refuses: `fatal:
'<path>' is not a working tree`. `lado finish`, `finish_worker` and a run's end fail on
it.
Wanted: a worktree git does not list (`git worktree list --porcelain`) counts as gone. Its
folder is left for the human, or removed after LADO's usual check for uncommitted work.
Found: 2026-10-14, review of lado/lad-52/task-lad-52.

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
Seen again (2026-10-09): Claude Code 2.1.29x runs Agent-tool subagents in the background by
default, so an agent shows idle (up to 85 s seen) while its subagents work. Analysed without
code changes: every `Stop` payload carries `background_tasks` (running subagents, shells,
monitors; read in the binary, not yet seen live). Options: A `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`
(one line, loses background Bash); B keep `idle`, store the snapshot from each Stop and show
"idle · N in background" (M, schema change; recommended); C busy while tasks run (rejected:
blocks the queue). Not decided by the human yet. Full report: artifact `analysis-subagent-idle`
of session `lado`.
Done for Claude Code (2026-10-09, feature/background-status): a status `background`, which
takes input as idle, set from the Stop's `background_tasks` (seen live with 2.1.295). Still
open: OpenCode and Kilo report no background work (OpenCode's background subagents are
experimental, `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`; Kilo not checked), so their
agents show idle while it runs.

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
say so in docs/testing.md.
Found: 2026-10-06, fix/ci-git-identity, checking the tests without a global git identity.

## A start or resume from the UI that tmux fails is a 500 without its cause

Size: S. Why here: the UI hides the real cause (a missing tmux) the CLI now names.

`POST /api/sessions` and `POST /api/sessions/{name}/resume` (server/app.py) turn only
`LadoError` and `KitError` into a 400 with the reason; a `tmux.TmuxError` (`TmuxMissing`:
tmux not on the server's PATH) from `start_session` is a 500 "Internal Server Error", and
the notes of a failed undo (`runtime._undo`, also on a `LadoError`) are not in the 400 either.
Wanted: the API answers 400 with the error and its notes, as the CLI prints them.
Found: 2026-10-06, fix/tmux-missing-rollback.

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

Size: L. Why here: a project's artifacts that outlive its sessions come after the projects epic (docs/design/projects.md, Not now); a session's artifacts are enough until then (docs/design/artifacts.md, Left out).
`lado forget` removes a session's artifacts with it, so a design or report cannot outlive
the session that wrote it, nor belong to a project or a tracker task.
Wanted: a project scope for artifacts (one more scope, one migration), kept across the
sessions of that project and removed with the project.
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

## The session list's run time and the head's can differ by a minute

Size: S. Why here: cosmetic, at most a minute for under a minute.
The row and the head each run their own `useNow` interval (`web/src/Sessions.tsx`, `useRan`),
started at their own mount, not on a minute of the run time: when the head opens later than
the list, around a minute's turn the row can say `2 h 14 min` and the head `2 h 15 min`.
Wanted: one shared minute clock for the list and the head (a context or module-level store),
or ticks aligned to the next minute of `running_since`.
Found: 2026-10-11, review of feature/session-row-line (Minor finding 1).

## The wheel-up hint points at a disabled Take control

Size: S. Why here: a hint the human cannot follow, only while the terminal has no connection.
In view, a wheel up while the socket is not open (e.g. `reconnecting`) still rings Take
control (`attention`) and shows "Scrolling works after Take control.", though the button is
disabled then (`web/src/Terminals.tsx`, the wheel handler and the hint).
Wanted: the hint only while the socket is open, or no ring on a disabled button.
Found: 2026-10-11, review of feature/terminal-control-bar (Minor finding 1).

## A control socket that closes for good before it opened stays marked in control

Size: S. Why here: rare (a 44xx close right after Take control), and Reconnect ends it.
The terminal releases control only on a transition from `open`; a control socket that never
opens and closes for good keeps the blue bar and the tab's mark beside `closed: <reason>`
until Reconnect (which opens in View) or the agent changes.
Wanted: a close for good in control releases it too, whatever the phase before.
Found: 2026-10-11, review of feature/terminal-control-bar (noted, allowed by the design).

## Managing workspace folders outside projects

Size: M. Why here: the projects model gives LADO only the workspace's `projects/`; the rest is the human's (docs/design/projects.md, Not now).
LADO lists, adds and removes the repositories of a project, but not the other folders of the
workspace: sessions without a project (a clone by URL, a folder made from scratch) and
anything the human put there. Tidying them up is done on the host, which in Docker means
leaving the UI.
Wanted: if it is ever needed, listing those folders in the UI and removing one there, with
the same unpushed-work check as a project's repository; never a folder LADO did not show.
Found: 2026-10-21, design of LAD-117.
