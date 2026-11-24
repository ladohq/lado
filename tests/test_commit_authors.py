"""LADO's commit author and a project's (lado.commit_authors): the checks, the levels, git's
own author and the author in effect, held against git's own answer under the laid entries."""

import os
import subprocess

import pytest

from lado import commit_authors, git_servers, state
from lado.commit_authors import Author, InEffect

ANN = Author("Ann Lee", "ann@example.com")
IVAN = Author("Ivan Petrov", "ivan.petrov@corp.ru")
SHOP = Author("Shop Bot", "bot@shop.example")


def _fake_git(tmp_path, version: str) -> dict[str, str]:
    folder = tmp_path / "old-git"
    folder.mkdir(exist_ok=True)
    git = folder / "git"
    git.write_text(f"#!/bin/sh\necho 'git version {version}'\n")
    git.chmod(0o755)
    return {"PATH": f"{folder}:{os.environ['PATH']}"}


def _server(id: str, host: str, author: Author | None = None) -> state.GitServer:
    state.save_git_server(id, f"https://{host}", host, "gitlab", "ivan")
    if author:
        state.set_git_server_author(id, author.name, author.email)
    return state.git_server_by_host(host)


def _project(id: str = "shop", author: Author | None = None) -> None:
    with state.creating_project(id, None):
        pass
    if author:
        state.set_project_author(id, author.name, author.email)


def _repo(tmp_path, *remotes: str, name: str = "repo"):
    path = tmp_path / name
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for n, url in enumerate(remotes):
        subprocess.run(["git", "-C", str(path), "remote", "add", f"r{n}", url], check=True)
    return path


def test_text_of_an_author():
    assert commit_authors.text(ANN) == "Ann Lee <ann@example.com>"


def test_check_is_the_servers_check():
    assert git_servers.check_author(" Ann Lee", "ann@example.com ") == (
        "Ann Lee",
        "ann@example.com",
    )
    with pytest.raises(git_servers.Refused) as raised:
        commit_authors.check("Ann Lee", "ann")
    assert (str(raised.value), raised.value.field) == ("not an email address: name@host", "email")


def test_lado_author_set_read_and_cleared(lado_home):
    assert commit_authors.lado() is None
    assert commit_authors.set_lado(" Ann Lee ", "ann@example.com ") == ANN
    assert commit_authors.lado() == ANN
    assert commit_authors.clear_lado() is True
    assert commit_authors.lado() is None
    assert commit_authors.clear_lado() is False


def test_a_refused_lado_author_is_not_saved(lado_home):
    with pytest.raises(git_servers.Refused):
        commit_authors.set_lado("Ann <Lee>", "ann@example.com")
    assert commit_authors.lado() is None


def test_setting_an_author_needs_git_2_31(lado_home, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", _fake_git(tmp_path, "2.30.2")["PATH"])
    with pytest.raises(git_servers.Refused) as raised:
        commit_authors.set_lado("Ann Lee", "ann@example.com")
    assert str(raised.value) == (
        "git 2.30.2 is older than 2.31, which LADO's commit author needs; update git"
    )
    _project()
    with pytest.raises(git_servers.Refused) as raised:
        commit_authors.set_project("shop", "Shop Bot", "bot@shop.example")
    assert str(raised.value) == (
        "git 2.30.2 is older than 2.31, which a project's commit author needs; update git"
    )
    assert commit_authors.lado() is None
    assert commit_authors.project("shop") is None


def test_a_projects_author_set_read_and_cleared(lado_home):
    _project()
    assert commit_authors.project("shop") is None
    assert commit_authors.set_project("shop", "Shop Bot", "bot@shop.example") == SHOP
    assert commit_authors.project("shop") == SHOP
    assert commit_authors.clear_project("shop") is True
    assert commit_authors.project("shop") is None
    assert commit_authors.project("nope") is None
    assert commit_authors.set_project("nope", "Shop Bot", "bot@shop.example") is None
    assert commit_authors.clear_project("nope") is False


def test_entries_of_an_author():
    assert commit_authors.entries(ANN) == [
        ("user.name", "Ann Lee"),
        ("user.email", "ann@example.com"),
    ]


def test_git_own_reads_the_global_config(git_config, tmp_path):
    assert commit_authors.git_own(str(tmp_path / "new" / "folder")) == Author(
        "LADO test", "test@lado.invalid"
    )
    git_config.write_text("[user]\n\tname = LADO test\n")
    assert commit_authors.git_own(str(tmp_path)) is None


def test_git_own_reads_a_repositorys_own(git_config, tmp_path):
    git_config.write_text("")
    repo = _repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Alex Work"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "alex@work.example"], check=True
    )
    assert commit_authors.git_own(str(repo)) == Author("Alex Work", "alex@work.example")
    assert commit_authors.git_own(str(tmp_path)) is None


def test_git_own_leaves_out_ladOs_entries_of_an_agents_launch(git_config, tmp_path, monkeypatch):
    """`lado` run inside an agent has the launch's entries: they are not git's own."""
    git_config.write_text("")
    entries = git_servers.variables({}, [], lado=ANN)
    for name, value in entries.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("LADO_LAUNCH_VARS", ",".join(entries))
    assert commit_authors.git_own(str(tmp_path)) is None


@pytest.fixture
def nobody(git_config, lado_home):
    git_config.write_text("")
    return git_config


def test_in_effect_nobody(nobody, tmp_path):
    assert commit_authors.in_effect(str(tmp_path)) == InEffect(None, "none")


def test_in_effect_gits_own(git_config, lado_home, tmp_path):
    assert commit_authors.in_effect(str(tmp_path)) == InEffect(
        Author("LADO test", "test@lado.invalid"), "git"
    )


def test_in_effect_lado_over_git_and_the_repositorys_own(git_config, lado_home, tmp_path):
    repo = _repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Alex Work"], check=True)
    state.set_commit_author(ANN.name, ANN.email)
    assert commit_authors.in_effect(str(repo)) == InEffect(ANN, "lado")
    assert commit_authors.in_effect(str(tmp_path / "new")) == InEffect(ANN, "lado")


@pytest.mark.parametrize(
    "remote",
    [
        "https://git.test:8443/team/app.git",
        "https://ivan@git.test:8443/team/app.git",
    ],
)
def test_in_effect_a_servers_over_ladOs(nobody, tmp_path, remote):
    state.set_commit_author(ANN.name, ANN.email)
    _server("s1", "git.test:8443", IVAN)
    assert commit_authors.in_effect(str(_repo(tmp_path, remote))) == InEffect(IVAN, "server")


def test_in_effect_a_servers_by_its_ssh_address(nobody, tmp_path):
    _server("s1", "gitlab.corp.ru", IVAN)
    repo = _repo(tmp_path, "git@gitlab.corp.ru:team/app.git")
    assert commit_authors.in_effect(str(repo)) == InEffect(IVAN, "server")


def test_in_effect_a_server_without_an_author_is_passed(nobody, tmp_path):
    state.set_commit_author(ANN.name, ANN.email)
    _server("s1", "gitlab.corp.ru")
    repo = _repo(tmp_path, "https://gitlab.corp.ru/team/app.git", "https://other.example/x.git")
    assert commit_authors.in_effect(str(repo)) == InEffect(ANN, "lado")


def test_in_effect_of_two_servers_the_later_by_host(nobody, tmp_path):
    _server("s1", "a.example", IVAN)
    _server("s2", "b.example", SHOP)
    repo = _repo(tmp_path, "https://b.example/x.git", "https://a.example/x.git")
    assert commit_authors.in_effect(str(repo)) == InEffect(SHOP, "server")


def test_in_effect_the_projects_over_all(nobody, tmp_path):
    state.set_commit_author(ANN.name, ANN.email)
    _server("s1", "git.test:8443", IVAN)
    _project("shop", SHOP)
    repo = _repo(tmp_path, "https://git.test:8443/team/app.git")
    assert commit_authors.in_effect(str(repo), "shop") == InEffect(SHOP, "project")
    _project("plain")
    assert commit_authors.in_effect(str(repo), "plain") == InEffect(IVAN, "server")


def test_author_variables_names_the_four_only():
    env = {"GIT_AUTHOR_EMAIL": "x", "GIT_COMMITTER_NAME": "y", "GIT_DIR": "z", "HOME": "/h"}
    assert commit_authors.author_variables(env) == ["GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME"]
    assert commit_authors.author_variables({}) == []


def _git_answer(repo, laid: dict[str, str], key: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", key],
        env={**os.environ, **laid},
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


@pytest.mark.parametrize("lado", [None, ANN])
@pytest.mark.parametrize("server", [None, IVAN])
@pytest.mark.parametrize("project", [None, SHOP])
@pytest.mark.parametrize("own", [False, True])
def test_in_effect_agrees_with_git_under_the_laid_entries(
    git_config, lado_home, tmp_path, lado, server, project, own
):
    """Every combination of the levels: what the page says is what git takes."""
    if not own:
        git_config.write_text("")
    if lado:
        state.set_commit_author(lado.name, lado.email)
    servers = [_server("s1", "git.test:8443", server)]
    _project("shop", project)
    repo = _repo(tmp_path, "https://git.test:8443/team/app.git")
    found = commit_authors.in_effect(str(repo), "shop")
    authors = git_servers.author_files(tmp_path / "authors", servers)
    laid = git_servers.variables(
        {},
        servers,
        authors=authors,
        lado=commit_authors.lado(),
        project=commit_authors.project("shop"),
    )
    name, email = _git_answer(repo, laid, "user.name"), _git_answer(repo, laid, "user.email")
    assert (found.author or Author("", "")) == Author(name, email)
