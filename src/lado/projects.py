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
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lado import runtime, state

if TYPE_CHECKING:
    from lado import clone as clone_module

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


def _ids() -> set[str]:
    """The ids of LADO's projects; none without a lado.db, which asking does not make
    (`lado doctor`)."""
    if state.schema_version() is None:
        return set()
    return {project.id for project in state.list_projects()}


def owned_by_human() -> list[str] | None:
    """The visible entries of projects/ when it is the human's own folder: it holds some and
    none is a project's folder. None otherwise."""
    visible = _visible()
    if not visible:
        return None
    return None if _ids() & set(visible) else visible


def foreign() -> list[str]:
    """The visible entries of projects/ that are no project's folder, files too, once a
    project's folder is there (before that, the folder is the human's: owned_by_human)."""
    visible = _visible() or []
    ids = _ids()
    return [name for name in visible if name not in ids] if ids & set(visible) else []


def lados_folder() -> Path | None:
    """The real path of projects/ while it is LADO's: a folder, LADO has projects, and it is
    not the human's own folder (owned_by_human). None otherwise: nothing in it is refused."""
    if not projects_folder().is_dir():
        return None  # first: most checks find no projects/ at all, and need no lado.db
    if not _ids() or owned_by_human() is not None:
        return None
    return Path(os.path.realpath(projects_folder()))


def refusal(path: str) -> runtime.FolderProblem | None:
    """Why no new session without a project may start at `path` (kind `in_project`), by its
    real path: it is inside projects/ while that folder is LADO's. The text names the
    project, and the hint offers its session, or the projects for a folder of none. None
    outside projects/, when projects/ is the human's own folder, and without projects."""
    root = lados_folder()
    real = Path(os.path.realpath(path))
    if root is None or not real.is_relative_to(root):
        return None
    parts = real.relative_to(root).parts
    if not parts or parts[0] not in _ids():
        return runtime.FolderProblem(
            "in_project",
            f"{path} is in {projects_folder()}, which holds LADO's projects only: start a "
            "session in a project, or move the folder out of projects/",
            runtime.Hint("See the projects:", "lado project list"),
        )
    project = get(parts[0])
    if len(parts) == 1:
        hint = runtime.Hint("See the project's repositories:", f"lado project show {project.id}")
    else:
        hint = runtime.Hint(
            "Start a session in the project:",
            f"lado start --project {project.id} --repo {parts[1]}",
        )
    return runtime.FolderProblem(
        "in_project",
        f"{path} belongs to the project {project.title or project.id}: start a session in "
        "the project",
        hint,
    )


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
    """Every project by id, with its folder and whether that folder is there; none without
    a lado.db."""
    if state.schema_version() is None:
        return []
    found = [(p, folder(p.id)) for p in state.list_projects()]
    return [(p, where, where.is_dir()) for p, where in found]


GIT_TIMEOUT = 20  # seconds one git command of the unpushed scan may take


def _git(checkout: Path, *args: str) -> str:
    """git's output in `checkout`, with no prompt and git's words in English; _GitFailed
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


@dataclass(frozen=True)
class Repository:
    """A repository of a project, as git has it now."""

    name: str
    path: Path
    branch: str | None  # None on a detached HEAD
    remote: str | None  # origin without a secret (runtime.public_remote); None without one


def _entries(id: str) -> list[os.DirEntry]:
    """The entries of the project's folder whose names do not start with ".", by name; none
    when the folder is not found."""
    try:
        with os.scandir(folder(id)) as found:
            return sorted((e for e in found if not e.name.startswith(".")), key=lambda e: e.name)
    except OSError:
        return []


def _own_root(entry: os.DirEntry) -> bool:
    """Whether the folder `entry` is the root of a git repository of its own: not a plain
    folder inside a repository that holds it, such as a project folder made one."""
    try:
        top = _git(Path(entry.path), "rev-parse", "--show-toplevel").strip()
    except _GitFailed:
        return False  # no repository LADO can start in
    return os.path.realpath(top) == os.path.realpath(entry.path)


def repositories(id: str) -> list[Repository]:
    """The project's repositories, read from the disk each time: the folders directly in its
    folder, not hidden and not links, that are each a git repository's root; by name."""
    found = []
    for entry in _entries(id):
        if entry.is_symlink() or not entry.is_dir() or not _own_root(entry):
            continue
        url = runtime.remote(entry.path)
        found.append(
            Repository(
                entry.name,
                Path(entry.path),
                runtime.branch(entry.path),
                runtime.public_remote(url) if url else None,
            )
        )
    return found


def links(id: str) -> list[tuple[str, str]]:
    """The symbolic links directly in the project's folder, not hidden, with their targets
    as written: never a repository of the project, whose work would then lie outside its
    folder; named so the human knows where such a repository went."""
    return [(e.name, os.readlink(e.path)) for e in _entries(id) if e.is_symlink()]


REPO_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")  # the case kept, as git clone keeps it
MAX_REPO_NAME = 100


class NoSuchRepository(ProjectError):
    pass


def check_repo_name(name: str) -> None:
    if not (REPO_NAME.fullmatch(name) and len(name) <= MAX_REPO_NAME):
        raise ProjectError(
            f"the repository name {name} is not valid: Latin letters, digits, ., _ and -, "
            f"not starting with . or -, at most {MAX_REPO_NAME} characters"
        )


def new_repo_folder(id: str, name: str) -> Path:
    """The folder a repository `name` added to the project `id` goes to, checked before
    anything is cloned or made: a known project whose folder is there, the name rule, and
    no entry of that name (any kind; the disk decides the case)."""
    get(id)
    where = folder(id)
    if not where.is_dir():
        raise ProjectError(f"the folder of project {id} is not found: {where}")
    check_repo_name(name)
    target = where / name
    if os.path.lexists(target):
        raise ProjectError(
            f"{target} already exists in project {id}: choose another name with --name"
        )
    return target


def adds_to(id: str | None, path: str) -> bool:
    """Whether `path` is an entry directly in the folder of the project `id`, by real paths:
    the one place a clone or fresh start for that project may go (`clone.clone`,
    `scratch.make`), past the refusal of a new session inside projects/."""
    if id is None:
        return False
    return Path(os.path.realpath(path)).parent == Path(os.path.realpath(folder(id)))


def _added(id: str, target: Path) -> Repository:
    """The repository just made at `target`, as `repositories` reads it."""
    return next(repo for repo in repositories(id) if repo.path == target)


def add_clone(
    id: str,
    url: str,
    name: str | None,
    branch: str | None = None,
    on_progress: "Callable[[clone_module.Progress], None] | None" = None,
    cancelled: threading.Event | None = None,
) -> Repository:
    """Clone `branch` of `url` into the project's folder as `name` (else the URL's
    repository name), through `clone.clone`: a failed or cancelled clone leaves nothing."""
    from lado import clone  # lado.clone builds on this module

    if name is None:
        name = clone.default_folder(url).name  # its refusal for a URL that names none
    target = new_repo_folder(id, name)
    clone.clone(url, str(target), branch, on_progress, cancelled, project=id)
    return _added(id, target)


def add_new(id: str, name: str) -> Repository:
    """Make `name` in the project's folder a repository with one empty commit, through
    `scratch.make`."""
    from lado import scratch  # lado.scratch builds on this module

    target = new_repo_folder(id, name)
    scratch.make(str(target), name, project=id)
    return _added(id, target)


def repository(id: str, name: str) -> Repository:
    """The repository `name` of the project `id`, a session's folder in the project; refused
    naming what there is (a link of that name as a link)."""
    get(id)
    found = repositories(id)
    for repo in found:
        if repo.name == name:
            return repo
    for link, target in links(id):
        if link == name:
            raise ProjectError(
                f"{name} in project {id} is a link to {target}: clone it into {folder(id)} instead"
            )
    if not found:
        raise ProjectError(
            f"project {id} has no repositories yet: a repository is a git folder in {folder(id)}"
        )
    raise ProjectError(
        f"project {id} has no repository {name}; its repositories: "
        + ", ".join(repo.name for repo in found)
    )


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


def sessions_to_forget(id: str) -> list[tuple[str, int]]:
    """The sessions of the project that deleting it forgets, by name, each with its number
    of open runs. Refused while one of them, or any session working in the project's folder
    (one from before sessions had projects too), is not stopped: deleting would pull the
    folder from under its agents."""
    get(id)
    real = Path(os.path.realpath(folder(id)))
    busy = [
        sess.name
        for sess in state.list_sessions()
        if (sess.project == id or Path(os.path.realpath(sess.repo)).is_relative_to(real))
        and runtime.session_status(sess) != runtime.SessionStatus.STOPPED
    ]
    if busy:
        raise ProjectError(
            f"project {id} has sessions not stopped: {names(busy)}; stop them first with "
            "lado stop <name>"
        )
    return sorted(
        (sess.name, len(state.list_runs(sess.name, open_only=True)))
        for sess in state.project_sessions(id)
    )


def delete(id: str, yes: bool) -> None:
    """Remove the project's folder whole, then forget its sessions (sessions_to_forget,
    which refuses first), then remove its record; without `yes`, refuse (the CLI shows
    `unpushed` first). Nothing outside <workspace>/projects is removed: a folder that is a
    link loses the link only, and a folder whose real path is not directly in the real
    projects/ is refused. A folder not removed whole keeps the sessions and the record; a
    session not forgotten keeps the record, which the sessions' foreign key holds anyway."""
    sessions = [name for name, _ in sessions_to_forget(id)]
    target = folder(id)
    if not yes:
        forgets = ""
        if sessions:
            forgets = f" and forgets its {len(sessions)} session{'' if len(sessions) == 1 else 's'}"
        raise ProjectError(
            f"deleting project {id} removes its folder {target} with everything in it"
            f"{forgets}; run again with --yes"
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
    for name in sessions:
        try:
            runtime.forget_session(name, force=True)
        except runtime.LadoError as error:
            raise ProjectError(
                f"could not forget session {name}: {error}; the project stays: run lado "
                f"project delete {id} --yes again"
            ) from error
    state.delete_project(id)
