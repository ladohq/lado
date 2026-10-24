"""The human's checks of a release candidate (docs/release.md, section 4).

    python3 scripts/rc_check.py sandbox [X.Y.ZrcN] [--provider NAME] [--no-ui]
    python3 scripts/rc_check.py upgrade X.Y.ZrcN
    python3 scripts/rc_check.py rollback

Run with `python3` from the repository's root on the RC's commit, never with `uv run`:
that puts the working copy's `.venv/bin/lado` first on PATH, and `upgrade` and
`rollback` run the human's own installed `lado` (they refuse one inside this repository).

`sandbox` first refuses, naming what to install, when `uv`, `tmux` or `git` is not on
PATH. It installs the RC (by default the newest release on PyPI, refused when that is a
final) with `uv tool install` into a temporary folder, with a LADO home, a tmux socket and
uv tool folders of its own and statistics off, checks it one line each, shows its UI until
Enter, then removes everything with the RC's own `lado uninstall`. A failed check keeps
the folder and prints the command that removes it, with the failed command's `[FAIL]`
lines (`lado doctor`'s form) or else its last lines; Ctrl-C removes it. The RC's image is
not checked here (docs/release.md, 4.5 and 4.6). `upgrade` runs the human's `lado update
X.Y.ZrcN`, then one `lado ls` (which migrates lado.db when no session resumed) and, coming
from a final whose schema the RC moved, keeps a copy of the migration's backup of that
final's database (`backups/lado.db.schema-<N>`) in `~/.lado-rc/`, as the migration keeps
only one. `rollback` goes back to the final of that copy: it asks first, stops the sessions
and the UI server, puts the copy into `backups/lado.db.schema-<N>` when the RC moved the
schema, runs `lado update <final>`, which restores it, and starts again the sessions the
copy has and the UI. `sandbox` and `upgrade` end with what is left by hand, the items
of CHANGELOG.md's `## X.Y.Z (unreleased)` among them (`release_notes.section`).

Exit 0 when every check passed, 1 for a failed check or a refusal, 2 for a usage error, 130
on Ctrl-C. Standard library only; nothing of LADO is imported.
"""

from __future__ import annotations  # the human's python3 may be older than LADO's

import argparse
import contextlib
import importlib.util
import json
import math
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repository this script is part of
PYPI_JSON = "https://pypi.org/pypi/lado/json"
PYPI_TIMEOUT = 10  # seconds
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:rc(\d+))?")  # the only forms LADO publishes
PYPROJECT_VERSION = re.compile(r'^version = "([^"]*)"', re.MULTILINE)
OUTPUT_LINES = 10  # of a failed command's output, under its [FAIL] line
# What the sandbox runs itself, each with how to install it (docs/install.md's ways).
NEEDED = {
    "uv": "brew install uv, or curl -LsSf https://astral.sh/uv/install.sh | sh",
    "tmux": "brew install tmux, or sudo apt install tmux",
    "git": "xcode-select --install, or sudo apt install git",
}
SESSION = "rc-check"  # the sandbox's session
# A calling agent's identity, the working copy's venv and the human's own tmux client
# never reach the sandbox's LADO.
DROPPED = ("LADO_SESSION", "LADO_AGENT", "LADO_INSTANCE", "VIRTUAL_ENV", "TMUX", "TMUX_PANE")
IDENTITY = "rc-check"  # the scratch repository's commit, with no git identity of the human's
BY_HAND = [
    "[ ] A session with the sdlc kit through one run to its first gate, answered in the UI",
    "[ ] The UI: the chat, a gate's card, the System panel with its pre-release pill",
]


class RcError(Exception):
    """A refusal: one line, exit 1."""


@dataclass(frozen=True, order=True)
class Version:
    """X.Y.Z or X.Y.ZrcN; a final sorts after its release candidates."""

    release: tuple[int, int, int]
    candidate: float  # N of rcN, math.inf for a final
    text: str = field(compare=False)

    @property
    def final(self) -> bool:
        return self.candidate == math.inf

    def __str__(self) -> str:
        return self.text


def parse(text: str) -> Version | None:
    match = VERSION.fullmatch(text.strip())
    if not match:
        return None
    candidate = math.inf if match[4] is None else int(match[4])
    return Version((int(match[1]), int(match[2]), int(match[3])), candidate, match[0])


def fetch_index() -> dict:
    """PyPI's JSON of the package."""
    with urllib.request.urlopen(PYPI_JSON, timeout=PYPI_TIMEOUT) as answer:
        return json.load(answer)


def releases(index: dict) -> list[Version]:
    """The releases of PyPI's JSON in order, but those of another form and yanked ones."""
    found = []
    for text, files in index.get("releases", {}).items():
        version = parse(text)
        if version and not (files and all(f.get("yanked") for f in files)):
            found.append(version)
    return sorted(found)


@dataclass(frozen=True)
class Result:
    code: int
    output: str  # stdout and stderr; empty for a command run on the terminal


def run(
    argv: list[str],
    env: dict[str, str] | None = None,
    terminal: bool = False,
    cwd: Path | None = None,
) -> Result:
    """Every command of the script: its output kept, or with `terminal` the human's
    terminal for its output and its questions."""
    try:
        if terminal:
            return Result(subprocess.run(argv, env=env, cwd=cwd, check=False).returncode, "")
        done = subprocess.run(
            argv,
            env=env,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except OSError as error:  # not on PATH, not executable
        return Result(127, f"{argv[0]}: {error.strerror or error}\n")
    return Result(done.returncode, done.stdout)


class Report:
    """The check lines, `[ok  ]` or `[FAIL]` as `lado doctor` prints them."""

    def __init__(self) -> None:
        self.failed = False

    def ok(self, what: str) -> None:
        print(f"[ok  ] {what}", flush=True)

    def fail(self, what: str, reason: str, output: str = "") -> None:
        self.failed = True
        print(f"[FAIL] {what}: {reason}", flush=True)
        for line in shown(output):
            print(f"         {line}")


def shown(output: str) -> list[str]:
    """The lines of a failed command's output under its [FAIL] line: the `[FAIL]` lines
    of `lado doctor`'s form with their indented hints, wherever they are, else the last
    OUTPUT_LINES."""
    lines = output.rstrip().splitlines()
    failures: list[str] = []
    in_block = False
    for line in lines:
        hint = line[:1].isspace() and bool(line.strip())
        in_block = line.startswith("[FAIL]") or (in_block and hint)
        if in_block:
            failures.append(line)
    return failures or lines[-OUTPUT_LINES:]


def missing_tools() -> list[str]:
    """The programs of NEEDED that are not on PATH."""
    return [name for name in NEEDED if shutil.which(name) is None]


def _release_notes():
    """scripts/release_notes.py, beside this script: the CHANGELOG's rules are its own."""
    path = Path(__file__).resolve().with_name("release_notes.py")
    spec = importlib.util.spec_from_file_location("release_notes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checklist(version: Version, changelog: str | None, pyproject: str | None) -> list[str]:
    """What is left to the human: the checks by hand, then each item of the RC's section
    of CHANGELOG.md, then what makes that list doubtful."""
    lines = list(BY_HAND)
    if changelog is None:
        lines.append("warning: no CHANGELOG.md here: run the script from the repository's root")
    else:
        notes = _release_notes()
        try:
            text = notes.section(f"v{version}", changelog)
        except notes.NotesError as error:
            lines.append(f"warning: {error}")
        else:
            lines += [f"[ ] {line[2:]}" for line in text.splitlines() if line.startswith("- ")]
    found = PYPROJECT_VERSION.search(pyproject or "")
    if found and found[1] != str(version):
        lines.append(
            f"warning: pyproject.toml says {found[1]}, not {version}: this checkout is not the "
            "RC's commit, and its CHANGELOG.md may not be the RC's"
        )
    return lines


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def print_checklist(version: Version) -> None:
    print(f"\nLeft to check by hand on LADO {version}:")
    for line in checklist(version, _read(Path("CHANGELOG.md")), _read(Path("pyproject.toml"))):
        print(f"  {line}")


class Failed(Exception):
    """A check failed; its [FAIL] line is printed."""


def _ran(
    report: Report,
    what: str,
    name: str,
    argv: list[str],
    env: dict[str, str],
    cwd: Path | None = None,
) -> Result:
    """`argv`'s result; a [FAIL] line for `what` and Failed when it exits non-zero."""
    result = run(argv, env=env, cwd=cwd)
    _require(report, what, not result.code, f"{name} exited {result.code}", result.output)
    return result


def _require(report: Report, what: str, holds: bool, reason: str, output: str = "") -> None:
    """Nothing when `holds`; else a [FAIL] line for `what` and Failed."""
    if not holds:
        report.fail(what, reason, output)
        raise Failed


@dataclass(frozen=True)
class Sandbox:
    """The temporary folder of a clean install: its LADO home, uv tool folders, scratch
    repository, and a tmux socket of its own."""

    root: Path
    socket: str

    @classmethod
    def create(cls) -> Sandbox:
        return cls(Path(tempfile.mkdtemp(prefix="lado-rc-")), f"lado-rc-{os.getpid()}")

    @property
    def home(self) -> Path:
        return self.root / "home"

    @property
    def tools(self) -> Path:
        return self.root / "tools"

    @property
    def bin(self) -> Path:
        return self.root / "bin"

    @property
    def repo(self) -> Path:
        return self.root / "repo"

    @property
    def lado(self) -> str:
        return str(self.bin / "lado")

    def env(self) -> dict[str, str]:
        """The environment of every command of the sandbox: nothing of it reaches the
        human's LADO home, tmux server or uv tools, and its LADO sends no statistics."""
        env = {name: value for name, value in os.environ.items() if name not in DROPPED}
        env.update(
            LADO_HOME=str(self.home),
            LADO_TMUX_SOCKET=self.socket,
            UV_TOOL_DIR=str(self.tools),
            UV_TOOL_BIN_DIR=str(self.bin),
            LADO_TELEMETRY="0",
        )
        return env

    def cleanup_line(self) -> str:
        """One command that stops and removes a kept sandbox."""
        q = shlex.quote
        return (
            f"LADO_HOME={q(str(self.home))} LADO_TMUX_SOCKET={q(self.socket)} LADO_TELEMETRY=0 "
            f"{q(self.lado)} uninstall --yes; tmux -L {q(self.socket)} kill-server; "
            f"rm -rf {q(str(self.root))} {q(str(self.socket_file))}"
        )

    @property
    def socket_file(self) -> Path:
        """The socket's file, which tmux leaves behind when its server ends."""
        folder = Path(os.environ.get("TMUX_TMPDIR") or "/tmp") / f"tmux-{os.getuid()}"
        return folder / self.socket

    def delete(self) -> None:
        """The folder and the socket's file gone."""
        shutil.rmtree(self.root, ignore_errors=True)
        with contextlib.suppress(OSError):
            self.socket_file.unlink()

    def remove(self, stop: bool) -> None:
        """Everything of the sandbox gone, whatever each step says (after a Ctrl-C)."""
        env = self.env()
        if stop:
            run([self.lado, "stop", SESSION], env=env)
        run([self.lado, "uninstall", "--yes"], env=env)
        run(["tmux", "-L", self.socket, "kill-server"], env=env)
        self.delete()


def _sandbox_checks(
    box: Sandbox, version: Version, provider: str, ui: bool, report: Report, done: list[str]
) -> None:
    """The sandbox's checks in order; Failed at the first that fails. `done` gets
    "session" once its session may run and "stopped" once it is stopped."""
    env, lado = box.env(), box.lado
    install = ["uv", "tool", "install", "--refresh-package", "lado", f"lado=={version}"]
    _ran(report, "install", "uv tool install", install, env)
    report.ok(f"install: lado {version} with uv tool install")

    said = _ran(report, "version", "lado --version", [lado, "--version"], env).output.strip()
    _require(report, "version", said == f"lado {version}", f"lado --version says {said}")
    report.ok(f"version: {said}")

    what = "statistics off"
    status = _ran(report, what, "lado telemetry status", [lado, "telemetry", "status"], env)
    off = "LADO_TELEMETRY=0 is set"
    holds = off in status.output
    _require(report, what, holds, f"lado telemetry status does not say {off}", status.output)
    report.ok("statistics off: LADO_TELEMETRY=0")

    doctor = _ran(report, "doctor", "lado doctor", [lado, "doctor"], env)
    shown = f"{version} (pre-release)"
    _require(report, "doctor", shown in doctor.output, f"it does not say {shown}", doctor.output)
    report.ok(f"doctor: no FAIL, {shown}")

    box.repo.mkdir()
    _ran(report, "scratch repository", "git init", ["git", "init", "-q", str(box.repo)], env)
    (box.repo / "README.md").write_text("A scratch repository of scripts/rc_check.py.\n")
    _ran(report, "scratch repository", "git add", ["git", "add", "README.md"], env, box.repo)
    email = f"{IDENTITY}@localhost"
    identity = {
        "GIT_AUTHOR_NAME": IDENTITY,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": IDENTITY,
        "GIT_COMMITTER_EMAIL": email,
    }
    commit = ["git", "commit", "-q", "--no-verify", "--no-gpg-sign", "-m", "A scratch repository"]
    _ran(report, "scratch repository", "git commit", commit, {**env, **identity}, box.repo)
    report.ok(f"scratch repository: {box.repo}, one commit")

    done.append("session")
    start = [lado, "start", str(box.repo), "--name", SESSION, "--provider", provider, "--no-attach"]
    _ran(report, "session starts", "lado start", start, env)
    listed = _ran(report, "session starts", "lado ls", [lado, "ls"], env).output
    # Its line, `<name>  <repo>`, has no `(stopped)` or `(tmux session is gone)` after it.
    holds = any(line.split()[:1] == [SESSION] and "(" not in line for line in listed.splitlines())
    _require(report, "session starts", holds, f"lado ls does not show {SESSION} running", listed)
    report.ok(f"session starts: {SESSION} with {provider}, shown by lado ls")

    if ui:
        code = run([lado, "ui", "--no-open", "--port", "0"], env=env, terminal=True).code
        _require(report, "UI", not code, f"lado ui exited {code}")
        try:
            input("Look at the sandbox's UI (the link above), then press Enter: ")
        except EOFError:
            print()

    _ran(report, "session stops", "lado stop", [lado, "stop", SESSION], env)
    done.append("stopped")
    report.ok(f"session stops: lado stop {SESSION}")

    removed = _ran(report, "uninstall", "lado uninstall", [lado, "uninstall", "--yes"], env)
    gone = not box.home.exists()
    _require(report, "uninstall", gone, f"{box.home} is still there", removed.output)
    server = run(["tmux", "-L", box.socket, "list-sessions"], env=env)
    _require(report, "uninstall", server.code != 0, "its tmux server still runs", server.output)
    report.ok("uninstall: its LADO home and tmux server are gone")


def sandbox(version: Version, provider: str, ui: bool) -> int:
    """`sandbox`: a clean install of `version`, checked, then removed."""
    box = Sandbox.create()
    print(f"Sandbox of LADO {version}: {box.root} (tmux socket {box.socket})", flush=True)
    done: list[str] = []
    try:
        _sandbox_checks(box, version, provider, ui, Report(), done)
    except Failed:
        print(f"\nThe sandbox is kept for a look: {box.root}")
        print(f"Remove it with: {box.cleanup_line()}")
        return 1
    except KeyboardInterrupt:
        box.remove(stop="session" in done and "stopped" not in done)
        print("\nInterrupted: the sandbox is removed.")
        return 130
    box.delete()
    print(f"The sandbox is removed: {box.root}")
    print_checklist(version)
    return 0


def own_lado() -> str:
    """The human's own `lado` on PATH; RcError for none, or for one of this repository
    (its `.venv`, first on PATH under `uv run`)."""
    found = shutil.which("lado")
    if found is None:
        raise RcError("no lado on PATH: install LADO first (docs/install.md)")
    if Path(found).resolve().is_relative_to(ROOT):
        raise RcError(
            f"lado on PATH is this repository's {found}, not your installed LADO: run "
            "python3 scripts/rc_check.py, not under uv run or an activated .venv"
        )
    return found


def lado_home() -> Path:
    return Path(os.environ.get("LADO_HOME") or Path.home() / ".lado").expanduser()


def keep_dir() -> Path:
    """Where the final's database is kept: outside LADO_HOME, so neither `lado update`
    nor `lado uninstall` removes it."""
    return Path.home() / ".lado-rc"


def kept() -> list[Path]:
    """The copies in keep_dir(), `lado.db.<version>` each."""
    folder = keep_dir()
    if not folder.is_dir():
        return []
    prefix = "lado.db."
    return sorted(
        p for p in folder.iterdir() if p.name.startswith(prefix) and parse(p.name[len(prefix) :])
    )


def installed(lado: str) -> Version:
    """The version `lado --version` says; RcError when it says none."""
    said = run([lado, "--version"]).output.strip()
    version = parse(said.removeprefix("lado "))
    if version is None:
        raise RcError(f"{lado} --version says {said or 'nothing'}, no LADO version")
    return version


def _copy(source: Path, target: Path) -> None:
    """`source` as `target`, the only file of its folder: written beside it, then renamed."""
    target.parent.mkdir(parents=True, exist_ok=True)
    written = target.with_name(f".{target.name}.tmp")
    shutil.copy2(source, written)
    written.replace(target)
    for other in target.parent.iterdir():
        if other != target:
            other.unlink()


def upgrade(version: Version) -> int:
    """`upgrade`: the human's `lado update <version>`, then, coming from a final whose
    schema the RC moved, a copy of the migration's backup of that final's database in
    keep_dir()."""
    lado = own_lado()
    before = installed(lado)
    live = lado_home() / "lado.db"
    schema_before = _schema(live) if live.exists() else None
    print(f"Your LADO is {before}; running lado update {version}:", flush=True)
    code = run([lado, "update", str(version)], terminal=True).code
    # By the version, not the exit code: an update that installed the RC exits 1 when a
    # session did not resume on it (`partial`), and the final's database is there all the same.
    after = installed(lado)
    if after != version:
        if code:
            print(
                f"rc_check: lado update {version} did not update (exit {code}): nothing kept",
                file=sys.stderr,
            )
            return code
        raise RcError(f"lado --version says lado {after} after the update, not {version}")
    # With no session resumed nothing has migrated lado.db yet: any command of the RC does.
    listed = run([lado, "ls"])
    if listed.code:
        print(listed.output, end="")
    if before.final:
        _keep(before, live, schema_before)
    else:
        copies = kept()
        if copies:
            final = copies[-1].name.removeprefix("lado.db.")
            print(f"{copies[-1]} stays: rollback goes back to LADO {final}")
        else:
            print(
                "warning: ~/.lado-rc holds no copy of a final's database: rollback cannot "
                "restore lado.db"
            )
    print_checklist(version)
    if code:
        print(
            f"rc_check: lado update {version} exited {code}, but LADO is {version} now: "
            "read what it printed above (a session that did not resume?)",
            file=sys.stderr,
        )
    return code


def _keep(final: Version, live: Path, schema_before: int | None) -> None:
    """The final's database for rollback: the migration's backup of it, when the RC moved
    the schema."""
    if schema_before is None:
        print(f"no lado.db: nothing kept; `lado update {final}` alone goes back")
        return
    if _schema(live) == schema_before:
        print(
            f"lado.db keeps schema {schema_before}: nothing kept; `lado update {final}` "
            "alone goes back"
        )
        return
    backup = lado_home() / "backups" / f"lado.db.schema-{schema_before}"
    if not backup.is_file():
        print(f"warning: no backup {backup}: rollback has no copy of LADO {final}'s database")
        return
    target = keep_dir() / f"lado.db.{final}"
    _copy(backup, target)
    print(f"Kept a copy of LADO {final}'s database: {target} (for rollback)")


def _terminal() -> bool:
    return sys.stdin.isatty()


def _read_only(path: Path) -> contextlib.closing:
    return contextlib.closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True))


def _schema(path: Path) -> int:
    with _read_only(path) as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def _hand_over(copy: Path, schema: int) -> Path:
    """The copy where `lado update` looks for it, backups/lado.db.schema-<schema>: written
    beside it, then renamed over a file of that name; the other files stay."""
    target = lado_home() / "backups" / f"lado.db.schema-{schema}"
    target.parent.mkdir(parents=True, exist_ok=True)
    written = target.with_name(f"{target.name}.tmp")
    shutil.copy2(copy, written)
    written.replace(target)
    return target


def _alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@dataclass(frozen=True)
class Plan:
    """What a rollback does, read before it changes anything."""

    lado: str
    now: Version
    final: Version
    copy: Path
    live: Path
    sessions: list[tuple[str, str]]  # (name, repo): not stopped and alive in tmux
    server: dict | None  # server.json of a UI server that runs
    live_schema: int
    copy_schema: int
    copy_sessions: list[str]  # the names the copy has

    @property
    def restore(self) -> bool:
        return self.live_schema > self.copy_schema

    @property
    def started(self) -> list[tuple[str, str]]:
        """The sessions started again: after a restore only those the copy has."""
        if not self.restore:
            return self.sessions
        return [(name, repo) for name, repo in self.sessions if name in self.copy_sessions]

    def resume_lines(self) -> list[str]:
        """The commands that start the sessions and the UI server again by hand."""
        lines = [f"lado start {shlex.quote(repo)} --name {name}" for name, repo in self.sessions]
        if self.server:
            lines.append(" ".join(_ui_args("lado", self.server, opened=True)))
        return lines


def _ui_args(lado: str, server: dict, opened: bool = False) -> list[str]:
    """`lado ui` of a server on the same host and port again."""
    argv = [lado, "ui", *([] if opened else ["--no-open"]), "--port", str(server["port"])]
    host = server.get("host", "127.0.0.1")
    return argv if host == "127.0.0.1" else [*argv, "--host", host]


def plan() -> Plan:
    lado = own_lado()
    now = installed(lado)
    if now.final:
        raise RcError(f"your LADO is {now}, no pre-release: nothing to roll back")
    copies = kept()
    if not copies:
        raise RcError(
            "~/.lado-rc holds no copy of a final's lado.db: upgrade from a final makes it. "
            "Without a schema change since that final, `lado update <final>` is enough"
        )
    if len(copies) > 1:
        names = ", ".join(p.name for p in copies)
        raise RcError(f"~/.lado-rc holds more than one copy ({names}): keep the one to go back to")
    copy = copies[0]
    final = parse(copy.name.removeprefix("lado.db."))
    home = lado_home()
    live = home / "lado.db"
    sessions: list[tuple[str, str]] = []
    live_schema = 0
    if live.exists():
        live_schema = _schema(live)
        with _read_only(live) as db:
            rows = db.execute(
                "SELECT name, repo FROM sessions WHERE stopped_at IS NULL ORDER BY name"
            ).fetchall()
        socket = os.environ.get("LADO_TMUX_SOCKET") or "lado"
        for name, repo in rows:
            # A session whose tmux is gone is no running one: it is not started again.
            if run(["tmux", "-L", socket, "has-session", "-t", f"={name}"]).code == 0:
                sessions.append((name, repo))
    server = None
    try:
        info = json.loads((home / "server.json").read_text())
    except (OSError, ValueError):
        info = None
    if isinstance(info, dict) and _alive(info.get("pid")) and "port" in info:
        server = info
    with _read_only(copy) as db:
        copy_sessions = [row[0] for row in db.execute("SELECT name FROM sessions")]
    return Plan(
        lado, now, final, copy, live, sessions, server, live_schema, _schema(copy), copy_sessions
    )


def print_plan(p: Plan) -> None:
    print(f"Roll back LADO {p.now} to {p.final}:")
    if p.sessions:
        listed = ", ".join(f"{name} ({repo})" for name, repo in p.sessions)
        print(f"- stop your sessions and start them again on {p.final}: {listed}")
    else:
        print("- no session runs")
    if p.server:
        where = f"{p.server.get('host', '127.0.0.1')}:{p.server['port']}"
        print(f"- stop the UI server and start it again on {where}")
    else:
        print("- the UI server does not run")
    print(f"- lado update {p.final} (it shows its plan and asks too)")
    if p.restore:
        print(
            f"- restore lado.db from {p.copy}: its schema {p.copy_schema} is older than "
            f"lado.db's {p.live_schema}, so everything done on the RC since the upgrade is lost;"
            f" lado update {p.final} restores it from backups/lado.db.schema-{p.copy_schema}"
        )
        lost = [name for name, repo in p.sessions if (name, repo) not in p.started]
        if lost:
            print(f"- not started again, not in the copy: {', '.join(lost)}")
    else:
        print(f"- lado.db is kept: its schema {p.live_schema} is the copy's")


def _stopped(p: Plan, why: str, all_stopped: bool = True) -> int:
    """The rollback ends before the restore: what is left and how to start it again."""
    sessions = (
        "your sessions are stopped"
        if all_stopped
        else "some of your sessions may be stopped (lado ls)"
    )
    print(f"rc_check: {why}: lado.db is not restored, and {sessions}.", file=sys.stderr)
    lines = p.resume_lines()
    if lines:
        print("Start them again with:", file=sys.stderr)
        for line in lines:
            print(f"  {line}", file=sys.stderr)
    return 1


def rollback() -> int:
    """`rollback`: back to the final of the kept copy, after the human's yes."""
    p = plan()
    print_plan(p)
    if not _terminal():
        raise RcError("rollback asks first: run it on a terminal")
    if input("Roll back? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Not rolled back.")
        return 1
    code = run([p.lado, "stop", "--all"], terminal=True).code
    if code:
        return _stopped(p, f"lado stop --all exited {code}", all_stopped=False)
    code = run([p.lado, "server", "stop"], terminal=True).code
    if code:
        return _stopped(p, f"lado server stop exited {code}")
    if p.restore:  # lado update <final> warns, asks and restores it (docs/install.md)
        _hand_over(p.copy, p.copy_schema)
    code = run([p.lado, "update", str(p.final)], terminal=True).code
    if code:
        return _stopped(p, f"lado update {p.final} did not update (exit {code})")
    after = installed(p.lado)
    if after != p.final:
        return _stopped(p, f"lado --version says lado {after}, not {p.final}")
    report = Report()
    if p.restore:
        restored = _schema(p.live)
        if restored != p.copy_schema:
            report.fail("lado.db restored", f"its schema is {restored}, not {p.copy_schema}")
            return _stopped(p, "the restore did not take")
        report.ok(f"lado.db restored: schema {restored}, from {p.copy}")
    for name, repo in p.started:
        started = run([p.lado, "start", repo, "--name", name, "--no-attach"])
        if started.code:
            report.fail(f"session {name}", f"lado start exited {started.code}", started.output)
        else:
            report.ok(f"session {name} started on {p.final}")
    if p.server:
        ui = run(_ui_args(p.lado, p.server))
        if ui.code:
            report.fail("UI server", f"lado ui exited {ui.code}", ui.output)
        else:
            report.ok(f"UI server started on {p.final}")
    print(f"Rolled back to LADO {p.final}.")
    return 1 if report.failed else 0


def _version(text: str) -> Version:
    version = parse(text)
    if version is None:
        raise argparse.ArgumentTypeError(f"{text!r} is no LADO version (X.Y.Z or X.Y.ZrcN)")
    return version


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rc_check.py", description="The checks of a release candidate (docs/release.md)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    box = commands.add_parser("sandbox", help="check a clean install of the RC, then remove it")
    box.add_argument("version", nargs="?", type=_version, help="X.Y.ZrcN; the newest on PyPI")
    box.add_argument("--provider", default="claude", help="the session's (default claude)")
    box.add_argument("--no-ui", action="store_true", help="do not open the sandbox's UI")
    up = commands.add_parser("upgrade", help="move your own LADO onto the RC")
    up.add_argument("version", type=_version, help="X.Y.ZrcN")
    commands.add_parser("rollback", help="go back to the final you upgraded from")
    return parser


def _final_refused(version: Version) -> int:
    print(
        f"rc_check: {version} is a final release: name the RC to check (X.Y.ZrcN)",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "sandbox":
            lacking = missing_tools()
            if lacking:
                hints = "; ".join(f"{name}: {NEEDED[name]}" for name in lacking)
                raise RcError(
                    f"not on PATH: {', '.join(lacking)}; install first ({hints}; docs/install.md)"
                )
            version = args.version
            if version is None:
                try:
                    found = releases(fetch_index())
                except (OSError, ValueError) as error:
                    Report().fail("PyPI", str(getattr(error, "reason", error)))
                    return 1
                if not found:
                    Report().fail("PyPI", "it lists no release of LADO")
                    return 1
                version = found[-1]
            if version.final:
                return _final_refused(version)
            return sandbox(version, args.provider, not args.no_ui)
        if os.environ.get("LADO_AGENT"):
            raise RcError(
                f"{args.command} is the human's: run it on your terminal, not in an agent"
            )
        if args.command == "upgrade":
            if args.version.final:
                return _final_refused(args.version)
            return upgrade(args.version)
        return rollback()
    except RcError as error:
        print(f"rc_check: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nrc_check: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
