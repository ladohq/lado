"""`lado update` from the CLI and the UI alike: the plan, the refusals, and the update itself
(stop the sessions and the UI server, install, check, resume, and roll back when the new
version itself is bad). It keeps no copy of lado.db of its own and touches nothing in
LADO_HOME/backups/: the copy its rollback restores is the migration's
(backups/lado.db.schema-<N>, state.migrate). An update to a release with an older schema
(its wheel says which, update.release_schema) warns in its plan, refuses without that
schema's copy, and puts the copy back after the installer. lado.update is its pure part:
the index, the installer, the marks and the result file.

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
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

import lado
from lado import gui_session, loop, providers, runtime, state, tmux, update
from lado.server import run as server_run

DEFAULT_HOST = "127.0.0.1"  # `lado server --host`'s default
# The first LADO whose `lado start` takes `--wait-for-login` (LAD-163); an older one's
# argparse refuses it (exit 2), so an update to it resumes without.
WAIT_FOR_LOGIN_SINCE = "0.44.0.dev0"
LOCK_WAIT = 0.1  # seconds an update tries to take the lock: `refusal()` holds it briefly
TAIL = 20  # lines of update.log the result keeps

AGENT = "agent"
CONTAINER = "container"
RUNNING = "running"
NO_INSTALLER = "no installer"

Say = Callable[..., None]  # print's signature: text, file=, end=, flush=


def lock_path() -> Path:
    return state.home() / "update.lock"


def log_path() -> Path:
    return state.home() / "update.log"


def backups() -> Path:
    return state.backups()


class UpdateRefused(runtime.LadoError):
    """An update holds the lock already."""


def take_lock(wait: float = 0, shared: bool = False) -> IO | None:
    """The update's lock, exclusive for an update (and for `lado uninstall`); `shared` for
    a look at it, so two looks at once do not see each other as an update."""
    lock = open(lock_path(), "a+")
    deadline = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(lock, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
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
    lock = take_lock(shared=True)
    if lock is not None:
        lock.close()
        return None
    try:
        return int(lock_path().read_text().strip() or 0)
    except (OSError, ValueError):
        return 0


@dataclass(frozen=True)
class Refusal:
    kind: str  # AGENT, CONTAINER, RUNNING or NO_INSTALLER
    why: str


def refusal(installer: update.Installer | None) -> Refusal | None:
    """Why this LADO cannot update itself now, for the CLI and the UI alike: inside an
    agent, in LADO's container (`update.in_container`), while an update runs, or with no
    installer (`installer()` found none)."""
    agent = os.environ.get("LADO_AGENT")
    if agent:
        return Refusal(AGENT, f'lado update is for the human; agent "{agent}" cannot use it')
    if update.in_container():
        return Refusal(
            CONTAINER, "LADO runs in a container: a new image updates it, not lado update"
        )
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


@dataclass(frozen=True)
class Restore:
    """How an update to a release with an older lado.db schema goes back: lado.db becomes
    the migration's `copy` of `schema` (made at `made`, local `YYYY-MM-DD HH:MM`) in place
    of the schema `live`; the planned sessions the copy lacks (`missing`) are not resumed."""

    copy: Path
    schema: int
    live: int
    made: str
    missing: list[str]


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
    # On a Mac outside the graphical session: where the resumed agents' tmux server starts,
    # or why they cannot read their login from the keychain (lado.gui_session); else None.
    agents_note: str | None = None
    restore: Restore | None = None  # lado.db goes back to an older schema's copy

    @property
    def command(self) -> str | None:
        return shlex.join(self.installer.command(self.to.version)) if self.installer else None

    @property
    def downgrade(self) -> bool:
        return update.newer(self.current, self.to.version)

    def by_hand(self) -> list[str]:
        """The commands that do it without an installer, paths shell-quoted: stop every
        planned session and the UI server, install with what the prefix holds (its pip,
        else uv tool, else pipx, else a comment that LADO does not know the installer),
        put the migration's copy back into lado.db for an older schema, and start again
        the sessions the copy has."""
        lines = [f"lado stop {s.name}" for s in self.sessions]
        lines += ["lado server stop"] if self.server else []
        lines.append(_install_by_hand(self.to.version))
        if self.restore:
            db = str(state.home().absolute() / "lado.db")
            lines.append(
                f"{shlex.join(['rm', '-f', f'{db}-wal', f'{db}-shm'])} && "
                f"{shlex.join(['cp', str(self.restore.copy.absolute()), db])}"
            )
        missing = self.restore.missing if self.restore else []
        lines += [
            f"lado start {shlex.quote(s.repo)} --name {s.name}"
            for s in self.sessions
            if s.name not in missing
        ]
        lines += ["lado ui"] if self.server else []
        return lines


def takes_wait_for_login(version: str) -> bool:
    """Whether LADO `version`'s `lado start` takes `--wait-for-login`."""
    return not update.newer(WAIT_FOR_LOGIN_SINCE, version)


def _install_by_hand(version: str) -> str:
    """The install line of the commands by hand, by the files of the prefix only (as
    update.installer); its pip first, since a venv made by hand may hold another tool's
    file too. uv and pipx get the folders of the install in `where`, else they install
    a second lado into their default ones: uv's tool folder and the executable's folder
    (uv moves it), pipx's home when `where` is `<home>/venvs/<name>` (pipx links its
    executable into the venv, so the old link runs the new version)."""
    where, requirement = update.prefix(), f"lado=={version}"
    q = shlex.quote
    pip = where / "bin" / "pip"
    if pip.is_file():
        return f"{q(str(pip))} install {requirement}"
    if (where / "uv-receipt.toml").is_file():
        bin_dir = update.uv_bin_dir(where)
        folders = f"UV_TOOL_DIR={q(str(where.parent))} "
        folders += f"UV_TOOL_BIN_DIR={q(str(bin_dir))} " if bin_dir else ""
        return f"{folders}uv tool install {requirement}"
    if (where / "pipx_metadata.json").is_file():
        home = f"PIPX_HOME={q(str(where.parent.parent))} " if where.parent.name == "venvs" else ""
        return f"{home}pipx install --force {requirement}"
    return (
        f"# install {requirement} with the installer of {shlex.quote(str(where))}: "
        "LADO does not know it"
    )


def plan(to: update.Release, index: dict | None = None) -> Plan:
    """The plan of an update to `to`; `index` is PyPI's JSON, read again when None and an
    older release's schema is needed. runtime.LadoError, before anything is stopped, when
    `to` is older and its lado.db schema cannot be learned, or is older than lado.db's
    without the migration's copy of it to go back to."""
    live = state.schema_version()  # before list_sessions(), which makes a lado.db
    found = Plan(lado.__version__, to, update.installer(), [], [], server_run.running())
    found.agents_note = agents_note()
    for sess in state.list_sessions():
        status = runtime.session_status(sess)
        if status in (runtime.SessionStatus.RUNNING, runtime.SessionStatus.LOOP_DOWN):
            found.sessions.append(sess)
        elif status == runtime.SessionStatus.TMUX_GONE:
            found.gone.append(sess)
    if found.downgrade and live is not None:
        found.restore = _way_back(to.version, live, index, found.sessions)
    return found


def _way_back(
    version: str, live: int, index: dict | None, sessions: list[state.Session]
) -> Restore | None:
    """The Restore of an update to the older `version` from lado.db at schema `live`; None
    when that version knows this schema."""
    try:
        schema = update.release_schema(update.fetch_index() if index is None else index, version)
    except (OSError, ValueError) as exc:
        raise runtime.LadoError(
            f"cannot learn which lado.db schema LADO {version} needs: {exc}; nothing was stopped"
        ) from exc
    if schema >= live:
        return None
    copy = backups() / f"lado.db.schema-{schema}"
    if not copy.is_file():
        raise runtime.LadoError(
            f"LADO {version} needs lado.db at schema {schema}, and lado.db has schema {live}; "
            f"{backups()} holds no {copy.name} to go back to (docs/install.md, Going back to "
            "an older version); nothing was stopped"
        )
    try:
        # immutable: a read-only look at a WAL file may leave -wal and -shm in backups/.
        db = sqlite3.connect(f"{copy.as_uri()}?mode=ro&immutable=1", uri=True, timeout=10)
        try:
            names = {row[0] for row in db.execute("SELECT name FROM sessions")}
        finally:
            db.close()
    except sqlite3.Error as exc:
        raise runtime.LadoError(f"cannot read {copy}: {exc}; nothing was stopped") from exc
    made = datetime.datetime.fromtimestamp(copy.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    missing = [s.name for s in sessions if s.name not in names]
    return Restore(copy, schema, live, made, missing)


def agents_note() -> str | None:
    """The plan's line on where the resumed sessions' tmux server starts: from outside the
    graphical session of a Mac, launchd starts it there; with nobody logged in to it, the
    agent CLIs installed that keep their login in the keychain cannot read it."""
    where = gui_session.place()
    if where == gui_session.Place.REMOTE:
        return gui_session.PLAN_REMOTE
    if where == gui_session.Place.NO_GUI:
        users = providers.keychain_users(dict(os.environ), shutil.which)
        return gui_session.fill(gui_session.NO_GUI, users)
    return None


def latest_plan() -> Plan | None:
    """The plan for the release PyPI offers this LADO (`update.offered`), None when it is
    no newer. OSError or ValueError when the index cannot be read."""
    to = update.offered(update.fetch_index(), lado.__version__)
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
    back = found.restore
    if back:
        lines = [
            f"lado: WARNING: LADO {found.to.version} knows lado.db up to schema {back.schema}; "
            f"lado.db has schema {back.live}.",
            f"  lado.db goes back to {back.copy}, made {back.made}",
            f"  by the upgrade from schema {back.schema}. Everything LADO recorded since then "
            "is lost: sessions,",
            "  runs, gates, messages, projects. Repositories, worktrees and project folders "
            "stay on disk.",
        ]
        if back.missing:
            lines.append(
                f"  Sessions not in that copy are not started again: {', '.join(back.missing)}"
            )
        say("\n".join(lines), file=sys.stderr)
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
    if found.agents_note:
        say(found.agents_note)
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


def not_started(id: str, to: str, why: str) -> None:
    """The result of the UI's update `id` that ended before it started (PyPI unreachable, a
    refusal): `failed` with no log, so the page that waits for its id learns why. Written
    under the lock, and never over that update's own result or a running update's."""
    lock = take_lock(LOCK_WAIT)
    if lock is None:
        return
    with lock:
        last = update.read_result()
        if last and last.id == id:
            return
        now = _now()
        update.write_result(
            update.Result(
                "failed",
                lado.__version__,
                to,
                now,
                ended_at=now,
                id=id,
                reason=f"the update did not start: {why}",
            )
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


_TOKEN = re.compile(r"([?&]token=)[^\s&#]+")


class _Told:
    """`say` that also writes each line to update.log, with the UI's login token cut out of
    it (`lado ui` prints its link): the log's tail goes into the result, which the UI shows."""

    def __init__(self, say: Say, log: IO):
        self.say, self.log = say, log

    def __call__(self, text: str = "", *, file=None, end: str = "\n", flush: bool = False):
        self.say(text, file=file, end=end, flush=flush)
        self.log.write(_TOKEN.sub(r"\1…", text) + end)
        self.log.flush()


def run(found: Plan, say: Say = print, id: str | None = None) -> int:
    """The update `found` plans, with the installer it found: 0 when everything is on the
    new version again. UpdateRefused, with nothing written, when another update runs."""
    lock = take_lock(LOCK_WAIT)
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
        self.schema: int | None = None  # lado.db's before the installer, None without one
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
            # Nothing writes lado.db now; its copy is the migration's (state.migrate).
            self.schema = state.schema_version()
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
        database = "kept"
        back = self.plan.restore
        if back:
            try:
                restore(back.copy, state.home() / "lado.db")
                now_schema = state.schema_version()
            except sqlite3.Error as exc:
                why = f"lado.db not restored from {back.copy}: {exc}"
                return self._roll_back(why, stopped, [], started_server=False)
            if now_schema != back.schema:
                why = (
                    f"lado.db restored from {back.copy} has schema {now_schema}, not {back.schema}"
                )
                return self._roll_back(why, stopped, [], started_server=False)
            database = "restored"
            say(f"Restored lado.db from {back.copy} (schema {back.schema})")
            # The sessions the copy lacks are not in lado.db now: not started again.
            stopped = [s for s in stopped if s.name not in back.missing]
        say(f"Resuming on LADO {self.new}:", flush=True)
        resumed = self._resume(stopped, None, waits=takes_wait_for_login(self.new))
        if self.address:
            down = self._server(self.new)
            if down:
                return self._roll_back(down, stopped, resumed, started_server=True)
        if self.failed:
            count = len(self.failed)
            self.end(
                "partial", f"{count} session{'' if count == 1 else 's'} did not resume", database
            )
            return 1
        update.clear_pending()
        say(f"LADO {self.new} is ready." + (" Reload open UI tabs." if self.address else ""))
        self.end("ok", None, database)
        return 0

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
        self, sessions: list[state.Session], server: tuple[str, int] | None, waits: bool = True
    ) -> list[state.Session]:
        """Resume the sessions, then the UI server, with the installed `lado`'s commands;
        the sessions that resumed (the others go to `failed`). With `waits` (a `lado` that
        takes it: this version, or a new one from WAIT_FOR_LOGIN_SINCE) a supervisor whose
        CLI has no login waits for it (`--wait-for-login`), as at the container's start."""
        resumed, self.failed = [], []
        waiting = ["--wait-for-login"] if waits else []
        for sess in sessions:
            code = _run(
                self.binary,
                self.say,
                *("start", sess.repo, "--name", sess.name, "--no-attach", *waiting),
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
        reinstall the old version and check it, restore lado.db from the migration's copy
        only when its schema is newer than before, resume on the old version. Without that
        copy it changes nothing: the new version can open lado.db, the old one could not."""
        say = self.say
        copy = self._copy_needed()
        if copy and not copy.exists():
            reason = (
                f"{why}; not rolled back: lado.db has schema {state.schema_version()} and "
                f"backups/ holds no {copy.name} for LADO {self.old}, so LADO {self.new} "
                "stays installed"
            )
            say(f"lado: {reason}", file=sys.stderr)
            self.end("rollback_failed", reason)
            return 1
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
                    "end" + (f"; its backup is {copy}" if copy else ""),
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
        if copy:
            try:
                restore(copy, state.home() / "lado.db")
            except sqlite3.Error as exc:
                self.end(
                    "rollback_failed", f"{why}; lado.db not restored: {exc}; its backup is {copy}"
                )
                return 1
            database = "restored"
            say(f"Restored lado.db from {copy}")
        say(f"Resuming on LADO {self.old}:", flush=True)
        self._resume(stopped, self.address)
        self.end("rolled_back", why, database)
        return 1

    def _copy_needed(self) -> Path | None:
        """The migration's copy a rollback restores: when lado.db's schema is newer than
        before the update, backups/lado.db.schema-<the schema before>; else None."""
        now = state.schema_version()
        if self.schema is None or now is None or now <= self.schema:
            return None
        return backups() / f"lado.db.schema-{self.schema}"


def restore(source: Path, target: Path) -> None:
    """The copy `source` into `target`, the live file too, by SQLite's backup API (as
    state.copy_db). `source` is opened read-only and immutable: a copy gone since the plan
    is an sqlite3.Error before anything is written, never an empty database made in its
    place and copied over `target`; and no -wal or -shm is left beside it in backups/."""
    uri = f"{source.as_uri()}?mode=ro&immutable=1"
    with contextlib.closing(sqlite3.connect(uri, uri=True, timeout=10)) as src:
        with contextlib.closing(sqlite3.connect(target, timeout=10)) as dst:
            src.backup(dst)


def _install(installer: update.Installer, version: str, say: Say, verb: str = "Upgrading") -> int:
    argv = installer.command(version)
    say(f"{verb}: {shlex.join(argv)}", flush=True)
    return command(argv, say)


def _run(binary: Path, say: Say, *args: str) -> int:
    """`binary` with `args`: its exit code; its output said line by line."""
    return command([str(binary), *args], say)


def command(argv: list[str], say: Say) -> int:
    """Run `argv`: its exit code (127 when it cannot start); its output said line by line.
    Imports nothing: `lado update` and `lado uninstall` run it on a package being replaced."""
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
