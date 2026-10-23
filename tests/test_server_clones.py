"""The UI server's clone from a URL: the remote's branches, the target folder, and clone
jobs the window keeps alive (openspec change clone-from-url). In process, with FastAPI's
test client; git clones `file://` repositories, a fake git stands in for a slow one."""

import asyncio
import time

import pytest
import uvicorn
from agent_helpers import bare_remote, fake_git, fake_git_calls, gone, init_repo
from fastapi.testclient import TestClient

from lado import clone, projects, runtime
from lado.server import app as server_app
from lado.server import auth, clones, launch

PORT = 8123
OWN = "http://testserver"


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    yield client
    client.app.state.clones.close()


@pytest.fixture
def slow_git(tmp_path, monkeypatch):
    folder = tmp_path / "fake"
    for key, value in fake_git(folder, "slow").items():
        monkeypatch.setenv(key, value)
    return folder


def _until(check, timeout: float = 10):
    deadline = time.monotonic() + timeout
    while not (result := check()):
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)
    return result


def _leftovers(parent):
    return [p.name for p in parent.iterdir() if ".clone-" in p.name]


def test_the_remotes_branches(client, tmp_path):
    url = bare_remote(tmp_path)
    answer = client.post("/api/remote-branches", json={"url": url})
    assert answer.status_code == 200
    assert answer.json() == {
        "url": url,
        "branches": ["main", "develop", "release/1.2"],
        "default": "main",
        "repo_name": "app",  # the name a clone takes in a project, until the human edits it
    }


def test_a_listing_refused_is_400_with_its_kind_and_hint(client, tmp_path):
    answer = client.post("/api/remote-branches", json={"url": (tmp_path / "x.git").as_uri()})
    assert answer.status_code == 400
    detail = answer.json()["detail"]
    assert detail["kind"] == "not_found"
    assert detail["message"].startswith(f"cannot read {(tmp_path / 'x.git').as_uri()}: ")
    assert detail["hint"] is None
    answer = client.post("/api/remote-branches", json={"url": "some/folder"})
    assert answer.status_code == 400
    assert answer.json()["detail"] == {
        "message": "some/folder is not a git URL",
        "kind": "not_url",
        "hint": None,
    }


def test_a_listing_failure_with_a_hint(client, tmp_path, monkeypatch):
    for key, value in fake_git(tmp_path / "fake", "fail").items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("FAKE_GIT_STDERR", "ERROR: Repository not found.")
    answer = client.post("/api/remote-branches", json={"url": "git@github.com:acme/app.git"})
    assert answer.status_code == 400
    assert answer.json()["detail"]["hint"] == {
        "text": "See which GitHub account this machine uses:",
        "command": "gh auth status",
    }


def test_the_clone_target_in_the_repositories_folder(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "repos"))
    monkeypatch.setattr(launch, "_installed", lambda provider: False)
    answer = client.get("/api/clone-target", params={"url": "git@github.com:acme/app.git"})
    assert answer.status_code == 200
    assert answer.json()["path"] == str(tmp_path / "repos" / "app")


def test_the_clone_target_by_default(home_workspace, client, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(launch, "_installed", lambda provider: False)
    answer = client.get("/api/clone-target", params={"url": "git@github.com:ladohq/lado.git"})
    assert answer.status_code == 200
    assert answer.json() == {
        "path": str(tmp_path / "home" / "workspace" / "lado"),
        "state": "new",
        "text": "a new folder",
        "origin": None,
        "branch": None,
        "suggestion": None,
        "default_name": "lado",
        "name_state": "free",
        "provider": None,
        "warning": None,
        "hint": None,
        "project": None,
    }


@pytest.fixture
def shop(tmp_path, monkeypatch):
    """The workspace <tmp>/ws with the project shop titled Shop; its folder."""
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "ws"))
    monkeypatch.setattr(launch, "_installed", lambda provider: False)
    projects.create("shop", "Shop")
    return projects.folder("shop")


IN_SHOP = "{} belongs to the project Shop: start a session in the project"
WEB_HINT = {
    "text": "Add a repository to the project:",
    "command": "lado project repo add shop https://github.com/shop/web",
}


def test_a_clone_target_in_a_project(client, shop):
    params = {"url": "https://github.com/shop/web", "path": str(shop / "web")}
    target = client.get("/api/clone-target", params=params).json()
    assert (target["state"], target["text"], target["hint"]) == (
        "in_project",
        IN_SHOP.format(shop / "web"),
        WEB_HINT,
    )
    assert target["project"] == {"id": "shop", "title": "Shop", "repo": None}
    away = client.get("/api/clone-target", params={"url": "https://github.com/shop/web"}).json()
    assert (away["state"], away["hint"], away["project"]) == ("new", None, None)


def test_a_clone_into_a_project_is_400_and_starts_no_job(client, shop):
    answer = client.post(
        "/api/clones", json={"url": "https://github.com/shop/web", "path": str(shop / "web")}
    )
    assert answer.status_code == 400
    assert answer.json()["detail"] == {
        "message": IN_SHOP.format(shop / "web"),
        "kind": "in_project",
        "hint": WEB_HINT,
    }
    assert client.app.state.clones._jobs == {} and list(shop.iterdir()) == []


def test_in_a_container_a_clone_target_outside_the_repositories_folder_warns(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr(launch, "_installed", lambda provider: False)
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "repos"))
    url = "git@github.com:acme/app.git"
    inside = client.get("/api/clone-target", params={"url": url}).json()
    assert (inside["path"], inside["warning"]) == (str(tmp_path / "repos" / "app"), None)
    away = client.get("/api/clone-target", params={"url": url, "path": str(tmp_path / "app")})
    assert away.json()["warning"] == runtime.OUTSIDE_WORKSPACE.format(folder=tmp_path / "repos")


def test_the_clone_targets_other_states(client, tmp_path, repo, fake_tmux):
    folder = init_repo(tmp_path / "app")
    runtime.git(str(folder), "remote", "add", "origin", "git@github.com:acme/app.git")
    same = client.get(
        "/api/clone-target", params={"url": "https://github.com/acme/app", "path": str(folder)}
    ).json()
    assert (same["state"], same["branch"], same["origin"]) == (
        "same_repo",
        "main",
        "git@github.com:acme/app.git",
    )
    other = client.get(
        "/api/clone-target", params={"url": "git@github.com:ladohq/app.git", "path": str(folder)}
    ).json()
    assert (other["state"], other["suggestion"]) == ("other_repo", str(tmp_path / "ladohq-app"))
    # A name a session of another folder has, before anything is cloned.
    runtime.start_session(str(repo), "fresh", None, "kilo")
    taken = client.get(
        "/api/clone-target",
        params={"url": "https://h/a/fresh", "path": str(tmp_path / "fresh")},
    ).json()
    assert (taken["state"], taken["default_name"], taken["name_state"]) == (
        "new",
        "fresh",
        "taken_elsewhere",
    )
    relative = client.get("/api/clone-target", params={"url": "https://h/a/b", "path": "x"})
    assert relative.status_code == 400
    assert relative.json()["detail"]["message"] == "x is not a full path: give one from / or ~"


def test_a_clone_job_to_done(client, tmp_path):
    url = bare_remote(tmp_path)
    target = tmp_path / "work" / "app"
    answer = client.post("/api/clones", json={"url": url, "path": str(target), "branch": "develop"})
    assert answer.status_code == 200
    job = answer.json()
    assert (job["url"], job["path"], job["branch"], job["state"]) == (
        url,
        str(target),
        "develop",
        "running",
    )
    done = _until(
        lambda: (j := client.get(f"/api/clones/{job['id']}").json())["state"] != "running" and j
    )
    assert done["state"] == "done", done
    assert done["error"] is None
    assert runtime.branch(str(target)) == "develop"


def test_a_clone_into_a_folder_that_may_not_take_one_is_400(client, tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "x").write_text("x")
    answer = client.post(
        "/api/clones", json={"url": "https://h/a/app", "path": str(tmp_path / "app")}
    )
    assert answer.status_code == 400
    assert answer.json()["detail"]["kind"] == "not_empty"


def test_delete_cancels_a_clone(client, tmp_path, slow_git):
    target = tmp_path / "app"
    job = client.post("/api/clones", json={"url": "https://h/a/app", "path": str(target)}).json()
    progress = _until(lambda: client.get(f"/api/clones/{job['id']}").json()["progress"])
    assert (progress["phase"], progress["detail"]) == ("Receiving objects", "1.00 MiB | 2.00 MiB/s")
    answer = client.delete(f"/api/clones/{job['id']}")
    assert answer.status_code == 200
    assert (answer.json()["state"], answer.json()["error"]) == ("cancelled", None)
    assert not target.exists() and _leftovers(tmp_path) == []
    [call] = fake_git_calls(slow_git)
    assert gone(call["pid"]) and gone(call["child"])


def test_two_clones_into_one_folder(client, tmp_path, slow_git):
    target = str(tmp_path / "app")
    first = client.post("/api/clones", json={"url": "https://h/a/app", "path": target})
    assert first.status_code == 200
    second = client.post("/api/clones", json={"url": "https://h/b/app", "path": target + "/"})
    assert second.status_code == 409
    assert second.json()["detail"] == f"a clone into {target}/ runs already"


def test_an_unknown_job(client):
    assert client.get("/api/clones/nope").status_code == 404
    assert client.delete("/api/clones/nope").status_code == 404


def test_a_window_that_went_away(client, tmp_path, slow_git, monkeypatch):
    monkeypatch.setattr(clone, "ABANDONED", 0.5)
    monkeypatch.setattr(clones, "SWEEP", 0.1)
    target = tmp_path / "app"
    job = client.post("/api/clones", json={"url": "https://h/a/app", "path": str(target)}).json()
    _until(lambda: fake_git_calls(slow_git))
    jobs = client.app.state.clones
    _until(lambda: jobs.get(job["id"], seen=False).state == "cancelled")
    assert not target.exists() and _leftovers(tmp_path) == []
    [call] = fake_git_calls(slow_git)
    assert gone(call["pid"]) and gone(call["child"])


def test_a_finished_job_is_kept_a_while(client, tmp_path, monkeypatch):
    monkeypatch.setattr(clone, "KEPT", 0.3)
    monkeypatch.setattr(clones, "SWEEP", 0.1)
    url = bare_remote(tmp_path)
    job = client.post("/api/clones", json={"url": url, "path": str(tmp_path / "app")}).json()
    _until(lambda: client.get(f"/api/clones/{job['id']}").json()["state"] == "done")
    _until(lambda: client.get(f"/api/clones/{job['id']}").status_code == 404)


def test_the_servers_shutdown_cancels_a_running_clone(client, tmp_path, slow_git, monkeypatch):
    target = tmp_path / "app"
    job = client.post("/api/clones", json={"url": "https://h/a/app", "path": str(target)}).json()
    _until(lambda: fake_git_calls(slow_git))

    async def uvicorns_own(self, sockets=None):
        pass

    monkeypatch.setattr(uvicorn.Server, "shutdown", uvicorns_own)
    server = server_app.Server(uvicorn.Config(client.app))
    asyncio.run(server.shutdown())
    assert client.app.state.clones.get(job["id"], seen=False).state == "cancelled"
    assert not target.exists() and _leftovers(tmp_path) == []
    [call] = fake_git_calls(slow_git)
    assert gone(call["pid"]) and gone(call["child"])


def test_the_changes_need_the_servers_own_origin(client, tmp_path):
    del client.headers["origin"]
    url = "https://h/a/app"
    assert client.post("/api/remote-branches", json={"url": url}).status_code == 403
    assert (
        client.post("/api/clones", json={"url": url, "path": str(tmp_path / "a")}).status_code
        == 403
    )
    assert client.delete("/api/clones/x").status_code == 403
    assert client.get("/api/clone-target", params={"url": url}).status_code == 200
    client.cookies.clear()
    assert client.get("/api/clone-target", params={"url": url}).status_code == 401
    assert client.get("/api/clones/x").status_code == 401


def test_clone_target_without_lado_db_makes_none(client, lado_home, tmp_path):
    answer = client.get(
        "/api/clone-target", params={"url": "https://h/a/app", "path": str(tmp_path / "app")}
    )
    assert answer.json()["name_state"] == "free"
    assert not (lado_home / "lado.db").exists()


def test_the_clone_target_suggests_the_only_provider_installed(client, tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "_installed", lambda provider: provider.name == "codex")
    answer = client.get(
        "/api/clone-target", params={"url": "https://h/a/app", "path": str(tmp_path / "app")}
    )
    assert answer.json()["provider"] == {"name": "codex", "reason": "only_installed"}


def test_a_folder_that_cannot_be_read_is_400_not_500(client, tmp_path):
    closed = tmp_path / "closed"
    closed.mkdir()
    closed.chmod(0o000)
    try:
        params = {"url": "https://h/a/app", "path": str(closed / "app")}
        answer = client.get("/api/clone-target", params=params)
        assert answer.status_code == 400
        assert answer.json()["detail"]["kind"] == "no_access"
        answer = client.post(
            "/api/clones", json={"url": "https://h/a/app", "path": str(closed / "app")}
        )
        assert answer.status_code == 400
    finally:
        closed.chmod(0o755)


def test_a_window_that_goes_away_cancels_its_clone_at_once(client, tmp_path, slow_git):
    target = tmp_path / "app"
    job = client.post("/api/clones", json={"url": "https://h/a/app", "path": str(target)}).json()
    _until(lambda: fake_git_calls(slow_git))
    answer = client.post(f"/api/clones/{job['id']}/cancel")  # the window's beacon on pagehide
    assert answer.status_code == 200
    assert answer.json()["state"] == "cancelled"
    assert not target.exists() and _leftovers(tmp_path) == []
    [call] = fake_git_calls(slow_git)
    assert gone(call["pid"]) and gone(call["child"])
    assert client.post("/api/clones/nope/cancel").status_code == 404


def test_the_beacons_cancel_needs_the_servers_own_origin(client):
    del client.headers["origin"]
    assert client.post("/api/clones/x/cancel").status_code == 403
    client.headers["origin"] = "http://evil.example"
    assert client.post("/api/clones/x/cancel").status_code == 403
