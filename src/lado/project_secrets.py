"""A project's secrets: one file per secret in `<LADO_HOME>/projects/<id>/secrets/`, the
file's name the variable's and its content the value (openspec capability `projects`; the
model: docs/design/projects.md).

This module alone writes and removes them, and lado.projects keeps their rules. The human
sets them (the CLI, the server); nothing reads a value back but the launch of an agent of
a session in the project (lado.runtime._base_env), LADO's git of a clone into the project
(lado.clone, both through `layer`), and `lado doctor` and the server's
answer of a project (`unused`), which read the folder to say which files the agents do not
get and let no value out, all through the one reader of variable folders
(lado.agent_env.read_folder). Listing them never opens a file.

Every folder from `<LADO_HOME>/projects` down is opened without following a symbolic link,
each relative to the one above, so a link anywhere on the way is refused, not followed;
`LADO_HOME` itself may be a link (the human's choice). The folders are 700 and the files
600 whatever the umask. A value is written to a new file beside its name and renamed over
it: a reader finds the old value or the new one whole, and a failed write leaves the old
one and no new file. No error holds a value."""

import contextlib
import errno
import os
import secrets
import stat
from collections.abc import Callable, Iterator
from pathlib import Path

from lado import agent_env, providers, state

DATA = "projects"  # under LADO_HOME
SECRETS = "secrets"  # under a project's data folder
FOLDER_MODE, FILE_MODE = 0o700, 0o600
FOLDER_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class LinkRefused(ValueError):
    """A symbolic link on the way to a project's secrets; lado.projects names it."""

    def __init__(self, path: Path):
        super().__init__(
            f"{path} is a symbolic link: LADO writes and removes a project's secrets only in "
            "its own folders"
        )


def data_folder(id: str) -> Path:
    """The folder of what LADO keeps of the project `id` beside lado.db."""
    return state.home_path() / DATA / id


def folder(id: str) -> Path:
    return data_folder(id) / SECRETS


def reserved(name: str) -> bool:
    """A name an agent CLI sets, reserved for a project's secret as for its plain variable
    (the shell's and LADO's own the reader reserves itself)."""
    return name in providers.base.CLI_VARIABLES


def stored(value: str) -> bytes:
    """A value as its file holds it: the reader drops one line break at a file's end (the
    outside folder's rule), so a value ending in one is stored with one more and given
    whole."""
    return value.encode() + (b"\n" if value.endswith("\n") else b"")


def _is_name(name: str) -> bool:
    """Whether `name` can be a secret's file: a variable name only, so no path (`..`, `/`)
    leads out of the folder and no file being written (`.<name>.<random>.tmp`) is one."""
    return bool(agent_env.VARIABLE_NAME.fullmatch(name))


def held(id: str, name: str) -> bool:
    """Whether the secrets folder of `id` has an entry `name`, also one the agents do not
    get now (a link, a loose mode): the name is taken all the same."""
    return _is_name(name) and os.path.lexists(folder(id) / name)


def read(id: str) -> agent_env.Folder:
    """The project's secrets as an agent gets them, and each file not given with why."""
    return agent_env.read_folder(str(folder(id)), own=reserved)


def layer(id: str) -> dict[str, str]:
    """The project's layer of variables, read now: its plain variables from lado.db with its
    secrets over them (a project holds one value per name, and a hand-made file of a plain
    variable's name wins). The one source of both the agents' layer
    (lado.runtime._base_env) and that of a clone into the project (lado.clone)."""
    return {**state.project_variables(id), **read(id).values}


def unused(id: str) -> list[tuple[str | None, str]]:
    """Each entry of the project's secrets folder its agents do not get, by name with why
    (None for the folder itself), as `read` finds them; the values it reads stay here."""
    return [(name or None, reason) for name, reason in read(id).unused]


def names(id: str) -> list[str]:
    """The names of the project's secrets, sorted, without opening a file: the files the
    reader takes by what needs no content, and a file of a loose mode, which a replace mends
    (a file it still cannot give, for its mode, size or content, `unused` names). None while
    the folder is unused (a link, loose)."""
    return _names(str(folder(id)), reserved)


def _names(where: str, own: Callable[[str], bool]) -> list[str]:
    """The names in the own folder `where`, as `names` says."""
    if agent_env.check_own_folder(where) != "":
        return []
    try:
        with os.scandir(where) as found:
            return sorted(
                entry.name
                for entry in found
                if not entry.name.startswith(".")
                and agent_env.check_entry(entry, own) in ("", agent_env.LOOSE_FILE)
            )
    except OSError:
        return []


def _refuse_link(fd: int, name: str, path: Path) -> None:
    """Raise LinkRefused when `name` in the folder `fd` is a symbolic link."""
    with contextlib.suppress(FileNotFoundError):
        if stat.S_ISLNK(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode):
            raise LinkRefused(path)


def _open_folder(fd: int, name: str, path: Path) -> int:
    """The folder `name` in the folder `fd`, opened without following a link."""
    try:
        return os.open(name, FOLDER_FLAGS, dir_fd=fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR, errno.EMLINK):
            _refuse_link(fd, name, path)
        raise


def _chain(id: str, *, make: bool, depth: int = 3) -> contextlib.AbstractContextManager:
    """The folder `depth` levels down `projects/<id>/secrets` (_open_chain)."""
    return _open_chain((DATA, id, SECRETS)[:depth], make=make)


@contextlib.contextmanager
def _open_chain(parts: tuple[str, ...], *, make: bool) -> Iterator[int | None]:
    """The folder `parts` down from LADO_HOME, opened with no link followed on the way
    (LinkRefused); a missing one is made 700 with `make`, else None. `make` makes every
    folder of the chain 700."""
    home = state.home_path()
    path = home
    fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in parts:
            path = path / name
            try:
                child = _open_folder(fd, name, path)
            except FileNotFoundError:
                if not make:
                    yield None
                    return
                with contextlib.suppress(FileExistsError):  # made by another writer since
                    os.mkdir(name, FOLDER_MODE, dir_fd=fd)
                child = _open_folder(fd, name, path)
            os.close(fd)
            fd = child
            if make:
                os.fchmod(fd, FOLDER_MODE)  # the umask's doing, or an older folder's
        yield fd
    finally:
        os.close(fd)


def write(id: str, name: str, value: str) -> None:
    """Set the secret `name` of `id` to `value` (checked by lado.projects), replacing it
    whole. OSError when the disk refuses it, the old value then kept; ValueError for a name
    that is no variable name (lado.projects refuses it first)."""
    _write((DATA, id, SECRETS), folder(id), name, value)


def _write(parts: tuple[str, ...], where: Path, name: str, value: str) -> None:
    """Set `name` in the folder `parts` (at `where`) to `value`, as `write` says."""
    if not _is_name(name):
        raise ValueError(f"{name!r} is not a variable name")
    with _open_chain(parts, make=True) as fd:
        assert fd is not None
        _refuse_link(fd, name, where / name)
        temporary = f".{name}.{secrets.token_hex(6)}.tmp"
        out = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, FILE_MODE, dir_fd=fd
        )
        try:
            try:
                os.fchmod(out, FILE_MODE)
                data = memoryview(stored(value))
                while data:
                    data = data[os.write(out, data) :]
                os.fsync(out)
            finally:
                os.close(out)
            os.rename(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temporary, dir_fd=fd)
            raise
        os.fsync(fd)


def remove(id: str, name: str) -> bool:
    """Remove the secret `name` of `id`; False when it has none of that name, which a name
    that is no variable name never is (a path or a file being written is no secret)."""
    return _remove((DATA, id, SECRETS), folder(id), name)


def _remove(parts: tuple[str, ...], where: Path, name: str) -> bool:
    """Remove `name` from the folder `parts` (at `where`), as `remove` says."""
    if not _is_name(name):
        return False
    with _open_chain(parts, make=False) as fd:
        if fd is None:
            return False
        _refuse_link(fd, name, where / name)
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            return False
        os.fsync(fd)
        return True


# LADO's secrets: `<LADO_HOME>/secrets/`, the same store over LADO's own folder, for the
# agent CLIs' login variables the human sets in Settings (lado.logins checks the names);
# agent_env.resolve lays them between the outside folder and a project's layer.


def lado_folder() -> Path:
    return agent_env.lado_secrets_folder()


def write_lado(name: str, value: str) -> None:
    """Set LADO's secret `name` to `value`, as `write` does for a project's."""
    state.home()  # made when missing, as for lado.db
    _write((agent_env.LADO_SECRETS,), lado_folder(), name, value)


def remove_lado(name: str) -> bool:
    """Remove LADO's secret `name`, as `remove` does for a project's."""
    return _remove((agent_env.LADO_SECRETS,), lado_folder(), name)


def read_lado() -> agent_env.Folder:
    """LADO's secrets as the agents get them, and each file not given with why."""
    return agent_env.lado_secrets()


def lado_names() -> list[str]:
    """The names of LADO's secrets the agents get, sorted, without a value."""
    return _names(str(lado_folder()), agent_env.nothing_more)


def _links(fd: int, path: Path) -> Iterator[Path]:
    """Every symbolic link in the folder `fd` (at `path`) and its subfolders."""
    with os.scandir(fd) as found:
        entries = list(found)
    for entry in entries:
        if entry.is_symlink():
            yield path / entry.name
        elif entry.is_dir(follow_symlinks=False):
            child = _open_folder(fd, entry.name, path / entry.name)
            try:
                yield from _links(child, path / entry.name)
            finally:
                os.close(child)


def check_removable(id: str) -> None:
    """Refuse (LinkRefused) when a link is on the way to the data folder of `id` or in it,
    so that remove_all can remove it whole; nothing to remove is no refusal."""
    with _chain(id, make=False, depth=2) as fd:
        if fd is None:
            return
        for link in _links(fd, data_folder(id)):
            raise LinkRefused(link)


def _remove_entries(fd: int, path: Path) -> None:
    with os.scandir(fd) as found:
        entries = list(found)
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            child = _open_folder(fd, entry.name, path / entry.name)
            try:
                _remove_entries(child, path / entry.name)
            finally:
                os.close(child)
            os.rmdir(entry.name, dir_fd=fd)
        else:
            os.unlink(entry.name, dir_fd=fd)


def remove_all(id: str) -> None:
    """Remove the data folder of `id` whole (its secrets with it), after check_removable;
    a folder already gone is no error."""
    check_removable(id)
    with _chain(id, make=False, depth=1) as projects:
        if projects is None:
            return
        try:
            fd = _open_folder(projects, id, data_folder(id))
        except FileNotFoundError:
            return
        try:
            _remove_entries(fd, data_folder(id))
        finally:
            os.close(fd)
        os.rmdir(id, dir_fd=projects)
