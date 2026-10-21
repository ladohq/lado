"""The workspace and the projects in it (openspec capabilities `repos-folder` and
`projects`; the model: docs/design/projects.md).

The workspace is the folder LADO keeps code in: `LADO_REPOS` when it is a full path after
`~`, else `~/workspace`. One function answers it for every caller (the clone's and a
fresh start's default folder, the UI server, the container's warning, `lado doctor`,
projects); nothing makes it before the first clone, fresh start or project needs it."""

import os
import stat
import tempfile
from pathlib import Path
from typing import Literal

WORKSPACE_VAR = "LADO_REPOS"  # the workspace's name in an installation (LADO's image sets it)
DEFAULT_WORKSPACE = "~/workspace"


def _given() -> Path:
    return Path(os.path.expanduser(os.environ.get(WORKSPACE_VAR, "")))  # unset: "."


def workspace() -> Path:
    """The folder LADO keeps code in: LADO_REPOS when it is a full path after ~, else
    ~/workspace. Never None and never made here."""
    given = _given()
    return given if given.is_absolute() else Path(os.path.expanduser(DEFAULT_WORKSPACE))


def workspace_source() -> Literal["LADO_REPOS", "default", "ignored"]:
    """Where `workspace` comes from: LADO_REPOS, the default, or the default because
    LADO_REPOS is set but not a full path (`lado doctor` warns)."""
    if not os.environ.get(WORKSPACE_VAR):
        return "default"
    return "LADO_REPOS" if _given().is_absolute() else "ignored"


def workspace_label() -> str:
    """The workspace's name in a text: LADO_REPOS when it comes from there."""
    return WORKSPACE_VAR if workspace_source() == "LADO_REPOS" else "the workspace"


WRITE_HINT = (
    "give your user write access to it; in LADO's image on Linux, the folder's owner gives "
    "the container's user its uid"
)


def workspace_problem(folder: Path, name: str) -> tuple[str, str] | None:
    """Why LADO cannot use the existing path `folder` as the workspace (`name` in the
    text), with a hint or ""; None when it is a folder LADO may write in. A missing path
    raises FileNotFoundError: the caller says what that means (`lado doctor`, create)."""
    # stat, not exists(): for a folder above it LADO may not look in, exists() raises on some
    # Pythons and says "missing" on others; stat says why on all.
    try:
        info = folder.stat()
    except FileNotFoundError:
        raise
    except OSError as error:
        return f"cannot look at {name} {folder}: {error.strerror or error}", ""
    if not stat.S_ISDIR(info.st_mode):
        return f"{name} is not a folder: {folder}", ""
    # A file made and removed, not os.access: a bind mount of Docker Desktop shows its root
    # as 0:0 to any user while it lets that user write.
    try:
        handle, probe = tempfile.mkstemp(prefix=".lado-doctor-", dir=folder)
    except OSError as error:
        return f"LADO may not write in {name} {folder}: {error.strerror or error}", WRITE_HINT
    try:
        os.close(handle)
    finally:
        os.unlink(probe)
    return None
