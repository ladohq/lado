"""runtime.start_session in a project, and the refusal of a new session without one inside
LADO's projects/ (openspec change sessions-in-projects)."""

import os
from pathlib import Path

import pytest
from agent_helpers import init_repo

from lado import projects, runtime, state


@pytest.fixture
def shop(tmp_path, monkeypatch, fake_tmux):
    """The workspace <tmp>/ws with the project shop titled Shop and its repository
    frontend; the folder of the project."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    init_repo(projects.folder("shop") / "frontend")
    return projects.folder("shop")


def _start(**kwargs) -> runtime.Started:
    return runtime.start_session(
        kwargs.pop("path", None), kwargs.pop("name", None), None, provider="claude", **kwargs
    )


def test_a_session_in_a_project_takes_its_repository_and_name(shop, fake_tmux):
    started = _start(project="shop", repo_name="frontend")
    assert started.session.name == "shop-frontend"
    stored = state.get_session("shop-frontend")
    assert (stored.repo, stored.project) == (str(shop / "frontend"), "shop")
    [(kind, session, _window, cwd, *_)] = fake_tmux
    assert (kind, session, cwd) == ("new_session", "shop-frontend", str(shop / "frontend"))


def test_a_given_name_is_kept(shop):
    assert _start(project="shop", repo_name="frontend", name="Fix Login").session.name == (
        "fix-login"
    )
    assert state.get_session("fix-login").project == "shop"


def test_an_unknown_project(shop):
    with pytest.raises(projects.NoSuchProject, match='^unknown project "acme"$'):
        _start(project="acme", repo_name="frontend")
    assert state.list_sessions() == []


def test_an_unknown_repository_names_those_there_are(shop):
    init_repo(shop / "backend")
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="shop", repo_name="web")
    assert (
        str(refused.value)
        == "project shop has no repository web; its repositories: backend, frontend"
    )
    assert state.list_sessions() == []


@pytest.mark.parametrize("entry", ["notes", ".hidden"])
def test_what_is_no_repository_is_refused_as_unknown(shop, entry):
    (shop / entry).mkdir()
    with pytest.raises(
        runtime.LadoError, match=f"has no repository {entry}; its repositories: frontend$"
    ):
        _start(project="shop", repo_name=entry)


def test_a_link_is_named_as_one(shop, tmp_path):
    elsewhere = init_repo(tmp_path / "elsewhere" / "docs")
    (shop / "docs").symlink_to(elsewhere)
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="shop", repo_name="docs")
    assert str(refused.value) == (
        f"docs in project shop is a link to {elsewhere}: clone it into {shop} instead"
    )
    assert state.list_sessions() == []


def test_a_project_without_repositories(shop):
    projects.create("acme", None)
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="acme", repo_name="crm")
    assert str(refused.value) == (
        "project acme has no repositories yet: add one with lado project repo add acme "
        "<git-url> or --new <name>"
    )


def test_a_session_of_the_project_is_resumed_with_it(shop):
    _start(project="shop", repo_name="frontend")
    runtime.stop_session("shop-frontend")
    started = runtime.start_session(
        None, None, None, provider="codex", project="shop", repo_name="frontend"
    )
    assert started.resumed
    assert state.get_session("shop-frontend").project == "shop"


def test_a_resume_without_the_project_keeps_it(shop):
    _start(project="shop", repo_name="frontend")
    runtime.stop_session("shop-frontend")
    started = _start(path=str(shop / "frontend"), name="shop-frontend", resume=True)
    assert started.resumed  # not refused: it is no new session
    assert state.get_session("shop-frontend").project == "shop"


@pytest.mark.parametrize(
    ("old_project", "said"),
    [("acme", "is in project acme"), (None, "is not in a project")],
)
def test_a_sessions_project_never_changes(shop, tmp_path, old_project, said):
    if old_project:
        projects.create("acme", None)
        init_repo(projects.folder("acme") / "frontend")
        _start(project="acme", repo_name="frontend", name="site")
    else:
        _start(path=str(init_repo(tmp_path / "site")), name="site")
    runtime.stop_session("site")
    with pytest.raises(runtime.LadoError) as refused:
        _start(project="shop", repo_name="frontend", name="site")
    assert str(refused.value) == (
        f'session "site" {said}; a session\'s project never changes: give another name with --name'
    )
    assert state.get_session("site").project == old_project


def test_a_new_session_without_the_project_is_refused_in_its_repository(shop):
    with pytest.raises(runtime.FolderProblem) as refused:
        _start(path=str(shop / "frontend"))
    assert refused.value.kind == "in_project"
    assert str(refused.value) == (
        f"{shop / 'frontend'} belongs to the project Shop: start a session in the project"
    )
    assert refused.value.hint.command == "lado start --project shop --repo frontend"
    assert state.list_sessions() == []


def test_a_folder_without_git_in_a_project_is_the_projects_refusal(shop):
    (shop / "notes").mkdir()
    with pytest.raises(runtime.FolderProblem) as refused:
        _start(path=str(shop / "notes"))
    assert refused.value.kind == "in_project"  # not not_repo's `git init`


def test_a_missing_folder_in_a_project_is_the_projects_refusal(shop):
    with pytest.raises(runtime.FolderProblem) as refused:
        _start(path=str(shop / "gone"))
    assert refused.value.kind == "in_project"


def test_a_session_from_before_projects_resumes_there(shop):
    """A session started under projects/ before schema 33 has no project and is resumed."""
    repo = str(shop / "frontend")
    state.add_session(state.Session("site", repo, None, provider="claude"))
    state.stop_session("site")
    started = _start(path=repo, name="site")
    assert started.resumed
    assert state.get_session("site").project is None


def test_nothing_is_refused_in_the_humans_own_projects_folder(tmp_path, monkeypatch, fake_tmux):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    app = init_repo(tmp_path / "ws" / "projects" / "app")
    assert _start(path=str(app)).session.name == "app"
    assert state.get_session("app").project is None


def test_a_link_from_outside_is_refused(shop, tmp_path):
    link = Path(tmp_path / "front")
    os.symlink(shop / "frontend", link)
    with pytest.raises(runtime.FolderProblem, match="belongs to the project Shop"):
        _start(path=str(link))
