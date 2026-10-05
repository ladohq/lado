"""The Kits page in the UI server's API: installed and available kits, plans, install,
update, remove, the check for updates and the marketplaces. In process, with FastAPI's test
client; kits and marketplaces are local git repos, never the network."""

import json
import shutil
import subprocess

import agent_helpers
import pytest
from agent_helpers import init_repo, publish
from fastapi.testclient import TestClient

from lado import gitcache, kits, marketplaces, runtime, state
from lado.server import app as server_app
from lado.server import auth, models

PORT = 8123
OWN = "http://testserver"
WORKER = "---\nname: w\ndescription: works\n---\nWork.\n"
WITH_DB = "---\nname: w\ndescription: works\nmcp: {db: {command: [db-server, --ro]}}\n---\nW.\n"


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


def kit_repo(tmp_path, *versions, agent=WORKER, name="team"):
    """A kit with a tag v<version> for each version: (work repo, its bare repo's URL)."""
    work = init_repo(tmp_path / f"{name}-kit")
    url = ""
    for version in versions:
        files = {
            "kit.yaml": f"name: {name}\nversion: {version}\ndescription: about {name}\n",
            "agents/w.md": agent,
        }
        url = publish(work, files, tag=f"v{version}")
    return work, url


def market_repo(tmp_path, name, kits: dict[str, str], index: dict | None = None) -> str:
    files = {"marketplace.yaml": "kits:\n" + "".join(f"  {k}: {u}\n" for k, u in kits.items())}
    if index is not None:
        files["index.json"] = json.dumps({"index": 1, "kits": index})
    return publish(init_repo(tmp_path / name), files)


def folder_kit(tmp_path, name="mine", agent=WORKER):
    kit = tmp_path / "dev" / name
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text(f"name: {name}\nversion: 1.0.0\ndescription: local\n")
    (kit / "agents" / "w.md").write_text(agent)
    return kit


def ok(answer, status=200):
    assert answer.status_code == status, answer.text
    return answer.json() if answer.content else None


def plan(client, spec, **given):
    return ok(client.post("/api/kits/plan", json={"spec": spec, **given}))


def install(client, planned, **given):
    body = {"spec": planned["spec"], "marketplace": planned["marketplace"], **given}
    if planned["tag"] is None:
        body.setdefault("mcp", [m["name"] for m in planned["mcp"]])
    else:
        body.setdefault("commit", planned["commit"])
    return client.post("/api/kits/install", json=body)


# Without lado.db, nothing is made and nothing is cloned


def test_the_lists_neither_make_lado_db_nor_clone(client, lado_home, monkeypatch):
    monkeypatch.setattr(marketplaces, "OFFICIAL_URL", "file:///nowhere/official.git")
    installed = ok(client.get("/api/kits/installed"))
    assert [(k["name"], k["kind"]) for k in installed] == [("default", "built-in")]
    assert ok(client.get("/api/kits/available")) == []
    assert ok(client.get("/api/marketplaces")) == [
        {
            "name": "official",
            "url": "file:///nowhere/official.git",
            "enabled": True,
            "updated_at": None,
            "official": True,
            "kits": None,
            "index": False,
            "problem": "not fetched yet: update it",
        }
    ]
    assert client.get("/api/kits/team/remove-preview").status_code == 404
    assert not (lado_home / "lado.db").exists()
    assert not (lado_home / "marketplaces").exists()


def test_the_lists_are_503_for_another_schema(client):
    state.list_sessions()
    agent_helpers.previous_schema()
    for path in ("/api/kits/installed", "/api/kits/available", "/api/marketplaces"):
        assert client.get(path).status_code == 503
    assert client.post("/api/kits/check-updates").status_code == 503
    assert state.schema_version() == state.SCHEMA_VERSION - 1


# Installed kits


def test_installed_kits_say_where_they_come_from(client, tmp_path):
    _, url = kit_repo(tmp_path, "1.0.0", agent=WITH_DB)
    ok(install(client, plan(client, url)))
    ok(install(client, plan(client, str(folder_kit(tmp_path)))))
    mine, team, default = ok(client.get("/api/kits/installed"))
    commit = gitcache.commit(gitcache.clone_dir(url, "v1.0.0"))
    assert team == {
        "name": "team",
        "version": "1.0.0",
        "description": "about team",
        "valid": True,
        "problem": None,
        "kind": "git",
        "address": url,
        "tag": "v1.0.0",
        "commit": commit,
        "folder": None,
        "marketplace": None,
        "installed_at": team["installed_at"],
        "updated_at": None,
        "agents": 1,
        "skills": 0,
        "flows": 0,
        "mcp": ["db"],
        "missing": False,
    }
    assert team["installed_at"]
    assert (mine["kind"], mine["folder"], mine["address"]) == (
        "folder",
        str((tmp_path / "dev" / "mine").resolve()),
        None,
    )
    assert (default["name"], default["kind"], default["valid"]) == ("default", "built-in", True)


def test_an_installed_kit_whose_folder_is_gone_says_so(client, tmp_path):
    kit = folder_kit(tmp_path)
    ok(install(client, plan(client, str(kit))))
    subprocess.run(["rm", "-rf", str(kit)], check=True)
    (mine, _) = ok(client.get("/api/kits/installed"))
    assert (mine["valid"], mine["version"], mine["missing"]) == (False, "", True)
    assert "its folder" in mine["problem"] and "is missing" in mine["problem"]


# Plan and install


def test_a_plan_from_git_says_what_install_would_do_and_installs_nothing(client, tmp_path):
    _, url = kit_repo(tmp_path, "1.0.0", "1.1.0", agent=WITH_DB)
    planned = plan(client, url)
    commit = gitcache.commit(gitcache.clone_dir(url, "v1.1.0"))
    assert planned == {
        "name": "team",
        "version": "1.1.0",
        "description": "about team",
        "spec": f"{url}@v1.1.0",
        "address": url,
        "tag": "v1.1.0",
        "commit": commit,
        "source": "git",
        "marketplace": None,
        "installed": None,
        "needs_confirmation": True,
        "current": False,
        "versions": ["v1.1.0", "v1.0.0"],
        "agents": ["w"],
        "skills": [],
        "flows": [],
        "mcp": [{"name": "db", "command": "db-server --ro"}],
        "new_mcp": [],
        "warnings": [],
        "notes": [],
        "users": None,
        "before": None,
    }
    assert state.list_kits() == []


def test_install_takes_the_plans_tag_even_after_a_new_release(client, tmp_path):
    work, url = kit_repo(tmp_path, "1.0.0")
    planned = plan(client, url)
    publish(work, {"kit.yaml": "name: team\nversion: 1.1.0\n"}, tag="v1.1.0")
    installed = ok(install(client, planned))
    assert (installed["name"], installed["tag"]) == ("team", "v1.0.0")
    assert state.get_kit("team").tag == "v1.0.0"


def test_install_of_another_commit_than_the_plans_is_409(client, tmp_path):
    work, url = kit_repo(tmp_path, "1.0.0")
    planned = plan(client, url)
    answer = install(client, planned, commit="0" * 40)
    assert answer.status_code == 409
    assert "changed since the plan" in answer.json()["detail"]
    assert state.list_kits() == []


def test_a_folder_is_installed_only_with_the_mcp_servers_of_its_plan(client, tmp_path):
    kit = folder_kit(tmp_path)
    planned = plan(client, str(kit))
    assert (planned["tag"], planned["commit"], planned["source"]) == (None, None, "folder")
    assert planned["spec"] == str(kit.resolve()) and planned["needs_confirmation"] is False
    (kit / "agents" / "w.md").write_text(WITH_DB)  # changed after the human looked
    answer = install(client, planned)
    assert answer.status_code == 409
    assert "MCP servers" in answer.json()["detail"]
    assert ok(install(client, planned, mcp=["db"]))["name"] == "mine"


def test_a_plan_from_a_marketplace_names_it(client, tmp_path, monkeypatch):
    _, url = kit_repo(tmp_path, "1.0.0")
    monkeypatch.setattr(marketplaces, "OFFICIAL_URL", market_repo(tmp_path, "off", {"team": url}))
    planned = plan(client, "team", marketplace="official")
    assert (planned["source"], planned["marketplace"], planned["needs_confirmation"]) == (
        "official",
        "official",
        False,
    )
    assert planned["spec"] == "team@v1.0.0"
    installed = ok(install(client, planned))
    assert installed["marketplace"] == "official"


def test_a_refused_plan_is_400_with_the_cores_words(client, tmp_path):
    _, url = kit_repo(tmp_path, "1.0.0")
    answer = client.post("/api/kits/plan", json={"spec": f"{url}@main"})
    assert answer.status_code == 400
    assert answer.json()["detail"]["message"].startswith(
        f"{url}@main: a kit is pinned by its version tag vX.Y.Z"
    )
    answer = client.post("/api/kits/plan", json={"spec": "team", "marketplace": "nowhere"})
    assert answer.json()["detail"]["message"] == (
        'no marketplace "nowhere"; lado marketplaces lists them'
    )
    ok(install(client, plan(client, url)))
    answer = client.post("/api/kits/plan", json={"spec": url})
    assert answer.status_code == 400
    assert 'kit "team" is installed already' in answer.json()["detail"]["message"]


# Update


def test_a_plan_update_names_new_mcp_servers_and_the_running_sessions(
    client, tmp_path, monkeypatch
):
    work, url = kit_repo(tmp_path, "1.0.0")
    ok(install(client, plan(client, url)))
    publish(work, {"kit.yaml": "name: team\nversion: 1.1.0\n", "agents/w.md": WITH_DB}, "v1.1.0")
    state.add_session(state.Session("a", str(tmp_path), None, kits=["team"]))
    state.add_session(state.Session("b", str(tmp_path), None, kits=["team"]))
    status = {"a": runtime.SessionStatus.RUNNING, "b": runtime.SessionStatus.STOPPED}
    monkeypatch.setattr(runtime, "session_status", lambda sess: status[sess.name])
    planned = ok(client.post("/api/kits/team/plan-update", json={}))
    assert (planned["tag"], planned["installed"], planned["current"]) == ("v1.1.0", "v1.0.0", False)
    assert planned["new_mcp"] == ["db"]
    assert planned["warnings"] == [
        "team v1.1.0 starts an MCP server v1.0.0 did not: db (db-server --ro)"
    ]
    assert planned["notes"] == ["running session a gets v1.1.0 for new agents only"]
    assert planned["users"] == {
        "running": ["a"],
        "stopped": ["b"],
        "running_line": 'running session a uses kit "team": its new agents and flow runs fail '
        "to start until it is added again; the agents running now keep working",
        "stopped_line": 'stopped session b uses kit "team" too: a resume needs it',
    }
    assert planned["versions"] == ["v1.1.0", "v1.0.0"]
    assert state.get_kit("team").tag == "v1.0.0"
    # Another commit than the plan's is 409; the plan's moves the kit.
    body = {"tag": "v1.1.0", "commit": "0" * 40}
    assert client.post("/api/kits/team/update", json=body).status_code == 409
    body["commit"] = planned["commit"]
    updated = ok(client.post("/api/kits/team/update", json=body))
    assert (updated["tag"], updated["mcp"]) == ("v1.1.0", ["db"]) and updated["updated_at"]


def test_a_plan_update_to_the_installed_version_says_so(client, tmp_path):
    _, url = kit_repo(tmp_path, "1.0.0")
    ok(install(client, plan(client, url)))
    planned = ok(client.post("/api/kits/team/plan-update", json={"tag": "v1.0.0"}))
    assert planned["current"] is True
    assert planned["notes"] == ['Kit "team" is at v1.0.0 already.']


SKILL = "---\nname: {0}\ndescription: does {0}\n---\nDo {0}.\n"


def pack_repo(tmp_path, *skills) -> str:
    """A skill pack with a tag v1: its bare repo's URL."""
    files = {f"skills/{s}/SKILL.md": SKILL.format(s) for s in skills}
    return publish(init_repo(tmp_path / "pack"), files, tag="v1")


def kit_with_pack(work, version, pack, own="own", agent=WORKER, flows=()):
    files = {
        "kit.yaml": f"name: team\nversion: {version}\n"
        f"dependencies: {{skills: {{p: '{pack}@v1'}}}}\n",
        "agents/w.md": agent,
        f"skills/{own}/SKILL.md": SKILL.format(own),
        **{f"flows/{f}.yaml": FLOW for f in flows},
    }
    return publish(work, files, tag=f"v{version}")


FLOW = (
    "name: ship\ndescription: ships\nstart: work\nstates:\n"
    "  work: {agent: w, do: work, outcomes: {done: end}}\n  end: {end: true}\n"
)


def test_a_plan_update_gives_what_the_installed_version_has(client, tmp_path):
    pack = pack_repo(tmp_path, "review")
    work = init_repo(tmp_path / "team-kit")
    url = kit_with_pack(work, "1.0.0", pack, own="old", agent=WITH_DB)
    ok(install(client, plan(client, url)))
    shutil.rmtree(work / "skills" / "old")
    kit_with_pack(work, "1.1.0", pack, own="new", flows=["ship"])
    planned = ok(client.post("/api/kits/team/plan-update", json={}))
    assert planned["before"] == {
        "agents": ["w"],
        "skills": ["old", "review"],
        "flows": [],
        "mcp": ["db"],
    }
    assert (planned["skills"], planned["flows"]) == (["new", "review"], ["ship"])


def test_a_plan_update_gives_no_before_without_the_installed_versions_clone(client, tmp_path):
    work, url = kit_repo(tmp_path, "1.0.0")
    ok(install(client, plan(client, url)))
    publish(work, {"kit.yaml": "name: team\nversion: 1.1.0\n"}, "v1.1.0")
    shutil.rmtree(gitcache.clone_dir(url, "v1.0.0"))
    assert ok(client.post("/api/kits/team/plan-update", json={}))["before"] is None


def test_a_plan_update_gives_no_before_when_a_pack_of_the_installed_version_is_gone(
    client, tmp_path
):
    pack = pack_repo(tmp_path, "review")
    work = init_repo(tmp_path / "team-kit")
    url = kit_with_pack(work, "1.0.0", pack)
    ok(install(client, plan(client, url)))
    kit_with_pack(work, "1.1.0", pack)
    shutil.rmtree(gitcache.clone_dir(pack, "v1"))
    # Its skills would be missing from before: each would look added.
    assert ok(client.post("/api/kits/team/plan-update", json={}))["before"] is None


def test_an_update_of_a_folder_kit_is_refused(client, tmp_path):
    ok(install(client, plan(client, str(folder_kit(tmp_path)))))
    answer = client.post("/api/kits/mine/plan-update", json={})
    assert answer.status_code == 400
    assert "it is read in place, nothing to update" in answer.json()["detail"]["message"]


# Remove


def test_remove_preview_names_the_sessions_and_remove_forgets_the_kit(
    client, tmp_path, monkeypatch
):
    _, url = kit_repo(tmp_path, "1.0.0")
    ok(install(client, plan(client, url)))
    state.add_session(state.Session("a", str(tmp_path), None, kits=["team"]))
    monkeypatch.setattr(runtime, "session_status", lambda sess: runtime.SessionStatus.RUNNING)
    preview = ok(client.get("/api/kits/team/remove-preview"))
    assert (preview["running"], preview["stopped"], preview["stopped_line"]) == (["a"], [], None)
    assert ok(client.delete("/api/kits/team"), 204) is None
    assert state.list_kits() == []
    assert client.get("/api/kits/team/remove-preview").status_code == 404
    answer = client.delete("/api/kits/default")
    assert answer.status_code == 400
    assert answer.json()["detail"]["message"].startswith('no kit "default" is installed')


# Check for updates


def test_check_updates_compares_each_installed_kit_with_its_remote(client, tmp_path):
    work, url = kit_repo(tmp_path, "1.0.0")
    ok(install(client, plan(client, url)))
    ok(install(client, plan(client, str(folder_kit(tmp_path)))))
    publish(work, {"kit.yaml": "name: team\nversion: 1.1.0\n"}, "v1.1.0")
    assert ok(client.post("/api/kits/check-updates")) == [
        {
            "name": "mine",
            "installed": "",
            "latest": None,
            "pre": None,
            "note": "local, not checked",
            "warnings": [],
            "newer": None,
        },
        {
            "name": "team",
            "installed": "v1.0.0",
            "latest": "v1.1.0",
            "pre": None,
            "note": "",
            "warnings": [],
            "newer": "v1.1.0",
        },
    ]


@pytest.mark.parametrize(
    ("installed", "latest", "newer"),
    [
        ("v1.0.0", "v1.0.0", None),
        ("v1.2.0-rc.1", "v1.1.0", None),
        ("v1.0.0-rc.1", "v1.0.0", "v1.0.0"),
    ],
)
def test_newer_is_the_latest_release_only_when_it_is_above_the_installed_one(
    installed, latest, newer
):
    row = kits.Outdated("team", installed, latest=latest)
    assert models.outdated_info(row).newer == newer


# Available and marketplaces


def test_available_lists_the_kits_of_fetched_marketplaces(client, tmp_path):
    _, url = kit_repo(tmp_path, "1.0.0")
    entry = {"address": url, "latest": "v1.0.0", "description": "about team", "flows": ["f"]}
    other = "https://example.com/other.git"
    market = market_repo(tmp_path, "ours", {"team": url, "other": other}, {"team": entry})
    added = ok(client.post("/api/marketplaces", json={"name": "ours", "url": market}))
    assert added == {
        "name": "ours",
        "url": market,
        "enabled": True,
        "updated_at": added["updated_at"],
        "official": False,
        "kits": 2,
        "index": True,
        "problem": None,
    }
    other_offer, team_offer = ok(client.get("/api/kits/available"))
    assert other_offer == {
        "name": "other",
        "marketplace": "ours",
        "address": other,
        "installed": False,
        "index": None,
    }
    assert team_offer["index"] == {
        "address": url,
        "latest": "v1.0.0",
        "commit": None,
        "lado": None,
        "description": "about team",
        "agents": None,
        "skills": None,
        "flows": ["f"],
        "mcp": None,
    }
    ok(install(client, plan(client, "team", marketplace="ours")))
    assert [o["installed"] for o in ok(client.get("/api/kits/available"))] == [False, True]
    # Disabled: its kits leave Available; the official one was never fetched.
    ok(client.patch("/api/marketplaces/ours", json={"enabled": False}))
    assert ok(client.get("/api/kits/available")) == []
    assert not (state.home() / "marketplaces" / "official").exists()


def test_marketplaces_are_added_updated_and_removed_through_the_core(client, tmp_path, monkeypatch):
    monkeypatch.setattr(marketplaces, "OFFICIAL_URL", "file:///nowhere/official.git")
    work = init_repo(tmp_path / "ours")
    market = publish(work, {"marketplace.yaml": "kits:\n  a: https://e.com/a.git\n"})
    ok(client.post("/api/marketplaces", json={"name": "ours", "url": market}))
    answer = client.post("/api/marketplaces", json={"name": "ours", "url": market})
    assert answer.status_code == 400
    assert 'marketplace "ours" exists already' in answer.json()["detail"]["message"]
    publish(
        work, {"marketplace.yaml": "kits:\n  a: https://e.com/a.git\n  b: https://e.com/b.git\n"}
    )
    done = ok(client.post("/api/marketplaces/update", json={}))
    assert [(d["name"], d["error"] is None) for d in done] == [("official", False), ("ours", True)]
    assert done[0]["error"].startswith("cannot clone file:///nowhere/official.git")
    assert done[1]["marketplace"]["kits"] == 2
    (one,) = ok(client.post("/api/marketplaces/update", json={"name": "ours"}))
    assert one["name"] == "ours"
    disabled = ok(client.patch("/api/marketplaces/ours", json={"enabled": False}))
    assert disabled["enabled"] is False
    answer = client.delete("/api/marketplaces/official")
    assert answer.status_code == 400
    assert answer.json()["detail"]["message"].startswith("the official marketplace cannot be")
    assert ok(client.delete("/api/marketplaces/ours"), 204) is None
    assert [m["name"] for m in ok(client.get("/api/marketplaces"))] == ["official"]
    assert client.patch("/api/marketplaces/ours", json={"enabled": True}).status_code == 400


def test_an_index_lado_cannot_use_is_the_marketplaces_problem(client, tmp_path):
    files = {
        "marketplace.yaml": "kits:\n  a: https://e.com/a.git\n",
        "index.json": '{"index": 2, "kits": {}}',
    }
    market = publish(init_repo(tmp_path / "ours"), files)
    added = ok(client.post("/api/marketplaces", json={"name": "ours", "url": market}))
    assert added["problem"] == "index.json is version 2: it needs a newer LADO"
    assert (added["kits"], added["index"]) == (1, True)
    (offer,) = ok(client.get("/api/kits/available"))
    assert (offer["name"], offer["index"]) == ("a", None)


# Every change needs the token and the server's own Origin


CHANGES = [
    ("post", "/api/kits/plan", {"spec": "x"}),
    ("post", "/api/kits/install", {"spec": "x"}),
    ("post", "/api/kits/team/plan-update", {}),
    ("post", "/api/kits/team/update", {"tag": "v1.0.0", "commit": "c"}),
    ("delete", "/api/kits/team", None),
    ("post", "/api/kits/check-updates", None),
    ("post", "/api/marketplaces", {"name": "x", "url": "file:///x.git"}),
    ("patch", "/api/marketplaces/official", {"enabled": False}),
    ("delete", "/api/marketplaces/x", None),
    ("post", "/api/marketplaces/update", {}),
]


@pytest.mark.parametrize(("method", "path", "body"), CHANGES)
def test_a_kits_change_needs_the_token_and_the_servers_own_origin(client, method, path, body):
    kwargs = {} if body is None else {"json": body}
    send = getattr(client, method)
    del client.headers["origin"]
    assert send(path, **kwargs).status_code == 403
    client.headers["origin"] = "http://evil.example"
    assert send(path, **kwargs).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert send(path, **kwargs).status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/kits/installed",
        "/api/kits/available",
        "/api/marketplaces",
        "/api/kits/t/remove-preview",
    ],
)
def test_the_kits_lists_need_the_token(client, path):
    client.cookies.clear()
    assert client.get(path).status_code == 401
