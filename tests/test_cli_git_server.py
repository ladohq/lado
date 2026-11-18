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

from lado import git_kinds, git_servers, model_servers, state
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


def test_the_usage_puts_the_address_before_the_token(capsys):
    # --token takes an optional value: a command typed as `add --token <address>` gives the
    # address as the token and is refused.
    with pytest.raises(SystemExit):
        main(["git-server", "add", "--help"])
    usage = capsys.readouterr().out.splitlines()[0]
    assert usage.index("address") < usage.index("--token")


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


def test_github_com_with_kind_is_refused_before_the_token(capsys, monkeypatch):
    stdin = Stdin(TOKEN)
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["git-server", "add", "github.com", "--token", "--kind", "github"]) == 1
    assert "github.com's kind is GitHub: add it without --kind" in capsys.readouterr().err
    assert not stdin.touched


def test_github_com_with_a_path_exits_2(capsys):
    assert main(["git-server", "add", "github.com/acme", "--token"]) == 2
    assert capsys.readouterr().err == (
        "lado: not a git server's address: github.com is signed in to at https://github.com\n"
    )


def test_add_list_and_remove_github_com(capsys, monkeypatch, tmp_path):
    with fake.reached_as(monkeypatch, tmp_path, "api.github.com", "github-com", token=TOKEN):
        assert main(["git-server", "add", "www.github.com", "--token"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[:2] == [
        f"GitHub, signed in as {fake.LOGIN}",
        "Saved git server https://github.com.",
    ]
    assert main(["git-server", "list"]) == 0
    assert capsys.readouterr().out.splitlines()[1].split() == [
        "https://github.com",
        "GitHub",
        fake.LOGIN,
        "yes",
        "-",
    ]
    assert main(["git-server", "remove", "github.com"]) == 0
    assert capsys.readouterr().out == "Removed git server https://github.com.\n"


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
        ["ADDRESS", "KIND", "LOGIN", "TOKEN", "AUTHOR"],
        [server.url, "GitLab", fake.LOGIN, "yes", "-"],
        ["https://git.lan", "GitLab", "not", "checked", "no", "-"],
    ]
    assert len(server.requests) == asked


def test_list_with_none(capsys):
    assert main(["git-server", "list"]) == 0
    assert capsys.readouterr().out == (
        "No git servers. Add one: lado git-server add <address> --token\n"
    )


def test_add_saves_a_token_without_push_and_warns(serve, capsys, lado_home):
    server = serve("gitlab-read", token=TOKEN)
    assert main(["git-server", "add", server.url, "--token"]) == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        f"GitLab, signed in as {fake.LOGIN}",
        f"Saved git server {server.url}.",
        RESTART,
    ]
    assert err.splitlines() == [
        PLAIN,
        "lado: warning: the token lacks write_repository: agents can clone but not push",
        "lado: replace it with a token with the scopes read_repository, write_repository, "
        f"read_api: lado git-server add {server.url} --token",
    ]
    assert [s.login for s in state.git_servers()] == [fake.LOGIN]


# The check of a saved server.


def _added(serve, capsys, profile, kind=None):
    server = serve(profile, token=TOKEN)
    args = ["git-server", "add", server.url, "--token"] + (["--kind", kind] if kind else [])
    assert main(args) == 0
    capsys.readouterr()
    return server


def test_check_of_a_server_that_works(serve, capsys, lado_home):
    server = _added(serve, capsys, "gitlab-full")
    assert main(["git-server", "check", server.url.removeprefix("http://") + "/"]) == 0
    out, err = capsys.readouterr()
    assert out == f"Works: GitLab, signed in as {fake.LOGIN}, may clone and push.\n"
    assert err == ""
    assert TOKEN not in out + err


@pytest.mark.parametrize(
    ("profile", "then", "lines"),
    [
        (
            "gitlab-full",
            "gitlab-refuses",
            [
                "lado: GitLab refused the token: it expired or was revoked",
                "lado: replace it: lado git-server add {url} --token",
            ],
        ),
        (
            "gitlab-full",
            "gitlab-read",
            [
                "lado: the token lacks write_repository: agents can clone but not push",
                "lado: replace it with a token with the scopes read_repository, "
                "write_repository, read_api: lado git-server add {url} --token",
            ],
        ),
        (
            "gitlab-full",
            "neither",
            ["lado: it answers as neither GitHub nor GitLab"],
        ),
        (
            "gitlab-full",
            "github",
            [
                "lado: it answers as GitHub, not GitLab: remove it and add it again",
                "lado: lado git-server remove {url}, then lado git-server add {url} --token",
            ],
        ),
    ],
)
def test_check_of_a_failure(serve, capsys, lado_home, monkeypatch, profile, then, lines):
    server = _added(serve, capsys, profile)
    monkeypatch.setitem(fake.PROFILES, profile, fake.PROFILES[then])
    assert main(["git-server", "check", server.url]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.splitlines() == [line.format(url=server.url) for line in lines]


def test_check_of_a_server_that_does_not_answer(serve, capsys, lado_home, monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    server = _added(serve, capsys, "hang", kind="gitlab")
    assert main(["git-server", "check", server.url]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: 127.0.0.1:{server.port} does not answer: it did not answer in 1 s",
        "lado: check that this computer reaches it: the company VPN or proxy; with LADO in "
        "Docker, its container",
    ]


def test_check_of_one_saved_without_a_check_saves_its_login(serve, capsys, lado_home, monkeypatch):
    server = _added(serve, capsys, "hang", kind="gitlab")
    monkeypatch.setitem(fake.PROFILES, "hang", fake.PROFILES["gitlab"])
    assert main(["git-server", "check", server.url]) == 0
    assert capsys.readouterr().out == (
        f"Works: GitLab, signed in as {fake.LOGIN}; the token's rights are not checked.\n"
    )
    assert main(["git-server", "list"]) == 0
    assert f"GitLab  {fake.LOGIN}" in capsys.readouterr().out


def test_check_of_no_saved_server(serve, capsys, lado_home):
    assert main(["git-server", "check", "git.lan"]) == 1
    assert capsys.readouterr().err.splitlines() == [
        "lado: https://git.lan is no saved git server",
        "lado: see them: lado git-server list",
    ]


def test_check_with_the_token_file_missing_sends_nothing(serve, capsys, lado_home):
    server = _added(serve, capsys, "gitlab-full")
    asked = len(server.requests)
    (lado_home / "git-servers" / state.git_servers()[0].id / "token").unlink()
    assert main(["git-server", "check", server.url]) == 1
    assert capsys.readouterr().err.splitlines() == [
        f"lado: the token file of {server.url} is missing",
        f"lado: replace it: lado git-server add {server.url} --token",
    ]
    assert len(server.requests) == asked


def test_check_of_an_address_it_does_not_take(capsys, lado_home):
    for text in ("ssh://git@git.lan", "not a url"):
        assert main(["git-server", "check", text]) == 2
        assert "not a git server's address" in capsys.readouterr().err
    assert main(["git-server", "add", "not a url", "--token"]) == 2
    assert "holds no space" in capsys.readouterr().err
    with pytest.raises(SystemExit) as raised:
        main(["git-server", "check"])
    assert raised.value.code == 2


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


def test_another_port_of_a_saved_host_name_is_refused_before_the_token(serve, capsys, monkeypatch):
    server = serve("gitlab")
    main(["git-server", "add", server.url, "--token"])
    capsys.readouterr()
    asked = len(server.requests)
    stdin = Stdin(TOKEN)
    monkeypatch.setattr("sys.stdin", stdin)
    assert main(["git-server", "add", "http://127.0.0.1:1", "--token"]) == 1
    out, err = capsys.readouterr()
    assert err.splitlines() == [
        f"lado: 127.0.0.1 already has a git server, {server.url}; LADO keeps one server per "
        "host name, as git's ssh addresses (git@127.0.0.1:…) carry no port",
        f"lado: remove it first: lado git-server remove {server.url}",
    ]
    assert out == ""
    assert not stdin.touched
    assert len(server.requests) == asked
    assert [s.address for s in state.git_servers()] == [server.url]


def test_removing_the_last_server_removes_the_folder(serve, capsys, lado_home):
    server = serve("gitlab")
    main(["git-server", "add", server.url, "--token"])
    assert main(["git-server", "remove", server.url]) == 0
    assert not (lado_home / "git-servers").exists()


def test_a_folder_that_stays_is_a_warning(serve, capsys, lado_home):
    server = serve("gitlab")
    main(["git-server", "add", server.url, "--token"])
    (lado_home / "git-servers" / "notes.txt").write_text("the human's")
    capsys.readouterr()
    assert main(["git-server", "remove", server.url]) == 0
    out, err = capsys.readouterr()
    assert out == f"Removed git server {server.url}.\n"
    assert err == (
        f"lado: warning: could not remove {lado_home / 'git-servers'}: directory not empty\n"
    )
    assert state.git_servers() == []


def test_the_bare_command_prints_its_help(capsys, lado_home):
    assert main(["git-server"]) == 0
    assert "add" in capsys.readouterr().out
    assert not (lado_home / "lado.db").exists()


# The commit author.

AUTHOR_RESTART = (
    "Agents started from now on commit so; restart running agents to give it to them.\n"
)


def _saved(address="https://gitlab.corp.ru"):
    checked = git_servers.Checked(git_kinds.by_name("gitlab"), "ivan")
    return git_servers.save(git_servers.address(address), checked, TOKEN)[0]


def _author(*args: str) -> int:
    return main(["git-server", "author", *args])


def test_author_sets_shows_and_clears(capsys):
    _saved()
    assert _author("gitlab.corp.ru", "--name", "Ivan Petrov", "--email", "ivan@corp.ru") == 0
    assert capsys.readouterr().out == (
        "Agents commit to https://gitlab.corp.ru as Ivan Petrov <ivan@corp.ru>.\n" + AUTHOR_RESTART
    )
    assert _author("https://gitlab.corp.ru/") == 0
    assert capsys.readouterr().out == "Ivan Petrov <ivan@corp.ru>\n"
    assert _author("gitlab.corp.ru", "--clear") == 0
    assert capsys.readouterr().out == (
        "Agents commit to https://gitlab.corp.ru with your own git author again.\n" + AUTHOR_RESTART
    )
    assert state.git_servers()[0].author_name is None
    assert _author("gitlab.corp.ru", "--clear") == 0  # none to clear: the same
    assert _author("gitlab.corp.ru") == 0
    assert capsys.readouterr().out.endswith(
        "https://gitlab.corp.ru has no commit author: agents commit there with your own git "
        "author.\n"
    )


def test_list_shows_the_author_last(capsys):
    _saved()
    _saved("https://git.lan")
    _author("gitlab.corp.ru", "--name", "Ivan Petrov", "--email", "ivan@corp.ru")
    capsys.readouterr()
    assert main(["git-server", "list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split()[-1] == "AUTHOR"
    assert lines[1].startswith("https://git.lan ") and lines[1].endswith(" -")
    assert lines[2].startswith("https://gitlab.corp.ru ")
    assert lines[2].endswith(" Ivan Petrov <ivan@corp.ru>")


def test_author_of_no_saved_server_exits_1(capsys):
    for args in ([], ["--clear"], ["--name", "I", "--email", "i@x"]):
        assert _author("git.lan", *args) == 1
        assert capsys.readouterr().err.splitlines() == [
            "lado: https://git.lan is no saved git server",
            "lado: see them: lado git-server list",
        ]


@pytest.mark.parametrize(
    ("args", "err"),
    [
        (["--name", "Ivan"], "lado: --name and --email go together\n"),
        (["--email", "i@corp.ru"], "lado: --name and --email go together\n"),
        (["--clear", "--name", "Ivan"], "lado: --clear takes no --name or --email\n"),
        (
            ["--clear", "--name", "I", "--email", "i@corp.ru"],
            "lado: --clear takes no --name or --email\n",
        ),
    ],
)
def test_a_half_author_exits_2_and_changes_nothing(capsys, args, err):
    _saved()
    assert _author("gitlab.corp.ru", *args) == 2
    assert capsys.readouterr().err == err
    assert state.git_servers()[0].author_name is None


def test_author_of_a_bad_address_exits_2(capsys):
    assert _author("ftp://git.lan") == 2
    assert capsys.readouterr().err.startswith("lado: not a git server's address: ")


@pytest.mark.parametrize(
    ("name", "email", "err"),
    [
        ("Ivan", "ivan.petrov", "lado: not an email address: name@host\n"),
        ("Ivan <boss>", "i@corp.ru", "lado: the author's name holds no < or > or line break\n"),
    ],
)
def test_a_refused_author_exits_1(capsys, name, email, err):
    _saved()
    assert _author("gitlab.corp.ru", "--name", name, "--email", email) == 1
    assert capsys.readouterr().err == err
    assert state.git_servers()[0].author_name is None


def test_an_old_git_is_refused_by_author(capsys, tmp_path, monkeypatch):
    _saved()
    folder = tmp_path / "old-git"
    folder.mkdir()
    (folder / "git").write_text("#!/bin/sh\necho 'git version 2.34.1'\n")
    (folder / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}:{os.environ['PATH']}")
    assert _author("gitlab.corp.ru", "--name", "I", "--email", "i@corp.ru") == 1
    assert capsys.readouterr().err == (
        "lado: git 2.34.1 is older than 2.36, which a commit author of a git server needs; "
        "update git\n"
    )


def test_author_help_names_its_options(capsys):
    with pytest.raises(SystemExit):
        _author("--help")
    out = capsys.readouterr().out
    assert all(option in out for option in ("--name", "--email", "--clear"))
