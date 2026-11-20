"""lado.git_servers: a server's address, the probe of its kind, the store of servers and
tokens, the git variables and the old-git check. The probe asks tests/fake_git_api.py over
real HTTP on 127.0.0.1."""

from __future__ import annotations

import dataclasses
import os
import shlex
import socket
import sqlite3
import stat
import subprocess
import sys
import time

import certificates as made
import fake_git_api as fake
import pytest
import yaml

from lado import git_certificates, git_kinds, git_servers, model_servers, state

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
        ("gitlab.corp.ru.", "https://gitlab.corp.ru", "gitlab.corp.ru"),
        ("https://GitLab.corp.ru.:443/gitlab", "https://gitlab.corp.ru/gitlab", "gitlab.corp.ru"),
        ("git.test..:8443", "https://git.test:8443", "git.test:8443"),
        (" gitlab.corp.ru \n", "https://gitlab.corp.ru", "gitlab.corp.ru"),
        ("git_lab.corp.ru", "https://git_lab.corp.ru", "git_lab.corp.ru"),
        ("https://[::1]:8443", "https://[::1]:8443", "[::1]:8443"),
        ("гитлаб.рф", "https://гитлаб.рф", "гитлаб.рф"),
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
        ("...", "names no host"),
        ("https://.:8443", "names no host"),
        ("https://gitlab.corp.ru:99999", "port"),
        ("not a url", "holds no space"),
        ("https://git lab.corp.ru", "holds no space"),
        ("gitlab.corp.ru/my group", "holds no space"),
        ("gitlab.corp.ru\t/x", "holds no space"),
        ("gitlab.corp.ru/\x00", "holds no space"),
        ("gitlab,corp.ru", "only letters, digits"),
        ("git%20lab.corp.ru", "only letters, digits"),
        ("https://[::1", "port"),
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


@pytest.mark.parametrize(
    "text",
    ["github.com", "https://www.github.com/", "api.github.com", "GitHub.com.", "github.com:443"],
)
def test_www_and_api_are_github_com(text):
    assert git_servers.address(text) == ("https://github.com", "github.com", "github.com", "https")


@pytest.mark.parametrize(
    "text", ["github.com:8443", "https://github.com/acme", "http://github.com", "www.github.com/x"]
)
def test_github_com_with_a_port_or_path_is_refused(text):
    with pytest.raises(git_servers.BadAddress) as raised:
        git_servers.address(text)
    assert str(raised.value) == "github.com is signed in to at https://github.com"


def test_kind_with_github_com_is_refused(lado_home):
    asked = []
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.add(git_servers.address("github.com"), asked.append, "gitlab", print)
    assert (str(raised.value), raised.value.field) == (
        "github.com's kind is GitHub: add it without --kind",
        "kind",
    )
    assert asked == [] and state.git_servers() == []


@pytest.fixture
def github_com(monkeypatch, tmp_path):
    """The fake GitHub API as https://api.github.com, taking TOKEN."""
    with fake.reached_as(monkeypatch, tmp_path, "api.github.com", "github-com", token=TOKEN) as s:
        yield s


def test_github_com_is_added_through_the_proxy(github_com, lado_home):
    saved, replaced, checked = git_servers.add(
        git_servers.address("github.com"), lambda: TOKEN, None, print
    )
    assert (saved.address, saved.host, saved.kind, saved.login) == (
        "https://github.com",
        "github.com",
        "github",
        fake.LOGIN,
    )
    assert (replaced, checked.rights_checked, checked.missing_scopes) == (False, True, ())
    assert github_com.paths() == [fake.GITHUB_COM]
    assert github_com.proxy.asked == ["api.github.com:443"]
    found = git_servers.check(git_servers.address("www.github.com"))
    assert (found.outcome, found.login) == ("ok", fake.LOGIN)
    assert git_servers.remove(git_servers.address("github.com")).server.id == saved.id
    assert state.git_servers() == []


def test_github_com_probe_asks_one_request(github_com, lado_home):
    hint = git_servers.hint(git_servers.address("github.com"))
    assert hint.kind.name == "github"
    assert github_com.paths() == [fake.GITHUB_COM]
    assert "Authorization" not in github_com.requests[0].headers


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
    # After GitLab's user, the token's own facts: its rights.
    assert server.paths() == [fake.GITHUB, fake.GITLAB_TOKEN, fake.GITLAB]
    by_path = {r.path: r for r in server.requests}
    assert by_path[fake.GITLAB].headers["PRIVATE-TOKEN"] == TOKEN
    assert by_path[fake.GITHUB].headers["Authorization"] == f"token {TOKEN}"
    for request in server.requests:
        held = [name.lower() for name, value in request.headers.items() if TOKEN in value]
        gitlab = request.path in (fake.GITLAB, fake.GITLAB_TOKEN)
        assert held == (["private-token"] if gitlab else ["authorization"])
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
@pytest.mark.parametrize("profile", ["gitlab-refuses", "gitlab-revoked", "gitlab-expired"])
def test_a_refused_token_is_refused_with_its_page_even_with_kind(serve, kind, profile):
    server = serve(profile)
    refused = _refused(server.url, kind=kind)
    assert str(refused) == f"GitLab at {server.url} refuses the token"
    assert refused.hint == (
        f"make a token at {server.url}/-/user_settings/personal_access_tokens (scope api)"
    )


def test_github_refusing_the_token(serve):
    server = serve("github-refuses")
    refused = _refused(server.url)
    assert str(refused) == f"GitHub at {server.url} refuses the token"
    assert refused.hint == f"make a token at {server.url}/settings/tokens (scope repo)"


NEITHER = "agents can neither clone nor push"
CLONE_ONLY = "agents can clone but not push"


@pytest.mark.parametrize(
    ("profile", "kind", "missing", "checked", "lacks"),
    [
        ("gitlab-full", "gitlab", (), True, None),
        ("gitlab-read", "gitlab", ("write_repository",), True, CLONE_ONLY),
        ("gitlab-no-repo", "gitlab", ("read_repository", "write_repository"), True, NEITHER),
        ("gitlab-api-only", "gitlab", (), True, None),  # api holds both
        ("gitlab", "gitlab", (), False, None),  # before GitLab 15.5: 404
        ("github-repo", "github", (), True, None),
        ("github-no-repo", "github", ("repo",), True, NEITHER),
        ("github-no-scopes", "github", ("repo",), True, NEITHER),
        ("github", "github", (), False, None),  # a fine-grained token tells none
    ],
)
def test_the_rights_of_a_token(serve, profile, kind, missing, checked, lacks):
    server = serve(profile, token=TOKEN)
    found = git_servers.probe(git_servers.address(server.url), TOKEN)
    assert (found.kind.name, found.login) == (kind, fake.LOGIN)
    assert (found.missing_scopes, found.rights_checked) == (missing, checked)
    expected = f"the token lacks {', '.join(missing)}: {lacks}" if lacks else None
    assert found.lacks() == expected
    if kind == "gitlab":  # the token's own facts asked after its user, with the token
        asked = [r for r in server.requests if r.path == fake.GITLAB_TOKEN]
        assert [r.headers["PRIVATE-TOKEN"] for r in asked] == [TOKEN]


def test_a_gitlab_whose_token_facts_refuse_tells_no_rights(serve):
    server = serve("gitlab-full", token=TOKEN)
    at = git_servers.address(server.url)
    kind = git_kinds.by_name("gitlab")
    user = model_servers.Answer(200, {"username": "a"})
    for answer in (model_servers.Answer(401, {}), model_servers.Answer(why="unknown host")):
        assert kind.rights(at.root, TOKEN, user, lambda url, headers, a=answer: a) is None


def test_a_server_saved_without_a_check_has_no_rights(serve):
    root = f"https://127.0.0.1:{closed_port()}"
    checked = git_servers.probe(git_servers.address(root), TOKEN, "gitlab")
    assert (checked.missing_scopes, checked.rights_checked, checked.lacks()) == ((), False, None)


def test_add_saves_a_token_without_push_and_says_so(serve, lado_home):
    server = serve("gitlab-read", token=TOKEN)
    at = git_servers.address(server.url)
    saved, replaced, checked = git_servers.add(at, lambda: TOKEN, None, lambda line: None)
    assert (saved.login, replaced) == (fake.LOGIN, False)
    assert checked.lacks() == f"the token lacks write_repository: {CLONE_ONLY}"
    assert checked.replace_hint(at) == (
        f"replace it with a token with the scope api: lado git-server add {server.url} --token"
    )


def test_a_gateway_refusing_every_kind_names_no_kind(serve):
    server = serve("gateway")
    refused = _refused(server.url)
    assert str(refused) == f"{server.url} refuses the token on GitHub's and GitLab's API alike"
    assert refused.hint == (
        "check that the token was copied whole; a sign-in gateway in front of the server "
        "refuses any token too"
    )
    assert (refused.field, refused.choose_kind) == ("token", False)
    assert refused.page == (
        "The server refused this token on both GitHub's and GitLab's API: copy it whole, or "
        "ask whether a sign-in gateway stands in front of it."
    )
    assert refused.page_hint == ""
    assert str(_refused(server.url, kind="gitlab")) == f"GitLab at {server.url} refuses the token"


@pytest.mark.parametrize("profile", ["hang", None])
def test_a_server_that_gives_no_answer_at_add_offers_the_kind(serve, monkeypatch, profile):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    root = serve(profile).url if profile else f"http://127.0.0.1:{closed_port()}"
    assert _refused(root).choose_kind is True
    for other in ("gitlab-refuses", "neither"):
        assert _refused(serve(other).url).choose_kind is False


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
    assert str(refused) == f"the certificate of {server.url} is not trusted"
    assert refused.offer is not None and refused.offer.own


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


# The store.

GITLAB = git_kinds.by_name("gitlab")


def _save(text="gitlab.corp.ru", token=TOKEN, login="ivan"):
    checked = git_servers.Checked(GITLAB, login)
    return git_servers.save(git_servers.address(text), checked, token)


def _files_holding(root, value: str) -> list[str]:
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink() and value.encode() in p.read_bytes()
    )


def test_a_saved_server_keeps_its_token_in_its_own_file(lado_home):
    previous = os.umask(0)  # the modes whatever the umask
    try:
        saved, replaced = _save()
    finally:
        os.umask(previous)
    assert replaced is False
    assert (saved.address, saved.host, saved.kind, saved.login) == (
        "https://gitlab.corp.ru",
        "gitlab.corp.ru",
        "gitlab",
        "ivan",
    )
    folder = lado_home / "git-servers" / saved.id
    assert (folder / "token").read_text() == TOKEN
    assert stat.S_IMODE((lado_home / "git-servers").stat().st_mode) == 0o700
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE((folder / "token").stat().st_mode) == 0o600
    assert _files_holding(lado_home, TOKEN) == [f"git-servers/{saved.id}/token"]
    assert git_servers.has_token(saved)


def test_a_link_on_the_way_is_refused(lado_home, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    lado_home.mkdir(exist_ok=True)
    (lado_home / "git-servers").symlink_to(elsewhere)
    with pytest.raises(git_servers.Refused) as raised:
        _save()
    assert "symbolic link" in str(raised.value)
    assert list(elsewhere.iterdir()) == []
    assert state.git_servers() == []


def test_a_second_save_of_the_host_replaces_and_keeps_the_id(lado_home):
    first, _ = _save()
    again, replaced = _save("https://gitlab.corp.ru:443/", "glpat-NEW", login="petr")
    assert replaced is True
    assert (again.id, again.login) == (first.id, "petr")
    assert (lado_home / "git-servers" / first.id / "token").read_text() == "glpat-NEW"
    assert len(state.git_servers()) == 1


def test_a_trailing_dot_replaces_the_server_of_its_host(lado_home):
    first, _ = _save()
    again, replaced = _save("gitlab.corp.ru.", "glpat-NEW", login="petr")
    assert (again.id, again.address, replaced) == (first.id, "https://gitlab.corp.ru", True)
    assert [s.address for s in state.git_servers()] == ["https://gitlab.corp.ru"]


def test_a_host_saved_meanwhile_gets_the_new_token_in_its_own_folder(lado_home, monkeypatch):
    first, _ = _save()
    monkeypatch.setattr(state, "git_server_by_host", lambda host: None)  # not seen yet
    again, replaced = _save(token="glpat-NEW")
    assert (again.id, replaced) == (first.id, True)
    assert [p.name for p in (lado_home / "git-servers").iterdir()] == [first.id]
    assert (lado_home / "git-servers" / first.id / "token").read_text() == "glpat-NEW"


def test_a_failed_row_leaves_no_folder_for_a_new_server(lado_home, monkeypatch):
    def broken(*args):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(state, "save_git_server", broken)
    with pytest.raises(sqlite3.OperationalError):
        _save()
    assert not (lado_home / "git-servers").exists()  # no server left: the folder goes too


def test_remove_takes_the_row_and_the_folder(lado_home):
    saved, _ = _save()
    removed, warning = git_servers.remove(git_servers.address("https://gitlab.corp.ru/"))
    assert (removed.id, warning) == (saved.id, None)
    assert state.git_servers() == []
    assert not (lado_home / "git-servers" / saved.id).exists()
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.remove(git_servers.address("gitlab.corp.ru"))
    assert str(raised.value) == "https://gitlab.corp.ru is no saved git server"
    assert raised.value.hint == "see them: lado git-server list"


def _hold_lock(lado_home):
    """The lock of the git servers held by another open file, as another process holds it."""
    import fcntl

    lado_home.mkdir(exist_ok=True)
    held = open(lado_home / "git-servers.lock", "a+")  # noqa: SIM115 - closed by the caller
    fcntl.flock(held, fcntl.LOCK_EX)
    return held


def test_a_removal_waits_for_a_save_holding_the_lock(lado_home):
    import threading

    _save()
    held = _hold_lock(lado_home)
    done = []
    removal = threading.Thread(
        target=lambda: done.append(git_servers.remove(git_servers.address("gitlab.corp.ru")))
    )
    removal.start()
    removal.join(0.5)
    assert done == [] and len(state.git_servers()) == 1
    held.close()
    removal.join(5)
    assert len(done) == 1 and state.git_servers() == []


def test_a_held_lock_refuses_after_its_wait(lado_home, monkeypatch):
    monkeypatch.setattr(git_servers, "LOCK_WAIT", 0.2)
    _save()
    with _hold_lock(lado_home):
        started = time.monotonic()
        for change in (_save, lambda: git_servers.remove(git_servers.address("gitlab.corp.ru"))):
            with pytest.raises(git_servers.Refused) as raised:
                change()
            assert str(raised.value) == "another change of the git servers is running; try again"
        assert time.monotonic() - started >= 0.4
    assert git_servers.LOCK_WAIT == 0.2 and len(state.git_servers()) == 1


def test_the_lock_waits_ten_seconds():
    assert git_servers.LOCK_WAIT == 10


def test_a_removal_racing_a_replacement_keeps_the_row_and_the_token_in_step(lado_home, monkeypatch):
    import threading

    _save()
    write = git_servers._write_token
    removals = []

    def slow(id, token):
        # The replacement's row is written: a removal starts before its token file is.
        removal = threading.Thread(
            target=lambda: removals.append(
                git_servers.remove(git_servers.address("gitlab.corp.ru"))
            )
        )
        removal.start()
        removals.append(removal)
        time.sleep(0.3)
        write(id, token)

    monkeypatch.setattr(git_servers, "_write_token", slow)
    _save(token="glpat-NEW")
    removals[0].join(10)
    assert len(removals) == 2  # the removal ran, after the replacement
    assert state.git_servers() == []
    assert not (lado_home / "git-servers").exists()


def test_a_server_without_its_token_file_has_none(lado_home):
    saved, _ = _save()
    (lado_home / "git-servers" / saved.id / "token").unlink()
    assert not git_servers.has_token(state.git_servers()[0])


# The git variables.


def _server(id="a1", address="https://gitlab.corp.ru", host="gitlab.corp.ru", kind="gitlab"):
    return state.GitServer(id, address, host, kind, "ivan", "2026-11-15 00:00:00")


def _entries(found: dict[str, str]) -> list[tuple[str, str]]:
    count = int(found["GIT_CONFIG_COUNT"])
    return [(found[f"GIT_CONFIG_KEY_{n}"], found[f"GIT_CONFIG_VALUE_{n}"]) for n in range(count)]


def test_no_server_sets_no_variable():
    assert git_servers.variables({"GIT_CONFIG_COUNT": "1"}, []) == {}


def test_each_server_gets_an_empty_helper_lados_and_its_ssh_forms(lado_home):
    found = git_servers.variables({}, [_server()])
    entries = _entries(found)
    assert len(found) == 2 + 2 * len(entries)
    assert found["LADO_GIT_CONFIG_BASE"] == ""  # the environment had no count of its own
    helper = git_servers.helper_command(_server())
    assert entries == [
        ("credential.https://gitlab.corp.ru.helper", ""),
        ("credential.https://gitlab.corp.ru.helper", helper),
        ("url.https://gitlab.corp.ru/.insteadOf", "git@gitlab.corp.ru:"),
        ("url.https://gitlab.corp.ru/.insteadOf", "ssh://git@gitlab.corp.ru/"),
        ("url.https://gitlab.corp.ru/.insteadOf", "ssh://git@gitlab.corp.ru:22/"),
    ]
    assert helper.startswith("!" + shlex.quote(sys.executable) + " -c ")
    assert shlex.split(helper[1:])[3:] == [
        "lado.git_credential",
        "--home",
        str(lado_home),
        "--server",
        "a1",
        "--user",
        "oauth2",
        "--address",
        "https://gitlab.corp.ru",
    ]


def test_a_server_under_a_path_and_a_port():
    entries = _entries(
        git_servers.variables(
            {}, [_server(address="https://corp.ru:8443/gitlab", host="corp.ru:8443", kind="github")]
        )
    )
    assert entries[0] == ("credential.https://corp.ru:8443.helper", "")
    assert "--user x-access-token" in entries[1][1]
    assert entries[2:] == [
        ("url.https://corp.ru:8443/gitlab/.insteadOf", "git@corp.ru:"),
        ("url.https://corp.ru:8443/gitlab/.insteadOf", "ssh://git@corp.ru/"),
        ("url.https://corp.ru:8443/gitlab/.insteadOf", "ssh://git@corp.ru:22/"),
    ]


def test_the_agents_own_entries_are_kept_and_lados_come_after():
    env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.autocrlf"}
    found = git_servers.variables(env, [_server(), _server("b2", "https://g.lan", "g.lan")])
    assert found["GIT_CONFIG_COUNT"] == "11"
    assert found["LADO_GIT_CONFIG_BASE"] == "1"
    assert "GIT_CONFIG_KEY_0" not in found
    assert found["GIT_CONFIG_KEY_1"] == "credential.https://gitlab.corp.ru.helper"
    assert found["GIT_CONFIG_KEY_6"] == "credential.https://g.lan.helper"


@pytest.mark.parametrize("count", ["x", "-3", ""])
def test_a_count_that_is_no_number_counts_as_none(count):
    found = git_servers.variables({"GIT_CONFIG_COUNT": count}, [_server()])
    assert found["GIT_CONFIG_COUNT"] == "5"
    assert found["GIT_CONFIG_KEY_0"] == "credential.https://gitlab.corp.ru.helper"


@pytest.fixture
def git_env(tmp_path):
    """git's environment with its own HOME and global config, no system one, no prompt."""
    home = tmp_path / "home"
    home.mkdir()
    # No system config: Apple's git reads its own (osxkeychain, whose keychain a HOME of
    # the test's has not: macOS asks in a window), which GIT_CONFIG_SYSTEM does not replace.
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "LADO_HOME": os.environ["LADO_HOME"],
    }


@pytest.mark.parametrize(
    ("remote", "url"),
    [
        ("git@gitlab.corp.ru:team/app.git", "https://gitlab.corp.ru/team/app.git"),
        ("ssh://git@gitlab.corp.ru/team/app.git", "https://gitlab.corp.ru/team/app.git"),
        ("ssh://git@gitlab.corp.ru:22/team/app.git", "https://gitlab.corp.ru/team/app.git"),
        (
            "ssh://git@gitlab.corp.ru:2222/team/app.git",
            "ssh://git@gitlab.corp.ru:2222/team/app.git",
        ),
        ("git@git.lan:team/app.git", "git@git.lan:team/app.git"),
        ("git@corp.ru:team/app.git", "https://corp.ru/gitlab/team/app.git"),
    ],
)
def test_git_sends_the_ssh_forms_of_a_server_over_https(git_env, tmp_path, remote, url):
    servers = [_server(), _server("b2", "https://corp.ru/gitlab", "corp.ru")]
    env = git_env | git_servers.variables(git_env, servers)
    for push in (False, True):
        args = ["git", "ls-remote", "--get-url", remote]
        if push:  # a push URL is rewritten the same: no pushInsteadOf of its own
            args = [
                "git",
                "-C",
                str(_repo(tmp_path, env, remote)),
                "remote",
                "get-url",
                "--push",
                "origin",
            ]
        result = subprocess.run(args, env=env, capture_output=True, text=True, check=True)
        assert result.stdout.strip() == url


def _repo(tmp_path, env, remote):
    repo = tmp_path / "repo"
    if not repo.exists():
        subprocess.run(["git", "init", "-q", str(repo)], env=env, check=True)
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", "origin", remote], env=env, check=True
        )
    return repo


@pytest.mark.parametrize(
    ("remote", "found"),
    [
        ("https://gitlab.corp.ru/team/app.git", "a1"),
        ("HTTPS://GitLab.corp.ru:443/team/app.git", "a1"),
        ("http://gitlab.corp.ru/team/app.git", "a1"),
        ("git@gitlab.corp.ru:team/app.git", "a1"),
        ("ssh://git@gitlab.corp.ru/team/app.git", "a1"),
        ("ssh://git@gitlab.corp.ru:22/team/app.git", "a1"),
        ("ssh://git@gitlab.corp.ru:2222/team/app.git", None),
        ("https://gitlab.corp.ru:8443/team/app.git", None),
        ("https://git.test:8443/a.git", "b2"),
        ("git@git.test:a.git", "b2"),
        ("https://git.test/a.git", None),
        ("https://github.com/a/b.git", None),
        ("/some/folder", None),
        ("file:///some/folder", None),
    ],
)
def test_the_server_of_a_remote(remote, found):
    servers = [_server(), _server("b2", "https://git.test:8443", "git.test:8443")]
    server = git_servers.server_for(remote, servers)
    assert (server.id if server else None) == found


# git older than 2.31.


def _fake_git(tmp_path, version: str) -> dict[str, str]:
    folder = tmp_path / "old-git"
    folder.mkdir(exist_ok=True)
    git = folder / "git"
    git.write_text(f"#!/bin/sh\necho 'git version {version}'\n")
    git.chmod(0o755)
    return {"PATH": f"{folder}:{os.environ['PATH']}"}


def test_an_old_git_is_refused(tmp_path):
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check_git(_fake_git(tmp_path, "2.30.2"))
    assert str(raised.value) == (
        "git 2.30.2 is older than 2.31, which git servers need; update git, or remove the "
        "servers (lado git-server remove <address>)"
    )


@pytest.mark.parametrize("version", ["2.31.0", "2.47.1 (Apple Git-154)"])
def test_a_current_git_is_taken(tmp_path, version):
    git_servers.check_git(_fake_git(tmp_path, version))


def test_a_missing_git_is_left_to_the_other_checks(tmp_path):
    git_servers.check_git({"PATH": str(tmp_path)})


# One server per host name.


def _host_taken(address: str, held: str) -> str:
    host = git_servers.address(address).host
    return (
        f"{host} already has a git server, {held}; LADO keeps one server per host name, as "
        f"git's ssh addresses (git@{host}:…) carry no port"
    )


@pytest.mark.parametrize("other", ["git.corp.example:8443", "http://git.corp.example:8080"])
def test_another_port_of_a_saved_host_name_is_refused(lado_home, other):
    _save("git.corp.example")
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check_host(git_servers.address(other))
    refused = raised.value
    assert str(refused) == _host_taken(other, "https://git.corp.example")
    assert refused.hint == "remove it first: lado git-server remove https://git.corp.example"
    assert refused.page_hint == "Remove it first if the server moved to this address."
    assert refused.field == "address"
    git_servers.check_host(git_servers.address("https://git.corp.example/"))  # its own key
    git_servers.check_host(git_servers.address("git.corp.example.org"))


def test_save_refuses_another_port_inside_its_write(lado_home):
    # Two adds at once both passed check_host: the second save is refused, its folder gone.
    first, _ = _save("git.corp.example")
    with pytest.raises(git_servers.Refused) as raised:
        _save("git.corp.example:8443", token="glpat-OTHER")
    assert str(raised.value) == _host_taken("git.corp.example:8443", "https://git.corp.example")
    assert [s.id for s in state.git_servers()] == [first.id]
    assert [p.name for p in (lado_home / "git-servers").iterdir()] == [first.id]
    assert _files_holding(lado_home, "glpat-OTHER") == []


def test_add_refuses_another_port_before_reading_the_token_or_asking(serve, lado_home):
    server = serve("gitlab", token=TOKEN)
    _save(f"https://127.0.0.1:{closed_port()}")
    asked = []

    def token():
        asked.append(True)
        return TOKEN

    with pytest.raises(git_servers.Refused) as raised:
        git_servers.add(git_servers.address(server.url), token, None, lambda line: None)
    assert "127.0.0.1 already has a git server" in str(raised.value)
    assert (asked, server.requests) == ([], [])


def test_add_checks_and_saves(serve, lado_home):
    server = serve("gitlab", token=TOKEN)
    warned = []
    saved, replaced, checked = git_servers.add(
        git_servers.address(server.url), lambda: TOKEN, None, warned.append
    )
    assert (saved.address, saved.login, replaced) == (server.url, fake.LOGIN, False)
    assert checked.kind.name == "gitlab"
    assert warned == [git_servers.plain_http_warning(git_servers.address(server.url))]


def test_add_refuses_a_kind_it_does_not_know(lado_home):
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.add(git_servers.address("git.lan"), lambda: TOKEN, "gitea", print)
    assert (str(raised.value), raised.value.field) == (
        "gitea is no kind of git server LADO knows: github or gitlab",
        "kind",
    )


# The check of a saved server.


def _saved(url, kind="gitlab", login="ivan.petrov"):
    at = git_servers.address(url)
    return git_servers.save(at, git_servers.Checked(git_kinds.by_name(kind), login), TOKEN)[0]


def _check(url) -> git_servers.Check:
    found = git_servers.check(git_servers.address(url))
    assert TOKEN not in found.text + found.hint + found.page + found.page_hint
    return found


@pytest.mark.parametrize(
    ("profile", "kind", "text", "page"),
    [
        (
            "gitlab-full",
            "gitlab",
            "Works: GitLab, signed in as ivan.petrov, may clone and push.",
            "Works: signed in as ivan.petrov, may clone and push.",
        ),
        (
            "gitlab-api-only",
            "gitlab",
            "Works: GitLab, signed in as ivan.petrov, may clone and push.",
            "Works: signed in as ivan.petrov, may clone and push.",
        ),
        (
            "gitlab-git",
            "gitlab",
            "Works: GitLab, signed in as ivan.petrov, may clone and push; glab cannot open "
            "merge requests: the token lacks api.",
            "Works: signed in as ivan.petrov, may clone and push; glab cannot open merge "
            "requests: the token lacks api.",
        ),
        (
            "gitlab",
            "gitlab",
            "Works: GitLab, signed in as ivan.petrov; the token's rights are not checked.",
            "Works: signed in as ivan.petrov; the token's rights are not checked.",
        ),
        (
            "github-repo",
            "github",
            "Works: GitHub, signed in as ivan.petrov, may clone and push.",
            "Works: signed in as ivan.petrov, may clone and push.",
        ),
        (
            "github",
            "github",
            "Works: GitHub, signed in as ivan.petrov; the token's rights are not checked.",
            "Works: signed in as ivan.petrov; the token's rights are not checked.",
        ),
    ],
)
def test_a_check_of_a_server_that_works(serve, lado_home, profile, kind, text, page):
    server = serve(profile, token=TOKEN)
    _saved(server.url, kind)
    found = _check(server.url)
    assert (found.outcome, found.kind.name, found.login) == ("ok", kind, fake.LOGIN)
    assert (found.text, found.hint, found.page, found.was_checked) == (text, "", page, True)
    assert found.rights_checked is ("rights are not checked" not in text)


@pytest.mark.parametrize(
    ("profile", "kind", "title"),
    [
        ("gitlab-refuses", "gitlab", "GitLab"),
        ("gitlab-revoked", "gitlab", "GitLab"),
        ("gitlab-expired", "gitlab", "GitLab"),
        ("github-refuses", "github", "GitHub"),
    ],
)
def test_a_check_of_a_refused_token(serve, lado_home, profile, kind, title):
    server = serve(profile)
    before = _saved(server.url, kind)
    found = _check(server.url)
    assert found.outcome == "token_refused"
    assert found.text == f"{title} refused the token: it expired or was revoked"
    assert found.hint == f"replace it: lado git-server add {server.url} --token"
    assert found.page == f"{title} refused the token: it expired or was revoked."
    assert state.git_servers() == [before]  # a failed check changes nothing
    assert (lado_home / "git-servers" / before.id / "token").read_text() == TOKEN


@pytest.mark.parametrize(
    ("profile", "kind", "missing", "can", "scopes"),
    [
        (
            "gitlab-read",
            "gitlab",
            "write_repository",
            "clone but not push",
            "scope api",
        ),
        (
            "gitlab-no-repo",
            "gitlab",
            "read_repository, write_repository",
            "neither clone nor push",
            "scope api",
        ),
        ("github-no-repo", "github", "repo", "neither clone nor push", "scope repo"),
        ("github-no-scopes", "github", "repo", "neither clone nor push", "scope repo"),
    ],
)
def test_a_check_of_a_token_without_a_right(serve, lado_home, profile, kind, missing, can, scopes):
    server = serve(profile, token=TOKEN)
    before = _saved(server.url, kind, login=None)
    found = _check(server.url)
    assert (found.outcome, found.missing_scopes) == ("scopes_missing", tuple(missing.split(", ")))
    assert found.text == f"the token lacks {missing}: agents can {can}"
    assert found.hint == (
        f"replace it with a token with the {scopes}: lado git-server add {server.url} --token"
    )
    assert found.page == f"The token lacks {missing}."
    assert found.page_hint == f"Agents can {can} with it. Make one with the {scopes}."
    assert state.git_servers() == [before]  # not ok: no login saved


def test_a_check_of_a_gitlab_token_without_read_api_names_it(serve, lado_home):
    # Saved with --kind, unchecked; its user API refuses a token without read_api.
    server = serve("gitlab-scope")
    before = _saved(server.url, login=None)
    found = _check(server.url)
    assert (found.outcome, found.missing_scopes) == ("scopes_missing", ("read_api",))
    assert found.text == "GitLab takes the token, but it lacks the scope read_api"
    assert found.hint == (
        f"replace it with a token with the scope api: lado git-server add {server.url} --token"
    )
    assert found.page == "The token lacks read_api."
    assert found.page_hint == "LADO asks the server's API with it. Make one with the scope api."
    assert state.git_servers() == [before]


def test_a_check_of_a_server_that_does_not_answer(serve, lado_home, monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    server = serve("hang")
    _saved(server.url)
    found = _check(server.url)
    assert found.outcome == "no_answer"
    assert found.text == f"127.0.0.1:{server.port} does not answer: it did not answer in 1 s"
    assert found.hint == (
        "check that this computer reaches it: the company VPN or proxy; with LADO in Docker, "
        "its container"
    )
    assert found.page == "No answer in 1 seconds."
    assert found.page_hint == (
        "Check that LADO's computer reaches the server: the company VPN or proxy; with LADO "
        "in Docker, its container."
    )


def test_a_check_of_a_name_not_found(lado_home):
    _saved("https://gitlab.invalid")
    found = _check("gitlab.invalid")
    assert found.outcome == "no_answer"
    assert found.text == "gitlab.invalid does not answer: the name is not found"
    assert found.page == "No answer: the name is not found."


def test_a_check_of_an_untrusted_certificate(serve, lado_home, tmp_path):
    server = serve("gitlab", certificate=fake.make_certificate(tmp_path))
    _saved(server.url)
    found = _check(server.url)
    assert found.outcome == "cert_untrusted"
    assert found.text == f"the certificate of {server.url} is not trusted"
    assert found.hint == (
        "trust it in Settings → Git servers (Check), or give its certificate: lado git-server "
        f"certificate {server.url} <file>"
    )
    assert found.page == "The server's certificate is not trusted."
    assert found.offer.own  # a self-signed server offers its own certificate
    assert found.offer.subject == "127.0.0.1"


def test_a_check_of_a_redirect_follows_none(serve, lado_home):
    sso = serve("gitlab")
    server = serve(fake.REDIRECT, location=sso.url + "/login?next=x")
    _saved(server.url)
    found = _check(server.url)
    assert found.outcome == "redirect"
    assert found.text == f"it redirects to {sso.url}/login: add that address instead"
    assert found.page == f"It redirects to {sso.url}/login: add that address instead."
    assert (found.hint, sso.requests) == ("", [])


def test_a_check_of_another_kind(serve, lado_home):
    server = serve("gitlab", token=TOKEN)
    before = _saved(server.url, "github")
    found = _check(server.url)
    assert (found.outcome, found.kind.name) == ("other_kind", "github")
    assert found.text == "it answers as GitLab, not GitHub: remove it and add it again"
    assert found.hint == (
        f"lado git-server remove {server.url}, then lado git-server add {server.url} --token"
    )
    assert found.page == "It answers as GitLab, not GitHub: remove it and add it again."
    assert state.git_servers() == [before]


def test_a_check_of_neither_kind(serve, lado_home):
    server = serve("neither")
    _saved(server.url)
    found = _check(server.url)
    assert found.outcome == "unrecognised"
    assert found.text == "it answers as neither GitHub nor GitLab"
    assert found.page == "It answers as neither GitHub nor GitLab."


def test_a_check_of_no_saved_server_asks_nothing(serve, lado_home):
    server = serve("gitlab")
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check(git_servers.address(server.url))
    assert str(raised.value) == f"{server.url} is no saved git server"
    assert raised.value.hint == "see them: lado git-server list"
    assert server.requests == []


def test_a_check_with_its_token_file_missing_asks_nothing(serve, lado_home):
    server = serve("gitlab")
    saved = _saved(server.url)
    (lado_home / "git-servers" / saved.id / "token").unlink()
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check(git_servers.address(server.url))
    assert str(raised.value) == f"the token file of {server.url} is missing"
    assert raised.value.hint == f"replace it: lado git-server add {server.url} --token"
    assert raised.value.page == "Its token file is missing."
    assert server.requests == []


def test_a_passing_check_saves_the_login_of_one_saved_without_a_check(serve, lado_home):
    server = serve("gitlab-full", token=TOKEN)
    before = _saved(server.url, login=None)
    found = _check(server.url)
    assert (found.outcome, found.was_checked) == ("ok", False)
    assert found.page == "Works: GitLab, signed in as ivan.petrov."
    [after] = state.git_servers()
    assert (after.id, after.login, after.kind) == (before.id, fake.LOGIN, "gitlab")
    assert (lado_home / "git-servers" / before.id / "token").read_text() == TOKEN


def test_a_first_check_of_a_token_for_git_alone_says_what_glab_cannot(serve, lado_home):
    server = serve("gitlab-git", token=TOKEN)
    _saved(server.url, login=None)
    found = _check(server.url)
    assert (found.outcome, found.tool_missing) == ("ok", ("api",))
    assert found.page == (
        "Works: GitLab, signed in as ivan.petrov; glab cannot open merge requests: the token "
        "lacks api."
    )


def test_a_check_without_save_login_writes_nothing(serve, lado_home):
    server = serve("gitlab-full", token=TOKEN)
    before = _saved(server.url, login=None)
    found = git_servers.check(git_servers.address(server.url), save_login=False)
    assert (found.outcome, found.login) == ("ok", fake.LOGIN)
    assert found.text == "Works: GitLab, signed in as ivan.petrov, may clone and push."
    assert state.git_servers() == [before]


def test_a_check_keeps_the_author_and_writes_no_removed_server_back(serve, lado_home, monkeypatch):
    server = serve("gitlab-full", token=TOKEN)
    saved = _saved(server.url, login="old")
    state.set_git_server_author(saved.id, "A", "a@b")
    assert _check(server.url).outcome == "ok"
    [after] = state.git_servers()
    assert (after.login, after.author_name) == (fake.LOGIN, "A")
    ask = git_servers._ask_kinds

    def removed_meanwhile(at, token, certificate=None):
        answers = ask(at, token, certificate)
        state.remove_git_server(saved.id)
        return answers

    monkeypatch.setattr(git_servers, "_ask_kinds", removed_meanwhile)
    assert _check(server.url).outcome == "ok"
    assert state.git_servers() == []


def test_a_check_finds_the_server_by_any_form_of_its_address(lado_home):
    _saved("https://gitlab.invalid")
    for text in ("gitlab.invalid.", "GitLab.Invalid", "https://gitlab.invalid:443/"):
        assert git_servers.check(git_servers.address(text)).outcome == "no_answer"


# The folder of the tokens.


def test_the_folder_goes_with_the_last_server(lado_home):
    _save("gitlab.corp.ru")
    other, _ = _save("git.lan")
    git_servers.remove(git_servers.address("gitlab.corp.ru"))
    assert [p.name for p in (lado_home / "git-servers").iterdir()] == [other.id]
    git_servers.remove(git_servers.address("git.lan"))
    assert not (lado_home / "git-servers").exists()


def test_a_folder_that_cannot_be_removed_warns(lado_home):
    _save()
    (lado_home / "git-servers" / "notes.txt").write_text("the human's")
    removed, warning = git_servers.remove_host("gitlab.corp.ru")
    assert removed.address == "https://gitlab.corp.ru"
    assert state.git_servers() == []
    assert warning == f"could not remove {lado_home / 'git-servers'}: directory not empty"
    assert [p.name for p in (lado_home / "git-servers").iterdir()] == ["notes.txt"]


def test_a_token_folder_that_cannot_be_removed_warns(lado_home):
    saved, _ = _save()
    (lado_home / "git-servers" / saved.id / "notes.txt").write_text("the human's")
    removed, warning = git_servers.remove_host("gitlab.corp.ru")
    assert (removed.id, state.git_servers()) == (saved.id, [])
    folder = lado_home / "git-servers" / saved.id
    assert warning == f"could not remove {folder}: directory not empty"
    assert not (folder / "token").exists()


def test_a_removal_of_one_of_two_does_not_warn(lado_home):
    _save()
    _save("git.lan")
    assert git_servers.remove_host("gitlab.corp.ru")[1] is None


def test_an_add_whose_folder_goes_under_it_writes_again(lado_home, monkeypatch):
    # The last server's removal takes git-servers/ between the add's opening of it and the
    # making of the new server's folder in it.
    mkdir = os.mkdir
    taken = []

    def racing(name, mode=0o777, *, dir_fd=None):
        if dir_fd is not None and not taken:
            taken.append(name)
            os.rmdir(lado_home / "git-servers")
        return mkdir(name, mode, dir_fd=dir_fd)

    lado_home.mkdir(exist_ok=True)
    (lado_home / "git-servers").mkdir()
    monkeypatch.setattr(os, "mkdir", racing)
    saved, _ = _save()
    assert taken
    assert (lado_home / "git-servers" / saved.id / "token").read_text() == TOKEN


# The address asked without the token.


def _credentials(server) -> list[str]:
    return [
        name
        for request in server.requests
        for name in request.headers
        if name.lower() in ("private-token", "authorization")
    ]


@pytest.mark.parametrize(
    ("profile", "token", "kind"),
    [
        ("gitlab", TOKEN, "gitlab"),  # asks for a token: GitLab's 401
        ("github", TOKEN, "github"),  # GitHub's 401
        ("gitlab", None, "gitlab"),  # answers its user even without one
        ("github", None, "github"),
        ("gitlab-refuses", None, "gitlab"),
        ("gitlab-github-hangs", None, "gitlab"),
    ],
)
def test_the_hint_tells_a_kind_without_a_credential(serve, monkeypatch, profile, token, kind):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    server = serve(profile, token=token)
    found = git_servers.hint(git_servers.address(server.url))
    assert (found.kind.name, found.choose, found.why) == (kind, False, None)
    assert server.paths() == [fake.GITHUB, fake.GITLAB]
    assert _credentials(server) == []


@pytest.mark.parametrize(
    ("profile", "why"),
    [
        ("neither", "{root} answers as neither GitHub nor GitLab"),
        ("both", "{root} answers as GitHub and as GitLab"),
        ("hang", "No answer in 1 seconds."),
    ],
)
def test_the_hint_asks_for_the_kind_of_one_it_cannot_tell(serve, monkeypatch, profile, why):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    server = serve(profile, token=TOKEN if profile == "both" else None)
    at = git_servers.address(server.url)
    started = time.monotonic()
    found = git_servers.hint(at)
    assert time.monotonic() - started < 3
    assert (found.kind, found.choose) == (None, True)
    assert found.why is not None
    assert found.why.page == why.format(root=at.root, key=at.key)
    assert found.why.page_hint == git_servers.PAGE_KIND_HINT
    assert _credentials(server) == []


def test_gitlab_com_refusing_github_s_path_too_is_told_gitlab(serve):
    # gitlab.com answers GitLab's 401 on any path of its API, GitHub's included.
    server = serve("gitlab-com", token=TOKEN)
    at = git_servers.address(server.url)
    found = git_servers.hint(at)
    assert (found.kind.name, found.choose, found.why) == ("gitlab", False, None)
    refused = _refused(server.url, token="glpat-WRONG")
    assert str(refused) == f"GitLab at {server.url} refuses the token"
    assert refused.hint == (
        f"make a token at {server.url}/-/user_settings/personal_access_tokens (scope api)"
    )
    checked = git_servers.probe(at, TOKEN)
    assert (checked.kind.name, checked.login) == ("gitlab", fake.LOGIN)


def test_github_s_refusal_is_told_by_its_documentation_link():
    from lado.model_servers import Answer

    def answer(body):
        return Answer(status=401, body=body)

    github, gitlab = git_kinds.by_name("github"), git_kinds.by_name("gitlab")
    assert github.refusal(answer(fake.GITHUB_401.body)) == "refuses the token"
    assert github.refusal(answer(fake.GITLAB_401.body)) is None
    assert gitlab.refusal(answer(fake.GITLAB_401.body)) == "refuses the token"
    assert gitlab.refusal(answer(fake.GITHUB_401.body)) is None


def test_the_hint_refuses_a_server_that_sends_elsewhere(serve):
    server = serve(fake.REDIRECT, location="https://sso.example/login")
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.hint(git_servers.address(server.url))
    assert str(raised.value) == (
        f"{server.url} sends to https://sso.example/login; give the server's own address"
    )
    assert raised.value.field == "address"


def test_a_request_without_a_token_has_no_credential_header():
    for kind in git_kinds.KINDS:
        url, headers = kind.request("https://git.lan", None)
        assert url == "https://git.lan" + kind.path
        assert headers == {}


# The page's words.


def _page_lines(refused: git_servers.Refused) -> str:
    return refused.page + " " + refused.page_hint


@pytest.mark.parametrize(
    ("profile", "kind", "field", "page_hint"),
    [
        ("gitlab-refuses", None, "token", None),
        ("gitlab-scope", None, "token", None),
        ("both", None, "kind", ""),
        ("gitlab", "github", "kind", ""),
        ("neither", None, "address", git_servers.PAGE_KIND_HINT),
        ("hang", None, "address", git_servers.PAGE_KIND_HINT),
    ],
)
def test_each_probe_refusal_has_its_field_and_page_words(
    serve, monkeypatch, profile, kind, field, page_hint
):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    server = serve(profile)
    refused = _refused(server.url, kind=kind)
    assert refused.field == field
    if page_hint is not None:
        assert refused.page_hint == page_hint
    assert "lado " not in _page_lines(refused) and "--" not in _page_lines(refused)


def test_the_page_words_of_the_add_form(serve, monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    for profile, title in (
        ("gitlab-refuses", "GitLab"),
        ("gitlab-revoked", "GitLab"),
        ("github-refuses", "GitHub"),
    ):
        refused = _refused(serve(profile).url)
        assert refused.page == f"{title} refused this token: copy it whole or make a new one."
        assert refused.page_hint == ""
    assert _refused(serve("gitlab-scope").url).page.endswith("lacks the scope read_api")
    silent = _refused(serve("hang").url)
    assert (silent.page, silent.page_hint) == (
        "No answer in 1 seconds.",
        git_servers.PAGE_KIND_HINT,
    )
    assert _refused("gitlab.invalid").page == "No answer: the name is not found."
    assert git_servers.PAGE_KIND_HINT == "Choose its kind to save it without a check."


def test_both_kinds_on_the_page_say_choose(serve):
    server = serve("both")
    assert _refused(server.url).page == (
        f"{server.url} answers as GitHub and as GitLab; choose its kind"
    )


def test_a_redirect_is_refused_under_the_address(serve):
    server = serve(fake.REDIRECT, location="https://sso.example/login")
    refused = _refused(server.url)
    assert (refused.field, refused.page_hint) == ("address", "")


def test_the_other_refusals_have_their_fields(lado_home, tmp_path):
    def refusal(call, *args) -> git_servers.Refused:
        with pytest.raises(git_servers.Refused) as raised:
            call(*args)
        assert "lado " not in _page_lines(raised.value)
        assert "--" not in _page_lines(raised.value)
        return raised.value

    assert refusal(git_servers.check_kind, git_servers.address("github.com"), "github").field == (
        "kind"
    )
    for token in ("", "a\nb"):
        assert refusal(git_servers.check_token, token).field == "token"
    old = refusal(git_servers.check_git, _fake_git(tmp_path, "2.30.1"))
    assert (old.field, old.page) == (
        "",
        "git 2.30.1 is older than 2.31, which git servers need; update git",
    )
    gone = refusal(git_servers.remove, git_servers.address("git.lan"))
    assert (gone.field, gone.page_hint) == ("address", "")


def test_an_address_with_a_user_names_the_token_field_on_the_page():
    with pytest.raises(git_servers.BadAddress) as raised:
        git_servers.address("https://me:pw@git.lan")
    assert raised.value.page == (
        "a git server's address holds no user or password; put the token in Token"
    )


# The commit author.

NAME_EMPTY = "the author's name is empty"
NAME_CHARS = "the author's name holds no < or > or line break"
NOT_EMAIL = "not an email address: name@host"


@pytest.mark.parametrize(
    ("name", "email", "text", "field"),
    [
        ("", "a@b", NAME_EMPTY, "name"),
        (" \t ", "a@b", NAME_EMPTY, "name"),
        ("Ivan <boss>", "a@b", NAME_CHARS, "name"),
        ("Ivan>", "a@b", NAME_CHARS, "name"),
        ("Ivan\nPetrov", "a@b", NAME_CHARS, "name"),
        ("Ivan\x7fPetrov", "a@b", NAME_CHARS, "name"),
        ("I" * 257, "a@b", "the author's name is longer than 256 characters", "name"),
        ("Ivan", "", NOT_EMAIL, "email"),
        ("Ivan", "ivan.petrov", NOT_EMAIL, "email"),
        ("Ivan", "@corp.ru", NOT_EMAIL, "email"),
        ("Ivan", "ivan@", NOT_EMAIL, "email"),
        ("Ivan", "ivan@corp@ru", NOT_EMAIL, "email"),
        ("Ivan", "ivan petrov@corp.ru", NOT_EMAIL, "email"),
        ("Ivan", "<ivan@corp.ru>", NOT_EMAIL, "email"),
        ("Ivan", "ivan\x01@corp.ru", NOT_EMAIL, "email"),
        ("Ivan", "a@" + "b" * 255, "the author's email is longer than 256 characters", "email"),
    ],
)
def test_an_author_refused(name, email, text, field):
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check_author(name, email)
    assert (str(raised.value), raised.value.field) == (text, field)


def test_an_author_is_trimmed_and_may_be_256_characters_long():
    assert git_servers.check_author("  Ivan Petrov ", " ivan@corp.ru\n") == (
        "Ivan Petrov",
        "ivan@corp.ru",
    )
    long = ("И" * 256, "a@" + "b" * 254)
    assert git_servers.check_author(*long) == long


AUTHOR_KEY = "includeIf.hasconfig:remote.*.url:{}.path"
GITLAB_CORP = "[gG][iI][tT][lL][aA][bB].[cC][oO][rR][pP].[rR][uU]"
CORP = "[cC][oO][rR][pP].[rR][uU]"


@pytest.mark.parametrize(
    ("address", "host", "globs"),
    [
        (
            "https://gitlab.corp.ru",
            "gitlab.corp.ru",
            [
                f"https://{GITLAB_CORP}/**",
                f"https://*@{GITLAB_CORP}/**",
                f"https://{GITLAB_CORP}:443/**",
                f"https://*@{GITLAB_CORP}:443/**",
                "git@gitlab.corp.ru:*",
                "git@gitlab.corp.ru:*/**",
                "ssh://git@gitlab.corp.ru/**",
                "ssh://git@gitlab.corp.ru:22/**",
            ],
        ),
        (
            "https://corp.ru:8443/gitlab",
            "corp.ru:8443",
            [
                f"https://{CORP}:8443/gitlab/**",
                f"https://*@{CORP}:8443/gitlab/**",
                "git@corp.ru:*",
                "git@corp.ru:*/**",
                "ssh://git@corp.ru/**",
                "ssh://git@corp.ru:22/**",
            ],
        ),
        (
            "http://[::1]:8080",
            "[::1]:8080",
            [
                "http://\\[::1\\]:8080/**",
                "http://*@\\[::1\\]:8080/**",
                "git@\\[::1\\]:*",
                "git@\\[::1\\]:*/**",
                "ssh://git@\\[::1\\]/**",
                "ssh://git@\\[::1\\]:22/**",
            ],
        ),
        (
            "http://git.lan",
            "git.lan",
            [
                "http://[gG][iI][tT].[lL][aA][nN]/**",
                "http://*@[gG][iI][tT].[lL][aA][nN]/**",
                "http://[gG][iI][tT].[lL][aA][nN]:80/**",
                "http://*@[gG][iI][tT].[lL][aA][nN]:80/**",
                "git@git.lan:*",
                "git@git.lan:*/**",
                "ssh://git@git.lan/**",
                "ssh://git@git.lan:22/**",
            ],
        ),
        (
            "https://corp.ru/a*b[c]",
            "corp.ru",
            [
                f"https://{CORP}/a\\*b\\[c\\]/**",
                f"https://*@{CORP}/a\\*b\\[c\\]/**",
                f"https://{CORP}:443/a\\*b\\[c\\]/**",
                f"https://*@{CORP}:443/a\\*b\\[c\\]/**",
                "git@corp.ru:*",
                "git@corp.ru:*/**",
                "ssh://git@corp.ru/**",
                "ssh://git@corp.ru:22/**",
            ],
        ),
    ],
)
def test_the_author_entries_of_a_server(tmp_path, address, host, globs):
    path = tmp_path / "a1.gitconfig"
    entries = git_servers.author_entries(_server(address=address, host=host), path)
    assert entries == [(AUTHOR_KEY.format(glob), str(path)) for glob in globs]


def test_the_author_entries_come_after_their_servers_own(lado_home, tmp_path):
    servers = [_server(), _server("b2", "https://g.lan", "g.lan")]
    path = tmp_path / "a1.gitconfig"
    without = _entries(git_servers.variables({}, servers))
    entries = _entries(git_servers.variables({}, servers, authors={"a1": path}))
    assert entries == [
        *without[:5],
        *git_servers.author_entries(servers[0], path),
        *without[5:],
    ]
    assert _entries(git_servers.variables({}, servers, authors={})) == without


def _with_author(server, name, email):
    return dataclasses.replace(server, author_name=name, author_email=email)


@pytest.fixture
def two_authors(git_env, tmp_path, lado_home):
    """git's environment with the variables of two servers with authors, the human's own
    author in ~/.gitconfig."""
    (tmp_path / "home" / ".gitconfig").write_text(
        "[user]\n\tname = Human\n\temail = human@home.example\n"
    )
    servers = [
        _with_author(_server(), "A One", "a1@corp.ru"),
        _with_author(_server("b2", "https://corp.ru/gitlab", "corp.ru"), "B Two", "b2@corp.ru"),
    ]
    authors = git_servers.author_files(tmp_path / "authors", servers)
    return git_env | git_servers.variables(git_env, servers, authors=authors)


def _author(repo, env) -> str:
    def value(key):
        return subprocess.run(
            ["git", "-C", str(repo), "config", key], env=env, capture_output=True, text=True
        ).stdout.strip()

    return f"{value('user.name')} <{value('user.email')}>"


A_ONE, B_TWO, HUMAN = "A One <a1@corp.ru>", "B Two <b2@corp.ru>", "Human <human@home.example>"


@pytest.mark.parametrize(
    ("remote", "author"),
    [
        ("https://gitlab.corp.ru/team/app.git", A_ONE),
        ("https://oauth2@gitlab.corp.ru/team/app.git", A_ONE),
        ("https://GitLab.Corp.ru/team/app.git", A_ONE),
        ("https://gitlab.corp.ru:443/team/app.git", A_ONE),
        ("https://oauth2@GITLAB.CORP.RU:443/team/app.git", A_ONE),
        ("https://gitlab.corp.ru:4430/team/app.git", HUMAN),
        ("https://gitlab.corp.rux/team/app.git", HUMAN),
        ("https://GitLab.Corp.ru.evil/team/app.git", HUMAN),
        ("https://Corp.RU/gitlab/team/app.git", B_TWO),
        ("https://corp.ru:443/gitlab/team/app.git", B_TWO),
        ("https://corp.ru/GitLab/team/app.git", HUMAN),  # a path keeps its case
        ("http://gitlab.corp.ru/team/app.git", HUMAN),  # another scheme: another origin
        ("git@gitlab.corp.ru:app.git", A_ONE),
        ("git@gitlab.corp.ru:team/app.git", A_ONE),
        ("git@gitlab.corp.ru:group/sub/app.git", A_ONE),
        ("ssh://git@gitlab.corp.ru/team/app.git", A_ONE),
        ("ssh://git@gitlab.corp.ru:22/team/app.git", A_ONE),
        ("https://corp.ru/gitlab/team/app.git", B_TWO),
        ("git@corp.ru:team/app.git", B_TWO),
        ("https://gitlab.corp.ru.evil/team/app.git", HUMAN),
        ("git@gitlab.corp.ru.evil:team/app.git", HUMAN),
        ("https://gitlab.corp.ru:8443/team/app.git", HUMAN),
        ("ssh://git@gitlab.corp.ru:2222/team/app.git", HUMAN),
        ("https://corp.ru/gitlabX/team/app.git", HUMAN),
        ("https://corp.ru/team/app.git", HUMAN),
        ("https://evil.example/gitlab.corp.ru/app.git", HUMAN),
        ("https://evil.example/https://gitlab.corp.ru/app.git", HUMAN),
    ],
)
def test_git_takes_the_author_by_the_remote(two_authors, tmp_path, remote, author):
    repo = _repo(tmp_path, two_authors, remote)
    assert _author(repo, two_authors) == author


@pytest.mark.parametrize(
    ("remote", "author"),
    [
        ("http://[::1]:8080/team/app.git", "Six <six@lan>"),
        ("git@[::1]:team/app.git", "Six <six@lan>"),
        ("http://[::2]:8080/team/app.git", HUMAN),
    ],
)
def test_git_takes_the_author_of_an_ipv6_server(git_env, tmp_path, lado_home, remote, author):
    (tmp_path / "home" / ".gitconfig").write_text(
        "[user]\n\tname = Human\n\temail = human@home.example\n"
    )
    servers = [
        _with_author(_server(address="http://[::1]:8080", host="[::1]:8080"), "Six", "six@lan")
    ]
    authors = git_servers.author_files(tmp_path / "authors", servers)
    env = git_env | git_servers.variables(git_env, servers, authors=authors)
    assert _author(_repo(tmp_path, env, remote), env) == author


def test_the_servers_author_wins_over_the_repositorys_own(two_authors, tmp_path):
    repo = _repo(tmp_path, two_authors, "git@gitlab.corp.ru:team/app.git")
    for key, value in (("user.name", "Local"), ("user.email", "local@repo.example")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], env=two_authors, check=True)
    assert _author(repo, two_authors) == A_ONE


def test_a_repository_without_a_remote_keeps_the_humans_author(two_authors, tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], env=two_authors, check=True)
    assert _author(repo, two_authors) == HUMAN


@pytest.mark.parametrize(
    "name", ['Ivan "the" Petrov', "back\\slash", "hash # and; semicolon", "  inner  spaces"]
)
def test_the_author_file_holds_the_name_and_email_alone(tmp_path, name):
    previous = os.umask(0)
    try:
        [(id, path)] = git_servers.author_files(
            tmp_path / "authors", [_with_author(_server(), name, "i@corp.ru")]
        ).items()
    finally:
        os.umask(previous)
    assert (id, path) == ("a1", tmp_path / "authors" / "a1.gitconfig")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    listed = subprocess.run(
        ["git", "config", "--file", str(path), "--list"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert listed == f"user.name={name}\nuser.email=i@corp.ru\n"


def test_a_failed_author_write_leaves_no_temp_file(tmp_path, monkeypatch):
    def broken(source, target):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(OSError, match="No space left"):
        git_servers.author_files(tmp_path / "authors", [_with_author(_server(), "A", "a@b")])
    assert list((tmp_path / "authors").iterdir()) == []


def test_only_servers_with_an_author_get_a_file(tmp_path):
    servers = [_server(), _with_author(_server("b2", "https://g.lan", "g.lan"), "B", "b@g.lan")]
    found = git_servers.author_files(tmp_path / "authors", servers)
    assert found == {"b2": tmp_path / "authors" / "b2.gitconfig"}
    assert sorted(p.name for p in (tmp_path / "authors").iterdir()) == ["b2.gitconfig"]
    assert git_servers.author_files(tmp_path / "none", [_server()]) == {}
    assert not (tmp_path / "none").exists()


AUTHOR_OLD = (
    "git 2.34.1 is older than 2.36, which a commit author of a git server needs; update git"
)


def test_an_author_needs_git_2_36(tmp_path):
    old = _fake_git(tmp_path, "2.34.1")
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check_author_git(old)
    assert (str(raised.value), raised.value.page, raised.value.field) == (
        AUTHOR_OLD,
        AUTHOR_OLD,
        "",
    )
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.check_author_git(old, ["https://gitlab.corp.ru"])
    assert str(raised.value) == (
        f"{AUTHOR_OLD}, or clear the author (lado git-server author https://gitlab.corp.ru --clear)"
    )


@pytest.mark.parametrize("version", ["2.36.0", "2.47.1 (Apple Git-154)"])
def test_a_git_for_an_author(tmp_path, version):
    git_servers.check_author_git(_fake_git(tmp_path, version))


def test_set_and_clear_an_author(lado_home):
    saved, _ = _save()
    at = git_servers.address("gitlab.corp.ru")
    server = git_servers.set_author(at, " Ivan Petrov ", "ivan@corp.ru")
    assert (server.id, server.author_name, server.author_email) == (
        saved.id,
        "Ivan Petrov",
        "ivan@corp.ru",
    )
    assert git_servers.author_text(server) == "Ivan Petrov <ivan@corp.ru>"
    assert state.git_servers() == [server]
    again, replaced = _save(token="another")  # a new token keeps the author
    assert replaced and git_servers.author_text(again) == "Ivan Petrov <ivan@corp.ru>"
    cleared = git_servers.clear_author(at)
    assert (cleared.author_name, cleared.author_email) == (None, None)
    assert git_servers.author_text(cleared) is None
    assert git_servers.clear_author(at) == cleared  # once more: nothing to clear


def test_an_author_is_refused_for_no_saved_server(lado_home):
    for call, args in (
        (git_servers.set_author, ("Ivan", "ivan@corp.ru")),
        (git_servers.clear_author, ()),
    ):
        with pytest.raises(git_servers.Refused) as raised:
            call(git_servers.address("git.lan"), *args)
        assert (str(raised.value), raised.value.hint, raised.value.field) == (
            "https://git.lan is no saved git server",
            "see them: lado git-server list",
            "address",
        )


def test_setting_an_author_checks_it_and_git_first(lado_home, tmp_path, monkeypatch):
    _save()
    at = git_servers.address("gitlab.corp.ru")
    with pytest.raises(git_servers.Refused):
        git_servers.set_author(at, "Ivan", "ivan.petrov")
    monkeypatch.setenv("PATH", _fake_git(tmp_path, "2.34.1")["PATH"])
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.set_author(at, "Ivan", "ivan@corp.ru")
    assert str(raised.value) == AUTHOR_OLD
    assert git_servers.author_text(state.git_servers()[0]) is None
    git_servers.clear_author(at)  # clearing needs no git


# A server's certificate.


@pytest.fixture
def corp_ca():
    return made.authority("Corp Root CA")


def test_a_certificate_is_kept_in_the_servers_folder_and_not_in_lado_db(lado_home, corp_ca):
    saved, _ = _save()
    database = (lado_home / "lado.db").read_bytes()
    previous = os.umask(0)
    try:
        git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), corp_ca.pem)
    finally:
        os.umask(previous)
    path = lado_home / "git-servers" / saved.id / "ca.pem"
    assert path.read_text() == corp_ca.pem
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert (lado_home / "lado.db").read_bytes() == database
    assert git_servers.certificate(saved) == corp_ca.pem
    assert sorted(p.name for p in path.parent.iterdir()) == ["ca.pem", "token"]


def test_a_certificate_is_refused_through_a_link(lado_home, tmp_path, corp_ca):
    saved, _ = _save()
    elsewhere = tmp_path / "elsewhere.pem"
    (lado_home / "git-servers" / saved.id / "ca.pem").symlink_to(elsewhere)
    with pytest.raises(git_servers.Refused, match="symbolic link"):
        git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), corp_ca.pem)
    assert not elsewhere.exists()


def test_a_certificate_of_no_saved_server_is_refused(lado_home, corp_ca):
    with pytest.raises(git_servers.Refused, match="is no saved git server"):
        git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), corp_ca.pem)
    assert not (lado_home / "git-servers").exists()


def test_a_new_token_keeps_the_certificate(lado_home, corp_ca):
    saved, _ = _save()
    git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), corp_ca.pem)
    again, replaced = _save(token="glpat-NEW")
    assert replaced and again.id == saved.id
    assert git_servers.certificate(again) == corp_ca.pem


def test_a_save_with_a_certificate_writes_it(lado_home, corp_ca):
    at = git_servers.address("gitlab.corp.ru")
    saved, _ = git_servers.save(at, git_servers.Checked(GITLAB, "ivan"), TOKEN, corp_ca.pem)
    assert git_servers.certificate(saved) == corp_ca.pem


def test_clearing_a_certificate_gives_it_back(lado_home, corp_ca):
    saved, _ = _save()
    at = git_servers.address("gitlab.corp.ru")
    git_servers.set_certificate(at, corp_ca.pem)
    assert git_servers.clear_certificate(at) == corp_ca.pem
    assert git_servers.certificate(saved) is None
    assert git_servers.clear_certificate(at) is None  # once more: nothing to clear
    assert (lado_home / "git-servers" / saved.id / "token").exists()


def test_remove_takes_the_certificate_and_the_folder(lado_home, corp_ca):
    saved, _ = _save()
    git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), corp_ca.pem)
    assert git_servers.remove_host("gitlab.corp.ru").warning is None
    assert not (lado_home / "git-servers").exists()


def test_a_previous_lado_leaves_the_folder_of_a_server_with_a_certificate(
    lado_home, corp_ca, monkeypatch
):
    """The way back: a LADO before certificates removes the token alone, so the folder with
    its ca.pem stays, with the warning."""
    saved, _ = _save()
    git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), corp_ca.pem)
    monkeypatch.setattr(git_servers, "_remove_certificate", lambda id: None)
    removed, warning = git_servers.remove_host("gitlab.corp.ru")
    folder = lado_home / "git-servers" / saved.id
    assert state.git_servers() == []
    assert warning == f"could not remove {folder}: directory not empty"
    assert [p.name for p in folder.iterdir()] == ["ca.pem"]


def test_git_gets_the_certificate_of_a_server_that_has_one(lado_home, corp_ca):
    saved, _ = _save("https://corp.ru:8443/git")
    plain = _entries(git_servers.variables({}, [saved]))
    assert not any("sslCAInfo" in key for key, _ in plain)
    git_servers.set_certificate(git_servers.address("https://corp.ru:8443/git"), corp_ca.pem)
    entries = _entries(git_servers.variables({}, [saved]))
    path = lado_home / "git-servers" / saved.id / "ca.pem"
    assert entries[: len(plain)] == plain
    assert entries[len(plain) :] == [("http.https://corp.ru:8443/git/.sslCAInfo", str(path))]


def test_git_takes_the_certificate_for_the_server_alone(lado_home, corp_ca, git_env):
    saved, _ = _save("https://corp.ru/git")
    git_servers.set_certificate(git_servers.address("https://corp.ru/git"), corp_ca.pem)
    env = git_env | git_servers.variables(git_env, [saved])

    def ca_for(url: str) -> str:
        done = subprocess.run(
            ["git", "config", "--get-urlmatch", "http.sslCAInfo", url],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return done.stdout.strip()

    path = str(lado_home / "git-servers" / saved.id / "ca.pem")
    assert ca_for("https://corp.ru/git/team/app.git") == path
    assert ca_for("https://corp.ru/gitlab/team/app.git") == ""
    assert ca_for("https://other.corp.ru/git/team/app.git") == ""


def _api(start, tmp_path, issuer, profile="gitlab-full"):
    leaf = made.server("localhost", issuer)
    chain = made.write_chain(tmp_path / f"chain-{leaf.certificate.serial_number}", leaf)
    return start(profile, token=TOKEN, certificate=chain)


def test_the_probe_trusts_the_given_certificate_alone(serve, tmp_path, corp_ca):
    server = _api(serve, tmp_path, corp_ca)
    at = git_servers.address(server.url.replace("127.0.0.1", "localhost"))
    assert git_servers.probe(at, TOKEN, certificate=corp_ca.pem).login == "ivan.petrov"
    with pytest.raises(git_servers.Refused, match="is not signed by the given certificate"):
        git_servers.probe(at, TOKEN, certificate=made.authority("Other Root").pem)


def test_a_check_trusts_the_saved_certificate_alone(serve, lado_home, tmp_path, corp_ca):
    server = _api(serve, tmp_path, corp_ca)
    url = server.url.replace("127.0.0.1", "localhost")
    at = git_servers.address(url)
    git_servers.save(at, git_servers.Checked(GITLAB, "ivan.petrov"), TOKEN, corp_ca.pem)
    assert _check(url).outcome == "ok"


# The check of a certificate.

TRUST_HINT = (
    "trust it in Settings → Git servers (Check), or give its certificate: lado git-server "
    "certificate {root} <file>"
)


def _local(server) -> str:
    return server.url.replace("127.0.0.1", "localhost")


def test_a_check_of_an_untrusted_certificate_offers_its_authority(serve, lado_home, tmp_path):
    root = made.authority("Corp Root CA")
    leaf = made.server("localhost", root)
    server = serve("gitlab-full", token=TOKEN, certificate=made.write_chain(tmp_path, leaf, root))
    url = _local(server)
    saved = _saved(url)
    for _ in range(2):  # refusing remembers nothing: the next check offers it again
        found = _check(url)
        assert found.outcome == "cert_untrusted"
        assert found.text == f"the certificate of {url} is not trusted"
        assert found.hint == TRUST_HINT.format(root=url)
        assert found.page == "The server's certificate is not trusted."
        assert found.page_hint == (
            "The server's certificate is signed by an authority LADO's computer does not know, "
            "often your company's own. If you trust it, LADO and agents' git trust it for this "
            "server only; nothing else on the computer changes."
        )
        assert found.offer is not None and found.offer.pem == root.pem
        assert found.before is None
        assert git_servers.certificate(saved) is None
    git_servers.set_certificate(git_servers.address(url), found.offer.pem)
    assert _check(url).outcome == "ok"


def test_a_check_of_a_changed_certificate_names_the_old_one(serve, lado_home, tmp_path):
    old, new = made.authority("Corp Root CA"), made.authority("Corp Root CA G2")
    leaf = made.server("localhost", new)
    server = serve("gitlab-full", token=TOKEN, certificate=made.write_chain(tmp_path, leaf, new))
    url = _local(server)
    saved = _saved(url)
    git_servers.set_certificate(git_servers.address(url), old.pem)
    found = _check(url)
    assert found.outcome == "cert_changed"
    assert found.text == f"the certificate of {url} has changed since you trusted it"
    assert found.hint == TRUST_HINT.format(root=url)
    assert found.page == "The server's certificate has changed since you trusted it."
    assert found.page_hint == (
        "LADO and agents' git trusted the old certificate for this server. Until you trust the "
        "new one, they cannot clone or push here."
    )
    assert (found.before.subject, found.offer.subject) == ("Corp Root CA", "Corp Root CA G2")
    assert git_servers.certificate(saved) == old.pem  # nothing changed


@pytest.mark.parametrize(
    ("leaf_of", "outcome", "text", "hint", "page"),
    [
        (
            lambda root: made.server("other.corp.example", root),
            "cert_name",
            "the certificate of {url} is not issued for localhost: trusting it would not help",
            "ask the server's administrator",
            "The server's certificate is not issued for localhost: trusting it would not help. "
            "Ask the server's administrator.",
        ),
        (
            lambda root: made.server("localhost", root, names=()),
            "cert_name",
            "the certificate of {url} names its host only in the old Common Name field, which "
            "LADO refuses",
            "ask the server's administrator to reissue it",
            "The server's certificate names its host only in the old Common Name field, which "
            "LADO refuses: ask the server's administrator to reissue it.",
        ),
        (
            lambda root: made.server(
                "localhost",
                root,
                not_before=made.NOW - 40 * made.DAY,
                not_after=made.NOW - 10 * made.DAY,
            ),
            "cert_expired",
            "the certificate of {url} expired on {date}",
            "ask the server's administrator to renew it",
            "The server's certificate expired on {date}: ask the server's administrator to "
            "renew it.",
        ),
    ],
)
def test_a_certificate_trust_cannot_fix_gets_no_offer(
    serve, lado_home, tmp_path, leaf_of, outcome, text, hint, page
):
    root = made.authority("Corp Root CA")
    leaf = leaf_of(root)
    server = serve("gitlab-full", token=TOKEN, certificate=made.write_chain(tmp_path, leaf, root))
    url = _local(server)
    _saved(url)
    found = _check(url)
    date = leaf.certificate.not_valid_after_utc.date().isoformat()
    assert found.outcome == outcome
    assert (found.text, found.hint) == (text.format(url=url, date=date), hint)
    assert (found.page, found.page_hint) == (page.format(date=date), "")
    assert found.offer is None


def test_add_of_an_untrusted_certificate_refuses_with_the_offer(serve, lado_home, tmp_path):
    root = made.authority("Corp Root CA")
    leaf = made.server("localhost", root)
    server = serve("gitlab-full", token=TOKEN, certificate=made.write_chain(tmp_path, leaf, root))
    url = _local(server)
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.add(git_servers.address(url), lambda: TOKEN, None, print)
    assert str(raised.value) == f"the certificate of {url} is not trusted"
    assert raised.value.hint == (
        "trust it in Settings → Git servers (Check), or give its certificate: lado git-server "
        f"add {url} --token --certificate <file>"
    )
    assert raised.value.offer.pem == root.pem
    assert raised.value.choose_kind
    assert state.git_servers() == []
    saved, _, checked = git_servers.add(
        git_servers.address(url), lambda: TOKEN, None, print, root.pem
    )
    assert checked.login == fake.LOGIN
    assert git_servers.certificate(saved) == root.pem


def test_add_with_a_certificate_that_does_not_fit_saves_nothing(serve, lado_home, tmp_path):
    root = made.authority("Corp Root CA")
    leaf = made.server("localhost", root)
    server = serve("gitlab-full", token=TOKEN, certificate=made.write_chain(tmp_path, leaf, root))
    url = _local(server)
    other = made.authority("Other Root")
    with pytest.raises(git_servers.Refused) as raised:
        git_servers.add(git_servers.address(url), lambda: TOKEN, None, print, other.pem)
    assert str(raised.value) == f"the certificate of {url} is not signed by the given certificate"
    assert raised.value.offer.pem == root.pem
    assert state.git_servers() == []
    assert not (lado_home / "git-servers").exists()


def test_the_address_check_offers_the_authority(serve, lado_home, tmp_path):
    root = made.authority("Corp Root CA")
    leaf = made.server("localhost", root)
    server = serve("gitlab", certificate=made.write_chain(tmp_path, leaf, root))
    found = git_servers.hint(git_servers.address(_local(server)))
    assert found.choose
    assert found.why.offer.pem == root.pem
    assert found.why.page == "The server's certificate is not trusted."


def test_a_python_that_gives_no_chain_makes_the_check_say_so(
    serve, lado_home, tmp_path, monkeypatch
):
    root = made.authority("Corp Root CA")
    leaf = made.server("localhost", root)
    server = serve("gitlab-full", token=TOKEN, certificate=made.write_chain(tmp_path, leaf, root))
    url = _local(server)
    _saved(url)

    def missing(tls):
        raise AttributeError("get_unverified_chain")

    monkeypatch.setattr(git_certificates, "_unverified", missing)
    found = _check(url)
    key = git_servers.address(url).key
    assert found.outcome == "no_answer"
    assert found.text == (
        f"{key} does not answer: TLS failed (this Python cannot read the server's certificates)"
    )
    assert found.offer is None


# glab's configuration of an agent.

GLAB_TOP = {"check_update": False, "telemetry": False, "git_protocol": "https", "no_prompt": True}


def _glab(servers, folder):
    found = git_servers.glab_variables(servers, folder)
    assert found == {"GLAB_CONFIG_DIR": str(folder)}
    text = (folder / "config.yml").read_text()
    assert TOKEN not in text
    return yaml.safe_load(text)


def _header(server):
    return [{"name": "PRIVATE-TOKEN", "valueFromCommand": git_servers.glab_command(server)}]


def test_glab_gets_an_entry_per_gitlab_server(lado_home, tmp_path):
    one = _saved("https://gitlab.corp.ru")
    two = _saved("http://git.example:8443/gitlab/")
    _saved("https://ghe.corp.ru", kind="github")
    assert _glab(state.git_servers(), tmp_path / "glab") == {
        **GLAB_TOP,
        "hosts": {
            "gitlab.corp.ru": {"api_protocol": "https", "custom_headers": _header(one)},
            "git.example:8443": {
                "api_protocol": "http",
                "subfolder": "gitlab",
                "custom_headers": _header(two),
            },
        },
    }


def test_glab_without_a_gitlab_server_gets_no_host(lado_home, tmp_path):
    _saved("https://ghe.corp.ru", kind="github")
    assert _glab(state.git_servers(), tmp_path / "glab") == {**GLAB_TOP, "hosts": {}}
    assert _glab([], tmp_path / "none") == {**GLAB_TOP, "hosts": {}}


def test_glab_gets_a_certificate_for_its_server_alone(lado_home, tmp_path, corp_ca):
    one = _saved("https://gitlab.corp.ru")
    _saved("https://git.lan")
    git_servers.set_certificate(git_servers.address("gitlab.corp.ru"), corp_ca.pem)
    hosts = _glab(state.git_servers(), tmp_path / "glab")["hosts"]
    assert hosts["gitlab.corp.ru"]["ca_cert"] == str(git_servers.certificate_file(one.id))
    assert "ca_cert" not in hosts["git.lan"]


def test_glabs_config_is_600_in_a_700_folder_written_whole(lado_home, tmp_path):
    _saved("https://gitlab.corp.ru")
    folder = tmp_path / "glab"
    folder.mkdir(mode=0o755)
    (folder / "config.yml").write_text(f"hosts:\n  gitlab.com:\n    token: {TOKEN}\n")
    previous = os.umask(0)
    try:
        _glab(state.git_servers(), folder)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert stat.S_IMODE((folder / "config.yml").stat().st_mode) == 0o600
    assert sorted(p.name for p in folder.iterdir()) == ["config.yml"]


def test_glabs_header_command_is_lados_python_with_ids_alone(lado_home):
    server = _saved("https://gitlab.corp.ru")
    words = shlex.split(git_servers.glab_command(server))
    assert words[:2] == [sys.executable, "-c"]
    assert words[3:] == [
        "lado.git_credential",
        "--home",
        str(lado_home.absolute()),
        "--server",
        server.id,
        "--user",
        "oauth2",
        "--address",
        "https://gitlab.corp.ru",
        "token",
    ]
    result = subprocess.run(words, capture_output=True, text=True, check=True, timeout=30)
    assert result.stdout == TOKEN + "\n"


# The server's tool, as an agent's launch and lado doctor find it.

GITHUB = git_kinds.by_name("github")


def _tool(tmp_path, name, script) -> dict[str, str]:
    folder = tmp_path / "tools"
    folder.mkdir(exist_ok=True)
    tool = folder / name
    tool.write_text(f"#!/bin/sh\n{script}\n")
    tool.chmod(0o755)
    return {"PATH": str(folder)}


@pytest.mark.parametrize(
    ("kind", "script", "state"),
    [
        (GITLAB, "echo 'glab 1.130.0 (206ebab4f)'", (True, "1.130.0", False)),
        (GITLAB, "echo 'glab 1.80.0 (x)'", (True, "1.80.0", True)),
        (GITLAB, "echo 'glab 1.114.0 (x)'", (True, "1.114.0", False)),
        (GITHUB, "echo 'gh version 2.83.0 (2026-10-01)'", (True, "2.83.0", False)),
        (GITLAB, "true", (True, "", False)),
        # A mise shim with no version set names versions on stderr and fails: no guess.
        (GITLAB, "echo 'mise use -g glab@1.80.0' >&2; exit 1", (True, "", False)),
    ],
)
def test_the_tool_and_its_version(tmp_path, kind, script, state):
    found = git_servers.tool_state(kind, _tool(tmp_path, kind.tool, script))
    assert (found.found, found.version, found.too_old) == state


@pytest.mark.parametrize("kind", [GITLAB, GITHUB])
def test_the_version_is_asked_with_a_config_folder_of_its_own(tmp_path, kind):
    # glab writes into its configuration at any call, --version too: never the human's.
    human = tmp_path / "human-config"
    script = (
        f'echo "${{{kind.config_variable}:-none}}" > "{tmp_path}/used"; '
        f'echo x >> "${{{kind.config_variable}:-{human}}}/config.yml"; '
        "echo 'tool 9.9.9'"
    )
    env = _tool(tmp_path, kind.tool, script) | {kind.config_variable: str(human)}
    found = git_servers.tool_state(kind, env)
    assert found.version == "9.9.9"
    used = (tmp_path / "used").read_text().strip()
    assert used not in ("none", str(human))
    assert not os.path.exists(used)  # a folder of the call's alone, gone after it
    assert not human.exists()


def test_no_tool_on_the_path(tmp_path):
    found = git_servers.tool_state(GITLAB, {"PATH": str(tmp_path)})
    assert (found.found, found.version, found.too_old) == (False, "", False)


def test_a_tool_that_hangs_is_cut_and_fits(tmp_path, monkeypatch):
    monkeypatch.setattr(git_servers, "TOOL_TIMEOUT", 0.5)
    env = _tool(tmp_path, "glab", "exec sleep 30")
    started = time.monotonic()
    found = git_servers.tool_state(GITLAB, env)
    assert time.monotonic() - started < 10
    assert (found.found, found.version, found.too_old) == (True, "", False)


def _state(found=True, version="1.130.0", too_old=False, line=""):
    return git_servers.ToolState(found, version, too_old, line)


LINE_START = (
    "The repository's origin is on GitLab (gitlab.corp.example), a git server LADO signs you in to"
)


def test_the_line_of_a_gitlab_with_glab(lado_home):
    server = _saved("https://gitlab.corp.example")
    assert git_servers.tool_line(server, _state()) == (
        f"{LINE_START}: use `glab` for its merge requests; it is logged in already."
    )


def test_the_line_of_github_com(lado_home):
    server = _saved("https://github.com", kind="github")
    assert git_servers.tool_line(server, _state(version="2.83.0")) == (
        "The repository's origin is on GitHub (github.com), a git server LADO signs you in to: "
        "use `gh` for its pull requests; it is logged in already."
    )


def test_the_line_of_a_missing_tool(lado_home):
    server = _saved("https://gitlab.corp.example")
    assert git_servers.tool_line(server, _state(found=False, version="")) == (
        f"{LINE_START}, but its tool `glab` is not installed here, so you cannot open its "
        "merge requests; tell the human."
    )


def test_the_line_of_an_old_tool(lado_home):
    server = _saved("https://gitlab.corp.example")
    assert git_servers.tool_line(server, _state(version="1.80.0", too_old=True)) == (
        f"{LINE_START}, but `glab` here is 1.80.0, older than 1.114.0, which LADO needs to sign "
        "it in, so you cannot open its merge requests; tell the human."
    )


def test_the_line_without_a_token(lado_home):
    server = _saved("https://gitlab.corp.example")
    (lado_home / "git-servers" / server.id / "token").unlink()
    assert git_servers.tool_line(server, _state(found=False)) == (
        f"{LINE_START}, but LADO has no token for it, so `glab` is not logged in and git cannot "
        "push there; tell the human."
    )


def test_the_line_of_a_github_server_with_a_certificate(lado_home, corp_ca):
    server = _saved("https://ghe.corp.example", kind="github")
    git_servers.set_certificate(git_servers.address("ghe.corp.example"), corp_ca.pem)
    assert git_servers.tool_line(server, _state(version="2.83.0")) == (
        "The repository's origin is on GitHub (ghe.corp.example), a git server LADO signs you "
        "in to: use `gh` for its pull requests; it is logged in already. `gh` does not get the "
        "server's certificate and cannot reach it; git can."
    )


def test_the_line_names_the_port(lado_home):
    server = _saved("https://git.example:8443/gitlab")
    assert git_servers.tool_line(server, _state()).startswith(
        "The repository's origin is on GitLab (git.example:8443), "
    )


def test_the_warnings_of_a_missing_or_old_tool(lado_home):
    gitlab = _saved("https://gitlab.corp.example")
    github = _saved("https://github.com", kind="github")
    missing = _state(found=False, version="")
    assert git_servers.tool_warning(gitlab, missing) == (
        "glab is not on the agents' PATH: agents cannot open merge requests on "
        "https://gitlab.corp.example; install glab 1.114.0 or newer"
    )
    assert git_servers.tool_warning(gitlab, _state(version="1.80.0", too_old=True)) == (
        "glab 1.80.0 is older than 1.114.0, which LADO needs to sign it in to "
        "https://gitlab.corp.example; update glab"
    )
    assert git_servers.tool_warning(github, missing) == (
        "gh is not on the agents' PATH: agents cannot open pull requests on "
        "https://github.com; install gh"
    )
    assert git_servers.tool_warning(gitlab, _state()) is None
