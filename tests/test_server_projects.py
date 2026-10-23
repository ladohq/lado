"""The UI server's API for a project's repositories: a clone job into a project, one from
scratch, the removal's preview and the removal (openspec change project-repositories). In
process, with FastAPI's test client; git clones `file://` repositories."""

import os
import time

import pytest
from agent_helpers import bare_remote, fake_git, init_repo
from fastapi.testclient import TestClient

from lado import project_secrets, projects, runtime, state
from lado.server import app as server_app
from lado.server import auth

PORT = 8124
OWN = "http://testserver"


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    yield client
    client.app.state.clones.close()


@pytest.fixture
def shop(tmp_path, monkeypatch, git_config):
    """The workspace <tmp>/ws and the project shop with its repository frontend; its folder."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    projects.create("shop", "Shop")
    init_repo(projects.folder("shop") / "frontend")
    return projects.folder("shop")


def _until(check, timeout: float = 10):
    deadline = time.monotonic() + timeout
    while not (result := check()):
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)
    return result


def _names(client) -> list[str]:
    return [repo["name"] for repo in client.get("/api/projects/shop").json()["repos"]]


# Adding


def test_a_clone_job_into_a_project(client, shop, tmp_path):
    url = bare_remote(tmp_path)
    answer = client.post("/api/clones", json={"url": url, "project": "shop"})
    assert answer.status_code == 200, answer.text
    job = answer.json()
    assert job["path"] == str(shop / "app")
    done = _until(
        lambda: (j := client.get(f"/api/clones/{job['id']}").json())["state"] != "running" and j
    )
    assert done["state"] == "done", done
    assert _names(client) == ["app", "frontend"]
    named = client.post(
        "/api/clones", json={"url": url, "project": "shop", "name": "site", "branch": "develop"}
    ).json()
    assert named["path"] == str(shop / "site")
    _until(lambda: client.get(f"/api/clones/{named['id']}").json()["state"] == "done")
    assert projects.repository("shop", "site").branch == "develop"


def test_a_clone_job_into_a_project_refused(client, shop):
    url = "https://h/shop/frontend"
    taken = client.post("/api/clones", json={"url": url, "project": "shop"})
    assert taken.status_code == 400
    assert taken.json()["detail"]["message"] == (
        f"{shop / 'frontend'} already exists in project shop: choose another name with --name"
    )
    both = client.post("/api/clones", json={"url": url, "project": "shop", "path": str(shop)})
    assert both.status_code == 400
    assert both.json()["detail"]["message"] == "a clone into a project takes no path"
    alone = client.post("/api/clones", json={"url": url, "name": "web"})
    assert alone.status_code == 400
    assert alone.json()["detail"]["message"] == "a clone's name goes with its project"
    empty = client.post("/api/clones", json={"url": url, "project": "shop", "name": ""})
    assert empty.status_code == 400
    assert "the repository name  is not valid" in empty.json()["detail"]["message"]
    unknown = client.post("/api/clones", json={"url": url, "project": "acme"})
    assert unknown.status_code == 404
    assert client.app.state.clones._jobs == {}
    assert sorted(p.name for p in shop.iterdir()) == ["frontend"]


def test_two_clone_jobs_into_one_folder_of_a_project(client, shop, tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "slow").items():
        monkeypatch.setenv(key, value)
    first = client.post("/api/clones", json={"url": "https://h/a/web", "project": "shop"})
    assert first.status_code == 200
    second = client.post("/api/clones", json={"url": "https://h/b/web", "project": "shop"})
    assert second.status_code == 409


def test_a_repository_from_scratch(client, shop):
    answer = client.post("/api/projects/shop/repos", json={"name": "site"})
    assert answer.status_code == 200, answer.text
    assert answer.json() == {
        "name": "site",
        "path": str(shop / "site"),
        "remote": None,
        "branch": "main",
    }
    assert _names(client) == ["frontend", "site"]
    taken = client.post("/api/projects/shop/repos", json={"name": "site"})
    assert taken.status_code == 400
    assert "already exists in project shop" in taken.json()["detail"]
    bad = client.post("/api/projects/shop/repos", json={"name": ".x"})
    assert bad.status_code == 400 and "is not valid" in bad.json()["detail"]
    assert client.post("/api/projects/acme/repos", json={"name": "x"}).status_code == 404


# Removing


def test_the_removal_preview(client, shop):
    state.add_session(
        state.Session("shop-frontend", str(shop / "frontend"), None, "kilo", project="shop")
    )
    state.stop_session("shop-frontend")
    state.add_session(state.Session("old-frontend", str(shop / "frontend"), None, "kilo"))
    state.stop_session("old-frontend")
    (shop / "frontend" / "new.txt").write_text("x")
    answer = client.get("/api/projects/shop/repos/frontend/removal")
    assert answer.status_code == 200, answer.text
    assert answer.json() == {
        "name": "frontend",
        "kind": "repository",
        "path": str(shop / "frontend"),
        "target": None,
        "sessions": [
            {"name": "old-frontend", "open_runs": 0, "project": None},
            {"name": "shop-frontend", "open_runs": 0, "project": "shop"},
        ],
        "unpushed": ["frontend: uncommitted changes; branch main not pushed"],
    }
    assert (shop / "frontend").is_dir() and state.get_session("shop-frontend")


def test_the_removal_of_a_link(client, shop, tmp_path):
    (tmp_path / "docs").mkdir()
    (shop / "docs").symlink_to(tmp_path / "docs")
    preview = client.get("/api/projects/shop/repos/docs/removal").json()
    assert (preview["kind"], preview["target"]) == ("link", str(tmp_path / "docs"))
    assert client.delete("/api/projects/shop/repos/docs").status_code == 200
    assert not os.path.lexists(shop / "docs") and (tmp_path / "docs").is_dir()


def test_delete_removes_and_answers_the_project(client, shop):
    state.add_session(
        state.Session("shop-frontend", str(shop / "frontend"), None, "kilo", project="shop")
    )
    state.stop_session("shop-frontend")
    init_repo(shop / "backend")
    answer = client.delete("/api/projects/shop/repos/frontend")
    assert answer.status_code == 200, answer.text
    assert answer.json()["id"] == "shop"
    assert [repo["name"] for repo in answer.json()["repos"]] == ["backend"]
    assert not (shop / "frontend").exists() and state.list_sessions() == []


def test_the_removal_refused(client, shop):
    state.add_session(
        state.Session("shop-frontend", str(shop / "frontend"), None, "kilo", project="shop")
    )
    (shop / "notes").mkdir()
    for ask in (client.get, client.delete):
        suffix = "/removal" if ask == client.get else ""
        running = ask(f"/api/projects/shop/repos/frontend{suffix}")
        assert running.status_code == 400
        assert "has sessions not stopped: shop-frontend" in running.json()["detail"]
        plain = ask(f"/api/projects/shop/repos/notes{suffix}")
        assert plain.status_code == 400
        assert "is not a repository" in plain.json()["detail"]
        assert ask(f"/api/projects/shop/repos/web{suffix}").status_code == 404
        assert ask(f"/api/projects/acme/repos/web{suffix}").status_code == 404
    assert (shop / "frontend").is_dir() and (shop / "notes").is_dir()


def test_no_project_without_a_database(client, lado_home):
    assert client.get("/api/projects/shop/repos/x/removal").status_code == 404
    assert client.delete("/api/projects/shop/repos/x").status_code == 404
    assert client.post("/api/projects/shop/repos", json={"name": "x"}).status_code == 404
    assert not (lado_home / "lado.db").exists()


# A project's variables (openspec change project-variables)


def test_a_project_gives_its_variables_by_name(client, shop):
    projects.set_variable("shop", "MODEL_URL", "http://m")
    projects.set_variable("shop", "BOARD_URL", "https://a\nb")
    assert client.get("/api/projects/shop").json()["variables"] == [
        {"name": "BOARD_URL", "value": "https://a\nb"},
        {"name": "MODEL_URL", "value": "http://m"},
    ]


def test_set_and_unset_a_variable(client, shop, monkeypatch):
    for name in ("shop-frontend", "old"):
        state.add_session(state.Session(name, str(shop / "frontend"), None, "kilo", project="shop"))
    state.stop_session("old")
    monkeypatch.setattr(projects.runtime.tmux, "has_session", lambda name: True)
    monkeypatch.setattr(projects.runtime.loop, "running", lambda name: True)
    answer = client.put("/api/projects/shop/variables/BOARD_URL", json={"value": "https://a"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["running"] == ["shop-frontend"]
    assert answer.json()["project"]["id"] == "shop"
    assert answer.json()["project"]["variables"] == [{"name": "BOARD_URL", "value": "https://a"}]
    client.put("/api/projects/shop/variables/BOARD_URL", json={"value": ""})
    assert state.project_variables("shop") == {"BOARD_URL": ""}
    answer = client.delete("/api/projects/shop/variables/BOARD_URL")
    assert answer.status_code == 200, answer.text
    assert answer.json() == {
        "project": client.get("/api/projects/shop").json(),
        "running": ["shop-frontend"],
    }
    assert answer.json()["project"]["variables"] == []


@pytest.mark.parametrize(
    ("name", "value", "said"),
    [
        ("GH_TOKEN", "x", "GH_TOKEN looks like a secret (TOKEN): "),
        ("PATH", "x", "PATH is reserved: LADO or the agent CLIs set it"),
        ("A-B", "x", "the name A-B is not a variable name: "),
        ("BIG", "x" * 70000, "the value of BIG is larger than 64 KiB"),
        ("NUL", "a\0b", "the value of NUL is not UTF-8 text"),
    ],
    ids=["secret", "reserved", "no-name", "large", "nul"],
)
def test_a_variable_refused(client, shop, name, value, said):
    answer = client.put(f"/api/projects/shop/variables/{name}", json={"value": value})
    assert answer.status_code == 400
    assert answer.json()["detail"].startswith(said)
    assert state.project_variables("shop") == {}


def test_an_unknown_project_or_variable(client, shop):
    assert client.put("/api/projects/acme/variables/X", json={"value": "x"}).status_code == 404
    assert client.delete("/api/projects/acme/variables/X").status_code == 404
    missing = client.delete("/api/projects/shop/variables/X")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "project shop has no variable X; its variables: none"


def test_no_variables_without_a_database(client, lado_home):
    assert client.put("/api/projects/shop/variables/X", json={"value": "x"}).status_code == 404
    assert client.delete("/api/projects/shop/variables/X").status_code == 404
    assert not (lado_home / "lado.db").exists()


def test_the_variables_need_the_token_and_the_servers_own_origin(client, shop):
    projects.set_variable("shop", "BOARD_URL", "https://a")
    del client.headers["origin"]
    assert client.put("/api/projects/shop/variables/X", json={"value": "x"}).status_code == 403
    assert client.delete("/api/projects/shop/variables/BOARD_URL").status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.put("/api/projects/shop/variables/X", json={"value": "x"}).status_code == 401
    assert client.delete("/api/projects/shop/variables/BOARD_URL").status_code == 401
    assert state.project_variables("shop") == {"BOARD_URL": "https://a"}


# A project's secrets (openspec change project-secrets): set and removed, never read back.


def test_set_replace_and_unset_a_secret(client, shop, monkeypatch):
    state.add_session(
        state.Session("shop-frontend", str(shop / "frontend"), None, "kilo", project="shop")
    )
    monkeypatch.setattr(projects.runtime.tmux, "has_session", lambda name: True)
    monkeypatch.setattr(projects.runtime.loop, "running", lambda name: True)
    answer = client.put("/api/projects/shop/secrets/GH_TOKEN", json={"value": "canary-5a"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["project"]["secrets"] == ["GH_TOKEN"]
    assert answer.json()["running"] == ["shop-frontend"]
    assert "canary-5a" not in answer.text
    assert (project_secrets.folder("shop") / "GH_TOKEN").read_text() == "canary-5a"
    answer = client.put("/api/projects/shop/secrets/GH_TOKEN", json={"value": "canary-5b"})
    assert answer.status_code == 200 and "canary-5b" not in answer.text
    assert (project_secrets.folder("shop") / "GH_TOKEN").read_text() == "canary-5b"
    shown = client.get("/api/projects/shop")
    assert shown.json()["secrets"] == ["GH_TOKEN"] and "canary" not in shown.text
    answer = client.delete("/api/projects/shop/secrets/GH_TOKEN")
    assert answer.status_code == 200, answer.text
    assert answer.json()["project"]["secrets"] == []
    assert project_secrets.names("shop") == []


@pytest.mark.parametrize(
    ("name", "value", "said"),
    [
        ("GH_TOKEN", "", "the secret GH_TOKEN is empty; to remove it: "),
        ("PATH", "canary-r", "PATH is reserved: LADO or the agent CLIs set it"),
        ("A-B", "canary-n", "the name A-B is not a variable name: "),
        ("BIG", "canary-l" * 9000, "the value of BIG is larger than 64 KiB"),
        ("NUL", "canary-z\0", "the value of NUL is not UTF-8 text"),
        ("BOARD_URL", "canary-c", "BOARD_URL is a plain variable of shop; remove it first "),
    ],
    ids=["empty", "reserved", "no-name", "large", "nul", "plain"],
)
def test_a_secret_refused(client, shop, name, value, said):
    projects.set_variable("shop", "BOARD_URL", "https://a")
    answer = client.put(f"/api/projects/shop/secrets/{name}", json={"value": value})
    assert answer.status_code == 400
    assert answer.json()["detail"].startswith(said)
    assert "canary" not in answer.text
    assert project_secrets.names("shop") == []


@pytest.mark.parametrize(
    "body",
    [{"secret": "canary-6"}, {"value": 5}, {"value": ["canary-6"]}, {"value": {"x": "canary-6"}}],
)
def test_a_body_the_server_cannot_read_is_not_echoed(client, shop, body):
    answer = client.put("/api/projects/shop/secrets/GH_TOKEN", json=body)
    assert answer.status_code == 422
    assert "canary-6" not in answer.text and '"input"' not in answer.text
    assert project_secrets.names("shop") == []


def test_a_body_that_is_no_json_is_not_echoed(client, shop):
    answer = client.put(
        "/api/projects/shop/secrets/GH_TOKEN",
        content=b'{"value": "canary-7"',
        headers={"content-type": "application/json"},
    )
    assert answer.status_code == 422 and "canary-7" not in answer.text


def test_other_routes_keep_their_422(client, shop):
    answer = client.put("/api/projects/shop/variables/X", json={"oops": "visible"})
    assert answer.status_code == 422 and "visible" in answer.text  # FastAPI's own answer


def test_an_unknown_project_or_secret(client, shop):
    assert client.put("/api/projects/acme/secrets/X", json={"value": "x"}).status_code == 404
    assert client.delete("/api/projects/acme/secrets/X").status_code == 404
    missing = client.delete("/api/projects/shop/secrets/X")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "project shop has no secret X; its secrets: none"


def test_the_variables_route_never_removes_a_secret(client, shop):
    projects.set_secret("shop", "GH_TOKEN", "g")
    projects.set_variable("shop", "BOARD_URL", "https://a")
    assert client.delete("/api/projects/shop/variables/GH_TOKEN").status_code == 404
    assert client.delete("/api/projects/shop/secrets/BOARD_URL").status_code == 404
    assert project_secrets.names("shop") == ["GH_TOKEN"]
    assert state.project_variables("shop") == {"BOARD_URL": "https://a"}


def test_one_value_per_name_through_the_api(client, shop):
    """The refusals S6 and the LADO manager rely on: the code and the whole text."""
    projects.set_secret("shop", "DATABASE_URL", "postgres://s")
    projects.set_variable("shop", "BOARD_URL", "https://a")
    refused = client.put("/api/projects/shop/variables/DATABASE_URL", json={"value": "x"})
    assert (refused.status_code, refused.json()) == (
        400,
        {
            "detail": "DATABASE_URL is a secret of shop; remove it first with lado project "
            "unset shop DATABASE_URL"
        },
    )
    refused = client.put("/api/projects/shop/secrets/BOARD_URL", json={"value": "canary-d4"})
    assert (refused.status_code, refused.json()) == (
        400,
        {
            "detail": "BOARD_URL is a plain variable of shop; remove it first with lado project "
            "unset shop BOARD_URL"
        },
    )
    assert project_secrets.names("shop") == ["DATABASE_URL"]
    assert state.project_variables("shop") == {"BOARD_URL": "https://a"}


def test_no_secrets_without_a_database(client, lado_home):
    assert client.put("/api/projects/shop/secrets/X", json={"value": "x"}).status_code == 404
    assert client.delete("/api/projects/shop/secrets/X").status_code == 404
    assert not (lado_home / "lado.db").exists()
    assert not (lado_home / "projects").exists()


def test_the_secrets_need_the_token_and_the_servers_own_origin(client, shop):
    projects.set_secret("shop", "GH_TOKEN", "g")
    del client.headers["origin"]
    assert client.put("/api/projects/shop/secrets/X", json={"value": "x"}).status_code == 403
    assert client.delete("/api/projects/shop/secrets/GH_TOKEN").status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.put("/api/projects/shop/secrets/X", json={"value": "x"}).status_code == 401
    assert client.delete("/api/projects/shop/secrets/GH_TOKEN").status_code == 401
    assert project_secrets.names("shop") == ["GH_TOKEN"]


# Renaming (openspec change project-page)


def test_a_project_renamed(client, shop):
    answer = client.patch("/api/projects/shop", json={"title": "Shop EU"})
    assert answer.status_code == 200, answer.text
    assert answer.json() == client.get("/api/projects/shop").json()
    assert (answer.json()["id"], answer.json()["title"]) == ("shop", "Shop EU")
    assert projects.get("shop").title == "Shop EU"
    assert projects.folder("shop") == shop and (shop / "frontend").is_dir()


@pytest.mark.parametrize("title", ["", "   ", None, "shop"])
def test_a_project_renamed_to_nothing_has_no_title(client, shop, title):
    answer = client.patch("/api/projects/shop", json={"title": title})
    assert answer.status_code == 200, answer.text
    assert answer.json()["title"] is None and projects.get("shop").title is None


def test_a_rename_refused(client, shop):
    answer = client.patch("/api/projects/shop", json={"title": "x" * (runtime.MAX_TITLE + 1)})
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        f"a title is at most {runtime.MAX_TITLE} characters",
    )
    assert projects.get("shop").title == "Shop"
    answer = client.patch("/api/projects/acme", json={"title": "ACME"})
    assert (answer.status_code, answer.json()["detail"]) == (404, 'unknown project "acme"')


def test_a_rename_without_a_database_makes_none(client, lado_home):
    assert client.patch("/api/projects/shop", json={"title": "Shop"}).status_code == 404
    assert not (lado_home / "lado.db").exists()


def test_a_rename_needs_the_token_and_the_servers_own_origin(client, shop):
    del client.headers["origin"]
    assert client.patch("/api/projects/shop", json={"title": "X"}).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.patch("/api/projects/shop", json={"title": "X"}).status_code == 401
    assert projects.get("shop").title == "Shop"


def test_the_changes_need_the_token_and_the_servers_own_origin(client, shop):
    del client.headers["origin"]
    assert client.post("/api/projects/shop/repos", json={"name": "x"}).status_code == 403
    assert client.delete("/api/projects/shop/repos/frontend").status_code == 403
    assert client.get("/api/projects/shop/repos/frontend/removal").status_code == 200
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.post("/api/projects/shop/repos", json={"name": "x"}).status_code == 401
    assert client.delete("/api/projects/shop/repos/frontend").status_code == 401
    assert client.get("/api/projects/shop/repos/frontend/removal").status_code == 401
    assert sorted(p.name for p in shop.iterdir()) == ["frontend"]


# The Projects section (openspec change projects-section): the list, New project and the
# facts of the project's page


def _running(monkeypatch, shop, *names, stopped=()):
    for name in (*names, *stopped):
        state.add_session(state.Session(name, str(shop / "frontend"), None, "kilo", project="shop"))
    for name in stopped:
        state.stop_session(name)
    monkeypatch.setattr(projects.runtime.tmux, "has_session", lambda name: True)
    monkeypatch.setattr(projects.runtime.loop, "running", lambda name: True)


def test_the_list_of_projects(client, shop, monkeypatch):
    init_repo(shop / "backend")
    projects.create("acme", "ACME CRM")
    init_repo(projects.folder("acme") / "crm")
    projects.create("sandbox", None)
    projects.folder("sandbox").rmdir()
    _running(monkeypatch, shop, "shop-frontend", stopped=["old"])
    answer = client.get("/api/projects")
    assert answer.status_code == 200, answer.text
    assert answer.json() == [
        {
            "id": "acme",
            "title": "ACME CRM",
            "folder": str(projects.folder("acme")),
            "found": True,
            "repos": 1,
            "running": [],
        },
        {
            "id": "sandbox",
            "title": None,
            "folder": str(projects.folder("sandbox")),
            "found": False,
            "repos": 0,
            "running": [],
        },
        {
            "id": "shop",
            "title": "Shop",
            "folder": str(shop),
            "found": True,
            "repos": 2,
            "running": ["shop-frontend"],
        },
    ]


def test_no_list_without_a_database(client, lado_home):
    assert client.get("/api/projects").json() == []
    assert not (lado_home / "lado.db").exists()


def test_new_project(client, tmp_path, monkeypatch, lado_home):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    assert not (lado_home / "lado.db").exists()
    answer = client.post("/api/projects", json={"id": "shop-eu", "title": "Shop EU"})
    assert answer.status_code == 200, answer.text
    assert answer.json() == client.get("/api/projects/shop-eu").json()
    assert answer.json()["title"] == "Shop EU" and answer.json()["repos"] == []
    assert (tmp_path / "ws" / "projects" / "shop-eu").is_dir()
    untitled = client.post("/api/projects", json={"id": "acme"})
    assert untitled.status_code == 200, untitled.text
    assert state.get_project("acme").title is None


def test_new_project_refused(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    target = tmp_path / "ws" / "projects" / "shop-eu"
    target.mkdir(parents=True)
    answer = client.post("/api/projects", json={"id": "shop-eu", "title": "Shop EU"})
    assert answer.status_code == 400
    assert answer.json()["detail"] == (
        f"{target} already exists: LADO makes a project's folder itself; choose another id "
        "or move that folder away"
    )
    assert state.get_project("shop-eu") is None
    bad = client.post("/api/projects", json={"id": "Shop"})
    assert bad.status_code == 400
    assert bad.json()["detail"].startswith("the project id Shop is not valid: ")
    long = client.post("/api/projects", json={"id": "shop", "title": "x" * 81})
    assert long.status_code == 400
    assert long.json()["detail"].startswith("a title is at most")
    assert state.list_projects() == []


def test_new_project_needs_the_token_and_the_servers_own_origin(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    del client.headers["origin"]
    assert client.post("/api/projects", json={"id": "shop"}).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert client.post("/api/projects", json={"id": "shop"}).status_code == 401
    assert not (tmp_path / "ws").exists()


def test_an_id_from_a_title(client, tmp_path, monkeypatch, lado_home):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    answer = client.get("/api/project-id", params={"title": "Магазин EU"})
    assert answer.status_code == 200, answer.text
    assert answer.json() == {
        "id": "magazin-eu",
        "folder": str(tmp_path / "ws" / "projects" / "magazin-eu"),
        "problem": None,
    }
    assert client.get("/api/project-id", params={"title": "日本"}).json() == {
        "id": None,
        "folder": None,
        "problem": "the name needs a Latin letter or digit for its folder: type one",
    }
    assert not (tmp_path / "ws").exists()
    assert not (lado_home / "lado.db").exists()  # asking makes nothing


def test_an_id_taken_or_typed(client, shop):
    assert client.get("/api/project-id", params={"title": "Shop"}).json() == {
        "id": "shop",
        "folder": str(shop),
        "problem": "project shop exists",
    }
    typed = client.get("/api/project-id", params={"id": "Shop"}).json()
    assert typed["id"] == "Shop" and typed["folder"] is None
    assert typed["problem"].startswith("the project id Shop is not valid: ")
    free = client.get("/api/project-id", params={"id": "eu-shop", "title": "Shop"}).json()
    assert free == {"id": "eu-shop", "folder": str(shop.parent / "eu-shop"), "problem": None}


def test_the_project_names_its_overrides_and_unused_secrets_without_values(
    client, shop, tmp_path, monkeypatch
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "YOUGILE_API_KEY").write_text("canary-out")
    (outside / "BOARD_URL").write_text("canary-out")
    monkeypatch.setenv("LADO_ENV_DIR", str(outside))
    projects.set_secret("shop", "YOUGILE_API_KEY", "canary-secret-1")
    projects.set_secret("shop", "SENTRY_DSN", "canary-secret-2")
    (project_secrets.folder("shop") / "SENTRY_DSN").chmod(0o644)
    _running(monkeypatch, shop, "shop-frontend", stopped=["shop-backend"])
    answer = client.get("/api/projects/shop")
    body = answer.json()
    assert body["secrets"] == ["SENTRY_DSN", "YOUGILE_API_KEY"]
    assert body["overrides"] == ["YOUGILE_API_KEY"]
    assert body["unused"] == [
        {"name": "SENTRY_DSN", "reason": "readable or writable by others: chmod 600 it"}
    ]
    assert body["running"] == ["shop-frontend"]
    assert "canary-" not in answer.text
    project_secrets.folder("shop").chmod(0o755)
    folder_unused = client.get("/api/projects/shop").json()["unused"]
    assert folder_unused == [
        {"name": None, "reason": "readable or writable by others: chmod 700 it"}
    ]
