"""The UI server's API of Settings → Git servers (openspec change git-servers-page): the
human's git servers through lado.server.git_entries over lado.git_servers. In process, with
FastAPI's test client and the fake git APIs of tests/fake_git_api.py."""

from __future__ import annotations

import os
import socket

import fake_git_api as fake
import pytest
from fastapi.testclient import TestClient

from lado import agent_env, git_kinds, git_servers, model_servers, state
from lado.cli import main
from lado.server import app as server_app
from lado.server import auth

PORT = 8127
OWN = "http://testserver"
TOKEN = "glpat-CANARY-3d81b0"  # a canary: no answer, log or file but its own may hold it


def _client(raise_server_exceptions: bool = True) -> TestClient:
    client = TestClient(
        server_app.create_app(auth.token(), PORT),
        raise_server_exceptions=raise_server_exceptions,
    )
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture
def client(lado_home, monkeypatch):
    monkeypatch.setenv(agent_env.SOURCE_VAR, agent_env.INHERIT)
    return _client()


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


def ok(answer):
    assert answer.status_code == 200, answer.text
    assert TOKEN not in answer.text
    return answer.json()


def refused(answer):
    assert answer.status_code == 400, answer.text
    assert TOKEN not in answer.text
    return answer.json()["detail"]


def add(client, address, token=TOKEN, kind=None):
    return client.post("/api/git-servers", json={"address": address, "token": token, "kind": kind})


def check(client, address):
    return ok(client.post("/api/git-servers/check", json={"address": address}))


def _files_holding(root, value: str) -> list[str]:
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink() and value.encode() in p.read_bytes()
    )


# The list.


def test_the_list_with_no_lado_db_makes_none(client, lado_home):
    found = ok(client.get("/api/git-servers"))
    assert found["servers"] == []
    assert [k["name"] for k in found["kinds"]] == ["github", "gitlab"]
    assert found["kinds"][1] == {
        "name": "gitlab",
        "title": "GitLab",
        "token_path": "/-/user_settings/personal_access_tokens",
        "scopes": "scopes read_repository, write_repository, read_api",
    }
    assert not (lado_home / "lado.db").exists()


def test_the_list_is_the_commands(client, serve, capsys, lado_home):
    server = serve("gitlab", token=TOKEN)
    ok(add(client, server.url))
    ok(add(client, f"https://git.lan:{closed_port()}", kind="github"))
    gone = state.git_servers()[1]
    state.set_git_server_author(gone.id, "Ivan Petrov", "ivan@corp.ru")
    (lado_home / "git-servers" / gone.id / "token").unlink()
    asked = len(server.requests)
    rows = ok(client.get("/api/git-servers"))["servers"]
    assert len(server.requests) == asked  # asking none
    capsys.readouterr()
    assert main(["git-server", "list"]) == 0
    printed = [line.split() for line in capsys.readouterr().out.splitlines()[1:]]
    assert [
        [
            r["address"],
            r["kind_title"],
            *(r["login"] or "not checked").split(),
            "yes" if r["has_token"] else "no",
            *(f"{r['author_name']} <{r['author_email']}>" if r["author_name"] else "-").split(),
        ]
        for r in rows
    ] == printed
    assert rows[1]["host"] == gone.host and rows[1]["login"] is None


# Add.


def test_add_gitlab_saves_it_with_its_login(client, serve, lado_home):
    server = serve("gitlab", token=TOKEN)
    added = ok(add(client, server.url))
    assert added["server"] == {
        "address": server.url,
        "host": server.url.removeprefix("http://"),
        "kind": "gitlab",
        "kind_title": "GitLab",
        "login": fake.LOGIN,
        "has_token": True,
        "author_name": None,
        "author_email": None,
    }
    assert added["line"] == f"Saved git server {server.url}: GitLab, signed in as {fake.LOGIN}."
    assert added["replaced"] is False
    assert added["warnings"] == [
        "the token goes to 127.0.0.1 over plain http://, unencrypted; use https:// if the "
        "server has it"
    ]
    assert _files_holding(lado_home, TOKEN) == [f"git-servers/{state.git_servers()[0].id}/token"]


def test_add_github_and_again_replaces(client, serve):
    server = serve("github", token=TOKEN)
    ok(add(client, server.url))
    again = ok(add(client, server.url + "/"))
    assert again["replaced"] is True
    assert again["line"] == (
        f"Replaced git server {server.url}: GitHub, signed in as {fake.LOGIN}."
    )
    assert len(state.git_servers()) == 1


def test_add_with_a_chosen_kind_saves_one_that_does_not_answer(client):
    root = f"https://127.0.0.1:{closed_port()}"
    added = ok(add(client, root, kind="gitlab"))
    assert added["server"]["login"] is None
    assert added["line"] == (
        f"Saved git server {root} as GitLab without a check (it does not answer: the "
        "connection is refused)."
    )


@pytest.mark.parametrize(
    ("address", "field", "message"),
    [
        ("github.com", "address", "github.com is reached through gh's login"),
        ("https://me:pw@git.lan", "address", "holds no user or password; put the token in Token"),
    ],
)
def test_add_refuses_the_address(client, address, field, message):
    detail = refused(add(client, address))
    assert (detail["field"], message in detail["message"]) == (field, True)
    assert state.git_servers() == []


def test_a_wrong_token_is_refused_under_token(client, serve, lado_home):
    server = serve("gitlab-refuses")
    detail = refused(add(client, server.url))
    assert detail["message"] == f"GitLab at {server.url} refuses the token"
    assert detail["hint"] == (
        f"make a token at {server.url}/-/user_settings/personal_access_tokens "
        "(scopes read_repository, write_repository, read_api)"
    )
    assert detail["field"] == "token"
    assert detail["warnings"] == [git_servers.PLAIN_HTTP.format(host="127.0.0.1")]
    assert state.git_servers() == []
    assert _files_holding(lado_home, TOKEN) == []


def test_another_port_of_a_saved_host_name_is_refused_under_address(client, serve):
    server = serve("gitlab", token=TOKEN)
    ok(add(client, server.url))
    other = serve("gitlab", token=TOKEN)
    detail = refused(add(client, other.url))
    assert detail["field"] == "address"
    assert detail["message"].startswith(f"127.0.0.1 already has a git server, {server.url}")
    assert detail["hint"] == "Remove it first if the server moved to this address."
    assert other.requests == []


def test_both_kinds_without_a_choice_are_refused_under_kind(client, serve):
    server = serve("both")
    detail = refused(add(client, server.url))
    assert (detail["field"], detail["message"]) == (
        "kind",
        f"{server.url} answers as GitHub and as GitLab; choose its kind",
    )


def test_the_pages_refusals_name_no_command(client, serve, monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    for profile in ("gitlab-refuses", "both", "neither", "hang"):
        detail = refused(add(client, serve(profile).url))
        assert "lado " not in detail["message"] + detail["hint"]
        assert "--" not in detail["message"] + detail["hint"]


# The token.


def test_an_unreadable_body_repeats_no_token(client):
    for body in (
        {"address": "git.lan", "token": [TOKEN]},
        {"token": TOKEN},
        {"address": 5, "token": TOKEN},
    ):
        answer = client.post("/api/git-servers", json=body)
        assert answer.status_code == 422
        assert TOKEN not in answer.text


def test_an_exception_in_the_probe_journals_no_token(lado_home, monkeypatch, serve):
    monkeypatch.setenv(agent_env.SOURCE_VAR, agent_env.INHERIT)

    def broken(at, token, kind_name=None):
        raise RuntimeError("the probe broke")

    monkeypatch.setattr(git_servers, "probe", broken)
    answer = add(_client(raise_server_exceptions=False), serve("gitlab").url)
    assert answer.status_code == 500
    assert TOKEN not in answer.text
    assert (lado_home / "errors.jsonl").exists()
    assert _files_holding(lado_home, TOKEN) == []


# The check.


def test_check_of_gitlab_hints_its_token_page_with_no_token_sent(client, serve):
    server = serve("gitlab", token=TOKEN)
    found = check(client, server.url + "/")
    assert found == {
        "address": server.url,
        "hint": "gitlab",
        "token_page": f"{server.url}/-/user_settings/personal_access_tokens",
        "scopes": "scopes read_repository, write_repository, read_api",
        "choose_kind": False,
        "unchecked": None,
        "saved": False,
        "refusals": [],
        "warnings": [git_servers.PLAIN_HTTP.format(host="127.0.0.1")],
    }
    for request in server.requests:
        assert "PRIVATE-TOKEN" not in request.headers
        assert "Authorization" not in request.headers


def test_check_of_a_saved_address_says_so(client, serve):
    server = serve("github", token=TOKEN)
    ok(add(client, server.url))
    found = check(client, server.url)
    assert (found["saved"], found["hint"]) == (True, "github")


def test_check_of_one_that_does_not_answer_asks_for_the_kind(client):
    root = f"https://127.0.0.1:{closed_port()}"
    found = check(client, root)
    assert (found["choose_kind"], found["hint"], found["refusals"]) == (True, None, [])
    assert found["unchecked"] == {
        "message": f"{root[8:]} does not answer: the connection is refused",
        "hint": git_servers.PAGE_KIND_HINT,
        "field": "address",
        "warnings": [],
        "choose_kind": True,
    }


def test_check_refuses_a_redirect_with_no_choice(client, serve):
    server = serve(fake.REDIRECT, location="https://sso.example/login")
    found = check(client, server.url)
    assert found["choose_kind"] is False
    assert [r["message"] for r in found["refusals"]] == [
        f"{server.url} sends to https://sso.example/login; give the server's own address"
    ]


def test_check_refuses_the_address_and_its_host_name_asking_no_server(client, serve):
    assert [r["field"] for r in check(client, "github.com")["refusals"]] == ["address"]
    assert check(client, "ftp://git.lan")["refusals"][0]["field"] == "address"
    server = serve("gitlab", token=TOKEN)
    ok(add(client, server.url))
    other = serve("gitlab")
    found = check(client, other.url)
    assert [r["field"] for r in found["refusals"]] == ["address"]
    assert other.requests == []


def test_check_of_nothing_says_nothing_and_makes_no_lado_db(client, lado_home):
    found = check(client, "  ")
    assert (found["address"], found["refusals"]) == (None, [])
    check(client, "github.com")
    assert not (lado_home / "lado.db").exists()


# Remove.


def test_remove_by_host_lists_the_rest(client, serve, lado_home):
    first = serve("gitlab", token=TOKEN)
    ok(add(client, first.url))
    ok(add(client, "https://git.lan", kind="github"))
    host = first.url.removeprefix("http://")
    left = ok(client.delete(f"/api/git-servers/{host}"))
    assert [s["address"] for s in left["servers"]] == ["https://git.lan"]
    ok(client.delete("/api/git-servers/git.lan"))
    assert not (lado_home / "git-servers").exists()
    detail = refused(client.delete("/api/git-servers/git.lan"))
    assert (detail["message"], detail["hint"], detail["field"]) == (
        "git.lan is no saved git server",
        "",
        "address",
    )


def test_an_ipv6_host_is_removed_by_its_key(client):
    ok(add(client, f"https://[::1]:{closed_port()}", kind="gitlab"))
    host = state.git_servers()[0].host
    assert host.startswith("[::1]:")
    assert ok(client.delete(f"/api/git-servers/{host}"))["servers"] == []


# The commit author.


def _saved(client, address="https://git.lan"):
    ok(add(client, address, kind="gitlab"))
    return state.git_servers()[0]


def put_author(client, host, name, email):
    return client.put(f"/api/git-servers/{host}/author", json={"name": name, "email": email})


def test_an_author_is_set_and_cleared_by_host(client, capsys):
    server = _saved(client)
    done = ok(put_author(client, server.host, " Ivan Petrov ", "ivan@corp.ru"))
    assert done["line"] == "Agents commit to https://git.lan as Ivan Petrov <ivan@corp.ru>."
    assert (done["server"]["author_name"], done["server"]["author_email"]) == (
        "Ivan Petrov",
        "ivan@corp.ru",
    )
    [listed] = ok(client.get("/api/git-servers"))["servers"]
    assert listed == done["server"]
    capsys.readouterr()
    main(["git-server", "list"])
    assert capsys.readouterr().out.splitlines()[1].endswith(" Ivan Petrov <ivan@corp.ru>")
    cleared = ok(client.delete(f"/api/git-servers/{server.host}/author"))
    assert cleared["line"] == "Agents commit to https://git.lan with your own git author again."
    assert (cleared["server"]["author_name"], cleared["server"]["author_email"]) == (None, None)
    assert [s.address for s in state.git_servers()] == ["https://git.lan"]  # not removed


def test_an_ipv6_hosts_author(client):
    server = _saved(client, f"https://[::1]:{closed_port()}")
    ok(put_author(client, server.host, "Ivan", "ivan@corp.ru"))
    assert state.git_servers()[0].author_name == "Ivan"
    ok(client.delete(f"/api/git-servers/{server.host}/author"))
    assert state.git_servers()[0].author_name is None


@pytest.mark.parametrize(
    ("name", "email", "field", "message"),
    [
        ("", "ivan@corp.ru", "name", "the author's name is empty"),
        ("Ivan <boss>", "ivan@corp.ru", "name", "the author's name holds no < or > or line break"),
        ("Ivan", "ivan.petrov", "email", "not an email address: name@host"),
    ],
)
def test_an_author_refused_under_its_field(client, name, email, field, message):
    server = _saved(client)
    detail = refused(put_author(client, server.host, name, email))
    assert (detail["message"], detail["field"]) == (message, field)
    assert state.git_servers()[0].author_name is None


def test_an_old_git_refuses_an_author_under_no_field(client, tmp_path, monkeypatch):
    server = _saved(client)
    folder = tmp_path / "old-git"
    folder.mkdir()
    (folder / "git").write_text("#!/bin/sh\necho 'git version 2.34.1'\n")
    (folder / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}:{os.environ['PATH']}")
    detail = refused(put_author(client, server.host, "Ivan", "ivan@corp.ru"))
    assert (detail["message"], detail["field"]) == (
        "git 2.34.1 is older than 2.36, which a commit author of a git server needs; update git",
        "",
    )


def test_the_author_of_no_saved_server_is_refused(client):
    _saved(client)
    for answer in (
        put_author(client, "gitlab.corp.ru", "Ivan", "ivan@corp.ru"),
        client.delete("/api/git-servers/gitlab.corp.ru/author"),
    ):
        detail = refused(answer)
        assert (detail["message"], detail["hint"], detail["field"]) == (
            "gitlab.corp.ru is no saved git server",
            "",
            "address",
        )


# A token's rights at Add, and Add's refusals.


def test_add_of_a_token_without_push_saves_it_with_a_warning(client, serve):
    server = serve("gitlab-read", token=TOKEN)
    added = ok(add(client, server.url))
    assert added["server"]["login"] == fake.LOGIN
    assert added["warning"] == ("The token lacks write_repository: agents can clone but not push.")
    assert added["missing_scopes"] == ["write_repository"]
    assert len(state.git_servers()) == 1
    full = serve("gitlab-full", token=TOKEN)
    added = ok(add(client, full.url.replace("127.0.0.1", "localhost")))
    assert (added["warning"], added["missing_scopes"]) == (None, [])


def test_a_server_that_stops_answering_at_add_offers_the_kind(client, monkeypatch):
    monkeypatch.setattr(model_servers, "TIMEOUT", 1)
    detail = refused(add(client, f"https://127.0.0.1:{closed_port()}"))
    assert (detail["field"], detail["choose_kind"]) == ("address", True)
    assert refused(add(client, "https://gitlab.invalid"))["choose_kind"] is True


def test_a_refused_token_offers_no_kind(client, serve):
    assert refused(add(client, serve("gitlab-refuses").url))["choose_kind"] is False


def test_a_removal_whose_folder_stays_warns(client, lado_home):
    server = _saved(client)
    (lado_home / "git-servers" / "notes.txt").write_text("the human's")
    left = ok(client.delete(f"/api/git-servers/{server.host}"))
    assert left["servers"] == []
    assert left["warning"] == (f"could not remove {lado_home / 'git-servers'}: directory not empty")
    (lado_home / "git-servers" / "notes.txt").unlink()
    _saved(client)
    assert ok(client.delete("/api/git-servers/git.lan"))["warning"] is None


# The check of a saved server.


def post_check(client, host):
    return client.post(f"/api/git-servers/{host}/check")


@pytest.mark.parametrize(
    ("profile", "kind", "outcome", "message", "hint"),
    [
        (
            "gitlab-full",
            "gitlab",
            "ok",
            f"Works: signed in as {fake.LOGIN}, may clone and push.",
            "",
        ),
        (
            "github",
            "github",
            "ok",
            f"Works: signed in as {fake.LOGIN}; the token's rights are not checked.",
            "",
        ),
        (
            "gitlab-refuses",
            "gitlab",
            "token_refused",
            "GitLab refused the token: it expired or was revoked.",
            "",
        ),
        (
            "gitlab-read",
            "gitlab",
            "scopes_missing",
            "The token lacks write_repository.",
            "Agents can clone but not push with it. Make one with the scopes read_repository, "
            "write_repository, read_api.",
        ),
        (
            "gitlab",
            "github",
            "other_kind",
            "It answers as GitLab, not GitHub: remove it and add it again.",
            "",
        ),
        ("neither", "gitlab", "unrecognised", "It answers as neither GitHub nor GitLab.", ""),
    ],
)
def test_the_check_of_a_saved_server(client, serve, profile, kind, outcome, message, hint):
    server = serve(profile, token=TOKEN)
    at = git_servers.address(server.url)
    git_servers.save(at, git_servers.Checked(git_kinds.by_name(kind), "ivan"), TOKEN)
    found = ok(post_check(client, at.key))
    assert (found["outcome"], found["kind"], found["message"], found["hint"]) == (
        outcome,
        kind,
        message,
        hint,
    )
    assert found["was_checked"] is True
    assert found["server"]["address"] == server.url
    if outcome == "ok":
        assert (found["login"], found["server"]["login"]) == (fake.LOGIN, fake.LOGIN)
    if outcome == "scopes_missing":
        assert found["missing_scopes"] == ["write_repository"]


def test_the_check_of_one_saved_without_a_check(client, serve):
    server = serve("gitlab", token=TOKEN)
    ok(add(client, server.url, kind="gitlab"))
    state.save_git_server(state.git_servers()[0].id, server.url, server.url[7:], "gitlab", None)
    found = ok(post_check(client, server.url[7:]))
    assert (found["outcome"], found["was_checked"], found["rights_checked"]) == (
        "ok",
        False,
        False,
    )
    assert found["message"] == f"Works: GitLab, signed in as {fake.LOGIN}."
    assert found["server"]["login"] == fake.LOGIN


def test_the_check_of_no_saved_server_is_404(client, serve):
    answer = post_check(client, "git.lan")
    assert answer.status_code == 404
    detail = answer.json()["detail"]
    assert (detail["message"], detail["field"]) == ("git.lan is no saved git server", "address")


def test_the_check_without_a_token_file_is_422(client, serve, lado_home):
    server = serve("gitlab", token=TOKEN)
    ok(add(client, server.url))
    (lado_home / "git-servers" / state.git_servers()[0].id / "token").unlink()
    asked = len(server.requests)
    answer = post_check(client, server.url[7:])
    assert answer.status_code == 422
    detail = answer.json()["detail"]
    assert (detail["message"], detail["field"]) == ("Its token file is missing.", "")
    assert len(server.requests) == asked


def test_the_check_puts_the_token_in_no_answer_or_log(client, serve, caplog):
    server = serve("gitlab-full", token=TOKEN)
    ok(add(client, server.url))
    refusing = git_servers.address(serve("gitlab-refuses").url.replace("127.0.0.1", "localhost"))
    git_servers.save(refusing, git_servers.Checked(git_kinds.by_name("gitlab"), "ivan"), TOKEN)
    with caplog.at_level("DEBUG"):
        assert ok(post_check(client, server.url[7:]))["outcome"] == "ok"
        found = ok(post_check(client, refusing.key))
        assert found["outcome"] == "token_refused"
        ok(client.get("/api/git-servers"))
    assert TOKEN not in caplog.text
