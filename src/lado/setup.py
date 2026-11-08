"""A plain folder of files set up for a session (openspec change new-session-window,
capability folder-setup): what its first commit would take and leave out, told before
anything changes, and the repository itself, one commit of the folder's files with what
was left out written to its `.gitignore`. The UI server calls it for the New session
window's "Set up and start"; a human at a terminal runs the command it gives.

git itself lists the files (`ls-files --others` against a temporary git folder), so the
preview and the commit cannot disagree on what a `.gitignore` already leaves out."""

import fnmatch
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from shlex import quote
from typing import Literal

from lado import projects, runtime, scratch

MAX_FILES = 20_000  # past this many files the folder is refused as too big
MAX_BYTES = 2 * 1024**3  # past this many bytes saved, too
MAX_FILE = 50 * 1024**2  # a file over this is left out as large
# A file of one of these names is left out as a secret, in any subfolder.
SECRETS = (
    ".env*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "credentials*",
    ".npmrc",
    ".netrc",
)
FIRST_COMMIT = "First commit"

Reason = Literal["secret", "large", "repository"]


class SetupError(runtime.LadoError):
    """Why a folder was not set up, by kind; the folder is as it was."""

    def __init__(self, kind: str, text: str) -> None:
        super().__init__(text)
        self.kind = kind


@dataclass(frozen=True)
class LeftOut:
    """A path the first commit leaves out: a file (`size` in bytes) or, for a
    `repository`, a folder with its own `.git`, ending in `/` (`size` None)."""

    path: str
    reason: Reason
    size: int | None


@dataclass(frozen=True)
class Refusal:
    """Why the folder may not be set up: the home folder or one holding the workspace
    (`home`), past the limits (`too_big`, with what was counted until then), or a folder
    git cannot read all of (`unreadable`, with git's line)."""

    kind: Literal["home", "too_big", "unreadable"]
    files: int
    bytes: int
    line: str = ""


@dataclass(frozen=True)
class Preview:
    """What the first commit of a folder would take (`files`, `bytes`) and leave out, or
    its refusal; `command` does the same by hand, leaving out all that is left out."""

    files: int
    bytes: int
    left_out: list[LeftOut] = field(default_factory=list)
    refusal: Refusal | None = None
    command: str = ""


def ignore_line(path: str) -> str:
    """The `.gitignore` line of a left-out path: anchored at the folder (a leading `/`),
    git's pattern characters taken as they are."""
    escaped = re.sub(r"([\\*?\[])", r"\\\1", path)
    if escaped.endswith(" "):
        escaped = escaped[:-1] + "\\ "
    return f"/{escaped}"


def command(left_out: list[LeftOut]) -> str:
    """The commands that set the folder up by hand, leaving out `left_out`."""
    make = runtime.NOT_REPO_HINT.command
    if not left_out:
        return make
    lines = " ".join(quote(ignore_line(item.path)) for item in left_out)
    return f"printf '%s\\n' {lines} >> .gitignore && {make}"


def _is_home(path: str) -> bool:
    """The home folder, `/`, the workspace, or a folder holding the workspace."""
    real = Path(os.path.realpath(path))
    workspace = Path(os.path.realpath(projects.workspace()))
    home = Path(os.path.realpath(Path.home()))
    return real in (home, Path("/")) or real == workspace or real in workspace.parents


def preview(path: str) -> Preview:
    """What setting the folder `path` (a full path, outside git) up would commit and leave
    out; it changes nothing on disk. Refused first by the path alone (`home`), then while
    counting, past MAX_FILES files or MAX_BYTES bytes (`too_big`)."""
    if _is_home(path):
        return Preview(0, 0, refusal=Refusal("home", 0, 0))
    files = size = 0
    left_out: list[LeftOut] = []
    listing = _listed(path)
    try:
        for name in listing:
            item = _left_out(path, name)
            if item is not None:
                left_out.append(item)
                continue
            files += 1
            size += os.lstat(os.path.join(path, name)).st_size
            if files > MAX_FILES or size > MAX_BYTES:
                return Preview(files, size, left_out, Refusal("too_big", files, size))
    except _Unreadable as unreadable:
        return Preview(files, size, left_out, Refusal("unreadable", files, size, str(unreadable)))
    finally:
        listing.close()
    return Preview(files, size, left_out, command=command(left_out))


def _left_out(path: str, name: str) -> LeftOut | None:
    if name.endswith("/"):
        return LeftOut(name, "repository", None)
    base = name.rsplit("/", 1)[-1]
    found = os.lstat(os.path.join(path, name)).st_size
    if any(fnmatch.fnmatchcase(base, pattern) for pattern in SECRETS):
        return LeftOut(name, "secret", found)
    if found > MAX_FILE:
        return LeftOut(name, "large", found)
    return None


class _Unreadable(Exception):
    """git could not read all of the folder; git's first line."""


def _listed(path: str) -> Iterator[str]:
    """What `git add -A` would take in `path`, as git lists it: a temporary git folder, the
    folder as the work tree, its `.gitignore` respected, a nested repository as one `dir/`.
    Read as a stream; closing the iterator stops git."""
    with tempfile.TemporaryDirectory() as gitdir, tempfile.TemporaryFile() as errors:
        scratch._git(path, "init", "--quiet", "--bare", gitdir)
        proc = subprocess.Popen(
            ["git", f"--git-dir={gitdir}", f"--work-tree={path}", "ls-files", "--others"]
            + ["--exclude-standard", "-z"],
            cwd=path,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=errors,
            env=scratch._english(),
        )
        try:
            rest = b""
            while chunk := proc.stdout.read(65536):
                *names, rest = (rest + chunk).split(b"\0")
                for name in names:
                    yield os.fsdecode(name)
            proc.wait()
            errors.seek(0)
            line = runtime._first_line(errors.read().decode(errors="replace"))
            if proc.returncode != 0 or line:
                raise _Unreadable(line or f"git exited {proc.returncode}")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            proc.stdout.close()


def refusal_text(path: str, refusal: Refusal) -> str:
    """The core's line for a refusal, as `make` raises it."""
    if refusal.kind == "home":
        return f"{path} is your home folder or holds the workspace: choose a smaller folder"
    if refusal.kind == "unreadable":
        return f"git cannot read all of {path}: {refusal.line}"
    return (
        f"{path} is too big to set up, over {MAX_FILES:,} files or {MAX_BYTES:,} bytes: "
        "choose a smaller folder"
    )


def make(path: str, include: list[str]) -> str:
    """Set the folder `path` up: its root. The checks first, again (git's author, a folder
    outside git, the preview's refusal, `include` naming only files left out), then `git
    init`, the branch as a fresh start's, the left-out paths not in `include` appended to
    `.gitignore` (made when missing), `git add -A` and one commit with no signing and no
    hooks. A failed step removes the `.git` it made and puts `.gitignore` back as it was:
    a SetupError `git_failed` with git's line."""
    if (problem := scratch.author_problem(path)) is not None:
        raise SetupError(problem.kind, str(problem))
    if scratch._repository_of(path) is not None:
        raise SetupError("not_plain", f"{path} is already inside a git repository")
    found = preview(path)
    if found.refusal is not None:
        raise SetupError(found.refusal.kind, refusal_text(path, found.refusal))
    files = {item.path: item for item in found.left_out}
    for asked in include:
        if asked not in files or files[asked].reason == "repository":
            raise SetupError("bad_include", f"{asked} is not a file the set-up can take in")
    ignored = [item for item in found.left_out if item.path not in include]
    gitignore = Path(path) / ".gitignore"
    before = gitignore.read_bytes() if gitignore.exists() else None
    try:
        if ignored:
            lead = b"\n" if before and not before.endswith(b"\n") else b""
            lines = "".join(f"{ignore_line(item.path)}\n" for item in ignored)
            gitignore.write_bytes((before or b"") + lead + os.fsencode(lines))
        git = scratch._git
        git(path, "init", "--quiet")
        branch = git(path, "config", "--get", "init.defaultBranch", missing_ok=True)
        git(path, "symbolic-ref", "HEAD", f"refs/heads/{branch or 'main'}")
        git(path, "add", "-A")
        git(
            path,
            *("-c", "commit.gpgsign=false", "-c", f"core.hooksPath={os.devnull}"),
            *("commit", "--no-verify", "--quiet", "-m", FIRST_COMMIT),
        )
        return git(path, "rev-parse", "--show-toplevel")
    except (OSError, scratch._GitFailed) as error:
        shutil.rmtree(Path(path) / ".git", ignore_errors=True)
        if before is None:
            gitignore.unlink(missing_ok=True)
        else:
            gitignore.write_bytes(before)
        line = (isinstance(error, OSError) and error.strerror) or str(error)
        raise SetupError("git_failed", f"git could not set up {path}: {line}") from None
