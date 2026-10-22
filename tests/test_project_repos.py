"""lado.projects: a project's repositories added and removed (openspec change
project-repositories)."""

import os
import subprocess
import threading
from pathlib import Path

import pytest
from agent_helpers import bare_remote, fake_git, fake_git_calls, init_repo

from lado import projects, runtime, scratch, state


@pytest.fixture
def home(home_workspace, tmp_path, monkeypatch):
    """HOME in tmp_path and no LADO_REPOS: the workspace is <tmp>/workspace."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LADO_REPOS", raising=False)
    return tmp_path


@pytest.fixture
def shop(home, git_config):
    """The project shop titled Shop with an empty folder; its folder."""
    projects.create("shop", "Shop")
    return projects.folder("shop")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return done.stdout


# The name rule and the add target

BAD_NAME = (
    "the repository name {} is not valid: Latin letters, digits, ., _ and -, not starting "
    "with . or -, at most 100 characters"
)


@pytest.mark.parametrize("name", ["frontend", "Web.App_2", "1", "_x", "a-b", "x" * 100])
def test_a_good_name(name):
    projects.check_repo_name(name)


@pytest.mark.parametrize(
    "name", [".hidden", "-x", "a/b", "..", ".", "сайт", "a b", "x" * 101, "", "a\nb"]
)
def test_a_bad_name(name):
    with pytest.raises(projects.ProjectError) as refused:
        projects.check_repo_name(name)
    assert str(refused.value) == BAD_NAME.format(name)


def test_the_target_of_an_add(shop):
    assert projects.new_repo_folder("shop", "frontend") == shop / "frontend"
    assert list(shop.iterdir()) == []  # nothing made


@pytest.mark.parametrize("kind", ["folder", "file", "link", "dangling"])
def test_a_taken_name(shop, home, kind):
    entry = shop / "frontend"
    if kind == "folder":
        entry.mkdir()
    elif kind == "file":
        entry.write_text("x")
    elif kind == "link":
        entry.symlink_to(home)
    else:
        entry.symlink_to(home / "gone")
    with pytest.raises(projects.ProjectError) as refused:
        projects.new_repo_folder("shop", "frontend")
    assert str(refused.value) == (
        f"{entry} already exists in project shop: choose another name with --name"
    )


def test_a_taken_name_in_another_case_where_the_disk_ignores_case(shop):
    (shop / "frontend").mkdir()
    if not (shop / "FRONTEND").exists():
        pytest.skip("this disk tells the case apart")
    with pytest.raises(projects.ProjectError, match="already exists in project shop"):
        projects.new_repo_folder("shop", "Frontend")


def test_the_target_of_an_unknown_project(home):
    with pytest.raises(projects.NoSuchProject, match='unknown project "acme"'):
        projects.new_repo_folder("acme", "crm")


def test_the_target_when_the_projects_folder_is_gone(shop):
    shop.rmdir()
    with pytest.raises(projects.ProjectError) as refused:
        projects.new_repo_folder("shop", "frontend")
    assert str(refused.value) == f"the folder of project shop is not found: {shop}"
    assert not shop.exists()


def test_the_name_is_checked_before_it_is_looked_for(shop):
    with pytest.raises(projects.ProjectError, match="is not valid"):
        projects.new_repo_folder("shop", "../acme")


# Adding: a clone or a fresh start into the project's folder


def test_add_clone_lists_the_repository(shop, tmp_path):
    url = bare_remote(tmp_path)
    seen = []
    added = projects.add_clone("shop", url, None, "develop", seen.append)
    assert added == projects.Repository("app", shop / "app", "develop", url)
    assert projects.repositories("shop") == [added]
    assert seen  # git's progress reached the caller


def test_add_clone_under_another_name(shop, tmp_path):
    url = bare_remote(tmp_path)
    assert projects.add_clone("shop", url, "site").path == shop / "site"


def test_add_clone_refuses_a_url_that_gives_no_name(shop):
    with pytest.raises(runtime.LadoError, match="names no repository"):
        projects.add_clone("shop", "https://github.com/", None)
    with pytest.raises(projects.ProjectError, match="is not valid"):
        projects.add_clone("shop", "https://github.com/shop/сайт", None)
    assert list(shop.iterdir()) == []


def test_add_clone_refuses_a_taken_name_before_git(shop, tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "ok").items():
        monkeypatch.setenv(key, value)
    (shop / "web").mkdir()
    with pytest.raises(projects.ProjectError, match="already exists in project shop"):
        projects.add_clone("shop", "https://github.com/shop/web", None)
    assert fake_git_calls(tmp_path / "fake") == []


def test_a_cancelled_add_clone_lists_nothing(shop, tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "slow").items():
        monkeypatch.setenv(key, value)
    cancelled = threading.Event()
    with pytest.raises(runtime.LadoError, match="was cancelled"):
        projects.add_clone(
            "shop", "https://github.com/shop/web", None, None, lambda _: cancelled.set(), cancelled
        )
    assert list(shop.iterdir()) == [] and projects.repositories("shop") == []


def test_add_new_makes_a_repository_with_an_empty_commit(shop):
    added = projects.add_new("shop", "site")
    assert (added.name, added.path, added.remote) == ("site", shop / "site", None)
    assert projects.repositories("shop") == [added]
    assert _git(shop / "site", "log", "--format=%s").split() == scratch.FIRST_COMMIT.split()


def test_add_new_refuses_a_taken_or_bad_name_and_an_unknown_project(shop):
    (shop / "site").mkdir()
    with pytest.raises(projects.ProjectError, match="already exists"):
        projects.add_new("shop", "site")
    with pytest.raises(projects.ProjectError, match="is not valid"):
        projects.add_new("shop", ".hidden")
    with pytest.raises(projects.NoSuchProject):
        projects.add_new("acme", "site")
    assert [p.name for p in shop.iterdir()] == ["site"]


# Removing


@pytest.fixture
def pushed(shop, home):
    """shop holding frontend and backend, each pushed to a bare remote and clean."""
    for name in ("frontend", "backend"):
        remote = home / f"{name}.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
        repo = init_repo(shop / name)
        _git(repo, "remote", "add", "origin", str(remote))
        _git(repo, "push", "-q", "-u", "origin", "main")
    return shop


def _session(name: str, repo: Path, project: str | None, stopped: bool = True) -> None:
    state.add_session(state.Session(name, str(repo), None, provider="claude", project=project))
    if stopped:
        state.stop_session(name)


def test_the_removal_of_a_clean_repository(pushed):
    assert projects.removal("shop", "frontend") == projects.Removal(
        "frontend", "repository", pushed / "frontend", None, [], []
    )


def test_the_removal_shows_its_unpushed_work_and_its_workers(pushed):
    repo = pushed / "frontend"
    (repo / "new.txt").write_text("x")
    tree = repo / ".lado" / "worktrees" / "shop-frontend" / "dev"
    _git(repo, "worktree", "add", "-q", str(tree), "-b", "lado/shop-frontend/dev")
    (tree / "work.txt").write_text("x")
    (pushed / "backend" / "other.txt").write_text("x")  # another repository's: not shown
    assert projects.removal("shop", "frontend").unpushed == [
        "frontend: uncommitted changes; branch lado/shop-frontend/dev not pushed",
        "frontend (worktree frontend/.lado/worktrees/shop-frontend/dev): uncommitted changes",
    ]


def test_the_removal_of_a_link(shop, home):
    elsewhere = init_repo(home / "elsewhere" / "docs")
    (shop / "docs").symlink_to(elsewhere)
    (elsewhere / "work.txt").write_text("x")
    _session("docs", elsewhere, None, stopped=False)  # the link's target is not the project's
    assert projects.removal("shop", "docs") == projects.Removal(
        "docs", "link", shop / "docs", str(elsewhere), [], []
    )


@pytest.mark.parametrize("kind", ["folder", "file", "nested"])
def test_what_is_no_repository_is_not_removed(shop, kind):
    entry = shop / "notes"
    if kind == "folder":
        entry.mkdir()
    elif kind == "file":
        entry.write_text("x")
    else:  # a folder of the project folder made a repository: no root of its own
        shop.rmdir()
        init_repo(shop)
        entry.mkdir()
        (entry / "x.txt").write_text("x")
    with pytest.raises(projects.ProjectError) as refused:
        projects.remove_repo("shop", "notes", yes=True)
    assert str(refused.value) == (
        "notes in project shop is not a repository: LADO removes only repositories and links"
    )
    assert os.path.lexists(shop / "notes")


def test_an_unknown_name_names_the_repositories(pushed):
    for name in ("web", "..", "frontend/src", ".git", ""):
        with pytest.raises(projects.NoSuchRepository) as refused:
            projects.removal("shop", name)
        assert str(refused.value) == (
            f"project shop has no repository {name}; its repositories: backend, frontend"
        )


def test_an_unknown_name_in_a_project_without_repositories(shop):
    with pytest.raises(projects.NoSuchRepository) as refused:
        projects.removal("shop", "web")
    assert str(refused.value) == (
        "project shop has no repositories yet: add one with lado project repo add shop "
        "<git-url> or --new <name>"
    )


def test_the_removal_of_an_unknown_project(home):
    with pytest.raises(projects.NoSuchProject):
        projects.removal("acme", "crm")


def test_a_session_working_in_the_repository_refuses(pushed):
    _session("shop-frontend", pushed / "frontend", "shop", stopped=False)
    _session("old", pushed / "frontend" / "src", None, stopped=False)  # by path, no project
    _session("shop-backend", pushed / "backend", "shop", stopped=False)  # another one: no matter
    for yes in (False, True):
        with pytest.raises(projects.ProjectError) as refused:
            projects.remove_repo("shop", "frontend", yes=yes)
        assert str(refused.value) == (
            "repository frontend of project shop has sessions not stopped: old, shop-frontend; "
            "stop them first with lado stop <name>"
        )
    assert (pushed / "frontend").is_dir()


def test_the_stopped_sessions_of_the_project_there_are_forgotten(pushed):
    _session("shop-frontend", pushed / "frontend", "shop")
    _session("fix-login", pushed / "frontend", "shop")
    _session("shop-backend", pushed / "backend", "shop")
    _session("old", pushed / "frontend", None)  # no project: the path is no way to learn one
    run = state.Run("shop-frontend", "f/x", "feature", "{}", {}, "do x", "design", "/w", "b")
    state.add_run(run, [], None)
    assert projects.removal("shop", "frontend").sessions == [
        ("fix-login", 0),
        ("shop-frontend", 1),
    ]


def test_remove_without_yes_changes_nothing(pushed):
    _session("shop-frontend", pushed / "frontend", "shop")
    with pytest.raises(projects.ProjectError) as refused:
        projects.remove_repo("shop", "frontend", yes=False)
    assert str(refused.value) == (
        f"removing repository frontend of project shop deletes its folder {pushed / 'frontend'} "
        "with everything in it and forgets its 1 session; run again with --yes"
    )
    assert (pushed / "frontend").is_dir() and state.get_session("shop-frontend")


def test_remove_without_yes_and_without_sessions(pushed):
    with pytest.raises(projects.ProjectError) as refused:
        projects.remove_repo("shop", "frontend", yes=False)
    assert str(refused.value) == (
        f"removing repository frontend of project shop deletes its folder {pushed / 'frontend'} "
        "with everything in it; run again with --yes"
    )


def test_remove_with_yes_removes_the_folder_then_forgets_its_sessions(pushed, home):
    _session("shop-frontend", pushed / "frontend", "shop")
    _session("shop-backend", pushed / "backend", "shop")
    (home / "beside.txt").write_text("mine")
    removed = projects.remove_repo("shop", "frontend", yes=True)
    assert (removed.kind, removed.sessions) == ("repository", [("shop-frontend", 0)])
    assert not os.path.lexists(pushed / "frontend")
    assert [s.name for s in state.list_sessions()] == ["shop-backend"]
    assert [r.name for r in projects.repositories("shop")] == ["backend"]
    assert state.get_project("shop") and (home / "frontend.git").is_dir()
    assert (home / "beside.txt").read_text() == "mine"


def test_a_link_inside_the_repository_is_removed_as_a_link(pushed, home):
    outside = home / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("mine")
    (pushed / "frontend" / "out").symlink_to(outside)
    projects.remove_repo("shop", "frontend", yes=True)
    assert (outside / "keep.txt").read_text() == "mine"


def test_a_link_loses_the_link_only(shop, home):
    elsewhere = init_repo(home / "elsewhere" / "docs")
    (elsewhere / "work.txt").write_text("mine")
    (shop / "docs").symlink_to(elsewhere)
    with pytest.raises(projects.ProjectError) as refused:
        projects.remove_repo("shop", "docs", yes=False)
    assert str(refused.value) == (
        f"removing docs of project shop deletes the link only, not its target {elsewhere}; "
        "run again with --yes"
    )
    assert projects.remove_repo("shop", "docs", yes=True).kind == "link"
    assert not os.path.lexists(shop / "docs")
    assert (elsewhere / "work.txt").read_text() == "mine"


def test_a_dangling_link_is_removed_too(shop, home):
    (shop / "docs").symlink_to(home / "gone")
    assert projects.remove_repo("shop", "docs", yes=True).target == str(home / "gone")
    assert not os.path.lexists(shop / "docs")


def test_a_project_folder_that_is_a_link_elsewhere_is_refused(home, git_config):
    projects.create("shop", None)
    elsewhere = home / "elsewhere" / "shop"
    elsewhere.parent.mkdir()
    projects.folder("shop").rename(elsewhere)
    projects.folder("shop").symlink_to(elsewhere)
    init_repo(elsewhere / "frontend")
    with pytest.raises(projects.ProjectError) as refused:
        projects.remove_repo("shop", "frontend", yes=True)
    assert str(refused.value) == (
        f"{projects.folder('shop') / 'frontend'} is not in {projects.projects_folder()}: LADO "
        "removes nothing outside it"
    )
    assert (elsewhere / "frontend").is_dir()


def test_a_folder_not_removed_whole_keeps_the_sessions(pushed, monkeypatch):
    _session("shop-frontend", pushed / "frontend", "shop")

    def fail(path, *args, **kwargs):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(projects.shutil, "rmtree", fail)
    with pytest.raises(projects.ProjectError) as refused:
        projects.remove_repo("shop", "frontend", yes=True)
    assert str(refused.value).startswith(f"could not remove {pushed / 'frontend'} whole: ")
    assert str(refused.value).endswith("; its sessions stay")
    assert state.get_session("shop-frontend")


def test_a_session_not_forgotten_is_named(pushed, monkeypatch):
    _session("shop-frontend", pushed / "frontend", "shop")

    def fail(name, force=False):
        raise runtime.LadoError("the disk is gone")

    monkeypatch.setattr(runtime, "forget_session", fail)
    with pytest.raises(projects.ProjectError) as refused:
        projects.remove_repo("shop", "frontend", yes=True)
    assert str(refused.value) == (
        "the repository is removed, but session shop-frontend could not be forgotten: the disk "
        "is gone; forget it with lado forget shop-frontend --force"
    )
    assert not os.path.lexists(pushed / "frontend")
