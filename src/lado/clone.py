"""A repository from its git URL: what a URL is, the folder a clone goes to by default,
whether a folder may take a clone, the remote's branches, and the clone itself, with
progress and cancellation (openspec change clone-from-url). `lado start <git-url>` and the
UI server's clone jobs (`server/clones.py`) both call it, and print only what it says.

LADO uses only the access git already has on this machine (ssh keys, `gh auth`, a
credential helper): its git calls run with no terminal and no prompt, so a missing
credential is a failure, never a wait. A URL reaches a text only through
`runtime.public_remote`."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lado import runtime

URL = re.compile(r"(https?|ssh|git|file)://(.+)", re.IGNORECASE)
# user@host:path, git's scp form; a bare host:path would take a folder with a colon.
SCP = re.compile(r"([^\s@/:]+)@([^\s@/:]+):(.+)")
DEFAULT_PARENT = "~/lado"  # a clone's folder is DEFAULT_PARENT/<repo> unless given


def is_url(source: str) -> bool:
    """Whether `source` is a git URL to clone; anything else is a folder."""
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
        segments = self._segments()
        return segments[-1] if segments else ""

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
    """The folder a clone of `url` goes to when the human gives none: ~/lado/<repo>."""
    return Path(os.path.expanduser(DEFAULT_PARENT)) / Address.parse(url).repo_name


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
    there when not. Only `CAN_CLONE` states let a clone start."""
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
