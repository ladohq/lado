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
