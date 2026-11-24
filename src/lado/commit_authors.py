"""Who LADO's agents and LADO itself commit as (openspec capability `commit-authors`): LADO's
own commit author and a project's, kept in lado.db (lado.state) alone, never in a git
config file, and the author in effect for a place.

The order is git's own once the launch laid its entries (lado.git_servers.variables): a
project's author, then the author of a saved git server a remote of the repository is on,
then LADO's author, then git's own config (system, global, the repository's). LADO's and a
project's go to an agent as plain `user.name`/`user.email` entries of `GIT_CONFIG_*`, which
git reads from 2.31 (`check_git`); LADO's own first commits (lado.scratch, lado.setup) pass
the author in effect with `-c`. `GIT_AUTHOR_*` and `GIT_COMMITTER_*` of an agent's
environment win over all: `author_variables` names them, and `in_effect` leaves them out.

A server's own author stays lado.git_servers'; its check is `check` here."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from lado import agent_env, git_servers, state
from lado.state import Author

__all__ = ["Author", "InEffect"]

# Where the author in effect comes from (`in_effect`), first to last.
PROJECT, SERVER, LADO, GIT, NONE = "project", "server", "lado", "git", "none"
SOURCES = (PROJECT, SERVER, LADO, GIT, NONE)
# The variables that set the author or committer over every git config.
VARIABLES = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
LADO_NEEDS = "LADO's commit author needs"
PROJECT_NEEDS = "a project's commit author needs"
CLEAR_LADO = "lado git-server author --clear"
CLEAR_PROJECT = "lado project author {id} --clear"


class InEffect(NamedTuple):
    """The author commits at a place carry, None for none, and its source (SOURCES)."""

    author: Author | None
    source: str


class Unreadable(Exception):
    """git ran but could not read its config, with git's first line."""


def text(author: Author) -> str:
    """`<name> <<email>>`."""
    return f"{author.name} <{author.email}>"


def check(name: str, email: str) -> tuple[str, str]:
    """The commit author's name and email, trimmed; lado.git_servers.Refused (field `name`
    or `email`) for a name that is empty or holds `<`, `>` or a control character, an email
    that is not `local@domain` (one `@`, text on both sides, no space, `<`, `>` or control
    character), and a value over git_servers.AUTHOR_MAX characters. git and the server
    decide the rest."""
    name, email = name.strip(), email.strip()
    refused = git_servers.Refused
    most = git_servers.AUTHOR_MAX
    if not name:
        raise refused("the author's name is empty", field=git_servers.NAME_FIELD)
    if len(name) > most:
        raise refused(
            f"the author's name is longer than {most} characters", field=git_servers.NAME_FIELD
        )
    if "<" in name or ">" in name or _control(name):
        raise refused(
            "the author's name holds no < or > or line break", field=git_servers.NAME_FIELD
        )
    if len(email) > most:
        raise refused(
            f"the author's email is longer than {most} characters", field=git_servers.EMAIL_FIELD
        )
    local, at, domain = email.partition("@")
    if (
        not local
        or not at
        or not domain
        or "@" in domain
        or any(c.isspace() or c in "<>" for c in email)
        or _control(email)
    ):
        raise refused("not an email address: name@host", field=git_servers.EMAIL_FIELD)
    return name, email


def _control(value: str) -> bool:
    return any(ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0 for c in value)


def check_git(env: Mapping[str, str], what: str, clear: str | None = None) -> None:
    """Refuse a git on `env`'s PATH older than 2.31, which reads no `GIT_CONFIG_COUNT`;
    `what` names the author that needs it, `clear` the command that clears it, for a
    launch."""
    from lado import runtime  # runtime lays the entries: imported when asked

    older = git_servers._older_git(env, runtime.GIT_MIN, what)
    if older:
        raise git_servers.Refused(f"{older}, or clear it ({clear})" if clear else older, page=older)


def _readable() -> bool:
    """Whether lado.db is there at this LADO's schema: without one, or at another schema,
    LADO has no author nor server to read (a read makes no lado.db, as `lado doctor` and a
    fresh start's check ask before any)."""
    return state.schema_version() == state.SCHEMA_VERSION


def lado() -> Author | None:
    return state.commit_author() if _readable() else None


def set_lado(name: str, email: str) -> Author:
    """Set LADO's commit author: the author as saved. Refused for a name or email `check`
    refuses, or a git older than 2.31 here."""
    name, email = check(name, email)
    check_git(os.environ, LADO_NEEDS)
    state.set_commit_author(name, email)
    return Author(name, email)


def clear_lado() -> bool:
    """False when LADO had no commit author."""
    return state.clear_commit_author()


def project(id: str) -> Author | None:
    """The project's commit author; None for none, or no such project."""
    found = state.get_project(id) if _readable() else None
    return _author(found.author_name, found.author_email) if found else None


def set_project(id: str, name: str, email: str) -> Author | None:
    """Set the project's commit author: the author as saved, None for no such project.
    Refused as `set_lado` is."""
    name, email = check(name, email)
    check_git(os.environ, PROJECT_NEEDS)
    return Author(name, email) if state.set_project_author(id, name, email) else None


def clear_project(id: str) -> bool:
    """False for no such project; True also when it had no author."""
    return state.set_project_author(id, None, None) is not None


def _author(name: str | None, email: str | None) -> Author | None:
    return Author(name, email) if name is not None and email is not None else None


def entries(author: Author) -> list[tuple[str, str]]:
    """The git config entries that make `author` the one commits carry."""
    return [("user.name", author.name), ("user.email", author.email)]


def git_own(path: str) -> Author | None:
    """git's own `user.name` and `user.email` where `path`'s nearest existing folder is
    (outside any repository: git's global and system config, the ones the agents' git
    reads), without the entries of a launch this process may run under
    (agent_env.without_launch); None when either is missing. A git that does not run
    raises LAD-5's FolderProblem; one that cannot read its config `Unreadable`."""
    from lado import runtime

    folder = str(_nearest(Path(path)))
    env = {**agent_env.without_launch(os.environ), "LC_ALL": "C"}
    found = []
    for key in ("user.name", "user.email"):
        result = runtime._run_git(folder, "config", "--get", key, env=env)
        if result.returncode not in (0, 1):  # 1: not set
            raise Unreadable(_line(result))
        if not result.stdout.strip():
            return None
        found.append(result.stdout.strip())
    return Author(*found)


def in_effect(path: str, project_id: str | None = None) -> InEffect:
    """The author a commit at `path` (a repository, or a folder to be made one) carries
    once the launch laid its entries, by git's own order: the project's author of
    `project_id`; of the saved servers a remote of the repository is on (lado.git_servers.
    server_for), the last by host with an author, as `git_servers.variables` lays them;
    LADO's author; `git_own`; none. The author variables of an environment are no part of
    it (`author_variables`)."""
    if project_id is not None and (found := project(project_id)) is not None:
        return InEffect(found, PROJECT)
    servers = state.git_servers() if _readable() else []
    if servers:
        on = {s.id for s in (git_servers.server_for(url, servers) for url in _remotes(path)) if s}
        authored = [s for s in servers if s.id in on and git_servers.author_text(s)]
        if authored:
            last = authored[-1]
            return InEffect(_author(last.author_name, last.author_email), SERVER)
    if (found := lado()) is not None:
        return InEffect(found, LADO)
    if (found := git_own(path)) is not None:
        return InEffect(found, GIT)
    return InEffect(None, NONE)


def _remotes(path: str) -> list[str]:
    """The remote URLs in the config git reads at `path`'s nearest existing folder."""
    from lado import runtime

    folder = str(_nearest(Path(path)))
    env = {**agent_env.without_launch(os.environ), "LC_ALL": "C"}
    result = runtime._run_git(folder, "config", "--get-regexp", r"^remote\..*\.url$", env=env)
    if result.returncode != 0:  # 1: none
        return []
    return [line.split(" ", 1)[1] for line in result.stdout.splitlines() if " " in line]


def author_variables(env: Mapping[str, str]) -> list[str]:
    """The names of VARIABLES `env` holds, in VARIABLES' order: they win over every author
    LADO gives."""
    return [name for name in VARIABLES if name in env]


def _nearest(folder: Path) -> Path:
    """`folder` when it exists, else its nearest ancestor that does."""
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    return folder


def _line(result: subprocess.CompletedProcess) -> str:
    """git's first line of a failure."""
    from lado import runtime

    return runtime._first_line(result.stderr) or f"git exited {result.returncode}"
