# How agents talk

How LADO starts agents and moves messages, statuses and turns between them and the human,
with each agent CLI's facts checked by hand. Moved from AGENTS.md (LAD-82).

- An agent's environment (PATH, keys, variables) is the user's login shell's, as a new
  terminal sees it, the same whichever process starts the agent (`lado start`, the UI
  server, an agent's `spawn_worker`) and whoever started LADO's tmux server
  (`agent_env.resolve`). For each launch (start, resume, spawn) LADO runs
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
  outside folder go over them, then LADO's variables, then the provider's. The outside
  folder (`agent_env.outside`) is the one `LADO_ENV_DIR` names, an absolute path (LADO's
  image: `/run/secrets`), read anew at each launch, so the kits' checks (`${NAME}` of an MCP
  server, `_check_commands`) see it too: each regular file directly in it is a variable,
  its name the file's, its value the content with one trailing `\n` or `\r\n` dropped. A
  dotfile is passed over; a file in a subfolder, not regular, not a variable name, reserved
  (`agent_env.RESERVED`: the shell's identity, `PATH`, tmux's, and every `LADO_*`),
  unreadable, over `MAX_VALUE` (64 KiB) or not UTF-8 text without NUL is not applied and
  named with why, never with its content (`variable file <name> in <folder> not used:
  <reason>`), in a start's and resume's warnings (`runtime._outside_warnings`) and by `lado
  doctor` (`Variables from outside`: the names, never a value; the bug report has none). A
  name LADO or the provider sets for the launch keeps their value and is named in that
  launch's warnings, `spawn_worker`'s too (`LADO sets <name> for <provider>`). Unset,
  empty, missing or the null device (`agent_env.null_device`: a character device with
  `os.devnull`'s `st_rdev`, so compose's `/dev/null` bound at `/run/secrets` is one), there
  is no layer and no line; any other path that is no folder is named `not a folder`. In a
  container doctor's `[info]` for no secrets names how to give them. A launching process with `LADO_ENV_DIR` set gives
  it to the agent and its `lado mcp` among LADO's variables (`providers.agent_env`), so a
  supervisor's `spawn_worker` and `start_session` read the same folder, also when the login
  shell does not name it. A tmux window starts with its server's environment, so the
  window runs `lado.agent_env <file> <argv>` (`interpreter.run_module`): it reads that environment from a file
  in the agent's config folder (`env.json`, mode 600 also when it was there before, removed
  once read; the one file under `LADO_HOME/agents/` that holds the values of a kit's MCP
  `env`, see `mcp_exec.py`; a Codex agent's `config.toml`, mode 600 too, holds what LADO
  carried of the user's Codex config, whose model providers may hold keys), keeps tmux's own `TERM`,
  `TERM_PROGRAM(_VERSION)`, `TMUX` and `TMUX_PANE`, and execs the agent's CLI, found on the
  resolved `PATH`. `lado doctor` shows the source and how long the shell takes (a warning
  above 2 s).
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
  (BACKLOG.md).
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
  already, so dropping it is no silent drop. A transient error after the last resume goes
  to the lead as above, with `after <N> resumes`. Every turn's end that plans no resume (as
  usual, a permanent error, the resumes spent) sets the count back to 0. Claude Code's
  transient types are `overloaded`, `server_error` and `unknown` (also the machine's
  sleep; `claude.TRANSIENT`); Kilo and OpenCode mark no error transient: the plugin gives
  only the error's class name (BACKLOG.md). Claude Code runs `StopFailure`
  instead of `Stop` then (API errors: rate_limit, overloaded, authentication_failed,
  billing_error, server_error, also the machine's sleep, max_output_tokens, unknown) and
  ignores its output (`Event.output_ignored`: the queue is typed in, not printed); read in
  the binary of 2.1.291, not triggered by hand. Kilo 7.8.3 and OpenCode 1.18.34 publish
  `session.error`, then `session.idle` of the same session (read in their bundles); the
  plugin passes the error's name (and an `APIError`'s message) with that idle, drops it at
  `session.compacted` (a context overflow the CLI compacts its way out of ends no turn),
  and `MessageAbortedError` (the human's Esc) is no error. Claude Code runs no hook when
  the human interrupts a turn with Esc, while text streams, while a tool runs or on a
  permission dialog (checked by hand with 2.1.292): the agent stays `busy`, or `waiting`
  after a `PermissionRequest`, until the human's next prompt in its window, whose `Stop`
  ends the turn and hands over the queue (BACKLOG.md). Codex CLI 0.162 runs no hook at all
  for a turn that ends on a model or API error: the agent stays `busy` (BACKLOG.md); the
  human's Esc, and a refused approval, run `Interrupt` and no `Stop`: a turn's end whose
  output Codex ignores (`output_ignored`, read in its source), so the queue is typed in, and
  a refused approval ends the wait at once.
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
- An agent whose CLI asks the human before any hook (Claude Code's "trust this folder?" in a
  repo it does not trust; `Provider.first_hook_blocker`) waits from its start: after
  `launch_command` and before its window starts (`runtime._first_hook_blocker`, for start,
  resume and spawn), `state.block` sets it `waiting` with a `blocked` event, whose detail
  is why and what to answer. That reason holds while no `status` or `spawned` event came
  after it (`state.block_reasons`, read by `_Reasons`: `lado ls`, `list_agents`,
  `AgentInfo.status_reason`, Needs you), before the reason of failed messages. Its first
  `SESSION_START` ends that wait (also only that one: a compaction's session start leaves
  any other wait), and its queue is handed over as after any start; an answer that ends
  the CLI ("No, exit") is an end like any other (`agent_ended`, the window check). Who
  starts it is told the reason, or the provider's `warning` when it cannot tell: `lado
  start` on stderr, the UI's start in `Started.warnings`, `spawn_worker` in its result's
  `warnings` and in `loop.log`.
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
  result (any channel; never a `pending` one, which keeps the queue's order); a stop or finish
  drops such a message unread. The supervisor stays quiet with the human: it does not relay reports,
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
  dropped (stop, finish), and a forgotten agent's open questions are `closed`. LADO's
  instructions tell the supervisor to answer where the human asked: a `[from human]`
  message with `send_message(to="human")` or `ask_human`, text typed into its window in the
  window. At each turn's end, before the queue is handed over, the human's messages the
  agent got (not answers or dismissals) are checked once: `replied` if it wrote to `human`
  after it got them (by `sent_at`, when each was handed over, not by id), else `missing`,
  which the chat shows as "replied only in its terminal".
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
  Kilo and OpenCode
  (`Capabilities.notice_on_argv`) lose text typed into their TUI right after the plugin's
  init, and no event or API says when it takes input (OpenCode 1.18.35, checked by hand):
  their queue's lines at launch, never a body, go on `--prompt` (`runtime._launch_command`),
  handed over then as `typed` with its first attempt and confirmed by `chat.message` as
  typed text; the agent stays `starting` until its session start. Codex CLI takes them as
  its own `[PROMPT]` argument, and starts its session (SessionStart) only when its first
  input is submitted (`Capabilities.session_start_on_first_input`): an agent of it with an
  empty queue (a new supervisor) first gets `runtime.FIRST_INPUT` from `lado`, a message
  like any other, so a Codex supervisor's start costs one short model turn. Codex's
  `SessionEnd` is not used: after `/resume` it runs for the conversation left, once the
  next one has started; an agent whose Codex exits is ended by the window check.
- A queue is handed over by one of two channels, kept with each message
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
  finished or stopped in between). A queue is taken only so, also an agent's first input.
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
  also how long `check_windows` leaves a new agent alone, and `loop.wait_stopped` waits
  three of them; `loop.log` names it at the loop's start), so an unconfirmed message is
  typed again or failed on time with no send and no hook. Before each sweep it looks at the
  session's windows (`runtime.check_windows`, one `tmux list-windows`, no screen; the
  pass's only tmux call): an agent
  not stopped whose window is missing in two passes in a row, and that was added more than
  one interval ago, has ended (`agent_ended`), so a CLI that crashed before its first hook
  or in a turn is `stopped` within a few seconds. A failing list changes nothing: only then
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
  migrates); an error in a pass is
  written there too with its traceback (and once to `errors.jsonl`, `telemetry.record`),
  and the loop goes on. While the same error
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
  `MESSAGING` (`runtime.CONTAINER_INSTRUCTIONS`): a tool the project needs and lacks is
  installed with mise into the home volume, by the project's version files or as
  `<tool>@<version>` run through `mise exec`; no file is added to the project unless the
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
