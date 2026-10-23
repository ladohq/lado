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


# What the Project way shows


def project_launch(client, **asked) -> dict:
    answer = client.get("/api/project-launch", params=asked)
    assert answer.status_code == 200, answer.text
    return answer.json()


@pytest.fixture
def acme(shop, git_config):
    """The project acme without a title, with its repository crm."""
    projects.create("acme", None)
    init_repo(projects.folder("acme") / "crm")


def _in_shop(repo: str, **given) -> None:
    runtime.start_session(None, None, None, provider="kilo", project="shop", repo_name=repo)


def test_the_projects_by_title_and_the_first_found_chosen(client, shop, acme):
    shown = project_launch(client)
    assert [(p["id"], p["title"], p["repos"]) for p in shown["projects"]] == [
        ("acme", None, 1),
        ("shop", "Shop", 2),
    ]
    assert (shown["project"], shown["repo"]) == ("acme", "crm")
    assert [r["name"] for r in shown["repos"]] == ["crm"]
    assert shown["repos"][0]["path"] == str(projects.folder("acme") / "crm")
    assert (shown["default_name"], shown["name_state"], shown["last"]) == (
        "acme-crm",
        "free",
        None,
    )


def test_the_project_and_repository_last_used(client, shop, acme, fake_tmux):
    _in_shop("backend")
    runtime.stop_session("shop-backend")
    shown = project_launch(client)
    assert (shown["project"], shown["repo"], shown["default_name"]) == (
        "shop",
        "backend",
        "shop-backend",
    )
    assert [r["name"] for r in shown["repos"]] == ["backend", "frontend"]
    assert shown["last"]["name"] == "shop-backend"
    assert shown["name_state"] == "stopped_here"
    assert shown["provider"] == {"name": "kilo", "reason": "last_session"}


def test_the_project_and_repository_asked(client, shop, acme, fake_tmux):
    _in_shop("backend")
    shown = project_launch(client, project="acme")
    assert (shown["project"], shown["repo"], shown["name_state"], shown["last"]) == (
        "acme",
        "crm",
        "free",
        None,
    )
    shown = project_launch(client, project="shop", repo="frontend")
    assert (shown["repo"], shown["default_name"], shown["last"]) == (
        "frontend",
        "shop-frontend",
        None,
    )
    assert shown["provider"] is None  # no session in frontend: the human picks
    shown = project_launch(client, project="nope", repo="docs")  # unknown: as not asked
    assert (shown["project"], shown["repo"], shown["name_state"]) == ("shop", "backend", "running")


def test_a_project_whose_folder_is_not_found_is_chosen_only_when_asked(client, shop, acme):
    projects.create("aaa", "Aaa")  # first by title
    projects.folder("aaa").rmdir()
    shown = project_launch(client)
    assert [p["id"] for p in shown["projects"]] == ["aaa", "acme", "shop"]
    assert shown["projects"][0]["found"] is False
    assert shown["project"] == "acme"
    shown = project_launch(client, project="aaa")
    assert (shown["project"], shown["repos"], shown["repo"]) == ("aaa", [], None)


def test_an_empty_project(client, shop):
    projects.create("acme", "ACME CRM")
    shown = project_launch(client, project="acme")
    assert (shown["project"], shown["repos"], shown["repo"]) == ("acme", [], None)
    assert (shown["default_name"], shown["name_state"], shown["provider"], shown["last"]) == (
        None,
        None,
        None,
        None,
    )


def test_no_project_without_a_database(client, lado_home):
    assert project_launch(client) == {
        "projects": [],
        "project": None,
        "repos": [],
        "repo": None,
        "default_name": None,
        "name_state": None,
        "provider": None,
        "last": None,
    }
    assert not (lado_home / "lado.db").exists()


def test_a_name_held_outside_the_project_is_taken_elsewhere(client, shop, tmp_path, fake_tmux):
    runtime.start_session(str(init_repo(tmp_path / "other")), "shop-frontend", None, "kilo")
    runtime.stop_session("shop-frontend")
    shown = project_launch(client, project="shop", repo="frontend")
    assert shown["name_state"] == "taken_elsewhere"
    assert shown["last"] is None


def test_no_secret_or_variable_value_is_shown(client, shop):
    projects.set_variable("shop", "API_URL", "https://plain-value.example")
    projects.set_secret("shop", "API_TOKEN", "canary-secret-value")
    body = client.get("/api/project-launch").text
    assert "plain-value" not in body and "canary-secret-value" not in body


def test_the_project_launch_needs_the_token(client, shop):
    client.cookies.clear()
    assert client.get("/api/project-launch").status_code == 401


# The folder check's project


def folder(client, path) -> dict:
    answer = client.get("/api/folders", params={"path": str(path)})
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_the_folder_check_names_the_project_a_folder_is_in(client, shop, tmp_path):
    (shop / "frontend" / "src").mkdir()
    assert folder(client, shop / "frontend" / "src")["project"] == {
        "id": "shop",
        "title": "Shop",
        "repo": "frontend",
    }
    (shop / "notes").mkdir()
    for path in (shop, shop / "notes"):
        assert folder(client, path)["project"] == {"id": "shop", "title": "Shop", "repo": None}
    (projects.projects_folder() / "old").mkdir()
    old = folder(client, projects.projects_folder() / "old")
    assert (old["problem_kind"], old["project"]) == ("in_project", None)
    assert folder(client, init_repo(tmp_path / "ws" / "app"))["project"] is None
