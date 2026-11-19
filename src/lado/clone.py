"""A repository from its git URL: what a URL is, the folder a clone goes to by default,
whether a folder may take a clone, the remote's branches, and the clone itself, with
progress and cancellation (openspec change clone-from-url). `lado start <git-url>` and the
UI server's clone jobs (`server/clones.py`) both call it, and print only what it says.

LADO uses only the access git already has on this machine (ssh keys, a credential helper,
the saved git servers, github.com's included, variables of the outside folder or, for a
clone into a project, of the project: lado.agent_env.for_git): its git calls run with no
terminal and no prompt, so a missing credential is a failure, never a wait. LADO's
container has no ssh: there an ssh failure points at Settings → Git servers. The kinds of a
failure here also tell those of LADO's git for kits (`explain`, lado.gitcache). A URL
reaches a text only through `runtime.public_remote`."""

import codecs
import os
import re
import select
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lado import (
    agent_env,
    git_servers,
    gitcache,
    project_secrets,
    projects,
    runtime,
    state,
    update,
)

URL = re.compile(r"(https?|ssh|git|file)://(.+)", re.IGNORECASE)
# user@host:path, git's scp form; a bare host:path would take a folder with a colon.
SCP = re.compile(r"([^\s@/:]+)@([^\s@/:]+):(.+)")


LIST_TIMEOUT = 20  # seconds a listing of the remote's branches may take
STOP_WAIT = 2  # seconds git's process group gets after SIGTERM, before SIGKILL
# A clone job of the UI server (server/clones.py): one no request asked about for ABANDONED
# seconds is cancelled (its window went away without its beacon: a lost connection, a
# sleeping laptop); longer than the minute a browser may leave between the timers of a tab
# in the background. A finished one is kept KEPT seconds.
ABANDONED = 150
KEPT = 60


def is_url(source: str) -> bool:
    """Whether `source` is a git URL to clone; anything else is a folder."""
    if source.startswith("-"):  # never an option of git's
        return False
    return bool(URL.fullmatch(source) or SCP.fullmatch(source))


@dataclass(frozen=True)
class Address:
    """The parts of a git URL that name its repository. A local path (or `file://`) is
    scheme `file` with no host."""

    scheme: str
    user: str | None
    host: str  # lowercased; "" for a local path
    port: int | None
    path: str

    @classmethod
    def parse(cls, source: str) -> "Address":
        url = URL.fullmatch(source)
        if url:
            scheme, rest = url.group(1).lower(), url.group(2)
            if scheme == "file":
                path = rest if rest.startswith("/") else "/" + rest.partition("/")[2]
                return cls("file", None, "", None, path)
            netloc, _, path = rest.partition("/")
            userinfo, at, hostport = netloc.rpartition("@")
            host, _, port = hostport.partition(":")
            return cls(
                scheme,
                userinfo.partition(":")[0] if at else None,
                host.lower(),
                int(port) if port.isdigit() else None,
                path,
            )
        scp = SCP.fullmatch(source)
        if scp:
            return cls("ssh", scp.group(1), scp.group(2).lower(), None, scp.group(3))
        return cls("file", None, "", None, source)

    def _segments(self) -> list[str]:
        path = self.path.strip("/")
        if path.endswith(".git"):
            path = path[: -len(".git")]
        return [part for part in path.split("/") if part and part != "~"]

    @property
    def repo_name(self) -> str:
        """The last path segment; none for `.` or `..`, which name no repository."""
        segments = self._segments()
        return segments[-1] if segments and segments[-1] not in (".", "..") else ""

    @property
    def owner(self) -> str | None:
        """The path segment before the repository's name (an account or group), if any."""
        segments = self._segments()
        return segments[-2] if len(segments) > 1 else None

    def same_repo(self, other: "Address") -> bool:
        """The same repository: the same host and path, whatever the scheme, user or port;
        local ones by real path."""
        if self.scheme == "file" or other.scheme == "file":
            return self.scheme == other.scheme == "file" and os.path.realpath(
                os.path.expanduser(self.path.rstrip("/"))
            ) == os.path.realpath(os.path.expanduser(other.path.rstrip("/")))
        return self.host == other.host and self._segments() == other._segments()


def default_folder(url: str) -> Path:
    """The folder a clone of `url` goes to when the human gives none: <workspace>/<repo>
    (`projects.workspace`); a URL that names no repository has none (it would be the parent
    itself)."""
    name = Address.parse(url).repo_name
    if not name:
        raise CloneError(
            "no_repo_name",
            f"{runtime.public_remote(url)} names no repository: give the folder to clone into",
        )
    return projects.workspace() / name


@dataclass(frozen=True)
class ServerWay:
    """A failure's way out through Settings → Git servers, for the UI: `way` "check" for the
    saved server git took the token of, "add" for an unsaved host; `host` the server's key
    (lado.git_servers.Address.key), `address` its root, `page` the UI's sentence."""

    way: Literal["check", "add"]
    host: str
    address: str
    page: str


class CloneError(runtime.LadoError):
    """Why a listing or a clone did not happen, by kind, with a hint when the human can
    act (LAD-5's `runtime.Hint`) and, for an access failure a git server can fix, its
    `server` way out."""

    def __init__(
        self,
        kind: str,
        text: str,
        hint: runtime.Hint | None = None,
        server: ServerWay | None = None,
    ) -> None:
        super().__init__(text)
        self.kind = kind
        self.hint = hint
        self.server = server


def _git_runs() -> None:
    """LAD-5's look at whether git runs, its `no_git` / `git_broken` as a CloneError."""
    try:
        runtime.git_version()
    except runtime.FolderProblem as problem:
        raise CloneError(problem.kind, str(problem), problem.hint) from None


TargetState = Literal[
    "new", "empty", "same_repo", "other_repo", "not_empty", "not_folder", "in_project"
]
CAN_CLONE = ("new", "empty")  # the target states a clone may start in


@dataclass(frozen=True)
class Target:
    """A folder a clone of a URL would go to, as LADO found it; it changes nothing there."""

    path: str
    state: TargetState
    text: str
    origin: str | None = None  # the folder's origin, through runtime.public_remote
    branch: str | None = None  # the folder's current branch, for same_repo
    suggestion: str | None = None  # a free folder beside it, for other_repo
    hint: runtime.Hint | None = None  # what to do instead, for in_project


def check_target(url: str, path: str, project: str | None = None) -> Target:
    """Whether a clone of `url` may go to the folder `path` (a full path), and what is
    there when not. Only `CAN_CLONE` states let a clone start; a folder LADO may not look
    at is a CloneError `no_access`. With `project`, a folder directly in that project's
    folder is no `in_project` (`projects.adds_to`): the clone adds a repository to it."""
    try:
        return _check_target(url, path, project)
    except OSError as exc:
        raise CloneError("no_access", f"cannot look at {path}: {exc.strerror or exc}") from None


def _check_target(url: str, path: str, project: str | None) -> Target:
    # A new session without a project could not start there.
    if not projects.adds_to(project, path) and (refused := projects.refusal(path, url=url)):
        return Target(path, "in_project", str(refused), hint=refused.hint)
    folder = Path(path)
    # stat, not exists() and is_dir(): from Python 3.14 on they answer False for a folder
    # LADO may not look into, where the clone must be refused as no_access.
    try:
        mode = folder.stat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return Target(path, "new", "a new folder")
    if not stat.S_ISDIR(mode):
        return Target(path, "not_folder", f"{path} is a file, not a folder")
    if not any(folder.iterdir()):
        return Target(path, "empty", "an empty folder")
    origin = _origin_of_root(path)
    public = runtime.public_remote(url)
    if origin is None:
        text = f"{path} is not empty and is not a clone of {public}: choose another folder"
        return Target(path, "not_empty", text)
    shown = runtime.public_remote(origin)
    address = Address.parse(url)
    if address.same_repo(Address.parse(origin)):
        branch = runtime.branch(path)
        where = f"on branch {branch}" if branch else "at a detached HEAD"
        text = f"{path} is already a clone of this repository (origin {shown}), {where}"
        return Target(path, "same_repo", text, shown, branch)
    suggestion = None
    if address.owner:
        beside = folder.parent / f"{address.owner}-{address.repo_name}"
        if not beside.exists():
            suggestion = str(beside)
    text = f"{path} is a clone of another repository (origin {shown}): choose another folder"
    if suggestion:
        text += f", e.g. {suggestion}"
    return Target(path, "other_repo", text, shown, suggestion=suggestion)


def _origin_of_root(path: str) -> str | None:
    """The origin of the repository whose root `path` is; None when it is no repository's
    root (a subfolder of one is not) or has no origin."""
    _git_runs()
    try:
        top = runtime.git(path, "rev-parse", "--show-toplevel")
    except runtime.LadoError:
        return None
    if os.path.realpath(top) != os.path.realpath(path):
        return None
    return runtime.remote(path)


# A failure's kind by git's words (LC_ALL=C), the first that matches.
KINDS: tuple[tuple[str, re.Pattern], ...] = (
    ("ssh_denied", re.compile(r"Permission denied \(publickey")),
    ("host_key", re.compile(r"Host key verification failed")),
    (
        "login_needed",
        re.compile(r"could not read Username|Authentication failed|terminal prompts disabled"),
    ),
    ("access_denied", re.compile(r"The requested URL returned error: 403")),
    (
        "not_found",
        re.compile(
            r"Repository not found|does not appear to be a git repository"
            r"|repository '[^']*' not found"
        ),
    ),
    (
        "unreachable",
        re.compile(
            r"Could not resolve host|Connection refused|Connection timed out"
            r"|Network is unreachable|Operation timed out"
        ),
    ),
    ("no_branch", re.compile(r"Remote branch .* not found")),
)
GIT_FAILED = "git_failed"
_LINE = re.compile(r"(fatal|error|ERROR):")
_ANY_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"]+")


def kind_of(stderr: str) -> str:
    for kind, words in KINDS:
        if words.search(stderr):
            return kind
    return GIT_FAILED


def _gits_line(stderr: str) -> str:
    """git's first error line, else its last line; any URL in it without a secret."""
    lines = [line.strip() for line in re.split(r"[\r\n]", stderr) if line.strip()]
    line = next((line for line in lines if _LINE.match(line)), lines[-1] if lines else "")
    return _ANY_URL.sub(lambda url: runtime.public_remote(url.group()), line)


def _ssh_check(address: Address) -> str:
    port = f"-p {address.port} " if address.port else ""
    return f"ssh -T {port}{address.user or 'git'}@{address.host}"


def _reason(kind: str, address: Address, branch: str | None) -> tuple[str, runtime.Hint | None]:
    host = address.host
    if kind == "ssh_denied":
        hint = f"Check that this machine's ssh key is added to your account on {host}:"
        return f"{host} refused this machine's ssh key", runtime.Hint(hint, _ssh_check(address))
    if kind == "host_key":
        hint = runtime.Hint(
            "Connect once in a terminal and accept the host key:", _ssh_check(address)
        )
        return f"this machine does not know {host}'s ssh host key yet", hint
    if kind == "login_needed":
        return (
            f"{host} asks for a login; set up a git credential helper for it on this machine",
            None,
        )
    if kind == "access_denied":
        return f"{host} refused access", None
    if kind == "not_found":
        return "no repository there, or this machine's account cannot read it", None
    if kind == "unreachable":
        return f"{host} cannot be reached", None
    return f"no branch {branch}", None  # no_branch


ACCESS_KINDS = ("login_needed", "access_denied", "not_found")
CHECK_PAGE = "Check this git server; if its token expired or was revoked, replace it there."


def _saved_servers() -> list[state.GitServer] | None:
    """The saved git servers, none without a lado.db; None (not known) for a lado.db at
    another schema than this LADO's. A failure's text never makes or migrates lado.db."""
    version = state.schema_version()
    if version is None:
        return []
    if version != state.SCHEMA_VERSION:
        return None
    try:
        return state.git_servers()
    except state.SchemaError:
        return None


def _server_way(
    kind: str, url: str, address: Address, servers: list[state.GitServer]
) -> tuple[str, runtime.Hint, ServerWay] | None:
    """An access failure's (`ACCESS_KINDS`) reason, hint and way out through the git
    servers: the saved server git took the token of (`git_servers.server_for`), else an
    unsaved http(s) host other than github.com to add; None for neither, as for a host saved
    under another scheme or port, whose token git did not take and which could not be added
    again."""
    host = address.host
    server = git_servers.server_for(url, servers)
    if server is not None and (
        address.scheme == "ssh" or urllib.parse.urlsplit(server.address).scheme == address.scheme
    ):
        root, key = server.address, server.host  # the host with its port
        reason = {
            "login_needed": f"{key} refused the token of the git server {root}",
            "access_denied": f"{key} refused access with the token of the git server {root}",
            "not_found": f"no repository there, or the token of the git server {root} cannot "
            "read it",
        }[kind]
        hint = runtime.Hint(
            "Check the git server:",
            f"lado git-server check {root}",
            (
                runtime.Hint(
                    "If its token expired or was revoked, replace it:",
                    f"{git_servers.ADD} {root} --token",
                ),
            ),
        )
        return reason, hint, ServerWay("check", server.host, root, CHECK_PAGE)
    if (
        kind == "not_found"
        or address.scheme not in ("https", "http")
        or any(urllib.parse.urlsplit(s.address).hostname == host for s in servers)
    ):
        return None
    port = f":{address.port}" if address.port else ""
    try:
        at = git_servers.address(f"{address.scheme}://{host}{port}")
    except git_servers.BadAddress:
        return None
    reason = f"{host} asks for a login" if kind == "login_needed" else f"{host} refused access"
    hint = runtime.Hint(
        "Add it as a git server with a token:", f"{git_servers.ADD} {at.root} --token"
    )
    page = f"Add {at.key} as a git server with a token: LADO and its agents then sign in to it."
    return reason, hint, ServerWay("add", at.key, at.root, page)


def failure(op: str, url: str, stderr: str, branch: str | None = None) -> CloneError:
    """git's failure of a listing (`op` "list") or a clone as LADO tells it: `cannot read
    <url>: <reason> (<git's line>)` or `cannot clone ...`, with a hint by its kind and, for
    an access failure a git server can fix, its way out. A clone into a project is told as
    any: a project's variable gives no login a git server should (lado.agent_env)."""
    verb = "read" if op == "list" else "clone"
    kind, text, hint, server = _told(url, stderr, branch)
    return CloneError(kind, f"cannot {verb} {runtime.public_remote(url)}: {text}", hint, server)


def explain(url: str, stderr: str) -> str:
    """git's failure of a network call for kits, skill packs or marketplaces
    (lado.gitcache), by the kinds of a clone's, on one line after LADO's head: `<reason>
    (<git's line>)` and `. <hint>` when the kind has one; git's line alone for no known
    kind."""
    _, text, hint, _ = _told(url, stderr, None)
    return text + (f". {hint.line()}" if hint else "")


SSH_KINDS = ("ssh_denied", "host_key")


def _container_ssh(address: Address) -> tuple[str, runtime.Hint | None, ServerWay | None]:
    """An ssh failure's reason, hint and way out in LADO's container, which has no ssh: an
    address a saved server would rewrite to https (`git@<host>`, port 22) of a host no
    server has, to add; any other ssh address, to clone over https. Servers not known (a
    lado.db at another schema) are taken as the host's."""
    no_ssh = "LADO's container has no ssh: clone by the repository's https address", None, None
    host = address.host
    servers = _saved_servers()
    if (
        address.user != "git"
        or address.port not in (None, 22)
        or servers is None
        or any(urllib.parse.urlsplit(s.address).hostname == host for s in servers)
    ):
        return no_ssh
    try:
        at = git_servers.address(f"https://{host}")
    except git_servers.BadAddress:
        return no_ssh
    hint = runtime.Hint(
        "Add it as a git server with a token:", f"{git_servers.ADD} {at.root} --token"
    )
    page = f"Add {at.key} as a git server with a token: its git@ addresses then go over https too."
    return (
        f"LADO's container has no ssh key for {host}",
        hint,
        ServerWay("add", at.key, at.root, page),
    )


def _told(
    url: str, stderr: str, branch: str | None
) -> tuple[str, str, runtime.Hint | None, ServerWay | None]:
    """git's failure by its kind: the kind, `<reason> (<git's line>)` (git's line alone
    for no known kind), the hint and the git server's way out."""
    line, kind = _gits_line(stderr), kind_of(stderr)
    if kind == GIT_FAILED:
        return kind, line, None, None
    address = Address.parse(url)
    if kind in SSH_KINDS and address.scheme == "ssh" and update.in_container():
        reason, hint, server = _container_ssh(address)
        return kind, f"{reason} ({line})", hint, server
    servers = _saved_servers() if kind in ACCESS_KINDS else None
    if servers is not None and (way := _server_way(kind, url, address, servers)):
        reason, hint, server = way
        return kind, f"{reason} ({line})", hint, server
    reason, found = _reason(kind, address, branch)
    return kind, f"{reason} ({line})", found, None


def _environment(project: str | None, url: str) -> dict[str, str]:
    """The environment of a clone's or listing's git of `url`: LADO's own git's
    (lado.agent_env.for_git, the saved git servers with it), into `project` with its layer,
    and no prompt over it. CloneError `git_too_old` for a saved server's URL and a git
    older than 2.31."""
    layer = project_secrets.layer(project) if project else None
    try:
        return {**agent_env.for_git(layer, remote=url), **gitcache.NO_PROMPT}
    except git_servers.Refused as exc:
        raise CloneError("git_too_old", str(exc)) from None


def _start_git(
    *args: str, env: dict[str, str], stdout: int | None = subprocess.DEVNULL
) -> subprocess.Popen:
    """A git process with no terminal and no prompt (`_environment`), in a process group of
    its own (Ctrl-C reaches LADO, which then ends the group: `_stop`)."""
    _git_runs()
    try:
        return subprocess.Popen(
            ["git", *args],
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
    except OSError:
        _git_runs()  # gone since: its text
        raise


def _stop(process: subprocess.Popen) -> None:
    """End git's whole process group (ssh and helpers too): SIGTERM, SIGKILL after
    STOP_WAIT seconds for what is left."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except OSError:  # the group is gone
            pass
        if sig == signal.SIGTERM:
            try:
                process.wait(STOP_WAIT)
            except subprocess.TimeoutExpired:
                pass
    process.wait()


@dataclass(frozen=True)
class Remote:
    """A remote's branches, its default one first; `default` None when it does not say."""

    branches: list[str]
    default: str | None


def list_branches(url: str, project: str | None = None) -> Remote:
    """The remote's branches and its default one, by one `git ls-remote` (for a clone into
    `project` when given: in its layer), within LIST_TIMEOUT seconds; a CloneError else."""
    process = _start_git(
        "ls-remote",
        "--symref",
        "--",
        url,
        "HEAD",
        "refs/heads/*",
        env=_environment(project, url),
        stdout=subprocess.PIPE,
    )
    try:
        out, err = process.communicate(timeout=LIST_TIMEOUT)
    except subprocess.TimeoutExpired:
        _stop(process)
        process.communicate()
        host = Address.parse(url).host or runtime.public_remote(url)
        raise CloneError(
            "unreachable",
            f"cannot read {runtime.public_remote(url)}: {host} did not answer within "
            f"{LIST_TIMEOUT:g} s",
        ) from None
    except BaseException:
        _stop(process)
        raise
    stderr = err.decode(errors="replace")
    if process.returncode != 0:
        raise failure("list", url, stderr)
    default, branches = None, []
    for line in out.decode(errors="replace").splitlines():
        value, _, ref = line.partition("\t")
        if ref == "HEAD" and value.startswith("ref: refs/heads/"):
            default = value[len("ref: refs/heads/") :]
        elif ref.startswith("refs/heads/"):
            branches.append(ref[len("refs/heads/") :])
    if not branches:
        raise CloneError(
            "no_branches",
            f"cannot read {runtime.public_remote(url)}: the repository has no branches yet",
        )
    branches.sort()
    if default in branches:
        branches.remove(default)
        branches.insert(0, default)
    else:
        default = None
    return Remote(branches, default)


# A line of git's progress: `Receiving objects:  45% (450/1000), 12.30 MiB | 2.10 MiB/s`.
_PROGRESS = re.compile(r"(?:remote: )?([A-Z][A-Za-z ]*?):\s+(\d+)%\s*(?:\(\d+/\d+\),?\s*)?(.*)")
POLL = 0.2  # seconds between two looks at whether a clone was cancelled
KEPT_LINES = 50  # git's last lines that are no progress, read for a failure's kind


@dataclass(frozen=True)
class Progress:
    """Where a clone is: git's phase, its percent and the rest of its line."""

    phase: str
    percent: int
    detail: str
    line: str


def parse_progress(line: str) -> Progress | None:
    found = _PROGRESS.fullmatch(line.strip())
    if not found:
        return None
    return Progress(found.group(1), int(found.group(2)), found.group(3).strip(), line)


def clone(
    url: str,
    path: str,
    branch: str | None = None,
    on_progress: Callable[[Progress], None] | None = None,
    cancelled: threading.Event | None = None,
    project: str | None = None,
) -> str:
    """Clone `branch` of `url` (the remote's default without one) into the folder `path`
    (a full path; `check_target` must let it, for `project` when one is given, whose layer
    the git then runs in): into a
    temporary folder beside it, renamed to `path` only once git succeeded. A cancel
    (`cancelled` set), a failure or an exception (Ctrl-C too) ends git's process group and
    removes the temporary folder; `path` stays as it was. Returns `path`."""
    target = check_target(url, path, project)
    if target.state not in CAN_CLONE:
        raise CloneError(target.state, target.text, target.hint)
    folder = Path(path)
    try:
        folder.parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.mkdtemp(prefix=f".{folder.name}.clone-", dir=folder.parent)
    except OSError as exc:
        raise CloneError(
            "no_access", f"cannot make a folder in {folder.parent}: {exc.strerror or exc}"
        ) from None
    try:
        _run_clone(url, temp, branch, on_progress, cancelled, project)
        try:
            os.rename(temp, path)  # onto a missing or an empty folder
        except OSError as exc:
            now = check_target(url, path, project)
            if now.state not in CAN_CLONE:
                raise CloneError(now.state, now.text) from None
            raise CloneError(
                GIT_FAILED, f"cannot clone {runtime.public_remote(url)} into {path}: {exc}"
            ) from None
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return path


def _run_clone(
    url: str,
    temp: str,
    branch: str | None,
    on_progress: Callable[[Progress], None] | None,
    cancelled: threading.Event | None,
    project: str | None,
) -> None:
    chosen = ["--branch", branch] if branch else []
    process = _start_git(
        "clone",
        "--progress",
        "--no-recurse-submodules",
        *chosen,
        "--",
        url,
        temp,
        env=_environment(project, url),
    )
    assert process.stderr is not None
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    pending, kept = "", []
    try:
        while True:
            if cancelled is not None and cancelled.is_set():
                raise CloneError(
                    "cancelled", f"the clone of {runtime.public_remote(url)} was cancelled"
                )
            ready, _, _ = select.select([process.stderr], [], [], POLL)
            if not ready:
                continue
            chunk = os.read(process.stderr.fileno(), 65536)
            if not chunk:
                break
            *lines, pending = re.split(r"[\r\n]", pending + decoder.decode(chunk))
            for line in lines:
                progress = parse_progress(line)
                if progress is None:
                    if line.strip():
                        kept = [*kept[-KEPT_LINES + 1 :], line]
                elif on_progress is not None:
                    on_progress(progress)
        process.wait()
    except BaseException:
        _stop(process)
        raise
    finally:
        process.stderr.close()
    if pending.strip():
        kept.append(pending)
    if process.returncode != 0:
        raise failure("clone", url, "\n".join(kept), branch)
