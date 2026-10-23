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

import contextlib
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lado import agent_env, project_secrets, providers, runtime, state

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


def refusal(
    path: str, *, url: str | None = None, fresh: bool = False
) -> runtime.FolderProblem | None:
    """Why no new session without a project may start at `path` (kind `in_project`), by its
    real path: it is inside projects/ while that folder is LADO's. The text names the
    project; the hint offers the session of the project's repository the path is in, or
    adding the repository for a clone of `url` or a fresh start (`fresh`) into a new folder
    directly in the project's folder, else the project's repositories, or the projects for
    a folder of none. None outside projects/, when projects/ is the human's own folder, and
    without projects."""
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
    return runtime.FolderProblem(
        "in_project",
        f"{path} belongs to the project {project.title or project.id}: start a session in "
        "the project",
        _hint(project.id, parts[1:], root, url, fresh),
    )


ADD_HINT = "Add a repository to the project:"


def _hint(
    id: str, below: tuple[str, ...], root: Path, url: str | None, fresh: bool
) -> runtime.Hint:
    """`refusal`'s hint for a path `below` the project's folder (in the real projects/
    `root`)."""
    if below and _is_repository(root / id / below[0]):
        return runtime.Hint(
            "Start a session in the project:", f"lado start --project {id} --repo {below[0]}"
        )
    new = (
        len(below) == 1 and _good_repo_name(below[0]) and not os.path.lexists(root / id / below[0])
    )
    if new and fresh:
        return runtime.Hint(ADD_HINT, f"lado project repo add {id} --new {below[0]}")
    if new and url:
        from lado import clone  # lado.clone builds on this module

        other = "" if clone.Address.parse(url).repo_name == below[0] else f" --name {below[0]}"
        return runtime.Hint(
            ADD_HINT, f"lado project repo add {id} {runtime.public_remote(url)}{other}"
        )
    return runtime.Hint("See the project's repositories:", f"lado project show {id}")


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
    left = project_secrets.data_folder(id)
    if os.path.lexists(left):  # only a failed deletion leaves one: never inherit its secrets
        raise ProjectError(f"{left} is left from a project {id}: remove it or choose another id")
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


# A project's plain variables (lado.db) and secrets (files, lado.project_secrets): the human
# sets them (the CLI, the server), every agent of a session in the project gets them
# (lado.runtime._base_env). A name the shell, LADO or an agent CLI sets is reserved for
# both; a name that looks like a secret is no plain variable; a project holds one value per
# name.
RESERVED_NAMES = agent_env.RESERVED | providers.base.CLI_VARIABLES
SECRET_WORDS = ("TOKEN", "KEY", "SECRET", "PASSWORD")


class NoSuchVariable(ProjectError):
    pass


def check_name(name: str) -> None:
    """Refuse a name that is no variable name or a reserved one: the rule of a plain
    variable's name and of a secret's."""
    if not agent_env.VARIABLE_NAME.fullmatch(name):
        raise ProjectError(
            f"the name {name} is not a variable name: Latin letters, digits and _, not "
            "starting with a digit"
        )
    if name in RESERVED_NAMES or name.startswith(agent_env.RESERVED_PREFIX):
        raise ProjectError(f"{name} is reserved: LADO or the agent CLIs set it")


def _check_value(name: str, value: str) -> None:
    """Refuse a value that is no text of at most 64 KiB."""
    try:
        data = value.encode()
    except UnicodeEncodeError:
        data = None  # lone surrogates, as argv gives bytes that are no UTF-8
    if data is None or "\0" in value:
        raise ProjectError(f"the value of {name} is not UTF-8 text")
    if len(data) > agent_env.MAX_VALUE:
        raise ProjectError(f"the value of {name} is larger than 64 KiB")


def check_variable(id: str, name: str, value: str | None) -> None:
    """Refuse a plain variable's name that is no variable name, reserved or like a
    secret's, and a `value` (when given) that is no text of at most 64 KiB; an empty value
    is a value."""
    check_name(name)
    word = next((w for w in SECRET_WORDS if w in name.upper()), None)
    if word:
        raise ProjectError(
            f"{name} looks like a secret ({word}): a plain variable takes no name with "
            f"{', '.join(SECRET_WORDS[:-1])} or {SECRET_WORDS[-1]}; set it as a secret with "
            f"lado project set {id} {name} --secret"
        )
    if value is not None:
        _check_value(name, value)


def check_secret(id: str, name: str, value: str) -> None:
    """Refuse a secret's name by check_name (any other name may be a secret), and a value
    that is empty or no text of at most 64 KiB."""
    check_name(name)
    if not value:
        raise ProjectError(
            f"the secret {name} is empty; to remove it: lado project unset {id} {name}"
        )
    _check_value(name, value)
    if len(project_secrets.stored(value)) > agent_env.MAX_VALUE:  # what the reader limits
        raise ProjectError(f"the value of {name} is larger than 64 KiB")


def variables(id: str) -> dict[str, str]:
    """The project's plain variables, by name."""
    get(id)
    return state.project_variables(id)


def secrets(id: str) -> list[str]:
    """The names of the project's secrets (lado.project_secrets.names), never a value."""
    get(id)
    return project_secrets.names(id)


def running(id: str) -> list[str]:
    """The project's sessions that are not stopped, by name: their agents keep the
    environment they started with."""
    return sorted(
        sess.name
        for sess in state.project_sessions(id)
        if runtime.session_status(sess) != runtime.SessionStatus.STOPPED
    )


def _held(id: str, name: str, kind: str) -> ProjectError:
    """A project holds one value per name: `name` is held as `kind`. The two stores share
    no transaction, so the human moves a name from one to the other in two commands."""
    return ProjectError(
        f"{name} is {kind} of {id}; remove it first with lado project unset {id} {name}"
    )


def set_variable(id: str, name: str, value: str) -> list[str]:
    """Set the project's plain variable (check_variable first), over its old value; the
    project's running sessions."""
    get(id)
    check_variable(id, name, value)
    if project_secrets.held(id, name):
        raise _held(id, name, "a secret")
    state.set_project_variable(id, name, value)
    return running(id)


def set_secret(id: str, name: str, value: str) -> list[str]:
    """Set the project's secret (check_secret first) in its own file, over its old value;
    the project's running sessions. No error holds the value."""
    get(id)
    check_secret(id, name, value)
    if name in state.project_variables(id):
        raise _held(id, name, "a plain variable")
    with _secrets_refused(f"could not write the secret {name} of {id}"):
        project_secrets.write(id, name, value)
    return running(id)


@contextlib.contextmanager
def _secrets_refused(failed: str, then: str = "") -> Iterator[None]:
    """The secrets store's refusals as ProjectError: a link by its own text, an OSError as
    `failed: <reason><then>`. The OSError's text is left out: it never holds a value, but
    its file name is no business of the human's either."""
    try:
        yield
    except project_secrets.LinkRefused as error:
        raise ProjectError(str(error)) from None
    except OSError as error:
        raise ProjectError(f"{failed}: {error.strerror or error}{then}") from None


def _remove_secret(id: str, name: str) -> bool:
    with _secrets_refused(f"could not remove the secret {name} of {id}"):
        return project_secrets.remove(id, name)


def _listed(found: list[str]) -> str:
    return names(found) or "none"


def unset_variable(id: str, name: str) -> list[str]:
    """Remove the project's plain variable, by any name stored (no name rule: a row stored
    before a rule changed can go); the project's running sessions. The server's: its routes
    go by kind."""
    get(id)
    if not state.unset_project_variable(id, name):
        found = _listed(list(state.project_variables(id)))
        raise NoSuchVariable(f"project {id} has no variable {name}; its variables: {found}")
    return running(id)


def unset_secret(id: str, name: str) -> list[str]:
    """Remove the project's secret; the project's running sessions. The server's."""
    get(id)
    if not _remove_secret(id, name):
        found = _listed(project_secrets.names(id))
        raise NoSuchVariable(f"project {id} has no secret {name}; its secrets: {found}")
    return running(id)


def unset(id: str, name: str) -> list[str]:
    """Remove the project's plain variable or secret `name` (both, should a hand-made file
    hold a name of lado.db); the project's running sessions. The CLI's."""
    get(id)
    if state.unset_project_variable(id, name):
        if project_secrets.held(id, name):
            _remove_secret(id, name)
    elif not _remove_secret(id, name):
        raise NoSuchVariable(
            f"project {id} has no variable or secret {name}; its variables: "
            f"{_listed(list(state.project_variables(id)))}; its secrets: "
            f"{_listed(project_secrets.names(id))}"
        )
    return running(id)


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


def _own_root(path: str) -> bool:
    """Whether the folder `path` is the root of a git repository of its own: not a plain
    folder inside a repository that holds it, such as a project folder made one."""
    try:
        top = _git(Path(path), "rev-parse", "--show-toplevel").strip()
    except _GitFailed:
        return False  # no repository LADO can start in
    return os.path.realpath(top) == os.path.realpath(path)


def _is_repository(path: Path) -> bool:
    """Whether the entry `path` of a project's folder is one of its repositories: not
    hidden, not a link, a folder that is a git repository's root (`repositories`)."""
    return (
        not path.name.startswith(".")
        and not path.is_symlink()
        and path.is_dir()
        and _own_root(str(path))
    )


def repositories(id: str) -> list[Repository]:
    """The project's repositories, read from the disk each time: the folders directly in its
    folder, not hidden and not links, that are each a git repository's root; by name."""
    found = []
    for entry in _entries(id):
        if not _is_repository(Path(entry.path)):
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


def _good_repo_name(name: str) -> bool:
    return bool(REPO_NAME.fullmatch(name)) and len(name) <= MAX_REPO_NAME


def check_repo_name(name: str) -> None:
    if not _good_repo_name(name):
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
    _check_own_folder(id)
    check_repo_name(name)
    target = where / name
    if os.path.lexists(target):
        raise ProjectError(
            f"{target} already exists in project {id}: choose another name with --name"
        )
    return target


def _own_folder(id: str) -> bool:
    """Whether the project's folder is its own: no link, its real path `<real
    projects/>/<id>`. A link (to another project's folder, or anywhere) would add or remove
    repositories somewhere else."""
    where = folder(id)
    real = Path(os.path.realpath(projects_folder())) / id
    return not where.is_symlink() and Path(os.path.realpath(where)) == real


def _check_own_folder(id: str) -> None:
    if not _own_folder(id):
        raise ProjectError(
            f"{folder(id)} is a link or not where project {id}'s folder belongs: LADO adds and "
            "removes repositories only in the project's own folder"
        )


def adds_to(id: str | None, path: str) -> bool:
    """Whether `path` is an entry directly in the own folder of the project `id`
    (`_own_folder`), by real paths: the one place a clone or fresh start for that project
    may go (`clone.clone`, `scratch.make`), past the refusal of a new session inside
    projects/."""
    if id is None or not _own_folder(id):
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
    raise _no_repository(id, name, found)


def _no_repository(id: str, name: str, found: list[Repository]) -> NoSuchRepository:
    if not found:
        return NoSuchRepository(
            f"project {id} has no repositories yet: add one with lado project repo add {id} "
            "<git-url> or --new <name>"
        )
    return NoSuchRepository(
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
    for entry in sorted(project_folder.iterdir()):
        if entry.is_dir() and os.path.lexists(entry / ".git"):
            lines += _checkout_lines(entry, project_folder)
    return lines


def _checkout_lines(entry: Path, base: Path) -> list[str]:
    """`unpushed`'s lines of the one repository `entry`: its uncommitted changes and
    branches not pushed, then each of its worktrees with changes, shown relative to `base`
    when inside it."""
    real = Path(os.path.realpath(base))  # git names worktrees by real paths
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
        return [f"{entry.name}: could not check: {failed}"]
    lines = [f"{entry.name}: {'; '.join(findings)}"] if findings else []
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
    which refuses first), then remove its data folder with its secrets, then its record;
    without `yes`, refuse (the CLI shows `unpushed` first). Nothing outside
    <workspace>/projects is removed: a folder that is a link loses the link only, and a
    folder whose real path is not directly in the real projects/ is refused. A link on the
    way to the data folder or in it refuses before anything is removed. A folder not
    removed whole keeps the sessions and the record; a session or a data folder not removed
    keeps the record, and a rerun finishes."""
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
    data = project_secrets.data_folder(id)
    with _secrets_refused(f"could not read {data}", "; the project stays"):
        project_secrets.check_removable(id)
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
    again = f"; the project stays: run lado project delete {id} --yes again"
    with _secrets_refused(f"could not remove {data} whole", again):
        project_secrets.remove_all(id)
    state.delete_project(id)


@dataclass(frozen=True)
class Removal:
    """What removing the entry `name` of a project's folder does: a repository's folder
    goes with the stopped sessions of the project in it (by name, with their open runs),
    and `unpushed` is what it loses; a link loses the link only (`target` as written)."""

    name: str
    kind: Literal["repository", "link"]
    path: Path
    target: str | None
    sessions: list[tuple[str, int]]
    unpushed: list[str]


def removal(id: str, name: str) -> Removal:
    """What `remove_repo` would do; refused for an unknown project, a name no visible entry
    of the project's folder has (NoSuchRepository), an entry that is neither a repository
    nor a link, and a repository with a session working in it (by path, one without a
    project too) that is not stopped, and for a project folder that is not its own
    (`_own_folder`)."""
    get(id)
    _check_own_folder(id)
    entry = next((e for e in _entries(id) if e.name == name), None)
    if entry is None:
        raise _no_repository(id, name, repositories(id))
    path = Path(entry.path)
    if entry.is_symlink():
        return Removal(name, "link", path, os.readlink(path), [], [])
    if not _is_repository(path):
        raise ProjectError(
            f"{name} in project {id} is not a repository: LADO removes only repositories and links"
        )
    real = Path(os.path.realpath(path))

    def inside(sess: state.Session) -> bool:
        return Path(os.path.realpath(sess.repo)).is_relative_to(real)

    busy = [
        sess.name
        for sess in state.list_sessions()
        if inside(sess) and runtime.session_status(sess) != runtime.SessionStatus.STOPPED
    ]
    if busy:
        raise ProjectError(
            f"repository {name} of project {id} has sessions not stopped: {names(busy)}; stop "
            "them first with lado stop <name>"
        )
    # The project's own only: the path is a safety check, never how LADO learns a project.
    sessions = sorted(
        (sess.name, len(state.list_runs(sess.name, open_only=True)))
        for sess in state.project_sessions(id)
        if inside(sess)
    )
    return Removal(name, "repository", path, None, sessions, _checkout_lines(path, folder(id)))


def remove_repo(id: str, name: str, yes: bool) -> Removal:
    """Remove the repository `name` of the project `id` (`removal`, which refuses first):
    its folder whole, then its sessions forgotten; a link loses the link only. Without
    `yes`, refuse (the CLI shows the removal first). Nothing outside the project's folder
    is removed: a repository whose real path is not directly in the project folder's, which
    is not directly in the real projects/, is refused. A folder not removed whole keeps the
    sessions; a session not forgotten is named."""
    found = removal(id, name)
    if not yes:
        if found.kind == "link":
            raise ProjectError(
                f"removing {name} of project {id} deletes the link only, not its target "
                f"{found.target}; run again with --yes"
            )
        count = len(found.sessions)
        forgets = f" and forgets its {count} session{'' if count == 1 else 's'}" if count else ""
        raise ProjectError(
            f"removing repository {name} of project {id} deletes its folder {found.path} with "
            f"everything in it{forgets}; run again with --yes"
        )
    if found.kind == "link":
        found.path.unlink()
        return found
    real = Path(os.path.realpath(found.path))
    parent = Path(os.path.realpath(folder(id)))
    if real.parent != parent or parent.parent != Path(os.path.realpath(projects_folder())):
        raise ProjectError(
            f"{found.path} is not in {projects_folder()}: LADO removes nothing outside it"
        )
    try:
        shutil.rmtree(real)  # links inside are removed as links, never followed
    except OSError as error:
        raise ProjectError(
            f"could not remove {found.path} whole: {error}; its sessions stay"
        ) from error
    for session, _ in found.sessions:
        try:
            runtime.forget_session(session, force=True)
        except runtime.LadoError as error:
            raise ProjectError(
                f"the repository is removed, but session {session} could not be forgotten: "
                f"{error}; forget it with lado forget {session} --force"
            ) from error
    return found
