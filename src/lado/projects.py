"""The workspace and the projects in it (openspec capabilities `repos-folder` and
`projects`; the model: docs/design/projects.md).

The workspace is the folder LADO keeps code in: `LADO_REPOS` when it is a full path after
`~`, else `~/workspace`. One function answers it for every caller (the clone's and a
fresh start's default folder, the UI server, the container's warning, `lado doctor`,
projects); nothing makes it before the first clone, fresh start or project needs it."""

import os
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
