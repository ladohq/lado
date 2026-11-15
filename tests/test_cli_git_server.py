"""`lado git-server add|list|remove`: the output, the exit codes and the token (lado.cli,
lado.git_servers), against the fake API of tests/fake_git_api.py over plain http on
127.0.0.1."""

from __future__ import annotations

import io
import os
import socket

import fake_git_api as fake
import pytest
from test_cli_model_server import Stdin

from lado import state
from lado.cli import main

TOKEN = "glpat-CANARY-a95c1e"
RESTART = "Agents started from now on reach it; restart running agents to give it to them."


@pytest.fixture
def serve():
    started = []

    def start(profile, **kwargs):
        server = fake.Server(profile, **kwargs)
        started.append(server)
        return server

    yield start
    for server in started:
        server.close()


class Piped(Stdin):
    """stdin as a pipe that holds the token again for each command."""

    def __init__(self):
        super().__init__(TOKEN + "\n")

    @property
    def buffer(self):
        return io.BytesIO((TOKEN + "\n").encode())

    @buffer.setter
    def buffer(self, value):
        pass


@pytest.fixture(autouse=True)
def piped(monkeypatch):
    monkeypatch.setattr("sys.stdin", Piped())
    monkeypatch.setattr("getpass.getpass", lambda prompt: pytest.fail("asked on a terminal"))


PLAIN = (
    "lado: warning: the token goes to 127.0.0.1 over plain http://, unencrypted; "
    "use https:// if the server has it"
)


def _held_anywhere(capsys_text: str, lado_home) -> list[str]:
    files = [
        str(p.relative_to(lado_home))
        for p in lado_home.rglob("*")
        if p.is_file() and TOKEN.encode() in p.read_bytes()
    ]
    return files + (["output"] if TOKEN in capsys_text else [])


def test_add_tells_the_kind_and_saves_it(serve, capsys, lado_home):
    server = serve("gitlab", token=TOKEN)
    assert main(["git-server", "add", server.url, "--token"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        f"GitLab, signed in as {fake.LOGIN}",
        f"Saved git server {server.url}.",
        RESTART,
    ]
    assert err.splitlines() == [PLAIN]
    saved = state.git_servers()
    assert [(s.address, s.kind, s.login) for s in saved] == [(server.url, "gitlab", fake.LOGIN)]
    assert _held_anywhere(out + err, lado_home) == [f"git-servers/{saved[0].id}/token"]


def test_add_of_github_enterprise(serve, capsys):
    server = serve("github", token=TOKEN)
    assert main(["git-server", "add", server.url, "--token"]) == 0
    assert capsys.readouterr().out.startswith(f"GitHub, signed in as {fake.LOGIN}\n")
    assert state.git_servers()[0].kind == "github"


def test_a_token_on_a_terminal_is_asked_without_echo(serve, capsys, monkeypatch):
    server = serve("gitlab", token=TOKEN)
    monkeypatch.setattr("sys.stdin", Stdin(tty=True))
    asked = []
    monkeypatch.setattr("getpass.getpass", lambda prompt: asked.append(prompt) or TOKEN)
    assert main(["git-server", "add", server.url, "--token"]) == 0
    assert asked == ["Token of the server (not shown): "]


def test_add_again_replaces(serve, capsys):
    server = serve("gitlab")
    main(["git-server", "add", server.url, "--token"])
    first = state.git_servers()[0]
    assert main(["git-server", "add", server.url + "/", "--token"]) == 0
    assert f"Replaced git server {server.url}." in capsys.readouterr().out
    assert [s.id for s in state.git_servers()] == [first.id]


def test_a_refused_token_saves_nothing(serve, capsys):
    server = serve("gitlab-refuses")
    for kind in ([], ["--kind", "gitlab"]):
        assert main(["git-server", "add", server.url, "--token", *kind]) == 1
        out, err = capsys.readouterr()
        assert err.splitlines()[1:] == [
            f"lado: GitLab at {server.url} refuses the token",
            f"lado: make a token at {server.url}/-/user_settings/personal_access_tokens "
            "(scopes read_repository, write_repository, read_api)",
        ]
        assert out == ""
    assert state.git_servers() == []


def test_one_that_does_not_answer_is_saved_with_kind_and_a_warning(capsys):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    url = f"https://127.0.0.1:{port}"
    assert main(["git-server", "add", url, "--token"]) == 1
    out, err = capsys.readouterr()
    assert err.splitlines() == [
        f"lado: 127.0.0.1:{port} does not answer: the connection is refused",
        "lado: if the server is there for git but its API is not reachable from here, save "
        f"it unchecked: lado git-server add {url} --token --kind github|gitlab",
    ]
    assert main(["git-server", "add", url, "--token", "--kind", "gitlab"]) == 0
    out, err = capsys.readouterr()
    assert err.splitlines() == [
        f"lado: warning: {url} could not be checked (it does not answer: the connection is "
        "refused); saved as GitLab"
    ]
    assert out.splitlines() == [f"Saved git server {url}.", RESTART]
    assert state.git_servers()[0].login is None


def test_kind_against_the_answer_is_refused(serve, capsys):
    server = serve("gitlab")
    assert main(["git-server", "add", server.url, "--token", "--kind", "github"]) == 1
    assert f"lado: {server.url} answers as GitLab, not GitHub" in capsys.readouterr().err


def test_kind_offers_the_kinds(capsys):
    with pytest.raises(SystemExit):
        main(["git-server", "add", "--help"])
    assert "{github,gitlab}" in capsys.readouterr().out


@pytest.mark.parametrize(
    "given",
    [
        ["--token", TOKEN],
        ["--token=" + TOKEN],
        ["--token", "-" + TOKEN],
        ["--to", "-" + TOKEN],
        [TOKEN, "--token"],
    ],
)
def test_a_token_on_the_command_line_is_refused_without_its_value(given, capsys, serve):
    server = serve("gitlab")
    code = main(["git-server", "add", "gitlab.corp.ru", *given])
    assert code in (1, 2)
    out, err = capsys.readouterr()
    assert TOKEN not in out + err
    assert "--token" in err
    assert server.requests == []
    assert state.git_servers() == []


@pytest.mark.parametrize("piped_in", ["", "\n"])
def test_an_empty_token_is_refused(piped_in, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", Stdin(piped_in))
    assert main(["git-server", "add", "gitlab.corp.ru", "--token"]) == 1
    assert capsys.readouterr().err == "lado: the token is empty\n"


def test_add_without_token_is_refused(capsys):
    assert main(["git-server", "add", "gitlab.corp.ru"]) == 1
    assert "--token" in capsys.readouterr().err


def test_github_com_is_refused_before_the_token(capsys, monkeypatch):
    stdin = Stdin(TOKEN)
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["git-server", "add", "github.com", "--token"]) == 1
    assert "github.com is reached through gh's login" in capsys.readouterr().err
    assert not stdin.touched


def test_a_bad_address_exits_2(capsys):
    assert main(["git-server", "add", "https://me:pw@git.lan", "--token"]) == 2
    err = capsys.readouterr().err
    assert err == (
        "lado: not a git server's address: a git server's address holds no user or password; "
        "its token: --token\n"
    )


def test_an_old_git_is_refused_by_add(serve, capsys, tmp_path, monkeypatch):
    server = serve("gitlab")
    folder = tmp_path / "old-git"
    folder.mkdir()
    (folder / "git").write_text("#!/bin/sh\necho 'git version 2.30.2'\n")
    (folder / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}:{os.environ['PATH']}")
    assert main(["git-server", "add", server.url, "--token"]) == 1
    assert "lado: git 2.30.2 is older than 2.31" in capsys.readouterr().err
    assert server.requests == []


def test_list_shows_the_servers_without_asking_them(serve, capsys, lado_home):
    server = serve("gitlab")
    main(["git-server", "add", server.url, "--token"])
    main(["git-server", "add", "https://git.lan", "--token", "--kind", "gitlab"])
    gone = state.git_server_by_host("git.lan")
    (lado_home / "git-servers" / gone.id / "token").unlink()
    asked = len(server.requests)
    capsys.readouterr()
    assert main(["git-server", "list"]) == 0
    rows = [line.split() for line in capsys.readouterr().out.splitlines()]
    assert rows == [
        ["ADDRESS", "KIND", "LOGIN", "TOKEN"],
        [server.url, "GitLab", fake.LOGIN, "yes"],
        ["https://git.lan", "GitLab", "not", "checked", "no"],
    ]
    assert len(server.requests) == asked


def test_list_with_none(capsys):
    assert main(["git-server", "list"]) == 0
    assert capsys.readouterr().out == (
        "No git servers. Add one: lado git-server add <address> --token\n"
    )


def test_remove_by_address(serve, capsys, lado_home):
    server = serve("gitlab")
    main(["git-server", "add", server.url, "--token"])
    id = state.git_servers()[0].id
    capsys.readouterr()
    assert main(["git-server", "remove", server.url.removeprefix("http://") + "/"]) == 0
    assert capsys.readouterr().out == f"Removed git server {server.url}.\n"
    assert state.git_servers() == []
    assert not (lado_home / "git-servers" / id).exists()
    assert main(["git-server", "remove", server.url]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: {server.url} is no saved git server",
        "lado: see them: lado git-server list",
    ]


def test_the_bare_command_prints_its_help(capsys, lado_home):
    assert main(["git-server"]) == 0
    assert "add" in capsys.readouterr().out
    assert not (lado_home / "lado.db").exists()
