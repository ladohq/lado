# Modules

What each module and folder of the repository does, in detail. Moved from AGENTS.md's
Layout (LAD-82); AGENTS.md keeps one line per module.

- `src/lado/`: the Python package.
  - `cli.py`: the `lado` command; its console script is `console.py`, which refuses native
    Windows in one line (WSL2) before importing `cli.py` (termios, fcntl). `doctor.py`: environment checks; a provider's state
    (installed, version, tested version, warning) is `doctor.provider_status`, which
    `lado doctor` formats and the UI's `GET /api/providers` serves. A `doctor.Check` has
    one `level` (`OK`, `INFO`, `WARN`, `FAIL`; printed `[ok  ]`, `[info]`, `[warn]`,
    `[FAIL]`; exit 1 only for a `FAIL`). No provider is required: a missing one is `info`
    with its install hint, an installed one with an untested version `warn`, and only
    none installed is one `FAIL` (`Agent CLI: no agent CLI installed`, every install hint).
    `git` (after `tmux`, `check_git`) is the folder check's own look, `runtime.git_version`:
    `FAIL` with the core's text and hint when git is missing or does not run, `WARN` below
    `runtime.GIT_MIN` (2.31: `gitpaths`' `--path-format=absolute`), else `OK`.
    `git author` (after `git`, `check_git_author`, no line when git does not run) is a fresh
    start's own look, `scratch.author_problem("/")`: `OK` with both `user.name` and
    `user.email`, else `WARN` with its hint (the `.env` one in LADO's container); it never
    prints them.
    `Repositories folder` (after `git author`, `check_repos_folder`, only while `LADO_REPOS` is
    set and not empty): `OK` for a folder, `INFO` for one not made yet, `WARN` for a path
    that is no folder or LADO may not look at (one `stat`, never `exists()`, which raises
    there on some Pythons), a folder LADO may not write in (a probe file made and removed,
    never `os.access`: a Docker Desktop bind mount shows its root as 0:0) or a value that
    is not absolute (which `clone.repos_folder` ignores).
    `Agent config folders` warns about each folder under `LADO_HOME/agents/` that no
    running agent uses (`runtime.stray_config_dirs`), with its `rm -rf`: an older LADO wrote
    kit MCP secrets there. The UI's system panel (`GET /api/system`) takes its facts from
    `doctor.system_info` (version, OS, installer, home, schema, tmux, git's version or
    `not installed` / `does not run`, never its path, providers, kits,
    session counts, on a Mac where it and LADO's tmux server run, `gui_places`, also
    `lado doctor`'s Graphical session, the update check and the last update's result) and
    the text to copy for
    an issue from `doctor.report(system, server)`: no address, path, repository, session
    name, token or message, only whether the server runs and is open to the network (a
    `ServerState`, its uptime when the server itself asks; None is `not running`) and
    whether LADO_HOME is set.
  - `bug_report.py`: a bug report for a new GitHub issue (openspec change bug-report), the
    one builder for `lado bug-report` and `GET /api/bug-report`: `build` gives a `Report`,
    `What happened`'s placeholder, `doctor.report`, the UI's browser line (checked against
    `BROWSER_LINE`) and the error journal's lines of the last `WINDOW` (30 days, both
    files; `errors`) grouped by kind (`kinds`: by `fingerprint`, a line without one by type
    and where; newest first; at most `MAX_FRAMES` innermost frames). Of a line it reads
    only `READ`, never the message, traceback, session or agent. `url` is GitHub's new
    issue form (`ISSUES_NEW`, title and body in its query) of at most `MAX_URL` characters:
    the oldest kinds leave its `body`, counted in a last line, `text` is never cut.
    `can_show_browser`: on macOS the graphical session (`gui_session.place`), else
    `DISPLAY`, `WAYLAND_DISPLAY` or `BROWSER`. It sends nothing.
  - `update.py`: upgrading LADO, no tmux, providers or UI: PyPI's JSON of the package
    (`fetch_index`; `latest` skips pre-releases and yanked ones, with `pre` it takes the
    newest of all; `release` finds a named one), what an update of this LADO is offered
    (`offered`, the one rule for the check, `lado update` and the UI's plan: the newest
    final release, for a LADO that is itself a pre-release, a release candidate, the newest
    of all; docs/release.md), the one PEP 440 comparison (`newer`, `same`, `prerelease`;
    not `gitcache.latest`, which sorts kit tags), a version as printed (`shown`: `X.Y.ZrcN
    (pre-release)`, `lado doctor` and its report), the daily check (`check`:
    `LADO_HOME/update-check.json`, a look at most once per `CHECK_EVERY` and
    `CHECK_TIMEOUT` seconds, a failure kept there too, for `lado ls`, `lado doctor` and the
    UI's `GET /api/update` alike; the file keeps the kind it looked for, `pre`, and one of
    the other kind, or without the key for a pre-release, is stale;
    `LADO_NO_UPDATE_CHECK=1`: no look and no line; in a container it names the new
    version's image, `IMAGE:<version>`, and no command instead of `lado update`:
    `available_line`), the published image's name (`IMAGE`, `ghcr.io/ladohq/lado`, the one
    in code: the Release workflow, docker/compose.yaml and `scripts/release_notes.py` are
    tested against it), whether LADO runs in its container (`in_container`:
    `LADO_CONTAINER` set, not empty, not `0`, which only the image sets; never guessed from
    `/.dockerenv`; the one answer for the CLI, `lado doctor`'s LADO line and report (its
    `Server:` line says `in a container` instead of loopback or open to the network), and
    the UI server, whose `run.serve` and `lado ui` pass it to `run.Listening.of`), the
    installer (`installer`: by this
    LADO's `sys.prefix`, a uv tool with `uv-receipt.toml` or pipx with
    `pipx_metadata.json` of lado from an index, else None,
    also for an editable, folder, git or URL install of lado; its `command` installs
    exactly the version, `uv tool install lado==X` with the receipt's `--python` and
    `--with` again, never `uv tool upgrade`; it refreshes lado's index entry (uv
    `--refresh-package lado`, pip `--no-cache-dir` in pipx's one `--pip-args`), since a
    cached index may not have a release PyPI's JSON already shows; `lost` names what it cannot repeat; `binary`
    is `<prefix>/bin/lado`, never one on PATH), `installed_version`, the mark of an
    update that did not finish (`LADO_HOME/update.json`, `Pending`) and the result of the
    latest update, `LADO_HOME/update-result.json` (`Result`, `write_result`,
    `read_result`): the one exchange between LADO versions, format 1 in the module's
    docstring, which only grows (a reader passes over unknown keys and names a higher
    format as a newer LADO's). `remover` is the argv that removes this install, whatever
    its source (`uv tool uninstall lado` by `uv-receipt.toml`, `pipx uninstall
    lado<suffix>` by `pipx_metadata.json`, else None), for `lado uninstall`. Tests:
    `LADO_UPDATE_INDEX` (a local file instead of PyPI), `LADO_UPDATE_INSTALLER` (an
    installer's argv, given the version as its last argument), `LADO_UNINSTALL_REMOVER`
    (the remover's argv) and `LADO_UPDATE_PREFIX` (the install's prefix instead of
    `sys.prefix`).
  - `telemetry.py`: LADO's own errors and, with the human's yes, usage statistics
    (openspec change usage-telemetry, docs/telemetry.md); standard library and
    `lado.state` only at its top (every hook imports it). `record(where, exc, ...)` is the
    one capture of an unexpected exception (never raises; `state.SchemaError` is none): a
    JSON line in `LADO_HOME/errors.jsonl` (mode 600; time, version, where, type, message,
    traceback, session, agent, and the scrubbed form's `chain`, `stack`, `fingerprint` and
    `provider`, which a bug report reads; LADO 0.37's lines lack them, and so does a line
    whose `scrub` failed: that line is still written and nothing of it queued, and the
    scrub's failure is an error of its own at `telemetry:scrub`, `SCRUB_FAILED`, once,
    `_scrubbed`), and, only while sending is on, a scrubbed event in
    `LADO_HOME/telemetry/outbox/` (`scrub`: types, LADO's own frames as
    `lado/<file>:<function>:<line>`, others `<external>`, `where`, provider, `fingerprint`;
    never a text, path or name), at most `OUTBOX_MAX` (200), further ones counted in
    `dropped` (at most `DROPPED_MAX`). `where`: `cli:<command>[ <sub>]` (`cli._where`),
    `hook:<neutral event, else native>`, `mcp:<tool>` (`mcp_server._Server.call_tool` on
    the SDK's `UnexpectedToolError`), `loop` (`loop.RepeatedErrors`, once per new error;
    the feed's `server:feed`), `server:<route template>` (`app.py`'s handler of
    `Exception`, the 500 as before). `bounded_append` writes `errors.jsonl`, `hooks.log`
    and `loop.log` (renamed to `<name>.1` over `JOURNAL_MAX`, 1 MiB); `rotate` bounds
    `server.log` at a background server's start and `trim` (copy, then truncate in place:
    the server's output has `O_APPEND`) while it runs (`server/run.housekeeping`, at its
    start and every `KICK_EVERY`). `state()` is a `State`: the stored choice
    (`telemetry/consent.json`, `choose`, `FIELDS_VERSION`), `off_by` (`DO_NOT_TRACK` set
    but `0` or empty, `LADO_TELEMETRY=0`), `endpoint` (`PROJECT_TOKEN`, or
    `LADO_TELEMETRY_URL` with `TEST_TOKEN`); `on`, `ask`, `chosen`, `new_fields` (of
    `FIELDS`, which docs/telemetry.md lists, a test keeps both the same). `kick` (cheap, no
    network, never raises) starts a detached `lado telemetry send` when sending is on,
    something is due (no report in `REPORT_EVERY`, or a queued error) and no try in
    `RETRY_AFTER`: `cli.main` after every command but `hook`, `mcp`, `loop`, `telemetry
    send`, `update` (which starts nothing after its installer), `stats` (which promises to
    send nothing), `server` while it serves
    (it kicks in its housekeeping; one at its exit could make LADO_HOME again after an
    uninstall stopped it; `server stop` kicks) and `uninstall` (which also records no
    error: either would make the deleted LADO_HOME again), `doctor` included;
    the session loop every `KICK_EVERY`; the UI server's housekeeping. A hook only
    queues. `sender_ended` waits for that lock (`lado uninstall`, before it deletes
    LADO_HOME). `send` (a flock, `send.lock`; a second one exits) is the only code that goes to
    the network: `_build` (`_expire` drops errors older than `OUTBOX_MAX_AGE`; `report`
    counted from lado.db's `usage` table by `state.usage_counts` from the last report,
    so a forgotten session still counts, at most
    `REPORT_MAX_WINDOW` back, never stored; `_groups`, PostHog's `$exception` per
    fingerprint), `_post` within `SEND_TIMEOUT` per operation, the whole try within
    `SEND_DEADLINE` (`_deadline`, SIGALRM: DNS too; `_Deadline` is a `BaseException`, so
    no `except Exception` of the build swallows it; the agent CLIs' `--version`, in
    daemon threads, get `PROVIDERS_WAIT` of it and are killed by their own timeout then,
    `doctor.provider_status(..., timeout)`, as nothing kills them after the sender ends),
    silent; a try with nothing to post leaves
    `sent.json` as it was; a failure keeps everything and
    its reason in `telemetry/sent.json` (`last_sent`, `status_lines`), a 2xx removes only
    the files it sent; the sender's own bug is `_journal_only`. `preview` is what `lado
    telemetry show` and `GET /api/telemetry/preview` show. `ask_if_needed` is the question
    of `lado start` and `lado ui` (both ttys, not in an agent).
  - `self_update.py`: `lado update` for the CLI and the UI alike (`cli.cmd_update` only
    asks and prints). `refusal` is the one answer to "can this LADO update itself now"
    (inside an agent, in a container, an update running, no installer, in that order), the
    CLI's and the API's `can_update`; the CLI and `POST /api/update` refuse a container's at
    once, stopping nothing and before PyPI (the container's main process is the UI server,
    whose stop would end it), with the reason alone: no command (the API's `by_hand` is
    empty there).
    `plan` is what an update would do (the sessions `runtime.session_status` says run, also
    with the loop down, those whose tmux is gone, the UI server; `print_plan`,
    `print_by_hand`, the API's `UpdatePlan`). `run` holds an exclusive flock on
    `LADO_HOME/update.lock` (its pid in it; `take_lock`, which `lado uninstall` takes too)
    for the whole update, so a second one, from the CLI or the UI, is refused at once; only
    then it truncates `LADO_HOME/update.log` (mode
    600), where each line it says and the output of each command it runs go too, the UI's
    login token cut out (`lado ui` prints its link), and writes the result `running` (mode
    600 too). A look at the lock (`running_pid`, `refusal`) takes it shared, so two looks
    at once never see each other as an update. It writes update.json, stops
    each session with `runtime.stop_session` and waits for its loop's lock
    (`loop.wait_stopped`; one that does not end stops the update before the installer, and
    the sessions are resumed), stops the server, backs up lado.db with SQLite's backup API
    to `LADO_HOME/backups/lado.db.<old version>` (one backup kept), runs the installer,
    checks `<prefix>/bin/lado --version` and resumes with that binary's public commands
    (`lado start <repo> --name <s> --no-attach`, `lado ui --no-open [--host H] --port P`;
    `--host` only for another than 127.0.0.1, which a LADO before 0.20 lacks). It rolls
    back only when the new version itself is bad: a wrong `--version`, or the UI server,
    when one ran before, does not come up on it (`lado ui` fails, or `/api/health` names
    another version). The rollback stops what the new version started, waits for those
    loops (one that does not end: `rollback_failed`, lado.db untouched), reinstalls the old
    version with the same installer and checks its `--version`, only then restores lado.db
    into the live file by the backup API, only when its `user_version` moved, and resumes on
    the old version. A session that does not resume is `partial`, never a rollback; a failed
    installer resumes on the old version (`failed`). After the installer the old process
    starts nothing of its own (`providers.lado_command`) and imports nothing more (all its
    imports at its top; a test forbids imports after the installer). update.json is removed
    when every step worked, and by `unfinished` once none of its sessions is stopped; while
    one is, `lado ls` and `lado update` name them with their `lado start`. Sessions on
    another tmux socket are not seen (the plan says so). `start_detached` is the UI's way:
    `lado update --yes <to> --id <id>` of this LADO in its own process group, its lines only
    in update.log (`--id`, hidden from the help); one that ends before it starts writes a
    `failed` result of its id with no log (`not_started`), unless another update holds the
    lock, so the page waiting for that id learns why.
  - `uninstall.py`: `lado uninstall` (`cli.cmd_uninstall` only refuses inside an agent,
    asks and prints; `main` runs it without `migrate_if_safe`). A `LADO_HOME` that is not
    there is never made (`state.home_path`; `state.home` makes it): only the program is
    left to remove. `plan` reads only: it
    refuses while an update runs and on a newer `lado.db`, reads the sessions of an older
    one read-only (`name`, `repo`, `stopped_at` when there), judges each worktree under
    `.lado/worktrees/<session>/` and branch `lado/<session>/*` of their repositories by
    finish's rule (`runtime.work_of`, `runtime.keeps_work`), and guards `LADO_HOME`
    (deleted only when it is `~/.lado` by real path or holds `lado.db`, never `/`, the home
    folder or above it; such a folder is never walked). `run` holds the update's lock
    (`self_update.take_lock`), stops the UI server, `runtime.stop_all` (which migrates an
    older `lado.db`), waits for each loop (one that does not end stops it before any
    repository or file), closes the viewers and kills LADO's tmux server when no session is
    left on its socket (`tmux.kill_server`); then judges the work again, removes what
    goes (`runtime.remove_work`), drops `.lado/worktrees`, the exclude line
    (`runtime.include_worktrees`) and an empty `.lado/` once no worktree is left, deletes
    `LADO_HOME`, and, for the default home only, runs `update.remover` last through
    `self_update.command`; after it nothing is imported (a test forbids it). Output on
    stdout only, no log; exit 0 when each step of the plan was done. `--keep-data` stops
    and removes the program only.
  - `runtime.py`: starts agents in tmux (worker = own git worktree and branch) and delivers
    messages to them. Whether a folder can hold a session is `check_repo` (its repository's
    root, or why not: a `FolderProblem`, a `LadoError` with a `kind`, `missing`,
    `not_folder`, `no_git`, `git_broken`, `not_repo`, `git_refused`, `no_commits`, the
    first that holds in that order, and a `Hint`, a sentence and one command, for `no_git`,
    `git_broken`, `not_repo` and `no_commits`, by `platform.system()`; the CLI prints it on
    the line after the reason, the UI's folder check gives both), asked by `start_session`
    and the UI's folder check. `not_repo` is only git's own "not a git repository" (its
    `rev-parse` runs with `LC_ALL=C`); another failure is `git_refused` with git's line.
    `outside_repos` (`OUTSIDE_REPOS`) is the one rule of the warning for a session folder
    outside `LADO_REPOS` in LADO's container (`update.in_container`; the host sees only
    that folder), by real paths, never a refusal and none outside a container: the UI's
    folder check (`FolderInfo.warning`), the clone's target (`CloneTarget.warning`) and
    `start_session`'s warnings, new and resumed. `git_version` (`git --version` on this process's PATH, no cache) is the one look at
    whether git runs, also `lado doctor`'s and the System panel's; `git` and
    `gitcache._git` turn a git that cannot run into their usual errors (the text of a
    missing one is `gitcache.not_found`), and `providers/gitpaths` reads it as outside
    git. A repository's current branch (`branch`,
    None on a detached HEAD) and its origin's URL (`remote`) are read next to `git`; a
    remote reaches the API only through `public_remote` (no userinfo but an ssh:// user;
    the scp form and a local path as they are). `start_session(resume=...)` takes what
    the caller means: `False` a new session (`SessionExists`, with that session's status
    and folder, when the name is taken), `True` a resume (`NoSuchSession` for an unknown
    name), `None` either, as `lado start`; `first` (a `FirstInput`, only with
    `resume=False`) copies its records into the new session (`artifacts.copy_record`) and
    queues the supervisor's first message from `lado` with the copies attached, the copies
    undone with the session; `prompt` (`check_prompt`, refused before anything changes),
    for a new session and a resume alike, queues the human's first message after LADO's
    (docs/design/agents.md). `start_approved_session` is the supervisor's
    `start_session` tool (docs/cli.md, Supervisor-started sessions). No provider is the default: a new session
    without one takes `suggested_provider(repo, installed)`, a `Suggestion` (provider and
    reason, `LAST_SESSION` or `ONLY_INSTALLED`; `line()` is what `lado start` prints as
    `provider: ...`): the provider of the folder's last session (`state.last_session`) if
    `installed`, else the only one installed, else none, and the start refuses with the
    installed ones and `--provider NAME`, or every install hint when none is. `installed`
    is the caller's `shutil.which` (never `--version`): for that choice `start_session`
    resolves the agents' environment first and looks on its PATH (a provider given or
    stored, and its permission mode, are checked before the login shell runs); the UI's
    folder check looks on the server's. A resume keeps its stored provider. The commands
    the session's kits expect are looked for on the agents' PATH by `_check_commands` in
    `start_session` (new and resumed) and `spawn_worker`, after the agents' environment is
    resolved and before anything changes; a missing one refuses the launch
    (`kits.commands_error`). `stop_preview` and `forget_preview` say what a
    stop or forget would do now, refused alike; `stop_session` and `forget_session` use
    them. So does `finish_worker` with `finish_preview`, which goes by `work_state`: where
    a worker's branch stands against the repo's current branch and what its worktree has
    not committed (the UI's Agents tab shows both). A start or spawn that fails is undone
    step by step (`_undo`: the session stored or the worker added, its window, config,
    worktree and branch): every step runs, also after one that fails, the cause stays the
    error raised, and a step that fails is noted on it (`__notes__`; the CLI and the MCP
    tools print the notes after the error) and written to `LADO_HOME/loop.log`
    (`loop.log`).
  - `clone.py`: a repository from its git URL (openspec change clone-from-url), for `lado
    start <git-url>` and the UI server's clone jobs alike, which print only what it says:
    `is_url` (`https://`, `http://`, `ssh://`, `git://`, `file://`, or the scp form only
    with a user; anything else, `/srv/app.git` too, is a folder), `Address` (host and path
    by which two URLs are `same_repo`; scheme, user and port aside; local ones by real
    path), `repos_folder` (the one reader of `REPOS`, `LADO_REPOS`, the folder of the
    human's repositories that LADO's image sets: `~` expanded, None when unset, empty or
    not absolute; read at each call), `default_folder` (`default_parent()`/<repo>: the
    repositories folder, else `DEFAULT_PARENT`, `~/lado`), `check_target` (a
    `Target`: `new`, `empty`, `same_repo`, `other_repo` with a free `~/lado/<owner>-<repo>`
    beside it, `not_empty`, `not_folder`; only `CAN_CLONE` lets a clone start, and LADO
    changes nothing in a folder of another state: no clone over it, no fetch, no branch
    switch), `list_branches` (one `git ls-remote --symref`, within `LIST_TIMEOUT`; a
    `Remote`, its default branch first) and `clone` (one branch, into a temporary folder
    `.<name>.clone-<random>` beside the target, renamed onto a missing or empty target only
    once git succeeded; a cancel, a failure or an exception, Ctrl-C too, ends git's process
    group, SIGTERM then SIGKILL after `STOP_WAIT`, and removes the temporary folder;
    `Progress` from git's `\r` lines). Each git process of a listing or a clone runs with
    no terminal and no prompt (`start_new_session`, stdin closed, `NO_PROMPT`:
    `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS` empty, `SSH_ASKPASS_REQUIRE=never`, `GCM_INTERACTIVE=never`,
    `LC_ALL=C`): a missing credential is a failure, never a wait; LADO uses the access the
    machine has and keeps no password or token. A failure is a `CloneError` (a `LadoError`
    with `kind` and a `runtime.Hint`) by git's words, `KINDS`, the first that matches
    (`failure`: `cannot read|clone <url>: <reason> (<git's line>)`), a URL in any text only
    through `runtime.public_remote`; git missing or not running is LAD-5's `no_git` /
    `git_broken`, a folder LADO may not look at or write in `no_access`, a URL that names
    no repository (no default folder) `no_repo_name`. `ABANDONED` and `KEPT` are the server's clone jobs' times.
  - `scratch.py`: a session from scratch (openspec change start-from-scratch), for `lado
    start --new`, the UI server's From scratch and `lado doctor` alike, which print only
    what it says. `names` (the text trimmed; refused empty, over `runtime.MAX_TITLE`, with
    a hidden character, or with no Latin letter or digit left for a folder; Cyrillic by
    the one table `CYRILLIC`, Latin letters without accents by NFKD, then `runtime.slug`;
    the title is the text unless it is the name), `default_folder` (`clone.default_parent()
    /<name>`), `check_target` (a `Target`: `new`, `empty` with nothing but `FINDER`'s
    `.DS_Store`, `inside_repo` with the repository's root, `not_empty`, `not_folder`; the
    path's nearest existing folder decides for a new path; only `CAN_START` lets a fresh
    start go on; `make` refuses each other state with its hint: LAD-5's `NOT_REPO_HINT` for
    files, `lado start <root>` inside a repository), `author_problem` (git's `user.name`
    and `user.email` where the folder would be, outside any repository the global and
    system config; no author is a refusal with the `.env` hint in LADO's container, the
    `git config --global` one elsewhere; LADO sets no author) and `make` (the checks again,
    the name as `runtime.check_name` first, then the folders, `git init`, the branch of
    `init.defaultBranch` else `main` by `symbolic-ref`, one empty commit `Start from
    scratch` with no signing, no hooks (`core.hooksPath` to the null device and
    `--no-verify`), no prompt and stdin closed; a failed step removes the folders it made,
    or the `.git` of an empty folder it was given). A refusal is a `ScratchError` (a
    `LadoError` with `kind` and a `runtime.Hint`); git missing is LAD-5's `no_git`.
  - `providers/`: agent CLIs behind one interface (`base.py`: `Provider`, `Capabilities`,
    `Launch`, neutral hook events, `Event.key` for `WAITING` and `RESUMED`; each provider's
    `EVENTS` maps its native events; `claude.py`: Claude Code, its role in `prompt.md` of
    its config folder (`--append-system-prompt-file`); `opencode_family.py`: the
    base of OpenCode and its fork Kilo, holding only what is checked on both (each claim
    names the CLI and version), with `opencode_plugin.js`, the plugin that runs LADO's
    hooks, and one config dict per agent, written to its config folder and passed in the
    environment (`env`, the subclass's: `KILO_CONFIG_CONTENT`, `OPENCODE_CONFIG_CONTENT`,
    which win over the repo's own config); `kilo.py`: Kilo CLI and `opencode.py`: OpenCode,
    its subclasses, each with its own `TESTED_VERSION`, config file name, switches and
    permission rules; `codex.py`: Codex CLI, below; `gitpaths.py`: where a folder sits in
    its repository (`git_root`, `main_root`), shared by the providers whose CLI looks a
    folder's trust up by it). OpenCode and Kilo still read the user's global config and
    global skills (`~/.claude/skills`, `~/.agents/skills`; BACKLOG.md); LADO's keys go on
    top. Codex reads `~/.agents/skills` too, whatever its home. A provider writes the agent's config, returns its argv and env (and its
    `warnings`, `Launch.warnings`, told whoever starts the agent as a blocker's are) and
    translates its hook events; it gets the agent's environment as `AgentSpec.environ`
    (read only) and, for a kit's MCP server, the names of the variables it reads
    (`McpServer.env_vars`). The config goes in the agent's config folder, `LADO_HOME/agents/<session>/<agent>/`
    (`base.config_path`), which exists only while the agent runs: each launch writes it anew,
    and finishing a worker, an agent's end (`agent_ended`), `lado stop` (also `--all`),
    `lado forget` and a start or resume (what is left of the session's) remove it
    (`base.remove_config_dir`, `remove_session_config_dirs`); nothing of the CLI's own goes
    there but Codex's, whose home it is. `first_hook_blocker(cwd, env)` (a `Blocker`:
    `reason`, `warning`) says what its CLI will ask the human before any hook (How agents
    talk). Claude Code asks whether
    to trust the folder, read from `projects[<folder>].hasTrustDialogAccepted` in its global
    config (`$CLAUDE_CONFIG_DIR/.claude.json` or `~/.claude.json`, an older
    `<config home>/.config.json` first), by the repo's main root (a worktree's main repo) or
    a folder from `cwd` up to its git root, each by real path; only `projects` is read,
    nothing written; a config it cannot read is a `warning`. Codex CLI (`codex.py`): each
    agent's `CODEX_HOME` is its config folder, with a `config.toml` (mode 600) LADO writes
    with a small TOML writer (`toml_text`; a value it cannot write is left out with a
    launch warning): the role as `developer_instructions` (the base prompt stays), Codex's
    update check, subagents (`features.multi_agent`), analytics and feedback off, its shell
    snapshot off (`features.shell_snapshot`: it writes the agent's whole environment, a
    kit's MCP secrets too, into the home's `shell_snapshots/`), LADO's
    hooks with their `trusted_hash` (`hook_hash`, Codex's formula, pinned by a test against
    hashes Codex wrote; keyed by the real path of that config.toml), the MCP servers (`lado`
    `required` and its tools approved; each server's `env_vars` names every variable of the
    agent's environment, Codex's own included, as the other CLIs pass them all), a
    permission profile that
    lets the sandbox write the git folders but their hooks and config (else a worker cannot
    commit; not with `bypassPermissions`), and what it carries from the user's own Codex
    config (`CODEX_HOME` of the agent's environment, else `~/.codex`; read, never written;
    one it cannot read is a launch warning): `CARRIED` (model settings), the `projects`
    entry Codex goes by in the agent's folder, and the user's `hooks.state` entries of the
    repository's own hooks. Codex asks before any hook whether to trust a folder with no
    entry (by the folder, its project root, then its repository's main root, each by real
    path then as spelled; the first entry with a level decides, `untrusted` too) and to
    review the repository's own hooks (`.codex/hooks.json` and `[hooks]` of
    `.codex/config.toml`, the main checkout's in a linked worktree) it has no trust for:
    `first_hook_blocker` reads both from the agent's config.toml. Its argv is `codex
    --no-daemon` (else a background app server outlives the agent) with the first lines
    last. Codex's own login is not carried (BACKLOG.md). The provider is chosen
    per session (`lado start --provider`) and per worker (`spawn_worker(provider=...)`).
    Each provider lists the `--permission-mode` values it honours (`permission_modes`; the
    CLI help shows them); `lado start` (also a resume) and `spawn_worker` refuse a mode the
    agent's provider does not support, before anything is launched.
  - `tmux.py`: tmux calls, on a private server (`tmux -L lado`; `LADO_TMUX_SOCKET` overrides
    the socket name and is passed on to agents). A tmux that cannot run (not on PATH, not
    executable) is `TmuxMissing`, a `TmuxError` naming the PATH it was looked up on; the
    calls that read a failing command as a gone session or window (`has_session`,
    `window_names`, `popup`) raise it instead, so it never reads as "gone". `list_windows`
    (the session loop's window check) raises on any failure, also for a gone session,
    never an empty list. A window's name is its agent's: `new_session` and `new_window` set
    `allow-rename off` globally on LADO's server, so no program renames it, also when the
    user's tmux.conf allows that (a human's `rename-window` still would).
    `without_agent_vars` (`clean_env` for this process) drops a parent Claude Code's
    variables and the calling agent's LADO identity (`LADO_SESSION`, `LADO_AGENT`,
    `LADO_INSTANCE`; every other `LADO_*` stays) from every tmux call, the popup, a UI
    terminal, the session loop's start (`loop.start`) and an agent's environment
    (`agent_env.resolve`): a session the supervisor's `lado mcp` starts never runs as that
    agent. `runs._popup` keeps its `env -u`: the tmux server builds the popup's environment.
    `server_running` is the one look at whether a server runs on a socket (`list-sessions`;
    it never starts one). `new_session` sets `exit-empty on` (tmux's default) first in its
    chain and takes `before_attempt`, run before each attempt, also the one after
    `SERVER_ENDED`, and returns what it said: `runtime.start_session` passes
    `gui_session.ensure_server`. tmux.py knows nothing of macOS (a test: it does not import
    `gui_session`).
  - `gui_session.py`: where a process runs on macOS (docs/design/agents.md): `place()`, a
    `Place` (`other` but on a Mac, `gui`, `remote`: outside the graphical session while
    someone is logged in to it, `no-gui`, `unknown`) by its audit session's flags
    (`getaudit_addr` through ctypes, `flags_from`) and `launchctl print gui/<uid>`, never by
    its environment; `LADO_MACOS_PLACE` (gui, remote, no-gui; only tests, `tests/conftest.py`
    sets `gui`) replaces it on a Mac. `server_place(socket)`: the same of LADO's tmux server,
    by a probe it runs (`run-shell`, `PROBE` with `-I`: it imports nothing of LADO), None
    when no server runs (asked first, so it never starts one). `start_server`: a launchd job
    of `gui/<uid>` (a plist under `LADO_HOME/launchd/`, removed in any outcome; label
    `LABEL_PREFIX.<socket>.<pid>`) that starts tmux with `exit-empty off`, waited for
    (`START_TIMEOUT`), then booted out; the server stays. `ensure_server`: that, only from
    `remote` with no server; a failure is `LAUNCHD_FAILED`, a warning, and the server starts
    here instead. The texts (`OUTSIDE_GUI`, `NO_GUI`, `PLAN_REMOTE`) name no provider:
    `fill` puts in the titles and hints of `Provider.keychain_login`.
  - `agent_env.py`: where an agent's environment comes from (docs/design/agents.md): `resolve`
    (the login shell's, then the outside folder's, `outside`), and `command`, the window's
    command that runs the agent with exactly that environment.
  - `interpreter.py`: `run_module`, the one way LADO starts a process of its own with its
    own Python (`providers.lado_command`: hooks, `lado mcp`, `lado loop`, the popup, the
    UI server; the window command; the MCP secrets wrapper). LADO's own processes never
    import from the agent's cwd, a repository LADO does not control: `python -m` would put
    it first on `sys.path`, so a `json.py` or a `lado/` there would run inside LADO with the
    user's keys. A loader under `-c` drops it (`''`) before importing anything but `sys`,
    then runs the module as `-m` would. Not `-P` (3.11+ only) nor `-I`, which also drops
    PYTHONPATH and the user site, where a user's LADO may be installed. Never `-m` for one.
    Each such process pays for its imports: `lado.__version__` is read from the package's
    metadata only when asked for (`lado/__init__.py`'s `__getattr__`; use it as
    `lado.__version__`, never `from lado import __version__` at a module's top), and
    `cli.py` imports `doctor`, `update` and `server` only in the commands that use them
    (`tests/test_lazy_imports.py`).
  - `mcp_exec.py`: a kit's MCP server whose `env` refers to `${NAME}`: its value never goes
    on disk. `kits.ResolvedAgent.mcp_servers` checks each name is set in the agent's
    environment (else `KitError`, before the start) and gives the CLI the command
    `lado.mcp_exec --name <server> <templates> -- <command...>` (`wrap`, `run_module`), with
    only the literals in `env`; the templates are JSON in base64, so no CLI expands them
    (Claude Code expands `${VAR}` in a server's args, OpenCode and Kilo `{env:VAR}` and
    `{file:...}`). The CLI passes its whole environment, the agent's, to a stdio server
    (checked by hand: providers/claude.py, opencode_family.py; Codex passes only a few
    variables and those its `env_vars` names, so codex.py names every variable of the
    agent's environment there, never a value); the wrapper fills the
    templates from it (`expand`; an unset name is one line on stderr and exit 1) and execs
    the server. Only the standard library; `VARIABLE`, `references` and `expand` are the
    one parser of `${NAME}`, also kits.py's.
  - `text.py`: the one rule of a line of visible text (openspec capability visible-text):
    a character is hidden when its Unicode category is Cc, Zl, Zp or Cf, but U+200D ZERO
    WIDTH JOINER (`hidden`, `first_hidden`). A one-line field its writer gives is refused
    naming the first one (`named`: `U+XXXX NAME`; `refusal`, the words after `... one
    line`): the session's title, `send_message`'s summary, `ask_human`'s question and
    choices, `flow_advance`'s `note_summary`, `flow_start`'s `human_language`,
    `write_artifact`'s title and summary. A line
    LADO takes from the human's longer text is cleaned (`one_line`: Cf removed, the others
    a space), the whole text kept in the body whenever the line is not exactly it: the
    human's chat message and own answer (`runtime._human_text`), a gate's comment and a
    `lado flow-set` reason as the next step's note, a loop limit's cancel reason, an
    uploaded file's title. No other copy of the check. Only the standard library.
  - `terminal.py`: an agent's terminal for the UI (design in
    [docs/design/ui.md](ui.md), section Terminal): `open` (a viewer tmux session
    with the agent's window linked in and a `tmux attach` on a pty), `NoTerminal`,
    and `close_viewers`, which `lado stop` and the UI server's start use; viewers are found
    by their tmux labels (`@lado-viewer`, `@lado-home`, `@lado-session`) only. Never a
    read-only tmux client: tmux would refuse LADO's own `send-keys` while one is attached.
  - `kits.py`: kits (agent roles, skills, MCP servers, flows): lookup (the installed kits,
    then built-in; no folder: a repository's own folders are never read for kits, so the
    kits are the same for every session and folder), `dependencies` (`lado`: the
    oldest LADO the kit runs with; `skills`: skill packs by `<git-url>@<tag|commit>` or a
    folder relative to the kit), `supervisor` (the kit's agent that leads a session; the
    agent name `supervisor` is reserved for it), `--without` (`kind:name@kit` in one kit
    before the kits combine, `kind:name` in the whole session after; the order is in
    `resolve`'s docstring; `agent:<name>` of a kit's supervisor is read as `@` its kit,
    `_supervisors_by_kit`, as older LADOs stored it), the session's lead (`Environment.lead`, kept apart from the
    worker roles: the one kit supervisor, else the built-in default kit's supervisor, with
    `Environment.warnings` for how the kit supervisors that do not lead are used; `lead_line`
    says who leads), the lead skills of the built-in lead (`Environment.lead_skills`, built
    only from `Environment.kit_supervisors`: each kit supervisor that does not lead, but
    the default kit's, with the `--without` items applied; its `skills:` is checked as if
    it led, so a skill its kit does not have is an error; a skill `lead-<kit>` the lead
    would get besides is refused with both ways out),
    a name in two kits refused with both ways out (`KitError.switch_off`), `expects.skills`
    (skills another kit of the session must bring; `resolve(expected=REQUIRE)`, the
    default of every session path, refuses a session where none does or `--without`
    switches one off, and `ASSUME`, only for `lado kits check` and `lado kits show`, takes
    them as visible to the kit's agents), `expects.commands` (CLIs the kit's agents need,
    names of `COMMAND`; `Kit.expects` is an `Expects` of both lists; `missing_commands`
    looks for them on a PATH it is given, `commands_error` is the one text of a launch
    refused for them; `EXPECTS_SINCE`, per key, the LADO `warnings` asks a kit to need), a
    flow state of
    a kit's supervisor read as the lead's (`kits.LEAD`), validation, and the installed kits:
    rows of the `kits` table in lado.db (`state.InstalledKit`; `installed_kits` gives each
    as a `Found` with its row in `Found.installed`), which `lado kits add/update/remove`
    write: a kit from git by address, tag and the tag's commit at install time, read from
    `gitcache.clone_dir(address, tag)` (not kept), or a folder read in place; `marketplace`
    is the `-m` it was added from, else NULL, never guessed. An installed kit's folder name
    need not be its name (`load` with `named_folder=False`), but its kit.yaml must give the
    row's name, else `KitError` with `remove` and `add`; a missing folder is a `KitError`
    with the same way out, no network. Its origin (`Found.link`, `Kit.origin`,
    `Kit.source`) is the row's. A kit is one repository with kit.yaml at its root;
    `version` is required of every kit and must agree with the tag `vX.Y.Z` it is installed
    by (a commit, a branch or `kits/<name>/` is refused). `plan_add` / `plan_update` say what
    an add or update would do (an `Install`: tag, commit, source, marketplace, MCP servers,
    whether to ask, warnings such as a moved tag; the clone made, nothing installed) and
    print nothing; `install` writes the row (an update keeps `marketplace` and
    `installed_at`, sets `updated_at`); `outdated` compares each installed kit with its
    remote's tags. `LADO_HOME/kits`, where older LADOs kept links, is never read: while it
    is there, `legacy_hint` (printed by `lado kits` and in "kit not found") gives the
    `lado kits add` of each entry in it (`@<tag>` for a version tag; none for a multi-kit
    `kits/<name>/` link) and `then delete`; LADO never changes it. `load` never uses the network (a git pack not in the cache
    yet is `Pack.skills is None`); `fetch` clones it; `resolve` builds an `Environment` only
    from fetched kits. An agent sees the session kits' own skills, its own kit's packs and
    the packs of kits without agents (`Environment.shared`, `.private`). A provider gets an
    `AgentSpec` (prompt, skill folders, MCP servers, and `read`: folders the agent reads
    without asking that are no skills: Claude Code `--add-dir`, Kilo and OpenCode
    `external_directory`), never the kit itself. `builtin_kits/`:
    kits shipped with LADO (`default`: supervisor + worker). LADO's own instructions to
    agents stay in `runtime.py` and are appended to the role. `LADO_HOME/sources.yaml` of
    older LADOs is not read; while it exists, `migration_hint` says how to move.
  - `gitcache.py`: the git cache: one clone per (address, tag or commit) in
    `LADO_HOME/cache/<repo>-<hash>/<quote(ref)>`, made in a temporary folder and renamed;
    a clone that is there is never fetched again; a branch is refused. Packs and
    `lado kits add/update` use `fetch_pinned`. Nothing cleans it yet. `remote_tags` (`git
    ls-remote`, an annotated tag's commit) is the one look at a remote's tags per add,
    update or outdated; `latest` sorts `VERSION_TAG`s by semver precedence (a pre-release
    only with `pre`). `clone_branch` and `refresh` keep a marketplace's clone on its main
    branch. All of LADO's git commands for kits and marketplaces are here.
  - `marketplaces.py`: kit marketplaces, git repositories with `marketplace.yaml` at the
    root (`kits:` kit name -> git address), kept in the `marketplaces` table (`list_`,
    `add`, `remove`, `set_enabled`, `update`); the official one is a row made with the
    table, no url (`OFFICIAL_URL`), never removed, only disabled. Its clone in
    `LADO_HOME/marketplaces/<name>/` is a cache: made on first use, made again when its
    origin is another address. `resolve` finds a kit's address for `lado kits add -m`
    (`kits` clones when there is no clone; only for the CLI). Never the network: `listed`
    (the list of the clone there is, None without one), `index` (the clone's `index.json`,
    format version 1 in the module's docstring and docs/marketplaces.md: entries of the listed kits,
    only `address` required, unknown keys passed over, a higher `index` "needs a newer
    LADO"; what does not agree is the `Index.problem`), `available` (each kit of the
    enabled marketplaces with a clone, `Offer`). `update_each` updates one by one, a failure
    is that marketplace's text and the others go on (the CLI and the API); `kits_from` the
    installed kits added from one (`lado marketplaces remove` names them).
    `MarketplaceError`; it does not import `kits`.
  - `flows.py`: the flow format (`flows/<name>.yaml` in a kit: work, gate and end states;
    a work state's optional `produces` lists the artifacts its step must write, a work or
    gate state's optional `reads` the run's artifacts its step or the human at the gate is
    shown, by their latest records; both checked against `ARTIFACT_NAME`, the one pattern
    of an artifact's name, which `artifacts.NAME` is; a name in `reads` must be one some
    state produces and not one of its own `produces`; the docstring has the rule of
    artifact or note) and its validator (`parse`; `needs`, the states of LADO 0.26 and
    older, is refused with `NEEDS_REPLACED`, also in a run's snapshot), and `lint`, the
    graph rules a flow loads with but should not break: a state no end can be reached
    from, a cycle with no `max_visits` state and no gate on it, a name in `reads` that no
    state before the reading one produces; only `lado kits check` fails on them
    (`kits.lint`), never loading a kit, `lado kits add` or a run's snapshot. `runs.py`: flow runs: start (own worktree and branch, shared by the
    run's workers), step messages from `lado`, `flow_advance` (refused while a `produces`
    artifact has no latest record of the state's current visit, `artifacts.produced`, by the
    name the caller writes it with; fail closed on the store's errors; the counted records
    attached to the step's note first; docs/design/artifacts.md, Flows), loop limits, gates (the run
    waits for the human), end (finish workers, remove the worktree if merged), cancel and
    `lado flow-set`. A run keeps a snapshot of its flow. A step whose `agent` is
    `kits.LEAD` (`supervisor`) is the session's lead's (`runs._lead_step`, by the name in
    the snapshot, never by the supervisor's role): the step of a kit's supervisor, and so
    also `agent: supervisor` in a kit with no supervisor of its own. A waiting run has one open gate
    record (`state.Gate`); `runs.answer` is the only way to answer it, called from
    `lado answer` and the UI server's API, never from an MCP tool; the answering surface
    (popup, CLI, UI) stays outside that core. A gate that opens asks the lead for its
    recommendation (`runs._ask_recommendation`, `runs.recommendation_request`; How agents
    talk), and `runs.resume` asks again for each open gate without a given one.
  - `mcp_server.py`: MCP tools for agents (`send_message`, `ask_human`, `read_messages`,
    `list_agents`, `flow_advance`, `flow_status`, `write_artifact`, `read_artifact`,
    `list_artifacts`; `send_message`, `ask_human` and `flow_advance` take `artifacts` to
    attach; `read_artifact` returns an image as MCP image content, the SDK's `Image`, after
    its facts, when `artifacts.read` gives it as `Shown`; the supervisor also gets
    `spawn_worker`, `finish_worker`, `flow_start`, `flow_cancel` and `start_session`,
    `COMMAND_TOOLS`, unless it is read-only: then they are not listed, and a call of one
    is refused as `role <r> is read-only: <tool> is not available`; and `recommend`, the
    lead's own, read-only or not: `runtime.recommend`). No tool answers a gate or a
    question.
  - `artifacts.py`: artifacts, named documents of a session (contract:
    [docs/design/artifacts.md](artifacts.md)); the only module the rest of LADO
    calls for them (MCP tools, CLI, runs, runtime, doctor, the UI server): names (`NAME`,
    full names parsed by the last `/`; `/<name>` the session's, for a run's worker too),
    scopes and the rights to write (`_writable`), the name an agent reads an artifact by
    (`as_read`, the one function for what agents are shown), limits (`MAX_SIZE`,
    `MAX_HUMAN_FILES`, and the images an agent is shown: `AGENT_IMAGES`, `IMAGE_LIMIT`,
    `IMAGE_MAX_SIDE`, each provider's number in the comment beside them), media types by
    one extension table (`EXTENSIONS`, `is_text`; `PREFERRED_EXTENSION`, one per type,
    for a download's `file_name`), the human's files (`upload`, the only writer for
    `human`: always the session's scope, named by `upload_name`, the same file again
    writes nothing), reading (`read`, an image within the limits as `Shown`, its size
    from `images.py`, the header read by the standard library; `listed`, `find`,
    `of_session`, and by id only of the session's: `of_artifact`, `of_record`),
    attachments (`resolve_attachments`, with no agent for the human; `attached`, the one builder of an
    `Attachment`, its artifact and record, with `changed` only when asked,
    `with_changed`; `read_attachments` for read_messages; `attached_line`) and the
    `Store` protocol (with `artifact(id)`), whose backend `store()` chooses. `artifacts_local.py`: `LocalStore`,
    the one backend: rows through `state.py`'s artifact functions, content in files by hash
    under `LADO_HOME/artifacts/<hh>/<sha256>` (a temporary file, fsync, rename; a file no
    record refers to is removed by `remove_session` only after `ORPHAN_AGE`, an hour).
    Nothing else touches the artifact tables or that folder.
  - `hooks.py`: neutral hook logic: agent status, handing over queued messages and, at a
    turn's end, the forgotten-reply check (docs/design/agents.md).
  - `state.py`: SQLite state in `~/.lado/lado.db` (`LADO_HOME` overrides the directory).
    Schema changes: bump `SCHEMA_VERSION`, add a step to `MIGRATIONS` and update
    `tests/agent_helpers.previous_schema` (it undoes the last step). `state.connect()`
    never migrates: it makes a missing lado.db, and another schema version (older, newer,
    incompatible) is a `state.SchemaError` with nothing changed, so no hook, `lado mcp`,
    session loop or UI server can migrate under a running session. Only `state.migrate()`
    applies `MIGRATIONS`, called by `runtime.migrate_if_safe` (the CLI before each command
    but `doctor`, `mcp`, `hook`, `loop` and `stop`), which refuses while a session runs (not
    stopped, tmux session alive on this socket), names them and asks for `lado stop --all`,
    and by `runtime.stop_session` and `stop_all` (`lado stop`, docs/cli.md), all through
    `runtime._migrate`. Before its first step, inside its write lock, `migrate` copies
    lado.db by SQLite's backup API (`state.copy_db`, also `self_update.restore`'s; a
    connection of its own reads it) to `backups/lado.db.schema-<N>` (N the schema before;
    `.tmp`, then a rename), then removes every other `lado.db.schema-*` (one it cannot
    stays, no failure) and leaves `lado
    update`'s `lado.db.<version>`; it returns a `Migrated` (before, after, backup), which
    `_migrate` says on stderr (`lado: upgraded lado.db from schema N to M; its backup is
    <path>`, a container's `docker logs`). A backup it cannot write is `BackupFailed`,
    nothing migrated, a `LadoError`; a step that fails is `MigrationFailed`, the
    transaction rolled back, `runtime.MigrationFailed`: one message with the backup and the
    way back (in a container the image of the version run before,
    `ghcr.io/ladohq/lado:<that version>`, on the same home volume, else the LADO you had
    before) and `lado bug-report`, its cause journaled by `cli.main`, no traceback
    (openspec capability schema-migration). A LADO upgraded in
    place under a running session: that session's hooks write the SchemaError's text
    (`lado stop --all`, then `lado start`) to `hooks.log`, its tools return it as their
    error, its loop ends with it in `loop.log`, and the UI server answers 503. An older
    LADO refuses a newer database and asks to upgrade; the CLI prints the SchemaError. A message counts its pastes
    (`messages.attempts`) and can end `failed` (`messages.failed_at`); an agent keeps when
    its latest hook ran
    (`agents.seen_at`). From schema 13 a message has a `kind` (`message` or `question`),
    a question its `choices`, `free_answer`, `question_state` and `answered_by`, an answer
    or dismissal its `reply_to` and `choice`, and the human's message to an agent its
    `reply_state` (docs/design/agents.md). The `events`
    table records what each agent did (`spawned`, `status` changes via `set_status`,
    `mcp_ready`, `finished`, `turn_error` with the error, `ended` with why its process
    ended by itself, `blocked` with what its CLI asks the human before any hook) and what happened to each flow run (`flow_start`, `flow` transitions,
    `flow_end`, `flow_cancel`, `flow_set`, `gate_open`, `gate_answer`; their `run` column
    names the run) and the session's `session_stop`, `session_resume` and `session_gone`
    (a stop or resume found its tmux gone: written by `state.stop_session(gone=True)` in
    the stop's transaction, before the agents go, only for a session not stopped yet, at
    its last sign of life, `state.last_alive`: its agents' latest `seen_at`, else its
    latest event; the `session_stop` follows). The `notes`
    table keeps every note a run's step reported (`flow_advance`, a gate's answer,
    `lado flow-set`'s reason) with the state it was reported from and its kind: a
    `report` is a work state's own or the answer at an approval or choice gate; an
    `override` (a flow-set reason, from the state the run was in; an answer at a loop
    limit, from the state it kept the run out of) is kept but never taken for a state's
    report. From schema 15 a note is the record of its step: `actor`, `outcome` (none for
    a flow-set) and `target`, written by `update_run` from the transition (`state.Noted`);
    `state.run_notes` lists them (the UI's Flows tab). From schema 16 an agent keeps the
    request it waits for, `agents.waiting_for` (docs/design/agents.md; not in the API). Events, messages,
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
    statement, a change, since why it waits, `status_reason`, changes with `seen_at`), and
    each insert drops changes older than
    the latest `CHANGES_KEPT`. From schema 14 `events` is journaled too, key its id, but
    only inserts (`JOURNALED_OPS`) of a flow run's events (`RUN_EVENT`: `run IS NOT NULL`;
    a status event would double the journal); a trigger's condition is in `JOURNAL_WHEN`.
    A new table the UI shows gets its triggers in `JOURNALED`. From schema 17 the
    `marketplaces` table (name, url, enabled, updated_at; `state.Marketplace`) holds the kit
    marketplaces; the `official` row is made with it (in `SCHEMA` and in the migration),
    and its changes are journaled with session `''` (`JOURNAL_SESSION`); the feed sends them
    with a `MarketplaceInfo`. From schema 18 the `kits` table (name, address, tag, commit, folder,
    marketplace, installed_at, updated_at; a CHECK: an address with its tag and commit, or a
    folder) holds the installed kits, journaled the same way (session `''`, an
    `InstalledKitInfo`; each item only its own row and files). From schema 19 a message
    keeps the channel it was handed over by, `messages.channel` (`typed`, `hook_output`;
    NULL while pending and for a message to the human; docs/design/agents.md; not in the
    API). From schema 20 an agent keeps its planned resume after a transient turn error,
    `agents.resume_at` and `agents.resumes` (docs/design/agents.md; not in the API). From schema
    21 the local artifact store's tables `artifacts` and `artifact_records` (each with its
    session, journaled with it; no foreign key to `sessions`: `lado forget` removes them
    through the store first), used only by `artifacts_local.py` through `state.py`'s
    artifact functions, and LADO's `attachments` (a message's or a note's, by position: the
    store's artifact and record ids, no foreign key to them; not journaled), written in the
    transaction of their message (`queue_message`, `add_question`) or note (`update_run`).
    `TO_READ` is the one condition of a message with something to read (a body or an
    attachment), for `read_messages` and `UNRECEIVED`; a `Message`, a `Note`
    (`NOTE_COLUMNS`) and a `Gate` (`GATE_COLUMNS`, its note's) count their `attachments`,
    so only a row that has some asks for them. From schema 22 a gate keeps the note that
    led to it, `gates.note_id` (`GATES_NOTE`): `update_run` writes the note first and the
    gate after it in the same transaction; a gate's attachments are that note's
    (`runs.gate_attachments`, `gate_artifacts`), and `runs.gate_reads` leaves the artifacts
    that note carries out of those the gate reads, so `lado answer` and the UI show each
    once. Schema 23 changes data only (`closed_runs_without_needs`, a callable step of
    `MIGRATIONS`): an ended or cancelled run's snapshot drops `needs`; an open run's stays
    and shows its problem (`runs.SnapshotError`), a snapshot that is no flow's JSON too.
    From schema 24 a message keeps when its turn-end hook printed it, `messages.printed_at`
    (only for a provider with `output_taken_when_printed`; docs/design/agents.md; not in the API).
    From schema 25 an agent keeps whether its role is read-only, `agents.read_only`
    (`AGENTS_READ_ONLY`; written at each launch, resume included; docs/design/agents.md, Read-only roles),
    and the events `repo_changed` (detail: the changes, one per line) and
    `repo_check_failed` (detail: why) are its turns' repository checks.
    From schema 26 a gate and a question (`RECOMMENDATION`, six columns on `gates` and
    `messages`) keep the lead's recommendation: `recommendation_state` (NULL never asked,
    `asked`, `given`, `missing`; `REC_*`), its text, `recommended_choice`,
    `recommendation_disagrees`, `recommended_at` and `recommendation_request`, the id of
    the request from `lado` (NULL for a notice). `ask_recommendation` queues the request
    and marks `asked` in one transaction, `recommend` is one conditional update on an open
    item, every transaction that closes a gate or a question drops its request still
    `pending` (`_drop_requests`), `recommendations_missed` is the lead's turn-end check, and
    the lead's end and a stop mark every `asked` one `missing` (`_missed`). The existing
    triggers journal them: the feed sends the gate or message again.
    From schema 27 the `usage` table (`USAGE`: kind, key, provider, agrees, created_at; no
    session column) holds one anonymous row per counted fact (`USAGE_KINDS`): a session
    added, a resume, an agent spawned (key `<role>@<kit>`, with its provider), its process
    ended by itself, a turn error (key the error's kind), a run started, ended or cancelled
    (key `<flow>@<kit>`), a gate opened (its kind) or closed (its answer, and whether it is
    the lead's recommended choice; none when closed by no answer of the human,
    `GATE_UNANSWERED`: `cancelled`, `overridden`), a question to the human, a message failed or dropped.
    Only `USAGE_TRIGGERS` write it (one per `USAGE_SOURCES` entry, on `sessions`, `events`,
    `gates` and `messages`), in the writer's transaction; the migration fills it once from
    the rows kept (`usage_from_history`, the same `USAGE_SOURCES`), and `lado forget`
    leaves it, so the counts outlive their session. The `spawned` event's detail names the
    role's kit (`spawned_detail`: `role <r>, kit <k>, provider <p>`); an older one is keyed
    `<role>@?`. An agent's provider in `ended` and `turn_error` is its latest spawn's (a
    stop forgets the agent). A trigger stays in lado.db as it was made: a new count, or a
    change of what one reads (`spawned_detail`'s form, `base.error_line`'s), is a migration
    step that makes it again (tests/test_usage.py compares both forms). `usage_summary`
    (a `Usage`: per kind by key, provider, both, and agreement) and `usage_start` are
    `lado stats`'; `usage_counts` the report's.
    From schema 28 a session keeps an optional title, `sessions.title` (`SESSIONS_TITLE`;
    NULL for none; `state.set_title` stores it as given): a label for the human over its
    name, which stays its identifier. `runtime.check_title` (and `set_title` through it)
    is the one rule of what a title is (trimmed, one line with no hidden character, `text.py`, at most
    `runtime.MAX_TITLE`, 80, characters; empty or equal to the name is none; a bad one is
    refused, never cut), for `lado title`, `PUT /api/sessions/{name}/title` and a new
    session's `runtime.start_session(title=)` (a fresh start's; a resume refuses one) alike;
    `SessionInfo.title` carries it, through the existing journal of `sessions`, and
    `Limits.max_title` the limit.
    From schema 29 a session keeps whether the container's stop stopped it,
    `sessions.resume_at_start` (`SESSIONS_RESUME_AT_START`; not in the API):
    `state.stop_for_container` marks every session not stopped as `stop_session` does, with
    the mark, in one transaction (its `session_stop` detail ends `; the container
    stopped`), `resume_session` clears it in the update that takes the session, and
    `give_up_resume` clears it, stopping a session not stopped (`session_gone` first);
    `resumable` lists the marked and the not stopped ones.
    From schema 30 a closed gate keeps the run's event its closing wrote,
    `gates.closed_event` (`GATES_CLOSED_EVENT`; NULL while open): `update_run` stores the
    first of its events (a `flow` move, a `flow_set`, a `flow_cancel`) in the transaction
    that closes the gate (`_close_gate` returns the gate's id, `_add_event` the event's).
    The migration fills it once for gates closed before (`gates_closed_events`: the run's
    first event after the gate's `gate_answer`); one not found stays NULL.
    `GateInfo.closed_by_event` gives it to the UI, which links the answer's comment to the
    move by it. From schema 31 a gate closed by an answer keeps the note that answer kept
    for the next step, `gates.answer_note` (`GATES_ANSWER_NOTE`; NULL while open, for a
    gate closed with no note, and for every gate closed before, whose answers carried no
    files): `update_run` stores it in the closing's transaction, and
    `runs.gate_answer_attachments` gives that note's attachments, the human's files,
    `GateInfo.answer_attachments` (LAD-86).
  - `fingerprint.py`: a read-only agent's git fingerprint (docs/design/agents.md, Read-only roles): `take`
    (HEAD and checked-out branch of its worktree, the session repo's current branch, tags,
    stash, each changed or new file not ignored and not under `.lado/` with its content's
    hash; no copy of a file; all git commands within a budget, `--no-optional-locks`, else
    `FingerprintError`) and `diff` (one short line per change). Only git, no state.
  - `log.py`: `lado log`: a session's messages and events merged into one time-ordered feed.
  - `stats.py`: `lado stats`: the lines of a period's usage (`lines`), from
    `state.usage_summary`, `state.usage_start` and `telemetry.lado_errors`; reads only,
    sends nothing (`cli.cmd_stats` prints them).
  - `loop.py`: the session loop, `lado loop <session>` (see docs/design/agents.md).
  - `server/`: the UI server, one per `LADO_HOME` (`lado server`, `lado ui`; design and
    rules in [docs/design/ui.md](ui.md), section Server). `auth.py`: the token (written
    whole beside its file and moved over it; `Guard.renew` swaps it in the running server)
    and, for a connection that changes something, the Origin against the request's own
    Host (`Guard.check`), the only place that checks them; `app.py`: the FastAPI app, the API under `/api` (data only
    through `state.py`/`runtime.py`, never migrates the database), the bundle's files, and `index.html` for every other path
    that is a page of the UI (its router shows it); `feed.py`: the change feed behind
    `GET /api/events` (Server-Sent Events): the `Source` of changes (now the `changes`
    journal, read only), one hub per server, `reset` and resume, the derived fields, and
    the end of every stream when the server shuts down (`Hub.close`, called first by
    `app.Server`'s shutdown, as uvicorn waits for open responses before the lifespan's),
    and of the open ones only at a new token (`Hub.end_streams`: the hub stays open);
    `models.py`: the API's models, one form for REST and the stream's items;
    `terminals.py`: an agent's terminal WebSocket
    (`/api/sessions/{name}/agents/{agent}/terminal`) around `lado.terminal`: frames,
    backpressure, close codes, and the open sockets (`OPEN`), which a new token closes
    (`close_all`); the agents, messages, run events
    (`/api/sessions/{name}/events`), gates (with the human's answer), the human's answers
    to one agent's open questions (`POST …/answers`, a tab of the UI's waiting card, all or
    none, through `runtime.answer_questions`; each reply and a gate's answer with the full
    names of the files uploaded for it, `artifacts`), runs and notes endpoints are in `app.py`,
    and the artifacts' (docs/design/artifacts.md, The human's
    side): `GET …/artifacts`, `…/artifacts/{id}`, `…/records/{record}` and
    `…/records/{record}/content[?download=1]`, a session's only (404 else), the human's
    upload `POST …/artifacts?file_name=` (the raw bytes, under `Guard.changes`; it reads no
    more than `artifacts.MAX_SIZE` and a chunk, else 413) and `GET /api/limits` (`Limits`:
    the extension table, the types agents read and the limits the composer checks), through
    `artifacts.py` alone, whose content's headers are one function, `_content_headers`
    (`Content-Security-Policy: sandbox`, `allow-scripts` only for `text/html`, nosniff,
    inline only for `INLINE`, the file's name; `immutable` only on a 200, a missing
    content a 500 with `no-store`); messages, notes and gates carry `attachments`
    (`models.attachment_infos`, built by `artifacts.attached`), and the feed's
    `artifacts` item is an `ArtifactInfo` (`feed.ITEMS`; a new record updates its
    artifact's item by `feed.OWNER`); `GET …/messages` gives a page, `MessagePage {items,
    earlier}`, of the messages a filter takes (`with`, `agent`, the id cursors `before`
    and `after`, the times `since` and `until` by whole seconds via `models.db_second`,
    the latest `limit` or all without it), filtered in SQL (`state.MessageFilter`,
    `state.message_page`); `web/src/messageFilter.cases.json` is the one case table of
    that filter and of the UI's feed rule (docs/design/ui.md, Message windows); a gate's
    model is built by `models.gate_info`, a run's by
    `models.run_info` (its flow from the run's snapshot), for REST and the feed; when
    `runs.flow_of` cannot read the snapshot (`runs.SnapshotError`, the only error they
    catch), both build the item without the flow (no `states`, no `reads`) and name it in
    `problem`, logged once; what
    waits for the human (open gates, open questions, agents in `waiting`: the one "needs
    you") is `state.waiting_items`, only of sessions not stopped (`stopped_at IS NULL`, in
    its SQL), served as `GET /api/waiting` (`models.WaitingItem`) and counted from that same
    list as a session's `waiting` in `models.session_info` (`state.waiting_for_human`), so
    the list and the count cannot differ; whether something moves in a session, its
    agents in `busy`, `starting` or `background`, is `state.working_agents` (a count), a
    session's `busy` (0 unless its status is `running`); an agent's `status_reason` (`AgentInfo`, only
    for an agent in `waiting` or `stopped`) is `runtime.status_reason`, which
    `status_reasons` uses too (`lado ls`, `list_agents`);
    `clones.py`: the New session window's Clone from URL (docs/design/ui.md, Launch and
    session control): `POST /api/remote-branches` (`RemoteInfo`; under `Guard.changes`, as
    it goes to the network with the machine's credentials), `GET /api/clone-target`
    (`CloneTarget`: `clone.check_target` of the folder, by default the URL's default
    folder, with the name a session there gets, its `name_state` and the server's provider
    suggestion), and clone jobs: `Jobs`, one per app (`app.state.clones`), each a thread
    of the server running `clone.clone`, in memory only; `POST /api/clones` (`CloneJob`;
    409 while another running job clones into that folder), `GET /api/clones/{id}` (asking
    keeps it alive), `DELETE /api/clones/{id}` (cancels it and waits for its clone to end)
    and `POST /api/clones/{id}/cancel`, the same for the window's `navigator.sendBeacon`
    when its page goes away (a beacon can only POST);
    a sweeper cancels a running job no request asked about for `clone.ABANDONED` seconds and
    drops a finished one after `clone.KEPT`, and `app.Server`'s shutdown cancels every
    running job (`Jobs.close`). A refusal is 400 `CloneRefused` (`message`, `kind`, `hint`);
    a cancelled job has no `error`;
    `launch.py`: what the New session window asks (docs/design/ui.md, Launch and session
    control): `GET /api/folders` (`FolderInfo`: the core's `check_repo`, its `problem_kind` and `hint`, subfolders, the
    default name and whether a session has it, and `provider`, the core's
    `runtime.suggested_provider` with the server's `shutil.which`, a
    `ProviderSuggestion` of name and reason or none; `scratch` for a missing or not-repo
    folder a fresh start may take), `GET /api/scratch-target` (`ScratchTarget`: `lado.scratch`'s
    names, folder state and author, the name's state and a provider), `/api/folders/recent`,
    `/api/repos-folder` (in `app.py`; `ReposFolder`, `clone.repos_folder` or none: where
    an empty Where starts),
    `/api/kits` (the kit of each name the lookup takes, the same for every folder; a
    `where` the page still sends is ignored; an invalid one `valid: false`) and `/api/providers` (no provider is marked the default);
    `GET /api/sessions/{name}/about` (`SessionAbout`, `launch.session_about`; docs/design/ui.md,
    Session head) is what the session's head shows besides its settings, read anew: `repos`
    (path, public remote, branch; one now), each kit by `kits.find` with its version and
    `source` (`Found.source` when it does not load), and the provider's `ProviderInfo`
    (`launch.provider_info`, also `/api/providers`'s), never in the feed; `app.py` has the session control: `POST /api/sessions` (a new
    session, 409 `Taken` for a taken name), `POST …/{name}/resume`, `GET …/stop-preview`,
    `POST …/stop`, `GET …/forget-preview`, `DELETE /api/sessions/{name}?force=`, all
    through the core, the changing ones under `Guard.changes`; `SessionInfo` carries the
    session's kits, provider, permission mode and without, and how long it ran
    (`ran_seconds`, its closed spans; `running_since`, the start of the open one while it
    runs; `stopped_at`), and whether its agents work (`busy`);
    the Kits page's endpoints are in `app.py` too (docs/design/ui.md, Kits):
    `GET /api/kits/installed` (`InstalledKitInfo`, the installed then the built-in kits;
    with `KitInfo` it shares `KitSummary`), `GET /api/kits/available` (`OfferInfo`),
    `GET /api/marketplaces` (`MarketplaceInfo`) and `GET /api/kits/{name}/remove-preview`
    (`runtime.kit_users`: the running and stopped sessions whose kits name it, with the
    core's lines `lado kits remove` prints);
    under `Guard.changes`, as they change something or go to the network:
    `POST /api/kits/plan` (`PlanInfo`, `kits.plan_add`), `POST /api/kits/install` (the
    plan's `spec` with its tag, and its commit, or a folder's MCP servers: planned again,
    another one is 409), `POST /api/kits/{name}/plan-update` (with `users` and the core's
    `kits.update_line`), `POST /api/kits/{name}/update` (tag and commit, 409 likewise),
    `DELETE /api/kits/{name}`, `POST /api/kits/check-updates` (`kits.outdated`; `newer`),
    `POST`, `PATCH` and `DELETE /api/marketplaces[/{name}]` and
    `POST /api/marketplaces/update` (`update_each`); a core refusal is 400 `Refused`
    (`kits_core`). Without lado.db the lists make none and clone nothing (the official
    marketplace as the table would make it, `marketplaces.UNMADE_OFFICIAL`);
    usage statistics (docs/design/ui.md, Usage statistics): `GET /api/telemetry`
    (`TelemetryInfo`, `models.telemetry_info`, also `SystemInfo.telemetry`), `POST
    /api/telemetry` (under `Guard.changes`; 409 while the server's environment switches it
    off) and `GET /api/telemetry/preview` (`TelemetryPreview`, `telemetry.preview`);
    the Report a bug page's `GET /api/bug-report?browser=<line>` (`BugReport`,
    `bug_report.build` with the server's own `ServerState`; a `browser` that is not
    `bug_report.BROWSER_LINE`'s shape is 422; it reads only, so not under
    `Guard.changes`);
    `run.py`: the lock, `server.json`, the host and port (`--host`, 127.0.0.1 by default;
    `Listening`: the local link, the remote one (the base of the link for another device,
    or none with its `reason`) and the warning for the address taken, by one rule with
    `LADO_PUBLIC_HOST` (`public_host`; an invalid one is in `problems`, printed at the
    start) and, for `0.0.0.0`, `network_address` (a UDP route's source address, found at
    each call); in a container, `container=update.in_container()`, `LADO_LISTEN` decides
    (`listen`): the warning for a non-loopback one, else none, and unset or not IPv4 a
    `note`, `CONTAINER_NOTE`, as the port's publication decides who reaches it; `lado ui`
    there prints the link and `OPEN_ON_HOST` and opens no browser; `access`, what a server
    answers on `GET /api/access`, which `lado ui` prints as `From another machine`),
    the background start and stop (`stop` returns once the server's process has ended, not
    only its lock: `_gone` reaps a child of its own), server.log's bound (`rotate` at a background start,
    `housekeeping`'s `bound_log` and `telemetry.kick` every `KICK_EVERY`). Only in a
    container (`update.in_container()`), the sessions go with the server (openspec change
    container-session-restart): `app.Server.shutdown` first sets `app.state.stopping`
    and runs `runtime.stop_for_container` (mark every running session, then kill each
    one's tmux session, close its viewers, remove its config folders; nothing without
    lado.db), before `Hub.close` and uvicorn's wait, so open streams cannot eat Docker's
    grace period, and prints `lado: the container stops: stopped sessions ...` on stderr;
    `serve`, once the socket listens, starts `run.resume_sessions`, a thread that runs
    `runtime.resume_at_start`: the marked sessions and those not stopped whose tmux is
    gone, one at a time, by `start_session(resume=True, reason=runtime.AT_START)`, a line
    each on stderr (and one per `Started.problems` and `warnings`, as `lado start` prints
    them), a failure given up (`state.give_up_resume`), nothing more once
    `stopping` is set; each session is read again just before its resume (`_to_resume`),
    so one the human resumed from the UI meanwhile is left running. Outside a container
    neither runs. `static/`:
    the built bundle, git-ignored. A session's status (`lado ls`, the API) comes from
    `runtime.session_status`, how long it ran from `runtime.session_time`: spans from its
    `created_at` or a `session_resume` to the next `session_gone` or `session_stop` (an end
    before its start makes nothing), by the events' ids, read with one query by kind
    (`state.span_events`); the open span of a running session (or `loop_down`) is
    `running_since`, and one whose tmux is gone ends at `state.last_alive`, as the
    `session_gone` a stop or resume then writes, so its time stays the same.
- `web/`: the web UI (React, TypeScript, Vite). `openapi.json` and `src/api.gen.ts` are made
  by `make web-types` and committed. `src/attachFiles.tsx` is the human's files in one
  module (attach by the server's limits, paste, drop zone, chips, upload, `AnswerBox`), used
  by the composer and the waiting card's fields (docs/design/ui.md, Files in the composer).
- `tests/`: pytest tests; `tests/integration/`: integration tests with a fake agent;
  `tests/ui/`: UI end-to-end tests in a browser; `tests/live/`: live tests with real agent
  CLIs; `tests/js/`: Node tests of the OpenCode-family plugin; `web/src/*.test.tsx`: the
  UI's unit tests (vitest).
  `tests/agent_helpers.py`: isolation guard and polling shared by integration and live tests.
- `scripts/check_lock.py`: the Makefile's machine-wide test-run lock (docs/testing.md).
  `scripts/check_groups.py`: `make check`'s test groups, one after another (docs/testing.md).
  `scripts/smoke_ci.py`: a cell of CI's job `smoke` and of the Windows probe's smoke
  (`run`), a cell of CI's job `container` (`container`), and the CLIs' pins (docs/testing.md);
  standard library only.
  `scripts/release_check.py`: the Release workflow's check that a final release is the code
  of its last release candidate (docs/release.md); standard library only.
  `scripts/check_telemetry.py`: the Release workflow's check that the region of
  `telemetry.ENDPOINT` accepts `telemetry.PROJECT_TOKEN` (one `POST /flags/?v=2` of its
  host, no event; docs/release.md); standard library and `lado.telemetry` only.
  `scripts/release_notes.py`: a release tag's notes from CHANGELOG.md for its GitHub
  release, checked before PyPI too, with the release's `docker pull` (docs/release.md);
  standard library only, so it holds the image's name as its own `IMAGE`, kept equal to
  `update.IMAGE` by a test.
  `scripts/rc_check.py`: the human's checks of a release candidate (docs/release.md,
  section 4): `sandbox` (a clean install in a temporary folder, statistics off, removed
  after), `upgrade` (the human's `lado update X.Y.ZrcN`, keeping the final's database in
  `~/.lado-rc/`) and `rollback`; run with `python3`, never `uv run`; standard library
  only, nothing of `lado` imported (its CHANGELOG items through `release_notes.section`).
- `tests/real_clis.py`: what the live and the smoke tests share (isolation, `with_model`,
  the trust dialogs, the agents' processes, the evidence of a failed test).
  `tests/fake_endpoint.py`: the 401 model API of the smoke and container tests.
  `tests/leftovers.py`: the processes a test or a test run leaves alive, found by
  `LADO_HOME` or `LADO_TEST_PID` in their environment, killed and named (docs/testing.md).
  `tests/container/`: the container tests (docs/testing.md).
- `docker/`: LADO's image, built from a checkout by `make docker` (`lado:local`) and
  published by the Release workflow for each release as `ghcr.io/ladohq/lado:<version>`
  (`update.IMAGE`; amd64 and arm64, tested before anything is published; `latest` only for
  a final; docs/release.md, The image). `Dockerfile`: Debian 12 (tmux 3.3a, git 2.39),
  Node 22 and npm from the official `node` image, uv from its own, every base pinned by
  digest; LADO from the one wheel of the build context (`Dockerfile.dockerignore`, an
  allowlist: `dist/lado-*.whl`, `profile.sh`, `entrypoint.sh`, `ssh-agent-socket.sh`,
  `ssh-agent-env.sh`, `ssh_known_hosts` and `mise.toml`; the image holds no one's key or login, only public host keys), the
  four agent CLIs at
  `smoke_ci.py`'s `PINS`, one `ARG <NAME>_VERSION` and one layer each (`CLAUDE_VERSION`,
  `CODEX_VERSION`, `OPENCODE_VERSION`, `KILO_VERSION`; Codex's login is not carried yet),
  programs under `/opt` (the `/opt` folders named only in the build's install lines), the
  projects' toolchains (below), the user `lado` (uid
  1000 in the image) with its home a volume; `lado server --host 0.0.0.0 --port
  $LADO_PORT` (8765) under tini and `entrypoint.sh` (`/usr/local/bin/lado-entrypoint`).
  The human's projects are mounted at the host's own path and named by `LADO_REPOS`
  (`/projects` by default), so git's absolute worktree links and LADO's stored paths hold
  on the host too. The entrypoint, at a container's first start (the marker
  `/etc/lado/first-start`), reruns itself as root by `sudo -E` through
  `/etc/sudoers.d/lado-entrypoint`, a rule for it alone; that run deletes the rule and the
  marker first, gives `lado` the uid of `LADO_REPOS`'s owner unless it is 0 (Docker
  Desktop shows a bind mount so) and its gid unless that is 0 (root's group; `usermod -o`,
  `groupmod -o`), `chown -R`s the home when anything there has another owner, writes
  `LADO_REPOS` to `/etc/profile.d/lado-repos.sh` for the agents, and drops back to `lado`
  (`/usr/bin/setpriv`). The root run uses a fixed PATH and gives back the caller's
  (`LADO_ENTRYPOINT_PATH`, as sudo sets its `secure_path`) only after the drop: where the
  entrypoint was replaced the rule stays, and its SETENV must not let a caller choose what
  runs as root. A step of the root run that fails (the rule's removal, `usermod`, the
  home's `chown`) is a warning, and the start goes on. A container that may not become
  root (`NoNewPrivs`, a `CapBnd` without CHOWN, DAC_OVERRIDE, FOWNER, SETGID or SETUID:
  no-new-privileges, `--cap-drop`) or whose `/` is read-only (`/proc/self/mountinfo`:
  `--read-only`) is not sent to sudo: it warns and runs as uid 1000, the agents'
  `LADO_REPOS` the image's default `lado-repos.sh` (`/projects`). `docker run --user root`
  runs its command as `lado` too. Every start then warns in `docker logs` about a `LADO_REPOS` that is no
  folder or not writable (a probe file), and execs the command. `/opt` stays uid 1000's.
  git's system config has `safe.directory = *` and `gh auth git-credential` as the one
  credential helper of `https://github.com` (`GH_TOKEN`, or `gh auth login` inside, its
  token on the home volume). `/etc/ssh/ssh_known_hosts` is `docker/ssh_known_hosts`,
  GitHub's published public host keys (api.github.com/meta), so an agent's first ssh to
  github.com asks nothing; a container test does a real ssh to GitHub, which turns red when
  GitHub rotates them. The environment is set twice with the same
  values (`tests/test_docker.py`): in `ENV` for the server and `docker exec`, and in
  `profile.sh`, the image's `/etc/profile.d/lado.sh`, for the agents, whose environment
  comes from the login shell (`LADO_CONTAINER=1`, `PATH`, `CLAUDE_CONFIG_DIR`,
  `DISABLE_AUTOUPDATER`, `LANG`, `LADO_ENV_DIR=/run/secrets`, `NPM_CONFIG_PREFIX`;
  `LADO_REPOS` is the entrypoint's `lado-repos.sh`, read before `lado.sh` by name, so
  `profile.sh` sets `MISE_TRUSTED_CONFIG_PATHS` from it, in the profile only, as the ENV
  cannot follow `-e LADO_REPOS`; `SSH_AUTH_SOCK` from `ssh-agent-env.sh`, below). The projects' toolchains:
  `make`, `gcc`, `g++` and `libc6-dev` in the first apt layer, and mise at
  `/usr/local/bin/mise`, root's (copied before `USER lado`, so `mise self-update` cannot
  replace it), from `jdxcode/mise` pinned by digest, which Dependabot's `docker` ecosystem
  moves with the other bases. Its system config `/etc/mise/config.toml` is
  `docker/mise.toml`, the image's (a new image replaces it, a home volume needs no change):
  the version files of Go, Java, Python and Ruby besides `.tool-versions` and `mise.toml`,
  not Node's, and no update warning. Its data, config and cache stay at mise's defaults on
  the home volume (`~/.local/share/mise`, `~/.config/mise`, `~/.cache/mise`). `PATH` is the
  image's programs, the system's, then `~/.local/bin` and mise's shims: no shim shadows the
  image's Node 22, which Kilo and Codex (`env node`) and kits' MCP servers (`npx`) run on.
  An agent's `npm install -g` (`NPM_CONFIG_PREFIX=$HOME/.local`) and `uv tool install`
  (uv's defaults) write under `~/.local`, at any uid the entrypoint gave `lado`; the runtime
  `ENV` points no install at `/opt`, which stays uid 1000's. What the agents are told:
  docs/design/agents.md (the container paragraph). The agents'
  variables are files at `/run/secrets` (`LADO_ENV_DIR`, docs/design/agents.md), never compose's
  `environment:` or `LADO_AGENT_ENV=inherit`, so no value is in `docker inspect`; compose
  binds `${LADO_SECRETS:-/dev/null}` there read-only with `create_host_path: false`: by
  default no secrets, which LADO takes silently (`agent_env.null_device`), and a folder
  `LADO_SECRETS` names but that is missing is refused rather than Docker making it root's.
  Every start, as `lado`,
  writes `LADO_GIT_NAME` and `LADO_GIT_EMAIL` (compose passes both from `.env`) to git's
  global config on the home volume and warns in `docker logs` when git still has no
  identity. The host's ssh agent: compose binds `${LADO_SSH_AGENT:-/dev/null}` at
  `/run/lado/ssh-agent.sock` (`/run/lado` root's, 755; `/dev/null`: none), and
  `ssh-agent-env.sh` (`/etc/profile.d/lado-ssh-agent.sh`, the one rule) sets
  `SSH_AUTH_SOCK` there only when it is a socket: every login shell reads it, and the
  entrypoint sources it before the command, once the socket is `lado`'s, so the UI server's
  Clone from URL and branch listing use the agent too (a container test reads the
  server's `/proc/<pid>/environ`). Docker Desktop's socket is root's in
  a container: every start that finds a socket `lado` cannot use (`ssh-add -l` exit 2) and
  root's runs `sudo -n /usr/local/bin/lado-ssh-agent-socket` (`ssh-agent-socket.sh`; the
  rule `/etc/sudoers.d/lado-ssh-agent`, no SETENV, which the first start leaves), which
  takes no argument and gives that one socket, no symbolic link, to `lado`, keeping its
  group; a socket still unusable is one warning line. No `group_add`.
  The sessions go with the container (`server/`, above): its stop stops them with a mark,
  and its start resumes them after the migration; tini sends the stop's SIGTERM to `lado
  server`, its one child, and the default grace period is kept (no `stop_grace_period`).
  Both headers say so, with the supervisor's model turn per resumed session.
  `compose.yaml`: the same image, `ghcr.io/ladohq/lado:${LADO_VERSION}` (required, no
  default: the tag of a version never moves, so the image before an update keeps its name;
  `LADO_IMAGE` replaces it, `lado:local` and the tests), one `LADO_PORT` both inside and
  published as `127.0.0.1:${LADO_PORT}:${LADO_PORT}`, `LADO_PROJECTS` (required) at that
  same path and as `LADO_REPOS`, no container name; its header keeps the settings in
  `.env` next to the file, updates by the version's `compose.yaml`
  (`releases/download/v<version>/compose.yaml`), a new `LADO_VERSION` and `up -d`, goes
  back by the version before, keeping the newer `compose.yaml`, with a migration's backup (`docker compose down`, the backup copied over
  lado.db by `docker compose run`, `up -d`), and runs a second LADO from a folder of its
  own with its own `.env` (`COMPOSE_PROJECT_NAME`, `LADO_PORT`, `LADO_VERSION`,
  `LADO_PROJECTS`); the Dockerfile's header gives the same for `docker run`.
  `tests/test_docker.py`'s `header_steps` and `way_back` read them, the container tests
  run them. The users' guide is docs/install.md's `## Docker` (compose first, `docker run`
  short; both headers link to it): `guide_steps` keeps its start, update, way back and
  `docker run` the headers', its `.env` naming every variable compose reads but
  `LADO_IMAGE` and `LADO_SECRETS`; it removes only its own container and `<project>_home`
  volume by name, and no `prune` is in README.md, docs/*.md or docker/. The Release
  workflow attaches the tag's `compose.yaml` to each GitHub release, which the guide
  downloads from `releases/latest/download/compose.yaml`. The research
  prototype in
  `docs/research/docker-install/` is evidence only.
- `npm/`: placeholder npm package that only reserves the name. Leave it alone.
