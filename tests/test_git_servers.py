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

import fake_git_api as fake
import pytest

from lado import git_kinds, git_servers, model_servers, state

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
    """git's environment with its own HOME and global and system configs, no prompt."""
    home = tmp_path / "home"
    home.mkdir()
    system = tmp_path / "gitconfig-system"
    system.write_text("")
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
        "GIT_CONFIG_SYSTEM": str(system),
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
        ("hang", "{key} does not answer: it did not answer in 1 s"),
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
        f"make a token at {server.url}/-/user_settings/personal_access_tokens "
        "(scopes read_repository, write_repository, read_api)"
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

    assert refusal(git_servers.check_not_github, git_servers.address("github.com")).field == (
        "address"
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
