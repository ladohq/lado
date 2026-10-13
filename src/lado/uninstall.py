"""`lado uninstall`: the plan, and the uninstall itself. Stop the UI server, every session of
this LADO_HOME, their loops and the UI's viewers, and LADO's tmux server when no session is
left on its socket; in each session's repository remove the worktrees and branches
`lado finish` would remove without asking (runtime.keeps_work), keep and list the others;
delete LADO_HOME; and, for the default ~/.lado only, remove the program last.

It holds the update's lock for its whole run, so an update and an uninstall never run at
once. Its output goes to the terminal only: no log in a folder it deletes. After the
program's remover started it imports nothing: the package under it is being removed.
Everything it needs is imported here at the top.
"""

import contextlib
import os
import shlex
import shutil
import sqlite3
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import lado
from lado import loop, runtime, self_update, state, telemetry, terminal, tmux, update
from lado.server import run as server_run

Say = Callable[..., None]  # print's signature: text, file=, end=, flush=

# Seconds to wait for a statistics sender that runs (it lives SEND_DEADLINE at most).
SENDER_WAIT = telemetry.SEND_DEADLINE + 5

DOCS = "docs/install.md, Uninstall"
AGENT_CLIS = (
    "Agent CLIs keep their own records of these folders (e.g. Claude Code's ~/.claude.json): "
    f"see {DOCS}."
)
HOME_FOLDER = "it is your home folder"
ABOVE_HOME = "it is / or a folder above your home folder"
NO_DATABASE = "it holds no lado.db"


class UninstallRefused(runtime.LadoError):
    """An update holds the lock."""


@dataclass
class Work:
    """A worktree of a session and its branch, and why it stays (None: it goes)."""

    repo: str
    worktree: str
    branch: str
    gone: list[str]  # of runtime.WORKTREE, BRANCH: not there
    keeps: str | None

    def parts(self, relative: bool) -> list[str]:
        where = os.path.relpath(self.worktree, self.repo) if relative else self.worktree
        return runtime.named(
            [n for n in (runtime.WORKTREE, runtime.BRANCH) if n not in self.gone],
            where,
            self.branch,
        )

    def text(self, relative: bool = False) -> str:
        return " and ".join(self.parts(relative))

    def commands(self) -> list[str]:
        """The git commands that remove it by hand."""
        lines = []
        if runtime.WORKTREE not in self.gone:
            lines.append(
                f"git -C {shlex.quote(self.repo)} worktree remove --force "
                f"{shlex.quote(self.worktree)}"
            )
        if runtime.BRANCH not in self.gone:
            lines.append(f"git -C {shlex.quote(self.repo)} branch -D {shlex.quote(self.branch)}")
        return lines


@dataclass
class Repo:
    path: str
    sessions: list[str]
    work: list[Work] = field(default_factory=list)
    problem: str | None = None  # why it is passed over: gone, or git cannot read it


@dataclass
class Session:
    name: str
    repo: str
    stopped: bool
    agents: list[str] | None  # None when lado.db is not this LADO's schema yet


@dataclass
class Plan:
    """What `lado uninstall` would do now; reads only."""

    version: str
    socket: str
    home: Path
    default_home: bool
    schema: int | None  # lado.db's; None without one
    server: dict | None
    sessions: list[Session]
    repos: list[Repo]
    home_kept: str | None  # why LADO_HOME is not deleted (HOME_FOLDER, ABOVE_HOME, NO_DATABASE)
    size: int
    prefix: Path
    remover: list[str] | None
    keep_data: bool = False

    @property
    def migrates(self) -> bool:
        return self.schema is not None and self.schema != state.SCHEMA_VERSION

    @property
    def removes_program(self) -> bool:
        return self.default_home and self.remover is not None

    def program_kept(self) -> str | None:
        """Why the program stays, with how to remove it; None when it goes."""
        if self.remover is None:
            return (
                f"LADO runs from {self.prefix}, not a uv tool or pipx install: remove it the "
                "way you installed it (pip uninstall lado in that environment)"
            )
        if not self.default_home:
            return (
                "LADO_HOME is not ~/.lado, which may still use it; remove it with: "
                f"{shlex.join(self.remover)}"
            )
        return None


def plan(keep_data: bool = False) -> Plan:
    """The plan; refused (LadoError) while an update runs or on a newer lado.db."""
    pid = self_update.running_pid()
    if pid is not None:
        raise runtime.LadoError(f"an update is running, pid {pid}; nothing was changed")
    home = state.home()
    schema = state.schema_version()
    if schema is not None and schema > state.SCHEMA_VERSION:
        raise runtime.LadoError(
            f"{home / 'lado.db'} has schema version {schema}, made by a newer LADO (this one "
            f"knows up to {state.SCHEMA_VERSION}): uninstall with that LADO's lado uninstall, "
            f"or by hand ({DOCS}); nothing was changed"
        )
    sessions = _sessions(schema, agents=True)
    default = _default_home(home)
    kept = _home_kept(home, default)
    return Plan(
        version=lado.__version__,
        socket=tmux.socket(),
        home=home,
        default_home=default,
        schema=schema,
        server=server_run.running() if server_run.lock_path().exists() else None,
        sessions=sessions,
        repos=[] if keep_data else _repos(sessions),
        home_kept=kept,
        size=0 if kept else _size(home),  # never a walk of / or the home folder
        prefix=update.prefix(),
        remover=update.remover(),
        keep_data=keep_data,
    )


def _default_home(home: Path) -> bool:
    """LADO_HOME not set, or set to ~/.lado by its real path."""
    if not os.environ.get("LADO_HOME"):
        return True
    return home.resolve() == (Path.home() / ".lado").resolve()


def _home_kept(home: Path, default: bool) -> str | None:
    """Why LADO_HOME must not be deleted: never /, the home folder or above it; another
    folder only when it holds lado.db."""
    real, user = home.resolve(), Path.home().resolve()
    if real == user:
        return HOME_FOLDER
    if real in user.parents:
        return ABOVE_HOME
    if not default and not (home / "lado.db").exists():
        return NO_DATABASE
    return None


def _size(home: Path) -> int:
    total = 0
    for root, _, files in os.walk(home):
        for name in files:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(root, name)).st_size
    return total


def _sessions(schema: int | None, agents: bool = False) -> list[Session]:
    """The sessions of lado.db, read only with the columns every schema with sessions has,
    so an older lado.db is shown without migrating it; with `agents` (the plan's) their
    agents when lado.db is this LADO's schema."""
    if schema is None:
        return []
    path = state.home() / "lado.db"
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=10)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        if not columns:
            return []
        stopped = "stopped_at" if "stopped_at" in columns else "NULL"
        rows = conn.execute(f"SELECT name, repo, {stopped} FROM sessions ORDER BY rowid").fetchall()
    finally:
        conn.close()
    current = agents and schema == state.SCHEMA_VERSION
    return [
        Session(
            name,
            repo,
            bool(stopped_at),
            [a.name for a in state.list_agents(name)] if current else None,
        )
        for name, repo, stopped_at in rows
    ]


def _repos(sessions: list[Session]) -> list[Repo]:
    """Each repository of the sessions, with the work of those sessions judged now."""
    repos: dict[str, Repo] = {}
    for sess in sessions:
        repos.setdefault(sess.repo, Repo(sess.repo, [])).sessions.append(sess.name)
    for repo in repos.values():
        if not Path(repo.path).is_dir():
            repo.problem = "no longer there"
            continue
        try:
            for name in repo.sessions:
                repo.work += _work(repo.path, name)
        except runtime.LadoError as error:
            repo.problem = f"git cannot read it: {error}"
            repo.work = []
    return list(repos.values())


def _work(repo: str, session: str) -> list[Work]:
    """The session's worktrees under .lado/worktrees/<session>/ and its branches
    lado/<session>/*, each judged by finish's rule."""
    prefix = f"lado/{session}/"
    folder = Path(repo, ".lado", "worktrees", session)
    inside = str(folder) + "/"
    found: dict[str, str] = {}  # branch -> worktree
    path = None
    # Every worktree under the session's folder, by its folder's branch: one whose branch
    # was deleted (a detached HEAD, which runtime.session_worktrees leaves out) then has
    # that branch gone, and work_of reads its HEAD. Another branch of LADO's session it has
    # checked out goes by that name; a branch not of LADO's is never one to delete.
    for line in runtime.git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
            if path.startswith(inside):
                found[f"{prefix}{Path(path).name}"] = path
        elif line.startswith("branch ") and path and path.startswith(inside):
            branch = line.removeprefix("branch refs/heads/")
            own = f"{prefix}{Path(path).name}"
            if branch != own and branch.startswith(prefix):
                del found[own]
                found[branch] = path
    refs = runtime.git(repo, "for-each-ref", "--format=%(refname:short)", f"refs/heads/{prefix}")
    for name in refs.split():
        found.setdefault(name, str(folder / name.removeprefix(prefix)))
    return [_judge(repo, worktree, branch) for branch, worktree in sorted(found.items())]


def _judge(repo: str, worktree: str, branch: str) -> Work:
    try:
        work = runtime.work_of(repo, worktree, branch)
    except runtime.LadoError as error:
        gone = runtime.gone(repo, worktree, branch)
        return Work(repo, worktree, branch, gone, f"cannot read its work: {error}")
    return Work(repo, worktree, branch, work.gone, runtime.keeps_work(work))


def _megabytes(size: int) -> str:
    if size < 1_000_000:
        return f"{size // 1000} KB"
    return f"{size / 1_000_000:.0f} MB"


def print_plan(found: Plan, say: Say = print) -> None:
    """The plan as `lado uninstall` prints it."""
    say(
        f'LADO {found.version} will be uninstalled (tmux socket "{found.socket}", '
        f"LADO_HOME {found.home}):"
    )
    if found.migrates:
        say(f"lado.db (schema {found.schema}) is upgraded first, as lado stop --all does")
    say("Stop:")
    if found.server:
        say(f"  the UI server ({found.server['url']})")
    for sess in found.sessions:
        if sess.stopped:
            say(f'  session "{sess.name}" (stopped)')
        elif sess.agents:
            say(f'  session "{sess.name}" (running: {", ".join(sess.agents)})')
        else:
            say(f'  session "{sess.name}" (running)')
    if not found.server and not found.sessions:
        say("  nothing runs")
    if found.keep_data:
        say("Keep (--keep-data): LADO_HOME and the repositories as they are")
    else:
        if found.repos:
            say("Repositories:")
        for repo in found.repos:
            if repo.problem:
                say(f"  {repo.path}: {repo.problem}, passed over")
                continue
            say(f"  {repo.path}")
            for work in repo.work:
                if work.keeps:
                    say(f"    keep   {work.text(relative=True)}: {work.keeps}")
                else:
                    say(f"    remove {work.text(relative=True)} (merged)")
            if not repo.work:
                say("    no worktree or branch of LADO's")
        if found.home_kept:
            say(f"Keep {found.home}: {found.home_kept}")
        else:
            say("Delete:")
            say(
                f"  {found.home} ({_megabytes(found.size)}: history, artifacts, installed "
                "kits, backups, logs)"
            )
    kept = found.program_kept()
    if kept:
        say(f"Keep the program: {kept}")
    else:
        say("Remove the program:")
        say(f"  {shlex.join(found.remover)}")
    say(AGENT_CLIS)


def run(found: Plan, say: Say = print) -> int:
    """The uninstall `found` plans: 0 when each step of it was done. UninstallRefused, with
    nothing changed, while an update runs."""
    lock = self_update.take_lock(self_update.LOCK_WAIT)
    if lock is None:
        pid = self_update.running_pid()
        raise UninstallRefused(f"an update is running, pid {pid}; nothing was changed")
    with lock:
        return _Uninstall(found, say).run()


class _Uninstall:
    def __init__(self, found: Plan, say: Say):
        self.plan, self.say = found, say
        self.failed = False
        self.left: list[str] = []  # the closing block's lines

    def fail(self, text: str) -> None:
        self.failed = True
        self.say(f"lado: {text}", file=sys.stderr)

    def run(self) -> int:
        try:
            self._stop()
        except (runtime.LadoError, tmux.TmuxError, OSError, state.SchemaError) as error:
            self.fail(f"{error}; no repository or file was touched: run lado uninstall again")
            return 1
        if not self.plan.keep_data:
            for repo in _repos(self._sessions()):
                self._clean(repo)
            self._delete_home()
        kept = self.plan.program_kept()
        if kept:
            self.say(f"Kept the program: {kept}")
            if self.plan.remover:
                self.left.append(f"  {shlex.join(self.plan.remover)}")
            return self._close()
        return self._remove_program()

    def _sessions(self) -> list[Session]:
        """The sessions anew after the stop, which may have migrated lado.db."""
        return _sessions(state.schema_version())

    def _stop(self) -> None:
        """The UI server, the sessions, their loops, the viewers, then the tmux server when
        no session is left on its socket. Raises when something did not stop."""
        say = self.say
        if server_run.lock_path().exists() and server_run.stop():
            say("Stopped the UI server")
        if self.plan.schema is not None:
            runtime.stop_all(lambda name, _: say(f'Stopped session "{name}"'))
            for sess in self._sessions():
                if not loop.wait_stopped(sess.name):
                    raise runtime.LadoError(
                        f'the loop of session "{sess.name}" did not end '
                        f"(LADO_HOME/loop/{sess.name}.lock is held)"
                    )
        terminal.close_viewers(None)
        try:
            if not tmux.server_running():
                return
        except tmux.TmuxMissing:
            return  # no tmux, no server
        left = [row[0] for row in tmux.sessions_with()]
        if left:
            names = ", ".join(left)
            say(
                f'Kept LADO\'s tmux server (socket "{tmux.socket()}"): sessions of another '
                f"LADO_HOME run there: {names}"
            )
            self.left.append(f'  tmux server on socket "{tmux.socket()}": sessions {names}')
            return
        tmux.kill_server()
        say("Ended LADO's tmux server")

    def _clean(self, repo: Repo) -> None:
        say = self.say
        if repo.problem:
            say(f"Passed over {repo.path}: {repo.problem}")
            return
        planned = {
            (w.repo, w.worktree, w.branch)
            for r in self.plan.repos
            for w in r.work
            if r.path == repo.path and not w.keeps
        }
        kept: list[Work] = []
        for work in repo.work:
            if work.keeps is None:
                try:
                    runtime.remove_work(repo.path, work.worktree, work.branch, work.gone)
                    say(f"Removed {work.text()}")
                    continue
                except runtime.LadoError as error:
                    work.keeps = f"git could not remove it: {error}"
            say(f"Kept {work.text()}: {work.keeps}")
            if (work.repo, work.worktree, work.branch) in planned:
                self.failed = True
            kept.append(work)
        if kept:
            self.left.append(
                f"  {repo.path}: " + ", ".join(p for w in kept for p in w.parts(relative=True))
            )
            self.left += [f"    {line}" for w in kept for line in w.commands()]
        self._tidy(repo)

    def _tidy(self, repo: Repo) -> None:
        """Remove the sessions' empty worktree folders; with .lado/worktrees empty, it goes
        with the exclude line, and an empty .lado/ after it. Nothing else under .lado/."""
        worktrees = Path(repo.path, ".lado", "worktrees")
        try:
            for folder in [worktrees / name for name in repo.sessions] + [worktrees]:
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
            if not worktrees.exists():
                runtime.git(repo.path, "worktree", "prune")
                runtime.include_worktrees(repo.path)
                lado_folder = worktrees.parent
                if lado_folder.is_dir() and not any(lado_folder.iterdir()):
                    lado_folder.rmdir()
        except (OSError, runtime.LadoError) as error:
            self.fail(f"could not tidy {worktrees}: {error}")

    def _delete_home(self) -> None:
        home = self.plan.home
        if self.plan.home_kept:
            self.fail(f"kept {home}: {self.plan.home_kept}")
            self.left.append(f"  {home}: {self.plan.home_kept}")
            return
        # A sender `lado telemetry send` started before the stop writes into LADO_HOME.
        if not telemetry.sender_ended(SENDER_WAIT):
            why = "LADO's statistics sender still runs (LADO_HOME/telemetry/send.lock is held)"
            self.fail(f"kept {home}: {why}; run lado uninstall again")
            self.left.append(f"  {home}: {why}")
            return
        errors: list[str] = []

        def failed(function, path, error) -> None:
            exc = error[1] if isinstance(error, tuple) else error
            errors.append(f"{path}: {exc}")

        if sys.version_info >= (3, 12):
            shutil.rmtree(home, onexc=failed)
        else:
            shutil.rmtree(home, onerror=failed)
        for error in errors:
            self.fail(f"could not delete {error}")
        if errors:
            self.left.append(f"  {home}: not all deleted")
        else:
            self.say(f"Deleted {home}")

    def _remove_program(self) -> int:
        """Last: nothing is imported after the remover started, and only strings made before
        it are said."""
        argv = self.plan.remover
        command = shlex.join(argv)
        removing = f"Removing the program: {command}"
        failed = "the program was not removed (exit code {code}): run " + command
        self.say(removing, flush=True)
        code = self_update.command(argv, self.say)
        if code:
            self.failed = True
        else:
            self.say("Uninstalled lado")
        self._close()
        if code:
            self.say(f"lado: {failed.format(code=code)}", file=sys.stderr)
        return 1 if self.failed else 0

    def _close(self) -> int:
        if self.left:
            self.say()
            self.say("Left on this machine:")
            for line in self.left:
                self.say(line)
        return 1 if self.failed else 0
