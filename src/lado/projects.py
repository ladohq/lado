"""The workspace and the projects in it (openspec capabilities `repos-folder` and
`projects`; the model: docs/design/projects.md).

The workspace is the folder LADO keeps code in: `LADO_REPOS` when it is a full path after
`~`, else `~/workspace`. One function answers it for every caller (the clone's and a
fresh start's default folder, the UI server, the container's warning, `lado doctor`,
projects); nothing makes it before the first clone, fresh start or project needs it.

A project is an id that never changes, a title that can, and a record in lado.db; its
folder `<workspace>/projects/<id>` is derived from the id, stored nowhere, and made by
LADO. `projects/` belongs to LADO once a project's folder is in it; before that, a
`projects/` holding anything visible is the human's own folder, and LADO makes no project
there. The CLI (`lado project`) and `lado doctor` only print what this module says."""

import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from lado import runtime, state

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


ID = re.compile(r"[a-z0-9][a-z0-9-]*")  # lowercase: the folder never depends on the case
MAX_ID = 40
SHOWN = 3  # names a text lists, then "…"


class ProjectError(runtime.LadoError):
    pass


class NoSuchProject(ProjectError):
    pass


def check_id(id: str) -> None:
    if not (ID.fullmatch(id) and len(id) <= MAX_ID):
        raise ProjectError(
            f"the project id {id} is not valid: lowercase Latin letters, digits and -, "
            f"starting with a letter or digit, at most {MAX_ID} characters"
        )


def projects_folder() -> Path:
    return workspace() / "projects"


def folder(id: str) -> Path:
    """A project's folder, derived from its id in the workspace of now."""
    return projects_folder() / id


def names(entries: list[str]) -> str:
    """Names for a text: sorted, at most SHOWN, then "…"."""
    shown = sorted(entries)
    return ", ".join(shown[:SHOWN] + (["…"] if len(shown) > SHOWN else []))


def _visible() -> list[str] | None:
    """The entries of projects/ whose names do not start with "."; None when it is no
    folder (missing, a file, or one LADO may not list)."""
    try:
        return sorted(name for name in os.listdir(projects_folder()) if not name.startswith("."))
    except OSError:
        return None


def owned_by_human() -> list[str] | None:
    """The visible entries of projects/ when it is the human's own folder: it holds some and
    none is a project's folder. None otherwise."""
    visible = _visible()
    if not visible:
        return None
    ids = {project.id for project in state.list_projects()}
    return None if ids & set(visible) else visible


def foreign() -> list[str]:
    """The visible entries of projects/ that are no project's folder, files too, once a
    project's folder is there (before that, the folder is the human's: owned_by_human)."""
    visible = _visible() or []
    ids = {project.id for project in state.list_projects()}
    return [name for name in visible if name not in ids] if ids & set(visible) else []


def create(id: str, title: str | None) -> state.Project:
    """Make the project `id`: its record and its folder, with the workspace and projects/
    when they are missing. Refused, with nothing made, for a bad id or title, a workspace
    LADO cannot use, a taken id, an existing folder of the name (a dangling link too) and
    the human's own projects/."""
    check_id(id)
    stored = runtime.check_title(title, id)
    try:
        problem = workspace_problem(workspace(), workspace_label())
    except FileNotFoundError:
        problem = None  # the first project makes it
    if problem:
        raise ProjectError(problem[0])
    if state.get_project(id):
        raise ProjectError(f"project {id} exists")
    target = folder(id)
    if os.path.lexists(target):
        raise ProjectError(
            f"{target} already exists: LADO makes a project's folder itself; "
            "choose another id or move that folder away"
        )
    if (own := owned_by_human()) is not None:
        raise ProjectError(
            f"{projects_folder()} is your own folder (it holds {names(own)}): LADO keeps "
            "projects there only; move it away or set LADO_REPOS to another workspace"
        )
    try:
        # The record stays only with its folder; exist_ok=False loses a race of two creates.
        with state.creating_project(id, stored):
            target.mkdir(parents=True, exist_ok=False)
    except sqlite3.IntegrityError as error:
        raise ProjectError(f"project {id} exists") from error
    except OSError as error:
        raise ProjectError(f"could not make {target}: {error.strerror or error}") from error
    made = state.get_project(id)
    assert made is not None
    return made


def rename(id: str, text: str | None) -> str | None:
    """Set or clear the title (the session title's rule); the id and the folder stay.
    Returns what is stored."""
    stored = runtime.check_title(text, id)
    if not state.set_project_title(id, stored):
        raise NoSuchProject(f'unknown project "{id}"')
    return stored


def get(id: str) -> state.Project:
    project = state.get_project(id)
    if project is None:
        raise NoSuchProject(f'unknown project "{id}"')
    return project


def listed() -> list[tuple[state.Project, Path, bool]]:
    """Every project by id, with its folder and whether that folder is there."""
    return [(p, folder(p.id), folder(p.id).is_dir()) for p in state.list_projects()]


GIT_TIMEOUT = 20  # seconds one git command of the unpushed scan may take


def _git(checkout: Path, *args: str) -> str:
    """git's output in `checkout`, with no prompt and git's words in English; GitFailed
    with git's first line when it fails or takes too long."""
    from lado import clone  # lado.clone builds on this module

    try:
        done = subprocess.run(
            ["git", "-C", str(checkout), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            env={**os.environ, **clone.NO_PROMPT},
        )
    except subprocess.TimeoutExpired as error:
        raise _GitFailed(f"git took more than {GIT_TIMEOUT} s") from error
    except OSError as error:
        raise _GitFailed(error.strerror or str(error)) from error
    if done.returncode:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise _GitFailed(lines[0] if lines else f"git exited with {done.returncode}")
    return done.stdout


class _GitFailed(Exception):
    pass


def _not_pushed(repo: Path) -> list[str]:
    """The local branches of `repo` with no upstream, a gone one, or commits ahead of it
    (the last fetch's view: no network)."""
    found = []
    refs = _git(
        repo,
        "for-each-ref",
        "refs/heads",
        "--format=%(refname:short)%00%(upstream)%00%(upstream:track)",
    )
    for line in refs.splitlines():
        branch, upstream, track = line.split("\0")
        if not upstream or "ahead" in track or "gone" in track:
            found.append(f"branch {branch} not pushed")
    return found


def _checkouts(repo: Path) -> list[Path]:
    """The worktrees of `repo` but its own, wherever they are."""
    listing = _git(repo, "worktree", "list", "--porcelain")
    trees = [
        Path(line.removeprefix("worktree "))
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]
    return trees[1:]  # the first is the repository's own


def unpushed(project_folder: Path) -> list[str]:
    """What deleting `project_folder` would lose of the human's work, one line per checkout:
    each git repository directly in it and each worktree of one, with its uncommitted
    changes (untracked files too) and, for the repository, its branches not pushed."""
    lines = []
    real = Path(os.path.realpath(project_folder))  # git names worktrees by real paths
    for entry in sorted(project_folder.iterdir()):
        if not entry.is_dir() or not os.path.lexists(entry / ".git"):
            continue
        try:
            findings = []
            if _git(entry, "status", "--porcelain", "--untracked-files=normal").strip():
                findings.append("uncommitted changes")
            findings += _not_pushed(entry)
            trees = []
            for tree in _checkouts(entry):
                if (
                    tree.is_dir()
                    and _git(tree, "status", "--porcelain", "--untracked-files=normal").strip()
                ):
                    trees.append(tree)
        except _GitFailed as failed:
            lines.append(f"{entry.name}: could not check: {failed}")
            continue
        if findings:
            lines.append(f"{entry.name}: {'; '.join(findings)}")
        for tree in trees:
            shown = tree.relative_to(real) if tree.is_relative_to(real) else tree
            lines.append(f"{entry.name} (worktree {shown}): uncommitted changes")
    return lines


def delete(id: str, yes: bool) -> None:
    """Remove the project's folder whole, then its record; without `yes`, refuse (the CLI
    shows `unpushed` first). Nothing outside <workspace>/projects is removed: a folder that
    is a link loses the link only, and a folder whose real path is not directly in the real
    projects/ is refused. A folder not removed whole keeps the record."""
    get(id)
    target = folder(id)
    if not yes:
        raise ProjectError(
            f"deleting project {id} removes its folder {target} with everything in it; "
            "run again with --yes"
        )
    if target.is_symlink():
        target.unlink()
    elif os.path.lexists(target):
        real = Path(os.path.realpath(target))
        if real.parent != Path(os.path.realpath(projects_folder())):
            raise ProjectError(
                f"{target} is not in {projects_folder()}: LADO removes nothing outside it"
            )
        try:
            shutil.rmtree(real)  # links inside are removed as links, never followed
        except OSError as error:
            raise ProjectError(
                f"could not remove {target} whole: {error}; the project stays"
            ) from error
    state.delete_project(id)
