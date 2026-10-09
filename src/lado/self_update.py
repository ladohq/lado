"""`lado update` from the CLI and the UI alike: the plan, the refusals, and the update itself
(stop the sessions and the UI server, back up lado.db, install, check, resume, and roll back
when the new version itself is bad). lado.update is its pure part: the index, the
installer, the marks and the result file.

One update at a time per LADO_HOME: it holds an exclusive flock on LADO_HOME/update.lock
(its pid in the file) for its whole run, and only then writes LADO_HOME/update.log (each
line it says, and the output of each command it runs) and update-result.json (`running`
at the start, the outcome at the end; lado.update's docstring).

After the installer this process starts nothing of its own and imports nothing: the
package under it may be another version, or broken. Everything the rollback, the restore
and the result need is imported here at the top.
"""

import contextlib
import datetime
import fcntl
import os
import shlex
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import lado
from lado import loop, providers, runtime, state, tmux, update
from lado.server import run as server_run

DEFAULT_HOST = "127.0.0.1"  # `lado server --host`'s default
LOCK_WAIT = 0.1  # seconds an update tries to take the lock: `refusal()` holds it briefly
TAIL = 20  # lines of update.log the result keeps

AGENT = "agent"
RUNNING = "running"
NO_INSTALLER = "no installer"

Say = Callable[..., None]  # print's signature: text, file=, end=, flush=


def lock_path() -> Path:
    return state.home() / "update.lock"


def log_path() -> Path:
    return state.home() / "update.log"


def backups() -> Path:
    return state.home() / "backups"


class UpdateRefused(runtime.LadoError):
    """An update holds the lock already."""


def _take_lock(wait: float = 0) -> IO | None:
    lock = open(lock_path(), "a+")
    deadline = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock
        except OSError:
            if time.monotonic() >= deadline:
                lock.close()
                return None
            time.sleep(wait / 10)


def running_pid() -> int | None:
    """The pid of the update that holds the lock (0 when it has not written it yet); None
    when none runs."""
    if not lock_path().exists():
        return None
    lock = _take_lock()
    if lock is not None:
        lock.close()
        return None
    try:
        return int(lock_path().read_text().strip() or 0)
    except (OSError, ValueError):
        return 0


@dataclass(frozen=True)
class Refusal:
    kind: str  # AGENT, RUNNING or NO_INSTALLER
    why: str


def refusal(installer: update.Installer | None) -> Refusal | None:
    """Why this LADO cannot update itself now, for the CLI and the UI alike: inside an
    agent, while an update runs, or with no installer (`installer()` found none)."""
    agent = os.environ.get("LADO_AGENT")
    if agent:
        return Refusal(AGENT, f'lado update is for the human; agent "{agent}" cannot use it')
    pid = running_pid()
    if pid is not None:
        return Refusal(RUNNING, f"an update is running, pid {pid}")
    if installer is None:
        return Refusal(
            NO_INSTALLER,
            f"LADO runs from {update.prefix()}, not a uv tool or pipx install of lado from "
            "PyPI; lado update does not upgrade it",
        )
    return None


@dataclass
class Plan:
    """What an update to `to` would do: the sessions it stops and resumes (those
    `runtime.session_status` says run, also with their loop down), and the UI server's
    server.json, if one runs."""

    current: str
    to: update.Release
    installer: update.Installer | None
    sessions: list[state.Session]
    gone: list[state.Session]  # not stopped, but their tmux is gone: not restarted
    server: dict | None
    socket: str = field(default_factory=tmux.socket)

    @property
    def command(self) -> str | None:
        return shlex.join(self.installer.command(self.to.version)) if self.installer else None

    @property
    def downgrade(self) -> bool:
        return update.newer(self.current, self.to.version)

    def by_hand(self) -> list[str]:
        """The commands that do it without an installer."""
        lines = [f"lado stop {s.name}" for s in self.sessions]
        lines += ["lado server stop"] if self.server else []
        lines.append(f"{update.prefix() / 'bin' / 'pip'} install lado=={self.to.version}")
        lines += [f"lado start {s.repo} --name {s.name}" for s in self.sessions]
        lines += ["lado ui"] if self.server else []
        return lines


def plan(to: update.Release) -> Plan:
    found = Plan(lado.__version__, to, update.installer(), [], [], server_run.running())
    for sess in state.list_sessions():
        status = runtime.session_status(sess)
        if status in (runtime.SessionStatus.RUNNING, runtime.SessionStatus.LOOP_DOWN):
            found.sessions.append(sess)
        elif status == runtime.SessionStatus.TMUX_GONE:
            found.gone.append(sess)
    return found


def latest_plan() -> Plan | None:
    """The plan for PyPI's latest release, None when it is no newer than this LADO.
    OSError or ValueError when the index cannot be read."""
    to = update.latest(update.fetch_index())
    if to is None or not update.newer(to.version, lado.__version__):
        return None
    return plan(to)


def open_runs(session: str) -> int:
    return len(state.list_runs(session, open_only=True))


def print_plan(found: Plan, say: Say = print) -> None:
    """The plan as `lado update` prints it."""
    say(f"LADO {found.current} -> {found.to.version} (PyPI, released {found.to.date})")
    if found.installer:
        say(f"Installed with {found.installer.kind}: {found.command}")
        if found.installer.lost:
            lost = ", ".join(found.installer.lost)
            say(
                f"lado: WARNING: {found.command} does not keep {lost} of this install",
                file=sys.stderr,
            )
    if found.downgrade:
        say(
            f"lado: WARNING: an older LADO may refuse lado.db (schema {state.SCHEMA_VERSION}); "
            "it says so when it starts",
            file=sys.stderr,
        )
    if found.sessions or found.server:
        say("Restarts:")
    for sess in found.sessions:
        agents = ", ".join(f"{a.name} {a.status}" for a in state.list_agents(sess.name))
        count = open_runs(sess.name)
        runs_open = f"{count} open run{'' if count == 1 else 's'}" if count else "no open runs"
        say(f"  session {sess.name}  ({sess.repo})  {agents or 'no agents'}; {runs_open}")
    if found.server:
        say(f"  UI server  {found.server['url']}")
    if found.sessions:
        say(
            "Busy agents lose their current turn. Runs, gates, branches and worktrees stay;\n"
            "each supervisor starts a new conversation and gets what its open runs wait for."
        )
    for sess in found.gone:
        say(
            f"Not running, its tmux session is gone: {sess.name}; resume it with "
            f"lado start {sess.repo} --name {sess.name}"
        )
    say(f'Only sessions on tmux socket "{found.socket}" are seen.')


def print_by_hand(found: Plan, say: Say = print) -> None:
    say(
        f"LADO runs from {update.prefix()}, not a uv tool or pipx install of lado from PyPI; "
        "lado update does not upgrade it. By hand:"
    )
    for line in found.by_hand():
        say(f"  {line}")


def unfinished() -> str | None:
    """Which sessions an update that did not finish left stopped, and how to resume them;
    its mark (update.json) goes once none of them is stopped."""
    pending = update.read_pending()
    if pending is None:
        return None
    left = []
    for name, repo in pending.sessions.items():
        sess = state.get_session(name)
        if sess and sess.stopped_at:
            left.append((name, repo))
    if not left:
        update.clear_pending()
        return None
    names = ", ".join(name for name, _ in left)
    commands = "; ".join(f"lado start {repo} --name {name}" for name, repo in left)
    return (
        f"lado: an update did not finish: sessions {names} may be stopped; "
        f"resume them with {commands}"
    )


def start_detached(to: str, id: str) -> None:
    """`lado update --yes <to> --id <id>` of this LADO as a process of its own, for the UI
    server, which the update stops: in its own session, so it outlives the server, its
    lines in update.log (`--id`); what it cannot say there (a traceback) goes where the
    server's own output goes."""
    subprocess.Popen(
        providers.lado_command("update", "--yes", to, "--id", id),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        start_new_session=True,
    )


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class _Told:
    """`say` that also writes each line to update.log."""

    def __init__(self, say: Say, log: IO):
        self.say, self.log = say, log

    def __call__(self, text: str = "", *, file=None, end: str = "\n", flush: bool = False):
        self.say(text, file=file, end=end, flush=flush)
        self.log.write(text + end)
        self.log.flush()


def run(found: Plan, say: Say = print, id: str | None = None) -> int:
    """The update `found` plans, with the installer it found: 0 when everything is on the
    new version again. UpdateRefused, with nothing written, when another update runs."""
    lock = _take_lock(LOCK_WAIT)
    if lock is None:
        refused = refusal(found.installer)
        raise UpdateRefused(refused.why if refused else "an update is running")
    with lock:
        lock.truncate(0)
        lock.write(str(os.getpid()))
        lock.flush()
        # The owner's only: `lado ui` prints its login link, token included.
        fd = os.open(log_path(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)  # also a log made before
        with os.fdopen(fd, "w") as log:
            told = _Told(say, log)
            started = update.Result(
                update.RUNNING, found.current, found.to.version, _now(), id=id, log=str(log_path())
            )
            update.write_result(started)
            done = _Update(found, told, started)
            try:
                code = done.run()
            except BaseException as exc:
                done.end("failed", f"the update stopped: {exc!r}")
                raise
            return code


class _Update:
    """One update's steps; `end` writes its result."""

    def __init__(self, found: Plan, say: _Told, started: update.Result):
        self.plan, self.say, self.started = found, say, started
        self.installer = found.installer
        self.binary = found.installer.binary
        self.old = found.current
        self.new = found.to.version
        server = found.server
        self.address = (server["host"], server["port"]) if server else None
        self.backup: Path | None = None
        self.schema: int | None = None  # lado.db's before the installer
        self.failed: list[state.Session] = []

    def end(self, outcome: str, reason: str | None, database: str | None = None) -> None:
        self.say.log.flush()
        lines = log_path().read_text().splitlines()
        update.write_result(
            update.Result(
                outcome,
                self.started.from_,
                self.started.to,
                self.started.started_at,
                ended_at=_now(),
                id=self.started.id,
                sessions_failed=[
                    {"name": s.name, "command": f"lado start {s.repo} --name {s.name}"}
                    for s in self.failed
                ],
                reason=reason,
                database=database,
                log=self.started.log,
                tail=lines[-TAIL:],
            )
        )

    def run(self) -> int:
        say = self.say
        update.write_pending(
            update.Pending({s.name: s.repo for s in self.plan.sessions}, self.address)
        )
        stopped: list[state.Session] = []
        server_stopped = False
        try:
            for sess in self.plan.sessions:
                say(f"Stopping session {sess.name}...", end=" ", flush=True)
                dropped = runtime.stop_session(sess.name).dropped
                stopped.append(sess)
                if not loop.wait_stopped(sess.name):
                    say()
                    raise runtime.LadoError(
                        f"the session loop of {sess.name} did not end; "
                        f"see {state.home() / 'loop.log'}"
                    )
                not_read = f" ({dropped} messages not read are dropped)" if dropped else ""
                say(f"stopped{not_read}")
            if self.address:
                say("Stopping the UI server...", end=" ", flush=True)
                server_run.stop()
                server_stopped = True
                say("stopped")
            self._back_up()
        except (runtime.LadoError, tmux.TmuxError, OSError, sqlite3.Error) as exc:
            say(f"lado: {exc}; nothing was upgraded. Resuming the sessions:", file=sys.stderr)
            self._resume(stopped, self.address if server_stopped else None)
            self.end("failed", f"{exc}; nothing was upgraded", "kept")
            return 1
        code = _install(self.installer, self.new, say)
        if code:
            say(f"The upgrade failed; LADO {self.old} is unchanged. Resuming the sessions on it:")
            self._resume(stopped, self.address)
            self.end("failed", f"the installer failed (exit code {code})", "kept")
            return 1
        now = update.installed_version(self.binary)
        if now is None or not update.same(now, self.new):
            why = f"LADO {self.new} did not install right: --version says {now or 'nothing'}"
            say(f"The installer finished, but LADO is {now or 'unknown'}, not {self.new}.")
            return self._roll_back(why, stopped, [], started_server=False)
        say(f"Resuming on LADO {self.new}:", flush=True)
        resumed = self._resume(stopped, None)
        if self.address:
            down = self._server(self.new)
            if down:
                return self._roll_back(down, stopped, resumed, started_server=True)
        if self.failed:
            count = len(self.failed)
            self.end(
                "partial", f"{count} session{'' if count == 1 else 's'} did not resume", "kept"
            )
            return 1
        update.clear_pending()
        say(f"LADO {self.new} is ready." + (" Reload open UI tabs." if self.address else ""))
        self.end("ok", None, "kept")
        return 0

    def _back_up(self) -> None:
        """lado.db by SQLite's backup API, in place of the backup before."""
        live = state.home() / "lado.db"
        if not live.exists():
            return
        folder = backups()
        folder.mkdir(exist_ok=True)
        self.backup = folder / f"lado.db.{self.old}"
        written = self.backup.with_suffix(".tmp")
        written.unlink(missing_ok=True)
        restore(live, written)
        written.replace(self.backup)
        for other in folder.iterdir():
            if other != self.backup:
                other.unlink()
        with contextlib.closing(sqlite3.connect(self.backup)) as db:
            self.schema = db.execute("PRAGMA user_version").fetchone()[0]
        self.say(f"Backed up lado.db to {self.backup}")

    def _server(self, version: str) -> str | None:
        """Why the UI server did not come up on `version` where it ran before; None when it
        did."""
        host, port = self.address
        hosting = [] if host == DEFAULT_HOST else ["--host", host]  # a LADO before 0.20 has none
        code = _run(self.binary, self.say, "ui", "--no-open", *hosting, "--port", str(port))
        if code:
            self.say(
                f"lado: the UI server did not start (exit code {code}); start it with lado ui",
                file=sys.stderr,
            )
            return f"the UI server did not start on LADO {version} (exit code {code})"
        info = server_run.running()
        health = server_run.health(info["url"]) if info else None
        said = health.get("version") if health else None
        if said is None or not update.same(said, version):
            return (
                f"the UI server did not come up on LADO {version}: "
                f"/api/health says {said or 'nothing'}"
            )
        return None

    def _resume(
        self, sessions: list[state.Session], server: tuple[str, int] | None
    ) -> list[state.Session]:
        """Resume the sessions, then the UI server, with the installed `lado`'s public
        commands; the sessions that resumed (the others go to `failed`)."""
        resumed, self.failed = [], []
        for sess in sessions:
            code = _run(
                self.binary, self.say, "start", sess.repo, "--name", sess.name, "--no-attach"
            )
            if code:
                self.say(
                    f"lado: session {sess.name} did not resume (exit code {code}); "
                    f"resume it with lado start {sess.repo} --name {sess.name}",
                    file=sys.stderr,
                )
                self.failed.append(sess)
            else:
                resumed.append(sess)
        if server:
            host, port = server
            hosting = [] if host == DEFAULT_HOST else ["--host", host]
            code = _run(self.binary, self.say, "ui", "--no-open", *hosting, "--port", str(port))
            if code:
                self.say(
                    f"lado: the UI server did not start (exit code {code}); start it with lado ui",
                    file=sys.stderr,
                )
        return resumed

    def _roll_back(
        self,
        why: str,
        stopped: list[state.Session],
        resumed: list[state.Session],
        started_server: bool,
    ) -> int:
        """Back to the old version: stop what the new one started, wait for those loops,
        reinstall the old version and check it, restore lado.db only when its schema moved,
        resume on the old version."""
        say = self.say
        say(f"Rolling back to LADO {self.old}: {why}", flush=True)
        for sess in resumed:
            _run(self.binary, say, "stop", sess.name)
        if started_server:
            _run(self.binary, say, "server", "stop")
        for sess in resumed:
            if not loop.wait_stopped(sess.name):
                self.failed = []
                self.end(
                    "rollback_failed",
                    f"{why}; lado.db not restored: the session loop of {sess.name} did not "
                    f"end; its backup is {self.backup}",
                )
                return 1
        code = _install(self.installer, self.old, say, "Reinstalling")
        if code:
            self.end(
                "rollback_failed", f"{why}; reinstalling LADO {self.old} failed (exit code {code})"
            )
            return 1
        now = update.installed_version(self.binary)
        if now is None or not update.same(now, self.old):
            self.end(
                "rollback_failed",
                f"{why}; reinstalled LADO {self.old}, but --version says {now or 'nothing'}",
            )
            return 1
        database = "kept"
        if self.backup and state.schema_version() != self.schema:
            try:
                restore(self.backup, state.home() / "lado.db")
            except sqlite3.Error as exc:
                self.end(
                    "rollback_failed",
                    f"{why}; lado.db not restored: {exc}; its backup is {self.backup}",
                )
                return 1
            database = "restored"
            say(f"Restored lado.db from {self.backup}")
        say(f"Resuming on LADO {self.old}:", flush=True)
        self._resume(stopped, self.address)
        self.end("rolled_back", why, database)
        return 1


def restore(source: Path, target: Path) -> None:
    """`source` into `target` by SQLite's backup API: into the live file, never a file
    copy, since lado.db runs in WAL mode and its -wal file would outlive a copy."""
    with contextlib.closing(sqlite3.connect(source)) as src:
        with contextlib.closing(sqlite3.connect(target, timeout=10)) as dst:
            src.backup(dst)


def _install(installer: update.Installer, version: str, say: Say, verb: str = "Upgrading") -> int:
    command = installer.command(version)
    say(f"{verb}: {shlex.join(command)}", flush=True)
    return _command(command, say)


def _run(binary: Path, say: Say, *args: str) -> int:
    """`binary` with `args`: its exit code; its output said line by line."""
    return _command([str(binary), *args], say)


def _command(argv: list[str], say: Say) -> int:
    try:
        process = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace"
        )
    except OSError as exc:
        say(f"lado: {exc}", file=sys.stderr)
        return 127
    with process:
        for line in process.stdout:
            say(line.rstrip("\n"), flush=True)
    return process.returncode
