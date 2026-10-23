"""A new session in a project from the UI server's API: the start of kind "project" and
what the New session window's Project way shows (openspec change new-session-in-project).
In process, with FastAPI's test client."""

import os

import pytest
from agent_helpers import init_repo
from fastapi.testclient import TestClient

from lado import projects, runtime, state
from lado.server import app as server_app
from lado.server import auth
from lado.server import launch as server_launch

PORT = 8125
OWN = "http://testserver"


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    """The provider CLIs the server finds: all of them."""
    monkeypatch.setattr(server_launch, "_installed", lambda provider: True)


@pytest.fixture
def shop(tmp_path, monkeypatch, git_config):
    """The workspace <tmp>/ws and the project shop titled Shop with its repositories frontend
    and backend; its folder."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    init_repo(projects.folder("shop") / "frontend")
    init_repo(projects.folder("shop") / "backend")
    return projects.folder("shop")


IN_SHOP = {"kind": "project", "project": "shop", "repo": "frontend"}


def start(client, where=None, **given):
    return client.post("/api/sessions", json={"where": where or IN_SHOP, **given})


# The start


def test_a_start_in_a_project_is_the_clis_call(client, shop, monkeypatch, fake_tmux):
    calls = []
    real = runtime.start_session

    def recorder(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(runtime, "start_session", recorder)
    answer = start(
        client,
        name="fix",
        kits=["default"],
        provider="kilo",
        permission_mode="plan",
        without=["agent:worker"],
        prompt="hello",
        title="Fix it",
    )
    assert answer.status_code == 200, answer.text
    assert calls == [
        (
            (None, "fix", "plan", "kilo", ["default"], ["agent:worker"]),
            {
                "resume": False,
                "prompt": "hello",
                "title": "Fix it",
                "project": "shop",
                "repo_name": "frontend",
            },
        )
    ]


def test_a_start_in_a_project_answers_started(client, shop, fake_tmux):
    answer = start(client, provider="kilo")
    assert answer.status_code == 200, answer.text
    started = answer.json()
    assert started["resumed"] is False
    session = started["session"]
    assert (session["name"], session["repo"], session["project"]) == (
        "shop-frontend",
        str(shop / "frontend"),
        "shop",
    )
    assert state.get_session("shop-frontend").project == "shop"


def _nothing_started(shop):
    assert state.list_sessions() == []


def test_an_unknown_project_or_repository_is_404_with_the_cores_text(client, shop, fake_tmux):
    answer = start(client, {"kind": "project", "project": "nope", "repo": "x"}, provider="kilo")
    assert (answer.status_code, answer.json()["detail"]) == (404, 'unknown project "nope"')
    answer = start(client, {"kind": "project", "project": "shop", "repo": "docs"}, provider="kilo")
    assert (answer.status_code, answer.json()["detail"]) == (
        404,
        "project shop has no repository docs; its repositories: backend, frontend",
    )
    _nothing_started(shop)


def test_a_link_is_400_with_the_cores_text(client, shop, tmp_path, fake_tmux):
    (shop / "lib").symlink_to(init_repo(tmp_path / "lib"))
    answer = start(client, {"kind": "project", "project": "shop", "repo": "lib"}, provider="kilo")
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        f"lib in project shop is a link to {tmp_path / 'lib'}: clone it into {shop} instead",
    )
    _nothing_started(shop)


def test_a_taken_name_is_409(client, shop, fake_tmux):
    runtime.start_session(None, None, None, provider="kilo", project="shop", repo_name="frontend")
    runtime.stop_session("shop-frontend")
    answer = start(client, provider="kilo")
    assert answer.status_code == 409
    detail = answer.json()["detail"]
    assert (detail["status"], detail["repo"]) == ("stopped", str(shop / "frontend"))
    assert detail["message"].startswith(
        f'session "shop-frontend" exists already (stopped, in {shop / "frontend"})'
    )
    assert state.get_session("shop-frontend").stopped_at is not None


@pytest.mark.parametrize(
    "where",
    [
        {**IN_SHOP, "path": "{x}"},
        {"kind": "project", "project": "shop"},
        {"kind": "project", "repo": "frontend"},
        {"kind": "folder", "path": "{x}", "project": "shop"},
        {"kind": "scratch", "path": "{x}", "repo": "frontend"},
        {"kind": "folder"},
    ],
)
def test_a_where_that_does_not_fit_its_kind_is_400(client, shop, tmp_path, fake_tmux, where):
    x = tmp_path / "x"
    where = {key: value.format(x=x) for key, value in where.items()}
    answer = start(client, where, provider="kilo")
    assert answer.status_code == 400, answer.text
    _nothing_started(shop)
    assert not os.path.lexists(x)


def test_an_unknown_kind_is_400_as_before(client, shop):
    answer = start(client, {"kind": "remote", "path": "x"})
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        'where of kind "remote" is not supported yet',
    )


def test_a_start_in_a_project_needs_the_token(client, shop, fake_tmux):
    client.cookies.clear()
    assert start(client, provider="kilo").status_code == 401
    del client.headers["origin"]
    assert start(client, provider="kilo").status_code in (401, 403)
    _nothing_started(shop)

