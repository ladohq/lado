"""lado.clone: a repository from its git URL (openspec change clone-from-url)."""

import os
import subprocess
from pathlib import Path

import pytest

from lado import clone, runtime


@pytest.mark.parametrize(
    "source",
    [
        "https://github.com/ladohq/lado",
        "http://git.example.com/a/b.git",
        "ssh://git@host:2222/a/b.git",
        "git://host/a/b",
        "file:///srv/app.git",
        "git@github.com:ladohq/lado.git",
    ],
)
def test_a_git_url(source):
    assert clone.is_url(source)


@pytest.mark.parametrize(
    "source", ["~/projects/app", "app", "/srv/app.git", "host:path", "C:/x", ".", ""]
)
def test_a_folder(source):
    assert not clone.is_url(source)


def test_default_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert clone.default_folder("https://github.com/ladohq/marketplace.git/") == (
        tmp_path / "lado" / "marketplace"
    )
    assert clone.default_folder("git@github.com:ladohq/lado.git") == tmp_path / "lado" / "lado"
    assert clone.default_folder("file:///srv/app.git") == tmp_path / "lado" / "app"


def test_address_parts():
    ssh = clone.Address.parse("ssh://deploy@Git.Example.com:2222/~/team/app.git")
    assert (ssh.scheme, ssh.user, ssh.host, ssh.port) == ("ssh", "deploy", "git.example.com", 2222)
    assert (ssh.repo_name, ssh.owner) == ("app", "team")
    scp = clone.Address.parse("git@github.com:ladohq/lado.git")
    assert (scp.scheme, scp.user, scp.host, scp.port) == ("ssh", "git", "github.com", None)
    assert (scp.repo_name, scp.owner) == ("lado", "ladohq")
    https = clone.Address.parse("https://ghp_x@github.com/acme/app")
    assert (https.user, https.host, https.repo_name, https.owner) == (
        "ghp_x",
        "github.com",
        "app",
        "acme",
    )
    assert clone.Address.parse("https://host/app").owner is None


SAME = [
    ("git@github.com:ladohq/lado.git", "https://github.com/ladohq/lado"),
    ("https://github.com/ladohq/lado.git", "ssh://git@github.com:22/ladohq/lado"),
    ("https://GitHub.com/ladohq/lado/", "git://github.com/ladohq/lado.git"),
    ("ssh://git@host/~/team/app.git", "git@host:team/app"),
    ("https://user:pw@host/a/b", "https://host/a/b"),
]
OTHER = [
    ("git@github.com:acme/app.git", "git@github.com:ladohq/app.git"),
    ("https://github.com/ladohq/lado", "https://gitlab.com/ladohq/lado"),
    ("https://github.com/ladohq/lado", "file:///srv/lado"),
]


@pytest.mark.parametrize(("one", "other"), SAME)
def test_the_same_repository_over_another_protocol(one, other):
    assert clone.Address.parse(one).same_repo(clone.Address.parse(other))
    assert clone.Address.parse(other).same_repo(clone.Address.parse(one))


@pytest.mark.parametrize(("one", "other"), OTHER)
def test_another_repository(one, other):
    assert not clone.Address.parse(one).same_repo(clone.Address.parse(other))


def test_local_repositories_compare_by_real_path(tmp_path):
    (tmp_path / "app.git").mkdir()
    (tmp_path / "link.git").symlink_to(tmp_path / "app.git")
    url = clone.Address.parse(f"file://{tmp_path}/app.git")
    assert url.same_repo(clone.Address.parse(f"file://{tmp_path}/link.git"))
    assert url.same_repo(clone.Address.parse(str(tmp_path / "link.git")))
    assert not url.same_repo(clone.Address.parse(f"file://{tmp_path}/other.git"))
