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
            return (
                self.scheme == other.scheme == "file"
                and os.path.realpath(os.path.expanduser(self.path.rstrip("/")))
                == os.path.realpath(os.path.expanduser(other.path.rstrip("/")))
            )
        return self.host == other.host and self._segments() == other._segments()


def default_folder(url: str) -> Path:
    """The folder a clone of `url` goes to when the human gives none: ~/lado/<repo>."""
    return Path(os.path.expanduser(DEFAULT_PARENT)) / Address.parse(url).repo_name
