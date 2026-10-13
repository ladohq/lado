## Context

What LADO leaves on a machine (read in the code, 0.36.0):

- the program: a uv tool or pipx install (`update.installer` reads `uv-receipt.toml` or
  `pipx_metadata.json` in `sys.prefix`), or pip in an environment, or a working copy;
- processes: LADO's tmux server (`tmux -L lado`, `LADO_TMUX_SOCKET`) with the sessions'
  agents, one `lado loop <session>` per session (`loop.py`, a flock in
  `LADO_HOME/loop/`), the UI server (`server/run.py`, `server.json`), the UI's terminal
  viewers (tmux sessions labelled `@lado-viewer`, `terminal.close_viewers`);
- `LADO_HOME` (`state.home()`, default `~/.lado`): `lado.db` and its WAL, `artifacts/`,
  `backups/`, `cache/`, `marketplaces/`, `agents/`, `loop/`, logs, the update's and the
  server's files. A launchd plist under `LADO_HOME/launchd/` is removed by
  `gui_session.start_server` in any outcome;
- in each session's repository: worktrees `.lado/worktrees/<session>/<name>`
  (`runtime.spawn_worker`, `runs.py`), branches `lado/<session>/<name>`, and the line
  `/.lado/worktrees/` in `.git/info/exclude` (`runtime.exclude_worktrees`).

Nothing of LADO's is written to the user's agent configs (Design principles); the agent
CLIs keep their own records of the folders they ran in.

Root cause: LADO knows all of it, and only `lado.db` knows the repositories, but no
command undoes it.

## Options

1. **Docs only**: an Uninstall section with commands by hand. Cheap, but the human must
   find the repositories (a SQL query on `lado.db`) and judge each worktree; the
   clean-state test of an upgrade (the human's second goal) is slow and easy to get
   wrong. Kept only as the fallback for a LADO before the command.
2. **`lado uninstall` in the core, the CLI only asking and printing** (chosen). Like
   `lado update` (`self_update.py`): a plan, a confirmation, steps said as they run.
   Long-term cost: one module of about 250 lines and its tests; it reuses `stop_all`,
   `server.run.stop`, `close_viewers`, finish's merged rule and the update's lock.
3. **A `--purge` on `lado stop --all` plus a separate program removal**: no new command,
   but it mixes a daily command with a destructive one and still leaves the program
   removal to the human. Rejected.

Held against ROADMAP.md: stage 7's desktop app will ship its own installer and will
uninstall through the OS; it can call the same core (`uninstall.plan`/`run`) for the data
part. Projects (Later) add repositories per project; the repository step goes by the
sessions in `lado.db`, so it covers them as they come. Design principles: *Neutral core*:
no provider is involved (the agent CLIs' own records are named in the docs, for every
provider); *One source of truth*: the repositories come from `lado.db`, the merged rule is
finish's own function, the installer from the same files `lado update` reads; *No silent
drops*: every kept worktree, branch, folder or program is listed with why and how to
remove it; *Never touch the user's global agent config*: the CLIs' records stay; *Only
what is used*: no UI, no `--discard`.

## Decisions

### D1. A core module, the CLI asks and prints

`src/lado/uninstall.py`: `plan() -> Plan` (reads only, also for `--dry-run`),
`print_plan(plan, say)`, `run(plan, say) -> int`. `cli.cmd_uninstall` refuses inside an
agent (`_human_only("uninstall")`), prints the plan, asks, and calls `run`. `uninstall` is
added beside `stop` to the commands `main` runs without `migrate_if_safe` (it stops the
sessions itself; D3). Every import the module needs is at its top, and nothing is
imported after the program's remover started (D8); a test forbids it as
`tests/test_self_update.py` does for the installer.

### D2. Stopping: the existing stops, in the update's order

`run` takes the update's lock exclusively (`self_update._take_lock`, made public as
`take_lock`) for its whole run; held, it is refused as `lado update` refuses a second
update. Then: `server.run.stop()`; `runtime.stop_all` (sessions marked stopped, their
tmux sessions killed); `loop.wait_stopped` per stopped session; `terminal.close_viewers()`.
A loop that does not end ends the run before step 2 of the plan (repositories), exit 1,
with the `lado uninstall` to run again. Then, when `tmux.server_running()` and the socket
has no session left, `tmux kill-server`; with sessions left (another `LADO_HOME`, or a
human's own on LADO's socket) the server stays and they are named.

### D3. The database's schema

`plan()` reads the schema version first (`PRAGMA user_version` on a read-only
connection, as `state.pending_migration` does). A newer one is refused before the plan,
naming the newer LADO's `lado uninstall` and the docs' steps by hand. The plan reads the
sessions' names, repositories and stopped state on that read-only connection with the
columns every schema with sessions has (`name`, `repo`; `stopped_at` when present), so an
older `lado.db` is shown without migrating; the plan then says `lado.db (schema N) is
upgraded first, as lado stop --all does`, and `run`'s `stop_all` migrates it. After the
stop, `run` reads through `state` as usual. No `lado.db` at all: no sessions, no
repositories; the plan still covers the folder and the program.

### D4. The repositories: finish's rule, one function

For each distinct `sessions.repo`: the worktrees `runtime.session_worktrees(repo,
session)` lists, and the branches `refs/heads/lado/<session>/*` (`git for-each-ref`), of
every session of `lado.db`. Each worktree with its branch, and each branch without a
worktree, is judged by one function factored out of `runtime._work_state` and
`_refusal`: `runtime.work_of(repo, worktree, branch) -> WorkState` and
`runtime.keeps_work(work) -> str | None` (why it cannot go: not merged into the current
branch, or uncommitted changes); `finish_preview` and `_work_state` call them, so finish
and uninstall cannot drift. Removable work goes by `runtime.remove_work` without `force`. A kept one
is listed with `git -C <repo> worktree remove --force <path>` and `git -C <repo> branch -D
<branch>`. A repository folder that is gone or not a git repository is named and passed
over. The plan judges the work as it is when shown; `run` judges it again after the
sessions are stopped (an agent may have committed in between), and goes by that.

### D5. The exclude line and `.lado/worktrees`

After a repository's work is handled: when `<repo>/.lado/worktrees` holds no entry (also
no other session's folder, of another `LADO_HOME`), it is removed with its empty session
folders, `git worktree prune` runs, and `runtime.include_worktrees(repo)`, the counterpart
of `exclude_worktrees` beside it, drops the `/.lado/worktrees/` line from the common
`info/exclude` (the file stays, also empty). `.lado/` itself is removed only when empty.

### D6. Deleting LADO_HOME

`home = state.home()`. It is deleted (`shutil.rmtree`, errors collected by `onerror`,
each named) only when it is `Path.home() / ".lado"` by real path or holds `lado.db`, and
never when it is `/`, `Path.home()` or an ancestor of it; else it is kept and named, exit
1. Deleted after the repositories, as the plan needs `lado.db` until then. The output
goes to stdout only: no log in a folder being deleted.

### D7. Which home is the default

`default = "LADO_HOME" not in os.environ or real(home) == real(Path.home() / ".lado")`.
Only the default home's uninstall removes the program (the human's decision): another home
is a trial folder, and `~/.lado` may still use the program.

### D8. Removing the program

`update.remover(where=None) -> list[str] | None`: `uv tool uninstall lado` when
`uv-receipt.toml` is in the prefix, `pipx uninstall lado<suffix>` when
`pipx_metadata.json` is (its `main_package.suffix`), whatever the source (unlike
`installer`, which needs an index); `LADO_UPDATE_PREFIX` makes the prefix testable, and a
new `LADO_UNINSTALL_REMOVER` (tests only, an argv) replaces the command as
`LADO_UPDATE_INSTALLER` does. None: the program is kept, and the output says `LADO runs
from <prefix>, not a uv tool or pipx install: remove it the way you installed it (pip
uninstall lado in that environment)`. The remover is the last subprocess; its output is
passed through; after it only `say` lines of strings built before it run. A failure is its
exit code plus the command, exit 1.

### D9. Exit codes and output

0 when every step of the plan was done (kept unmerged work is part of the plan, so it is
no failure); 1 on refusal, no confirmation, or a step that failed or kept something the
plan meant to remove. Each step prints one line as it ends (`Stopped the UI server`,
`Stopped session "x"`, `Removed worktree …`, `Kept …: <why>`, `Deleted ~/.lado`,
`Removing the program: uv tool uninstall lado`), and a closing block `Left on this
machine:` lists what stays with the command for each.

### D10. The agent CLIs' records

Not detected and not touched. The plan's last line: `Agent CLIs keep their own records of
these folders (e.g. Claude Code's ~/.claude.json): see docs/install.md, Uninstall`. The
docs list per provider what stays and where.
