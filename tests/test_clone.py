"""lado.clone: a repository from its git URL (openspec change clone-from-url)."""

import os
import subprocess
from pathlib import Path

import pytest

from agent_helpers import init_repo

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


def _with_origin(path: Path, origin: str | None) -> Path:
    init_repo(path)
    if origin:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin], check=True)
    return path


def _listing(path: Path) -> list[tuple[str, int]]:
    return sorted((str(p), p.stat().st_mtime_ns) for p in [path, *path.rglob("*")])


def test_a_new_folder(tmp_path):
    target = clone.check_target("https://github.com/ladohq/lado", str(tmp_path / "lado"))
    assert (target.state, target.text) == ("new", "a new folder")
    assert not (tmp_path / "lado").exists()


def test_an_empty_folder(tmp_path):
    (tmp_path / "lado").mkdir()
    target = clone.check_target("https://github.com/ladohq/lado", str(tmp_path / "lado"))
    assert (target.state, target.text) == ("empty", "an empty folder")


def test_a_clone_of_the_same_repository(tmp_path):
    folder = _with_origin(tmp_path / "lado", "git@github.com:ladohq/lado.git")
    before = _listing(folder)
    target = clone.check_target("https://github.com/ladohq/lado", str(folder))
    assert target.state == "same_repo"
    assert target.text == (
        f"{folder} is already a clone of this repository "
        "(origin git@github.com:ladohq/lado.git), on branch main"
    )
    assert (target.origin, target.branch) == ("git@github.com:ladohq/lado.git", "main")
    assert _listing(folder) == before


def test_another_repository_with_the_same_name(tmp_path):
    folder = _with_origin(tmp_path / "app", "git@github.com:acme/app.git")
    before = _listing(folder)
    target = clone.check_target("git@github.com:ladohq/app.git", str(folder))
    assert target.state == "other_repo"
    assert target.suggestion == str(tmp_path / "ladohq-app")
    assert target.text == (
        f"{folder} is a clone of another repository (origin git@github.com:acme/app.git): "
        f"choose another folder, e.g. {tmp_path / 'ladohq-app'}"
    )
    assert _listing(folder) == before


def test_no_suggestion_when_that_folder_is_taken_or_there_is_no_owner(tmp_path):
    folder = _with_origin(tmp_path / "app", "https://ghp_secret@github.com/acme/app")
    (tmp_path / "ladohq-app").mkdir()
    target = clone.check_target("git@github.com:ladohq/app.git", str(folder))
    assert (target.state, target.suggestion) == ("other_repo", None)
    assert target.text.endswith("(origin https://github.com/acme/app): choose another folder")
    assert "ghp_secret" not in target.text + str(target.origin)
    target = clone.check_target("https://host/app", str(folder))
    assert (target.state, target.suggestion) == ("other_repo", None)


def test_a_folder_with_other_files(tmp_path):
    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "notes.txt").write_text("mine")
    before = _listing(folder)
    target = clone.check_target("https://github.com/acme/app", str(folder))
    assert target.state == "not_empty"
    assert target.text == (
        f"{folder} is not empty and is not a clone of https://github.com/acme/app: "
        "choose another folder"
    )
    assert _listing(folder) == before


def test_a_subfolder_of_a_repository_or_one_without_origin_is_not_empty(tmp_path):
    repo = _with_origin(tmp_path / "app", "https://github.com/acme/app")
    (repo / "sub").mkdir()
    (repo / "sub" / "x").write_text("x")
    assert clone.check_target("https://github.com/acme/app", str(repo / "sub")).state == (
        "not_empty"
    )
    bare = _with_origin(tmp_path / "bare", None)
    assert clone.check_target("https://github.com/acme/bare", str(bare)).state == "not_empty"


def test_a_file(tmp_path):
    (tmp_path / "app").write_text("x")
    target = clone.check_target("https://github.com/acme/app", str(tmp_path / "app"))
    assert (target.state, target.text) == (
        "not_folder",
        f"{tmp_path / 'app'} is a file, not a folder",
    )
