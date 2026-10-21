# The CLI in use

How the `lado` commands behave: starting, kits, logs, finishing, stopping, gates and the
rest. Moved from AGENTS.md's "Try it locally" (LAD-82).

`uv run lado start <repo>` runs the working copy (a repository without commits is refused:
make a first commit). `lado start <git-url> [<folder>] [--branch NAME]` clones the URL's
branch (the remote's default without `--branch`) into the folder, a full path, by default
`$LADO_REPOS/<repo>` (an absolute `LADO_REPOS`), else `~/lado/<repo>`, then starts there as `lado start <folder>` does: the folder must be new or
empty (a clone of the same repository there is refused with the `lado start <folder>` that
uses it as it is; LADO never fetches into or switches a folder that exists), and a name a
session of another folder has is refused before the clone (`runtime.check_name`). git's
progress goes to stderr; Ctrl-C ends git's process group, removes the temporary folder and
exits 130 (`lado: clone cancelled`), a SIGTERM or SIGHUP the same way with 128 + its
number; a start refused after the clone says `the clone stays
in <folder>`. `<folder>` and `--branch` without a git URL exit 2. `--prompt TEXT` or
`--prompt-file FILE` (`-`: stdin; not both, exit 2) gives the supervisor a first message
from the human, for a folder, a git URL and a resume alike: read and checked
(`runtime.check_prompt`: not empty, at most `MAX_MESSAGE` characters; a file it cannot read
is exit 1) before any clone or start, stdin read once, and `first message: queued for the
supervisor` after the Started or Resumed line. The UI starts sessions too (Launch). Use `LADO_HOME=/tmp/some-dir` and
`LADO_TMUX_SOCKET=lado-dev` to keep test sessions apart from the LADO you work with.

`lado start --new [<folder>]` (default: the current folder; relative paths are taken from
it) starts from scratch (`lado.scratch`): the folder must be new or empty (nothing but
`.DS_Store`) and in no git repository, and git must know the commits' author (`user.name`
and `user.email`). It makes the folder (and the folders above it), `git init`, the branch
of `init.defaultBranch` (else `main`) and one empty commit `Start from scratch` (no file, no
signing, no hooks), prints `Made <folder> a git repository with an empty first commit`, and
starts the session as `lado start <folder>` does, named by `--name` or the folder. A refusal
is exit 1 with its hint and changes nothing: a folder with files gets LAD-5's `git init`
command, a folder of a repository `lado start <root>`, a git without the author the `git
config --global` command (in LADO's container: `LADO_GIT_NAME` and `LADO_GIT_EMAIL` in
`.env`); a git step that fails removes what it made. A start refused after the repository
was made says `the repository stays in <folder>`. `--new` with a git URL, a second folder or
`--branch` exits 2. Without `--new`, `lado start` never makes a repository.

`lado kits add <git-url>[@vX.Y.Z]` installs the kit of a repository (a row in lado.db; its
clone in the git cache): without a tag its latest release, with `--pre` its latest version
of all. A folder (read in place, the way to develop a kit) has no version. `lado kits add <kit>[@vX.Y.Z]
-m <marketplace>` takes the kit's address from that marketplace's list; without `-m` LADO
never looks in a marketplace. A kit not from the official marketplace or a folder shows
what would be installed (address, version, commit, MCP servers) and asks `Install? [y/N]`;
`--yes` skips the question, and without a terminal it is required. A kit whose latest
version needs a newer LADO is refused. `lado kits update <name> [vX.Y.Z]` moves a kit
installed from git to its latest or another version without asking, and warns on stderr
about the MCP servers the installed version did not start: running sessions build their
kits again at each spawn and run start, so only their new agents get it (the output says
so and names the running sessions that use it, `kits.update_line`); the old clone stays
in the cache. `lado kits outdated` checks each installed kit
against its remote's tags and says why it does not check a folder or a kit whose folder is
missing. `lado kits check <folder> --tag vX.Y.Z`
(a kit's CI) gives the verdict add would give for that tag without installing
(`kits.load_release`, shared with add), and fails on `kits.lint`'s problems (hardcoded
paths, the graph rules of `flows.lint`); `kits.warnings` are printed as `warning:` and do
not fail it (a flow step's role not in the kit, a role that acts in none of the kit's
flows, a version that differs from the clone's tags). A tag that points to another commit
than the installed one is a loud warning (outdated, update, add). `lado kits remove <name>`
drops the row; its folder stays (one already gone is no error); it warns on stderr about
the running and stopped sessions that use the kit (`runtime.kit_users`, the lines the UI
shows too). `lado kits` lists every kit
with its version and where it comes from (the marketplace it was added from, `removed` when
that marketplace is gone), and on stderr what to do with an older LADO's `LADO_HOME/kits`;
`lado kits show` names each kit's packs and where each agent's skills come from.
`lado marketplaces [list]`, `add <name> <git-url>`, `remove <name>`, `enable|disable
<name>` and `update [<name>]` manage the marketplaces; `official`
(github.com/ladohq/marketplace) is always there and can only be disabled. `remove` names
the installed kits from it, which stay. The UI's Kits page does all of this too.

`lado log <session>` shows what happened in a session: messages between agents (one line
with their delivery state and summary, the body indented below) and agent events (spawned,
status changes). `--agent NAME` keeps one agent's
lines, `-n N` the last N entries, `--follow` keeps printing new ones until Ctrl-C.
With `--follow` a message is printed once, with the state it had then; a later delivery
is not printed again.

`lado finish <session> <agent>` ends a worker whose branch is merged into the session repo's
current branch: it removes the worktree and branch, drops the agent from `lado ls` (its
messages and events stay in `lado log`, with a `finished` event), then closes the window (a
window already gone is fine, as for a worker that ended by itself; one that does not close
is an error that says the worker is finished and gives the `tmux kill-window` for it).
Messages it never got and bodies it never read are dropped, so a later worker of the same
name starts fresh. It refuses an unmerged branch or uncommitted changes; `--discard` ends
the worker anyway and throws that work away. "Merged" is LADO's own check against the
repo's current branch, the one gate: the branch then goes with `git branch -D`, as `-d`
would check a pushed branch against its upstream instead (`runtime.remove_work`, also a
run's end). A worktree or branch already gone (deleted by hand, an end that stopped half
way; `runtime.gone`) is no reason to refuse: the finish removes what is left and says
what was gone (`work_state`'s `gone`, the UI's Agents tab). With the branch gone, the work
is the worktree's HEAD (`runtime.tip`): commits there not in the current branch, or
uncommitted changes, are still refused without `--discard`. The supervisor does the same
with the MCP tool `finish_worker`. A worker of a flow run only has its window closed while
the run is open: the worktree and branch belong to the run; the run's end removes them by
the same rules, so a gone worktree or branch never keeps it from closing its workers.

`lado stop <session>` marks the session stopped, kills its tmux windows, then closes the
UI's terminals of its agents (their viewer sessions). A kill that fails leaves it marked
stopped: the error says its agents may still run and gives `tmux -L <socket> kill-session -t
<session>`, after which `lado start` resumes it (`lado stop` refuses a stopped session). Its history,
runs and gates stay, and so do worktrees and branches. Its agents are forgotten (their names
are free again; `lado log` keeps what they did), and messages they never got or whose body
they never read are dropped, with the count in the output: new agents start fresh.
`lado stop --all` stops every session not stopped yet (also one whose tmux or loop is gone),
prints each as soon as it is stopped and says which tmux socket it sees; one it cannot stop
does not keep the others running, and the error names it and the ones stopped (exit 1). On an older `lado.db` (a LADO upgraded by hand) this
LADO cannot mark a session stopped without migrating: `lado stop <session>` is refused,
with nothing changed, while another session runs, and points to `lado stop --all`;
otherwise the stop kills the tmux sessions, waits for their loops (one that does not end
stops it before the migration: run it again), migrates, then marks them stopped.
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
`spawn_worker` needs `role` unless the session has one worker role (`Environment.role`);
the lead's instructions say which, and list each role and flow with its kit.
`lado start` (also a resume) prints who leads (`lead: ...`) and, on stderr, how each kit
supervisor that does not lead is used (its lead skill, the MCP servers the lead does not
get, a supervisor that lists no skills).
When LADO's built-in supervisor leads, each kit supervisor that does not lead (but the
default kit's) gives it a skill `lead-<kit>` (`runtime._write_lead_skills`, at each start
and resume, once the session is taken): in the lead's config folder,
`lead-skills/lead-<kit>/SKILL.md` holds that supervisor's prompt and the paths of the
skills its `skills:` names, copied (links followed) into `lead-files/<kit>/<skill>/` in
that kit's versions. `lead-files` is no skills folder of any CLI (Kilo and OpenCode find
SKILL.md at any depth under their skill paths) but `AgentSpec.read`; the lead's instructions name the
kits with a lead skill.
A worker started without a name (`spawn_worker`, also for a run) is named after its role,
made valid like a given name (`slug`: `Code Reviewer` gives `code-reviewer`): `developer`,
or `developer-2`, `developer-3`… when that is taken. A name is taken by a running agent of
that name or a branch `lado/<session>/<name>` still there (from a stopped launch or a
worker not finished); `human`, `lado` and `supervisor` are never chosen. A given name wins
and is checked as before.
`lado forget <session>` deletes a stopped session with its history and its artifacts (the
store's `remove_session` first, which also removes content files no record refers to that
are more than an hour old; the output counts the artifacts); it refuses a running one, and
one with open runs unless `--force`; worktrees and branches stay on disk and are listed.

`lado title <session>` prints a session's title (or `<session> has no title`); `lado title
<session> TEXT` sets it and `--clear` clears it (both together exit 2), through
`runtime.set_title`, printing `<session>: title "<title>"` or that it has none; for a
running or stopped session alike, the name and everything named by it unchanged. A title
with a hidden character (a line break, a tab, a line separator, a bidi control, a
zero-width space; `text.py`) is refused naming it (`a title is one line of visible text:
U+202E RIGHT-TO-LEFT OVERRIDE is not allowed`). Setting
or clearing is refused inside an agent (`LADO_AGENT` set), as `lado answer` is; reading is
not. `lado ls` prints the title, quoted, after the name. The UI sets it too (the pencil in
the session's head, Rename… in the list; docs/design/ui.md, Session title). A title is
never set at the start and by no MCP tool.

`lado uninstall [--dry-run] [--keep-data] [--yes]` removes LADO (`uninstall.py`): it prints
its plan and asks `Uninstall? [y/N]` (`--yes` is required without a terminal; `--dry-run`
only prints), then stops the UI server and every session of this `LADO_HOME` with their
loops and viewers, waits up to 10 s for the agents' processes to end (an agent may run its
session-end hook first; one still running stops the uninstall with exit 1 before any
repository or file is touched, naming its session, its pid and `kill <pid>`, after which
`lado uninstall` runs again), ends LADO's tmux server when no other session is on its socket, removes
in each session's repository the worktrees and branches `lado finish` would remove without
asking and lists the others with their `git worktree remove --force` and `git branch -D`,
deletes `LADO_HOME`, and, only for the default `~/.lado`, removes the program last (`uv
tool uninstall lado`, `pipx uninstall lado<suffix>`). With another `LADO_HOME` the program
stays and its command is printed. Refused inside an agent, while `lado update` runs and on
a newer `lado.db`. `--keep-data` keeps `LADO_HOME` and the repositories, so a LADO installed
again resumes the sessions. The agent CLIs' own records of the folders stay
(docs/install.md, Uninstall).

Supervisor-started sessions: the supervisor proposes a new, independent session for a
problem it found or a new ticket by `ask_human` with the brief attached and the choice
`runtime.START_CHOICE` (`Start session <name>`, the one spelling, also in its
instructions); once the human picks it in the UI, its MCP tool `start_session(name,
question)` (`runtime.start_approved_session`) checks that the question is the calling
supervisor's of its session, answered with exactly that choice, and carries at least one
attachment (no two of one name), and starts the session with `resume=False` (a taken name
is `SessionExists`, so one approval starts one session) in the caller's repo with its kits,
provider, permission mode and without. Each attachment is copied into the new session's
scope (author `lado`, the summary naming where it came from), and its supervisor's first
message from `lado` carries them with the question, each artifact's author and the human's
comment; the brief never goes on argv or into the role. Nothing is stored for a proposal:
an unanswered one dies with its session's stop (its questions close); an answer stays
valid for a resumed supervisor, and after `lado forget <name>` it can start the session
again. The new session reports nothing back.

`lado artifacts list <session> [--run RUN]`, `lado artifacts show <session> <full-name>`
and `lado artifacts get <session> <full-name> [-o FILE]` list a session's artifacts, print
a text one and write one's bytes, also for a stopped session (docs/design/artifacts.md, The
human's side). `lado doctor` shows the store's size and warns about content no record
refers to that is older than an hour (the next `lado forget` removes it).

`lado telemetry [status]` says whether LADO sends anonymous usage statistics and its errors
to its maintainers, why not, and when it last sent (`telemetry.status_lines`); `lado
telemetry on|off` keeps the human's choice (refused inside an agent; `off` drops what is
queued), `lado telemetry show` prints the next daily report and the queued errors as the
sender posts them (no token); `lado telemetry send` (hidden) is the detached sender. None of
them migrates lado.db. `lado start` and `lado ui` ask once on a terminal before their work
(`telemetry.ask_if_needed`; Enter is off, EOF or Ctrl-C keeps no choice). What is sent and
where: docs/telemetry.md; how: `telemetry.py` (docs/design/modules.md).

`lado stats [--days N | --all]` prints how LADO was used on this machine in the last 30
days (`--days N`: N days, `--all`: everything kept; both, or an N that is no positive whole
number, exit 2), from lado.db's `usage` table (`state.py`, schema 27) and LADO's error
journal: sessions started and resumed; agents started per agent CLI and per role
(`<role>@<kit>`, `@?` for one spawned before 0.38.0, with a note), agents ended by
themselves, turn errors per CLI and kind; flow runs started per flow, ended, cancelled;
gates opened per kind, closed per answer, and how many of the human's answers with a
recommended choice took it (a cancelled or overridden gate is closed, never in that); questions to the human; messages failed and dropped; LADO's own errors. A
breakdown lists the larger first, then by name, and wraps under itself. The first line
names the period in UTC and says nothing is sent; `Earliest record:` follows with `--all`
or when the earliest row is later than the period's start. It reads only, opens no
connection and starts no statistics sender (`cli.main` does not kick after it); it
migrates lado.db as `lado ls` does.

`lado ui` prints (or opens) the local link with the token, then, when the running server
has a link for another device, `From another machine: <link>`: it asks the server
(`GET /api/access` with the token, `run.access`), so `LADO_PUBLIC_HOST` and, in a
container, `LADO_LISTEN` of the server's environment decide, not the shell's; a server that
does not answer it (an older one) gets no such line. In a container with `--no-open` that
line goes to stderr, so stdout stays the one local link. The rule for the link:
docs/design/ui.md, Server, Host.

`lado bug-report` prints a warning (the issue is public, nothing is sent until the human
submits GitHub's form, a vulnerability goes to private reporting), the bug report and
`Open a new issue: <link>` (`bug_report.build`; docs/design/modules.md); then, only when stdin and stdout
are terminals and a browser can show (`bug_report.can_show_browser`), asks `Open it in the
browser? [y/N]`: `y` runs `webbrowser.open`, one that fails prints `could not open a
browser: open the link above`, anything else (Enter, EOF, Ctrl-C) opens nothing; exit 0.
It does not migrate lado.db (a newer one is reported as it is) and is refused nowhere,
also not inside an agent. Its `Server:` line says `not running` or `running, loopback
only` / `open to the network` by the running server's `server.json`. The UI's Report a bug
page shows the same report (docs/design/ui.md, Report a bug).

Gates: a run that enters a gate state, or would enter a state more often than its
`max_visits`, waits for the human with an open gate (`lado ls`: `gate #<id> waiting:
<question>`). An approval gate has exactly the outcomes `approved` and `rejected` and is
answered `approve` / `reject`; a choice gate with one of its outcome names; a loop limit with
`continue` (enter the state anyway, the visit counts) or `cancel` (cancel the run). The
supervisor gets LADO's request for its recommendation, `recommend on gate #<id>: <run> at
<state>` (docs/design/agents.md; in its own `flow_advance`'s `notices` when its move opened the
gate). The answer and its comment become the next step's note, after which the note that led to the gate
follows in the body; when a worker gets the next step, the supervisor gets one line
`flow <run>: human answered <option> at <state>`.

A step's text (`runs.step_text`) has the task, the step's `do` (with `This step must
write: ...`, the `produces` names as its agent writes them, bare for a run's worker and
`<run>/<name>` for the lead), then the previous step's note with its artifacts, then
`Artifacts this step reads (read each with read_artifact):`, a line per name in its `reads`
with the artifact's latest record (`- <name>: <title> — <summary>`, named as its agent
writes it; `no record yet`; never the content), then on a later visit of the state
`Your artifacts so far` of its own `produces` that have a record, then the outcomes. A
record attached to the previous step's note is named only there. The records are read when
the step is told, so `lado flow-set` keeps them: a run set to `implement` with
`reads: [design]` is shown the latest design, and the flow-set reason is the previous
step's note. A human's comment at a gate reaches the next step only (its note).

`lado answer <session> <gate-id|run> <option> [-m COMMENT]` answers a gate. Without the
option it asks: with no arguments about the open gates of all sessions (a list to pick from
when there are several), and after each answer it goes on with the open gates of that session
until none is left or the human presses Enter on an empty line. It shows the question, the
one-line summary of the note that led to the gate with its artifacts, the supervisor's
recommendation (`Supervisor recommends: <option>`, or `Supervisor's recommendation:`
without one, ` (disagrees with <agent>)`, its first line; `Supervisor is preparing a
recommendation…` while asked, `The supervisor gave no recommendation.` when missing;
`cli._recommendation_lines`), then under
`Artifacts it reads:` a line per artifact of the gate state's `reads` but those the note
carries (`runs.gate_reads`: `<run>/<name>: <title> — <summary>` of its latest record, or
`no record yet`), and the numbered options, the recommended one marked `← supervisor
recommends`; when the note has a body or an artifact, the gate reads one, or a
recommendation is asked or given, `v` shows the whole text in `less -R` (printed when there
is no `less`): the note, the recommendation in full, each of its artifacts as attached,
then each artifact the gate reads as of its latest
record (a text one's content, else its type and size); then it asks again. The records and
the gate are read at each show, also after `v`: a write while the gate is open shows, and
the human approves the latest. A loop limit reads none. A gate whose run's flow cannot be read is
shown with its problem and left open (the supervisor's `flow_cancel` moves it), and
`lado answer` goes on with the other gates. When a gate opens, LADO opens a tmux popup (`display-popup -E`, titled
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

Flow tools return short results: the run, flow, state, status, who acts, outcomes, the
artifacts the step `produces` (full names), gate, visits, the note's summary and the run's language; `flow_status(run=...)` adds the task,
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
A run whose flow snapshot cannot be read (`runs.SnapshotError`) is shown with its problem
and the rest goes on: `lado ls` prints the reason instead of who acts or the gate it waits at, `flow_status` gives
it `problem` and no outcomes, a resume reports it on stderr and in the `session resumed`
body; only `flow_cancel` moves it (advancing, answering and `lado flow-set` refuse with
the error), and who acts without the flow is `runs.acting_or_problem`, for the core and
the UI alike.
