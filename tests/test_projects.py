"""lado.projects: the workspace and projects in it (openspec change projects-in-core)."""

from pathlib import Path

import pytest

from lado import projects


@pytest.fixture
def home(tmp_path, monkeypatch):
    """HOME in tmp_path and no LADO_REPOS: the workspace is <tmp>/workspace."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LADO_REPOS", raising=False)
    return tmp_path


def test_the_workspace_is_lado_repos_when_absolute(home, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", "~/code")
    assert projects.workspace() == home / "code"
    assert projects.workspace_source() == "LADO_REPOS"
    monkeypatch.setenv("LADO_REPOS", "/srv/repos")
    assert projects.workspace() == Path("/srv/repos")


@pytest.mark.parametrize("value", [None, "", "code", "./code"])
def test_else_the_workspace_is_home_workspace(home, monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("LADO_REPOS", value)
    assert projects.workspace() == home / "workspace"
    assert projects.workspace_source() == ("ignored" if value else "default")
    assert not (home / "workspace").exists()  # never made by asking
