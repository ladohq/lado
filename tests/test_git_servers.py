"""lado.git_servers: a server's address, the probe of its kind, the store of servers and
tokens, the git variables and the old-git check. The probe asks tests/fake_git_api.py over
real HTTP on 127.0.0.1."""

from __future__ import annotations

import socket
import time

import fake_git_api as fake
import pytest

from lado import git_kinds, git_servers, model_servers

TOKEN = "glpat-CANARY-7f3e9a"  # a canary: no output or file but its own may hold it


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


def closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _refused(address, token=TOKEN, kind=None) -> git_servers.Refused:
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.probe(git_servers.address(address), token, kind)
    assert TOKEN not in str(raised.value) + raised.value.hint
    return raised.value


# The address.


@pytest.mark.parametrize(
    ("text", "root", "key"),
    [
        ("gitlab.corp.ru", "https://gitlab.corp.ru", "gitlab.corp.ru"),
        ("gitlab.corp.ru/", "https://gitlab.corp.ru", "gitlab.corp.ru"),
        ("HTTPS://GitLab.Corp.RU:443/", "https://gitlab.corp.ru", "gitlab.corp.ru"),
        ("https://corp.ru/gitlab/", "https://corp.ru/gitlab", "corp.ru"),
        ("https://git.test:8443", "https://git.test:8443", "git.test:8443"),
        ("http://git.lan:80", "http://git.lan", "git.lan"),
        ("http://git.lan:8080/", "http://git.lan:8080", "git.lan:8080"),
    ],
)
def test_an_address_and_its_host(text, root, key):
    address = git_servers.address(text)
    assert (address.root, address.key) == (root, key)


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("", "no address given"),
        ("https://user:pw@gitlab.corp.ru", "no user or password"),
        ("https://gitlab.corp.ru/?a=1", "no query"),
        ("https://gitlab.corp.ru/#x", "no fragment"),
        ("ssh://git@gitlab.corp.ru", "https:// or http://"),
        ("git@gitlab.corp.ru:team/app.git", "https:// or http://"),
        ("https://", "names no host"),
        ("https://gitlab.corp.ru:99999", "port"),
    ],
)
def test_an_address_refused(text, why):
    with pytest.raises(ValueError) as raised:
        git_servers.address(text)
    assert why in str(raised.value)
    assert "pw" not in str(raised.value)


def test_plain_http_is_warned_about():
    assert git_servers.plain_http_warning(git_servers.address("http://git.lan")) == (
        "the token goes to git.lan over plain http://, unencrypted; "
        "use https:// if the server has it"
    )
    assert git_servers.plain_http_warning(git_servers.address("git.lan")) is None


@pytest.mark.parametrize("text", ["github.com", "https://www.github.com/", "api.github.com"])
def test_github_com_is_refused(text):
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check_not_github(git_servers.address(text))
    assert str(raised.value) == (
        "github.com is reached through gh's login (GH_TOKEN or gh auth login); "
        "LADO keeps no token for it"
    )
    git_servers.check_not_github(git_servers.address("github.corp.ru"))


# The probe.


def test_gitlab_is_told_with_its_login(serve):
    server = serve("gitlab", token=TOKEN)
    checked = git_servers.probe(git_servers.address(server.url), TOKEN)
    assert (checked.kind.name, checked.login, checked.unchecked) == ("gitlab", fake.LOGIN, "")
    assert checked.line() == f"GitLab, signed in as {fake.LOGIN}"


def test_github_is_told_with_its_login(serve):
    server = serve("github", token=TOKEN)
    checked = git_servers.probe(git_servers.address(server.url), TOKEN)
    assert (checked.kind.name, checked.login) == ("github", fake.LOGIN)
    assert checked.line() == f"GitHub, signed in as {fake.LOGIN}"


def test_both_kinds_are_asked_once_with_the_token_in_their_own_header(serve):
    server = serve("gitlab", token=TOKEN)
    git_servers.probe(git_servers.address(server.url), TOKEN)
    assert server.paths() == [fake.GITHUB, fake.GITLAB]
    by_path = {r.path: r for r in server.requests}
    assert by_path[fake.GITLAB].headers["PRIVATE-TOKEN"] == TOKEN
    assert by_path[fake.GITHUB].headers["Authorization"] == f"token {TOKEN}"
    for request in server.requests:
        held = [name.lower() for name, value in request.headers.items() if TOKEN in value]
        assert held == (["private-token"] if request.path == fake.GITLAB else ["authorization"])
        assert TOKEN not in request.path


def test_kinds_are_asked_at_once(serve, monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    server = serve("gitlab-github-hangs")
    started = time.monotonic()
    checked = git_servers.probe(git_servers.address(server.url), TOKEN)
    assert checked.kind.name == "gitlab"
    assert time.monotonic() - started < 3


def test_two_kinds_recognised_are_refused_without_kind(serve):
    server = serve("both")
    refused = _refused(server.url)
    assert str(refused) == (
        f"{server.url} answers as GitHub and as GitLab; say which: --kind github or --kind gitlab"
    )
    checked = git_servers.probe(git_servers.address(server.url), TOKEN, "github")
    assert (checked.kind.name, checked.login, checked.unchecked) == ("github", fake.LOGIN, "")


def test_kind_against_the_answer_is_refused(serve):
    server = serve("gitlab")
    assert str(_refused(server.url, kind="github")) == (
        f"{server.url} answers as GitLab, not GitHub"
    )


@pytest.mark.parametrize("kind", [None, "gitlab"])
def test_a_refused_token_is_refused_with_its_page_even_with_kind(serve, kind):
    server = serve("gitlab-refuses")
    refused = _refused(server.url, kind=kind)
    assert str(refused) == f"GitLab at {server.url} refuses the token"
    assert refused.hint == (
        f"make a token at {server.url}/-/user_settings/personal_access_tokens "
        "(scopes read_repository, write_repository, read_api)"
    )


def test_github_refusing_the_token(serve):
    server = serve("github-refuses")
    refused = _refused(server.url)
    assert str(refused) == f"GitHub at {server.url} refuses the token"
    assert refused.hint == f"make a token at {server.url}/settings/tokens (scope repo)"


def test_a_gitlab_token_without_read_api(serve):
    server = serve("gitlab-scope")
    assert str(_refused(server.url)) == (
        f"GitLab at {server.url} takes the token, but it lacks the scope read_api"
    )


def _kind_hint(root: str) -> str:
    return (
        "if the server is there for git but its API is not reachable from here, save it "
        f"unchecked: lado git-server add {root} --token --kind github|gitlab"
    )


def test_a_server_of_neither_kind(serve):
    server = serve("neither")
    refused = _refused(server.url)
    assert str(refused) == f"{server.url} answers as neither GitHub nor GitLab"
    assert refused.hint == _kind_hint(server.url)


def test_a_redirect_is_named_and_not_followed(serve):
    sso = serve("gitlab")
    server = serve(fake.REDIRECT, location=sso.url + "/login?next=secret")
    refused = _refused(server.url)
    assert str(refused) == f"{server.url} sends to {sso.url}/login; give the server's own address"
    assert sso.requests == []


def test_a_closed_port_does_not_answer():
    root = f"https://127.0.0.1:{closed_port()}"
    refused = _refused(root)
    assert str(refused) == f"{root[8:]} does not answer: the connection is refused"
    assert refused.hint == _kind_hint(root)


def test_an_unknown_name_does_not_answer():
    assert str(_refused("gitlab.invalid")) == (
        "gitlab.invalid does not answer: the name is not found"
    )


def test_a_hanging_server_does_not_answer(serve, monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    server = serve("hang")
    assert str(_refused(server.url)) == (
        f"127.0.0.1:{server.port} does not answer: it did not answer in 1 s"
    )


def test_an_untrusted_certificate(serve, tmp_path):
    server = serve("gitlab", certificate=fake.make_certificate(tmp_path))
    refused = _refused(server.url)
    assert str(refused).startswith(
        f"127.0.0.1:{server.port} does not answer: its certificate is not trusted on this machine"
    )


def test_kind_saves_one_that_cannot_be_checked(serve):
    root = f"https://127.0.0.1:{closed_port()}"
    checked = git_servers.probe(git_servers.address(root), TOKEN, "gitlab")
    assert (checked.kind.name, checked.login) == ("gitlab", None)
    assert checked.unchecked == "it does not answer: the connection is refused"
    neither = serve("neither")
    checked = git_servers.probe(git_servers.address(neither.url), TOKEN, "github")
    assert (checked.kind.name, checked.login) == ("github", None)
    assert checked.unchecked == "it answers as neither GitHub nor GitLab"
    assert checked.line() is None


def test_the_kinds_are_those_of_git_kinds():
    assert git_servers.KIND_NAMES == tuple(kind.name for kind in git_kinds.KINDS)
