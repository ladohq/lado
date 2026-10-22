"""A session from scratch (openspec change start-from-scratch): from a name the human types
in any script, the folder's and the session's name and the session's title; whether a
folder may take a fresh start; whether git knows whom to sign commits with; and the
repository itself, a new or empty folder with one empty commit. `lado start --new`, the UI
server and `lado doctor` all call it, and print only what it says.

None of the human's files ever goes into a commit: only a folder with nothing in it (but
Finder's `.DS_Store`) is made a repository."""

import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from shlex import quote
from typing import Literal

from lado import projects, runtime
from lado import text as visible


class ScratchError(runtime.LadoError):
    """Why a fresh start cannot go on, by kind, with a hint when the human can act (LAD-5's
    `runtime.Hint`)."""

    def __init__(self, kind: str, text: str, hint: runtime.Hint | None = None) -> None:
        super().__init__(text)
        self.kind = kind
        self.hint = hint


# Russian, Ukrainian and Belarusian letters, lowercase (a capital is lowered first).
CYRILLIC = {
    **dict(zip("абвгґдеёзийіїклмнопрстуфыэ", "abvggdeeziiiiklmnoprstufye", strict=True)),
    **{"є": "ie", "ж": "zh", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch"},
    **{"ъ": "", "ь": "", "ю": "iu", "я": "ia"},
}
NO_LATIN = "the name needs a Latin letter or digit for its folder: type one"


@dataclass(frozen=True)
class Names:
    """What a typed name gives: the folder's and the session's name, and the session's
    title (None when it is the name itself, as `runtime.set_title` stores it)."""

    name: str
    title: str | None


def names(text: str) -> Names:
    """The names of a fresh start from the text the human typed, or a ScratchError: empty,
    over `runtime.MAX_TITLE` characters, a hidden character, or nothing left for a folder's
    name once Cyrillic is transliterated and Latin letters lose their accents."""
    title = text.strip()
    if not title:
        raise ScratchError("no_name", "type a name")
    if len(title) > runtime.MAX_TITLE:
        raise ScratchError("too_long", f"a name is at most {runtime.MAX_TITLE} characters")
    if (char := visible.first_hidden(title)) is not None:
        raise ScratchError("hidden", f"a name is one line {visible.refusal(char)}")
    latin = "".join(CYRILLIC.get(char, char) for char in title.lower())
    latin = "".join(
        char for char in unicodedata.normalize("NFKD", latin) if not unicodedata.combining(char)
    )
    # runtime.slug would make "lado" of a text with nothing it keeps: no name of the human's.
    if not re.search(r"[a-z0-9]", latin):
        raise ScratchError("no_latin", NO_LATIN)
    name = runtime.slug(latin)
    return Names(name, title if title != name else None)


TargetState = Literal["new", "empty", "inside_repo", "not_empty", "not_folder", "in_project"]
CAN_START = ("new", "empty")  # the target states a fresh start may go on in
FINDER = ".DS_Store"  # what Finder leaves in a folder it shows: no file of the human's


@dataclass(frozen=True)
class Target:
    """A folder a fresh start would make a repository of, as LADO found it; it changes
    nothing there."""

    path: str
    state: TargetState
    text: str
    root: str | None = None  # the repository it is inside, for inside_repo
    hint: runtime.Hint | None = None  # what to do instead, for in_project


def default_folder(name: str) -> Path:
    """The folder of a fresh start when the human gives none: the workspace
    (`projects.workspace`), then the name."""
    return projects.workspace() / name


def check_target(path: str, project: str | None = None) -> Target:
    """Whether a fresh start may make the folder `path` (a full path) a repository, and
    what is there when not. Only `CAN_START` states let it go on; a folder LADO may not look
    at is a ScratchError `no_access`. With `project`, a folder directly in that project's
    folder is no `in_project` (`projects.adds_to`): it becomes a repository of it."""
    try:
        return _check_target(path, project)
    except OSError as exc:
        raise ScratchError("no_access", f"cannot look at {path}: {exc.strerror or exc}") from None


def _check_target(path: str, project: str | None) -> Target:
    # A new session without a project could not start there.
    if not projects.adds_to(project, path) and (refused := projects.refusal(path)):
        return Target(path, "in_project", str(refused), hint=refused.hint)
    folder = Path(path)
    nearest = _nearest(folder)
    if not nearest.is_dir():
        return Target(path, "not_folder", f"{nearest} is a file, not a folder")
    # Read first: git's own refusal of a folder it may not enter is no reason for the human.
    entries = [entry.name for entry in folder.iterdir()] if nearest == folder else None
    root = _repository_of(str(nearest))
    if root is not None:
        text = f"{path} is inside the git repository {root}: choose a folder outside it"
        return Target(path, "inside_repo", text, root)
    if entries is None:
        return Target(path, "new", "a new folder")
    if any(entry != FINDER for entry in entries):
        return Target(path, "not_empty", f"{path} is not empty: choose a new or empty folder")
    return Target(path, "empty", "an empty folder")


NO_AUTHOR = "git doesn't know who signs the agents' commits: it has no user.name or user.email"
AUTHOR_HINT_CONTAINER = runtime.Hint(
    "Set LADO_GIT_NAME and LADO_GIT_EMAIL in the .env file next to compose.yaml, then "
    "restart LADO there:",
    "docker compose up -d",
)
AUTHOR_HINT = runtime.Hint(
    "Tell git who you are, once for this computer:",
    'git config --global user.name "Your Name" && git config --global user.email you@example.com',
)


def author_problem(path: str) -> ScratchError | None:
    """Why git cannot sign the commits of a repository at `path`: no `user.name` or
    `user.email` where its nearest existing folder is, which outside any repository is
    git's global and system config, the ones the agents' git reads. None when both are
    set. A git that does not run raises LAD-5's FolderProblem; LADO never sets an author of
    its own."""
    folder = str(_nearest(Path(path)))
    for key in ("user.name", "user.email"):
        result = runtime._run_git(folder, "config", "--get", key, env=_english())
        if result.returncode not in (0, 1):  # 1: not set
            raise ScratchError("git_refused", f"git cannot read its config: {_line(result)}")
        if not result.stdout.strip():
            # Imported here: the CLI, which imports this module, imports update lazily.
            from lado import update

            hint = AUTHOR_HINT_CONTAINER if update.in_container() else AUTHOR_HINT
            return ScratchError("no_author", NO_AUTHOR, hint)
    return None


def _refusal(target: Target) -> ScratchError:
    """A target a fresh start may not go on in, as a refusal with what the human can do:
    a folder of files is made a repository by the human (LAD-5's hint), a folder of a
    repository starts in that repository."""
    hint = target.hint
    if target.state == "not_empty":
        hint = runtime.NOT_REPO_HINT
    elif target.state == "inside_repo":
        hint = runtime.Hint(
            "Start a session in that repository:", f"lado start {quote(target.root)}"
        )
    return ScratchError(target.state, target.text, hint)


FIRST_COMMIT = "Start from scratch"


def make(path: str, name: str, project: str | None = None) -> str:
    """Make the folder `path` (a full path) a git repository with one empty commit, for the
    session `name`; its root. The checks first, again (the name as `runtime.check_name`, the
    target, the author), then the folder and the folders above it when it is new, `git
    init`, the branch of git's `init.defaultBranch` (else `main`) and the commit: no file,
    no signing, no hooks, no prompt. A failed step removes what this call made (the
    folders it created, or the `.git` of an empty folder it was given): a ScratchError
    `git_failed` with git's line. With `project` it adds a repository to that project
    (`check_target`'s `project`), and no session's name is asked: none is made."""
    if project is None:
        runtime.check_name(name, path)
    target = check_target(path, project)
    if target.state not in CAN_START:
        raise _refusal(target)
    if (problem := author_problem(path)) is not None:
        raise problem
    folder = Path(path)
    made = None if folder.exists() else _topmost_missing(folder)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _git(path, "init", "--quiet")
        found = _git(path, "config", "--get", "init.defaultBranch", missing_ok=True)
        _git(path, "symbolic-ref", "HEAD", f"refs/heads/{found or 'main'}")
        _git(
            path,
            *("-c", "commit.gpgsign=false", "-c", f"core.hooksPath={os.devnull}"),
            *("commit", "--allow-empty", "--no-verify", "--quiet", "-m", FIRST_COMMIT),
        )
        return _git(path, "rev-parse", "--show-toplevel")
    except (OSError, _GitFailed) as error:
        shutil.rmtree(made or folder / ".git", ignore_errors=True)
        line = (isinstance(error, OSError) and error.strerror) or str(error)
        raise ScratchError(
            "git_failed", f"git could not make {path} a repository: {line}"
        ) from None


class _GitFailed(Exception):
    """A git command of `make` that failed, with git's first line."""


def _git(path: str, *args: str, missing_ok: bool = False) -> str:
    """git in `path` with no terminal, no prompt and git's words in English; its output.
    `missing_ok`: exit 1 (a config key not set) is an empty output."""
    result = subprocess.run(
        ["git", "-C", path, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        env={**_english(), "GIT_TERMINAL_PROMPT": "0"},
    )
    if missing_ok and result.returncode == 1:
        return ""
    if result.returncode != 0:
        raise _GitFailed(_line(result))
    return result.stdout.strip()


def _topmost_missing(folder: Path) -> Path:
    """The highest of `folder` and its ancestors that does not exist (`folder` does not)."""
    while not folder.parent.exists():
        folder = folder.parent
    return folder


def _nearest(folder: Path) -> Path:
    """`folder` when it exists, else its nearest ancestor that does."""
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    return folder


def _repository_of(folder: str) -> str | None:
    """The root of the git repository `folder` is in; None outside any."""
    # git's own words decide "not a repository", so they must not be translated.
    result = runtime._run_git(folder, "rev-parse", "--show-toplevel", env=_english())
    if result.returncode == 0:
        return result.stdout.strip()
    if "not a git repository" in result.stderr:
        return None
    raise ScratchError("git_refused", f"git cannot read {folder}: {_line(result)}")


def _english() -> dict[str, str]:
    return {**os.environ, "LC_ALL": "C"}


def _line(result: subprocess.CompletedProcess) -> str:
    """git's first line of a failure."""
    return runtime._first_line(result.stderr) or f"git exited {result.returncode}"
