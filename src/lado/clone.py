"""A repository from its git URL: what a URL is, the folder a clone goes to by default,
whether a folder may take a clone, the remote's branches, and the clone itself, with
progress and cancellation (openspec change clone-from-url). `lado start <git-url>` and the
UI server's clone jobs (`server/clones.py`) both call it, and print only what it says.

LADO uses only the access git already has on this machine (ssh keys, `gh auth`, a
credential helper): its git calls run with no terminal and no prompt, so a missing
credential is a failure, never a wait. A URL reaches a text only through
`runtime.public_remote`."""

import codecs
import os
import re
import select
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lado import runtime

URL = re.compile(r"(https?|ssh|git|file)://(.+)", re.IGNORECASE)
# user@host:path, git's scp form; a bare host:path would take a folder with a colon.
SCP = re.compile(r"([^\s@/:]+)@([^\s@/:]+):(.+)")
DEFAULT_PARENT = "~/lado"  # a clone's folder is <parent>/<repo> unless given: default_parent
REPOS = "LADO_REPOS"  # the folder of the human's repositories (LADO's image sets it)


LIST_TIMEOUT = 20  # seconds a listing of the remote's branches may take
# Each git process of a clone or listing: no prompt, git's words in English (KINDS). An empty
# GIT_ASKPASS stops git before core.askPass and SSH_ASKPASS: no askpass program either.
NO_PROMPT = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS_REQUIRE": "never",
    "GCM_INTERACTIVE": "never",
    "LC_ALL": "C",
}
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


def repos_folder() -> Path | None:
    """The folder of the human's repositories, `LADO_REPOS` with `~` expanded; None when it
    is unset, empty or not a full path (`lado doctor` says why it is ignored)."""
    value = os.environ.get(REPOS, "")
    folder = Path(os.path.expanduser(value)) if value else None
    return folder if folder is not None and folder.is_absolute() else None


def default_parent() -> Path:
    """Where a clone goes when the human gives no folder: the repositories folder, else
    ~/lado."""
    return repos_folder() or Path(os.path.expanduser(DEFAULT_PARENT))


def default_folder(url: str) -> Path:
    """The folder a clone of `url` goes to when the human gives none: <parent>/<repo>
    (`default_parent`); a URL that names no repository has none (it would be the parent
    itself)."""
    name = Address.parse(url).repo_name
    if not name:
        raise CloneError(
            "no_repo_name",
            f"{runtime.public_remote(url)} names no repository: give the folder to clone into",
        )
    return default_parent() / name


class CloneError(runtime.LadoError):
    """Why a listing or a clone did not happen, by kind, with a hint when the human can
    act (LAD-5's `runtime.Hint`)."""

    def __init__(self, kind: str, text: str, hint: runtime.Hint | None = None) -> None:
        super().__init__(text)
        self.kind = kind
        self.hint = hint


def _git_runs() -> None:
    """LAD-5's look at whether git runs, its `no_git` / `git_broken` as a CloneError."""
    try:
        runtime.git_version()
    except runtime.FolderProblem as problem:
        raise CloneError(problem.kind, str(problem), problem.hint) from None


TargetState = Literal["new", "empty", "same_repo", "other_repo", "not_empty", "not_folder"]
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


def check_target(url: str, path: str) -> Target:
    """Whether a clone of `url` may go to the folder `path` (a full path), and what is
    there when not. Only `CAN_CLONE` states let a clone start; a folder LADO may not look
    at is a CloneError `no_access`."""
    try:
        return _check_target(url, path)
    except OSError as exc:
        raise CloneError("no_access", f"cannot look at {path}: {exc.strerror or exc}") from None


def _check_target(url: str, path: str) -> Target:
    folder = Path(path)
    if not folder.exists():
        return Target(path, "new", "a new folder")
    if not folder.is_dir():
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
GITHUB = "github.com"
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
    host, github = address.host, address.host == GITHUB
    if kind == "ssh_denied":
        hint = f"Check that this machine's ssh key is added to your account on {host}:"
        return f"{host} refused this machine's ssh key", runtime.Hint(hint, _ssh_check(address))
    if kind == "host_key":
        hint = runtime.Hint(
            "Connect once in a terminal and accept the host key:", _ssh_check(address)
        )
        return f"this machine does not know {host}'s ssh host key yet", hint
    if kind == "login_needed":
        if github:
            hint = runtime.Hint("Log in with GitHub's CLI on this machine:", "gh auth login")
            return f"{host} asks for a login", hint
        return (
            f"{host} asks for a login; set up a git credential helper for it on this machine",
            None,
        )
    if kind == "not_found":
        hint = (
            runtime.Hint("See which GitHub account this machine uses:", "gh auth status")
            if github
            else None
        )
        return "no repository there, or this machine's account cannot read it", hint
    if kind == "unreachable":
        return f"{host} cannot be reached", None
    return f"no branch {branch}", None  # no_branch


def failure(op: str, url: str, stderr: str, branch: str | None = None) -> CloneError:
    """git's failure of a listing (`op` "list") or a clone as LADO tells it: `cannot read
    <url>: <reason> (<git's line>)` or `cannot clone ...`, with a hint by its kind."""
    verb = "read" if op == "list" else "clone"
    line, kind = _gits_line(stderr), kind_of(stderr)
    head = f"cannot {verb} {runtime.public_remote(url)}"
    if kind == GIT_FAILED:
        return CloneError(kind, f"{head}: {line}")
    reason, hint = _reason(kind, Address.parse(url), branch)
    return CloneError(kind, f"{head}: {reason} ({line})", hint)


def _start_git(*args: str, stdout: int | None = subprocess.DEVNULL) -> subprocess.Popen:
    """A git process with no terminal and no prompt, in a process group of its own (Ctrl-C
    reaches LADO, which then ends the group: `_stop`)."""
    _git_runs()
    try:
        return subprocess.Popen(
            ["git", *args],
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.PIPE,
            env={**os.environ, **NO_PROMPT},
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


def list_branches(url: str) -> Remote:
    """The remote's branches and its default one, by one `git ls-remote`, within
    LIST_TIMEOUT seconds; a CloneError else."""
    process = _start_git(
        "ls-remote", "--symref", "--", url, "HEAD", "refs/heads/*", stdout=subprocess.PIPE
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
) -> str:
    """Clone `branch` of `url` (the remote's default without one) into the folder `path`
    (a full path; `check_target` must let it): into a temporary folder beside it, renamed
    to `path` only once git succeeded. A cancel (`cancelled` set), a failure or an
    exception (Ctrl-C too) ends git's process group and removes the temporary folder;
    `path` stays as it was. Returns `path`."""
    target = check_target(url, path)
    if target.state not in CAN_CLONE:
        raise CloneError(target.state, target.text)
    folder = Path(path)
    try:
        folder.parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.mkdtemp(prefix=f".{folder.name}.clone-", dir=folder.parent)
    except OSError as exc:
        raise CloneError(
            "no_access", f"cannot make a folder in {folder.parent}: {exc.strerror or exc}"
        ) from None
    try:
        _run_clone(url, temp, branch, on_progress, cancelled)
        try:
            os.rename(temp, path)  # onto a missing or an empty folder
        except OSError as exc:
            now = check_target(url, path)
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
) -> None:
    chosen = ["--branch", branch] if branch else []
    process = _start_git("clone", "--progress", "--no-recurse-submodules", *chosen, "--", url, temp)
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
