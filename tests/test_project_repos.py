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
