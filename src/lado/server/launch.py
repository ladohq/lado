"""What the New session window asks before a start: a folder's check, the folders of past
sessions, the kits a session of a folder can take and the providers. The decisions stay in
the core: whether a folder will do is runtime.check_repo, a kit is the one kits.find takes,
a provider's state is doctor.provider_status."""

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lado import doctor, kits, providers, runtime, state
from lado.server import models

SUBFOLDERS = 50  # at most this many subfolders of a folder
RECENT = 10  # at most this many recent folders


def full_path(path: str) -> str:
    """`path` with `~` expanded; a relative path is refused: the server's own folder means
    nothing to the human."""
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded):
        raise runtime.LadoError(f"{path} is not a full path: give one from / or ~")
    return expanded


def folder_info(path: str, has_db: bool) -> models.FolderInfo:
    path = full_path(path)
    try:
        root = runtime.check_repo(path)
        ok, problem, has_commits = True, None, True
    except runtime.LadoError as refused:
        ok, problem, has_commits = False, str(refused), False
        root = _root_or_none(path)
    name = runtime.slug(Path(root).name) if root else None
    return models.FolderInfo(
        path=path,
        ok=ok,
        problem=problem,
        root=root,
        branch=_branch(root) if root else None,
        has_commits=has_commits,
        subfolders=_subfolders(Path(path)),
        default_name=name,
        name_state=_name_state(name, root, has_db) if name and root else None,
    )


def _root_or_none(path: str) -> str | None:
    if not Path(path).exists():
        return None
    try:
        return runtime.repo_root(path)
    except runtime.LadoError:
        return None


def _branch(root: str) -> str | None:
    try:
        return runtime.git(root, "symbolic-ref", "--short", "HEAD")
    except runtime.LadoError:
        return None  # a detached HEAD


def _subfolders(path: Path) -> list[str]:
    try:
        names = sorted(p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []
    return names[:SUBFOLDERS]


def _name_state(name: str, root: str, has_db: bool) -> models.NameState:
    sess = state.get_session(name) if has_db else None
    if sess is None:
        return "free"
    if sess.repo != root:
        return "taken_elsewhere"
    running = (runtime.SessionStatus.RUNNING, runtime.SessionStatus.LOOP_DOWN)
    return "running" if runtime.session_status(sess) in running else "stopped_here"


def recent_folders() -> list[models.RecentFolder]:
    """The folders of past sessions, each with its latest started session, latest first."""
    found: dict[str, state.Session] = {}
    for sess in state.sessions_by_start():
        found.setdefault(sess.repo, sess)
    return [
        models.RecentFolder(path=repo, session=models.session_info(sess))
        for repo, sess in list(found.items())[:RECENT]
    ]


def kit_infos(where: str | None, has_db: bool) -> list[models.KitInfo]:
    """The kit of each name a session of the folder `where` would take; one that does not
    load is there too, with why. Without lado.db no kit is installed (and none is made)."""
    repo = _root_or_none(full_path(where)) if where else None
    try:
        listed = kits.available(repo, with_installed=has_db)
    except kits.KitError as exc:
        raise runtime.LadoError(str(exc)) from exc
    infos = []
    for found, shadowed_by in listed:
        if shadowed_by is not None:
            continue
        try:
            kit = found.load()
        except kits.KitError as exc:
            infos.append(
                models.KitInfo(
                    name=found.name, version="", description="", valid=False, problem=str(exc)
                )
            )
            continue
        infos.append(
            models.KitInfo(
                name=kit.name,
                version=kit.version,
                description=kit.description,
                valid=True,
                problem=None,
            )
        )
    return infos


def provider_infos() -> list[models.ProviderInfo]:
    """Each provider of the registry, its CLI checked anew (`<cli> --version`), all at once."""
    registry = [providers.get(name) for name in providers.names()]
    with ThreadPoolExecutor(len(registry)) as pool:
        statuses = list(pool.map(lambda p: doctor.provider_status(p, shutil.which), registry))
    return [
        models.ProviderInfo(
            name=provider.name,
            title=provider.title,
            default=provider.name == providers.DEFAULT,
            permission_modes=list(provider.permission_modes),
            install_hint=provider.install_hint,
            installed=status.installed,
            version=status.version,
            detail=status.detail,
            tested_version=status.tested_version,
            warning=status.warning,
        )
        for provider, status in zip(registry, statuses, strict=True)
    ]
