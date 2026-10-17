"""A session from scratch (openspec change start-from-scratch): from a name the human types
in any script, the folder's and the session's name and the session's title; whether a
folder may take a fresh start; whether git knows whom to sign commits with; and the
repository itself, a new or empty folder with one empty commit. `lado start --new`, the UI
server and `lado doctor` all call it, and print only what it says.

None of the human's files ever goes into a commit: only a folder with nothing in it (but
Finder's `.DS_Store`) is made a repository."""

import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lado import clone, runtime
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


TargetState = Literal["new", "empty", "inside_repo", "not_empty", "not_folder"]
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


def default_folder(name: str) -> Path:
    """The folder of a fresh start when the human gives none: where a clone goes
    (`clone.default_parent`), then the name."""
    return clone.default_parent() / name


def check_target(path: str) -> Target:
    """Whether a fresh start may make the folder `path` (a full path) a repository, and
    what is there when not. Only `CAN_START` states let it go on; a folder LADO may not look
    at is a ScratchError `no_access`."""
    try:
        return _check_target(path)
    except OSError as exc:
        raise ScratchError("no_access", f"cannot look at {path}: {exc.strerror or exc}") from None


def _check_target(path: str) -> Target:
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
    lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    return lines[0] if lines else f"git exited {result.returncode}"
