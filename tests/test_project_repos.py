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
