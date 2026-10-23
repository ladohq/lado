"""What the New session window asks before a start: a folder's check, a fresh start's
names and folder, the folders of past sessions, the kits a session of a folder can take and
the providers. The decisions stay in the core: whether a folder will do is
runtime.check_repo, a fresh start is lado.scratch, a kit is the one kits.find takes, a
provider's state is doctor.provider_status."""

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lado import doctor, kits, project_secrets, projects, providers, runtime, scratch, state
from lado.server import models

SUBFOLDERS = 50  # at most this many subfolders of a folder
RECENT = 10  # at most this many recent folders


def folder_info(path: str, has_db: bool) -> models.FolderInfo:
    path = runtime.full_path(path)
    # Before git: a start there is refused whatever; a missing folder could be made one.
    if refused := projects.refusal(path, fresh=True):
        return models.FolderInfo(
            path=path,
            ok=False,
            problem=str(refused),
            root=None,
            branch=None,
            problem_kind=refused.kind,
            hint=models.hint_info(refused.hint),
            subfolders=[],
            default_name=None,
            name_state=None,
            provider=None,
            project=_project_place(path),
        )
    kind, hint = None, None
    try:
        root = runtime.check_repo(path)
        ok, problem = True, None
    except runtime.LadoError as refused:
        ok, problem = False, str(refused)
        if isinstance(refused, runtime.FolderProblem):
            kind = refused.kind
            hint = models.hint_info(refused.hint)
        root = _root_or_none(path)
    name = runtime.slug(Path(root).name) if root else None
    return models.FolderInfo(
        path=path,
        ok=ok,
        problem=problem,
        root=root,
        branch=runtime.branch(root) if root else None,
        problem_kind=kind,
        hint=hint,
        subfolders=_subfolders(Path(path)),
        default_name=name,
        name_state=name_state(name, root, has_db) if name and root else None,
        provider=provider_suggestion(root if has_db else None),
        warning=runtime.outside_workspace(root or path),  # a start judges the root
        scratch=kind in ("missing", "not_repo") and _can_start_from_scratch(path),
    )


def _project_place(path: str) -> models.ProjectPlace | None:
    place = projects.place(path)
    if place is None:
        return None
    return models.ProjectPlace(id=place.id, title=projects.get(place.id).title, repo=place.repo)


def _can_start_from_scratch(path: str) -> bool:
    try:
        return scratch.check_target(path).state in scratch.CAN_START
    except runtime.LadoError:
        return False


def scratch_target(text: str, path: str | None, has_db: bool) -> models.ScratchTarget:
    """A fresh start of the name `text` in `path` (by default the name's folder in where
    clones go), as the core finds it; it changes nothing."""
    try:
        names, problem = scratch.names(text), None
    except scratch.ScratchError as refused:
        names, problem = None, str(refused)
    if path is not None:
        folder: str | None = runtime.full_path(path)
    else:
        folder = str(scratch.default_folder(names.name)) if names else None
    state, text, hint = None, None, None
    if folder:
        try:
            target = scratch.check_target(folder)
            state, text, hint = target.state, target.text, models.hint_info(target.hint)
        except runtime.FolderProblem:
            pass  # no git that runs: unknown, and `author` says why with its hint
        except runtime.LadoError as refused:  # a folder LADO or git may not read
            text = str(refused)
    return models.ScratchTarget(
        path=folder,
        name=names.name if names else None,
        title=names.title if names else None,
        problem=problem,
        state=state,
        text=text,
        author=_author(folder or str(projects.workspace())),
        name_state=(
            name_state(names.name, os.path.realpath(folder), has_db) if names and folder else None
        ),
        provider=provider_suggestion(None),  # a new folder has no last session
        warning=runtime.outside_workspace(folder) if folder else None,
        hint=hint,
    )


def _author(path: str) -> models.ScratchProblem | None:
    """Why git cannot sign a fresh start's commit at `path`; a git that does not run, or
    cannot read its config, too."""
    try:
        problem: runtime.LadoError | None = scratch.author_problem(path)
    except runtime.LadoError as refused:
        problem = refused
    if problem is None:
        return None
    return models.ScratchProblem(
        text=str(problem), hint=models.hint_info(getattr(problem, "hint", None))
    )


def provider_suggestion(root: str | None) -> models.ProviderSuggestion | None:
    """The provider a new session in `root` takes (runtime.suggested_provider; None: a
    folder with no sessions known), its CLI looked for on the server's PATH."""
    suggestion = runtime.suggested_provider(root, _installed)
    if suggestion is None:
        return None
    return models.ProviderSuggestion(name=suggestion.provider, reason=suggestion.reason)


def _installed(provider: providers.Provider) -> bool:
    """Whether the server finds the provider's CLI, as GET /api/providers does; no
    `--version`, which each folder check would wait for."""
    return shutil.which(provider.command) is not None


def _root_or_none(path: str) -> str | None:
    if not Path(path).exists():
        return None
    try:
        return runtime.repo_root(path)
    except runtime.LadoError:
        return None


def _subfolders(path: Path) -> list[str]:
    """Its folders but hidden ones, and but LADO's projects/, where no folder is a start."""
    try:
        found = [p for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except OSError:
        return []
    owned = projects.lados_folder()
    names = sorted(p.name for p in found if not owned or os.path.realpath(p) != str(owned))
    return names[:SUBFOLDERS]


def name_state(name: str, root: str, has_db: bool, project: str | None = None) -> models.NameState:
    """Who has the name `name` of a new session in `root`; with `project`, a session of the
    name that is not of that project is elsewhere too: the core resumes none such."""
    sess = state.get_session(name) if has_db else None
    if sess is None:
        return "free"
    if sess.repo != root or (project is not None and sess.project != project):
        return "taken_elsewhere"
    running = (runtime.SessionStatus.RUNNING, runtime.SessionStatus.LOOP_DOWN)
    return "running" if runtime.session_status(sess) in running else "stopped_here"


def recent_folders() -> list[models.RecentFolder]:
    """The folders of past sessions, each with its latest started session, latest first;
    none inside LADO's projects/, where a new session is refused (a session there is
    resumed from its own page)."""
    owned = projects.lados_folder()
    found: dict[str, state.Session] = {}
    for sess in state.sessions_by_start():
        if owned and Path(os.path.realpath(sess.repo)).is_relative_to(owned):
            continue
        found.setdefault(sess.repo, sess)
    return [
        models.RecentFolder(path=repo, session=models.session_info(sess))
        for repo, sess in list(found.items())[:RECENT]
    ]


def kit_infos(has_db: bool) -> list[models.KitInfo]:
    """The kit of each name the lookup takes, the same for every folder; one that does not
    load is there too, with why. Without lado.db no kit is installed (and none is made)."""
    try:
        listed = kits.available(with_installed=has_db)
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
        return list(pool.map(provider_info, registry))


def provider_info(
    provider: providers.Provider, status: doctor.ProviderStatus | None = None
) -> models.ProviderInfo:
    """The provider and its CLI as the server finds it, checked anew (`<cli> --version`)
    unless `status` is that check."""
    status = status or doctor.provider_status(provider, shutil.which)
    return models.ProviderInfo(
        name=provider.name,
        title=provider.title,
        permission_modes=list(provider.permission_modes),
        install_hint=provider.install_hint,
        installed=status.installed,
        version=status.version,
        detail=status.detail,
        tested_version=status.tested_version,
        warning=status.warning,
    )


def session_about(sess: state.Session) -> models.SessionAbout:
    """What the session's head shows besides its settings, read now: its repository's
    remote and branch, its kits as the next agent would take them, its provider's CLI."""
    remote = runtime.remote(sess.repo)
    repo = models.RepoInfo(
        path=sess.repo,
        remote=runtime.public_remote(remote) if remote else None,
        branch=runtime.branch(sess.repo),
    )
    found = state.get_project(sess.project) if sess.project else None
    return models.SessionAbout(
        repos=[repo],
        kits=[_session_kit(name) for name in sess.kits],
        provider=provider_info(providers.get(sess.provider)),
        project=models.ProjectRef(id=found.id, title=found.title) if found else None,
    )


def project_info(id: str) -> models.ProjectInfo:
    """A project with its repositories as the disk has them now; NoSuchProject else."""
    project = projects.get(id)
    where = projects.folder(id)
    return models.ProjectInfo(
        id=project.id,
        title=project.title,
        folder=str(where),
        found=where.is_dir(),
        repos=[project_repo(r) for r in projects.repositories(id)],
        variables=[
            models.ProjectVariable(name=name, value=value)
            for name, value in state.project_variables(id).items()
        ],
        secrets=project_secrets.names(id),
        running=projects.running(id),
        overrides=projects.overrides(id),
        unused=[
            models.UnusedSecret(name=name, reason=reason)
            for name, reason in project_secrets.unused(id)
        ],
    )


def project_summaries() -> list[models.ProjectSummary]:
    """Every project by id for the Projects section's list."""
    return [
        models.ProjectSummary(
            id=project.id,
            title=project.title,
            folder=str(where),
            found=found,
            repos=len(projects.repositories(project.id)) if found else 0,
            running=projects.running(project.id),
        )
        for project, where, found in projects.listed()
    ]


def project_launch(asked: str | None, asked_repo: str | None, has_db: bool) -> models.ProjectLaunch:
    """What the Project way shows: the projects by title, the project `asked` (else that of
    the latest started session in a project whose folder is found, else the first found,
    else the first), its repository `asked_repo` (else that of the project's latest started
    session still there, else the first), and what a start there takes; makes nothing."""
    listed = project_summaries() if has_db else []
    listed.sort(key=lambda p: (p.title or p.id).casefold())
    started = state.sessions_by_start() if listed else []
    found = [p.id for p in listed if p.found]
    if asked in {p.id for p in listed}:
        project = asked
    else:
        used = (s.project for s in started if s.project in found)
        project = next(used, None) or next(iter(found + [p.id for p in listed]), None)
    nothing = models.ProjectLaunch(
        projects=listed,
        project=project,
        repos=[],
        repo=None,
        root=None,
        default_name=None,
        name_state=None,
        provider=None,
        last=None,
    )
    if project is None:
        return nothing
    repos = projects.repositories(project)
    in_project = [s for s in started if s.project == project]
    by_folder = {os.path.realpath(r.path): r for r in repos}
    named = {r.name: r for r in repos}
    if asked_repo in named:
        repo = named[asked_repo]
    else:
        still_there = (by_folder.get(os.path.realpath(s.repo)) for s in in_project)
        repo = next((r for r in still_there if r), None) or next(iter(repos), None)
    if repo is None:
        return nothing
    real = os.path.realpath(repo.path)
    last = next((s for s in in_project if os.path.realpath(s.repo) == real), None)
    root = _root_or_none(str(repo.path)) or str(repo.path)
    name = runtime.project_session_name(project, repo.name)
    return nothing.model_copy(
        update={
            "repos": [project_repo(r) for r in repos],
            "repo": repo.name,
            "root": root,
            "default_name": name,
            "name_state": name_state(name, root, has_db, project=project),
            "provider": provider_suggestion(root),
            "last": models.session_info(last) if last else None,
        }
    )


def project_id(title: str | None, typed: str | None) -> models.ProjectId:
    """The id New project offers for `title`, or `typed` as the human typed it, with its
    folder and the core's refusal of it (projects.check_new); makes nothing."""
    try:
        id = typed if typed is not None else projects.suggest_id(title or "")
    except runtime.LadoError as error:  # the fresh start's: no name for a folder
        return models.ProjectId(id=None, folder=None, problem=str(error))
    try:
        projects.check_id(id)
    except projects.ProjectError as error:
        return models.ProjectId(id=id, folder=None, problem=str(error))
    try:
        projects.check_new(id)
        problem = None
    except runtime.LadoError as error:
        problem = str(error)
    return models.ProjectId(id=id, folder=str(projects.folder(id)), problem=problem)


def project_repo(repo: projects.Repository) -> models.ProjectRepo:
    return models.ProjectRepo(
        name=repo.name, path=str(repo.path), remote=repo.remote, branch=repo.branch
    )


def repo_removal(found: projects.Removal) -> models.RepoRemoval:
    return models.RepoRemoval(
        name=found.name,
        kind=found.kind,
        path=str(found.path),
        target=found.target,
        sessions=[
            models.SessionToForget(name=n, open_runs=runs, project=project)
            for n, runs, project in found.sessions
        ],
        unpushed=found.unpushed,
    )


def _session_kit(name: str) -> models.SessionKitInfo:
    try:
        found = kits.find(name)
    except kits.KitError as exc:
        return models.SessionKitInfo(
            name=name, version="", source="", valid=False, problem=str(exc)
        )
    try:
        kit = found.load()
    except kits.KitError as exc:
        return models.SessionKitInfo(
            name=name, version="", source=found.source, valid=False, problem=str(exc)
        )
    return models.SessionKitInfo(
        name=name, version=kit.version, source=kit.source, valid=True, problem=None
    )
