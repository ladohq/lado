"""Launch and session control in the UI server's API: the folder check, recent folders,
kits, providers, and starting, resuming, stopping and forgetting a session. In process,
with FastAPI's test client."""

import os
import subprocess
from pathlib import Path

import agent_helpers
import pytest
from fastapi.testclient import TestClient

from lado import doctor, gitcache, providers, runs, runtime, state
from lado.server import app as server_app
from lado.server import auth
from lado.server import launch as server_launch

PORT = 8123
OWN = "http://testserver"  # the test client's Host


@pytest.fixture
def client(lado_home):
    client = TestClient(server_app.create_app(auth.token(), PORT))
    client.cookies.set(auth.cookie_name(PORT), auth.token())
    client.headers["origin"] = OWN
    return client


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    """The provider CLIs the server finds (server_launch._installed), all of them unless set."""
    found = set(providers.names())
    monkeypatch.setattr(server_launch, "_installed", lambda provider: provider.name in found)
    return found


def folder(client, path) -> dict:
    answer = client.get("/api/folders", params={"path": str(path)})
    assert answer.status_code == 200, answer.text
    return answer.json()


# The folder check


def test_a_repository_folder_is_ok_with_its_branch_name_and_subfolders(client, repo):
    for sub in ("src", "docs", ".hidden"):
        (repo / sub).mkdir()
    (repo / "README").write_text("x")
    info = folder(client, repo)
    assert info == {
        "path": str(repo),
        "ok": True,
        "problem": None,
        "root": str(repo),
        "branch": "main",
        "problem_kind": None,
        "hint": None,
        "subfolders": ["docs", "src"],
        "default_name": "my-repo",
        "name_state": "free",
        "provider": None,
        "warning": None,
        "scratch": False,
    }


def test_in_a_container_a_folder_outside_the_repositories_folder_is_ok_with_a_warning(
    client, repo, tmp_path, monkeypatch
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "projects"))
    outside = folder(client, repo)
    assert outside["ok"] is True
    assert outside["warning"] == runtime.OUTSIDE_REPOS.format(folder=tmp_path / "projects")
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    assert folder(client, repo)["warning"] is None
    monkeypatch.delenv("LADO_CONTAINER")
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "projects"))
    assert folder(client, repo)["warning"] is None


def test_the_folder_check_gives_the_cores_reason(client, tmp_path):
    info = folder(client, tmp_path)
    assert (info["ok"], info["root"], info["problem_kind"]) == (False, None, "not_repo")
    assert info["problem"] == f"{tmp_path} is not inside a git repository"
    assert info["hint"] == {
        "text": "Make it a repository with a first commit, in that folder:",
        "command": "git init && git add -A && git commit -m 'First commit'",
    }
    missing = folder(client, tmp_path / "nope")
    assert missing["problem"] == f"{tmp_path / 'nope'} does not exist"
    assert (missing["problem_kind"], missing["hint"]) == ("missing", None)
    assert missing["subfolders"] == []
    (tmp_path / "file").write_text("x")
    file = folder(client, tmp_path / "file")
    assert (file["problem_kind"], file["hint"]) == ("not_folder", None)


def test_a_repository_without_commits_is_named_so(client, tmp_path):
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", "-b", "trunk", str(empty)], check=True)
    info = folder(client, empty)
    assert (info["ok"], info["problem_kind"], info["branch"]) == (False, "no_commits", "trunk")
    assert info["problem"] == f"{empty} has no commits yet"
    assert info["hint"] == {
        "text": "Make a first commit, in that folder:",
        "command": "git add -A && git commit -m 'First commit'",
    }


def _git_script(tmp_path, monkeypatch, script: str | None) -> Path:
    bin_dir = tmp_path / "git-bin"
    bin_dir.mkdir()
    if script is not None:
        git = bin_dir / "git"
        git.write_text(f"#!/bin/sh\n{script}\n")
        git.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    return bin_dir


def test_no_git_is_a_folder_problem_not_a_server_error(client, repo, monkeypatch):
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    bin_dir = _git_script(repo.parent, monkeypatch, None)
    answer = client.get("/api/folders", params={"path": str(repo)})
    assert answer.status_code == 200
    info = answer.json()
    assert (info["ok"], info["problem_kind"], info["root"]) == (False, "no_git", None)
    assert info["problem"] == f"git is not installed or not on PATH ({bin_dir})"
    assert info["hint"]["command"] == "sudo apt install git"
    started = launch(client, repo, provider="claude")
    assert (started.status_code, started.json()["detail"]) == (400, info["problem"])


def test_a_git_that_refuses_the_folder_has_no_hint(client, tmp_path, monkeypatch):
    script = (
        'if [ "$1" = --version ]; then echo "git version 2.47.1"; exit 0; fi\n'
        "echo \"fatal: detected dubious ownership in repository at '/x'\" >&2\nexit 128"
    )
    _git_script(tmp_path, monkeypatch, script)
    info = folder(client, tmp_path)
    assert (info["problem_kind"], info["hint"]) == ("git_refused", None)
    broken = folder(client, tmp_path)
    assert broken["problem"].startswith(f"git cannot read {tmp_path}: fatal: detected dubious")


def test_the_folder_check_expands_the_home_folder(client, repo, monkeypatch):
    monkeypatch.setenv("HOME", str(repo.parent))
    assert folder(client, f"~/{repo.name}")["path"] == str(repo)


def test_a_relative_folder_is_refused(client):
    answer = client.get("/api/folders", params={"path": "some/where"})
    assert answer.status_code == 400
    assert "full path" in answer.json()["detail"]


def test_the_subfolders_are_at_most_fifty(client, tmp_path):
    for n in range(60):
        (tmp_path / f"d{n:02}").mkdir()
    assert folder(client, tmp_path)["subfolders"] == [f"d{n:02}" for n in range(50)]


@pytest.mark.parametrize(
    ("status", "name_state"),
    [("running", "running"), ("stopped", "stopped_here"), ("tmux_gone", "stopped_here")],
)
def test_the_default_name_says_whether_a_session_has_it(
    client, repo, fake_tmux, status, name_state
):
    runtime.start_session(str(repo), None, None, provider="claude")  # "my-repo"
    if status == "stopped":
        runtime.stop_session("my-repo")
    elif status == "tmux_gone":
        fake_tmux.append(("kill_session", "my-repo"))
    info = folder(client, repo)
    assert (info["default_name"], info["name_state"]) == ("my-repo", name_state)


def test_the_default_name_taken_by_a_session_of_another_folder(client, repo, tmp_path, fake_tmux):
    runtime.start_session(str(repo), None, None, provider="claude")
    other = agent_helpers.init_repo(tmp_path / "x" / "My Repo")
    info = folder(client, other)
    assert (info["default_name"], info["name_state"]) == ("my-repo", "taken_elsewhere")


def test_the_folder_suggests_the_only_installed_provider(client, repo, installed, lado_home):
    installed.intersection_update({"kilo"})
    info = folder(client, repo)
    assert info["provider"] == {"name": "kilo", "reason": "only_installed"}
    assert not (lado_home / "lado.db").exists()  # no history to look at, none made


def test_the_folder_suggests_its_last_sessions_provider(client, repo, installed, fake_tmux):
    runtime.start_session(str(repo), "s", None, "opencode")
    assert folder(client, repo)["provider"] == {"name": "opencode", "reason": "last_session"}
    installed.discard("opencode")  # not installed: the others leave a choice
    assert folder(client, repo)["provider"] is None


def test_a_subfolder_takes_its_repositorys_last_session(client, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, "kilo")
    (repo / "src").mkdir()
    assert folder(client, repo / "src")["provider"]["name"] == "kilo"


def test_a_folder_that_will_not_do_suggests_by_what_is_installed(client, tmp_path, installed):
    installed.intersection_update({"claude"})
    assert folder(client, tmp_path)["provider"] == {"name": "claude", "reason": "only_installed"}


# The repositories folder


def test_the_repositories_folder(client, tmp_path, monkeypatch):
    monkeypatch.delenv("LADO_REPOS", raising=False)
    assert client.get("/api/repos-folder").json() == {"path": None}
    monkeypatch.setenv("LADO_REPOS", str(tmp_path))
    assert client.get("/api/repos-folder").json() == {"path": str(tmp_path)}
    monkeypatch.setenv("LADO_REPOS", "code")
    assert client.get("/api/repos-folder").json() == {"path": None}


# Recent folders


def test_recent_folders_are_the_folders_of_past_sessions_latest_start_first(
    client, repo, tmp_path, fake_tmux
):
    other = agent_helpers.init_repo(tmp_path / "other")
    runtime.start_session(str(repo), "a", None, provider="claude")
    runtime.start_session(str(other), "b", "plan", provider="claude")
    runtime.start_session(str(repo), "c", None, kit_names=["default"], provider="claude")
    runtime.stop_session("a")
    runtime.start_session(str(repo), "a", None)  # resumed: the latest start
    recent = client.get("/api/folders/recent").json()
    assert [(r["path"], r["session"]["name"]) for r in recent] == [
        (str(repo), "a"),
        (str(other), "b"),
    ]
    assert recent[1]["session"]["permission_mode"] == "plan"


def test_recent_folders_are_at_most_ten(client, tmp_path, fake_tmux):
    for n in range(12):
        runtime.start_session(
            str(agent_helpers.init_repo(tmp_path / f"r{n}")), None, None, provider="claude"
        )
    recent = client.get("/api/folders/recent").json()
    assert [r["session"]["name"] for r in recent] == [f"r{n}" for n in range(11, 1, -1)]


def test_recent_folders_without_a_database_are_none(client):
    assert client.get("/api/folders/recent").json() == []


# Kits


def _kit(base: Path, name: str, text: str) -> Path:
    kit = base / name
    kit.mkdir(parents=True)
    (kit / "kit.yaml").write_text(text)
    return kit


def test_kits_are_the_installed_and_the_built_in_ones(client, tmp_path):
    team = _kit(tmp_path / "dev", "team", "name: team\nversion: 9.9.9\ndescription: ours\n")
    broken = _kit(tmp_path / "dev", "broken", "name: broken\nnope: 1\n")
    default = _kit(tmp_path / "dev", "default", "name: default\nversion: 2.0.0\n")
    for folder in (team, broken, default):
        state.add_kit(state.InstalledKit(folder.name, folder=str(folder)))
    kits = {k["name"]: k for k in client.get("/api/kits").json()}
    assert sorted(kits) == ["broken", "default", "team"]
    assert kits["team"] == {
        "name": "team",
        "version": "9.9.9",
        "description": "ours",
        "valid": True,
        "problem": None,
    }
    assert kits["default"]["version"] == "2.0.0"  # the installed one shadows the built-in one
    assert not kits["broken"]["valid"]
    assert "nope" in kits["broken"]["problem"]


def test_the_kit_list_ignores_a_folder(client, repo):
    _kit(repo / ".lado" / "kits", "team", "name: team\nversion: 1.0.0\n")
    answer = client.get("/api/kits", params={"where": str(repo)})
    assert answer.status_code == 200
    assert answer.json() == client.get("/api/kits").json()
    assert [k["name"] for k in answer.json()] == ["default"]


def test_kits_never_make_or_migrate_lado_db(client, lado_home):
    """The server never migrates: without lado.db no kit is installed, and the file stays
    unmade; a database of another schema is 503."""
    names = [k["name"] for k in client.get("/api/kits").json()]
    assert names == ["default"]
    assert not (lado_home / "lado.db").exists()
    state.list_sessions()  # creates lado.db
    agent_helpers.previous_schema()
    answer = client.get("/api/kits")
    assert answer.status_code == 503
    assert state.schema_version() == state.SCHEMA_VERSION - 1


def test_kits_are_listed_without_fetching_their_packs(client, tmp_path, monkeypatch):
    kit = _kit(
        tmp_path / "kits",
        "team",
        "name: team\nversion: 1.0.0\ndependencies:\n  skills:\n"
        "    sp: https://example.com/superpowers.git@v1\n",
    )
    agent_helpers.install_kit(kit)

    def no_git(*args, **kwargs):
        raise AssertionError(f"git ran: {args}")

    monkeypatch.setattr(gitcache, "_git", no_git)
    kits = {k["name"]: k for k in client.get("/api/kits").json()}
    assert (kits["team"]["valid"], kits["team"]["problem"]) == (True, None)


# Providers


def test_providers_are_lados_registry_with_their_status(client, monkeypatch):
    statuses = {
        "claude": doctor.ProviderStatus(True, "2.1.287", "2.1.287 (Claude Code)", "2.1.287", ""),
        "codex": doctor.ProviderStatus(True, "0.162.0", "codex-cli 0.162.0", "0.162", ""),
        "kilo": doctor.ProviderStatus(False, "", "`kilo` not found on PATH", "7.2", ""),
        "opencode": doctor.ProviderStatus(True, "1.18.34", "1.18.34", "1.18", ""),
    }
    monkeypatch.setattr(doctor, "provider_status", lambda p, which: statuses[p.name])
    answer = client.get("/api/providers").json()
    assert [p["name"] for p in answer] == providers.names()
    claude, codex, kilo, opencode = answer
    assert (codex["title"], codex["version"], codex["tested_version"]) == (
        "Codex CLI",
        "0.162.0",
        "0.162",
    )
    assert claude == {
        "name": "claude",
        "title": "Claude Code",
        "permission_modes": list(providers.get("claude").permission_modes),
        "install_hint": providers.get("claude").install_hint,
        "installed": True,
        "version": "2.1.287",
        "detail": "2.1.287 (Claude Code)",
        "tested_version": "2.1.287",
        "warning": "",
    }
    assert "default" not in kilo
    assert (kilo["installed"], kilo["detail"]) == (
        False,
        "`kilo` not found on PATH",
    )
    assert (opencode["title"], opencode["installed"], opencode["version"]) == (
        "OpenCode",
        True,
        "1.18.34",
    )


@pytest.mark.parametrize(
    "path", ["/api/folders?path=/", "/api/folders/recent", "/api/kits", "/api/providers"]
)
def test_the_launch_lookups_need_the_token(client, path):
    client.cookies.clear()
    assert client.get(path).status_code == 401


# Starting, resuming, stopping and forgetting


def launch(client, path, **given):
    return client.post(
        "/api/sessions", json={"where": {"kind": "folder", "path": str(path)}, **given}
    )


def test_a_session_starts_from_the_api(client, repo, fake_tmux):
    answer = launch(
        client, repo, name="s", kits=["default"], provider="kilo", without=["agent:worker"]
    )
    assert answer.status_code == 200, answer.text
    started = answer.json()
    assert (started["resumed"], started["changes"], started["problems"]) == (False, [], [])
    sess = started["session"]
    assert (sess["name"], sess["repo"], sess["agents"]) == ("s", str(repo), 1)
    assert (sess["kits"], sess["provider"], sess["permission_mode"], sess["without"]) == (
        ["default"],
        "kilo",
        None,
        ["agent:worker"],
    )
    assert state.get_agent("s", "supervisor").provider == "kilo"
    assert fake_tmux[0][0] == "new_session"


def test_a_start_says_who_leads_and_what_holds_the_supervisor(
    client, repo, fake_tmux, claude_config
):
    claude_config.trust()  # Claude Code trusts no folder
    answer = launch(client, repo, name="s", provider="claude")
    assert answer.status_code == 200, answer.text
    started = answer.json()
    assert started["lead"] == "lead: supervisor of kit default"
    assert started["warnings"] == [
        f'Claude Code asks whether to trust {repo}: in its terminal choose "Yes, I trust '
        'this folder" (Enter alone answers "No, exit" and closes the agent)'
    ]


def test_the_first_start_makes_the_database(client, repo, fake_tmux, lado_home):
    assert not (lado_home / "lado.db").exists()
    assert client.get("/api/sessions").json() == []
    assert launch(client, repo, provider="kilo").status_code == 200
    assert [s["name"] for s in client.get("/api/sessions").json()] == ["my-repo"]


@pytest.mark.parametrize("status", ["running", "stopped"])
def test_a_start_under_a_taken_name_is_409_with_that_sessions_status_and_folder(
    client, repo, fake_tmux, status
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    if status == "stopped":
        runtime.stop_session("s")
    answer = launch(client, repo, name="s")
    assert answer.status_code == 409
    detail = answer.json()["detail"]
    shown = "loop_down" if status == "running" else status  # no loop runs in these tests
    assert detail["status"] == shown and detail["repo"] == str(repo)
    assert f'session "s" exists already ({shown}, in {repo})' in detail["message"]


def test_a_start_the_core_refuses_is_400_with_its_reason(client, tmp_path, repo, fake_tmux):
    answer = launch(client, tmp_path)
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        f"{tmp_path} is not inside a git repository",
    )
    answer = launch(client, repo, provider="kilo", permission_mode="dontAsk")
    assert answer.status_code == 400
    assert 'permission mode "dontAsk" is not supported by Kilo CLI' in answer.json()["detail"]


def test_a_start_without_provider_goes_by_the_cores_rule(client, repo, fake_tmux):
    answer = launch(client, repo, name="a")  # the agents' PATH has every CLI, no history
    assert answer.status_code == 400
    assert "give one with --provider NAME" in answer.json()["detail"]
    assert state.get_session("a") is None
    runtime.start_session(str(repo), "b", None, "opencode")
    answer = launch(client, repo, name="c")
    assert answer.status_code == 200, answer.text
    assert answer.json()["session"]["provider"] == "opencode"


def test_a_name_in_two_kits_is_refused_with_the_ways_to_switch_one_off(client, repo, fake_tmux):
    for name in ("a", "b"):
        kit = repo.parent / "kits" / name
        (kit / "agents").mkdir(parents=True)
        (kit / "kit.yaml").write_text(f"name: {name}\nversion: 1.0.0\n")
        (kit / "agents" / "rev.md").write_text("---\nname: rev\ndescription: d\n---\n")
        agent_helpers.install_kit(kit)
    answer = launch(client, repo, kits=["a", "b"], provider="claude")
    assert answer.status_code == 400
    detail = answer.json()["detail"]
    assert detail["switch_off"] == ["agent:rev@a", "agent:rev@b"]
    assert detail["message"].startswith('agent "rev" is defined by two kits: a (')
    assert client.get("/api/sessions").json() == []
    assert (
        launch(
            client, repo, kits=["a", "b"], without=["agent:rev@b"], provider="claude"
        ).status_code
        == 200
    )
    runtime.stop_session("my-repo")
    answer = client.post("/api/sessions/my-repo/resume", json={"without": []})
    assert answer.status_code == 400
    assert answer.json()["detail"]["switch_off"] == ["agent:rev@a", "agent:rev@b"]
    schema = client.get("/openapi.json").json()
    for path in ("/api/sessions", "/api/sessions/{name}/resume"):
        refused = schema["paths"][path]["post"]["responses"]["400"]
        assert refused["content"]["application/json"]["schema"]["$ref"].endswith("/Refused")


def test_a_kit_not_found_says_how_to_move_from_sources_yaml(client, repo, fake_tmux, lado_home):
    lado_home.mkdir(exist_ok=True)
    (lado_home / "sources.yaml").write_text(
        "sources:\n- {name: dev, kind: path, location: /nowhere/dev}\n"
    )
    answer = launch(client, repo, kits=["mine"], provider="claude")
    assert answer.status_code == 400
    refused = answer.json()["detail"]
    assert refused["switch_off"] == []
    detail = refused["message"]
    assert detail.startswith('kit "mine" not found; looked in ')
    assert f"{lado_home / 'sources.yaml'} is no longer read" in detail
    assert client.get("/api/sessions").json() == []


def test_only_a_folder_and_a_full_path_are_taken(client, repo, fake_tmux):
    answer = client.post("/api/sessions", json={"where": {"kind": "project", "path": "x"}})
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        'where of kind "project" is not supported yet',
    )
    answer = launch(client, "some/where")
    assert answer.status_code == 400 and "full path" in answer.json()["detail"]
    assert client.get("/api/sessions").json() == []


def test_a_resume_replaces_settings_and_says_what_changed_and_what_cannot_go_on(
    client, repo, fake_tmux
):
    kit = repo.parent / "kits" / "team"
    (kit / "agents").mkdir(parents=True)
    (kit / "kit.yaml").write_text("name: team\nversion: 1.0.0\n")
    (kit / "agents" / "rev.md").write_text("---\nname: rev\ndescription: d\n---\nYou review.\n")
    (kit / "flows").mkdir()
    (kit / "flows" / "ship.yaml").write_text(
        "name: ship\ndescription: d\nstart: build\nstates:\n"
        "  build:\n    agent: rev\n    do: Build.\n    outcomes: {done: end}\n"
        "  end:\n    end: true\n"
    )
    agent_helpers.install_kit(kit)
    runtime.start_session(str(repo), "s", None, kit_names=["default", "team"], provider="claude")
    runs.start("s", "ship", "Add x", name="x")
    runtime.stop_session("s")
    answer = client.post(
        "/api/sessions/s/resume", json={"kits": ["default"], "permission_mode": "plan"}
    )
    assert answer.status_code == 200, answer.text
    started = answer.json()
    assert started["resumed"]
    assert started["changes"] == ["permission mode: none -> plan", "kits: default, team -> default"]
    assert [p for p in started["problems"] if "ship/x" in p]
    assert started["session"]["status"] != "stopped"


def test_an_empty_list_of_kits_is_refused_not_replaced(client, repo, fake_tmux):
    answer = launch(client, repo, kits=[])
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        "a session needs at least one kit",
    )
    assert client.get("/api/sessions").json() == []
    runtime.start_session(str(repo), "s", None, kit_names=["default"], provider="claude")
    runtime.stop_session("s")
    answer = client.post("/api/sessions/s/resume", json={"kits": []})
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        "a session needs at least one kit",
    )
    assert state.get_session("s").stopped_at


def test_a_resume_of_an_unknown_session_is_404(client, repo, fake_tmux):
    runtime.start_session(str(repo), "other", None, provider="claude")
    assert client.post("/api/sessions/s/resume", json={}).status_code == 404


def test_a_resume_of_a_running_session_is_400(client, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    answer = client.post("/api/sessions/s/resume", json={})
    assert answer.status_code == 400 and "already running" in answer.json()["detail"]


def _humans(session: str) -> list[str]:
    return [m.body for m in state.list_messages(session) if m.sender == state.HUMAN]


def test_a_start_with_a_prompt_queues_the_humans_first_message(client, repo, fake_tmux):
    answer = launch(client, repo, name="s", provider="kilo", prompt=" Take LAD-19\n")
    assert answer.status_code == 200, answer.text
    assert _humans("s") == ["Take LAD-19"]


def test_a_resume_with_a_prompt(client, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    answer = client.post("/api/sessions/s/resume", json={"prompt": "Continue"})
    assert answer.status_code == 200, answer.text
    last = state.list_messages("s")[-1]
    assert (last.sender, last.body) == ("human", "Continue")


def test_an_empty_prompt_is_400_with_the_cores_text(client, repo, fake_tmux):
    answer = launch(client, repo, name="s", provider="kilo", prompt="  ")
    assert answer.status_code == 400
    assert answer.json()["detail"] == "the first message is empty"
    assert state.get_session("s") is None
    runtime.start_session(str(repo), "s", None, provider="claude")
    runtime.stop_session("s")
    answer = client.post("/api/sessions/s/resume", json={"prompt": ""})
    assert answer.status_code == 400
    assert answer.json()["detail"] == "the first message is empty"
    assert state.get_session("s").stopped_at


def test_stop_shows_what_it_does_then_does_it(client, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    worker = runtime.spawn_worker("s", "task", name="w1")
    runtime.send_message("s", "supervisor", "w1", "hi")
    preview = client.get("/api/sessions/s/stop-preview").json()
    assert preview == {
        "agents": ["supervisor", "w1"],
        "dropped": 2,  # and w1's task
        "open_runs": [],
        "worktrees": [{"path": worker.cwd, "branch": worker.branch}],
    }
    assert client.post("/api/sessions/s/stop").json() == {"dropped": 2}
    assert state.get_session("s").stopped_at
    answer = client.post("/api/sessions/s/stop")
    assert answer.status_code == 400 and "stopped already" in answer.json()["detail"]
    assert client.get("/api/sessions/nope/stop-preview").status_code == 404


def test_forget_shows_what_it_drops_and_needs_force_for_open_runs(client, repo, fake_tmux):
    runtime.start_session(str(repo), "s", None, provider="claude")
    run = state.Run("s", "feature/x", "feature", "{}", {}, "do x", "design", "/w", "b")
    state.add_run(run, [("lado", state.FLOW_START, "at design")], None)
    answer = client.delete("/api/sessions/s")
    assert answer.status_code == 400 and "is not stopped" in answer.json()["detail"]
    runtime.stop_session("s")
    assert client.get("/api/sessions/s/forget-preview").json() == {
        "open_runs": ["feature/x"],
        "worktrees": [],
    }
    answer = client.delete("/api/sessions/s")
    assert answer.status_code == 400 and "has open runs: feature/x" in answer.json()["detail"]
    answer = client.delete("/api/sessions/s", params={"force": True})
    assert answer.json() == {"open_runs": ["feature/x"], "worktrees": []}
    assert state.get_session("s") is None
    assert client.delete("/api/sessions/s").status_code == 404


CHANGES = [
    ("post", "/api/sessions"),
    ("post", "/api/sessions/s/resume"),
    ("post", "/api/sessions/s/stop"),
    ("delete", "/api/sessions/s"),
]


@pytest.mark.parametrize(("method", "path"), CHANGES)
def test_a_launch_change_needs_the_token_and_the_servers_own_origin(
    client, repo, fake_tmux, method, path
):
    runtime.start_session(str(repo), "s", None, provider="claude")
    payload = {"where": {"kind": "folder", "path": str(repo)}} if path == "/api/sessions" else {}
    send = getattr(client, method)
    kwargs = {"json": payload} if method == "post" else {}
    del client.headers["origin"]
    assert send(path, **kwargs).status_code == 403
    client.headers["origin"] = "http://evil.example"
    assert send(path, **kwargs).status_code == 403
    client.headers["origin"] = OWN
    client.cookies.clear()
    assert send(path, **kwargs).status_code == 401
    assert state.get_session("s").stopped_at is None


@pytest.mark.parametrize("path", ["/api/sessions/s/stop-preview", "/api/sessions/s/forget-preview"])
def test_the_previews_need_the_token(client, path):
    client.cookies.clear()
    assert client.get(path).status_code == 401


# From scratch (openspec change start-from-scratch)


def scratch_target(client, text, path=None) -> dict:
    params = {"text": text, **({"path": str(path)} if path is not None else {})}
    answer = client.get("/api/scratch-target", params=params)
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_a_name_checked(client, git_config, tmp_path, monkeypatch, installed):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    installed.intersection_update({"kilo"})
    assert scratch_target(client, "Сайт кофейни") == {
        "path": str(tmp_path / "home" / "lado" / "sait-kofeini"),
        "name": "sait-kofeini",
        "title": "Сайт кофейни",
        "problem": None,
        "state": "new",
        "text": "a new folder",
        "author": None,
        "name_state": "free",
        "provider": {"name": "kilo", "reason": "only_installed"},
        "warning": None,
    }


def test_the_default_folder_is_in_the_repositories_folder(
    client, git_config, tmp_path, monkeypatch
):
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "projects"))
    info = scratch_target(client, "coffee-site")
    assert (info["path"], info["title"]) == (str(tmp_path / "projects" / "coffee-site"), None)


def test_a_folder_given_is_checked(client, git_config, tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.txt").write_text("x")
    info = scratch_target(client, "Notes", tmp_path / "notes")
    assert (info["path"], info["state"], info["name"]) == (
        str(tmp_path / "notes"),
        "not_empty",
        "notes",
    )
    assert info["text"] == f"{tmp_path / 'notes'} is not empty: choose a new or empty folder"
    (tmp_path / "empty").mkdir()
    assert scratch_target(client, "x", tmp_path / "empty")["state"] == "empty"
    inside = scratch_target(client, "x", agent_helpers.init_repo(tmp_path / "app") / "site")
    assert inside["state"] == "inside_repo"


def test_a_refused_name_without_a_folder_has_none(client, git_config):
    info = scratch_target(client, "東京")
    assert info["problem"] == "the name needs a Latin letter or digit for its folder: type one"
    assert (info["path"], info["name"], info["state"], info["name_state"]) == (
        None,
        None,
        None,
        None,
    )


def test_a_refused_name_with_a_folder_checks_the_folder(client, git_config, tmp_path):
    info = scratch_target(client, "", tmp_path / "shop")
    assert (info["problem"], info["path"], info["state"]) == (
        "type a name",
        str(tmp_path / "shop"),
        "new",
    )


@pytest.mark.parametrize(
    ("container", "command"),
    [(None, 'git config --global user.name "Your Name"'), ("1", "docker compose up -d")],
)
def test_no_author_in_the_target(client, git_config, tmp_path, monkeypatch, container, command):
    if container:
        monkeypatch.setenv("LADO_CONTAINER", container)
    git_config.write_text("")
    author = scratch_target(client, "shop", tmp_path / "shop")["author"]
    assert author["text"] == (
        "git doesn't know who signs the agents' commits: it has no user.name or user.email"
    )
    assert author["hint"]["command"].startswith(command)


def test_the_name_taken_by_a_session_of_another_folder(
    client, git_config, repo, tmp_path, fake_tmux
):
    runtime.start_session(str(repo), "shop", None, provider="claude")
    assert scratch_target(client, "Shop", tmp_path / "shop")["name_state"] == "taken_elsewhere"


def test_in_a_container_a_fresh_start_outside_the_repositories_folder_warns(
    client, git_config, tmp_path, monkeypatch
):
    monkeypatch.setenv("LADO_CONTAINER", "1")
    monkeypatch.setenv("LADO_REPOS", str(tmp_path / "projects"))
    assert scratch_target(client, "shop")["warning"] is None
    outside = scratch_target(client, "shop", tmp_path / "shop")["warning"]
    assert outside == runtime.OUTSIDE_REPOS.format(folder=tmp_path / "projects")


def test_a_relative_folder_for_a_fresh_start_is_400(client, git_config):
    answer = client.get("/api/scratch-target", params={"text": "x", "path": "some/where"})
    assert answer.status_code == 400 and "full path" in answer.json()["detail"]


def start_scratch(client, path, **given):
    return client.post(
        "/api/sessions", json={"where": {"kind": "scratch", "path": str(path)}, **given}
    )


def test_a_fresh_start_from_the_api(client, git_config, tmp_path, fake_tmux):
    path = tmp_path / "lado" / "sait-kofeini"
    answer = start_scratch(client, path, name="sait-kofeini", title="Сайт кофейни", provider="kilo")
    assert answer.status_code == 200, answer.text
    sess = answer.json()["session"]
    assert (sess["name"], sess["repo"], sess["title"]) == (
        "sait-kofeini",
        os.path.realpath(path),
        "Сайт кофейни",
    )
    assert runtime.check_repo(str(path)) == os.path.realpath(path)


def test_a_fresh_start_refused_before_the_repository_is_400_and_makes_nothing(
    client, git_config, tmp_path, repo, fake_tmux
):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.txt").write_text("x")
    answer = start_scratch(client, tmp_path / "notes", name="notes", provider="kilo")
    assert (answer.status_code, answer.json()["detail"]) == (
        400,
        f"{tmp_path / 'notes'} is not empty: choose a new or empty folder",
    )
    assert not (tmp_path / "notes" / ".git").exists()
    runtime.start_session(str(repo), "shop", None, provider="claude")
    answer = start_scratch(client, tmp_path / "shop", name="shop", provider="kilo")
    assert answer.status_code == 400 and 'session "shop" was started in' in answer.json()["detail"]
    git_config.write_text("")
    answer = start_scratch(client, tmp_path / "cafe", name="cafe", provider="kilo")
    assert answer.status_code == 400 and "user.name or user.email" in answer.json()["detail"]
    assert not (tmp_path / "shop").exists() and not (tmp_path / "cafe").exists()


def test_a_fresh_start_refused_after_the_repository_keeps_it(
    client, git_config, tmp_path, fake_tmux
):
    answer = start_scratch(client, tmp_path / "shop", name="shop", provider="nosuch")
    assert answer.status_code == 400
    assert runtime.check_repo(str(tmp_path / "shop")) == os.path.realpath(tmp_path / "shop")


def test_an_empty_folder_in_the_folder_check(client, git_config, tmp_path):
    (tmp_path / "empty").mkdir()
    info = folder(client, tmp_path / "empty")
    assert (info["ok"], info["problem_kind"], info["scratch"]) == (False, "not_repo", True)
    assert folder(client, tmp_path / "new")["scratch"] is True  # missing


def test_a_folder_that_cannot_start_from_scratch(client, git_config, tmp_path, repo):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.txt").write_text("x")
    assert folder(client, tmp_path / "notes")["scratch"] is False
    assert folder(client, repo / "nope")["scratch"] is False  # missing, inside a repository
    assert folder(client, repo)["scratch"] is False
