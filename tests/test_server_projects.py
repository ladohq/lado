"""The UI server's API for a project's repositories: a clone job into a project, one from
scratch, the removal's preview and the removal (openspec change project-repositories). In
process, with FastAPI's test client; git clones `file://` repositories."""

import os
import time

import pytest
from agent_helpers import bare_remote, fake_git, init_repo
from fastapi.testclient import TestClient

from lado import projects, state
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
    (shop / "frontend" / "new.txt").write_text("x")
    answer = client.get("/api/projects/shop/repos/frontend/removal")
    assert answer.status_code == 200, answer.text
    assert answer.json() == {
        "name": "frontend",
        "kind": "repository",
        "path": str(shop / "frontend"),
        "target": None,
        "sessions": [{"name": "shop-frontend", "open_runs": 0}],
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
